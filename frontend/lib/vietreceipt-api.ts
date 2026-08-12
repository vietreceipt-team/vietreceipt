import type {
  ApiErrorResponse,
  ApplyCorrectionRequest,
  ClearCorrectionRequest,
  FieldCorrectionRequest,
  FieldType,
  FieldValue,
  ReceiptDetail,
  ReceiptField,
  ValueStatus,
  VerifyRequest,
  VerifyResponse,
} from "../types/receipt";

export const API_BASE_PATH = "/api/v1";

function encodePathSegment(value: string) {
  return encodeURIComponent(value);
}

export const apiPaths = {
  receipts: `${API_BASE_PATH}/receipts`,
  receipt: (receiptId: string) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}`,
  field: (receiptId: string, fieldName: FieldType) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}/fields/${encodePathSegment(fieldName)}`,
  verifyReceipt: (receiptId: string) =>
    `${API_BASE_PATH}/receipts/${encodePathSegment(receiptId)}/verify`,
} as const;

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class OptimisticConcurrencyError extends ApiRequestError {
  constructor(message: string, code = "STALE_WRITE") {
    super(message, 409, code);
    this.name = "OptimisticConcurrencyError";
  }
}

export type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export function createApplyCorrectionRequest(
  field: Pick<ReceiptField, "updated_at">,
  correctedValue: FieldValue,
  correctedStatus: ValueStatus,
): ApplyCorrectionRequest {
  const isPresent = correctedStatus === "PRESENT";
  const hasPresentValue =
    typeof correctedValue === "number" ||
    (typeof correctedValue === "string" && correctedValue.trim().length > 0);

  if (isPresent !== hasPresentValue) {
    throw new Error(
      isPresent
        ? "PRESENT requires a non-null string or integer corrected_value."
        : `${correctedStatus} requires corrected_value null.`,
    );
  }

  return {
    operation: "APPLY",
    corrected_status: correctedStatus,
    corrected_value: correctedValue,
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

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;

  let error: ApiErrorResponse | null = null;
  try {
    error = (await response.json()) as ApiErrorResponse;
  } catch {
    // Backend errors should use ErrorResponse; preserve HTTP status if a proxy
    // returns an empty/non-JSON response.
  }

  const code = error?.error.code ?? `HTTP_${response.status}`;
  const message = error?.error.message ?? `Request failed with status ${response.status}.`;
  if (response.status === 409) {
    throw new OptimisticConcurrencyError(message, code);
  }
  throw new ApiRequestError(message, response.status, code);
}

export async function submitFieldCorrection(
  fetcher: FetchLike,
  receiptId: string,
  fieldName: FieldType,
  request: FieldCorrectionRequest,
): Promise<ReceiptField> {
  const response = await fetcher(apiPaths.field(receiptId, fieldName), {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<ReceiptField>(response);
}

export async function submitReceiptVerification(
  fetcher: FetchLike,
  receiptId: string,
  request: VerifyRequest,
): Promise<VerifyResponse> {
  const response = await fetcher(apiPaths.verifyReceipt(receiptId), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<VerifyResponse>(response);
}
