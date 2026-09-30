import { APP_CONFIG } from "./config.js";
import { getApiErrorMessage, vietReceiptApi } from "./api.js";
import { announce, escapeHtml, receiptUrl, renderNavigation } from "./common.js";

renderNavigation();

const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
const maxFileSize = 10 * 1024 * 1024;
let files = APP_CONFIG.dataMode === "mock" ? [
  { id: "sample-1", name: "hoa-don-an-nam-001.jpg", size: "1,8 MB", progress: 100, state: "UPLOAD_SUCCESS" },
  { id: "sample-2", name: "cafe-moc-aug11.png", size: "2,4 MB", progress: 68, state: "UPLOADING" },
  { id: "sample-3", name: "nha-thuoc-minh-tam.jpg", size: "824 KB", progress: 0, state: "SELECTED" },
] : [];

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

document.querySelector("#main-content").innerHTML = `<div class="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
  <header class="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p class="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-teal-700">Bước 1 · Thu thập dữ liệu</p><h1 class="text-3xl font-bold tracking-[-0.035em] text-slate-950 sm:text-4xl">Tải hóa đơn lên</h1><p class="mt-3 max-w-2xl text-sm leading-6 text-slate-500">Sau khi Backend lưu ảnh và metadata, receipt ở trạng thái UPLOADED và được tự động schedule. Frontend không gọi /process.</p></div><div class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"><span id="upload-count" class="font-bold text-slate-950"></span><span class="ml-1.5 text-slate-500">tệp đã tải xong</span></div></header>
  <section class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40"><div class="p-4 sm:p-6"><div id="dropzone" role="button" tabindex="0" aria-label="Chọn hoặc kéo thả hóa đơn để tải lên" class="group grid min-h-72 place-items-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/70 px-6 py-12 text-center outline-none transition hover:border-teal-500 hover:bg-teal-50/50 focus-visible:border-teal-600 focus-visible:ring-4 focus-visible:ring-teal-600/10"><input id="file-input" type="file" accept="image/jpeg,image/png,image/webp" multiple class="sr-only"><div><div class="mx-auto mb-5 grid size-16 place-items-center rounded-2xl border border-teal-100 bg-white text-3xl text-teal-700 shadow-sm transition group-hover:-translate-y-1">↑</div><h2 id="dropzone-title" class="text-lg font-bold text-slate-900">Kéo thả hóa đơn vào đây</h2><p class="mt-2 text-sm text-slate-500">hoặc <span class="font-bold text-teal-700">chọn tệp từ thiết bị</span></p><p class="mt-4 text-xs text-slate-400">JPEG, PNG hoặc WebP · Tối đa 10 MiB mỗi tệp</p></div></div><p id="validation-message" role="alert" hidden class="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"></p></div>
    <div class="border-t border-slate-100 bg-slate-50/60 px-4 py-5 sm:px-6"><div class="mb-4 flex items-center justify-between gap-4"><h2 class="text-sm font-bold text-slate-900">Danh sách tải lên</h2><button id="add-files" type="button" class="text-xs font-bold text-teal-700 hover:text-teal-900">+ Thêm tệp</button></div><div id="upload-list" class="space-y-2"></div></div></section>
  <div class="mt-6 flex flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center"><p class="text-xs leading-5 text-slate-400">${APP_CONFIG.dataMode === "api" ? "Đang dùng Backend thật qua multipart field “file”." : "Đang dùng mock HTTP adapter; luồng và navigation giữ giống API thật."}</p><a href="/receipts/" class="inline-flex h-11 items-center justify-center rounded-xl bg-teal-800 px-5 text-sm font-bold text-white shadow-sm transition hover:bg-teal-900">Xem danh sách hóa đơn <span class="ml-2">→</span></a></div>
</div>`;

const input = document.querySelector("#file-input");
const dropzone = document.querySelector("#dropzone");

function stateLabel(item) {
  if (item.state === "UPLOAD_SUCCESS") return ["Hoàn tất", "text-emerald-700"];
  if (item.state === "UPLOADING") return [`${item.progress}%`, "text-teal-700"];
  if (item.state === "UPLOAD_ERROR") return ["Lỗi", "text-red-700"];
  return ["Đã chọn", "text-slate-500"];
}

function renderFiles() {
  const completed = files.filter((file) => file.state === "UPLOAD_SUCCESS").length;
  document.querySelector("#upload-count").textContent = `${completed}/${files.length}`;
  const host = document.querySelector("#upload-list");
  if (!files.length) {
    host.innerHTML = `<div class="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-400">IDLE · Chưa có tệp nào.</div>`;
    return;
  }
  host.innerHTML = files.map((item) => {
    const [label, tone] = stateLabel(item);
    const extension = item.name.split(".").pop()?.slice(0, 3) ?? "Tệp";
    return `<article class="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm"><div class="grid size-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-black uppercase text-slate-500">${escapeHtml(extension)}</div><div class="min-w-0 flex-1"><div class="flex items-center justify-between gap-3"><p class="truncate text-sm font-bold text-slate-800">${escapeHtml(item.name)}</p><span class="shrink-0 text-xs font-bold ${tone}">${label}</span></div><div class="mt-2 flex items-center gap-3"><div class="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full transition-all duration-500 ${item.state === "UPLOAD_SUCCESS" ? "bg-emerald-500" : item.state === "UPLOAD_ERROR" ? "bg-red-500" : "bg-teal-600"}" style="width:${item.progress}%"></div></div><span class="w-14 shrink-0 text-right text-[11px] text-slate-400">${escapeHtml(item.size)}</span></div>${item.error ? `<p class="mt-2 text-xs font-semibold text-red-700">${escapeHtml(item.error)}</p>` : ""}</div><button type="button" data-remove="${escapeHtml(item.id)}" class="grid size-8 shrink-0 place-items-center rounded-lg text-lg text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Xóa ${escapeHtml(item.name)}">×</button></article>`;
  }).join("");
}

async function uploadItem(item, selectedCount) {
  item.state = "UPLOADING";
  item.progress = 20;
  renderFiles();
  try {
    const created = await vietReceiptApi.uploadReceipt(item.file);
    item.progress = 100;
    item.state = "UPLOAD_SUCCESS";
    item.receiptId = created.receipt_id;
    renderFiles();
    announce(`Đã tải ${item.name}. Đang mở trạng thái xử lý.`);
    if (selectedCount === 1) globalThis.setTimeout(() => window.location.assign(receiptUrl(created.receipt_id)), 350);
  } catch (error) {
    item.progress = 100;
    item.state = "UPLOAD_ERROR";
    item.error = getApiErrorMessage(error);
    renderFiles();
    announce(item.error, "error");
  }
}

function showValidation(message) {
  const validation = document.querySelector("#validation-message");
  validation.hidden = !message;
  validation.textContent = message ?? "";
}

function addFiles(selectedFiles) {
  const selected = Array.from(selectedFiles);
  const invalidType = selected.filter((file) => !allowedTypes.includes(file.type)).length;
  const tooLarge = selected.filter((file) => allowedTypes.includes(file.type) && file.size > maxFileSize).length;
  const valid = selected.filter((file) => allowedTypes.includes(file.type) && file.size <= maxFileSize);
  const errors = [];
  if (invalidType) errors.push(`${invalidType} tệp sai định dạng (tương ứng lỗi 415).`);
  if (tooLarge) errors.push(`${tooLarge} tệp vượt 10 MiB (tương ứng lỗi 413).`);
  showValidation(errors.join(" "));
  const additions = valid.map((file, index) => ({ id: `${file.name}-${file.lastModified}-${index}`, name: file.name, size: formatBytes(file.size), progress: 0, state: "SELECTED", file, error: null }));
  files = [...additions, ...files];
  renderFiles();
  additions.forEach((item) => uploadItem(item, additions.length));
}

dropzone.addEventListener("click", () => input.click());
dropzone.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); input.click(); } });
dropzone.addEventListener("dragenter", (event) => { event.preventDefault(); dropzone.classList.add("border-teal-600", "bg-teal-50"); document.querySelector("#dropzone-title").textContent = "Thả tệp tại đây"; });
dropzone.addEventListener("dragover", (event) => event.preventDefault());
dropzone.addEventListener("dragleave", () => { dropzone.classList.remove("border-teal-600", "bg-teal-50"); document.querySelector("#dropzone-title").textContent = "Kéo thả hóa đơn vào đây"; });
dropzone.addEventListener("drop", (event) => { event.preventDefault(); dropzone.classList.remove("border-teal-600", "bg-teal-50"); document.querySelector("#dropzone-title").textContent = "Kéo thả hóa đơn vào đây"; addFiles(event.dataTransfer.files); });
input.addEventListener("change", () => { if (input.files?.length) addFiles(input.files); input.value = ""; });
document.querySelector("#add-files").addEventListener("click", () => input.click());
document.querySelector("#upload-list").addEventListener("click", (event) => { const button = event.target.closest("[data-remove]"); if (!button) return; files = files.filter((file) => file.id !== button.dataset.remove); renderFiles(); });

globalThis.setInterval(() => {
  let changed = false;
  files.forEach((item) => { if (item.state === "UPLOADING" && !item.file) { item.progress = Math.min(100, item.progress + 8); if (item.progress === 100) item.state = "UPLOAD_SUCCESS"; changed = true; } });
  if (changed) renderFiles();
}, 650);

renderFiles();
