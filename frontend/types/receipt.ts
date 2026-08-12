export const RECEIPT_STATUSES = [
  "UPLOADED",
  "QUEUED",
  "PROCESSING",
  "NEEDS_REVIEW",
  "VERIFIED",
  "FAILED",
] as const;

export type ReceiptStatus = (typeof RECEIPT_STATUSES)[number];

export const PROCESSING_STAGES = [
  "PREPROCESSING",
  "OCR",
  "KIE",
  "PERSISTING",
] as const;

export type ProcessingStage = (typeof PROCESSING_STAGES)[number];

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

export const REVIEW_REASONS = [
  "LOW_CONFIDENCE",
  "NOT_PRESENT",
  "UNREADABLE",
  "AMBIGUOUS",
  "UNKNOWN",
  "NORMALIZATION_FAILED",
  "FORMAT_INVALID",
] as const;

export type ReviewReason = (typeof REVIEW_REASONS)[number];
export type FieldValue = string | number | null;

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

export interface ExtractedField {
  field_id: string;
  field_type: FieldType;
  ocr_run_id: string;
  kie_run_id: string;
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue;
  value_status: ValueStatus;
  corrected_value: FieldValue;
  corrected_status: ValueStatus | null;
  has_correction: boolean;
  effective_value: FieldValue;
  effective_status: ValueStatus;
  confidence: number;
  machine_needs_review: boolean;
  effective_needs_review: boolean;
  review_reasons: ReviewReason[];
  source_block_ids: string[];
  verified: boolean;
  updated_at: string;
}

export interface ProcessingError {
  stage: ProcessingStage;
  code: string;
  message: string;
  retryable: boolean;
  occurred_at: string;
}

export interface ReceiptSummary {
  receipt_id: string;
  original_filename: string;
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

export interface ReceiptDetail {
  receipt_id: string;
  original_filename: string;
  status: ReceiptStatus;
  processing_stage: ProcessingStage | null;
  image_url?: string;
  image_width_px: number;
  image_height_px: number;
  latest_ocr_run_id?: string | null;
  latest_kie_run_id?: string | null;
  fields: ExtractedField[];
  ocr_blocks: OcrBlock[];
  last_error?: ProcessingError | null;
  created_at: string;
  processed_at?: string | null;
  verified_at?: string | null;
}

export interface ProcessAccepted {
  receipt_id: string;
  status: "QUEUED";
}

export interface FieldCorrectionRequest {
  value: FieldValue;
  value_status: ValueStatus;
  expected_updated_at: string;
}

export interface CorrectionHistory {
  correction_id: string;
  field_id: string;
  field_type: FieldType;
  kie_run_id: string;
  old_value: FieldValue;
  new_value: FieldValue;
  old_status: ValueStatus | null;
  new_status: ValueStatus | null;
  changed_by: string;
  changed_at: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id: string;
  };
}

export function getExtractedField(
  receipt: Pick<ReceiptDetail, "fields">,
  fieldType: FieldType,
): ExtractedField | undefined {
  return receipt.fields.find((field) => field.field_type === fieldType);
}
