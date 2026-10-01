import { invoiceApi, validateFile, errorText } from "./api-v2.js?v=20260930";
import { escapeHtml, renderNavigation, receiptUrl } from "./common.js?v=20260930";
import { icon } from "./ui.js?v=20260930";

document.body.classList.add("app-v2");
renderNavigation();
const main = document.querySelector("#main-content");
let selected = null, previewUrl = null, busy = false, selectionVersion = 0;
let previewPdf = null, previewPdfTask = null, previewPage = 1, previewGeneration = 0, previewRenderTask = null;
main.innerHTML = `<div class="v2-container upload-page"><header class="v2-heading"><h1>Tải hóa đơn</h1><p>Kéo thả tệp vào đây hoặc chọn tệp để bắt đầu xử lý. Hỗ trợ JPEG, PNG, PDF (tối đa 10 MiB).</p></header>
<section class="v2-card upload-card"><div id="dropzone" class="dropzone" tabindex="0" role="button" aria-label="Chọn hoặc thả tệp hóa đơn"><div class="drop-icon">${icon("upload")}</div><h2>Kéo thả tệp vào đây</h2><p>hoặc</p><button type="button" id="pick-file" class="v2-button">Chọn tệp</button><input id="file-input" type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" hidden><p class="file-hint">Hỗ trợ: JPEG, PNG, PDF (tối đa 10 MiB)</p></div>
<div id="selection" class="upload-selection" hidden></div><label class="v2-label" for="source-group">Nguồn hóa đơn</label><select id="source-group" class="v2-input"><option value="">Tự nhận theo tệp</option><option value="PAPER_DIGITIZED">Hóa đơn giấy đã số hóa</option><option value="IMAGE">Ảnh có sẵn</option><option value="PDF">PDF</option></select>
<p id="upload-message" role="status" aria-live="polite"></p><button id="upload-submit" type="button" class="v2-button" disabled>${icon("upload")} Tải lên và xử lý</button></section>
<dialog id="file-preview" class="preview-dialog" aria-label="Xem trước hóa đơn"><div class="preview-head"><strong></strong><button type="button" class="icon-button" data-close-preview aria-label="Đóng xem trước">${icon("close")}</button></div><div class="preview-body"></div></dialog></div>`;
const input = main.querySelector("#file-input"), zone = main.querySelector("#dropzone"), selection = main.querySelector("#selection"), message = main.querySelector("#upload-message"), submit = main.querySelector("#upload-submit"), dialog = main.querySelector("#file-preview");
async function choose(file) {
  if (busy) return;
  dialog.close();
  clearPreview();
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  const version = ++selectionVersion;
  selected = file;
  const error = file ? validateFile(file) : null;
  submit.disabled = !file || Boolean(error);
  message.textContent = error || "";
  message.className = error ? "v2-error" : "v2-muted";
  selection.hidden = !file;
  if (!file) { selection.replaceChildren(); input.value = ""; return; }
  if (!error) previewUrl = URL.createObjectURL(file);
  const size = file.size < 1024 * 1024 ? `${Math.ceil(file.size / 1024)} KB` : `${(file.size / 1024 / 1024).toLocaleString("vi-VN", {maximumFractionDigits: 2})} MiB`;
  selection.innerHTML = `<div class="file-thumb">${previewUrl && file.type.startsWith("image/") ? `<img src="${previewUrl}" alt="Xem trước ảnh đã chọn">` : icon("file")}</div><div class="file-summary"><strong>${escapeHtml(file.name)}</strong><p>${size} · ${file.type === "application/pdf" ? "PDF" : "Ảnh"}</p><div class="file-actions"><button type="button" class="text-button" data-preview ${error ? "disabled" : ""}>${icon("eye")} Xem trước</button><button type="button" class="text-button" data-replace>${icon("refresh")} Đổi tệp</button><button type="button" class="text-button danger" data-remove>${icon("trash")} Bỏ tệp</button></div></div><button type="button" class="icon-button remove-file" data-remove aria-label="Bỏ tệp đã chọn">${icon("close")}</button>`;
  if (!error && file.type === "application/pdf") {
    let loadingTask;
    try {
      const pdfjs = await import("/assets/vendor/pdf.mjs");
      pdfjs.GlobalWorkerOptions.workerSrc = "/assets/vendor/pdf.worker.mjs";
      loadingTask = pdfjs.getDocument({url: previewUrl});
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1), base = page.getViewport({scale: 1}), viewport = page.getViewport({scale: 74 / base.height});
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
      await page.render({canvas, canvasContext: canvas.getContext("2d"), viewport}).promise;
      if (version === selectionVersion) selection.querySelector(".file-thumb").replaceChildren(canvas);
    } catch { /* The selected PDF can still be uploaded if its thumbnail cannot be rendered. */ }
    finally { await loadingTask?.destroy(); }
  }
}
function setBusy(value) {
  busy = value;
  main.querySelectorAll("#pick-file, #source-group, #selection button").forEach((button) => { button.disabled = value; });
  zone.setAttribute("aria-disabled", String(value));
  submit.disabled = value || !selected || Boolean(validateFile(selected));
  submit.innerHTML = value ? "Đang tải hóa đơn…" : `${icon("upload")} Tải lên và xử lý`;
}
main.querySelector("#pick-file").addEventListener("click", () => { if (!busy) input.click(); });
zone.addEventListener("click", (event) => { if (!busy && !event.target.closest("button")) input.click(); });
zone.addEventListener("keydown", (event) => { if (event.target === zone && !busy && ["Enter", " "].includes(event.key)) { event.preventDefault(); input.click(); } });
input.addEventListener("change", () => choose(input.files?.[0] || null));
for (const name of ["dragenter", "dragover"]) zone.addEventListener(name, (event) => { event.preventDefault(); if (!busy) zone.classList.add("dragging"); });
for (const name of ["dragleave", "drop"]) zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.remove("dragging"); });
zone.addEventListener("drop", (event) => { if (!busy) choose(event.dataTransfer?.files?.[0] || null); });
function clearPreview() {
  previewGeneration++;
  previewRenderTask?.cancel(); previewRenderTask = null;
  previewPdfTask?.destroy().catch(() => {}); previewPdfTask = null; previewPdf = null;
  dialog.querySelector(".preview-body").replaceChildren();
}
async function renderPreviewPage() {
  const generation = ++previewGeneration;
  previewRenderTask?.cancel(); previewRenderTask = null;
  const total = previewPdf.numPages;
  dialog.querySelector("[data-preview-page]").textContent = `Trang ${previewPage} / ${total}`;
  dialog.querySelector("[data-preview-prev]").disabled = previewPage === 1;
  dialog.querySelector("[data-preview-next]").disabled = previewPage === total;
  const page = await previewPdf.getPage(previewPage);
  if (generation !== previewGeneration || !dialog.open) return;
  const surface = dialog.querySelector(".preview-document"), base = page.getViewport({scale: 1});
  const viewport = page.getViewport({scale: Math.max(160, surface.clientWidth - 28) / base.width});
  const canvas = document.createElement("canvas"), ratio = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.ceil(viewport.width * ratio); canvas.height = Math.ceil(viewport.height * ratio);
  canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`;
  surface.replaceChildren(canvas);
  const task = page.render({canvas, canvasContext: canvas.getContext("2d"), viewport, transform: [ratio, 0, 0, ratio, 0, 0]});
  previewRenderTask = task;
  try { await task.promise; } catch (error) { if (error.name !== "RenderingCancelledException") throw error; }
}
async function openPreview() {
  if (!previewUrl || dialog.open) return;
  dialog.querySelector("strong").textContent = selected.name;
  const body = dialog.querySelector(".preview-body");
  if (selected.type !== "application/pdf") { body.innerHTML = `<img src="${previewUrl}" alt="Hóa đơn đã chọn">`; dialog.showModal(); return; }
  const generation = ++previewGeneration;
  body.innerHTML = '<div class="preview-toolbar"><button type="button" class="v2-button secondary small" data-preview-prev aria-label="Trang PDF trước" disabled>←</button><span data-preview-page>Đang tải PDF…</span><button type="button" class="v2-button secondary small" data-preview-next aria-label="Trang PDF sau" disabled>→</button></div><div class="preview-document"><p role="status">Đang mở tài liệu…</p></div>';
  dialog.showModal();
  try {
    const pdfjs = await import("/assets/vendor/pdf.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "/assets/vendor/pdf.worker.mjs";
    const task = pdfjs.getDocument({url: previewUrl}); previewPdfTask = task;
    const pdf = await task.promise;
    if (generation !== previewGeneration || !dialog.open) { await task.destroy(); return; }
    previewPdf = pdf; previewPage = 1; await renderPreviewPage();
  } catch (error) { if (generation === previewGeneration && dialog.open) body.innerHTML = `<p class="v2-error">Không mở được PDF: ${escapeHtml(errorText(error))}</p>`; }
}
dialog.addEventListener("close", clearPreview);
main.addEventListener("click", async (event) => {
  if (event.target.closest("[data-close-preview]")) dialog.close();
  if (busy) return;
  if (event.target.closest("[data-remove]")) choose(null);
  if (event.target.closest("[data-replace]")) input.click();
  if (event.target.closest("[data-preview]")) await openPreview();
  const previous = event.target.closest("[data-preview-prev]"), next = event.target.closest("[data-preview-next]");
  if (previewPdf && ((previous && !previous.disabled) || (next && !next.disabled))) {
    previewPage += previous ? -1 : 1;
    try { await renderPreviewPage(); } catch (error) { const surface = dialog.querySelector(".preview-document"); if (surface && dialog.open) surface.innerHTML = `<p class="v2-error">${escapeHtml(errorText(error))}</p>`; }
  }
});
submit.addEventListener("click", async () => {
  if (busy || !selected || validateFile(selected)) return;
  setBusy(true); message.textContent = "Đang tải tệp, vui lòng giữ trang này mở."; message.className = "v2-muted";
  try {
    const detail = await invoiceApi.upload(selected, main.querySelector("#source-group").value || null);
    window.location.assign(receiptUrl(detail.receipt_id));
  } catch (error) { message.textContent = errorText(error); message.className = "v2-error"; setBusy(false); }
});
window.addEventListener("pagehide", () => { clearPreview(); if (previewUrl) URL.revokeObjectURL(previewUrl); }, {once: true});
