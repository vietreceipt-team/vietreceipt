export const RECEIPT_STATUSES = [
  "UPLOADED",
  "PROCESSING",
  "NEEDS_REVIEW",
  "VERIFIED",
  "FAILED",
] as const;

export type ReceiptStatus = (typeof RECEIPT_STATUSES)[number];

export const CORE_FIELD_TYPES = [
  "merchant_name",
  "receipt_date",
  "total_amount",
  "invoice_id",
  "merchant_address",
] as const;

export type FieldType = (typeof CORE_FIELD_TYPES)[number];

export const FIELD_LABELS: Record<FieldType, string> = {
  merchant_name: "Tên cửa hàng",
  receipt_date: "Ngày giao dịch",
  total_amount: "Tổng tiền",
  invoice_id: "Mã hóa đơn",
  merchant_address: "Địa chỉ cửa hàng",
};

export const VALUE_STATUSES = [
  "PRESENT",
  "NOT_PRESENT",
  "UNREADABLE",
  "AMBIGUOUS",
  "UNKNOWN",
] as const;

export type ValueStatus = (typeof VALUE_STATUSES)[number];

export const REVIEW_REASON_CODES = [
  "NO_CANDIDATE",
  "LOW_CONFIDENCE",
  "MULTIPLE_CANDIDATES",
  "AMBIGUOUS_FORMAT",
  "UNREADABLE_SOURCE",
  "UNSUPPORTED_CURRENCY",
  "NEGATIVE_AMOUNT",
  "MISSING_DATE_COMPONENT",
  "UNSUPPORTED_TWO_DIGIT_YEAR",
  "SOURCE_ROLE_UNCLEAR",
  "NORMALIZATION_FAILED",
] as const;

export type ReviewReasonCode = (typeof REVIEW_REASON_CODES)[number];
export type FieldValue = string | number | null;

export interface ReviewReason {
  code: ReviewReasonCode;
  message?: string;
}

export interface Normalization {
  rule: string;
  version: string;
}

export interface Point {
  x: number;
  y: number;
}

export interface OcrBlock {
  block_id: string;
  text: string;
  confidence: number;
  polygon: [Point, Point, Point, Point];
  reading_order: number;
}

export interface MachineFieldState {
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue;
  value_status: ValueStatus;
  confidence: number;
  machine_needs_review: boolean;
  review_reasons: ReviewReason[];
  normalization?: Normalization;
  source_block_ids: string[];
  currency?: "VND";
}

export interface ReceiptField<TFieldName extends FieldType = FieldType> {
  field_name: TFieldName;
  machine: MachineFieldState;
  has_correction: boolean;
  corrected_status: ValueStatus | null;
  corrected_value: FieldValue;
  effective_status: ValueStatus;
  effective_value: FieldValue;
  effective_needs_review: boolean;
  updated_at: string;
  corrected_by?: string | null;
  corrected_at?: string | null;
}

export type CanonicalFields = {
  [TFieldName in FieldType]: ReceiptField<TFieldName>;
};

export interface ProcessingError {
  code: string;
  message: string;
}

export interface ReceiptDetail {
  receipt_id: string;
  status: ReceiptStatus;
  latest_ocr_run_id?: string | null;
  latest_kie_run_id?: string | null;
  fields?: CanonicalFields;
  processing_error?: ProcessingError | null;
  created_at: string;
  updated_at: string;
  verified_by?: string | null;
  verified_at?: string | null;

  // Presentation evidence is returned by the future authenticated receipt view.
  // It is kept separate from machine field values so the UI never reconstructs
  // an "original" image from OCR/KIE output.
  original_filename: string;
  image_url?: string;
  image_width_px?: number;
  image_height_px?: number;
  ocr_blocks?: OcrBlock[];
}

export interface ReceiptSummary {
  receipt_id: string;
  original_filename: string;
  image_url?: string;
  status: ReceiptStatus;
  merchant_name?: string | null;
  receipt_date?: string | null;
  total_amount?: number | null;
  created_at: string;
  verified_at?: string | null;
}

export interface ReceiptPage {
  items: ReceiptSummary[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface ReceiptAccepted {
  receipt_id: string;
  status: "UPLOADED" | "PROCESSING";
  created_at: string;
}

export interface ApplyCorrectionRequest {
  operation: "APPLY";
  corrected_status: ValueStatus;
  corrected_value: FieldValue;
  expected_updated_at: string;
}

export interface ClearCorrectionRequest {
  operation: "CLEAR";
  expected_updated_at: string;
}

export type FieldCorrectionRequest =
  | ApplyCorrectionRequest
  | ClearCorrectionRequest;

export interface VerifyRequest {
  expected_updated_at: string;
}

export interface VerifyResponse {
  receipt_id: string;
  status: "VERIFIED";
  verified_by: string;
  verified_at: string;
  updated_at: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

export function getExtractedField<TFieldName extends FieldType>(
  receipt: Pick<ReceiptDetail, "fields">,
  fieldType: TFieldName,
): ReceiptField<TFieldName> | undefined {
  return receipt.fields?.[fieldType];
}

export function getSourceBlocksForField(
  receipt: Pick<ReceiptDetail, "ocr_blocks">,
  field: Pick<ReceiptField, "machine">,
): OcrBlock[] {
  const sourceIds = new Set(field.machine.source_block_ids);
  return (receipt.ocr_blocks ?? []).filter((block) => sourceIds.has(block.block_id));
}

export function findFieldForSourceBlock(
  fields: CanonicalFields,
  blockId: string,
): FieldType | undefined {
  return CORE_FIELD_TYPES.find((fieldType) =>
    fields[fieldType].machine.source_block_ids.includes(blockId),
  );
}
