import type { ReceiptStatus } from "../types/receipt";

const statusConfig: Record<
  ReceiptStatus,
  { label: string; className: string; dot: string }
> = {
  UPLOADED: {
    label: "Đã tải lên",
    className: "bg-slate-100 text-slate-700 ring-slate-200",
    dot: "bg-slate-400",
  },
  PROCESSING: {
    label: "Đang xử lý",
    className: "bg-sky-50 text-sky-700 ring-sky-200",
    dot: "bg-sky-500",
  },
  NEEDS_REVIEW: {
    label: "Cần kiểm tra",
    className: "bg-amber-50 text-amber-800 ring-amber-200",
    dot: "bg-amber-500",
  },
  VERIFIED: {
    label: "Đã xác minh",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    dot: "bg-emerald-500",
  },
  FAILED: {
    label: "Thất bại",
    className: "bg-red-50 text-red-700 ring-red-200",
    dot: "bg-red-500",
  },
};

export function StatusBadge({ status }: { status: ReceiptStatus }) {
  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold leading-5 ring-1 ring-inset ${config.className}`}
    >
      <span className={`size-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  );
}
