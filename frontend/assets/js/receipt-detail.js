import { APP_CONFIG } from "./config.js";
import { createApplyCorrectionRequest, createClearCorrectionRequest, getApiErrorMessage, OptimisticConcurrencyError, vietReceiptApi } from "./api.js";
import { CORE_FIELD_TYPES, FIELD_LABELS, announce, escapeHtml, formatVnd, getReceiptIdFromLocation, renderNavigation } from "./common.js";
import { canVerifyReceipt, createFieldState, createFieldStates, DIRTY_FIELD_PHASES, editFieldStatus, editFieldValue, findFieldsForSourceBlock, getAdjacentField } from "./review-state.js";
import { saveCorrectionAndRefresh } from "./review-workflow.js";
import { createReviewTelemetry, withReviewActivityPaused } from "./review-telemetry.js";
import {
  C1_MANUAL,
  C2_VERIFY_ALL,
  canVerifyStudyReceipt,
  createC1ManualFieldState,
  createStudyFieldStates,
  createStudySession,
  getReviewKeyboardAction,
  isStudyDraftValid,
  rearmStudyFieldAfterUnknown,
  renderC1ManualForm,
  shouldRenderEvidence,
  studyModeCopy,
  studyPendingCount,
} from "./study-mode.js";

const studySession = createStudySession(APP_CONFIG);
const studyMode = studySession.currentMode;
renderNavigation();

const statusStyles = {
  PRESENT: { label: "Có dữ liệu", badge: "bg-emerald-50 text-emerald-700 ring-emerald-200", border: "border-emerald-300 focus:border-emerald-500 focus:ring-emerald-500/10", dot: "bg-emerald-500" },
  NOT_PRESENT: { label: "Không có trên hóa đơn", badge: "bg-slate-100 text-slate-700 ring-slate-200", border: "border-slate-300 focus:border-slate-500 focus:ring-slate-500/10", dot: "bg-slate-500" },
  UNREADABLE: { label: "Không đọc được", badge: "bg-orange-50 text-orange-800 ring-orange-200", border: "border-orange-300 focus:border-orange-500 focus:ring-orange-500/10", dot: "bg-orange-500" },
  AMBIGUOUS: { label: "Mơ hồ", badge: "bg-red-50 text-red-700 ring-red-200", border: "border-red-300 focus:border-red-500 focus:ring-red-500/10", dot: "bg-red-500" },
  UNKNOWN: { label: "Chưa xác định", badge: "bg-amber-50 text-amber-800 ring-amber-200", border: "border-amber-300 focus:border-amber-500 focus:ring-amber-500/10", dot: "bg-amber-500" },
};

const reasonLabels = {
  NO_CANDIDATE: "Không có ứng viên", LOW_CONFIDENCE: "Độ tin cậy thấp", MULTIPLE_CANDIDATES: "Có nhiều ứng viên",
  AMBIGUOUS_FORMAT: "Định dạng mơ hồ", UNREADABLE_SOURCE: "Nguồn không đọc được", UNSUPPORTED_CURRENCY: "Tiền tệ chưa hỗ trợ",
  NEGATIVE_AMOUNT: "Số tiền âm", MISSING_DATE_COMPONENT: "Ngày thiếu thành phần", UNSUPPORTED_TWO_DIGIT_YEAR: "Năm hai chữ số chưa hỗ trợ",
  SOURCE_ROLE_UNCLEAR: "Vai trò nguồn chưa rõ", NORMALIZATION_FAILED: "Không chuẩn hóa an toàn",
};

const phaseLabels = {
  VIEW: "Chưa thay đổi", EDITING: "Chưa lưu", SAVING: "Đang lưu...", SAVE_ERROR: "Lưu thất bại", STALE: "Dữ liệu đã cũ", SAVED: "Đã lưu",
};

const main = document.querySelector("#main-content");
const receiptId = getReceiptIdFromLocation();
let receipt = null;
let fieldStates = {};
let zoom = 95;
let rotation = 0;
let activeFields = [];
let activeBlockIds = new Set();
let verifying = false;
let staleMessage = null;
let pollingTimer = null;
let pollAttempt = 0;
let telemetry = null;
let visibilityPauseToken = null;

function orderedFields() { return receipt?.fields ? CORE_FIELD_TYPES.map((name) => receipt.fields[name]).filter(Boolean) : []; }
function field(name) { return receipt?.fields?.[name]; }
function reviewPendingCount() {
  return studyPendingCount(receipt?.fields, fieldStates, studyMode);
}
function draftIsValid(name) { return isStudyDraftValid(name, fieldStates[name]); }
function valueLabel(value) { return value === null ? "—" : typeof value === "number" ? formatVnd(value) : String(value); }
function fieldValueChanged(before, after) {
  return Boolean(before && after) && (!Object.is(before.effective_value, after.effective_value) || before.effective_status !== after.effective_status);
}

function polygonStyle(block) {
  const xs = block.polygon.map((point) => point.x);
  const ys = block.polygon.map((point) => point.y);
  const left = Math.min(...xs);
  const top = Math.min(...ys);
  return `left:${left * 100}%;top:${top * 100}%;width:${(Math.max(...xs) - left) * 100}%;height:${(Math.max(...ys) - top) * 100}%`;
}

function receiptPreview() {
  const overlays = shouldRenderEvidence(studyMode) ? (receipt.ocr_blocks ?? []).map((block) => `<button type="button" data-block-id="${escapeHtml(block.block_id)}" class="absolute border border-cyan-500/70 bg-cyan-300/10 transition ${activeBlockIds.has(block.block_id) ? "ocr-block-active" : ""}" style="${polygonStyle(block)}" aria-label="OCR: ${escapeHtml(block.text)}"></button>`).join("") : "";
  if (receipt.image_url) {
    return `<div id="receipt-paper" class="receipt-shadow relative w-[340px] shrink-0 origin-top transition-transform duration-200 sm:w-[390px]" style="transform:scale(${zoom / 100}) rotate(${rotation}deg)"><img src="${escapeHtml(receipt.image_url)}" alt="Ảnh hóa đơn gốc ${escapeHtml(receipt.original_filename)}" class="block h-auto w-full bg-white"><div class="absolute inset-0">${overlays}</div></div>`;
  }
  return `<div id="receipt-paper" class="grid min-h-96 w-[340px] place-items-center rounded-2xl border border-white/10 bg-slate-900/70 p-8 text-center text-sm text-slate-300 sm:w-[390px]" style="transform:scale(${zoom / 100}) rotate(${rotation}deg)"><div><p class="text-3xl">▧</p><p class="mt-3 font-bold text-white">Backend chưa cung cấp image_url</p><p class="mt-2 text-xs leading-5 text-slate-400">Frontend không tái dựng ảnh từ OCR/KIE và không tự sinh polygon.</p></div></div>`;
}

function stateDescription() {
  if (receipt.status === "UPLOADED") return "Đã tải hóa đơn. Đang chờ hệ thống bắt đầu xử lý.";
  if (receipt.status === "PROCESSING") {
    const labels = { PREPROCESSING: "Đang chuẩn hóa ảnh...", OCR: "Đang nhận dạng văn bản...", KIE: "Đang trích xuất thông tin...", PERSISTING: "Đang lưu kết quả..." };
    return labels[receipt.processing_stage] ?? "Worker đang xử lý OCR/KIE. Backend chưa cung cấp phần trăm tiến độ.";
  }
  return receipt.last_error?.message ?? "Pipeline đã dừng do lỗi xử lý.";
}

function renderNoFields() {
  main.innerHTML = `<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6"><a href="/receipts/" data-change-receipt class="text-sm font-bold text-teal-700">← Quay lại danh sách</a><section class="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"><p class="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">${escapeHtml(receipt.status)}</p><h1 class="mt-2 text-2xl font-bold text-slate-950">${escapeHtml(receipt.original_filename)}</h1><p class="mt-3 text-sm leading-6 text-slate-500">${escapeHtml(stateDescription())}</p>${receipt.status === "FAILED" && receipt.last_error ? `<dl class="mt-5 grid gap-3 rounded-2xl bg-red-50 p-4 text-sm sm:grid-cols-3"><div><dt class="text-red-500">Giai đoạn</dt><dd class="mt-1 font-bold text-red-900">${escapeHtml(receipt.last_error.stage)}</dd></div><div><dt class="text-red-500">Mã lỗi</dt><dd class="mt-1 font-bold text-red-900">${escapeHtml(receipt.last_error.code)}</dd></div><div><dt class="text-red-500">Có thể thử lại</dt><dd class="mt-1 font-bold text-red-900">${receipt.last_error.retryable ? "Có" : "Không"}</dd></div></dl>${receipt.last_error.retryable ? '<button id="retry-receipt" type="button" class="mt-5 h-11 rounded-xl bg-teal-800 px-5 text-sm font-bold text-white hover:bg-teal-900">Thử xử lý lại</button>' : ""}` : ""}<p class="mt-5 text-xs text-slate-400">Frontend chỉ hiển thị image_url và evidence do Backend cung cấp; không gọi OCR/KIE hoặc Storage trực tiếp.</p></section></div>`;
  document.querySelector("#retry-receipt")?.addEventListener("click", retryReceipt);
  document.querySelector("[data-change-receipt]")?.addEventListener("click", () => telemetry?.changeReceipt());
}

function renderReview() {
  const count = reviewPendingCount();
  main.innerHTML = `<div class="relative flex h-[calc(100dvh-56px)] min-h-0 flex-col overflow-hidden bg-slate-100 lg:flex-row">
    <section class="flex h-[46%] min-h-0 flex-col border-b border-slate-300 bg-slate-800 lg:h-full lg:w-[58%] lg:border-b-0 lg:border-r" aria-label="Ảnh hóa đơn gốc">
      <div class="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/10 bg-slate-900/90 px-3 text-white sm:px-4"><div class="flex min-w-0 items-center gap-3"><a href="/receipts/" data-change-receipt class="grid size-8 shrink-0 place-items-center rounded-lg bg-white/5 text-lg transition hover:bg-white/10" aria-label="Quay lại danh sách">←</a><div class="min-w-0"><p class="truncate text-xs font-bold">${escapeHtml(receipt.original_filename)}</p><p class="mt-0.5 text-[10px] text-slate-400">Ảnh gốc · ${receipt.image_width_px} × ${receipt.image_height_px} px</p></div></div><span id="review-progress-top" class="hidden rounded-full px-2.5 py-1 text-[10px] font-bold sm:inline ${receipt.status === "VERIFIED" ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}">${receipt.status === "VERIFIED" ? `VERIFIED · ${escapeHtml(receipt.verified_at ?? "")}` : `${count} trường cần xử lý/lưu`}</span></div>
      <div class="paper-texture relative min-h-0 flex-1 overflow-auto p-6 sm:p-10"><div id="receipt-preview" class="flex min-h-full min-w-full items-start justify-center">${receiptPreview()}</div></div>
      <div class="flex h-14 shrink-0 items-center justify-center gap-2 border-t border-white/10 bg-slate-900 px-3 text-white"><button id="zoom-out" type="button" class="grid size-8 place-items-center rounded-lg bg-white/5 text-lg hover:bg-white/10" aria-label="Thu nhỏ">−</button><input id="zoom-range" type="range" min="65" max="145" step="5" value="${zoom}" class="w-24 accent-teal-400 sm:w-36" aria-label="Mức thu phóng"><button id="zoom-in" type="button" class="grid size-8 place-items-center rounded-lg bg-white/5 text-lg hover:bg-white/10" aria-label="Phóng to">+</button><span id="zoom-label" class="w-10 text-center text-[11px] font-bold tabular-nums text-slate-300">${zoom}%</span><span class="mx-1 h-6 w-px bg-white/10"></span><button id="rotate-left" type="button" class="grid h-8 place-items-center rounded-lg bg-white/5 px-2.5 text-xs font-bold hover:bg-white/10" aria-label="Xoay trái">↶</button><button id="rotate-right" type="button" class="grid h-8 place-items-center rounded-lg bg-white/5 px-2.5 text-xs font-bold hover:bg-white/10" aria-label="Xoay phải">↷</button></div>
    </section>
    <section class="flex min-h-0 flex-1 flex-col bg-white lg:h-full lg:w-[42%]" aria-label="Biểu mẫu kiểm chứng"><header class="shrink-0 border-b border-slate-200 px-5 py-4 sm:px-6"><p id="review-mode-badge" class="text-[11px] font-bold uppercase tracking-[0.14em] text-teal-700">Bước 2 · Kiểm chứng</p><div class="mt-1.5 flex items-start justify-between gap-4"><h1 id="review-mode-title" class="text-xl font-bold tracking-[-0.025em] text-slate-950">Đối chiếu thông tin</h1><span id="review-count" class="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-700">${count}/5 cần xử lý</span></div><p id="review-mode-description" class="mt-2 text-xs leading-5 text-slate-500">Warning dùng effective_needs_review; confidence chỉ là provenance, không tự skip hoặc verify.</p></header>
      <form id="review-form" class="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6"><div id="stale-banner"></div><div id="field-list" class="space-y-5"></div></form>
      <footer class="shrink-0 border-t border-slate-200 bg-white p-4 sm:px-6"><p class="mb-2 text-[10px] text-slate-400">Ctrl/⌘+Enter: lưu field · Esc: bỏ draft · Alt+↑/↓: chuyển field</p><div class="flex gap-3"><button id="back-button" type="button" class="h-11 flex-1 rounded-xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50">Quay lại</button><button id="verify-button" type="button" class="h-11 flex-[1.8] rounded-xl bg-teal-800 px-4 text-sm font-bold text-white shadow-sm transition hover:bg-teal-900 disabled:cursor-not-allowed disabled:opacity-45"></button></div></footer>
    </section>
  </div>`;
  applyStudyChrome();
  renderStaleBanner();
  renderFields();
  bindReviewEvents();
  updateControls();
}

function applyStudyChrome() {
  const copy = studyModeCopy(studyMode);
  main.firstElementChild?.setAttribute("data-study-mode", studyMode ?? "STANDARD_REVIEW");
  const badge = document.querySelector("#review-mode-badge");
  const title = document.querySelector("#review-mode-title");
  const description = document.querySelector("#review-mode-description");
  if (badge) badge.textContent = copy.badge;
  if (title) title.textContent = copy.title;
  if (description) description.textContent = copy.description;
  if (studySession.enabled && description) description.insertAdjacentHTML("afterend", '<button id="reset-study-session" type="button" class="mt-3 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-600 hover:bg-slate-50">Reset phiên nghiên cứu</button>');
}

function renderStaleBanner() {
  const host = document.querySelector("#stale-banner");
  if (!host) return;
  host.innerHTML = staleMessage ? `<div role="alert" class="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"><p class="font-bold">Cần tải phiên bản hóa đơn mới.</p><p class="mt-1 text-xs">${escapeHtml(staleMessage)}</p><p class="mt-1 text-xs">Mutation không được tự retry bằng token cũ.</p><button id="reload-latest" type="button" class="mt-3 rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white">Tải phiên bản mới</button></div>` : "";
  document.querySelector("#reload-latest")?.addEventListener("click", reloadLatest);
}

function renderFields() {
  const canEdit = receipt.status === "NEEDS_REVIEW" && !staleMessage;
  const host = document.querySelector("#field-list");
  if (studyMode === C1_MANUAL) { host.innerHTML = renderC1ManualForm(fieldStates, canEdit); return; }
  host.innerHTML = orderedFields().map((item) => {
    const state = fieldStates[item.field_name];
    const style = statusStyles[state.value_status];
    const active = activeFields.includes(item.field_name);
    const commonClass = `w-full rounded-xl border bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition focus:ring-4 disabled:bg-slate-50 disabled:text-slate-500 ${style.border}`;
    const input = item.field_name === "merchant_address"
      ? `<textarea data-field-input="${item.field_name}" rows="2" ${!canEdit || state.value_status !== "PRESENT" ? "disabled" : ""} class="${commonClass} resize-none leading-6">${escapeHtml(state.value ?? "")}</textarea>`
      : `<input data-field-input="${item.field_name}" type="${item.field_name === "receipt_date" ? "date" : item.field_name === "total_amount" ? "number" : "text"}" ${item.field_name === "total_amount" ? 'inputmode="numeric" min="0" step="1"' : ""} value="${escapeHtml(state.value ?? "")}" ${!canEdit || state.value_status !== "PRESENT" ? "disabled" : ""} class="${commonClass} h-12">`;
    const showApply = canEdit && (item.effective_needs_review || DIRTY_FIELD_PHASES.has(state.phase));
    const phaseTone = state.phase === "SAVED" ? "text-emerald-700" : state.phase === "SAVE_ERROR" || state.phase === "STALE" ? "text-red-700" : state.phase === "SAVING" ? "text-sky-700" : "text-slate-400";
    return `<fieldset data-field-card="${item.field_name}" class="rounded-2xl border border-slate-200 p-3.5 ${active ? "field-source-active" : ""}"><legend class="px-1 text-sm font-bold text-slate-700">${FIELD_LABELS[item.field_name]}</legend>
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2"><span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-black ring-1 ring-inset ${style.badge}"><span class="size-1.5 rounded-full ${style.dot}"></span>${Math.round(item.confidence * 100)}% · ${style.label}</span><span class="text-[10px] font-semibold ${phaseTone}">${phaseLabels[state.phase]}</span></div>
      ${item.review_reasons.length ? `<p class="mb-2 text-[10px] font-semibold text-amber-700">${item.review_reasons.map((reason) => escapeHtml(reasonLabels[reason] ?? reason)).join(" · ")}</p>` : ""}${input}
      <div class="mt-2 grid gap-1 rounded-lg bg-slate-50 px-3 py-2 text-[10px] leading-4 text-slate-500"><p>Machine normalized: <strong class="text-slate-700">${escapeHtml(valueLabel(item.normalized_value))}</strong></p>${item.has_correction ? `<p>Human correction: <strong class="text-teal-800">${escapeHtml(valueLabel(item.corrected_value))}</strong></p>` : ""}<p>Effective: <strong class="text-slate-800">${escapeHtml(valueLabel(item.effective_value))}</strong></p></div>
      ${item.predicted_value !== null && item.predicted_value !== item.effective_value ? `<p class="mt-2 text-[11px] leading-4 text-slate-500">KIE predicted: <span class="font-semibold text-slate-700">${escapeHtml(item.predicted_value)}</span>. Prediction không tự trở thành effective value.</p>` : ""}
      ${canEdit ? `<div class="mt-2 flex flex-wrap items-center gap-2"><select data-field-status="${item.field_name}" class="h-9 min-w-44 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700">${state.value_status === "AMBIGUOUS" ? '<option value="AMBIGUOUS" disabled>Mơ hồ – cần quyết định</option>' : ""}${state.value_status === "UNKNOWN" ? '<option value="UNKNOWN" disabled>Chưa xác định – cần quyết định</option>' : ""}<option value="PRESENT" ${state.value_status === "PRESENT" ? "selected" : ""}>Có giá trị</option><option value="NOT_PRESENT" ${state.value_status === "NOT_PRESENT" ? "selected" : ""}>Không có trên hóa đơn</option><option value="UNREADABLE" ${state.value_status === "UNREADABLE" ? "selected" : ""}>Có nhưng không đọc được</option></select>${showApply ? `<button type="button" data-save-field="${item.field_name}" ${!draftIsValid(item.field_name) || state.phase === "SAVING" ? "disabled" : ""} class="h-9 rounded-lg bg-teal-800 px-3 text-xs font-bold text-white disabled:opacity-40">${state.phase === "SAVING" ? "Đang lưu" : "Lưu APPLY"}</button>` : ""}${item.has_correction ? `<button type="button" data-clear-field="${item.field_name}" ${state.phase === "SAVING" ? "disabled" : ""} class="h-9 rounded-lg border border-slate-300 bg-white px-3 text-xs font-bold text-slate-700">CLEAR</button>` : ""}${DIRTY_FIELD_PHASES.has(state.phase) && state.phase !== "SAVING" ? `<button type="button" data-reset-field="${item.field_name}" class="h-9 rounded-lg px-2 text-xs font-bold text-slate-500">Bỏ draft</button>` : ""}</div>${state.error ? `<p role="alert" class="mt-2 text-xs font-semibold text-red-700">${escapeHtml(state.error)}</p>` : ""}` : ""}
    </fieldset>`;
  }).join("");
}

function updateControls() {
  const count = reviewPendingCount();
  const button = document.querySelector("#verify-button");
  if (!button) return;
  const allowed = canVerifyStudyReceipt(receipt, fieldStates, studyMode) && !staleMessage;
  button.disabled = verifying || !allowed;
  button.textContent = verifying ? "Đang xác minh..." : receipt.status === "VERIFIED" ? "Đã xác minh" : allowed ? "Xác nhận hóa đơn" : count ? `Còn ${count} field cần lưu` : "Chưa thể xác minh";
  document.querySelector("#review-count").textContent = `${count}/5 cần xử lý`;
  const top = document.querySelector("#review-progress-top");
  if (top && receipt.status !== "VERIFIED") top.textContent = `${count} trường cần xử lý/lưu`;
}

function updatePreviewTransform() {
  const paper = document.querySelector("#receipt-paper");
  if (paper) paper.style.transform = `scale(${zoom / 100}) rotate(${rotation}deg)`;
  if (document.querySelector("#zoom-range")) document.querySelector("#zoom-range").value = zoom;
  if (document.querySelector("#zoom-label")) document.querySelector("#zoom-label").textContent = `${zoom}%`;
}

function highlightFields(names) {
  activeFields = names;
  activeBlockIds = new Set(names.flatMap((name) => field(name)?.source_block_ids ?? []));
  document.querySelectorAll("[data-field-card]").forEach((card) => card.classList.toggle("field-source-active", names.includes(card.dataset.fieldCard)));
  document.querySelectorAll("[data-block-id]").forEach((block) => block.classList.toggle("ocr-block-active", activeBlockIds.has(block.dataset.blockId)));
  names.forEach((name) => telemetry?.focusField(name));
}

function focusField(name) {
  highlightFields([name]);
  const card = document.querySelector(`[data-field-card="${name}"]`);
  card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  card?.querySelector("[data-field-input]:not(:disabled),[data-field-status]")?.focus();
}

function resetReviewField(name) {
  if (studyMode === C1_MANUAL) return createC1ManualFieldState();
  if (studyMode === C2_VERIFY_ALL) return createFieldState(field(name), "EDITING");
  return createFieldState(field(name));
}

function resetStudySession() {
  if (!studySession.enabled || !globalThis.confirm?.("Reset toàn bộ tiến trình condition của phiên nghiên cứu?")) return;
  telemetry?.resetSession();
  studySession.reset();
  globalThis.location.reload();
}

function bindReviewEvents() {
  document.querySelector("#back-button").addEventListener("click", () => { telemetry?.changeReceipt(); window.location.assign("/receipts/"); });
  document.querySelector("[data-change-receipt]")?.addEventListener("click", () => telemetry?.changeReceipt());
  document.querySelector("#verify-button").addEventListener("click", verifyReceipt);
  document.querySelector("#reset-study-session")?.addEventListener("click", resetStudySession);
  document.querySelector("#zoom-out").addEventListener("click", () => { zoom = Math.max(65, zoom - 10); updatePreviewTransform(); });
  document.querySelector("#zoom-in").addEventListener("click", () => { zoom = Math.min(145, zoom + 10); updatePreviewTransform(); });
  document.querySelector("#zoom-range").addEventListener("input", (event) => { zoom = Number(event.target.value); updatePreviewTransform(); });
  document.querySelector("#rotate-left").addEventListener("click", () => { rotation -= 90; updatePreviewTransform(); });
  document.querySelector("#rotate-right").addEventListener("click", () => { rotation += 90; updatePreviewTransform(); });
  const form = document.querySelector("#review-form");
  form.addEventListener("pointerdown", () => telemetry?.startReview(), { once: true });
  form.addEventListener("focusin", (event) => { const target = event.target.closest("[data-field-input],[data-field-status]"); if (target) highlightFields([target.dataset.fieldInput ?? target.dataset.fieldStatus]); });
  form.addEventListener("input", (event) => {
    const name = event.target.dataset.fieldInput;
    if (!name) return;
    fieldStates[name] = editFieldValue(fieldStates[name], name, event.target.value);
    telemetry?.editField(name);
    updateControls();
  });
  form.addEventListener("change", (event) => {
    const name = event.target.dataset.fieldStatus;
    if (!name) return;
    fieldStates[name] = editFieldStatus(fieldStates[name], event.target.value);
    telemetry?.editField(name);
    renderFields(); updateControls(); highlightFields([name]);
  });
  form.addEventListener("click", (event) => {
    const save = event.target.closest("[data-save-field]");
    const clear = event.target.closest("[data-clear-field]");
    const reset = event.target.closest("[data-reset-field]");
    if (save) saveField(save.dataset.saveField, "APPLY");
    if (clear) saveField(clear.dataset.clearField, "CLEAR");
    if (reset) { fieldStates[reset.dataset.resetField] = resetReviewField(reset.dataset.resetField); renderFields(); updateControls(); }
  });
  form.addEventListener("keydown", (event) => {
    const target = event.target.closest("[data-field-input],[data-field-status]");
    const name = target?.dataset.fieldInput ?? target?.dataset.fieldStatus ?? activeFields[0];
    if (!name) return;
    telemetry?.startReview();
    if (target && (event.key.length === 1 || ["Backspace", "Delete"].includes(event.key))) telemetry?.recordKeystroke();
    const action = getReviewKeyboardAction(event);
    if (action === "SAVE") { event.preventDefault(); saveField(name, "APPLY"); }
    if (action === "RESET") { event.preventDefault(); fieldStates[name] = resetReviewField(name); renderFields(); updateControls(); focusField(name); }
    if (["PREVIOUS_FIELD", "NEXT_FIELD"].includes(action)) { event.preventDefault(); focusField(getAdjacentField(name, action === "NEXT_FIELD" ? 1 : -1)); }
  });
  document.querySelector("#receipt-preview").addEventListener("click", (event) => {
    const block = event.target.closest("[data-block-id]");
    if (!block) return;
    telemetry?.startReview();
    const matches = findFieldsForSourceBlock(receipt.fields, block.dataset.blockId);
    if (matches.length) { highlightFields(matches); document.querySelector(`[data-field-card="${matches[0]}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
  });
}

async function saveField(name, operation) {
  const current = fieldStates[name];
  if (!current || current.phase === "SAVING" || staleMessage) return;
  if (operation === "APPLY" && !draftIsValid(name)) { announce("Giá trị field chưa hợp lệ để APPLY.", "error"); return; }

  let request;
  let authoritativeBefore;
  try {
    const item = field(name);
    authoritativeBefore = item;
    request = operation === "CLEAR" ? createClearCorrectionRequest(item) : createApplyCorrectionRequest(item, current.value, current.value_status);
  } catch (error) {
    fieldStates[name] = { ...current, phase: "SAVE_ERROR", error: getApiErrorMessage(error) };
    renderFields(); updateControls(); highlightFields([name]);
    return;
  }

  fieldStates[name] = { ...current, phase: "SAVING", error: null };
  renderFields(); updateControls(); highlightFields([name]);

  const result = await withReviewActivityPaused(telemetry, "correction-api", () => saveCorrectionAndRefresh({
    api: vietReceiptApi,
    receipt,
    fieldStates,
    fieldName: name,
    request,
  }));

  if (result.outcome === "MUTATION_ERROR") {
    if (result.error instanceof OptimisticConcurrencyError) {
      staleMessage = getApiErrorMessage(result.error);
      fieldStates[name] = { ...current, phase: "STALE", error: staleMessage };
    } else {
      fieldStates[name] = { ...current, phase: "SAVE_ERROR", error: getApiErrorMessage(result.error) };
    }
  } else {
    receipt = result.receipt;
    fieldStates = result.fieldStates;
    if (result.outcome === "REFRESHED_AFTER_UNKNOWN_MUTATION") fieldStates = rearmStudyFieldAfterUnknown(studyMode, receipt, fieldStates, name);
    if (result.outcome === "MUTATION_OUTCOME_UNKNOWN") {
      staleMessage = "Backend đã trả HTTP 2xx nhưng correction response không hợp lệ và GET reload thất bại. Verify và mutation bị khóa để tránh dùng token cũ.";
      announce("Kết quả correction chưa xác định. Hãy tải phiên bản mới trước khi tiếp tục.", "error");
    } else if (result.outcome === "REFRESH_REQUIRED") {
      telemetry?.confirmField(name, operation, fieldValueChanged(authoritativeBefore, result.receipt.fields[name]));
      staleMessage = "Correction đã được Backend lưu, nhưng frontend chưa lấy được receipt token mới. Verify bị khóa để tránh gửi token cũ.";
      announce("Correction đã được lưu. Hãy tải phiên bản mới trước khi tiếp tục.", "error");
    } else if (result.outcome === "REFRESHED_AFTER_UNKNOWN_MUTATION") {
      telemetry?.confirmField(name, operation, fieldValueChanged(authoritativeBefore, result.receipt.fields[name]));
      staleMessage = null;
      announce("Correction response không hợp lệ; đã tải receipt authoritative mới từ Backend.");
    } else {
      telemetry?.confirmField(name, operation, fieldValueChanged(authoritativeBefore, result.receipt.fields[name]));
      announce(operation === "CLEAR" ? "Đã CLEAR correction của " + FIELD_LABELS[name] + "." : "Đã lưu " + FIELD_LABELS[name] + ".");
    }
  }

  renderStaleBanner(); renderFields(); updateControls(); highlightFields([name]);
}
async function reloadLatest() {
  try {
    receipt = await withReviewActivityPaused(telemetry, "reload-latest", () => vietReceiptApi.getReceipt(receipt.receipt_id));
    fieldStates = createStudyFieldStates(receipt.fields, studyMode);
    staleMessage = null;
    announce("Đã tải phiên bản mới nhất từ Backend.");
    renderReview();
  } catch (error) { announce(getApiErrorMessage(error), "error"); }
}

async function verifyReceipt() {
  if (verifying || !canVerifyStudyReceipt(receipt, fieldStates, studyMode) || staleMessage) return;
  verifying = true; updateControls();
  try {
    receipt = await withReviewActivityPaused(telemetry, "verify-api", () => vietReceiptApi.verifyReceipt(receipt.receipt_id, receipt.updated_at));
    if (!studySession.enabled) fieldStates = createFieldStates(receipt.fields);
    telemetry?.verify();
    telemetry?.complete();
    studySession.completeCondition();
    announce("Hóa đơn đã được Backend xác minh.");
    renderReview();
  } catch (error) {
    if (error instanceof OptimisticConcurrencyError) { staleMessage = getApiErrorMessage(error); renderStaleBanner(); }
    announce(getApiErrorMessage(error), "error");
  } finally { verifying = false; updateControls(); }
}

async function retryReceipt() {
  const button = document.querySelector("#retry-receipt");
  if (button) { button.disabled = true; button.textContent = "Đang gửi yêu cầu..."; }
  try {
    await withReviewActivityPaused(telemetry, "retry-api", async () => {
      await vietReceiptApi.retryReceipt(receipt.receipt_id);
      telemetry?.retry();
      receipt = await vietReceiptApi.getReceipt(receipt.receipt_id);
    });
    announce("Backend đã chấp nhận lên lịch thử lại.");
    renderReceipt();
  } catch (error) {
    announce(getApiErrorMessage(error), "error");
    if (button) { button.disabled = false; button.textContent = "Thử xử lý lại"; }
  }
}

function renderReceipt() {
  globalThis.clearTimeout(pollingTimer);
  const hasFields = Boolean(receipt.fields && Object.keys(receipt.fields).length);
  telemetry?.observeReceipt(receipt.status, hasFields);
  if (!hasFields) {
    renderNoFields();
    if (APP_CONFIG.dataMode === "api" && ["UPLOADED", "PROCESSING"].includes(receipt.status)) schedulePoll();
  } else {
    fieldStates = createStudyFieldStates(receipt.fields, studyMode);
    renderReview();
  }
}

function schedulePoll() {
  if (pollAttempt >= 120) return;
  const delay = Math.min(10000, 2500 + pollAttempt * 250);
  pollingTimer = globalThis.setTimeout(async () => {
    pollAttempt += 1;
    try { receipt = await withReviewActivityPaused(telemetry, "poll-api", () => vietReceiptApi.getReceipt(receipt.receipt_id)); renderReceipt(); }
    catch { schedulePoll(); }
  }, delay);
}

globalThis.addEventListener?.("pagehide", () => { globalThis.clearTimeout(pollingTimer); telemetry?.pauseActive("pagehide"); }, { once: true });
globalThis.document?.addEventListener?.("visibilitychange", () => {
  if (document.hidden) {
    if (visibilityPauseToken === null) visibilityPauseToken = telemetry?.pauseActive("document-hidden") ?? null;
    return;
  }
  if (visibilityPauseToken !== null) telemetry?.resumeActive(visibilityPauseToken);
  visibilityPauseToken = null;
});

if (!receiptId) {
  main.innerHTML = `<div class="grid min-h-[calc(100dvh-56px)] place-items-center px-4 text-center"><div><p class="text-5xl">404</p><h1 class="mt-4 text-2xl font-bold text-slate-900">Không tìm thấy mã hóa đơn</h1><a href="/receipts/" class="mt-5 inline-flex rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white">Quay lại danh sách</a></div></div>`;
} else {
  main.innerHTML = `<div class="grid min-h-[calc(100dvh-56px)] place-items-center"><div class="text-center"><div class="mx-auto size-8 animate-spin rounded-full border-4 border-slate-200 border-t-teal-700"></div><p class="mt-4 text-sm font-semibold text-slate-500">Đang tải hóa đơn…</p></div></div>`;
  telemetry = createReviewTelemetry(receiptId, undefined, { reviewMode: studyMode ?? "PREFILL_FULL_REVIEW" });
  if (document.hidden && visibilityPauseToken === null) visibilityPauseToken = telemetry.pauseActive("document-hidden");
  try {
    receipt = await withReviewActivityPaused(telemetry, "initial-receipt-load", () => vietReceiptApi.getReceipt(receiptId));
    renderReceipt();
  } catch (error) {
    main.innerHTML = `<div class="grid min-h-[calc(100dvh-56px)] place-items-center px-4 text-center"><div><p class="text-5xl">404</p><h1 class="mt-4 text-2xl font-bold text-slate-900">Không tìm thấy hóa đơn</h1><p class="mt-2 text-sm text-slate-500">${escapeHtml(getApiErrorMessage(error))}</p><a href="/receipts/" class="mt-5 inline-flex rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white">Quay lại danh sách</a></div></div>`;
  }
}
