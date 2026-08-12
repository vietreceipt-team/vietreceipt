import type {
  ExtractedField,
  FieldCorrectionRequest,
  FieldValue,
  ValueStatus,
} from "../types/receipt";

export const API_BASE_PATH = "/api/v1";

function encodeId(value: string) {
  return encodeURIComponent(value);
}

export const apiPaths = {
  login: `${API_BASE_PATH}/auth/login`,
  register: `${API_BASE_PATH}/auth/register`,
  receipts: `${API_BASE_PATH}/receipts`,
  receipt: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}`,
  receiptImage: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/image`,
  processReceipt: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/process`,
  retryReceipt: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/retry`,
  receiptFields: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/fields`,
  field: (fieldId: string) => `${API_BASE_PATH}/fields/${encodeId(fieldId)}`,
  clearFieldCorrection: (fieldId: string) => `${API_BASE_PATH}/fields/${encodeId(fieldId)}/correction`,
  verifyReceipt: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/verify`,
  receiptHistory: (receiptId: string) => `${API_BASE_PATH}/receipts/${encodeId(receiptId)}/history`,
  dashboardSummary: `${API_BASE_PATH}/dashboard/summary`,
  receiptExport: `${API_BASE_PATH}/receipts/export`,
} as const;

export function createFieldCorrectionRequest(
  field: Pick<ExtractedField, "updated_at">,
  value: FieldValue,
  valueStatus: ValueStatus,
): FieldCorrectionRequest {
  const isPresent = valueStatus === "PRESENT";
  const hasPresentValue = typeof value === "number" || (typeof value === "string" && value.trim().length > 0);

  if (isPresent !== hasPresentValue) {
    throw new Error(
      isPresent
        ? "PRESENT requires a non-null string or integer value."
        : `${valueStatus} requires a null value.`,
    );
  }

  return {
    value,
    value_status: valueStatus,
    expected_updated_at: field.updated_at,
  };
}
