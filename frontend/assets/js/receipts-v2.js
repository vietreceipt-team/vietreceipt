import { invoiceApi, errorText, STATUS_LABELS } from "./api-v2.js?v=20260930";
import { escapeHtml, receiptUrl, renderNavigation } from "./common.js?v=20260930";
import { icon, invoiceDate, searchText } from "./ui.js?v=20260930";

document.body.classList.add("app-v2");
renderNavigation();
const main = document.querySelector("#main-content");
const pageSize = 10;
let invoices = [], currentPage = 1, loading = false, searchTimer;
main.innerHTML = `<div class="v2-container"><header class="v2-heading v2-heading-row"><div><h1>Danh sách hóa đơn</h1><p>Quản lý và xem chi tiết các hóa đơn đã tải lên.</p></div><a class="v2-button" href="/upload/">${icon("upload")} Tải hóa đơn</a></header>
<div class="list-filters"><div class="filter-field filter-search"><label class="sr-only" for="invoice-search">Tìm hóa đơn</label><div class="search-field">${icon("search")}<input id="invoice-search" class="v2-input" type="search" placeholder="Tìm theo tên file, số hóa đơn, người bán…"></div></div><div class="filter-field"><label for="filter-status">Trạng thái</label><select id="filter-status" class="v2-input"><option value="">Tất cả</option>${Object.entries(STATUS_LABELS).map(([code, label]) => `<option value="${code}">${label}</option>`).join("")}</select></div><div class="filter-field"><label for="filter-from">Từ ngày</label><input id="filter-from" class="v2-input" type="date"></div><div class="filter-field"><label for="filter-to">Đến ngày</label><input id="filter-to" class="v2-input" type="date"></div><button type="button" id="reload-list" class="icon-button" aria-label="Tải lại danh sách" title="Tải lại danh sách">${icon("refresh")}</button></div>
<div id="list-message" role="status" aria-live="polite"></div><div id="invoice-list"></div><div id="list-footer" class="list-footer"></div></div>`;
const list = main.querySelector("#invoice-list"), message = main.querySelector("#list-message"), footer = main.querySelector("#list-footer");
function filteredInvoices() {
  const query = searchText(main.querySelector("#invoice-search").value.trim()), status = main.querySelector("#filter-status").value, from = main.querySelector("#filter-from").value, to = main.querySelector("#filter-to").value;
  return invoices.filter((item) => (!status || item.status === status) && (!from || item.invoice_date >= from) && (!to || (item.invoice_date && item.invoice_date <= to)) && (!query || searchText(`${item.original_filename} ${item.invoice_number || ""} ${item.seller_name || ""}`).includes(query)));
}
function render() {
  const items = filteredInvoices(), pages = Math.max(1, Math.ceil(items.length / pageSize));
  currentPage = Math.min(currentPage, pages);
  const start = (currentPage - 1) * pageSize, visible = items.slice(start, start + pageSize);
  if (!visible.length) {
    list.innerHTML = invoices.length ? `<div class="empty-state">${icon("search")}<h2>Không tìm thấy hóa đơn phù hợp</h2><p>Thử tên tệp khác hoặc xóa các bộ lọc.</p><button type="button" id="clear-filters" class="v2-button secondary">Xóa bộ lọc</button></div>` : `<div class="empty-state">${icon("receipt")}<h2>${loading ? "Đang tải hóa đơn…" : "Bạn chưa tải hóa đơn nào"}</h2>${loading ? "" : '<p>Bắt đầu bằng một ảnh hoặc tệp PDF.</p><a class="v2-button" href="/upload/">Tải hóa đơn đầu tiên</a>'}</div>`;
    footer.replaceChildren(); return;
  }
  list.innerHTML = `<div class="list-table-wrap"><table class="invoice-table"><thead><tr><th>#</th><th>Tên file</th><th>Số hóa đơn</th><th>Người bán</th><th>Ngày lập</th><th class="number">Tổng tiền</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${visible.map((item, index) => `<tr><td>${start + index + 1}</td><td class="file-name"><a href="${receiptUrl(item.receipt_id)}" title="${escapeHtml(item.original_filename)}">${escapeHtml(item.original_filename)}</a></td><td class="no-wrap">${escapeHtml(item.invoice_number || "—")}</td><td class="seller-column" title="${escapeHtml(item.seller_name || "")}">${escapeHtml(item.seller_name || "—")}</td><td class="no-wrap">${escapeHtml(invoiceDate(item.invoice_date))}</td><td class="number">${item.total_amount == null ? "—" : `${Number(item.total_amount).toLocaleString("vi-VN")} <small>${escapeHtml(item.currency || "")}</small>`}</td><td><span class="status-pill status-${item.status.toLowerCase()}">${escapeHtml(STATUS_LABELS[item.status] || item.status)}</span></td><td><a class="v2-button secondary small" href="${receiptUrl(item.receipt_id)}">Xem chi tiết</a></td></tr>`).join("")}</tbody></table></div>`;
  const first = Math.max(1, Math.min(currentPage - 2, pages - 4)), last = Math.min(pages, first + 4);
  footer.innerHTML = `<span>Hiển thị ${start + 1} – ${start + visible.length} trong ${items.length} hóa đơn</span><nav class="pagination" aria-label="Phân trang hóa đơn"><button type="button" id="previous-page" class="page-button" aria-label="Trang trước" ${currentPage === 1 ? "disabled" : ""}>${icon("back")}</button>${Array.from({length: last - first + 1}, (_, i) => first + i).map((page) => `<button type="button" class="page-button ${page === currentPage ? "active" : ""}" data-page="${page}" ${page === currentPage ? 'aria-current="page"' : ""}>${page}</button>`).join("")}<button type="button" id="next-page" class="page-button" aria-label="Trang sau" ${currentPage === pages ? "disabled" : ""}>${icon("chevron")}</button></nav>`;
}
async function load() {
  if (loading) return;
  loading = true; message.textContent = "Đang tải danh sách…"; main.querySelector("#reload-list").disabled = true;
  try {
    const loaded = [], seen = new Set();
    for (let offset = 0; ; offset += 100) {
      const page = await invoiceApi.list(100, offset);
      const fresh = page.items.filter((item) => !seen.has(item.receipt_id));
      fresh.forEach((item) => { seen.add(item.receipt_id); loaded.push(item); });
      if (page.items.length < 100 || !fresh.length) break;
    }
    invoices = loaded; render();
    // Older backends omit these fields; retain bounded fallback for compatibility.
    let index = 0, failures = 0;
    await Promise.all(Array.from({length: Math.min(4, invoices.length)}, async () => {
      while (index < invoices.length) {
        const item = invoices[index++];
        if (Object.hasOwn(item, "invoice_number") && Object.hasOwn(item, "currency")) continue;
        try { const detail = await invoiceApi.detail(item.receipt_id); item.invoice_number = detail.fields.invoice_number?.effective_value; item.currency = detail.fields.currency?.effective_value; }
        catch { failures++; }
      }
    }));
    message.textContent = failures ? "Một số chi tiết chưa tải được. Bạn vẫn có thể mở hóa đơn hoặc tải lại danh sách." : "";
  } catch (error) {
    message.innerHTML = `<span class="v2-error">${escapeHtml(errorText(error))}</span> <button type="button" id="retry-list" class="text-button">Thử lại</button>`;
  } finally { loading = false; main.querySelector("#reload-list").disabled = false; render(); }
}
function resetPage() { currentPage = 1; render(); }
main.querySelector("#invoice-search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(resetPage, 150); });
for (const id of ["filter-status", "filter-from", "filter-to"]) main.querySelector(`#${id}`).addEventListener("change", resetPage);
main.addEventListener("click", (event) => {
  const button = event.target.closest("button"); if (!button) return;
  if (["reload-list", "retry-list"].includes(button.id)) load();
  else if (button.id === "clear-filters") { main.querySelectorAll(".list-filters input, .list-filters select").forEach((input) => { input.value = ""; }); resetPage(); }
  else if (button.id === "previous-page") { currentPage--; render(); }
  else if (button.id === "next-page") { currentPage++; render(); }
  else if (button.dataset.page) { currentPage = Number(button.dataset.page); render(); }
});
load();
