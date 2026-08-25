// @ts-check
import { APP_CONFIG, API_BASE_PATH } from "./config.js";
import { CORE_FIELD_TYPES, deepClone } from "./common.js";
import { MOCK_RECEIPTS, summarizeReceipt } from "./mock-data.js";

export const apiPaths = {
  receipts: `${API_BASE_PATH}/receipts`,
  receipt: (receiptId) => `${API_BASE_PATH}/receipts/${encodeURIComponent(receiptId)}`,
  fieldCorrection: (receiptId, fieldName) => `${API_BASE_PATH}/receipts/${encodeURIComponent(receiptId)}/fields/${encodeURIComponent(fieldName)}/correction`,
  retryReceipt: (receiptId) => `${API_BASE_PATH}/receipts/${encodeURIComponent(receiptId)}/retry`,
  verifyReceipt: (receiptId) => `${API_BASE_PATH}/receipts/${encodeURIComponent(receiptId)}/verify`,
};

export class ApiRequestError extends Error {
  constructor(message, status, code, details = null, requestId = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export class OptimisticConcurrencyError extends ApiRequestError {
  constructor(message, code = "STALE_WRITE", details = null, requestId = null) {
    super(message, 409, code, details, requestId);
    this.name = "OptimisticConcurrencyError";
  }
}

function createUrl(path) {
  return `${APP_CONFIG.apiBaseUrl}${path}`;
}

function requestDefaults(init = {}) {
  return { ...init, credentials: APP_CONFIG.requestCredentials, headers: { accept: "application/json", ...init.headers } };
}

export async function parseResponse(response) {
  if (response.ok) return response.status === 204 ? null : response.json();
  let envelope = null;
  try { envelope = await response.json(); } catch { /* proxy có thể trả body rỗng */ }
  const error = envelope?.error;
  const message = error?.message ?? `Request failed with status ${response.status}.`;
  const code = error?.code ?? `HTTP_${response.status}`;
  if (response.status === 409) throw new OptimisticConcurrencyError(message, code, error?.details ?? null, error?.request_id ?? null);
  throw new ApiRequestError(message, response.status, code, error?.details ?? null, error?.request_id ?? null);
}

function isCanonicalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  return year > 0 && month > 0 && month <= 12 && day > 0 && day <= new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export function validateCorrectionValue(fieldName, value, valueStatus) {
  if (!["PRESENT", "NOT_PRESENT", "UNREADABLE", "AMBIGUOUS", "UNKNOWN"].includes(valueStatus)) throw new Error("value_status không hợp lệ.");
  if (valueStatus !== "PRESENT") {
    if (value !== null) throw new Error(`${valueStatus} requires value null.`);
    return;
  }
  if (fieldName === "total_amount") {
    if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw new Error("total_amount phải là số nguyên VND không âm.");
  } else if (fieldName === "receipt_date") {
    if (typeof value !== "string" || !isCanonicalDate(value)) throw new Error("receipt_date phải là ngày hợp lệ YYYY-MM-DD.");
  } else if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${fieldName} phải là chuỗi không rỗng.`);
  }
}

export function createApplyCorrectionRequest(field, value, valueStatus) {
  validateCorrectionValue(field.field_name, value, valueStatus);
  return { operation: "APPLY", value, value_status: valueStatus, expected_updated_at: field.updated_at };
}

export function createClearCorrectionRequest(field) {
  return { operation: "CLEAR", expected_updated_at: field.updated_at };
}

export function projectApiExtractedField(field, expectedFieldName = field?.field_name, validSourceBlockIds = null) {
  if (!field || typeof field !== "object") throw new Error("Backend field response phải là object.");
  if (!CORE_FIELD_TYPES.includes(field.field_name)) throw new Error(`Backend field_name không canonical: ${field.field_name}`);
  if (field.field_name !== expectedFieldName) throw new Error(`Field key/URL ${expectedFieldName} không khớp field_name ${field.field_name}.`);
  if (!Array.isArray(field.review_reasons) || !Array.isArray(field.source_block_ids)) throw new Error(`${field.field_name} thiếu review/evidence arrays.`);
  if (typeof field.has_correction !== "boolean" || typeof field.machine_needs_review !== "boolean") throw new Error(`${field.field_name} thiếu correction/review flags.`);

  validateCorrectionValue(field.field_name, field.normalized_value, field.value_status);
  validateCorrectionValue(field.field_name, field.effective_value, field.effective_status);

  if (field.has_correction) {
    if (field.corrected_status === null) throw new Error("Field có correction phải có corrected_status.");
    validateCorrectionValue(field.field_name, field.corrected_value, field.corrected_status);
  } else if (field.corrected_status !== null || field.corrected_value !== null) {
    throw new Error("Field không có correction không được mang corrected data.");
  }

  const expectedEffectiveValue = field.has_correction ? field.corrected_value : field.normalized_value;
  const expectedEffectiveStatus = field.has_correction ? field.corrected_status : field.value_status;
  if (!Object.is(field.effective_value, expectedEffectiveValue) || field.effective_status !== expectedEffectiveStatus) {
    throw new Error("effective_value/effective_status phải suy ra từ correction hoặc normalization.");
  }

  const hasPolicy = typeof field.review_policy_version === "string" && field.review_policy_version.trim() !== "";
  if (field.machine_needs_review) {
    if (!field.review_reasons.length || !hasPolicy) throw new Error("machine_needs_review yêu cầu review_reasons và review_policy_version.");
  } else if (field.review_reasons.length) {
    throw new Error("review_reasons phải rỗng khi machine_needs_review=false.");
  }

  if (field.value_status === "PRESENT" && !field.source_block_ids.length) {
    throw new Error("Machine field PRESENT phải có source evidence.");
  }

  if (validSourceBlockIds !== null) {
    if (!(validSourceBlockIds instanceof Set)) throw new Error("Evidence context phải là Set OCR block IDs.");
    for (const sourceId of field.source_block_ids) {
      if (!validSourceBlockIds.has(sourceId)) throw new Error(`Thiếu OCR block ${sourceId} được field ${field.field_name} tham chiếu.`);
    }
  }

  return deepClone(field);
}

export function projectApiReceiptDetail(receipt) {
  if (!receipt || typeof receipt !== "object") throw new Error("Backend receipt response phải là object.");
  if (!["UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED"].includes(receipt.status)) throw new Error(`Backend trả public status không hợp lệ: ${receipt.status}`);
  const keys = Object.keys(receipt.fields ?? {});
  const projected = deepClone(receipt);
  if (keys.length) {
    if (keys.length !== 5 || CORE_FIELD_TYPES.some((key) => !keys.includes(key))) throw new Error("Backend fields phải rỗng hoặc chứa đúng năm canonical keys.");
    const blockIds = new Set((receipt.ocr_blocks ?? []).map((block) => block.block_id));
    projected.fields = Object.fromEntries(CORE_FIELD_TYPES.map((fieldName) => [
      fieldName,
      projectApiExtractedField(receipt.fields[fieldName], fieldName, blockIds),
    ]));
  }
  return projected;
}

export class HttpApi {
  async uploadReceipt(file, options = {}) {
    const form = new FormData();
    form.set("file", file);
    return parseResponse(await fetch(createUrl(apiPaths.receipts), requestDefaults({ method: "POST", body: form, signal: options.signal })));
  }

  async getReceipts(query = {}, options = {}) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value !== undefined && value !== "") params.set(key, String(value));
    return parseResponse(await fetch(createUrl(`${apiPaths.receipts}${params.size ? `?${params}` : ""}`), requestDefaults({ signal: options.signal })));
  }

  async getReceipt(receiptId, options = {}) {
    const detail = await parseResponse(await fetch(createUrl(apiPaths.receipt(receiptId)), requestDefaults({ signal: options.signal })));
    return projectApiReceiptDetail(detail);
  }

  async updateCorrection(receiptId, fieldName, request, options = {}) {
    const response = await fetch(createUrl(apiPaths.fieldCorrection(receiptId, fieldName)), requestDefaults({ method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify(request), signal: options.signal }));
    const field = await parseResponse(response);
    if (!Array.isArray(options.ocrBlocks)) throw new Error("Correction response thiếu receipt OCR evidence context.");
    const validSourceBlockIds = new Set(options.ocrBlocks.map((block) => block.block_id));
    return projectApiExtractedField(field, fieldName, validSourceBlockIds);
  }

  async verifyReceipt(receiptId, expectedUpdatedAt, options = {}) {
    const response = await fetch(createUrl(apiPaths.verifyReceipt(receiptId)), requestDefaults({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_updated_at: expectedUpdatedAt }), signal: options.signal }));
    const detail = await parseResponse(response);
    if (detail.receipt_id !== receiptId || detail.status !== "VERIFIED") throw new Error("Backend verify response không trả đúng hóa đơn VERIFIED.");
    return projectApiReceiptDetail(detail);
  }

  async retryReceipt(receiptId, options = {}) {
    const response = await fetch(createUrl(apiPaths.retryReceipt(receiptId)), requestDefaults({ method: "POST", signal: options.signal }));
    const accepted = await parseResponse(response);
    if (response.status !== 202 || accepted.receipt_id !== receiptId || accepted.retry_accepted !== true) throw new Error("Backend retry response không đúng canonical 202 shape.");
    return accepted;
  }
}

const MOCK_STORAGE_KEY = "vietreceipt:mock-receipts:v1";

function loadStoredMockReceipts() {
  try {
    const stored = globalThis.sessionStorage?.getItem(MOCK_STORAGE_KEY);
    return stored ? JSON.parse(stored) : deepClone(MOCK_RECEIPTS);
  } catch { return deepClone(MOCK_RECEIPTS); }
}

export class MockApi {
  /** @param {{ receipts?: object[], delay?: number, persist?: boolean }} [options] */
  constructor({ receipts, delay = 180, persist = true } = {}) {
    this.receipts = deepClone(receipts ?? loadStoredMockReceipts());
    this.delay = delay;
    this.persistEnabled = persist;
  }

  async pause() { if (this.delay) await new Promise((resolve) => globalThis.setTimeout(resolve, this.delay)); }
  persist() {
    if (!this.persistEnabled) return;
    try { globalThis.sessionStorage?.setItem(MOCK_STORAGE_KEY, JSON.stringify(this.receipts)); } catch { /* storage có thể bị tắt */ }
  }

  async uploadReceipt(file) {
    await this.pause();
    const now = new Date().toISOString();
    const receipt = { receipt_id: crypto.randomUUID(), original_filename: file.name, status: "UPLOADED", processing_stage: null, image_url: null, image_width_px: 1, image_height_px: 1, latest_ocr_run_id: null, latest_kie_run_id: null, fields: {}, ocr_blocks: [], last_error: null, created_at: now, updated_at: now, processed_at: null, verified_at: null };
    this.receipts.unshift(receipt);
    this.persist();
    return summarizeReceipt(receipt);
  }

  async getReceipts(query = {}) {
    await this.pause();
    let items = this.receipts.map(summarizeReceipt);
    if (query.status) items = items.filter((item) => item.status === query.status);
    if (query.merchant_name) items = items.filter((item) => item.merchant_name === query.merchant_name);
    const pageSize = Math.min(100, Number(query.page_size ?? 20));
    const page = Math.max(1, Number(query.page ?? 1));
    const totalItems = items.length;
    return { items: deepClone(items.slice((page - 1) * pageSize, page * pageSize)), page, page_size: pageSize, total_items: totalItems, total_pages: totalItems ? Math.ceil(totalItems / pageSize) : 0 };
  }

  async getReceipt(receiptId) {
    await this.pause();
    const receipt = this.receipts.find((item) => item.receipt_id === receiptId);
    if (!receipt) throw new ApiRequestError("Không tìm thấy hóa đơn.", 404, "RECEIPT_NOT_FOUND");
    return deepClone(receipt);
  }

  async updateCorrection(receiptId, fieldName, request) {
    await this.pause();
    const receipt = this.receipts.find((item) => item.receipt_id === receiptId);
    const field = receipt?.fields?.[fieldName];
    if (!receipt || !field) throw new ApiRequestError("Không tìm thấy hóa đơn hoặc field.", 404, "FIELD_NOT_FOUND");
    if (receipt.status !== "NEEDS_REVIEW") throw new OptimisticConcurrencyError("Receipt không ở NEEDS_REVIEW.", "RECEIPT_STATE_CONFLICT");
    if (request.expected_updated_at !== field.updated_at) throw new OptimisticConcurrencyError("Field đã thay đổi ở nơi khác.");
    const now = new Date(Date.now() + Math.random() * 1000).toISOString();
    if (request.operation === "CLEAR") {
      field.has_correction = false;
      field.corrected_value = null;
      field.corrected_status = null;
      field.effective_value = field.normalized_value;
      field.effective_status = field.value_status;
      field.effective_needs_review = field.machine_needs_review;
    } else {
      validateCorrectionValue(fieldName, request.value, request.value_status);
      field.has_correction = true;
      field.corrected_value = request.value;
      field.corrected_status = request.value_status;
      field.effective_value = request.value;
      field.effective_status = request.value_status;
      field.effective_needs_review = ["AMBIGUOUS", "UNKNOWN"].includes(request.value_status);
    }
    field.updated_at = now;
    receipt.updated_at = now;
    this.persist();
    return deepClone(field);
  }

  async verifyReceipt(receiptId, expectedUpdatedAt) {
    await this.pause();
    const receipt = this.receipts.find((item) => item.receipt_id === receiptId);
    if (!receipt) throw new ApiRequestError("Không tìm thấy hóa đơn.", 404, "RECEIPT_NOT_FOUND");
    if (receipt.updated_at !== expectedUpdatedAt) throw new OptimisticConcurrencyError("Receipt đã thay đổi ở nơi khác.");
    if (CORE_FIELD_TYPES.some((name) => receipt.fields[name]?.effective_needs_review)) throw new ApiRequestError("Vẫn còn field cần kiểm tra.", 422, "UNRESOLVED_FIELDS");
    receipt.status = "VERIFIED";
    receipt.verified_at = new Date().toISOString();
    receipt.updated_at = receipt.verified_at;
    for (const field of Object.values(receipt.fields)) { field.verified = true; field.effective_needs_review = false; }
    this.persist();
    return deepClone(receipt);
  }

  async retryReceipt(receiptId) {
    await this.pause();
    const receipt = this.receipts.find((item) => item.receipt_id === receiptId);
    if (!receipt) throw new ApiRequestError("Không tìm thấy hóa đơn.", 404, "RECEIPT_NOT_FOUND");
    if (receipt.status !== "FAILED" || !receipt.last_error?.retryable) throw new OptimisticConcurrencyError("Không thể thử lại receipt này.", "RECEIPT_STATE_CONFLICT");
    receipt.status = "UPLOADED";
    receipt.last_error = null;
    receipt.updated_at = new Date().toISOString();
    this.persist();
    return { receipt_id: receiptId, retry_accepted: true };
  }
}

export const vietReceiptApi = APP_CONFIG.dataMode === "api" ? new HttpApi() : new MockApi();

export function getApiErrorMessage(error) {
  if (error instanceof OptimisticConcurrencyError) return "Dữ liệu đã được cập nhật ở nơi khác. Hãy tải phiên bản mới trước khi tiếp tục.";
  if (!(error instanceof ApiRequestError)) return error instanceof Error ? `Giá trị không hợp lệ: ${error.message}` : "Không thể kết nối dịch vụ. Hãy kiểm tra mạng và thử lại.";
  if (error.status === 404) return "Không tìm thấy hóa đơn hoặc dữ liệu đã bị thay đổi.";
  if (error.status === 413) return "File vượt quá kích thước cho phép.";
  if (error.status === 415) return "File không phải định dạng ảnh được hỗ trợ.";
  if (error.status === 422) return "Dữ liệu chỉnh sửa không hợp lệ. Hãy kiểm tra lại giá trị.";
  return error.status >= 500 ? "Dịch vụ đang tạm thời không khả dụng. Hãy thử lại sau." : error.message;
}
