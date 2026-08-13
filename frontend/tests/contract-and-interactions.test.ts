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
  projectApiExtractedField,
  projectApiReceiptDetail,
  submitFieldCorrection,
  submitReceiptVerification,
  validateCorrectionValue,
} from "../lib/vietreceipt-api";
import {
  CORE_FIELD_TYPES,
  RECEIPT_STATUSES,
  REVIEW_REASON_CODES,
  VALUE_STATUSES,
  findFieldForSourceBlock,
  getSourceBlocksForField,
  type ApiCanonicalFields,
  type ApiExtractedField,
  type ApiReceiptDetail,
  type ReceiptField,
} from "../types/receipt";

interface ContractFixture {
  receipt_statuses: string[];
  field_names: string[];
  value_statuses: string[];
  review_reason_codes: string[];
  field_response_shape: string;
  review_reason_shape: string;
  ocr_evidence_source: string;
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
const verifiedReceipt = mockReceipts.find(
  (receipt) => receipt.status === "VERIFIED",
)!;
const totalField = reviewReceipt.fields!.total_amount;

function toApiExtractedField(field: ReceiptField): ApiExtractedField {
  return {
    field_name: field.field_name,
    ocr_run_id: field.machine.ocr_run_id,
    kie_run_id: field.machine.kie_run_id,
    raw_text: field.machine.raw_text,
    predicted_value: field.machine.predicted_value,
    normalized_value: field.machine.normalized_value,
    normalization: field.machine.normalization,
    value_status: field.machine.value_status,
    corrected_value: field.corrected_value,
    corrected_status: field.corrected_status,
    has_correction: field.has_correction,
    effective_value: field.effective_value,
    effective_status: field.effective_status,
    confidence: field.machine.confidence,
    machine_needs_review: field.machine.machine_needs_review,
    effective_needs_review: field.effective_needs_review,
    review_reasons: field.machine.review_reasons,
    review_policy_version: field.machine.review_policy_version,
    source_block_ids: field.machine.source_block_ids,
    verified: field.verified,
    updated_at: field.updated_at,
  };
}

const apiFields = Object.fromEntries(
  CORE_FIELD_TYPES.map((fieldName) => [
    fieldName,
    toApiExtractedField(reviewReceipt.fields![fieldName]),
  ]),
) as ApiCanonicalFields;

const apiReceipt: ApiReceiptDetail = {
  receipt_id: reviewReceipt.receipt_id,
  original_filename: reviewReceipt.original_filename,
  status: reviewReceipt.status,
  processing_stage: null,
  image_url: reviewReceipt.image_url,
  image_width_px: reviewReceipt.image_width_px!,
  image_height_px: reviewReceipt.image_height_px!,
  latest_ocr_run_id: reviewReceipt.latest_ocr_run_id,
  latest_kie_run_id: reviewReceipt.latest_kie_run_id,
  fields: apiFields,
  ocr_blocks: reviewReceipt.ocr_blocks!,
  last_error: null,
  created_at: reviewReceipt.created_at,
  updated_at: reviewReceipt.updated_at,
  verified_at: reviewReceipt.verified_at,
};

const verifiedApiFields = Object.fromEntries(
  CORE_FIELD_TYPES.map((fieldName) => [
    fieldName,
    toApiExtractedField(verifiedReceipt.fields![fieldName]),
  ]),
) as ApiCanonicalFields;

const verifiedApiReceipt: ApiReceiptDetail = {
  ...apiReceipt,
  receipt_id: verifiedReceipt.receipt_id,
  original_filename: verifiedReceipt.original_filename,
  status: "VERIFIED",
  fields: verifiedApiFields,
  created_at: verifiedReceipt.created_at,
  updated_at: verifiedReceipt.updated_at,
  verified_at: verifiedReceipt.verified_at,
};

test("runtime constants mirror the frozen Backend/KIE v1.3 fixture", () => {
  assert.deepEqual(RECEIPT_STATUSES, contract.receipt_statuses);
  assert.deepEqual(CORE_FIELD_TYPES, contract.field_names);
  assert.deepEqual(VALUE_STATUSES, contract.value_statuses);
  assert.deepEqual(REVIEW_REASON_CODES, contract.review_reason_codes);
  assert.equal(contract.field_response_shape, "flat_extracted_field");
  assert.equal(contract.review_reason_shape, "string_enum");
  assert.equal(contract.ocr_evidence_source, "backend_ocr_contract");
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

test("rejects field-specific correction values before a request is sent", () => {
  assert.doesNotThrow(() =>
    validateCorrectionValue("total_amount", 113000, "PRESENT"),
  );
  assert.doesNotThrow(() =>
    validateCorrectionValue("receipt_date", "2020-08-12", "PRESENT"),
  );
  assert.doesNotThrow(() =>
    validateCorrectionValue("invoice_id", "000123", "PRESENT"),
  );

  assert.throws(() =>
    validateCorrectionValue("total_amount", "113000", "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("total_amount", -1, "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("total_amount", 1.5, "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("receipt_date", "12/08/2020", "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("receipt_date", "2020-02-30", "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("invoice_id", 123, "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("merchant_name", "   ", "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("merchant_address", 123, "PRESENT"),
  );
  assert.throws(() =>
    validateCorrectionValue("merchant_name", "value", "NOT_PRESENT"),
  );
});

test("projects the canonical flat Backend response into the UI view model", () => {
  const projectedField = projectApiExtractedField(
    toApiExtractedField(totalField),
  );
  assert.equal(projectedField.field_name, "total_amount");
  assert.equal(projectedField.machine.normalized_value, 113000);
  assert.deepEqual(projectedField.machine.review_reasons, ["LOW_CONFIDENCE"]);
  assert.deepEqual(
    projectedField.machine.source_block_ids,
    ["block_total_label", "block_total_value"],
  );

  const projectedReceipt = projectApiReceiptDetail(apiReceipt);
  assert.deepEqual(Object.keys(projectedReceipt.fields!), contract.field_names);
  assert.equal(projectedReceipt.fields!.invoice_id.field_name, "invoice_id");
  assert.equal(projectedReceipt.ocr_blocks, apiReceipt.ocr_blocks);
});

test("rejects a Backend field whose object key and field_name disagree", () => {
  const mismatchedReceipt = {
    ...apiReceipt,
    fields: {
      ...apiFields,
      merchant_name: {
        ...apiFields.merchant_name,
        field_name: "total_amount",
      },
    } as unknown as ApiCanonicalFields,
  };

  assert.throws(() => projectApiReceiptDetail(mismatchedReceipt));
});

test("rejects Backend projection and evidence invariants that drift from KIE", () => {
  const apiTotal = toApiExtractedField(totalField);

  assert.throws(() =>
    projectApiExtractedField({
      ...apiTotal,
      review_reasons: [],
    }),
  );
  assert.throws(() =>
    projectApiExtractedField({
      ...apiTotal,
      source_block_ids: [],
    }),
  );
  assert.throws(() =>
    projectApiExtractedField({
      ...apiTotal,
      effective_value: 999,
    }),
  );
  assert.throws(() =>
    projectApiReceiptDetail({
      ...apiReceipt,
      ocr_blocks: apiReceipt.ocr_blocks.filter(
        (block) => block.block_id !== "block_total_value",
      ),
    }),
  );
});

test("PATCH correction uses canonical correction path and serializes APPLY", async () => {
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const request = createApplyCorrectionRequest(totalField, 113000, "PRESENT");
  const fetcher = async (input: string | URL | Request, init?: RequestInit) => {
    calls.push({ input: String(input), init });
    return new Response(JSON.stringify(toApiExtractedField(totalField)), {
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
        ...verifiedApiReceipt,
        receipt_id: reviewReceipt.receipt_id,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  };

  const request = createVerifyRequest(reviewReceipt);
  const verified = await submitReceiptVerification(
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
  assert.equal(verified.status, "VERIFIED");
  assert.equal(verified.receipt_id, reviewReceipt.receipt_id);
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
