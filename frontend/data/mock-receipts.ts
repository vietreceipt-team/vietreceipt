import {
  CORE_FIELD_TYPES,
  type ExtractedField,
  type FieldType,
  type FieldValue,
  type ProcessingError,
  type ReceiptDetail,
  type ReceiptPage,
  type ReceiptStatus,
  type ReviewReason,
  type ValueStatus,
} from "../types/receipt";

const receiptIds = {
  review: "11111111-1111-4111-8111-111111111111",
  verified: "22222222-2222-4222-8222-222222222222",
  processing: "33333333-3333-4333-8333-333333333333",
  queued: "44444444-4444-4444-8444-444444444444",
  uploaded: "55555555-5555-4555-8555-555555555555",
  failed: "66666666-6666-4666-8666-666666666666",
} as const;

const fieldNumber: Record<FieldType, number> = {
  merchant_name: 1,
  receipt_date: 2,
  total_amount: 3,
  invoice_id: 4,
  merchant_address: 5,
};

interface FieldFixture {
  field_type: FieldType;
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue;
  value_status?: ValueStatus;
  confidence: number;
  machine_needs_review?: boolean;
  review_reasons?: ReviewReason[];
  source_block_ids?: string[];
  verified?: boolean;
}

function createField(
  receiptNumber: number,
  ocrRunId: string,
  kieRunId: string,
  fixture: FieldFixture,
): ExtractedField {
  const valueStatus = fixture.value_status ?? "PRESENT";
  const machineNeedsReview = fixture.machine_needs_review ?? valueStatus !== "PRESENT";
  const verified = fixture.verified ?? false;

  return {
    field_id: `${receiptNumber}${fieldNumber[fixture.field_type]}000000-0000-4000-8000-000000000000`,
    field_type: fixture.field_type,
    ocr_run_id: ocrRunId,
    kie_run_id: kieRunId,
    raw_text: fixture.raw_text,
    predicted_value: fixture.predicted_value,
    normalized_value: fixture.normalized_value,
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
    source_block_ids: fixture.source_block_ids ?? [],
    verified,
    updated_at: verified ? "2026-08-11T02:19:07Z" : "2026-08-11T02:43:18Z",
  };
}

function createReviewFields(): ExtractedField[] {
  const ocrRunId = "11111111-aaaa-4aaa-8aaa-111111111111";
  const kieRunId = "11111111-bbbb-4bbb-8bbb-111111111111";

  return [
    createField(1, ocrRunId, kieRunId, {
      field_type: "merchant_name",
      raw_text: "CỬA HÀNG TIỆN LỢI AN NAM",
      predicted_value: "CỬA HÀNG TIỆN LỢI AN NAM",
      normalized_value: "CỬA HÀNG TIỆN LỢI AN NAM",
      confidence: 0.96,
      source_block_ids: ["block_0"],
    }),
    createField(1, ocrRunId, kieRunId, {
      field_type: "receipt_date",
      raw_text: "Ngày: 10/08/2026",
      predicted_value: "10/08/2026",
      normalized_value: "2026-08-10",
      confidence: 0.89,
      source_block_ids: ["block_2"],
    }),
    createField(1, ocrRunId, kieRunId, {
      field_type: "total_amount",
      raw_text: "TỔNG CỘNG\n325.OOO VND",
      predicted_value: "325.OOO VND",
      normalized_value: null,
      value_status: "AMBIGUOUS",
      confidence: 0.54,
      machine_needs_review: true,
      review_reasons: ["AMBIGUOUS", "NORMALIZATION_FAILED"],
      source_block_ids: ["block_5"],
    }),
    createField(1, ocrRunId, kieRunId, {
      field_type: "invoice_id",
      raw_text: "Số HĐ: 00018427",
      predicted_value: "00018427",
      normalized_value: "00018427",
      confidence: 0.74,
      machine_needs_review: true,
      review_reasons: ["LOW_CONFIDENCE"],
      source_block_ids: ["block_3"],
    }),
    createField(1, ocrRunId, kieRunId, {
      field_type: "merchant_address",
      raw_text: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM",
      predicted_value: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM",
      normalized_value: "28 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM",
      confidence: 0.82,
      source_block_ids: ["block_1"],
    }),
  ];
}

function createVerifiedFields(): ExtractedField[] {
  const ocrRunId = "22222222-aaaa-4aaa-8aaa-222222222222";
  const kieRunId = "22222222-bbbb-4bbb-8bbb-222222222222";
  const values: Array<[FieldType, string, FieldValue, number, string]> = [
    ["merchant_name", "CÀ PHÊ MỘC", "CÀ PHÊ MỘC", 0.98, "block_0"],
    ["receipt_date", "11/08/2026", "2026-08-11", 0.96, "block_2"],
    ["total_amount", "158.000 VND", 158000, 0.93, "block_5"],
    ["invoice_id", "CF002918", "CF002918", 0.91, "block_3"],
    ["merchant_address", "12 Trần Phú, P. Điện Biên, Q. Ba Đình, Hà Nội", "12 Trần Phú, P. Điện Biên, Q. Ba Đình, Hà Nội", 0.92, "block_1"],
  ];

  return values.map(([field_type, predicted_value, normalized_value, confidence, blockId]) =>
    createField(2, ocrRunId, kieRunId, {
      field_type,
      raw_text: predicted_value,
      predicted_value,
      normalized_value,
      confidence,
      source_block_ids: [blockId],
      verified: true,
    }),
  );
}

function createReceipt(
  receipt_id: string,
  original_filename: string,
  status: ReceiptStatus,
  created_at: string,
  fields: ExtractedField[] = [],
  last_error: ProcessingError | null = null,
): ReceiptDetail {
  const processed = status === "NEEDS_REVIEW" || status === "VERIFIED";
  const processing_stage = status === "PROCESSING" ? "OCR" : null;

  return {
    receipt_id,
    original_filename,
    status,
    processing_stage,
    image_width_px: 2480,
    image_height_px: 3508,
    latest_ocr_run_id: fields[0]?.ocr_run_id ?? null,
    latest_kie_run_id: fields[0]?.kie_run_id ?? null,
    fields,
    ocr_blocks: [],
    last_error,
    created_at,
    processed_at: processed ? "2026-08-11T02:43:18Z" : null,
    verified_at: status === "VERIFIED" ? "2026-08-11T02:20:00Z" : null,
  };
}

export const mockReceipts: ReceiptDetail[] = [
  createReceipt(receiptIds.review, "hoa-don-an-nam-001.jpg", "NEEDS_REVIEW", "2026-08-11T02:42:00Z", createReviewFields()),
  createReceipt(receiptIds.verified, "cafe-moc-aug11.png", "VERIFIED", "2026-08-11T02:18:00Z", createVerifiedFields()),
  createReceipt(receiptIds.processing, "sieu-thi-xanh-1008.jpg", "PROCESSING", "2026-08-11T01:56:00Z"),
  createReceipt(receiptIds.queued, "nha-thuoc-minh-tam.jpg", "QUEUED", "2026-08-11T01:43:00Z"),
  createReceipt(receiptIds.uploaded, "dien-may-thanh-cong.jpg", "UPLOADED", "2026-08-11T01:31:00Z"),
  createReceipt(
    receiptIds.failed,
    "hoa-don-mo-1008.jpg",
    "FAILED",
    "2026-08-11T01:12:00Z",
    [],
    {
      stage: "OCR",
      code: "UNREADABLE_IMAGE",
      message: "Ảnh mờ, không thể đọc nội dung.",
      retryable: true,
      occurred_at: "2026-08-11T01:13:00Z",
    },
  ),
];

export const mockReceiptPage: ReceiptPage = {
  items: mockReceipts.map((receipt) => {
    const merchant = receipt.fields.find((field) => field.field_type === "merchant_name");
    const date = receipt.fields.find((field) => field.field_type === "receipt_date");
    const total = receipt.fields.find((field) => field.field_type === "total_amount");

    return {
      receipt_id: receipt.receipt_id,
      original_filename: receipt.original_filename,
      status: receipt.status,
      merchant_name: typeof merchant?.effective_value === "string" ? merchant.effective_value : null,
      receipt_date: typeof date?.effective_value === "string" ? date.effective_value : null,
      total_amount: typeof total?.effective_value === "number" ? total.effective_value : null,
      created_at: receipt.created_at,
      verified_at: receipt.verified_at ?? null,
    };
  }),
  page: 1,
  page_size: 20,
  total_items: mockReceipts.length,
  total_pages: 1,
};

export function getReceiptById(receiptId: string): ReceiptDetail | undefined {
  return mockReceipts.find((receipt) => receipt.receipt_id === receiptId);
}

if (new Set(CORE_FIELD_TYPES).size !== 5) {
  throw new Error("VietReceipt v1.3 requires exactly five canonical field types.");
}
