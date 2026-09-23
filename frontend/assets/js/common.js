// @ts-nocheck
export const CORE_FIELD_TYPES = [
  "merchant_name",
  "receipt_date",
  "total_amount",
  "invoice_id",
  "merchant_address",
];

export const FIELD_LABELS = {
  merchant_name: "Tên cửa hàng",
  receipt_date: "Ngày giao dịch",
  total_amount: "Tổng tiền",
  invoice_id: "Mã hóa đơn",
  merchant_address: "Địa chỉ cửa hàng",
};

export const PUBLIC_RECEIPT_STATUSES = [
  "UPLOADED",
  "PROCESSING",
  "NEEDS_REVIEW",
  "VERIFIED",
  "FAILED",
];

export const STATUS_CONFIG = {
  UPLOADED: { label: "Đã tải lên", className: "bg-slate-100 text-slate-700 ring-slate-200", dot: "bg-slate-400" },
  PROCESSING: { label: "Đang xử lý", className: "bg-sky-50 text-sky-700 ring-sky-200", dot: "bg-sky-500" },
  NEEDS_REVIEW: { label: "Cần kiểm tra", className: "bg-amber-50 text-amber-800 ring-amber-200", dot: "bg-amber-500" },
  VERIFIED: { label: "Đã xác minh", className: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500" },
  FAILED: { label: "Thất bại", className: "bg-red-50 text-red-700 ring-red-200", dot: "bg-red-500" },
};

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value) {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatVnd(value, suffix = " VND") {
  return `${new Intl.NumberFormat("vi-VN").format(value)}${suffix}`;
}

export function deepClone(value) {
  return structuredClone(value);
}

export function receiptUrl(receiptId) {
  return `/receipts/${encodeURIComponent(receiptId)}/`;
}

export function getReceiptIdFromLocation() {
  const queryId = new URLSearchParams(window.location.search).get("id");
  if (queryId) return queryId;
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts[0] === "receipts" && parts.length >= 2 && parts[1] !== "detail.html"
    ? decodeURIComponent(parts[1])
    : null;
}

export function renderStatusBadge(status) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.FAILED;
  return `<span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold leading-5 ring-1 ring-inset ${config.className}">
    <span class="size-1.5 rounded-full ${config.dot}" aria-hidden="true"></span>${config.label}
  </span>`;
}

export function renderNavigation() {
  const host = document.querySelector("#site-navigation");
  if (!host) return;
  const pathname = window.location.pathname;
  const navItems = [
    { href: "/upload/", label: "Tải hóa đơn", active: pathname.startsWith("/upload") },
    { href: "/receipts/", label: "Hóa đơn", active: pathname.startsWith("/receipts") },
  ];

  host.innerHTML = `<header class="sticky top-0 z-50 h-14 border-b border-slate-200/90 bg-white/95 backdrop-blur">
    <div class="flex h-full w-full items-center gap-3 px-5">
      <a href="/receipts/" class="flex shrink-0 items-center gap-2.5 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2" aria-label="VietReceipt — Trang hóa đơn">
        <span class="grid size-9 place-items-center rounded-xl bg-teal-800 text-base font-black tracking-tight text-white shadow-sm shadow-teal-900/20">V</span>
        <span class="hidden text-lg font-bold tracking-[-0.025em] text-slate-950 sm:inline">VietReceipt</span>
      </a>
      <nav class="ml-1 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:ml-6" aria-label="Điều hướng chính">
        ${navItems.map((item) => `<a href="${item.href}" class="shrink-0 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${item.active ? "bg-teal-50 text-teal-800" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"}">${item.label}</a>`).join("")}
      </nav>
      <span class="hidden text-xs text-slate-500 lg:inline">Bản thử nghiệm · chưa có đăng nhập</span>
    </div>
  </header>`;
}

export function setBusy(button, busy, busyText, idleText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : idleText;
}

export function announce(message, tone = "success") {
  let toast = document.querySelector("#global-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "global-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.className = "fixed bottom-5 right-5 z-[80] max-w-sm rounded-xl px-4 py-3 text-sm font-bold text-white shadow-2xl transition-all duration-300";
    document.body.append(toast);
  }
  toast.classList.toggle("bg-red-700", tone === "error");
  toast.classList.toggle("bg-slate-950", tone !== "error");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(announce.timer);
  announce.timer = window.setTimeout(() => { toast.hidden = true; }, 4200);
}
