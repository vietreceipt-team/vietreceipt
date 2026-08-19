import {
  CORE_FIELD_TYPES,
  type CanonicalFields,
  type FieldType,
  type FieldValue,
  type ProcessingStage,
  type ReceiptDetail,
  type ReceiptField,
  type ReceiptStatus,
  type ValueStatus,
} from "../types/receipt";

export type FieldSavePhase =
  | "VIEW"
  | "EDITING"
  | "SAVING"
  | "SAVE_ERROR"
  | "STALE"
  | "SAVED";

export interface FieldInteractionState {
  phase: FieldSavePhase;
  value: FieldValue;
  valueStatus: ValueStatus;
  error: string | null;
}

export type FieldInteractionAction =
  | { type: "EDIT"; value: FieldValue; valueStatus: ValueStatus }
  | { type: "SAVE" }
  | { type: "SAVED"; field: ReceiptField }
  | { type: "SAVE_ERROR"; message: string }
  | { type: "STALE"; message: string }
  | { type: "RESET"; field: ReceiptField };

export function createFieldInteractionState(field: ReceiptField): FieldInteractionState {
  return {
    phase: "VIEW",
    value: field.effective_value,
    valueStatus: field.effective_status,
    error: null,
  };
}

export function getFieldInteractionState(
  states: Partial<Record<FieldType, FieldInteractionState>>,
  field: ReceiptField,
) {
  return states[field.field_name] ?? createFieldInteractionState(field);
}

export function reduceFieldInteraction(
  state: FieldInteractionState,
  action: FieldInteractionAction,
): FieldInteractionState {
  switch (action.type) {
    case "EDIT":
      return {
        phase: "EDITING",
        value: action.value,
        valueStatus: action.valueStatus,
        error: null,
      };
    case "SAVE":
      return { ...state, phase: "SAVING", error: null };
    case "SAVED":
      return {
        phase: "SAVED",
        value: action.field.effective_value,
        valueStatus: action.field.effective_status,
        error: null,
      };
    case "SAVE_ERROR":
      return { ...state, phase: "SAVE_ERROR", error: action.message };
    case "STALE":
      return { ...state, phase: "STALE", error: action.message };
    case "RESET":
      return createFieldInteractionState(action.field);
  }
}

export function replaceReceiptField(
  receipt: ReceiptDetail,
  field: ReceiptField,
): ReceiptDetail {
  if (!receipt.fields) {
    throw new Error("Cannot replace a field before canonical fields are available.");
  }
  return {
    ...receipt,
    fields: { ...receipt.fields, [field.field_name]: field },
  };
}

const draftPhases = new Set<FieldSavePhase>([
  "EDITING",
  "SAVING",
  "SAVE_ERROR",
  "STALE",
]);

export function reconcileFieldStatesAfterCorrection(
  current: Partial<Record<FieldType, FieldInteractionState>>,
  latestFields: CanonicalFields,
  savedFieldName: FieldType,
) {
  return Object.fromEntries(
    CORE_FIELD_TYPES.map((fieldName) => {
      const local = current[fieldName];
      if (
        fieldName !== savedFieldName &&
        local &&
        draftPhases.has(local.phase)
      ) {
        return [fieldName, local];
      }

      const authoritative = createFieldInteractionState(latestFields[fieldName]);
      return [
        fieldName,
        fieldName === savedFieldName
          ? { ...authoritative, phase: "SAVED" as const }
          : authoritative,
      ];
    }),
  ) as Record<FieldType, FieldInteractionState>;
}

export function canVerifyReceipt(receipt: ReceiptDetail) {
  return (
    receipt.status === "NEEDS_REVIEW" &&
    Boolean(receipt.fields) &&
    CORE_FIELD_TYPES.every((fieldName) => {
      const field = receipt.fields?.[fieldName];
      return field && !field.effective_needs_review;
    })
  );
}

export function isPollingStatus(status: ReceiptStatus) {
  return status === "UPLOADED" || status === "PROCESSING";
}

const processingStageLabels: Record<Exclude<ProcessingStage, null>, string> = {
  PREPROCESSING: "Đang chuẩn hóa ảnh...",
  OCR: "Đang nhận dạng văn bản...",
  KIE: "Đang trích xuất thông tin...",
  PERSISTING: "Đang lưu kết quả...",
};

export interface ReceiptStatePresentation {
  title: string;
  description: string;
  tone: "neutral" | "progress" | "review" | "success" | "error";
}

export function getReceiptStatePresentation(
  status: ReceiptStatus,
  processingStage: ProcessingStage = null,
): ReceiptStatePresentation {
  switch (status) {
    case "UPLOADED":
      return {
        title: "Đã tải hóa đơn",
        description: "Đang chờ hệ thống bắt đầu xử lý.",
        tone: "neutral",
      };
    case "PROCESSING":
      return {
        title: "Đang xử lý hóa đơn",
        description: processingStage
          ? processingStageLabels[processingStage]
          : "Worker đang xử lý OCR/KIE. Chưa có phần trăm tiến độ từ Backend.",
        tone: "progress",
      };
    case "NEEDS_REVIEW":
      return {
        title: "Cần người dùng kiểm tra",
        description: "Đối chiếu năm trường chuẩn với ảnh và bằng chứng OCR.",
        tone: "review",
      };
    case "VERIFIED":
      return {
        title: "Hóa đơn đã được xác minh",
        description: "Dữ liệu hiệu lực đang ở chế độ chỉ đọc; bằng chứng máy vẫn được giữ lại.",
        tone: "success",
      };
    case "FAILED":
      return {
        title: "Xử lý hóa đơn thất bại",
        description: "Xem giai đoạn, thông báo lỗi và khả năng thử lại do Backend cung cấp.",
        tone: "error",
      };
  }
}

export function getAdjacentField(current: FieldType, direction: 1 | -1) {
  const index = CORE_FIELD_TYPES.indexOf(current);
  const next = Math.min(CORE_FIELD_TYPES.length - 1, Math.max(0, index + direction));
  return CORE_FIELD_TYPES[next];
}

export function parseCorrectionInput(fieldName: FieldType, rawValue: string): FieldValue {
  if (rawValue.trim() === "") return null;
  if (fieldName !== "total_amount") return rawValue;

  const compact = rawValue.trim().replace(/[.\s]/g, "");
  if (!/^\d+$/.test(compact)) return rawValue;
  return Number(compact);
}
