import { CORE_FIELD_TYPES, deepClone } from "./common.js";

export const RECEIPT_IDS = {
  review: "11111111-1111-4111-8111-111111111111",
  verified: "22222222-2222-4222-8222-222222222222",
  processing: "33333333-3333-4333-8333-333333333333",
  waiting: "44444444-4444-4444-8444-444444444444",
  uploaded: "55555555-5555-4555-8555-555555555555",
  failed: "66666666-6666-4666-8666-666666666666",
};

const fieldNumber = {
  merchant_name: 1,
  receipt_date: 2,
  total_amount: 3,
  invoice_id: 4,
  merchant_address: 5,
};

const OCR_BLOCKS = [
  { block_id: "block_0", text: "CỬA HÀNG TIỆN LỢI AN NAM", confidence: .98, polygon: [{ x: .18, y: .08 }, { x: .82, y: .08 }, { x: .82, y: .13 }, { x: .18, y: .13 }], reading_order: 0 },
  { block_id: "block_1", text: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM", confidence: .91, polygon: [{ x: .16, y: .14 }, { x: .84, y: .14 }, { x: .84, y: .19 }, { x: .16, y: .19 }], reading_order: 1 },
  { block_id: "block_2", text: "Ngày: 10/08/2026", confidence: .93, polygon: [{ x: .13, y: .28 }, { x: .87, y: .28 }, { x: .87, y: .32 }, { x: .13, y: .32 }], reading_order: 2 },
  { block_id: "block_3", text: "Số HĐ: 00018427", confidence: .88, polygon: [{ x: .13, y: .23 }, { x: .87, y: .23 }, { x: .87, y: .27 }, { x: .13, y: .27 }], reading_order: 3 },
  { block_id: "block_5", text: "TỔNG CỘNG 325.OOO VND", confidence: .63, polygon: [{ x: .12, y: .62 }, { x: .88, y: .62 }, { x: .88, y: .69 }, { x: .12, y: .69 }], reading_order: 5 },
];

function createField(receiptNumber, fixture, verified = false) {
  const valueStatus = fixture.value_status ?? "PRESENT";
  const machineNeedsReview = fixture.machine_needs_review ?? valueStatus !== "PRESENT";
  return {
    field_name: fixture.field_name,
    ocr_run_id: `${receiptNumber}1111111-aaaa-4aaa-8aaa-111111111111`,
    kie_run_id: `${receiptNumber}1111111-bbbb-4bbb-8bbb-111111111111`,
    raw_text: fixture.raw_text,
    predicted_value: fixture.predicted_value,
    normalized_value: fixture.normalized_value,
    normalization: fixture.normalized_value === null ? null : { rule: "fixture_v1", version: "1.0" },
    value_status: valueStatus,
    corrected_value: null,
    corrected_status: null,
    has_correction: false,
    effective_value: fixture.normalized_value,
    effective_status: valueStatus,
    confidence: fixture.confidence,
    machine_needs_review: machineNeedsReview,
    effective_needs_review: verified ? false : machineNeedsReview,
    review_reasons: fixture.review_reasons ?? [],
    review_policy_version: machineNeedsReview ? "kie-review-policy-v1.1" : null,
    source_block_ids: fixture.source_block_ids ?? [],
    verified,
    updated_at: verified ? "2026-08-11T02:19:07Z" : "2026-08-11T02:43:18Z",
    _fixture_id: `${receiptNumber}${fieldNumber[fixture.field_name]}`,
  };
}

function fieldsFrom(fixtures, receiptNumber, verified = false) {
  return Object.fromEntries(fixtures.map((fixture) => [fixture.field_name, createField(receiptNumber, fixture, verified)]));
}

const reviewFields = fieldsFrom([
  { field_name: "merchant_name", raw_text: "CỬA HÀNG TIỆN LỢI AN NAM", predicted_value: "CỬA HÀNG TIỆN LỢI AN NAM", normalized_value: "CỬA HÀNG TIỆN LỢI AN NAM", confidence: .96, source_block_ids: ["block_0"] },
  { field_name: "receipt_date", raw_text: "Ngày: 10/08/2026", predicted_value: "10/08/2026", normalized_value: "2026-08-10", confidence: .89, source_block_ids: ["block_2"] },
  { field_name: "total_amount", raw_text: "TỔNG CỘNG\n325.OOO VND", predicted_value: "325.OOO VND", normalized_value: null, value_status: "AMBIGUOUS", confidence: .54, machine_needs_review: true, review_reasons: ["AMBIGUOUS_FORMAT", "NORMALIZATION_FAILED"], source_block_ids: ["block_5"] },
  { field_name: "invoice_id", raw_text: "Số HĐ: 00018427", predicted_value: "00018427", normalized_value: "00018427", confidence: .74, machine_needs_review: true, review_reasons: ["LOW_CONFIDENCE"], source_block_ids: ["block_3"] },
  { field_name: "merchant_address", raw_text: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM", predicted_value: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM", normalized_value: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM", confidence: .82, source_block_ids: ["block_1"] },
], 1);

const verifiedFields = fieldsFrom([
  { field_name: "merchant_name", raw_text: "CÀ PHÊ MỘC", predicted_value: "CÀ PHÊ MỘC", normalized_value: "CÀ PHÊ MỘC", confidence: .98, source_block_ids: ["block_0"] },
  { field_name: "receipt_date", raw_text: "11/08/2026", predicted_value: "11/08/2026", normalized_value: "2026-08-11", confidence: .96, source_block_ids: ["block_2"] },
  { field_name: "total_amount", raw_text: "158.000 VND", predicted_value: "158.000 VND", normalized_value: 158000, confidence: .93, source_block_ids: ["block_5"] },
  { field_name: "invoice_id", raw_text: "CF002918", predicted_value: "CF002918", normalized_value: "CF002918", confidence: .91, source_block_ids: ["block_3"] },
  { field_name: "merchant_address", raw_text: "12 Trần Phú, P. Điện Biên, Q. Ba Đình, Hà Nội", predicted_value: "12 Trần Phú, P. Điện Biên, Q. Ba Đình, Hà Nội", normalized_value: "12 Trần Phú, P. Điện Biên, Q. Ba Đình, Hà Nội", confidence: .92, source_block_ids: ["block_1"] },
], 2, true);

function createReceipt(receiptId, filename, status, createdAt, fields = {}, error = null, stage = null) {
  return {
    receipt_id: receiptId,
    original_filename: filename,
    status,
    processing_stage: stage,
    image_url: Object.keys(fields).length ? "/assets/fixtures/R001.jpg" : null,
    image_width_px: 2480,
    image_height_px: 3508,
    latest_ocr_run_id: Object.values(fields)[0]?.ocr_run_id ?? null,
    latest_kie_run_id: Object.values(fields)[0]?.kie_run_id ?? null,
    fields,
    ocr_blocks: Object.keys(fields).length ? deepClone(OCR_BLOCKS) : [],
    last_error: error,
    created_at: createdAt,
    updated_at: status === "VERIFIED" ? "2026-08-11T02:20:00Z" : "2026-08-11T02:43:18Z",
    processed_at: ["NEEDS_REVIEW", "VERIFIED"].includes(status) ? "2026-08-11T02:43:18Z" : null,
    verified_at: status === "VERIFIED" ? "2026-08-11T02:20:00Z" : null,
  };
}

export const MOCK_RECEIPTS = [
  createReceipt(RECEIPT_IDS.review, "hoa-don-an-nam-001.jpg", "NEEDS_REVIEW", "2026-08-11T02:42:00Z", reviewFields),
  createReceipt(RECEIPT_IDS.verified, "cafe-moc-aug11.png", "VERIFIED", "2026-08-11T02:18:00Z", verifiedFields),
  createReceipt(RECEIPT_IDS.processing, "sieu-thi-xanh-1008.jpg", "PROCESSING", "2026-08-11T01:56:00Z", {}, null, "OCR"),
  createReceipt(RECEIPT_IDS.waiting, "nha-thuoc-minh-tam.jpg", "UPLOADED", "2026-08-11T01:43:00Z"),
  createReceipt(RECEIPT_IDS.uploaded, "dien-may-thanh-cong.jpg", "UPLOADED", "2026-08-11T01:31:00Z"),
  createReceipt(RECEIPT_IDS.failed, "hoa-don-mo-1008.jpg", "FAILED", "2026-08-11T01:12:00Z", {}, { stage: "OCR", code: "UNREADABLE_IMAGE", message: "Ảnh mờ, không thể đọc nội dung.", retryable: true, occurred_at: "2026-08-11T01:13:00Z" }),
];

export function summarizeReceipt(receipt) {
  return {
    receipt_id: receipt.receipt_id,
    original_filename: receipt.original_filename,
    status: receipt.status,
    merchant_name: typeof receipt.fields?.merchant_name?.effective_value === "string" ? receipt.fields.merchant_name.effective_value : null,
    receipt_date: typeof receipt.fields?.receipt_date?.effective_value === "string" ? receipt.fields.receipt_date.effective_value : null,
    total_amount: typeof receipt.fields?.total_amount?.effective_value === "number" ? receipt.fields.total_amount.effective_value : null,
    created_at: receipt.created_at,
    verified_at: receipt.verified_at,
  };
}

export function assertMockContract() {
  for (const receipt of MOCK_RECEIPTS) {
    if (!["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"].includes(receipt.status)) throw new Error(`Public status không hợp lệ: ${receipt.status}`);
    const keys = Object.keys(receipt.fields);
    if (keys.length && CORE_FIELD_TYPES.some((key) => !keys.includes(key))) throw new Error("Receipt fields phải có đúng năm canonical keys.");
  }
}

assertMockContract();
