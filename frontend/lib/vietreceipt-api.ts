import type {
  ApiErrorResponse,
  ApiExtractedField,
  ApiReceiptDetail,
  ApplyCorrectionRequest,
  CanonicalFields,
  ClearCorrectionRequest,
  FieldCorrectionRequest,
  FieldType,
  FieldValue,
  ReceiptDetail,
  ReceiptField,
  ReceiptPage,
  ReceiptStatus,
  ReceiptSummary,
  RetryAccepted,
  ValueStatus,
  VerifyRequest,
} from "../types/receipt";
import { CORE_FIELD_TYPES } from "../types/receipt";

export const API_BASE_PATH = "/api/v1";

function encodePathSegment(value: string) {
  return encodeURIComponent(value);
}

export const apiPaths = {
  receipts: `${API_BASE_PATH}/receipts`,
  receipt: (receiptId: string) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}`,
  fieldCorrection: (receiptId: string, fieldName: FieldType) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}/fields/${encodePathSegment(fieldName)}/correction`,
  retryReceipt: (receiptId: string) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}/retry`,
  verifyReceipt: (receiptId: string) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}/verify`,
} as const;

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details: Record<string, unknown> | null = null,
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class OptimisticConcurrencyError extends ApiRequestError {
  constructor(
    message: string,
    code = "STALE_WRITE",
    details: Record<string, unknown> | null = null,
    requestId: string | null = null,
  ) {
    super(message, 409, code, details, requestId);
    this.name = "OptimisticConcurrencyError";
  }
}

export class ApiValidationError extends ApiRequestError {
  constructor(
    message: string,
    code = "VALIDATION_ERROR",
    details: Record<string, unknown> | null = null,
    requestId: string | null = null,
  ) {
    super(message, 422, code, details, requestId);
    this.name = "ApiValidationError";
  }
}

export type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export interface RequestOptions {
  signal?: AbortSignal;
}

export interface ReceiptListQuery {
  page?: number;
  page_size?: number;
  status?: ReceiptStatus;
  merchant_name?: string;
  date_from?: string;
  date_to?: string;
}

export interface VietReceiptApi {
  uploadReceipt(file: File, options?: RequestOptions): Promise<ReceiptSummary>;
  getReceipts(query?: ReceiptListQuery, options?: RequestOptions): Promise<ReceiptPage>;
  getReceipt(receiptId: string, options?: RequestOptions): Promise<ReceiptDetail>;
  applyCorrection(
    receiptId: string,
    fieldName: FieldType,
    request: ApplyCorrectionRequest,
    options?: RequestOptions,
  ): Promise<ReceiptField>;
  clearCorrection(
    receiptId: string,
    fieldName: FieldType,
    request: ClearCorrectionRequest,
    options?: RequestOptions,
  ): Promise<ReceiptField>;
  verifyReceipt(
    receiptId: string,
    request: VerifyRequest,
    options?: RequestOptions,
  ): Promise<ReceiptDetail>;
  retryReceipt(receiptId: string, options?: RequestOptions): Promise<RetryAccepted>;
}

function isCanonicalDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;

  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return day <= daysInMonth;
}

export function validateCorrectionValue(
  fieldName: FieldType,
  value: FieldValue,
  valueStatus: ValueStatus,
) {
  if (valueStatus !== "PRESENT") {
    if (value !== null) {
      throw new Error(`${valueStatus} requires value null.`);
    }
    return;
  }

  switch (fieldName) {
    case "total_amount":
      if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
        throw new Error("total_amount must be a non-negative integer VND value.");
      }
      return;
    case "receipt_date":
      if (typeof value !== "string" || !isCanonicalDate(value)) {
        throw new Error("receipt_date must be a valid YYYY-MM-DD date.");
      }
      return;
    case "invoice_id":
    case "merchant_name":
    case "merchant_address":
      if (typeof value !== "string" || value.trim().length === 0) {
        throw new Error(`${fieldName} must be a non-empty string.`);
      }
  }
}

export function createApplyCorrectionRequest(
  field: Pick<ReceiptField, "field_name" | "updated_at">,
  value: FieldValue,
  valueStatus: ValueStatus,
): ApplyCorrectionRequest {
  validateCorrectionValue(field.field_name, value, valueStatus);

  return {
    operation: "APPLY",
    value_status: valueStatus,
    value,
    expected_updated_at: field.updated_at,
  };
}

export function createClearCorrectionRequest(
  field: Pick<ReceiptField, "updated_at">,
): ClearCorrectionRequest {
  return {
    operation: "CLEAR",
    expected_updated_at: field.updated_at,
  };
}

export function createVerifyRequest(
  receipt: Pick<ReceiptDetail, "updated_at">,
): VerifyRequest {
  return { expected_updated_at: receipt.updated_at };
}

export function projectApiExtractedField<
  TFieldName extends FieldType,
>(field: ApiExtractedField<TFieldName>): ReceiptField<TFieldName> {
  validateCorrectionValue(field.field_name, field.normalized_value, field.value_status);
  validateCorrectionValue(field.field_name, field.effective_value, field.effective_status);

  if (field.has_correction) {
    if (field.corrected_status === null) {
      throw new Error("A corrected field requires corrected_status.");
    }
    validateCorrectionValue(field.field_name, field.corrected_value, field.corrected_status);
  } else if (field.corrected_status !== null || field.corrected_value !== null) {
    throw new Error("An uncorrected field cannot contain corrected data.");
  }

  if (
    field.machine_needs_review &&
    (field.review_reasons.length === 0 || field.review_policy_version === null)
  ) {
    throw new Error("machine_needs_review requires review_reasons and review_policy_version.");
  }
  if (!field.machine_needs_review && field.review_reasons.length > 0) {
    throw new Error("review_reasons must be empty when machine review is false.");
  }
  if (field.value_status === "PRESENT" && field.source_block_ids.length === 0) {
    throw new Error("A PRESENT machine field requires source_block_ids.");
  }

  const expectedEffectiveValue = field.has_correction
    ? field.corrected_value
    : field.normalized_value;
  const expectedEffectiveStatus = field.has_correction
    ? field.corrected_status
    : field.value_status;
  if (
    field.effective_value !== expectedEffectiveValue ||
    field.effective_status !== expectedEffectiveStatus
  ) {
    throw new Error("effective_value/effective_status must derive from correction or normalization.");
  }

  return {
    field_name: field.field_name,
    machine: {
      ocr_run_id: field.ocr_run_id,
      kie_run_id: field.kie_run_id,
      raw_text: field.raw_text,
      predicted_value: field.predicted_value,
      normalized_value: field.normalized_value,
      normalization: field.normalization,
      value_status: field.value_status,
      confidence: field.confidence,
      machine_needs_review: field.machine_needs_review,
      review_reasons: field.review_reasons,
      review_policy_version: field.review_policy_version,
      source_block_ids: field.source_block_ids,
      currency: field.field_name === "total_amount" ? "VND" : undefined,
    },
    has_correction: field.has_correction,
    corrected_status: field.corrected_status,
    corrected_value: field.corrected_value,
    effective_status: field.effective_status,
    effective_value: field.effective_value,
    effective_needs_review: field.effective_needs_review,
    verified: field.verified,
    updated_at: field.updated_at,
  };
}

export function projectApiReceiptDetail(receipt: ApiReceiptDetail): ReceiptDetail {
  const fieldEntries = Object.entries(receipt.fields);
  let fields: CanonicalFields | undefined;

  if (fieldEntries.length > 0) {
    const keys = fieldEntries.map(([key]) => key).sort();
    const canonicalKeys = [...CORE_FIELD_TYPES].sort();
    if (JSON.stringify(keys) !== JSON.stringify(canonicalKeys)) {
      throw new Error("Backend fields must contain exactly five canonical keys.");
    }

    fields = Object.fromEntries(
      CORE_FIELD_TYPES.map((fieldName) => {
        const field = receipt.fields[fieldName];
        if (!field || field.field_name !== fieldName) {
          throw new Error(`Field key ${fieldName} must match embedded field_name.`);
        }
        return [fieldName, projectApiExtractedField(field)];
      }),
    ) as CanonicalFields;

    const ocrBlockIds = new Set(receipt.ocr_blocks.map((block) => block.block_id));
    for (const fieldName of CORE_FIELD_TYPES) {
      for (const sourceBlockId of fields[fieldName].machine.source_block_ids) {
        if (!ocrBlockIds.has(sourceBlockId)) {
          throw new Error(`Field ${fieldName} references missing OCR block ${sourceBlockId}.`);
        }
      }
    }
  }

  return {
    receipt_id: receipt.receipt_id,
    original_filename: receipt.original_filename,
    status: receipt.status,
    processing_stage: receipt.processing_stage,
    latest_ocr_run_id: receipt.latest_ocr_run_id,
    latest_kie_run_id: receipt.latest_kie_run_id,
    fields,
    processing_error: receipt.last_error ? { ...receipt.last_error } : null,
    created_at: receipt.created_at,
    updated_at: receipt.updated_at,
    processed_at: receipt.processed_at,
    verified_at: receipt.verified_at,
    image_url: receipt.image_url,
    image_width_px: receipt.image_width_px,
    image_height_px: receipt.image_height_px,
    ocr_blocks: receipt.ocr_blocks,
  };
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;

  let error: ApiErrorResponse | null = null;
  try {
    error = (await response.json()) as ApiErrorResponse;
  } catch {
    // A proxy may return an empty or non-JSON error. Preserve the HTTP status.
  }

  const code = error?.error.code ?? `HTTP_${response.status}`;
  const message = error?.error.message ?? `Request failed with status ${response.status}.`;
  const details = error?.error.details ?? null;
  const requestId = error?.error.request_id ?? null;
  if (response.status === 409) {
    throw new OptimisticConcurrencyError(message, code, details, requestId);
  }
  if (response.status === 422) {
    throw new ApiValidationError(message, code, details, requestId);
  }
  throw new ApiRequestError(message, response.status, code, details, requestId);
}

function createUrl(path: string, baseUrl = "") {
  const normalizedBase = baseUrl.trim().replace(/\/$/, "");
  return `${normalizedBase}${path}`;
}

function createQueryString(query: ReceiptListQuery) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

function withDefaults(init: RequestInit = {}): RequestInit {
  return {
    ...init,
    credentials: "include",
    headers: { accept: "application/json", ...init.headers },
  };
}

export async function uploadReceipt(
  fetcher: FetchLike,
  file: File,
  options: RequestOptions = {},
  baseUrl = "",
): Promise<ReceiptSummary> {
  const form = new FormData();
  form.set("file", file);
  const response = await fetcher(createUrl(apiPaths.receipts, baseUrl), withDefaults({
    method: "POST",
    body: form,
    signal: options.signal,
  }));
  return parseResponse<ReceiptSummary>(response);
}

export async function getReceipts(
  fetcher: FetchLike,
  query: ReceiptListQuery = {},
  options: RequestOptions = {},
  baseUrl = "",
): Promise<ReceiptPage> {
  const response = await fetcher(
    createUrl(`${apiPaths.receipts}${createQueryString(query)}`, baseUrl),
    withDefaults({ signal: options.signal }),
  );
  return parseResponse<ReceiptPage>(response);
}

export async function getReceipt(
  fetcher: FetchLike,
  receiptId: string,
  options: RequestOptions = {},
  baseUrl = "",
): Promise<ReceiptDetail> {
  const response = await fetcher(
    createUrl(apiPaths.receipt(receiptId), baseUrl),
    withDefaults({ signal: options.signal }),
  );
  return projectApiReceiptDetail(await parseResponse<ApiReceiptDetail>(response));
}

export async function submitReceiptRetry(
  fetcher: FetchLike,
  receiptId: string,
  options: RequestOptions = {},
  baseUrl = "",
): Promise<RetryAccepted> {
  const response = await fetcher(createUrl(apiPaths.retryReceipt(receiptId), baseUrl), withDefaults({
    method: "POST",
    signal: options.signal,
  }));
  const accepted = await parseResponse<RetryAccepted>(response);
  const responseKeys = Object.keys(accepted).sort();
  if (
    response.status !== 202 ||
    accepted.receipt_id !== receiptId ||
    accepted.retry_accepted !== true ||
    JSON.stringify(responseKeys) !== JSON.stringify(["receipt_id", "retry_accepted"])
  ) {
    throw new Error("Backend retry response must be the canonical 202 RetryAccepted shape.");
  }
  return accepted;
}

export async function submitFieldCorrection(
  fetcher: FetchLike,
  receiptId: string,
  fieldName: FieldType,
  request: FieldCorrectionRequest,
  options: RequestOptions = {},
  baseUrl = "",
): Promise<ReceiptField> {
  const response = await fetcher(
    createUrl(apiPaths.fieldCorrection(receiptId, fieldName), baseUrl),
    withDefaults({
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal: options.signal,
    }),
  );
  const field = await parseResponse<ApiExtractedField>(response);
  if (field.field_name !== fieldName) {
    throw new Error("Backend correction response field_name does not match the request path.");
  }
  return projectApiExtractedField(field);
}

export async function submitReceiptVerification(
  fetcher: FetchLike,
  receiptId: string,
  request: VerifyRequest,
  options: RequestOptions = {},
  baseUrl = "",
): Promise<ReceiptDetail> {
  const response = await fetcher(createUrl(apiPaths.verifyReceipt(receiptId), baseUrl), withDefaults({
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    signal: options.signal,
  }));
  const receipt = await parseResponse<ApiReceiptDetail>(response);
  if (receipt.receipt_id !== receiptId || receipt.status !== "VERIFIED") {
    throw new Error("Backend verify response must return the requested VERIFIED receipt.");
  }
  return projectApiReceiptDetail(receipt);
}

export function createVietReceiptApi({
  fetcher = globalThis.fetch.bind(globalThis),
  baseUrl = "",
}: {
  fetcher?: FetchLike;
  baseUrl?: string;
} = {}): VietReceiptApi {
  return {
    uploadReceipt: (file, options) => uploadReceipt(fetcher, file, options, baseUrl),
    getReceipts: (query, options) => getReceipts(fetcher, query, options, baseUrl),
    getReceipt: (receiptId, options) => getReceipt(fetcher, receiptId, options, baseUrl),
    applyCorrection: (receiptId, fieldName, request, options) =>
      submitFieldCorrection(fetcher, receiptId, fieldName, request, options, baseUrl),
    clearCorrection: (receiptId, fieldName, request, options) =>
      submitFieldCorrection(fetcher, receiptId, fieldName, request, options, baseUrl),
    verifyReceipt: (receiptId, request, options) =>
      submitReceiptVerification(fetcher, receiptId, request, options, baseUrl),
    retryReceipt: (receiptId, options) => submitReceiptRetry(fetcher, receiptId, options, baseUrl),
  };
}

export function createBrowserVietReceiptApi() {
  return createVietReceiptApi({
    baseUrl: process.env.NEXT_PUBLIC_VIETRECEIPT_API_BASE_URL ?? "",
  });
}

export function getApiErrorMessage(error: unknown) {
  if (!(error instanceof ApiRequestError)) {
    if (error instanceof Error && !(error instanceof TypeError)) {
      return `Giá trị không hợp lệ: ${error.message}`;
    }
    return "Không thể kết nối dịch vụ. Hãy kiểm tra mạng và thử lại.";
  }
  switch (error.status) {
    case 404:
      return "Không tìm thấy hóa đơn hoặc dữ liệu đã bị thay đổi.";
    case 409:
      return "Dữ liệu đã được cập nhật ở nơi khác. Hãy tải phiên bản mới trước khi tiếp tục.";
    case 413:
      return "File vượt quá kích thước cho phép.";
    case 415:
      return "File không phải định dạng ảnh được hỗ trợ.";
    case 422:
      return "Dữ liệu chỉnh sửa không hợp lệ. Hãy kiểm tra lại giá trị.";
    default:
      return error.status >= 500
        ? "Dịch vụ đang tạm thời không khả dụng. Hãy thử lại sau."
        : error.message;
  }
}
