import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  ApiRequestError,
  createApplyCorrectionRequest,
  createClearCorrectionRequest,
  getApiErrorMessage,
  HttpApi,
  MockApi,
  MutationOutcomeUnknownError,
  OptimisticConcurrencyError,
  parseResponse,
  projectApiExtractedField,
} from "../assets/js/api.js";
import { CORE_FIELD_TYPES } from "../assets/js/common.js";
import { MOCK_RECEIPTS, RECEIPT_IDS } from "../assets/js/mock-data.js";
import {
  canVerifyReceipt,
  createFieldState,
  createFieldStates,
  editFieldStatus,
  findFieldsForSourceBlock,
  getAdjacentField,
  reconcileStatesAfterCorrection,
} from "../assets/js/review-state.js";
import { createReviewTelemetry } from "../assets/js/review-telemetry.js";
import { saveCorrectionAndRefresh } from "../assets/js/review-workflow.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const detailSource = readFileSync(join(root, "assets/js/receipt-detail.js"), "utf8");

function freshMock() {
  return new MockApi({ receipts: MOCK_RECEIPTS, delay: 0, persist: false });
}

test("2xx malformed correction chủ động GET reload authoritative receipt", async () => {
  const originalFetch = globalThis.fetch;
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  const latestReceipt = structuredClone(receipt);
  latestReceipt.updated_at = "2026-08-25T04:00:00Z";
  const malformed = { ...receipt.fields.merchant_name, source_block_ids: ["unknown-block"] };
  let patchCalls = 0;
  globalThis.fetch = async () => {
    patchCalls += 1;
    return new Response(JSON.stringify(malformed), { status: 200, headers: { "content-type": "application/json" } });
  };
  let refreshCalls = 0;
  const api = new HttpApi();
  api.getReceipt = async () => { refreshCalls += 1; return latestReceipt; };
  try {
    const result = await saveCorrectionAndRefresh({
      api,
      receipt,
      fieldStates: createFieldStates(receipt.fields),
      fieldName: "merchant_name",
      request: {},
    });
    assert.equal(result.outcome, "REFRESHED_AFTER_UNKNOWN_MUTATION");
    assert.ok(result.error instanceof MutationOutcomeUnknownError);
    assert.equal(patchCalls, 1);
    assert.equal(refreshCalls, 1);
    assert.equal(result.receipt, latestReceipt);
    assert.equal(result.receipt.fields.merchant_name.source_block_ids.includes("unknown-block"), false);
    assert.equal(result.fieldStates.merchant_name.phase, "VIEW");
  } finally { globalThis.fetch = originalFetch; }
});

test("2xx malformed và GET reload lỗi khóa verify, không retry token cũ", async () => {
  const originalFetch = globalThis.fetch;
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  for (const field of Object.values(receipt.fields)) field.effective_needs_review = false;
  const malformed = { ...receipt.fields.merchant_name, source_block_ids: ["unknown-block"] };
  let patchCalls = 0;
  globalThis.fetch = async () => {
    patchCalls += 1;
    return new Response(JSON.stringify(malformed), { status: 200, headers: { "content-type": "application/json" } });
  };
  let refreshCalls = 0;
  const refreshError = new ApiRequestError("reload failed", 503, "UPSTREAM_ERROR");
  const api = new HttpApi();
  api.getReceipt = async () => { refreshCalls += 1; throw refreshError; };
  try {
    const result = await saveCorrectionAndRefresh({
      api,
      receipt,
      fieldStates: createFieldStates(receipt.fields),
      fieldName: "merchant_name",
      request: {},
    });
    assert.equal(result.outcome, "MUTATION_OUTCOME_UNKNOWN");
    assert.ok(result.error instanceof MutationOutcomeUnknownError);
    assert.equal(result.refreshError, refreshError);
    assert.equal(patchCalls, 1);
    assert.equal(refreshCalls, 1);
    assert.equal(result.receipt, receipt);
    assert.equal(result.receipt.fields.merchant_name.source_block_ids.includes("unknown-block"), false);
    assert.equal(result.fieldStates.merchant_name.phase, "STALE");
    assert.equal(canVerifyReceipt(result.receipt, result.fieldStates), false);
    assert.match(detailSource, /result.outcome === "MUTATION_OUTCOME_UNKNOWN"/);
    assert.match(detailSource, /current.phase === "SAVING" || staleMessage/);
  } finally { globalThis.fetch = originalFetch; }
});

test("upload success gửi multipart file và trả receipt_id", async () => {
  const originalFetch = globalThis.fetch;
  let captured = null;
  globalThis.fetch = async (url, init) => {
    captured = { url, init };
    return new Response(JSON.stringify({ receipt_id: RECEIPT_IDS.uploaded, original_filename: "receipt.jpg", status: "UPLOADED", merchant_name: null, receipt_date: null, total_amount: null, created_at: "2026-08-23T00:00:00Z", verified_at: null }), { status: 201, headers: { "content-type": "application/json" } });
  };
  try {
    const result = await new HttpApi().uploadReceipt(new File(["image"], "receipt.jpg", { type: "image/jpeg" }));
    assert.equal(result.receipt_id, RECEIPT_IDS.uploaded);
    assert.equal(captured.url, "/api/v1/receipts");
    assert.ok(captured.init.body instanceof FormData);
    assert.equal(captured.init.body.get("file").name, "receipt.jpg");
  } finally { globalThis.fetch = originalFetch; }
});

test("413 và 415 có message upload có nghĩa", async () => {
  for (const [status, expected] of [[413, "kích thước"], [415, "định dạng"]]) {
    await assert.rejects(() => parseResponse(new Response(JSON.stringify({ error: { code: `HTTP_${status}`, message: "rejected" } }), { status })), ApiRequestError);
    assert.match(getApiErrorMessage(new ApiRequestError("rejected", status, `HTTP_${status}`)), new RegExp(expected));
  }
});

test("năm public receipt states có fixture render", () => {
  assert.deepEqual(new Set(MOCK_RECEIPTS.map((receipt) => receipt.status)), new Set(["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"]));
  for (const label of ["Đã tải hóa đơn", "Đang chuẩn hóa ảnh", "NEEDS_REVIEW", "VERIFIED", "FAILED"]) assert.match(detailSource, new RegExp(label));
});

test("polling chỉ bounded ở UPLOADED/PROCESSING và cleanup khi pagehide", () => {
  assert.match(detailSource, /\["UPLOADED", "PROCESSING"\]\.includes/);
  assert.match(detailSource, /pollAttempt >= 120/);
  assert.match(detailSource, /pagehide/);
  assert.match(detailSource, /clearTimeout\(pollingTimer\)/);
});

test("APPLY prefilled value hoạt động không cần edit trước", async () => {
  const api = freshMock();
  const detail = await api.getReceipt(RECEIPT_IDS.review);
  const field = detail.fields.invoice_id;
  const request = createApplyCorrectionRequest(field, field.effective_value, field.effective_status);
  const saved = await api.updateCorrection(detail.receipt_id, field.field_name, request);
  assert.equal(saved.has_correction, true);
  assert.equal(saved.effective_value, "00018427");
});

test("đổi status trực tiếp tạo EDITING state hợp lệ", () => {
  const field = MOCK_RECEIPTS[0].fields.total_amount;
  const changed = editFieldStatus(createFieldState(field), "NOT_PRESENT");
  assert.equal(changed.phase, "EDITING");
  assert.equal(changed.value, null);
  assert.equal(changed.resolved, true);
});

test("CLEAR correction trở lại machine normalized authority", async () => {
  const api = freshMock();
  const detail = await api.getReceipt(RECEIPT_IDS.review);
  const field = detail.fields.invoice_id;
  const applied = await api.updateCorrection(detail.receipt_id, field.field_name, createApplyCorrectionRequest(field, "00018427", "PRESENT"));
  const cleared = await api.updateCorrection(detail.receipt_id, field.field_name, createClearCorrectionRequest(applied));
  assert.equal(cleared.has_correction, false);
  assert.equal(cleared.effective_value, cleared.normalized_value);
  assert.notEqual(cleared.effective_value, cleared.predicted_value === null ? "fallback" : null);
});

test("successful correction refresh giữ draft field khác", () => {
  const detail = structuredClone(MOCK_RECEIPTS[0]);
  const states = createFieldStates(detail.fields);
  states.merchant_name = { ...states.merchant_name, phase: "EDITING", value: "Draft chưa lưu" };
  const reconciled = reconcileStatesAfterCorrection(states, detail.fields, "total_amount");
  assert.equal(reconciled.merchant_name.value, "Draft chưa lưu");
  assert.equal(reconciled.merchant_name.phase, "EDITING");
  assert.equal(reconciled.total_amount.phase, "SAVED");
});

test("stale token trả OptimisticConcurrencyError và UI có nút tải phiên bản mới", async () => {
  const api = freshMock();
  const detail = await api.getReceipt(RECEIPT_IDS.review);
  const request = createApplyCorrectionRequest({ ...detail.fields.invoice_id, updated_at: "2020-01-01T00:00:00Z" }, "00018427", "PRESENT");
  await assert.rejects(() => api.updateCorrection(detail.receipt_id, "invoice_id", request), OptimisticConcurrencyError);
  assert.match(detailSource, /Tải phiên bản mới/);
  assert.match(detailSource, /không được tự retry/);
});

test("verify chỉ enable sau authoritative corrections", async () => {
  const api = freshMock();
  let detail = await api.getReceipt(RECEIPT_IDS.review);
  let states = createFieldStates(detail.fields);
  assert.equal(canVerifyReceipt(detail, states), false);
  await api.updateCorrection(detail.receipt_id, "total_amount", createApplyCorrectionRequest(detail.fields.total_amount, 325000, "PRESENT"));
  await api.updateCorrection(detail.receipt_id, "invoice_id", createApplyCorrectionRequest(detail.fields.invoice_id, "00018427", "PRESENT"));
  detail = await api.getReceipt(detail.receipt_id);
  states = createFieldStates(detail.fields);
  assert.equal(canVerifyReceipt(detail, states), true);
  const verified = await api.verifyReceipt(detail.receipt_id, detail.updated_at);
  assert.equal(verified.status, "VERIFIED");
});

test("FAILED retry chỉ có cho retryable error", async () => {
  const api = freshMock();
  const accepted = await api.retryReceipt(RECEIPT_IDS.failed);
  assert.deepEqual(accepted, { receipt_id: RECEIPT_IDS.failed, retry_accepted: true });
  const updated = await api.getReceipt(RECEIPT_IDS.failed);
  assert.equal(updated.status, "UPLOADED");
});

test("một OCR block có thể highlight nhiều canonical fields", () => {
  const fields = structuredClone(MOCK_RECEIPTS[0].fields);
  fields.merchant_address.source_block_ids.push("block_0");
  assert.deepEqual(findFieldsForSourceBlock(fields, "block_0"), ["merchant_name", "merchant_address"]);
});

test("keyboard mapping hỗ trợ save, reset và chuyển field", () => {
  assert.equal(getAdjacentField("receipt_date", 1), "total_amount");
  assert.equal(getAdjacentField("receipt_date", -1), "merchant_name");
  assert.match(detailSource, /getReviewKeyboardAction\(event\)/);
  assert.match(detailSource, /action === "SAVE"/);
  assert.match(detailSource, /action === "RESET"/);
  assert.match(detailSource, /"PREVIOUS_FIELD", "NEXT_FIELD"/);
});

test("telemetry chỉ bắt đầu ở interaction và không chứa dữ liệu nhạy cảm", () => {
  const events = [];
  const telemetry = createReviewTelemetry(RECEIPT_IDS.review, (payload) => events.push(payload));
  assert.equal(events.length, 0);
  telemetry.focusField("merchant_name");
  telemetry.editField("merchant_name");
  telemetry.correction("merchant_name", "APPLY");
  assert.deepEqual(events.map((event) => event.event), ["REVIEW_STARTED", "FIELD_FOCUSED", "FIELD_EDITED", "CORRECTION_APPLIED"]);
  for (const event of events) {
    assert.deepEqual(Object.keys(event).sort(), event.event === "CORRECTION_APPLIED" ? ["event", "field_name", "occurred_at", "operation", "receipt_id", "review_mode"] : event.event.includes("FIELD") ? ["event", "field_name", "occurred_at", "receipt_id", "review_mode"] : ["event", "occurred_at", "receipt_id", "review_mode"]);
    assert.equal(JSON.stringify(event).includes("raw_text"), false);
  }
});

test("canonical five-field model không bị giảm", () => {
  assert.deepEqual(CORE_FIELD_TYPES, ["merchant_name", "receipt_date", "total_amount", "invoice_id", "merchant_address"]);
});


test("PATCH đã lưu nhưng GET refresh lỗi giữ authoritative field và yêu cầu reload", async () => {
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  const states = createFieldStates(receipt.fields);
  states.total_amount = { ...states.total_amount, phase: "SAVING" };
  states.merchant_name = { ...states.merchant_name, phase: "EDITING", value: "Draft chưa lưu" };
  const savedField = {
    ...receipt.fields.total_amount,
    has_correction: true,
    corrected_value: 325000,
    corrected_status: "PRESENT",
    effective_value: 325000,
    effective_status: "PRESENT",
    effective_needs_review: false,
    updated_at: "2026-08-25T01:00:00Z",
  };
  let mutationCalls = 0;
  let refreshCalls = 0;
  const api = {
    async updateCorrection() { mutationCalls += 1; return savedField; },
    async getReceipt() { refreshCalls += 1; throw new ApiRequestError("refresh failed", 503, "UPSTREAM_ERROR"); },
  };

  const result = await saveCorrectionAndRefresh({ api, receipt, fieldStates: states, fieldName: "total_amount", request: {} });
  assert.equal(result.outcome, "REFRESH_REQUIRED");
  assert.equal(mutationCalls, 1);
  assert.equal(refreshCalls, 1);
  assert.equal(result.receipt.fields.total_amount.effective_value, 325000);
  assert.equal(result.fieldStates.total_amount.phase, "SAVED");
  assert.equal(result.fieldStates.merchant_name.value, "Draft chưa lưu");
  assert.equal(result.fieldStates.merchant_name.phase, "EDITING");
});

test("mutation correction thất bại vẫn trả MUTATION_ERROR và không refresh", async () => {
  const receipt = structuredClone(MOCK_RECEIPTS[0]);
  const states = createFieldStates(receipt.fields);
  const marker = new ApiRequestError("mutation failed", 500, "MUTATION_FAILED");
  const api = {
    async updateCorrection() { throw marker; },
    async getReceipt() { assert.fail("Không được refresh khi mutation thất bại"); },
  };
  const result = await saveCorrectionAndRefresh({ api, receipt, fieldStates: states, fieldName: "invoice_id", request: {} });
  assert.equal(result.outcome, "MUTATION_ERROR");
  assert.equal(result.error, marker);
  assert.equal(result.receipt, receipt);
});

test("projector từ chối malformed field 2xx theo invariant W2", () => {
  const valid = structuredClone(MOCK_RECEIPTS[0].fields.merchant_name);
  assert.doesNotThrow(() => projectApiExtractedField(valid, "merchant_name"));
  for (const malformed of [
    { ...valid, effective_value: "giá trị lệch" },
    { ...valid, corrected_value: "không hợp lệ khi has_correction=false" },
    { ...valid, review_reasons: ["LOW_CONFIDENCE"] },
    { ...valid, source_block_ids: [] },
  ]) assert.throws(() => projectApiExtractedField(malformed, "merchant_name"));
});

test("correction response 2xx luôn đi qua shared field projector", async () => {
  const originalFetch = globalThis.fetch;
  const malformed = { ...structuredClone(MOCK_RECEIPTS[0].fields.merchant_name), effective_value: "drift" };
  globalThis.fetch = async () => new Response(JSON.stringify(malformed), { status: 200, headers: { "content-type": "application/json" } });
  try {
    await assert.rejects(
      () => new HttpApi().updateCorrection(RECEIPT_IDS.review, "merchant_name", {}, { ocrBlocks: MOCK_RECEIPTS[0].ocr_blocks }),
      (error) => {
        assert.ok(error instanceof MutationOutcomeUnknownError);
        assert.match(error.cause.message, /effective_value\/effective_status/);
        return true;
      },
    );
  } finally { globalThis.fetch = originalFetch; }
});
