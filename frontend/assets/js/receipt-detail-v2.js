import { invoiceApi, ApiError, HEADER_GROUPS, LINE_FIELDS, TAX_FIELDS, VALUE_LABELS, STATUS_LABELS, correctionValue, unresolvedCells, errorText } from "./api-v2.js?v=20260930";
import { escapeHtml, formatDate, getReceiptIdFromLocation, renderNavigation } from "./common.js?v=20260930";
import { icon, invoiceDate } from "./ui.js?v=20260930";
import { createSourceViewer } from "./source-v2.js?v=20260930";

document.body.classList.add("app-v2", "is-review");
renderNavigation();
const main = document.querySelector("#main-content"), receiptId = getReceiptIdFromLocation();
let detail, viewer, timer, pollCount = 0, stale = false, saving = false, verifying = false, exporting = false;
let tab = "info", activeEditor = null, selectedCell = null, inspectorId = null, history = null, historyError = "", historyLoading = false, retrying = false;
const drafts = new Map(), saved = new Set(), errors = new Map();
const key = (section, row, field) => `${section}|${row}|${field}`;
const moneyFields = new Set(["subtotal", "tax_amount", "total_amount", "unit_price", "amount", "taxable_amount"]);
const labelMap = Object.fromEntries([...HEADER_GROUPS.flatMap(([, fields]) => fields), ...LINE_FIELDS, ...TAX_FIELDS]);
const safe = escapeHtml;
const editable = () => detail.status === "NEEDS_REVIEW";
const disabled = () => !editable() || saving || stale || verifying;
function display(value, field) {
  if (value === null || value === undefined || value === "") return "—";
  if (field === "invoice_date") return invoiceDate(value);
  return moneyFields.has(field) && typeof value === "number" ? value.toLocaleString("vi-VN") : String(value);
}
function allCells() {
  return [...Object.entries(detail.fields).map(([field, cell]) => ["header", "", field, cell]),
    ...detail.line_items.flatMap((row) => LINE_FIELDS.map(([field]) => ["line", row.line_id, field, row[field]])),
    ...detail.tax_breakdown.flatMap((row) => TAX_FIELDS.map(([field]) => ["tax", row.tax_id, field, row[field]]))].filter((entry) => entry[3]);
}
const getCell = (id) => allCells().find(([section, row, field]) => key(section, row, field) === id);
const sourceIds = (cell) => Array.isArray(cell?.source_block_ids) ? cell.source_block_ids : [];
function draftValue(id, cell) { return drafts.get(id) || {text: cell.effective_value == null ? "" : String(cell.effective_value), status: cell.effective_status || "UNKNOWN"}; }
function warning(cell) { return cell.effective_needs_review ? `<span class="cell-warning-dot" title="Cần kiểm tra" aria-label="Cần kiểm tra">${icon("warning")}</span>` : ""; }
function cellState(id) { return `<p class="cell-state ${errors.has(id) ? "v2-error" : ""}" role="status">${errors.has(id) ? safe(errors.get(id)) : drafts.has(id) ? (saving && activeEditor === id ? "Đang lưu…" : "Chưa lưu") : saved.has(id) ? "Đã lưu" : ""}</p>`; }
function editorExtra(id, cell) {
  const draft = draftValue(id, cell);
  return `<div class="cell-editor-extra" ${activeEditor === id ? "" : "hidden"}><label class="sr-only" for="status-${safe(id)}">Trạng thái ${safe(labelMap[id.split("|").at(-1)])}</label><select id="status-${safe(id)}" class="v2-input" data-status="${safe(id)}" ${disabled() ? "disabled" : ""}>${Object.entries(VALUE_LABELS).map(([code, label]) => `<option value="${code}" ${draft.status === code ? "selected" : ""}>${label}</option>`).join("")}</select><button type="button" class="v2-button small" data-save="${safe(id)}" ${disabled() ? "disabled" : ""}>Lưu</button><button type="button" class="v2-button secondary small" data-cancel="${safe(id)}" ${saving ? "disabled" : ""}>Hủy</button></div>`;
}
function inputHtml(id, field, cell) {
  const draft = draftValue(id, cell), numeric = moneyFields.has(field) || field === "quantity";
  if (field === "seller_address") return `<textarea class="v2-input" rows="3" data-input="${safe(id)}" aria-label="${safe(labelMap[field])}" ${!editable() ? "readonly" : ""} ${saving || stale || verifying || draft.status !== "PRESENT" ? "disabled" : ""} placeholder="${safe(draft.status === "PRESENT" ? "Chưa có dữ liệu" : VALUE_LABELS[draft.status])}">${safe(draft.text)}</textarea>`;
  return `<input class="v2-input ${numeric ? "number" : ""}" data-input="${safe(id)}" aria-label="${safe(labelMap[field] || field)}" value="${safe(draft.text)}" ${field === "invoice_date" ? 'type="date"' : 'type="text"'} ${numeric ? 'inputmode="decimal"' : ""} ${!editable() ? "readonly" : ""} ${saving || stale || verifying || draft.status !== "PRESENT" ? "disabled" : ""} placeholder="${safe(draft.status === "PRESENT" ? "Chưa có dữ liệu" : VALUE_LABELS[draft.status])}">`;
}
function renderField(field) {
  const cell = detail.fields[field] || {}, id = key("header", "", field);
  return `<div class="review-cell field-row ${cell.effective_needs_review ? "needs-review" : ""} ${selectedCell === id ? "source-selected" : ""}" data-cell="${id}" data-field="${field}"><label class="field-label">${safe(labelMap[field])} ${warning(cell)}</label><div class="field-control">${inputHtml(id, field, cell)}<span class="cell-icons"><button type="button" class="icon-button" data-evidence="${id}" aria-label="Xem vị trí nguồn: ${safe(labelMap[field])}" title="Xem vị trí nguồn" ${sourceIds(cell).length ? "" : "disabled"}>${icon("eye")}</button><button type="button" class="icon-button" data-inspect="${id}" aria-label="Chi tiết: ${safe(labelMap[field])}" title="Chi tiết dữ liệu">${icon("info")}</button></span></div>${editable() ? editorExtra(id, cell) : ""}${cellState(id)}</div>`;
}
function renderTableCell(section, row, field, cell) {
  cell ||= {};
  const id = key(section, row, field), draft = drafts.get(id), editing = activeEditor === id && editable(), numeric = moneyFields.has(field) || field === "quantity";
  const text = draft ? draft.status === "PRESENT" ? display(draft.text, field) : VALUE_LABELS[draft.status] : display(cell.effective_value, field);
  return `<div class="review-cell ${cell.effective_needs_review ? "needs-review" : ""} ${selectedCell === id ? "source-selected" : ""}" data-cell="${safe(id)}">${editing ? `<div class="table-cell-editor">${inputHtml(id, field, cell)}${editorExtra(id, cell)}</div>` : `<button type="button" class="table-cell-value ${numeric ? "number" : ""}" data-edit="${safe(id)}" aria-label="${editable() ? "Sửa" : "Chi tiết"} ${safe(labelMap[field])}: ${safe(text)}"><span>${safe(text)}</span>${warning(cell)}${draft ? '<span class="cell-draft-label">*</span>' : ""}</button>`}${cellState(id)}</div>`;
}
function renderTable(section) {
  const rows = section === "line" ? detail.line_items : detail.tax_breakdown, fields = section === "line" ? LINE_FIELDS : TAX_FIELDS;
  const title = section === "line" ? "Dòng hàng hóa, dịch vụ" : "Nhóm thuế";
  return `<section class="review-group"><h2>${title}</h2>${rows.length ? `<div class="table-scroll"><table class="review-table ${section === "tax" ? "tax-table" : ""}"><thead><tr><th scope="col">${section === "line" ? "STT" : "#"}</th>${fields.map(([field, label]) => `<th scope="col" ${moneyFields.has(field) || field === "quantity" ? 'class="number"' : ""}>${safe(label)}${moneyFields.has(field) && detail.fields.currency?.effective_value ? ` (${safe(detail.fields.currency.effective_value)})` : ""}</th>`).join("")}</tr></thead><tbody>${rows.map((row, index) => `<tr><th scope="row">${index + 1}</th>${fields.map(([field]) => `<td>${renderTableCell(section, section === "line" ? row.line_id : row.tax_id, field, row[field])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : `<p class="v2-muted">Chưa có ${section === "line" ? "dòng hàng" : "nhóm thuế"} được trích xuất từ hóa đơn.</p>`}</section>`;
}
function renderTotals() {
  const labels = {subtotal: "Tổng tiền hàng", tax_amount: "Tiền thuế", total_amount: "Tổng thanh toán"};
  return `<section class="review-group"><h2>Tiền và thuế</h2><div class="totals-grid">${Object.entries(labels).map(([field, label]) => {
    const cell = detail.fields[field] || {}, id = key("header", "", field), editing = activeEditor === id && editable(), draft = drafts.get(id);
    return `<div class="review-cell amount-card ${field === "total_amount" ? "total" : ""} ${cell.effective_needs_review ? "needs-review" : ""}" data-cell="${id}"><div class="amount-top"><span class="field-label">${label} ${warning(cell)}</span><button type="button" class="icon-button" data-inspect="${id}" aria-label="Chi tiết: ${label}">${icon("info")}</button></div>${editing ? `${inputHtml(id, field, cell)}${editorExtra(id, cell)}` : `<button type="button" class="amount-value" data-edit="${id}" aria-label="${editable() ? "Sửa" : "Chi tiết"} ${label}">${safe(display(draft ? (draft.status === "PRESENT" ? draft.text : null) : cell.effective_value, field))}${draft ? " *" : ""}</button><small class="amount-currency">${safe(detail.fields.currency?.effective_value || "")}</small>`}${cellState(id)}</div>`;
  }).join("")}</div><div class="currency-row">${renderField("currency")}</div></section>`;
}
function renderInfo() {
  const info = ["invoice_number", "invoice_date", "invoice_symbol", "invoice_template_number"];
  return `<section class="review-group"><h2>Thông tin chung</h2><div class="field-grid">${info.map(renderField).join("")}</div></section>${HEADER_GROUPS.slice(1, 3).map(([title, fields]) => `<section class="review-group"><h2>${safe(title)}</h2><div class="field-grid ${title === "Người bán" ? "seller-fields" : ""}">${fields.map(([field]) => renderField(field)).join("")}</div></section>`).join("")}${renderTotals()}`;
}
function renderHistory() {
  if (historyLoading) return '<p class="v2-muted" role="status">Đang tải lịch sử…</p>';
  if (historyError) return `<div class="v2-error-panel">${safe(historyError)} <button type="button" id="reload-history" class="text-button">Thử lại</button></div>`;
  if (!history?.length) return '<div class="empty-state"><h2>Chưa có thay đổi</h2><p>Các lần chỉnh sửa và xác nhận hóa đơn sẽ xuất hiện ở đây.</p></div>';
  return `<section class="review-group"><h2>Lịch sử chỉnh sửa</h2><ol class="history-list">${history.map((event) => {
    const location = event.section === "line" ? "Dòng hàng" : event.section === "tax" ? "Nhóm thuế" : "Thông tin";
    const valueText = (entry) => !entry ? "—" : entry.status === "PRESENT" ? display(entry.value, event.field) : VALUE_LABELS[entry.status] || "—";
    return `<li><strong>${event.kind === "VERIFIED" ? "Đã xác nhận hóa đơn" : `${location} · ${safe(labelMap[event.field] || event.field || "Đã cập nhật")}`}</strong>${event.kind === "CORRECTION" ? `<p>${safe(valueText(event.old_value))} → ${safe(valueText(event.new_value))}</p>` : ""}${event.actor ? `<p>${safe(event.actor)}</p>` : ""}<time datetime="${safe(event.created_at)}">${safe(formatDate(event.created_at))}</time></li>`;
  }).join("")}</ol></section>`;
}
async function loadHistory() {
  if (historyLoading) return;
  historyLoading = true; historyError = "";
  if (tab === "history") renderContent();
  try { history = await invoiceApi.history(receiptId); }
  catch (error) { historyError = errorText(error); }
  finally { historyLoading = false; if (tab === "history") renderContent(); }
}
function renderInspector() {
  const existing = main.querySelector(".inspector"); existing?.remove();
  const match = inspectorId && getCell(inspectorId); if (!match) return;
  const [, , field, cell] = match;
  const reasonLabels = {LOW_CONFIDENCE: "Độ tin cậy thấp", UNKNOWN: "Chưa xác định", AMBIGUOUS: "Có nhiều cách hiểu", UNREADABLE: "Không đọc được"};
  main.querySelector(".data-panel").insertAdjacentHTML("beforeend", `<aside class="inspector" role="dialog" aria-label="Chi tiết dữ liệu"><div class="inspector-head"><h3>${safe(labelMap[field])}</h3><button type="button" class="icon-button" id="close-inspector" aria-label="Đóng chi tiết">${icon("close")}</button></div><dl><div><dt>Giá trị hiện tại · ${safe(VALUE_LABELS[cell.effective_status] || "Chưa xác định")}</dt><dd><strong>${safe(display(cell.effective_value, field))}</strong></dd></div><div><dt>Máy đọc · ${safe(VALUE_LABELS[cell.value_status] || "Chưa xác định")}</dt><dd>${safe(display(cell.normalized_value, field))}</dd></div>${cell.has_correction ? `<div><dt>Người sửa · ${safe(VALUE_LABELS[cell.corrected_status] || "")}</dt><dd>${safe(display(cell.corrected_value, field))}</dd></div>` : ""}${cell.raw_text ? `<div><dt>Văn bản gốc</dt><dd>${safe(cell.raw_text)}</dd></div>` : ""}${cell.effective_needs_review ? `<div><dt>Cần kiểm tra</dt><dd>${safe((cell.review_reasons || []).map((reason) => reasonLabels[reason] || reason).join(" · ") || "Đối chiếu giá trị này với tài liệu nguồn.")}</dd></div>` : ""}</dl><div class="button-row"><button type="button" class="v2-button secondary small" data-evidence="${safe(inspectorId)}" ${sourceIds(cell).length ? "" : "disabled"}>${icon("eye")} Xem nguồn</button>${editable() ? `<button type="button" class="v2-button secondary small" data-edit="${safe(inspectorId)}" ${disabled() ? "disabled" : ""}>${icon("edit")} Sửa giá trị</button>` : ""}${editable() && cell.effective_needs_review ? `<button type="button" class="v2-button small" data-confirm="${safe(inspectorId)}" ${disabled() || drafts.has(inspectorId) ? "disabled" : ""}>${icon("check")} Xác nhận giá trị</button>` : ""}</div></aside>`);
}
function tabCounts() {
  const counts = {info: 0, lines: 0, tax: 0};
  allCells().forEach(([section, , , cell]) => { if (cell.effective_needs_review) counts[section === "header" ? "info" : section === "line" ? "lines" : "tax"]++; });
  return counts;
}
function updateTabs() {
  const counts = tabCounts();
  main.querySelectorAll("[data-tab]").forEach((button) => {
    const name = button.dataset.tab;
    button.setAttribute("aria-selected", String(name === tab)); button.tabIndex = name === tab ? 0 : -1;
    const old = button.querySelector(".tab-count"); old?.remove();
    if (counts[name]) button.insertAdjacentHTML("beforeend", `<span class="tab-count" aria-label="${counts[name]} ô cần kiểm tra">${counts[name]}</span>`);
  });
}
function updateHeader() {
  const unresolved = unresolvedCells(detail), blocked = disabled() || unresolved.length > 0 || drafts.size > 0;
  main.querySelector(".review-heading").innerHTML = `<a class="back-link" href="/receipts/">${icon("back")} Quay lại danh sách</a><div class="review-title-row">${icon("file")}<h1 title="${safe(detail.original_filename)}">${safe(detail.original_filename)}</h1><span class="status-pill status-${detail.status.toLowerCase()}">${STATUS_LABELS[detail.status]}</span></div><div class="review-meta"><span>Số hóa đơn: <b>${safe(display(detail.fields.invoice_number?.effective_value, "invoice_number"))}</b></span><span>Ngày lập: <b>${safe(invoiceDate(detail.fields.invoice_date?.effective_value))}</b></span><span>Tổng tiền: <b>${safe(display(detail.fields.total_amount?.effective_value, "total_amount"))} ${safe(detail.fields.currency?.effective_value || "")}</b></span></div>`;
  const actions = main.querySelector(".review-header-actions"), open = actions.querySelector("details")?.open;
  actions.innerHTML = `${editable() && unresolved.length ? `<button type="button" class="review-count" id="show-unresolved">${icon("warning")} ${unresolved.length} mục cần kiểm tra</button>` : ""}<details class="export-menu" ${open ? "open" : ""}><summary class="v2-button secondary" title="${detail.status === "VERIFIED" ? "Xuất dữ liệu" : "Xác nhận hóa đơn trước khi xuất"}">Xuất kết quả ${icon("down")}</summary><div class="export-menu-items">${[["json", "Tải JSON"], ["csv", "Tải CSV (ZIP)"], ["xlsx", "Tải Excel"]].map(([format, label]) => `<button type="button" data-export="${format}" ${detail.status !== "VERIFIED" || exporting ? "disabled" : ""}>${icon("download")} ${label}</button>`).join("")}${detail.status !== "VERIFIED" ? '<p class="v2-muted export-hint">Xác nhận hóa đơn để xuất dữ liệu.</p>' : ""}</div></details>${detail.status === "VERIFIED" ? `<span class="verified-label">${icon("check")} Đã xác nhận</span>` : `<button type="button" id="verify" class="v2-button" ${blocked ? "disabled" : ""}>${verifying ? "Đang xác nhận…" : "Xác nhận hóa đơn"}</button>`}`;
  main.querySelector("#review-help").textContent = detail.status === "VERIFIED" ? "Hóa đơn đã xác nhận. Bạn có thể xuất dữ liệu." : drafts.size ? `${drafts.size} ô có thay đổi chưa lưu. Lưu hoặc hủy trước khi xác nhận.` : unresolved.length ? `${unresolved.length} ô cần đối chiếu. Nhấn biểu tượng chi tiết để kiểm tra hoặc xác nhận giá trị.` : editable() ? "Đã xử lý các ô cần kiểm tra. Bạn có thể xác nhận hóa đơn." : "Hóa đơn đang được xử lý.";
  main.querySelector("#stale-banner").hidden = !stale;
  updateTabs();
}
function renderContent() {
  const body = main.querySelector("#detail-body"); if (!body) return;
  body.setAttribute("aria-labelledby", `tab-${tab}`);
  if (["UPLOADED", "PROCESSING"].includes(detail.status)) {
    body.innerHTML = `<div class="processing-state"><span class="processing-spinner" aria-hidden="true"></span><h2>Đang xử lý hóa đơn…</h2><p>${safe(STATUS_LABELS[detail.status])}</p><p>${safe(({DOCUMENT_READING: "Đang đọc nội dung hóa đơn", KIE: "Đang trích xuất thông tin"})[detail.processing_stage] || "Đang chuẩn bị tài liệu")}</p><button type="button" id="refresh-now" class="v2-button secondary">${icon("refresh")} Kiểm tra ngay</button><p id="poll-message" role="status"></p></div>`;
  } else if (detail.status === "FAILED") {
    const failure = detail.processing_error;
    body.innerHTML = `<div class="processing-state"><span class="v2-error">${icon("warning")}</span><h2>Xử lý thất bại</h2><p>${safe(failure?.message || "Không có chi tiết lỗi xử lý.")}</p>${failure?.retryable ? `<button type="button" id="retry-processing" class="v2-button" ${retrying || stale ? "disabled" : ""}>${icon("refresh")} ${retrying ? "Đang gửi…" : "Thử xử lý lại"}</button>` : '<p>Hãy thử tải lại tệp rõ hơn.</p>'}<p id="retry-message" role="status"></p></div>`;
  } else body.innerHTML = tab === "history" ? renderHistory() : tab === "info" ? renderInfo() : `${tab === "lines" ? renderTable("line") : ""}${renderTable("tax")}${renderTotals()}<p class="review-help">Nhấn vào một ô để ${editable() ? "chỉnh sửa hoặc xem vị trí trong tài liệu" : "xem chi tiết dữ liệu"}.</p>`;
  renderInspector();
}
function renderShell() {
  main.innerHTML = `<div class="review-workspace"><header class="review-header"><div class="review-heading"></div><div class="review-header-actions"></div></header><div id="stale-banner" class="v2-error-panel" hidden><strong>Dữ liệu đã thay đổi.</strong> Các thay đổi chưa lưu được giữ lại. Tải phiên bản mới và kiểm tra lại trước khi lưu. <button type="button" id="reload-detail" class="v2-button secondary small">Tải phiên bản mới</button></div><p id="top-message" class="workspace-message" role="status"></p><div class="review-layout"><section class="source-panel"><div class="source-panel-head"><h2>Tài liệu nguồn</h2><button type="button" class="icon-button" data-toggle-source aria-label="Ẩn tài liệu nguồn" title="Ẩn tài liệu nguồn">${icon("panel")}</button></div><div id="source-viewer"></div></section><section class="data-panel"><nav class="review-tabs" role="tablist" aria-label="Dữ liệu hóa đơn">${[["info", "Thông tin"], ["lines", "Dòng hàng"], ["tax", "Thuế"], ["history", "Lịch sử"]].map(([name, label]) => `<button type="button" class="review-tab" role="tab" id="tab-${name}" data-tab="${name}" aria-controls="detail-body">${label}</button>`).join("")}<button type="button" class="icon-button source-show" data-toggle-source hidden aria-label="Hiện tài liệu nguồn" title="Hiện tài liệu nguồn">${icon("panel")}</button></nav><div id="detail-body" role="tabpanel"></div><footer class="review-footer"><p id="review-help"></p><p id="action-message" role="status" aria-live="polite"></p></footer></section></div></div>`;
  viewer = createSourceViewer(main.querySelector("#source-viewer"), receiptId, (blockId) => {
    const match = allCells().find(([, , , cell]) => sourceIds(cell).includes(blockId));
    if (match) selectField(key(...match.slice(0, 3)));
  });
  viewer.load().catch((error) => { main.querySelector("#top-message").textContent = errorText(error); });
}
function render() {
  if (!main.querySelector("#detail-body")) renderShell();
  updateHeader(); renderContent();
  clearTimeout(timer);
  if (["UPLOADED", "PROCESSING"].includes(detail.status)) schedulePoll();
}
function applyDetail(next) {
  const wasProcessing = ["UPLOADED", "PROCESSING", "FAILED"].includes(detail.status);
  detail = next;
  if (wasProcessing && ["NEEDS_REVIEW", "VERIFIED"].includes(next.status)) viewer?.refreshEvidence().catch(() => {});
}
function schedulePoll() {
  clearTimeout(timer);
  if (pollCount >= 120) { const note = main.querySelector("#poll-message"); if (note) note.textContent = "Đã tạm dừng kiểm tra tự động. Nhấn Kiểm tra ngay để cập nhật."; return; }
  timer = setTimeout(async () => {
    if (document.hidden) { schedulePoll(); return; }
    pollCount++;
    try { applyDetail(await invoiceApi.detail(receiptId)); render(); }
    catch (error) { const note = main.querySelector("#poll-message"); if (note) note.textContent = errorText(error); schedulePoll(); }
  }, Math.min(10000, 2500 + pollCount * 250));
}
function setTab(name) {
  tab = name; activeEditor = null; inspectorId = null; updateHeader(); renderContent();
  main.querySelector("#detail-body").scrollTop = 0;
  if (tab === "history" && history === null) loadHistory();
}
function selectField(id) {
  const match = getCell(id); if (!match) return;
  const section = match[0]; tab = section === "line" ? "lines" : section === "tax" ? "tax" : "info";
  selectedCell = id; activeEditor = null; inspectorId = null; updateHeader(); renderContent();
  const cell = [...main.querySelectorAll("[data-cell]")].find((node) => node.dataset.cell === id);
  cell?.scrollIntoView({block: "nearest", behavior: "smooth"});
}
async function revealSource(id) {
  const match = getCell(id); if (!match) return;
  selectedCell = id;
  const layout = main.querySelector(".review-layout");
  if (layout.classList.contains("source-collapsed")) toggleSource();
  main.querySelectorAll("[data-cell]").forEach((node) => node.classList.toggle("source-selected", node.dataset.cell === id));
  await viewer?.highlight(sourceIds(match[3]));
}
function toggleSource() {
  const collapsed = main.querySelector(".review-layout").classList.toggle("source-collapsed");
  main.querySelector(".source-show").hidden = !collapsed;
  if (!collapsed) viewer?.resize();
}
function activate(id) {
  const match = getCell(id); if (!match) return;
  if (!editable()) { inspectorId = id; renderInspector(); revealSource(id); return; }
  if (disabled()) return;
  activeEditor = id; inspectorId = null; renderContent();
  const input = [...main.querySelectorAll("[data-input]")].find((node) => node.dataset.input === id);
  (input?.disabled ? main.querySelector(`[data-status="${CSS.escape(id)}"]`) : input)?.focus();
  revealSource(id);
}
async function reload() {
  if (saving || verifying) return;
  try { applyDetail(await invoiceApi.detail(receiptId)); stale = false; errors.clear(); saved.clear(); render(); main.querySelector("#top-message").textContent = drafts.size ? "Đã tải phiên bản mới. Các thay đổi chưa lưu vẫn được giữ; hãy đối chiếu trước khi lưu." : "Đã cập nhật hóa đơn."; }
  catch (error) { main.querySelector("#top-message").textContent = errorText(error); }
}
async function save(id, confirm = false) {
  if (disabled()) return;
  const match = getCell(id); if (!match) return;
  const [section, row, field, cell] = match, draft = confirm ? {text: cell.effective_value == null ? "" : String(cell.effective_value), status: cell.effective_status} : draftValue(id, cell);
  let value;
  try { value = correctionValue(field, draft.text, draft.status, detail.fields.currency?.effective_value || "VND"); }
  catch (error) { errors.set(id, errorText(error)); renderContent(); return; }
  drafts.set(id, draft); errors.delete(id); saving = true; render();
  try {
    applyDetail(await invoiceApi.correction(receiptId, section, row, field, value, draft.status, detail.version));
    drafts.delete(id); saved.add(id); activeEditor = null; history = null;
    main.querySelector("#action-message").textContent = `Đã ${confirm ? "xác nhận" : "lưu"} ${labelMap[field]}.`;
  } catch (error) { errors.set(id, errorText(error)); if (error instanceof ApiError && error.status === 409) stale = true; }
  finally { saving = false; render(); }
}
async function retry() {
  if (retrying || stale) return;
  retrying = true; renderContent();
  try { applyDetail(await invoiceApi.retry(receiptId, detail.version)); pollCount = 0; }
  catch (error) { if (error instanceof ApiError && error.status === 409) stale = true; main.querySelector("#top-message").textContent = errorText(error); }
  finally { retrying = false; render(); }
}
async function verify() {
  if (disabled() || drafts.size || unresolvedCells(detail).length) return;
  verifying = true; updateHeader(); renderContent(); main.querySelector("#action-message").textContent = "Đang xác nhận hóa đơn…";
  try { applyDetail(await invoiceApi.verify(receiptId, detail.version)); history = null; main.querySelector("#action-message").textContent = "Hóa đơn đã được xác nhận. Có thể xuất kết quả."; }
  catch (error) { if (error instanceof ApiError && error.status === 409) stale = true; main.querySelector("#action-message").textContent = errorText(error); }
  finally { verifying = false; render(); if (tab === "history") loadHistory(); }
}
async function download(format) {
  if (exporting || detail.status !== "VERIFIED") return;
  exporting = true; updateHeader();
  const message = main.querySelector("#action-message"); message.textContent = `Đang tạo tệp ${format.toUpperCase()}…`;
  try {
    const result = await invoiceApi.export(receiptId, format), url = URL.createObjectURL(result.blob), link = document.createElement("a");
    link.href = url; link.download = result.filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
    message.textContent = `Đã tải ${result.filename}.`;
  } catch (error) { if (error instanceof ApiError && error.status === 409) stale = true; message.textContent = `Không thể xuất tệp: ${errorText(error)}`; }
  finally { exporting = false; updateHeader(); }
}
main.addEventListener("click", (event) => {
  const button = event.target.closest("button"); if (!button || button.disabled) return;
  if (button.dataset.tab) setTab(button.dataset.tab);
  else if (button.dataset.evidence) revealSource(button.dataset.evidence).catch((error) => { main.querySelector("#action-message").textContent = errorText(error); });
  else if (button.dataset.edit) activate(button.dataset.edit);
  else if (button.dataset.inspect) { inspectorId = button.dataset.inspect; renderInspector(); main.querySelector("#close-inspector")?.focus(); }
  else if (button.dataset.save) save(button.dataset.save);
  else if (button.dataset.confirm) save(button.dataset.confirm, true);
  else if (button.dataset.cancel) { drafts.delete(button.dataset.cancel); errors.delete(button.dataset.cancel); activeEditor = null; render(); }
  else if (button.dataset.export) download(button.dataset.export);
  else if (button.hasAttribute("data-toggle-source")) toggleSource();
  else if (button.id === "close-inspector") { inspectorId = null; renderInspector(); }
  else if (button.id === "verify") verify();
  else if (button.id === "retry-processing") retry();
  else if (["refresh-now", "reload-detail"].includes(button.id)) reload();
  else if (button.id === "reload-history") loadHistory();
  else if (button.id === "show-unresolved") { const first = allCells().find(([, , , cell]) => cell.effective_needs_review); if (first) { const id = key(...first.slice(0, 3)); selectField(id); inspectorId = id; renderInspector(); revealSource(id); } }
});
main.addEventListener("input", (event) => {
  const id = event.target.dataset.input; if (!id) return;
  const cell = getCell(id)?.[3]; if (!cell) return;
  drafts.set(id, {text: event.target.value, status: drafts.get(id)?.status || cell.effective_status || "UNKNOWN"}); saved.delete(id); errors.delete(id);
  const state = event.target.closest("[data-cell]")?.querySelector(".cell-state"); if (state) state.textContent = "Chưa lưu";
  updateHeader();
});
main.addEventListener("change", (event) => {
  const id = event.target.dataset.status; if (!id) return;
  const cell = getCell(id)?.[3]; if (!cell) return;
  const input = [...main.querySelectorAll("[data-input]")].find((node) => node.dataset.input === id);
  drafts.set(id, {text: input?.value || draftValue(id, cell).text, status: event.target.value}); saved.delete(id); errors.delete(id);
  if (input) input.disabled = event.target.value !== "PRESENT";
  const state = event.target.closest("[data-cell]")?.querySelector(".cell-state"); if (state) state.textContent = "Chưa lưu";
  updateHeader();
});
main.addEventListener("focusin", (event) => {
  const id = event.target.dataset.input;
  if (!id || !editable() || disabled()) return;
  activeEditor = id;
  main.querySelectorAll(".cell-editor-extra").forEach((extra) => { extra.hidden = extra.querySelector("[data-status]")?.dataset.status !== id; });
  revealSource(id).catch(() => {});
});
main.addEventListener("keydown", (event) => {
  const id = event.target.closest("[data-cell]")?.dataset.cell;
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && id) { event.preventDefault(); save(id); }
  if (event.key === "Escape") {
    if (inspectorId) { inspectorId = null; renderInspector(); }
    else if (id && !saving) { drafts.delete(id); errors.delete(id); activeEditor = null; render(); }
  }
  const button = event.target.closest("[data-tab]");
  if (button && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    event.preventDefault(); const tabs = [...main.querySelectorAll("[data-tab]")], index = tabs.indexOf(button);
    const next = tabs[event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    setTab(next.dataset.tab); next.focus();
  }
});
window.addEventListener("pagehide", () => { clearTimeout(timer); viewer?.destroy(); }, {once: true});
window.addEventListener("beforeunload", (event) => { if (drafts.size) { event.preventDefault(); event.returnValue = ""; } });
document.addEventListener("visibilitychange", () => { if (document.hidden) clearTimeout(timer); else if (detail && ["UPLOADED", "PROCESSING"].includes(detail.status)) schedulePoll(); });
if (!receiptId) main.innerHTML = '<div class="v2-container"><div class="v2-error-panel">Không tìm thấy mã hóa đơn. <a href="/receipts/">Về danh sách</a></div></div>';
else {
  main.innerHTML = '<div class="v2-container"><p role="status">Đang tải hóa đơn…</p></div>';
  try { detail = await invoiceApi.detail(receiptId); render(); }
  catch (error) { main.innerHTML = `<div class="v2-container"><div class="v2-error-panel"><h1>Không mở được hóa đơn</h1><p>${safe(errorText(error))}</p><button type="button" id="retry-initial" class="v2-button">Thử lại</button></div></div>`; main.querySelector("#retry-initial").addEventListener("click", () => location.reload()); }
}
