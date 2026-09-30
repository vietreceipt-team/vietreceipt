// @ts-check
import { validateCorrectionValue } from "./api.js";
import { CORE_FIELD_TYPES, FIELD_LABELS, escapeHtml } from "./common.js";
import { canVerifyReceipt, createFieldState, createFieldStates, DIRTY_FIELD_PHASES } from "./review-state.js";

export const C1_MANUAL = "C1_MANUAL";
export const C2_VERIFY_ALL = "C2_VERIFY_ALL";
export const STUDY_MODES = Object.freeze([C1_MANUAL, C2_VERIFY_ALL]);
const SESSION_KEY = "vietreceipt:study-session:v1";

const phaseLabels = {
  VIEW: "Chưa xác nhận",
  EDITING: "Chưa lưu",
  SAVING: "Đang lưu...",
  SAVE_ERROR: "Lưu thất bại",
  STALE: "Dữ liệu đã cũ",
  SAVED: "Đã xác nhận",
};

export function normalizeStudyOrder(value) {
  const order = Array.isArray(value) ? value : String(value ?? "").split(",");
  const normalized = order.map((mode) => String(mode).trim()).filter(Boolean);
  if (normalized.length !== 2 || new Set(normalized).size !== 2 || normalized.some((mode) => !STUDY_MODES.includes(mode))) {
    throw new Error("studyOrder phải chứa đúng C1_MANUAL và C2_VERIFY_ALL, mỗi mode một lần.");
  }
  return normalized;
}

export function resolveStudyConfig(config = {}) {
  const configuredMode = config.studyMode ?? null;
  if (configuredMode !== null && !STUDY_MODES.includes(configuredMode)) throw new Error(`Study mode không hợp lệ: ${configuredMode}`);
  const order = normalizeStudyOrder(config.studyOrder ?? STUDY_MODES);
  if (configuredMode && order[0] !== configuredMode) throw new Error("studyMode phải là condition đầu tiên trong studyOrder.");
  return Object.freeze({ enabled: configuredMode !== null, configuredMode, order: Object.freeze(order) });
}

export function createStudySession(config = {}, storage = globalThis.sessionStorage) {
  const resolved = resolveStudyConfig(config);
  if (!resolved.enabled) {
    return Object.freeze({ enabled: false, currentMode: null, order: resolved.order, reset() { return null; }, completeCondition() { return null; } });
  }

  const signature = resolved.order.join("|");
  let index = 0;
  try {
    const saved = JSON.parse(storage?.getItem(SESSION_KEY) ?? "null");
    if (saved?.signature === signature && Number.isInteger(saved?.index) && saved.index >= 0 && saved.index < resolved.order.length) index = saved.index;
  } catch { /* session storage có thể bị tắt hoặc chứa dữ liệu cũ */ }

  function persist() {
    try { storage?.setItem(SESSION_KEY, JSON.stringify({ signature, index })); } catch { /* research flow vẫn hoạt động không persistence */ }
  }
  persist();

  return {
    enabled: true,
    order: resolved.order,
    get currentMode() { return resolved.order[index]; },
    reset() { index = 0; persist(); return resolved.order[index]; },
    completeCondition() { index = Math.min(resolved.order.length - 1, index + 1); persist(); return resolved.order[index]; },
  };
}

export function createC1ManualFieldState(phase = "EDITING") {
  return { phase, value: null, value_status: "PRESENT", resolved: false, error: null };
}

export function createStudyFieldStates(fields, mode) {
  if (mode === C1_MANUAL) return Object.fromEntries(CORE_FIELD_TYPES.map((name) => [name, createC1ManualFieldState()]));
  if (mode === C2_VERIFY_ALL) return Object.fromEntries(CORE_FIELD_TYPES.filter((name) => fields?.[name]).map((name) => [name, createFieldState(fields[name], "EDITING")]));
  return createFieldStates(fields);
}

export function rearmStudyFieldAfterUnknown(mode, receipt, states, fieldName) {
  if (!STUDY_MODES.includes(mode)) return states;
  return {
    ...states,
    [fieldName]: mode === C1_MANUAL ? createC1ManualFieldState() : createFieldState(receipt.fields[fieldName], "EDITING"),
  };
}

export function studyPendingCount(fields, states, mode) {
  if (STUDY_MODES.includes(mode)) return CORE_FIELD_TYPES.filter((name) => states[name]?.phase !== "SAVED").length;
  return CORE_FIELD_TYPES.filter((name) => fields?.[name]?.effective_needs_review || DIRTY_FIELD_PHASES.has(states[name]?.phase)).length;
}

export function isStudyDraftValid(fieldName, state) {
  if (!state) return false;
  try { validateCorrectionValue(fieldName, state.value, state.value_status); return true; }
  catch { return false; }
}

export function canVerifyStudyReceipt(receipt, states, mode) {
  if (!canVerifyReceipt(receipt, states)) return false;
  if (!STUDY_MODES.includes(mode)) return true;
  return CORE_FIELD_TYPES.every((name) => states[name]?.phase === "SAVED" && isStudyDraftValid(name, states[name]));
}

export function shouldRenderEvidence(mode) {
  return mode !== C1_MANUAL;
}

export function getReviewKeyboardAction(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") return "SAVE";
  if (event.key === "Escape") return "RESET";
  if (event.altKey && event.key === "ArrowUp") return "PREVIOUS_FIELD";
  if (event.altKey && event.key === "ArrowDown") return "NEXT_FIELD";
  return null;
}

export function renderC1ManualForm(fieldStates, canEdit = true) {
  return CORE_FIELD_TYPES.map((fieldName) => {
    const state = fieldStates[fieldName] ?? createC1ManualFieldState();
    const commonClass = "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-500/10 disabled:bg-slate-50 disabled:text-slate-500";
    const disabled = !canEdit || state.value_status !== "PRESENT";
    const input = fieldName === "merchant_address"
      ? `<textarea data-field-input="${fieldName}" rows="2" ${disabled ? "disabled" : ""} class="${commonClass} resize-none leading-6">${escapeHtml(state.value ?? "")}</textarea>`
      : `<input data-field-input="${fieldName}" type="${fieldName === "receipt_date" ? "date" : fieldName === "total_amount" ? "number" : "text"}" ${fieldName === "total_amount" ? 'inputmode="numeric" min="0" step="1"' : ""} value="${escapeHtml(state.value ?? "")}" ${disabled ? "disabled" : ""} class="${commonClass} h-12">`;
    const actions = canEdit ? `<div class="mt-2 flex flex-wrap items-center gap-2"><select data-field-status="${fieldName}" class="h-9 min-w-44 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"><option value="PRESENT" ${state.value_status === "PRESENT" ? "selected" : ""}>Có giá trị</option><option value="NOT_PRESENT" ${state.value_status === "NOT_PRESENT" ? "selected" : ""}>Không có trên hóa đơn</option><option value="UNREADABLE" ${state.value_status === "UNREADABLE" ? "selected" : ""}>Có nhưng không đọc được</option></select><button type="button" data-save-field="${fieldName}" ${!isStudyDraftValid(fieldName, state) || state.phase === "SAVING" ? "disabled" : ""} class="h-9 rounded-lg bg-teal-800 px-3 text-xs font-bold text-white disabled:opacity-40">${state.phase === "SAVING" ? "Đang lưu" : "Xác nhận"}</button><button type="button" data-reset-field="${fieldName}" class="h-9 rounded-lg px-2 text-xs font-bold text-slate-500">Xóa nhập</button></div>` : "";
    return `<fieldset data-field-card="${fieldName}" class="rounded-2xl border border-slate-200 p-3.5"><legend class="px-1 text-sm font-bold text-slate-700">${FIELD_LABELS[fieldName]}</legend><div class="mb-2 flex justify-end"><span class="text-[10px] font-semibold text-slate-500">${phaseLabels[state.phase] ?? state.phase}</span></div>${input}${actions}${state.error ? `<p role="alert" class="mt-2 text-xs font-semibold text-red-700">${escapeHtml(state.error)}</p>` : ""}</fieldset>`;
  }).join("");
}

export function studyModeCopy(mode) {
  if (mode === C1_MANUAL) return { badge: "C1 · Nhập thủ công", title: "Nhập đủ năm trường từ ảnh hóa đơn", description: "Form không hiển thị kết quả máy. Hãy nhập hoặc đánh dấu trạng thái rồi xác nhận từng trường." };
  if (mode === C2_VERIFY_ALL) return { badge: "C2 · Kiểm tra toàn bộ", title: "Đối chiếu đủ năm trường", description: "Prediction và evidence được hiển thị, nhưng mọi trường đều phải được xác nhận hoặc sửa; confidence không làm trường nào bị bỏ qua." };
  return { badge: "Bước 2 · Kiểm chứng", title: "Đối chiếu thông tin", description: "Warning dùng effective_needs_review; confidence chỉ là provenance, không tự skip hoặc verify." };
}
