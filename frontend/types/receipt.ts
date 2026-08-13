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

export interface CanonicalPresentValueMap {
  merchant_name: string;
  receipt_date: string;
  total_amount: number;
  invoice_id: string;
  merchant_address: string;
}

export type PresentFieldValue<TFieldName extends FieldType = FieldType> =
  CanonicalPresentValueMap[TFieldName];
export type FieldValue<TFieldName extends FieldType = FieldType> =
  | PresentFieldValue<TFieldName>
  | null;

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

export interface MachineFieldState<TFieldName extends FieldType = FieldType> {
  ocr_run_id: string;
  kie_run_id: string;
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue<TFieldName>;
  value_status: ValueStatus;
  confidence: number;
  machine_needs_review: boolean;
  review_reasons: ReviewReasonCode[];
  review_policy_version: string | null;
  normalization: Normalization | null;
  source_block_ids: string[];
  currency?: "VND";
}

export interface ReceiptField<TFieldName extends FieldType = FieldType> {
  field_name: TFieldName;
  machine: MachineFieldState<TFieldName>;
  has_correction: boolean;
  corrected_status: ValueStatus | null;
  corrected_value: FieldValue<TFieldName>;
  effective_status: ValueStatus;
  effective_value: FieldValue<TFieldName>;
  effective_needs_review: boolean;
  verified: boolean;
  updated_at: string;
  corrected_by?: string | null;
  corrected_at?: string | null;
}

export type CanonicalFields = {
  [TFieldName in FieldType]: ReceiptField<TFieldName>;
};

export const PROCESSING_STAGES = [
  "PREPROCESSING",
  "OCR",
  "KIE",
  "PERSISTING",
] as const;

export type ProcessingStage = (typeof PROCESSING_STAGES)[number] | null;

export const PROCESSING_ERROR_STAGES = [
  "SCHEDULING",
  ...PROCESSING_STAGES,
] as const;

export type ProcessingErrorStage = (typeof PROCESSING_ERROR_STAGES)[number];

export interface ProcessingError {
  stage: ProcessingErrorStage;
  code: string;
  message: string;
  retryable: boolean;
  occurred_at: string;
}

export type ApiProcessingError = ProcessingError;

export interface ApiExtractedField<
  TFieldName extends FieldType = FieldType,
> {
  field_name: TFieldName;
  ocr_run_id: string;
  kie_run_id: string;
  raw_text: string | null;
  predicted_value: string | null;
  normalized_value: FieldValue<TFieldName>;
  normalization: Normalization | null;
  value_status: ValueStatus;
  corrected_value: FieldValue<TFieldName>;
  corrected_status: ValueStatus | null;
  has_correction: boolean;
  effective_value: FieldValue<TFieldName>;
  effective_status: ValueStatus;
  confidence: number;
  machine_needs_review: boolean;
  effective_needs_review: boolean;
  review_reasons: ReviewReasonCode[];
  review_policy_version: string | null;
  source_block_ids: string[];
  verified: boolean;
  updated_at: string;
}

export type ApiCanonicalFields = {
  [TFieldName in FieldType]: ApiExtractedField<TFieldName>;
};

export interface ApiReceiptDetail {
  receipt_id: string;
  original_filename: string;
  status: ReceiptStatus;
  processing_stage: ProcessingStage;
  image_url?: string;
  image_width_px: number;
  image_height_px: number;
  latest_ocr_run_id?: string | null;
  latest_kie_run_id?: string | null;
  fields: ApiCanonicalFields | Record<string, never>;
  ocr_blocks: OcrBlock[];
  last_error?: ApiProcessingError | null;
  created_at: string;
  updated_at: string;
  processed_at?: string | null;
  verified_at?: string | null;
}

export interface ReceiptDetail {
  receipt_id: string;
  status: ReceiptStatus;
  processing_stage?: ProcessingStage;
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

export interface RetryAccepted {
  receipt_id: string;
  retry_accepted: true;
}

export interface ApplyCorrectionRequest {
  operation: "APPLY";
  value_status: ValueStatus;
  value: FieldValue;
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
