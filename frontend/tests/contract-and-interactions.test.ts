import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { mockReceipts } from "../data/mock-receipts";
import {
  OptimisticConcurrencyError,
  apiPaths,
  createApplyCorrectionRequest,
  createClearCorrectionRequest,
  createVerifyRequest,
  submitFieldCorrection,
  submitReceiptVerification,
} from "../lib/vietreceipt-api";
import {
  CORE_FIELD_TYPES,
  RECEIPT_STATUSES,
  REVIEW_REASON_CODES,
  VALUE_STATUSES,
  findFieldForSourceBlock,
  getSourceBlocksForField,
} from "../types/receipt";

interface ContractFixture {
  receipt_statuses: string[];
  field_names: string[];
  value_statuses: string[];
  review_reason_codes: string[];
  public_paths: Record<string, string>;
  has_public_process_endpoint: boolean;
}

const contract = JSON.parse(
  await readFile(
    new URL("./fixtures/backend-contract-v1.3.json", import.meta.url),
    "utf8",
  ),
) as ContractFixture;

const reviewReceipt = mockReceipts.find(
  (receipt) => receipt.status === "NEEDS_REVIEW",
)!;
const totalField = reviewReceipt.fields!.total_amount;

test("runtime constants mirror the frozen Backend/KIE v1.3 fixture", () => {
  assert.deepEqual(RECEIPT_STATUSES, contract.receipt_statuses);
  assert.deepEqual(CORE_FIELD_TYPES, contract.field_names);
  assert.deepEqual(VALUE_STATUSES, contract.value_statuses);
  assert.deepEqual(REVIEW_REASON_CODES, contract.review_reason_codes);
  assert.equal(contract.has_public_process_endpoint, false);
  assert.equal(Object.hasOwn(apiPaths, "processReceipt"), false);
  assert.equal(apiPaths.receipts, contract.public_paths.upload);
  assert.equal(
    contract.public_paths.field_correction,
    "/api/v1/receipts/{receipt_id}/fields/{field_name}/correction",
  );
  assert.equal(
    apiPaths.fieldCorrection("receipt id", "total_amount"),
    "/api/v1/receipts/receipt%20id/fields/total_amount/correction",
  );
});

test("mock KIE projection uses exactly five canonical object keys", () => {
  assert.deepEqual(Object.keys(reviewReceipt.fields!), contract.field_names);
  assert.equal(Array.isArray(reviewReceipt.fields), false);
  assert.equal(reviewReceipt.image_url, "/fixtures/R001.jpg");
  assert.equal(reviewReceipt.image_width_px, 465);
  assert.equal(reviewReceipt.image_height_px, 564);
});

test("creates exact APPLY, CLEAR and verify optimistic concurrency payloads", () => {
  assert.deepEqual(
    createApplyCorrectionRequest(totalField, 113000, "PRESENT"),
    {
      operation: "APPLY",
      value_status: "PRESENT",
      value: 113000,
      expected_updated_at: totalField.updated_at,
    },
  );
  assert.deepEqual(createClearCorrectionRequest(totalField), {
    operation: "CLEAR",
    expected_updated_at: totalField.updated_at,
  });
  assert.deepEqual(createVerifyRequest(reviewReceipt), {
    expected_updated_at: reviewReceipt.updated_at,
  });
  assert.throws(() =>
    createApplyCorrectionRequest(totalField, null, "PRESENT"),
  );
  assert.throws(() =>
    createApplyCorrectionRequest(totalField, 113000, "UNREADABLE"),
  );
});

test("PATCH correction uses canonical correction path and serializes APPLY", async () => {
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const request = createApplyCorrectionRequest(totalField, 113000, "PRESENT");
  const fetcher = async (input: string | URL | Request, init?: RequestInit) => {
    calls.push({ input: String(input), init });
    return new Response(JSON.stringify(totalField), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  await submitFieldCorrection(
    fetcher,
    reviewReceipt.receipt_id,
    "total_amount",
    request,
  );

  assert.equal(calls.length, 1);
  assert.equal(
    calls[0].input,
    `/api/v1/receipts/${reviewReceipt.receipt_id}/fields/total_amount/correction`,
  );
  assert.equal(calls[0].init?.method, "PATCH");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), request);
});

test("maps stale correction and verify responses to optimistic concurrency errors", async () => {
  const staleFetcher = async () =>
    new Response(
      JSON.stringify({
        error: {
          code: "STALE_FIELD_VERSION",
          message: "expected_updated_at is stale",
        },
      }),
      { status: 409, headers: { "content-type": "application/json" } },
    );

  await assert.rejects(
    submitFieldCorrection(
      staleFetcher,
      reviewReceipt.receipt_id,
      "total_amount",
      createClearCorrectionRequest(totalField),
    ),
    (error) =>
      error instanceof OptimisticConcurrencyError &&
      error.code === "STALE_FIELD_VERSION",
  );
  await assert.rejects(
    submitReceiptVerification(
      staleFetcher,
      reviewReceipt.receipt_id,
      createVerifyRequest(reviewReceipt),
    ),
    OptimisticConcurrencyError,
  );
});

test("POST verify serializes receipt updated_at token", async () => {
  let captured: { input: string; init?: RequestInit } | undefined;
  const fetcher = async (input: string | URL | Request, init?: RequestInit) => {
    captured = { input: String(input), init };
    return new Response(
      JSON.stringify({
        receipt_id: reviewReceipt.receipt_id,
        status: "VERIFIED",
        verified_by: "99999999-9999-4999-8999-999999999999",
        verified_at: "2026-08-12T03:11:00Z",
        updated_at: "2026-08-12T03:11:00Z",
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  };

  const request = createVerifyRequest(reviewReceipt);
  await submitReceiptVerification(
    fetcher,
    reviewReceipt.receipt_id,
    request,
  );

  assert.equal(
    captured?.input,
    `/api/v1/receipts/${reviewReceipt.receipt_id}/verify`,
  );
  assert.equal(captured?.init?.method, "POST");
  assert.deepEqual(JSON.parse(String(captured?.init?.body)), request);
});

test("source highlighting maps field to OCR polygons in both directions", () => {
  const blocks = getSourceBlocksForField(reviewReceipt, totalField);
  assert.deepEqual(
    blocks.map((block) => block.block_id),
    ["block_total_label", "block_total_value"],
  );
  assert.equal(
    findFieldForSourceBlock(reviewReceipt.fields!, "block_total_value"),
    "total_amount",
  );
  assert.equal(
    findFieldForSourceBlock(reviewReceipt.fields!, "missing_block"),
    undefined,
  );
});
