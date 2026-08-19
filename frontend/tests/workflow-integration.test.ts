import assert from "node:assert/strict";
import test from "node:test";
import { mockReceipts } from "../data/mock-receipts";
import {
  ApiRequestError,
  createApplyCorrectionRequest,
  createVietReceiptApi,
  getApiErrorMessage,
  uploadReceipt,
} from "../lib/vietreceipt-api";
import { createReceiptPoller } from "../lib/receipt-polling";
import {
  canVerifyReceipt,
  createFieldInteractionState,
  getAdjacentField,
  getFieldInteractionState,
  getReceiptStatePresentation,
  isPollingStatus,
  parseCorrectionInput,
  reconcileFieldStatesAfterCorrection,
  reduceFieldInteraction,
  replaceReceiptField,
} from "../lib/receipt-workflow";
import {
  createReviewInteractionSession,
  createReviewTelemetryEvent,
  recordReviewInteraction,
} from "../lib/review-telemetry";
import type {
  ApiCanonicalFields,
  ApiReceiptDetail,
  ReceiptDetail,
  ReceiptField,
} from "../types/receipt";

const reviewReceipt = mockReceipts.find((receipt) => receipt.status === "NEEDS_REVIEW")!;
const uploadedReceipt = mockReceipts.find((receipt) => receipt.status === "UPLOADED")!;
const processingReceipt = mockReceipts.find((receipt) => receipt.status === "PROCESSING")!;
const verifiedReceipt = mockReceipts.find((receipt) => receipt.status === "VERIFIED")!;
const failedReceipt = mockReceipts.find((receipt) => receipt.status === "FAILED")!;

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("upload sends canonical multipart file and returns the Backend receipt summary", async () => {
  let request: { input: string; init?: RequestInit } | undefined;
  const file = new File(["receipt"], "receipt.jpg", { type: "image/jpeg" });
  const summary = {
    receipt_id: "11111111-1111-4111-8111-111111111111",
    original_filename: "receipt.jpg",
    status: "UPLOADED",
    merchant_name: null,
    receipt_date: null,
    total_amount: null,
    created_at: "2026-08-17T01:00:00Z",
    verified_at: null,
  };
  const fetcher = async (input: string | URL | Request, init?: RequestInit) => {
    request = { input: String(input), init };
    return response(summary, 201);
  };

  assert.deepEqual(await uploadReceipt(fetcher, file), summary);
  assert.equal(request?.input, "/api/v1/receipts");
  assert.equal(request?.init?.method, "POST");
  assert.ok(request?.init?.body instanceof FormData);
  assert.equal((request?.init?.body as FormData).get("file"), file);
  assert.equal(Object.hasOwn(request?.init?.headers ?? {}, "content-type"), false);
});

for (const [status, expected] of [
  [413, "File vượt quá kích thước cho phép."],
  [415, "File không phải định dạng ảnh được hỗ trợ."],
] as const) {
  test(`upload ${status} maps to a meaningful user action`, async () => {
    const fetcher = async () => response({ error: { code: `HTTP_${status}`, message: "rejected" } }, status);
    const file = new File(["x"], "receipt.bin", { type: "application/octet-stream" });
    await assert.rejects(
      uploadReceipt(fetcher, file),
      (error) => error instanceof ApiRequestError && error.status === status && getApiErrorMessage(error) === expected,
    );
  });
}

test("all five public receipt states have explicit W2 presentations", () => {
  assert.match(getReceiptStatePresentation(uploadedReceipt.status).description, /chờ hệ thống/i);
  assert.match(getReceiptStatePresentation(processingReceipt.status, "OCR").description, /nhận dạng văn bản/i);
  assert.match(getReceiptStatePresentation(reviewReceipt.status).description, /năm trường/i);
  assert.match(getReceiptStatePresentation(verifiedReceipt.status).description, /chỉ đọc/i);
  assert.match(getReceiptStatePresentation(failedReceipt.status).description, /Backend/i);
  assert.equal(isPollingStatus("UPLOADED"), true);
  assert.equal(isPollingStatus("PROCESSING"), true);
  assert.equal(isPollingStatus("NEEDS_REVIEW"), false);
});

test("polling stops as soon as Backend returns a terminal receipt state", async () => {
  const scheduled: Array<() => void> = [];
  const receipts: ReceiptDetail[] = [];
  let loads = 0;
  const poller = createReceiptPoller(
    async () => {
      loads += 1;
      return reviewReceipt;
    },
    {
      schedule: (callback) => {
        scheduled.push(callback);
        return scheduled.length as unknown as ReturnType<typeof setTimeout>;
      },
      cancel: () => undefined,
      onReceipt: (receipt) => receipts.push(receipt),
      onError: (error) => assert.fail(String(error)),
    },
  );

  poller.start(processingReceipt);
  assert.equal(scheduled.length, 1);
  scheduled.shift()!();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(loads, 1);
  assert.deepEqual(receipts, [reviewReceipt]);
  assert.equal(scheduled.length, 0);
});

test("polling cleanup cancels the active timer and restart never duplicates it", () => {
  let nextTimer = 0;
  const activeTimers = new Set<number>();
  const poller = createReceiptPoller(async () => processingReceipt, {
    schedule: () => {
      nextTimer += 1;
      activeTimers.add(nextTimer);
      return nextTimer as unknown as ReturnType<typeof setTimeout>;
    },
    cancel: (timer) => activeTimers.delete(timer as unknown as number),
    onReceipt: () => undefined,
    onError: (error) => assert.fail(String(error)),
  });

  poller.start(processingReceipt);
  assert.equal(activeTimers.size, 1);
  poller.start(uploadedReceipt);
  assert.equal(activeTimers.size, 1);
  poller.stop();
  assert.equal(activeTimers.size, 0);
});

test("field-specific reducer exposes EDITING, SAVING, SAVED, error and stale phases", () => {
  const field = reviewReceipt.fields!.total_amount;
  const initial = createFieldInteractionState(field);
  const editing = reduceFieldInteraction(initial, { type: "EDIT", value: 113000, valueStatus: "PRESENT" });
  assert.equal(editing.phase, "EDITING");
  const saving = reduceFieldInteraction(editing, { type: "SAVE" });
  assert.equal(saving.phase, "SAVING");
  const savedField = { ...field, effective_needs_review: false, updated_at: "2026-08-17T02:00:00Z" } as ReceiptField;
  assert.equal(reduceFieldInteraction(saving, { type: "SAVED", field: savedField }).phase, "SAVED");
  assert.equal(reduceFieldInteraction(saving, { type: "SAVE_ERROR", message: "bad" }).phase, "SAVE_ERROR");
  assert.equal(reduceFieldInteraction(saving, { type: "STALE", message: "stale" }).phase, "STALE");
});

test("prefetched fields can APPLY their effective value and change status before text editing", () => {
  const field = reviewReceipt.fields!.total_amount;
  const initial = getFieldInteractionState({}, field);

  assert.equal(initial.value, field.effective_value);
  assert.equal(initial.valueStatus, field.effective_status);
  assert.deepEqual(
    createApplyCorrectionRequest(field, initial.value, initial.valueStatus),
    {
      operation: "APPLY",
      value_status: field.effective_status,
      value: field.effective_value,
      expected_updated_at: field.updated_at,
    },
  );

  const saving = reduceFieldInteraction(initial, { type: "SAVE" });
  assert.equal(saving.phase, "SAVING");
  assert.equal(saving.value, field.effective_value);

  const statusChanged = reduceFieldInteraction(initial, {
    type: "EDIT",
    value: null,
    valueStatus: "NOT_PRESENT",
  });
  assert.equal(statusChanged.phase, "EDITING");
  assert.equal(statusChanged.value, null);
  assert.equal(statusChanged.valueStatus, "NOT_PRESENT");
});

test("authoritative correction refresh preserves unsaved drafts on other fields", () => {
  const merchantField = reviewReceipt.fields!.merchant_name;
  const totalField = reviewReceipt.fields!.total_amount;
  const merchantDraft = reduceFieldInteraction(
    createFieldInteractionState(merchantField),
    { type: "EDIT", value: "Cửa hàng đang sửa", valueStatus: "PRESENT" },
  );
  const totalSaving = reduceFieldInteraction(
    createFieldInteractionState(totalField),
    { type: "SAVE" },
  );
  const latestFields = {
    ...reviewReceipt.fields!,
    total_amount: {
      ...totalField,
      corrected_value: 113000,
      corrected_status: "PRESENT" as const,
      has_correction: true,
      effective_value: 113000,
      effective_status: "PRESENT" as const,
      effective_needs_review: false,
      updated_at: "2026-08-17T04:00:00Z",
    },
  };

  const reconciled = reconcileFieldStatesAfterCorrection(
    { merchant_name: merchantDraft, total_amount: totalSaving },
    latestFields,
    "total_amount",
  );

  assert.equal(reconciled.merchant_name.phase, "EDITING");
  assert.equal(reconciled.merchant_name.value, "Cửa hàng đang sửa");
  assert.equal(reconciled.total_amount.phase, "SAVED");
  assert.equal(reconciled.total_amount.value, 113000);
});

test("correction response replaces only the field before a fresh GET supplies receipt concurrency token", async () => {
  const originalToken = reviewReceipt.updated_at;
  const savedField = {
    ...reviewReceipt.fields!.total_amount,
    effective_needs_review: false,
    updated_at: "2026-08-17T02:00:00Z",
  } as ReceiptField;
  const afterFieldResponse = replaceReceiptField(reviewReceipt, savedField);
  assert.equal(afterFieldResponse.fields!.total_amount.updated_at, savedField.updated_at);
  assert.equal(afterFieldResponse.updated_at, originalToken);

  const api = createVietReceiptApi({
    fetcher: async () => response({
      receipt_id: reviewReceipt.receipt_id,
      original_filename: reviewReceipt.original_filename,
      status: reviewReceipt.status,
      processing_stage: null,
      image_url: reviewReceipt.image_url,
      image_width_px: reviewReceipt.image_width_px!,
      image_height_px: reviewReceipt.image_height_px!,
      latest_ocr_run_id: reviewReceipt.latest_ocr_run_id,
      latest_kie_run_id: reviewReceipt.latest_kie_run_id,
      fields: Object.fromEntries(Object.entries(reviewReceipt.fields!).map(([key, value]) => [key, {
        field_name: value.field_name,
        ocr_run_id: value.machine.ocr_run_id,
        kie_run_id: value.machine.kie_run_id,
        raw_text: value.machine.raw_text,
        predicted_value: value.machine.predicted_value,
        normalized_value: value.machine.normalized_value,
        normalization: value.machine.normalization,
        value_status: value.machine.value_status,
        corrected_value: value.corrected_value,
        corrected_status: value.corrected_status,
        has_correction: value.has_correction,
        effective_value: value.effective_value,
        effective_status: value.effective_status,
        confidence: value.machine.confidence,
        machine_needs_review: value.machine.machine_needs_review,
        effective_needs_review: value.effective_needs_review,
        review_reasons: value.machine.review_reasons,
        review_policy_version: value.machine.review_policy_version,
        source_block_ids: value.machine.source_block_ids,
        verified: value.verified,
        updated_at: value.updated_at,
      }])) as ApiCanonicalFields,
      ocr_blocks: reviewReceipt.ocr_blocks!,
      last_error: null,
      created_at: reviewReceipt.created_at,
      updated_at: "2026-08-17T02:00:01Z",
      processed_at: reviewReceipt.processed_at,
      verified_at: null,
    } satisfies ApiReceiptDetail),
  });
  const refreshed = await api.getReceipt(reviewReceipt.receipt_id);
  assert.notEqual(refreshed.updated_at, originalToken);
});

test("validation treats Vietnamese amount separators as formatting and preserves invoice leading zeros", () => {
  assert.equal(parseCorrectionInput("total_amount", "113.000"), 113000);
  assert.equal(parseCorrectionInput("total_amount", "113 000"), 113000);
  assert.equal(parseCorrectionInput("invoice_id", "000123"), "000123");
  assert.equal(parseCorrectionInput("total_amount", "not-money"), "not-money");
});

test("verify eligibility, keyboard order and telemetry remain HITL-safe", () => {
  assert.equal(canVerifyReceipt(reviewReceipt), false);
  assert.equal(canVerifyReceipt(verifiedReceipt), false);
  assert.equal(getAdjacentField("receipt_date", 1), "total_amount");
  assert.equal(getAdjacentField("merchant_name", -1), "merchant_name");

  const event = createReviewTelemetryEvent(
    "CORRECTION_APPLIED",
    reviewReceipt.receipt_id,
    { field_name: "invoice_id", operation: "APPLY" },
    () => new Date("2026-08-17T03:00:00Z"),
  );
  assert.deepEqual(Object.keys(event).sort(), [
    "event",
    "field_name",
    "occurred_at",
    "operation",
    "receipt_id",
    "review_mode",
  ]);
  assert.equal(JSON.stringify(event).includes("raw_text"), false);
  assert.equal(JSON.stringify(event).includes("image"), false);
  assert.equal(event.review_mode, "PREFILL_FULL_REVIEW");
});

test("review telemetry starts only on explicit interaction and focuses the default field", () => {
  const idle = createReviewInteractionSession(reviewReceipt.receipt_id);
  assert.equal(idle.started, false);
  assert.equal(idle.lastFocusedField, null);

  const first = recordReviewInteraction(
    idle,
    "total_amount",
    () => new Date("2026-08-17T03:30:00Z"),
  );
  assert.deepEqual(first.events.map((event) => event.event), [
    "REVIEW_STARTED",
    "FIELD_FOCUSED",
  ]);
  assert.equal(first.events[1].field_name, "total_amount");

  const duplicate = recordReviewInteraction(first.session, "total_amount");
  assert.deepEqual(duplicate.events, []);

  const nextField = recordReviewInteraction(first.session, "merchant_name");
  assert.deepEqual(nextField.events.map((event) => event.event), ["FIELD_FOCUSED"]);
});

test("404, 409, 422 and 5xx errors produce distinct workflow guidance", () => {
  assert.match(getApiErrorMessage(new ApiRequestError("missing", 404, "NOT_FOUND")), /Không tìm thấy/i);
  assert.match(getApiErrorMessage(new ApiRequestError("stale", 409, "STALE")), /tải phiên bản mới/i);
  assert.match(getApiErrorMessage(new ApiRequestError("invalid", 422, "INVALID")), /không hợp lệ/i);
  assert.match(getApiErrorMessage(new ApiRequestError("down", 503, "UNAVAILABLE")), /tạm thời/i);
});
