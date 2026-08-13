import {
  CORE_FIELD_TYPES,
  getExtractedField,
  type CanonicalFields,
  type FieldType,
  type FieldValue,
  type OcrBlock,
  type ReceiptDetail,
  type ReceiptField,
  type ReceiptPage,
  type ReceiptStatus,
  type ReviewReasonCode,
  type ValueStatus,
} from "../types/receipt";

const OCR_FIXTURE_IMAGE = "/fixtures/R001.jpg";
const OCR_FIXTURE_WIDTH = 465;
const OCR_FIXTURE_HEIGHT = 564;
const OCR_FIXTURE_RUN_ID = "77777777-7777-4777-8777-777777777777";
const KIE_FIXTURE_RUN_ID = "88888888-8888-4888-8888-888888888888";

const receiptIds = {
  review: "11111111-1111-4111-8111-111111111111",
  verified: "22222222-2222-4222-8222-222222222222",
  processing: "33333333-3333-4333-8333-333333333333",
  uploaded: "55555555-5555-4555-8555-555555555555",
  failed: "66666666-6666-4666-8666-666666666666",
} as const;

interface FieldFixture {
  field_name: FieldType;
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue;
  value_status?: ValueStatus;
  confidence: number;
  machine_needs_review?: boolean;
  review_reasons?: ReviewReasonCode[];
  source_block_ids?: string[];
  corrected_status?: ValueStatus | null;
  corrected_value?: FieldValue;
  effective_needs_review?: boolean;
}

function createField(fixture: FieldFixture, updatedAt: string): ReceiptField {
  const valueStatus = fixture.value_status ?? "PRESENT";
  const machineNeedsReview =
    fixture.machine_needs_review ?? valueStatus !== "PRESENT";
  const hasCorrection = fixture.corrected_status !== undefined;
  const correctedStatus = fixture.corrected_status ?? null;
  const correctedValue = fixture.corrected_value ?? null;
  const effectiveStatus = hasCorrection ? correctedStatus! : valueStatus;
  const effectiveValue = hasCorrection
    ? correctedValue
    : fixture.normalized_value;

  return {
    field_name: fixture.field_name,
    machine: {
      ocr_run_id: OCR_FIXTURE_RUN_ID,
      kie_run_id: KIE_FIXTURE_RUN_ID,
      raw_text: fixture.raw_text,
      predicted_value: fixture.predicted_value,
      normalized_value: fixture.normalized_value,
      value_status: valueStatus,
      confidence: fixture.confidence,
      machine_needs_review: machineNeedsReview,
      review_reasons: fixture.review_reasons ?? [],
      review_policy_version: machineNeedsReview
        ? "kie-review-policy/1.0.0"
        : null,
      normalization:
        fixture.normalized_value === null
          ? null
          : {
              rule:
                fixture.field_name === "total_amount"
                  ? "vnd_amount_parser"
                  : fixture.field_name === "receipt_date"
                    ? "dmy_date_parser"
                    : "unicode_nfc_whitespace",
              version: "1.0.0-example",
            },
      source_block_ids: fixture.source_block_ids ?? [],
      currency: fixture.field_name === "total_amount" ? "VND" : undefined,
    },
    has_correction: hasCorrection,
    corrected_status: correctedStatus,
    corrected_value: correctedValue,
    effective_status: effectiveStatus,
    effective_value: effectiveValue,
    effective_needs_review:
      fixture.effective_needs_review ??
      (hasCorrection ? false : machineNeedsReview),
    verified: false,
    updated_at: updatedAt,
    corrected_by: hasCorrection
      ? "99999999-9999-4999-8999-999999999999"
      : null,
    corrected_at: hasCorrection ? updatedAt : null,
  };
}

function createReviewFields(): CanonicalFields {
  const updatedAt = "2026-08-12T03:05:00Z";
  return {
    merchant_name: createField(
      {
        field_name: "merchant_name",
        raw_text: "MINIMART ANAN",
        predicted_value: "MINIMART ANAN",
        normalized_value: "MINIMART ANAN",
        confidence: 0.916,
        source_block_ids: ["block_merchant"],
      },
      updatedAt,
    ),
    receipt_date: createField(
      {
        field_name: "receipt_date",
        raw_text: "Ngày: 12/08/2020-16:26",
        predicted_value: "12/08/2020",
        normalized_value: "2020-08-12",
        confidence: 0.865,
        source_block_ids: ["block_date"],
      },
      updatedAt,
    ),
    total_amount: createField(
      {
        field_name: "total_amount",
        raw_text: "Tổng tiền\n113,000",
        predicted_value: "113,000",
        normalized_value: 113000,
        confidence: 0.753,
        machine_needs_review: true,
        review_reasons: ["LOW_CONFIDENCE"],
        source_block_ids: ["block_total_label", "block_total_value"],
      },
      updatedAt,
    ),
    invoice_id: createField(
      {
        field_name: "invoice_id",
        raw_text: "Số GD: 000AC2212008001576",
        predicted_value: "000AC2212008001576",
        normalized_value: "000AC2212008001576",
        confidence: 0.905,
        source_block_ids: ["block_invoice"],
        corrected_status: "PRESENT",
        corrected_value: "000AC2212008001576",
      },
      updatedAt,
    ),
    merchant_address: createField(
      {
        field_name: "merchant_address",
        raw_text: "Chợ Sủi Phú Thị Gia Lâm",
        predicted_value: "Chợ Sủi Phú Thị Gia Lâm",
        normalized_value: "Chợ Sủi Phú Thị Gia Lâm",
        confidence: 0.906,
        source_block_ids: ["block_address"],
      },
      updatedAt,
    ),
  } as CanonicalFields;
}

function createVerifiedFields(): CanonicalFields {
  const updatedAt = "2026-08-12T03:10:00Z";
  const fields = createReviewFields();

  return Object.fromEntries(
    CORE_FIELD_TYPES.map((fieldName) => {
      const field = fields[fieldName];
      return [
        fieldName,
        {
          ...field,
          has_correction: false,
          corrected_status: null,
          corrected_value: null,
          effective_status: field.machine.value_status,
          effective_value: field.machine.normalized_value,
          effective_needs_review: false,
          verified: true,
          updated_at: updatedAt,
          corrected_by: null,
          corrected_at: null,
        },
      ];
    }),
  ) as CanonicalFields;
}

function normalizedRect(
  left: number,
  top: number,
  width: number,
  height: number,
): OcrBlock["polygon"] {
  const right = left + width;
  const bottom = top + height;
  return [
    { x: left / OCR_FIXTURE_WIDTH, y: top / OCR_FIXTURE_HEIGHT },
    { x: right / OCR_FIXTURE_WIDTH, y: top / OCR_FIXTURE_HEIGHT },
    { x: right / OCR_FIXTURE_WIDTH, y: bottom / OCR_FIXTURE_HEIGHT },
    { x: left / OCR_FIXTURE_WIDTH, y: bottom / OCR_FIXTURE_HEIGHT },
  ];
}

const reviewOcrBlocks: OcrBlock[] = [
  {
    block_id: "block_merchant",
    text: "MINIMART ANAN",
    confidence: 0.916,
    polygon: normalizedRect(132, 74, 162, 15),
    reading_order: 0,
  },
  {
    block_id: "block_address",
    text: "Chợ Sủi Phú Thị Gia Lâm",
    confidence: 0.906,
    polygon: normalizedRect(110, 102, 202, 18),
    reading_order: 1,
  },
  {
    block_id: "block_total_label",
    text: "Tổng tiền",
    confidence: 0.878,
    polygon: normalizedRect(6, 426, 72, 20),
    reading_order: 12,
  },
  {
    block_id: "block_total_value",
    text: "113,000",
    confidence: 0.753,
    polygon: normalizedRect(353, 426, 61, 16),
    reading_order: 13,
  },
  {
    block_id: "block_invoice",
    text: "Số GD: 000AC2212008001576",
    confidence: 0.905,
    polygon: normalizedRect(26, 489, 213, 18),
    reading_order: 14,
  },
  {
    block_id: "block_date",
    text: "Ngày: 12/08/2020-16:26",
    confidence: 0.865,
    polygon: normalizedRect(244, 489, 164, 18),
    reading_order: 15,
  },
];

function createReceipt(
  receipt_id: string,
  original_filename: string,
  status: ReceiptStatus,
  created_at: string,
  options: Partial<ReceiptDetail> = {},
): ReceiptDetail {
  return {
    receipt_id,
    original_filename,
    status,
    created_at,
    updated_at: options.updated_at ?? created_at,
    latest_ocr_run_id: options.latest_ocr_run_id ?? null,
    latest_kie_run_id: options.latest_kie_run_id ?? null,
    ...options,
  };
}

export const mockReceipts: ReceiptDetail[] = [
  createReceipt(
    receiptIds.review,
    "R001.jpg",
    "NEEDS_REVIEW",
    "2026-08-12T03:00:00Z",
    {
      updated_at: "2026-08-12T03:05:00Z",
      latest_ocr_run_id: "11111111-aaaa-4aaa-8aaa-111111111111",
      latest_kie_run_id: "11111111-bbbb-4bbb-8bbb-111111111111",
      fields: createReviewFields(),
      image_url: OCR_FIXTURE_IMAGE,
      image_width_px: OCR_FIXTURE_WIDTH,
      image_height_px: OCR_FIXTURE_HEIGHT,
      ocr_blocks: reviewOcrBlocks,
    },
  ),
  createReceipt(
    receiptIds.verified,
    "R001-verified.jpg",
    "VERIFIED",
    "2026-08-12T02:18:00Z",
    {
      updated_at: "2026-08-12T03:10:00Z",
      latest_ocr_run_id: "22222222-aaaa-4aaa-8aaa-222222222222",
      latest_kie_run_id: "22222222-bbbb-4bbb-8bbb-222222222222",
      fields: createVerifiedFields(),
      image_url: OCR_FIXTURE_IMAGE,
      image_width_px: OCR_FIXTURE_WIDTH,
      image_height_px: OCR_FIXTURE_HEIGHT,
      ocr_blocks: reviewOcrBlocks,
      verified_by: "99999999-9999-4999-8999-999999999999",
      verified_at: "2026-08-12T03:10:00Z",
    },
  ),
  createReceipt(
    receiptIds.processing,
    "sieu-thi-xanh-1008.jpg",
    "PROCESSING",
    "2026-08-12T01:56:00Z",
  ),
  createReceipt(
    receiptIds.uploaded,
    "dien-may-thanh-cong.jpg",
    "UPLOADED",
    "2026-08-12T01:31:00Z",
  ),
  createReceipt(
    receiptIds.failed,
    "hoa-don-mo-1008.jpg",
    "FAILED",
    "2026-08-12T01:12:00Z",
    {
      processing_error: {
        code: "UNREADABLE_IMAGE",
        message: "Ảnh mờ, không thể đọc nội dung.",
      },
    },
  ),
];

export const mockReceiptPage: ReceiptPage = {
  items: mockReceipts.map((receipt) => {
    const merchant = getExtractedField(receipt, "merchant_name");
    const date = getExtractedField(receipt, "receipt_date");
    const total = getExtractedField(receipt, "total_amount");

    return {
      receipt_id: receipt.receipt_id,
      original_filename: receipt.original_filename,
      image_url: receipt.image_url,
      status: receipt.status,
      merchant_name:
        typeof merchant?.effective_value === "string"
          ? merchant.effective_value
          : null,
      receipt_date:
        typeof date?.effective_value === "string" ? date.effective_value : null,
      total_amount:
        typeof total?.effective_value === "number"
          ? total.effective_value
          : null,
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
  throw new Error("VietReceipt v1.3 requires exactly five canonical field names.");
}
