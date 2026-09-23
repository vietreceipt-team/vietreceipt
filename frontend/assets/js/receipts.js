import { getApiErrorMessage, vietReceiptApi } from "./api.js";
import { announce, escapeHtml, formatDate, formatVnd, receiptUrl, renderNavigation, renderStatusBadge } from "./common.js";

renderNavigation();

const pageSize = 5;
const inProgressStatuses = ["UPLOADED", "PROCESSING"];
const tabLabels = { ALL: "Tất cả", NEEDS_REVIEW: "Cần kiểm tra", IN_PROGRESS: "Đang xử lý", VERIFIED: "Đã xác minh", FAILED: "Thất bại" };
const state = { receipts: [], query: "", activeTab: "ALL", dateFilter: "ALL", merchant: "ALL", sortOrder: "NEWEST", reviewOnly: false, showAdvanced: false, page: 1, loading: true };

function matchesTab(receipt, tab) {
  if (tab === "ALL") return true;
  if (tab === "IN_PROGRESS") return inProgressStatuses.includes(receipt.status);
  return receipt.status === tab;
}

function getCounts() {
  return {
    ALL: state.receipts.length,
    NEEDS_REVIEW: state.receipts.filter((receipt) => receipt.status === "NEEDS_REVIEW").length,
    IN_PROGRESS: state.receipts.filter((receipt) => inProgressStatuses.includes(receipt.status)).length,
    VERIFIED: state.receipts.filter((receipt) => receipt.status === "VERIFIED").length,
    FAILED: state.receipts.filter((receipt) => receipt.status === "FAILED").length,
  };
}

function filteredReceipts() {
  const normalized = state.query.trim().toLocaleLowerCase("vi");
  const latestUploadTime = Math.max(...state.receipts.map((receipt) => new Date(receipt.created_at).getTime()), 0);
  const dateWindow = state.dateFilter === "LAST_24_HOURS" ? 86400000 : state.dateFilter === "LAST_7_DAYS" ? 604800000 : null;
  return state.receipts.filter((receipt) => {
    const matchesQuery = !normalized || receipt.original_filename.toLocaleLowerCase("vi").includes(normalized) || (receipt.merchant_name?.toLocaleLowerCase("vi").includes(normalized) ?? false);
    const matchesDate = dateWindow === null || latestUploadTime - new Date(receipt.created_at).getTime() <= dateWindow;
    return matchesTab(receipt, state.activeTab) && matchesQuery && matchesDate && (state.merchant === "ALL" || receipt.merchant_name === state.merchant) && (!state.reviewOnly || receipt.status === "NEEDS_REVIEW");
  }).sort((left, right) => {
    if (state.sortOrder === "NEWEST") return new Date(right.created_at) - new Date(left.created_at);
    if (state.sortOrder === "OLDEST") return new Date(left.created_at) - new Date(right.created_at);
    const leftTotal = left.total_amount ?? -1;
    const rightTotal = right.total_amount ?? -1;
    return state.sortOrder === "TOTAL_HIGH" ? rightTotal - leftTotal : leftTotal - rightTotal;
  });
}

function reviewState(receipt) {
  if (receipt.status === "NEEDS_REVIEW") return `<div class="min-w-56"><p class="font-bold text-teal-800">Có trường cần người dùng kiểm tra</p><p class="mt-0.5 text-sm text-slate-500">Mở chi tiết để xem trạng thái hiệu lực và lý do.</p></div>`;
  if (receipt.status === "VERIFIED") return `<div class="min-w-56"><p class="font-bold text-slate-800">Đã xác minh tất cả các trường</p><p class="mt-0.5 text-xs font-semibold text-emerald-700">Quyết định bởi người kiểm duyệt</p></div>`;
  if (receipt.status === "PROCESSING") return `<div class="flex items-center gap-2 text-sm font-medium text-slate-600"><span class="icon size-4 animate-spin text-sky-600" aria-hidden="true">◌</span>Đang xử lý OCR/KIE... <span class="text-xs font-normal text-slate-400">Chưa có kết quả cuối</span></div>`;
  if (receipt.status === "UPLOADED") return `<p class="text-sm font-medium text-slate-600">Đã nhận tệp · Đang chờ worker bắt đầu</p>`;
  return `<div class="min-w-56"><p class="font-bold text-red-700">Không thể xử lý hóa đơn</p><p class="mt-0.5 text-sm text-slate-500">Mở chi tiết để xem lỗi an toàn do Backend trả về.</p></div>`;
}

function thumbnail(receipt) {
  if (receipt.image_url) return `<img src="${escapeHtml(receipt.image_url)}" alt="Ảnh thu nhỏ ${escapeHtml(receipt.original_filename)}" class="h-14 w-12 shrink-0 rounded-lg border border-slate-200 bg-white object-cover shadow-sm" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><div hidden class="relative grid h-14 w-12 shrink-0 place-items-center rounded-lg border border-slate-200 bg-[#fffdf8] text-xl text-slate-400 shadow-sm">▤</div>`;
  return `<div class="relative grid h-14 w-12 shrink-0 place-items-center overflow-hidden rounded-lg border border-slate-200 bg-[#fffdf8] text-xl text-slate-400 shadow-sm" role="img" aria-label="Ảnh thu nhỏ ${escapeHtml(receipt.original_filename)}">▤</div>`;
}

function renderShell() {
  document.querySelector("#main-content").innerHTML = `<div class="w-full space-y-4 px-5 py-5">
    <header class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h1 class="text-[32px] font-bold leading-9 tracking-[-0.035em] text-slate-950">Hóa đơn</h1><p class="mt-1 text-sm font-normal leading-5 text-slate-500">Quản lý, kiểm tra và xác nhận dữ liệu hóa đơn</p></div><a href="/upload/" class="inline-flex h-10 items-center justify-center rounded-lg bg-teal-800 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"><span class="mr-2 text-lg leading-none" aria-hidden="true">＋</span>Tải hóa đơn</a></header>
    <section id="summary-cards" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Tổng quan hóa đơn"></section>
    <section aria-label="Bộ lọc hóa đơn">
      <div id="receipt-tabs" class="flex gap-1 overflow-x-auto border-b border-slate-200"></div>
      <div class="flex flex-col gap-2 py-3 xl:flex-row xl:items-center xl:justify-between">
        <label class="relative block w-full xl:max-w-xl"><span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true">⌕</span><span class="sr-only">Tìm kiếm hóa đơn</span><input id="query" type="search" placeholder="Tìm tên tệp hoặc cửa hàng..." class="h-10 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10"></label>
        <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          <label class="relative"><span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">◫</span><span class="sr-only">Khoảng ngày tải lên</span><select id="date-filter" class="h-10 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600 sm:w-auto"><option value="ALL">Ngày tải: Tất cả</option><option value="LAST_24_HOURS">24 giờ gần nhất</option><option value="LAST_7_DAYS">7 ngày gần nhất</option></select></label>
          <label class="relative"><span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">▣</span><span class="sr-only">Lọc theo cửa hàng</span><select id="merchant-filter" class="h-10 w-full max-w-56 appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600"></select></label>
          <button id="advanced-toggle" type="button" class="inline-flex h-10 items-center justify-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"><span class="mr-2" aria-hidden="true">☷</span><span>Bộ lọc</span></button>
          <label class="relative"><span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">⇅</span><span class="sr-only">Sắp xếp hóa đơn</span><select id="sort-order" class="h-10 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600 sm:w-auto"><option value="NEWEST">Mới nhất</option><option value="OLDEST">Cũ nhất</option><option value="TOTAL_HIGH">Tổng tiền giảm dần</option><option value="TOTAL_LOW">Tổng tiền tăng dần</option></select></label>
        </div>
      </div>
      <div id="advanced-filter"></div>
    </section>
    <section class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50" aria-label="Danh sách hóa đơn"><div class="overflow-x-auto"><table class="w-full min-w-[1120px] border-collapse text-left"><thead><tr class="h-10 border-b border-slate-200 bg-slate-50/80 text-xs font-semibold text-slate-600"><th class="px-4">Hóa đơn</th><th class="px-4 text-right">Tổng tiền</th><th class="px-4">Trạng thái</th><th class="px-4">Tình trạng kiểm tra</th><th class="px-4">Thời gian tải lên</th><th class="px-4 text-right">Hành động</th></tr></thead><tbody id="receipt-table" class="divide-y divide-slate-100 text-sm"></tbody></table></div><footer id="pagination" class="flex items-center justify-end border-t border-slate-100 px-4 py-2 text-xs text-slate-500"></footer></section>
  </div>`;
}

function renderSummary() {
  const counts = getCounts();
  const cards = [
    { label: "Cần kiểm tra", count: counts.NEEDS_REVIEW, helper: "Ưu tiên xử lý hôm nay", icon: "!", iconClass: "bg-amber-100 text-amber-700" },
    { label: "Đang xử lý", count: counts.IN_PROGRESS, helper: "Hệ thống OCR đang xử lý", icon: "◌", iconClass: "bg-sky-100 text-sky-700" },
    { label: "Đã xác minh", count: counts.VERIFIED, helper: "Dữ liệu sẵn sàng", icon: "✓", iconClass: "bg-emerald-100 text-emerald-700" },
    { label: "Thất bại", count: counts.FAILED, helper: "Hóa đơn cần thử lại", icon: "×", iconClass: "bg-red-100 text-red-700" },
  ];
  document.querySelector("#summary-cards").innerHTML = cards.map((card) => `<article class="flex min-h-20 items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-100/60"><span class="grid size-10 shrink-0 place-items-center rounded-lg text-lg font-bold ${card.iconClass}">${card.icon}</span><div><p class="text-base font-semibold leading-5 text-slate-900">${card.label}: ${card.count}</p><p class="mt-0.5 text-xs font-normal leading-4 text-slate-500">${card.helper}</p></div></article>`).join("");
}

function renderTabs() {
  const counts = getCounts();
  document.querySelector("#receipt-tabs").innerHTML = Object.entries(tabLabels).map(([tab, label]) => `<button type="button" data-tab="${tab}" class="relative flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold transition ${state.activeTab === tab ? "text-teal-800" : "text-slate-500 hover:text-slate-800"}">${label}<span class="rounded-full px-2 py-0.5 text-xs ${state.activeTab === tab ? "bg-teal-100 text-teal-800" : "bg-slate-200/70 text-slate-600"}">${counts[tab]}</span>${state.activeTab === tab ? '<span class="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-teal-700"></span>' : ""}</button>`).join("");
}

function renderAdvanced() {
  const host = document.querySelector("#advanced-filter");
  host.innerHTML = state.showAdvanced ? `<div class="mb-3 flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50/60 px-3 py-2"><label class="flex items-center gap-2 text-sm font-medium text-teal-900"><input id="review-only" type="checkbox" ${state.reviewOnly ? "checked" : ""} class="size-4 accent-teal-700">Chỉ hiện hóa đơn có trường cần kiểm tra</label><button id="reset-filters" type="button" class="text-xs font-bold text-teal-700 hover:text-teal-950">Đặt lại</button></div>` : "";
  const toggle = document.querySelector("#advanced-toggle");
  toggle.className = `inline-flex h-10 items-center justify-center rounded-lg border px-3 text-sm font-medium transition ${state.showAdvanced ? "border-teal-300 bg-teal-50 text-teal-800" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`;
  toggle.querySelector("span:last-child").textContent = `Bộ lọc${state.reviewOnly ? " · 1" : ""}`;
}

function renderTable() {
  const filtered = filteredReceipts();
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  state.page = Math.min(state.page, totalPages);
  const visible = filtered.slice((state.page - 1) * pageSize, state.page * pageSize);
  const tbody = document.querySelector("#receipt-table");
  if (state.loading) {
    tbody.innerHTML = Array.from({ length: 4 }, () => `<tr class="animate-pulse border-b border-slate-100"><td class="px-4 py-3"><div class="h-14 w-64 rounded-lg bg-slate-100"></div></td><td class="px-4 py-3"><div class="h-5 w-24 rounded bg-slate-100"></div></td><td class="px-4 py-3"><div class="h-7 w-28 rounded-full bg-slate-100"></div></td><td class="px-4 py-3"><div class="h-10 w-56 rounded bg-slate-100"></div></td><td class="px-4 py-3"><div class="h-5 w-32 rounded bg-slate-100"></div></td><td class="px-4 py-3"><div class="ml-auto h-9 w-24 rounded-lg bg-slate-100"></div></td></tr>`).join("");
    return;
  }
  if (!visible.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-6 py-16 text-center"><div class="mx-auto grid size-12 place-items-center rounded-full bg-slate-100 text-xl text-slate-400">⌕</div><p class="mt-4 font-bold text-slate-700">Không tìm thấy hóa đơn phù hợp</p><p class="mt-1 text-sm text-slate-400">Hãy thử bỏ bớt bộ lọc hoặc dùng từ khóa khác.</p></td></tr>`;
  } else {
    tbody.innerHTML = visible.map((receipt) => `<tr class="group transition-colors hover:bg-slate-50/70 ${receipt.status === "NEEDS_REVIEW" ? "bg-teal-50/40 shadow-[inset_0_1px_0_rgb(204_251_241),inset_0_-1px_0_rgb(204_251_241)]" : ""}"><td class="px-4 py-2"><div class="flex items-center gap-3">${thumbnail(receipt)}<div class="min-w-0"><p class="max-w-sm truncate text-sm font-semibold leading-5 text-slate-900">${escapeHtml(receipt.original_filename)}</p><p class="max-w-sm truncate text-xs font-normal uppercase leading-4 text-slate-500">${escapeHtml(receipt.merchant_name ?? "Chưa có kết quả KIE")}</p></div></div></td><td class="px-4 py-2 text-right font-semibold tabular-nums text-slate-800">${typeof receipt.total_amount === "number" ? formatVnd(receipt.total_amount) : '<span class="text-slate-400">—</span>'}</td><td class="px-4 py-2">${renderStatusBadge(receipt.status)}</td><td class="px-4 py-2">${reviewState(receipt)}</td><td class="whitespace-nowrap px-4 py-2 text-xs font-normal tabular-nums text-slate-500">${formatDate(receipt.created_at)}</td><td class="px-4 py-2"><div class="flex items-center justify-end gap-2"><a href="${receiptUrl(receipt.receipt_id)}" class="inline-flex h-9 items-center rounded-lg ${receipt.status === "NEEDS_REVIEW" ? "bg-teal-800 text-white hover:bg-teal-900" : "border border-slate-200 bg-white text-slate-700 hover:border-teal-300 hover:text-teal-800"} px-3 text-xs font-semibold transition">${receipt.status === "NEEDS_REVIEW" ? "Kiểm tra" : "Xem chi tiết"}<span class="ml-1.5" aria-hidden="true">→</span></a><button type="button" class="grid size-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Thêm hành động cho ${escapeHtml(receipt.original_filename)}">•••</button></div></td></tr>`).join("");
  }
  const rangeStart = filtered.length ? (state.page - 1) * pageSize + 1 : 0;
  const rangeEnd = Math.min(state.page * pageSize, filtered.length);
  document.querySelector("#pagination").innerHTML = `<div class="flex items-center gap-2"><span class="mr-1">${rangeStart}–${rangeEnd} trên ${filtered.length} hóa đơn</span><button type="button" data-page="prev" ${state.page === 1 ? "disabled" : ""} class="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40" aria-label="Trang trước">‹</button><span class="min-w-14 text-center font-medium">${state.page}/${totalPages}</span><button type="button" data-page="next" ${state.page === totalPages ? "disabled" : ""} class="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40" aria-label="Trang sau">›</button></div>`;
}

function renderDynamic() { renderSummary(); renderTabs(); renderAdvanced(); renderTable(); }

renderShell();
renderDynamic();

document.querySelector("#receipt-tabs").addEventListener("click", (event) => { const button = event.target.closest("[data-tab]"); if (!button) return; state.activeTab = button.dataset.tab; state.page = 1; renderDynamic(); });
document.querySelector("#query").addEventListener("input", (event) => { state.query = event.target.value; state.page = 1; renderTable(); });
document.querySelector("#date-filter").addEventListener("change", (event) => { state.dateFilter = event.target.value; state.page = 1; renderTable(); });
document.querySelector("#merchant-filter").addEventListener("change", (event) => { state.merchant = event.target.value; state.page = 1; renderTable(); });
document.querySelector("#sort-order").addEventListener("change", (event) => { state.sortOrder = event.target.value; state.page = 1; renderTable(); });
document.querySelector("#advanced-toggle").addEventListener("click", () => { state.showAdvanced = !state.showAdvanced; renderAdvanced(); });
document.querySelector("#advanced-filter").addEventListener("change", (event) => { if (event.target.id !== "review-only") return; state.reviewOnly = event.target.checked; state.page = 1; renderDynamic(); });
document.querySelector("#advanced-filter").addEventListener("click", (event) => { if (event.target.id !== "reset-filters") return; state.reviewOnly = false; state.dateFilter = "ALL"; state.merchant = "ALL"; state.page = 1; document.querySelector("#date-filter").value = "ALL"; document.querySelector("#merchant-filter").value = "ALL"; renderDynamic(); });
document.querySelector("#pagination").addEventListener("click", (event) => { const button = event.target.closest("[data-page]"); if (!button || button.disabled) return; state.page += button.dataset.page === "next" ? 1 : -1; renderTable(); });

try {
  const page = await vietReceiptApi.getReceipts({ page: 1, page_size: 100 });
  state.receipts = page.items;
  const merchants = [...new Set(state.receipts.map((receipt) => receipt.merchant_name).filter(Boolean))].sort((a, b) => a.localeCompare(b, "vi"));
  document.querySelector("#merchant-filter").innerHTML = `<option value="ALL">Cửa hàng: Tất cả</option>${merchants.map((merchant) => `<option value="${escapeHtml(merchant)}">${escapeHtml(merchant)}</option>`).join("")}`;
} catch (error) {
  announce(getApiErrorMessage(error), "error");
} finally {
  state.loading = false;
  renderDynamic();
}
