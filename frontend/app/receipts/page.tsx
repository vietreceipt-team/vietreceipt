"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  ArrowUpDown,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  CircleX,
  ListFilter,
  LoaderCircle,
  MoreHorizontal,
  Plus,
  Search,
  Store,
} from "lucide-react";
import { mockReceiptPage } from "../../data/mock-receipts";
import { StatusBadge } from "../../components/status-badge";
import { ReceiptThumbnail } from "../../components/receipt-thumbnail";
import { apiPaths } from "../../lib/vietreceipt-api";
import type { ReceiptStatus, ReceiptSummary } from "../../types/receipt";

type ReceiptTab = "ALL" | "NEEDS_REVIEW" | "IN_PROGRESS" | "VERIFIED" | "FAILED";
type DateFilter = "ALL" | "LAST_24_HOURS" | "LAST_7_DAYS";
type SortOrder = "NEWEST" | "OLDEST" | "TOTAL_HIGH" | "TOTAL_LOW";

const tabLabels: Record<ReceiptTab, string> = {
  ALL: "Tất cả",
  NEEDS_REVIEW: "Cần kiểm tra",
  IN_PROGRESS: "Đang xử lý",
  VERIFIED: "Đã xác minh",
  FAILED: "Thất bại",
};

const inProgressStatuses: ReceiptStatus[] = ["UPLOADED", "QUEUED", "PROCESSING"];
const pageSize = 5;
const receiptSummaries = mockReceiptPage.items;

function formatDate(date: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

function formatVnd(value: number) {
  return `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
}

function matchesTab(receipt: ReceiptSummary, tab: ReceiptTab) {
  if (tab === "ALL") return true;
  if (tab === "IN_PROGRESS") return inProgressStatuses.includes(receipt.status);
  return receipt.status === tab;
}

function ReviewState({ receipt }: { receipt: ReceiptSummary }) {
  if (receipt.status === "NEEDS_REVIEW") {
    return (
      <div className="min-w-56">
        <p className="font-bold text-teal-800">Có trường cần người dùng kiểm tra</p>
        <p className="mt-0.5 text-sm text-slate-500">Mở chi tiết để xem trạng thái hiệu lực và lý do.</p>
      </div>
    );
  }

  if (receipt.status === "VERIFIED") {
    return (
      <div className="min-w-56">
        <p className="font-bold text-slate-800">Đã xác minh tất cả các trường</p>
        <p className="mt-0.5 text-xs font-semibold text-emerald-700">Quyết định bởi người kiểm duyệt</p>
      </div>
    );
  }

  if (receipt.status === "PROCESSING") {
    return (
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
        <LoaderCircle className="size-4 animate-spin text-sky-600" aria-hidden="true" />
        Đang xử lý OCR... <span className="text-xs font-normal text-slate-400">Chưa có kết quả KIE</span>
      </div>
    );
  }

  if (receipt.status === "QUEUED") {
    return <p className="text-sm font-medium text-slate-600">Đang chờ trong hàng OCR</p>;
  }

  if (receipt.status === "UPLOADED") {
    return <p className="text-sm font-medium text-slate-600">Đã nhận tệp · Chưa bắt đầu xử lý</p>;
  }

  return (
    <div className="min-w-56">
      <p className="font-bold text-red-700">Không thể xử lý hóa đơn</p>
      <p className="mt-0.5 text-sm text-slate-500">Mở chi tiết để xem lỗi an toàn do Backend trả về.</p>
    </div>
  );
}

function LoadingRows() {
  return (
    <>
      {Array.from({ length: 4 }).map((_, index) => (
        <tr key={index} className="animate-pulse border-b border-slate-100">
          <td className="px-4 py-3"><div className="h-14 w-64 rounded-lg bg-slate-100" /></td>
          <td className="px-4 py-3"><div className="h-5 w-24 rounded bg-slate-100" /></td>
          <td className="px-4 py-3"><div className="h-7 w-28 rounded-full bg-slate-100" /></td>
          <td className="px-4 py-3"><div className="h-10 w-56 rounded bg-slate-100" /></td>
          <td className="px-4 py-3"><div className="h-5 w-32 rounded bg-slate-100" /></td>
          <td className="px-4 py-3"><div className="ml-auto h-9 w-24 rounded-lg bg-slate-100" /></td>
        </tr>
      ))}
    </>
  );
}

export default function ReceiptsPage() {
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState<ReceiptTab>("ALL");
  const [dateFilter, setDateFilter] = useState<DateFilter>("ALL");
  const [merchant, setMerchant] = useState("ALL");
  const [sortOrder, setSortOrder] = useState<SortOrder>("NEWEST");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setLoading(false), 500);
    return () => window.clearTimeout(timer);
  }, []);

  const counts = useMemo<Record<ReceiptTab, number>>(() => ({
    ALL: receiptSummaries.length,
    NEEDS_REVIEW: receiptSummaries.filter((receipt) => receipt.status === "NEEDS_REVIEW").length,
    IN_PROGRESS: receiptSummaries.filter((receipt) => inProgressStatuses.includes(receipt.status)).length,
    VERIFIED: receiptSummaries.filter((receipt) => receipt.status === "VERIFIED").length,
    FAILED: receiptSummaries.filter((receipt) => receipt.status === "FAILED").length,
  }), []);

  const merchants = useMemo(() => Array.from(new Set(
    receiptSummaries
      .map((receipt) => receipt.merchant_name)
      .filter((value): value is string => Boolean(value)),
  )).sort((a, b) => a.localeCompare(b, "vi")), []);

  const latestUploadTime = useMemo(() => Math.max(
    ...receiptSummaries.map((receipt) => new Date(receipt.created_at).getTime()),
  ), []);

  const filteredReceipts = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("vi");
    const dateWindow = dateFilter === "LAST_24_HOURS"
      ? 24 * 60 * 60 * 1000
      : dateFilter === "LAST_7_DAYS"
        ? 7 * 24 * 60 * 60 * 1000
        : null;

    const result = receiptSummaries.filter((receipt) => {
      const matchesQuery = !normalized
        || receipt.original_filename.toLocaleLowerCase("vi").includes(normalized)
        || (receipt.merchant_name?.toLocaleLowerCase("vi").includes(normalized) ?? false);
      const matchesDate = dateWindow === null
        || latestUploadTime - new Date(receipt.created_at).getTime() <= dateWindow;
      const matchesMerchant = merchant === "ALL" || receipt.merchant_name === merchant;
      const matchesReviewOnly = !reviewOnly || receipt.status === "NEEDS_REVIEW";

      return matchesTab(receipt, activeTab)
        && matchesQuery
        && matchesDate
        && matchesMerchant
        && matchesReviewOnly;
    });

    return result.sort((left, right) => {
      if (sortOrder === "NEWEST") return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
      if (sortOrder === "OLDEST") return new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      const leftTotal = left.total_amount ?? -1;
      const rightTotal = right.total_amount ?? -1;
      return sortOrder === "TOTAL_HIGH" ? rightTotal - leftTotal : leftTotal - rightTotal;
    });
  }, [activeTab, dateFilter, latestUploadTime, merchant, query, reviewOnly, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredReceipts.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleReceipts = filteredReceipts.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const rangeStart = filteredReceipts.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(currentPage * pageSize, filteredReceipts.length);

  return (
    <div className="w-full space-y-4 px-5 py-5">
      <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-[32px] font-bold leading-9 tracking-[-0.035em] text-slate-950">Hóa đơn</h1>
          <p className="mt-1 text-sm font-normal leading-5 text-slate-500">Quản lý, kiểm tra và xác nhận dữ liệu hóa đơn</p>
        </div>
        <Link
          href="/upload"
          className="inline-flex h-10 items-center justify-center rounded-lg bg-teal-800 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
        >
          <Plus className="mr-2 size-4" aria-hidden="true" /> Tải hóa đơn
        </Link>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Tổng quan hóa đơn">
        {[
          { label: "Cần kiểm tra", count: counts.NEEDS_REVIEW, helper: "Ưu tiên xử lý hôm nay", icon: AlertCircle, iconClass: "bg-amber-100 text-amber-700" },
          { label: "Đang xử lý", count: counts.IN_PROGRESS, helper: "Hệ thống OCR đang xử lý", icon: LoaderCircle, iconClass: "bg-sky-100 text-sky-700" },
          { label: "Đã xác minh", count: counts.VERIFIED, helper: "Dữ liệu sẵn sàng", icon: CircleCheck, iconClass: "bg-emerald-100 text-emerald-700" },
          { label: "Thất bại", count: counts.FAILED, helper: "Hóa đơn cần thử lại", icon: CircleX, iconClass: "bg-red-100 text-red-700" },
        ].map((card) => (
          <article key={card.label} className="flex min-h-20 items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-100/60">
            <span className={`grid size-10 shrink-0 place-items-center rounded-lg ${card.iconClass}`}><card.icon className="size-5" aria-hidden="true" /></span>
            <div>
              <p className="text-base font-semibold leading-5 text-slate-900">{card.label}: {card.count}</p>
              <p className="mt-0.5 text-xs font-normal leading-4 text-slate-500">{card.helper}</p>
            </div>
          </article>
        ))}
      </section>

      <section aria-label="Bộ lọc hóa đơn">
        <div className="flex gap-1 overflow-x-auto border-b border-slate-200">
          {(Object.keys(tabLabels) as ReceiptTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => { setActiveTab(tab); setPage(1); }}
              className={`relative flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-semibold transition ${activeTab === tab ? "text-teal-800" : "text-slate-500 hover:text-slate-800"}`}
            >
              {tabLabels[tab]}
              <span className={`rounded-full px-2 py-0.5 text-xs ${activeTab === tab ? "bg-teal-100 text-teal-800" : "bg-slate-200/70 text-slate-600"}`}>{counts[tab]}</span>
              {activeTab === tab && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-teal-700" />}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2 py-3 xl:flex-row xl:items-center xl:justify-between">
          <label className="relative block w-full xl:max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <span className="sr-only">Tìm kiếm hóa đơn</span>
            <input
              type="search"
              value={query}
              onChange={(event) => { setQuery(event.target.value); setPage(1); }}
              placeholder="Tìm tên tệp hoặc cửa hàng..."
              className="h-10 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10"
            />
          </label>

          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <label className="relative">
              <CalendarDays className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <span className="sr-only">Khoảng ngày tải lên</span>
              <select value={dateFilter} onChange={(event) => { setDateFilter(event.target.value as DateFilter); setPage(1); }} className="h-10 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600 sm:w-auto">
                <option value="ALL">Ngày tải: Tất cả</option>
                <option value="LAST_24_HOURS">24 giờ gần nhất</option>
                <option value="LAST_7_DAYS">7 ngày gần nhất</option>
              </select>
            </label>
            <label className="relative">
              <Store className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <span className="sr-only">Lọc theo cửa hàng</span>
              <select value={merchant} onChange={(event) => { setMerchant(event.target.value); setPage(1); }} className="h-10 w-full max-w-56 appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600">
                <option value="ALL">Cửa hàng: Tất cả</option>
                {merchants.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <button type="button" onClick={() => setShowAdvanced((value) => !value)} className={`inline-flex h-10 items-center justify-center rounded-lg border px-3 text-sm font-medium transition ${showAdvanced ? "border-teal-300 bg-teal-50 text-teal-800" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>
              <ListFilter className="mr-2 size-4" aria-hidden="true" /> Bộ lọc {reviewOnly ? "· 1" : ""}
            </button>
            <label className="relative">
              <ArrowUpDown className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <span className="sr-only">Sắp xếp hóa đơn</span>
              <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value as SortOrder); setPage(1); }} className="h-10 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-9 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-teal-600 sm:w-auto">
                <option value="NEWEST">Mới nhất</option>
                <option value="OLDEST">Cũ nhất</option>
                <option value="TOTAL_HIGH">Tổng tiền giảm dần</option>
                <option value="TOTAL_LOW">Tổng tiền tăng dần</option>
              </select>
            </label>
          </div>
        </div>

        {showAdvanced && (
          <div className="mb-3 flex items-center justify-between rounded-lg border border-teal-100 bg-teal-50/60 px-3 py-2">
            <label className="flex items-center gap-2 text-sm font-medium text-teal-900">
              <input type="checkbox" checked={reviewOnly} onChange={(event) => { setReviewOnly(event.target.checked); setPage(1); }} className="size-4 accent-teal-700" />
              Chỉ hiện hóa đơn có trường cần kiểm tra
            </label>
            <button type="button" onClick={() => { setReviewOnly(false); setDateFilter("ALL"); setMerchant("ALL"); setPage(1); }} className="text-xs font-bold text-teal-700 hover:text-teal-950">Đặt lại</button>
          </div>
        )}
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50" aria-label="Danh sách hóa đơn">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1120px] border-collapse text-left">
            <thead>
              <tr className="h-10 border-b border-slate-200 bg-slate-50/80 text-xs font-semibold text-slate-600">
                <th className="px-4">Hóa đơn</th>
                <th className="px-4 text-right">Tổng tiền</th>
                <th className="px-4">Trạng thái</th>
                <th className="px-4">Tình trạng kiểm tra</th>
                <th className="px-4">Thời gian tải lên</th>
                <th className="px-4 text-right">Hành động</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {loading ? <LoadingRows /> : visibleReceipts.map((receipt) => {
                const hasFinalTotal = receipt.total_amount !== null && receipt.total_amount !== undefined;
                return (
                  <tr key={receipt.receipt_id} className={`group transition-colors hover:bg-slate-50/70 ${receipt.status === "NEEDS_REVIEW" ? "bg-teal-50/40 shadow-[inset_0_1px_0_rgb(204_251_241),inset_0_-1px_0_rgb(204_251_241)]" : ""}`}>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-3">
                        <ReceiptThumbnail label={receipt.original_filename} src={apiPaths.receiptImage(receipt.receipt_id)} />
                        <div className="min-w-0">
                          <p className="max-w-sm truncate text-sm font-semibold leading-5 text-slate-900">{receipt.original_filename}</p>
                          <p className="max-w-sm truncate text-xs font-normal uppercase leading-4 text-slate-500">{receipt.merchant_name ?? "Chưa có kết quả KIE"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold tabular-nums text-slate-800">
                      {hasFinalTotal ? formatVnd(receipt.total_amount as number) : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-2"><StatusBadge status={receipt.status} /></td>
                    <td className="px-4 py-2"><ReviewState receipt={receipt} /></td>
                    <td className="whitespace-nowrap px-4 py-2 text-xs font-normal tabular-nums text-slate-500">{formatDate(receipt.created_at)}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center justify-end gap-2">
                        {receipt.status === "NEEDS_REVIEW" && (
                          <Link href={`/receipts/${receipt.receipt_id}`} className="inline-flex h-9 items-center rounded-lg bg-teal-800 px-3 text-xs font-semibold text-white transition hover:bg-teal-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600">
                            Kiểm tra <ArrowRight className="ml-1.5 size-3.5" aria-hidden="true" />
                          </Link>
                        )}
                        {receipt.status !== "NEEDS_REVIEW" && (
                          <Link href={`/receipts/${receipt.receipt_id}`} className="inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:border-teal-300 hover:text-teal-800">
                            Xem chi tiết <ArrowRight className="ml-1.5 size-3.5" aria-hidden="true" />
                          </Link>
                        )}
                        <button type="button" className="grid size-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label={`Thêm hành động cho ${receipt.original_filename}`}><MoreHorizontal className="size-4" aria-hidden="true" /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!loading && visibleReceipts.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-16 text-center">
                    <div className="mx-auto grid size-12 place-items-center rounded-full bg-slate-100 text-xl text-slate-400">⌕</div>
                    <p className="mt-4 font-bold text-slate-700">Không tìm thấy hóa đơn phù hợp</p>
                    <p className="mt-1 text-sm text-slate-400">Hãy thử bỏ bớt bộ lọc hoặc dùng từ khóa khác.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <footer className="flex items-center justify-end border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="mr-1">{rangeStart}–{rangeEnd} trên {filteredReceipts.length} hóa đơn</span>
            <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1} className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40" aria-label="Trang trước"><ChevronLeft className="size-4" /></button>
            <span className="min-w-14 text-center font-medium">{currentPage}/{totalPages}</span>
            <button type="button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={currentPage === totalPages} className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white disabled:opacity-40" aria-label="Trang sau"><ChevronRight className="size-4" /></button>
          </div>
        </footer>
      </section>
    </div>
  );
}
