"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StatusBadge } from "../../components/status-badge";
import { createBrowserVietReceiptApi, getApiErrorMessage } from "../../lib/vietreceipt-api";
import type { ReceiptPage, ReceiptStatus } from "../../types/receipt";

type StatusFilter = "ALL" | ReceiptStatus;
const pageSize = 20;

const statusLabels: Record<StatusFilter, string> = {
  ALL: "Tất cả",
  UPLOADED: "Đã tải",
  PROCESSING: "Đang xử lý",
  NEEDS_REVIEW: "Cần kiểm tra",
  VERIFIED: "Đã xác minh",
  FAILED: "Thất bại",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatVnd(value: number | null | undefined) {
  return value === null || value === undefined
    ? "—"
    : `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
}

export default function ReceiptsPage() {
  const api = useMemo(() => createBrowserVietReceiptApi(), []);
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ReceiptPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await api.getReceipts(
        {
          page,
          page_size: pageSize,
          status: status === "ALL" ? undefined : status,
        },
        { signal },
      );
      setData(result);
      setError(null);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(getApiErrorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [api, page, status]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load, reloadKey]);

  const visibleItems = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("vi");
    if (!normalized) return data?.items ?? [];
    return (data?.items ?? []).filter((receipt) =>
      receipt.original_filename.toLocaleLowerCase("vi").includes(normalized) ||
      receipt.merchant_name?.toLocaleLowerCase("vi").includes(normalized),
    );
  }, [data, query]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700">Workflow thật</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Hóa đơn</h1>
          <p className="mt-2 text-sm text-slate-500">Danh sách được tải từ canonical Backend API, không dùng fixture trong component.</p>
        </div>
        <Link href="/upload" className="inline-flex h-11 items-center justify-center rounded-xl bg-teal-800 px-5 text-sm font-bold text-white">
          + Tải hóa đơn
        </Link>
      </header>

      <section className="mt-7 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-4 sm:p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {(Object.keys(statusLabels) as StatusFilter[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { setLoading(true); setError(null); setStatus(value); setPage(1); }}
                  className={`shrink-0 rounded-lg px-3 py-2 text-xs font-bold ${status === value ? "bg-teal-800 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                >
                  {statusLabels[value]}
                </button>
              ))}
            </div>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Lọc tên file hoặc cửa hàng trên trang..."
              className="h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10 lg:w-80"
            />
          </div>
        </div>

        {error ? (
          <div className="p-10 text-center">
            <p role="alert" className="font-semibold text-red-700">{error}</p>
            <button type="button" onClick={() => { setLoading(true); setError(null); setReloadKey((value) => value + 1); }} className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white">
              Thử tải lại
            </button>
          </div>
        ) : loading && !data ? (
          <div className="space-y-3 p-5" aria-label="Đang tải danh sách">
            {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-20 animate-pulse rounded-2xl bg-slate-100" />)}
          </div>
        ) : visibleItems.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-500">Không có hóa đơn phù hợp.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-left">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Hóa đơn</th>
                  <th className="px-5 py-3">Trạng thái</th>
                  <th className="px-5 py-3">Cửa hàng</th>
                  <th className="px-5 py-3">Tổng tiền</th>
                  <th className="px-5 py-3">Thời gian</th>
                  <th className="px-5 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((receipt) => (
                  <tr key={receipt.receipt_id} className="border-t border-slate-100 text-sm">
                    <td className="px-5 py-4">
                      <p className="max-w-64 truncate font-bold text-slate-900">{receipt.original_filename}</p>
                      <p className="mt-1 font-mono text-[10px] text-slate-400">{receipt.receipt_id}</p>
                    </td>
                    <td className="px-5 py-4"><StatusBadge status={receipt.status} /></td>
                    <td className="px-5 py-4 text-slate-700">{receipt.merchant_name ?? "—"}</td>
                    <td className="px-5 py-4 font-semibold text-slate-800">{formatVnd(receipt.total_amount)}</td>
                    <td className="px-5 py-4 text-slate-500">{formatDate(receipt.created_at)}</td>
                    <td className="px-5 py-4 text-right">
                      <Link href={`/receipts/${encodeURIComponent(receipt.receipt_id)}`} className="rounded-lg bg-teal-50 px-3 py-2 text-xs font-bold text-teal-800 hover:bg-teal-100">
                        Mở chi tiết →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="flex items-center justify-between border-t border-slate-100 px-5 py-4 text-sm text-slate-500">
          <span>{loading && data ? "Đang cập nhật..." : `${data?.total_items ?? 0} hóa đơn`}</span>
          <div className="flex items-center gap-2">
            <button type="button" disabled={page <= 1 || loading} onClick={() => { setLoading(true); setPage((value) => value - 1); }} className="rounded-lg border border-slate-200 px-3 py-2 font-bold disabled:opacity-40">←</button>
            <span>Trang {data?.page ?? page}/{Math.max(1, data?.total_pages ?? 1)}</span>
            <button type="button" disabled={loading || page >= (data?.total_pages ?? 0)} onClick={() => { setLoading(true); setPage((value) => value + 1); }} className="rounded-lg border border-slate-200 px-3 py-2 font-bold disabled:opacity-40">→</button>
          </div>
        </footer>
      </section>
    </div>
  );
}
