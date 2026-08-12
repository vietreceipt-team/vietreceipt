"use client";

import { type ChangeEvent, type CSSProperties, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getReceiptById } from "../../../data/mock-receipts";
import { apiPaths, createFieldCorrectionRequest } from "../../../lib/vietreceipt-api";
import {
  CORE_FIELD_TYPES,
  FIELD_LABELS,
  getExtractedField,
  type ExtractedField,
  type FieldType,
  type FieldValue,
  type OcrBlock,
  type ReviewReason,
  type ValueStatus,
} from "../../../types/receipt";

interface FieldDraft {
  value: FieldValue;
  value_status: ValueStatus;
  resolved: boolean;
}

type FieldDrafts = Partial<Record<FieldType, FieldDraft>>;

const statusStyles: Record<ValueStatus, { label: string; badge: string; border: string; dot: string }> = {
  PRESENT: {
    label: "Có dữ liệu",
    badge: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    border: "border-emerald-300 focus:border-emerald-500 focus:ring-emerald-500/10",
    dot: "bg-emerald-500",
  },
  NOT_PRESENT: {
    label: "Không có trên hóa đơn",
    badge: "bg-slate-100 text-slate-700 ring-slate-200",
    border: "border-slate-300 focus:border-slate-500 focus:ring-slate-500/10",
    dot: "bg-slate-500",
  },
  UNREADABLE: {
    label: "Không đọc được",
    badge: "bg-orange-50 text-orange-800 ring-orange-200",
    border: "border-orange-300 focus:border-orange-500 focus:ring-orange-500/10",
    dot: "bg-orange-500",
  },
  AMBIGUOUS: {
    label: "Mơ hồ",
    badge: "bg-red-50 text-red-700 ring-red-200",
    border: "border-red-300 focus:border-red-500 focus:ring-red-500/10",
    dot: "bg-red-500",
  },
  UNKNOWN: {
    label: "Chưa xác định",
    badge: "bg-amber-50 text-amber-800 ring-amber-200",
    border: "border-amber-300 focus:border-amber-500 focus:ring-amber-500/10",
    dot: "bg-amber-500",
  },
};

const reasonLabels: Record<ReviewReason, string> = {
  LOW_CONFIDENCE: "Độ tin cậy thấp",
  NOT_PRESENT: "Có thể không tồn tại",
  UNREADABLE: "Nguồn không đọc được",
  AMBIGUOUS: "Có nhiều cách diễn giải",
  UNKNOWN: "Chưa xác định được giá trị",
  NORMALIZATION_FAILED: "Không chuẩn hóa an toàn",
  FORMAT_INVALID: "Định dạng không hợp lệ",
};

function formatVnd(value: number) {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function valuesEqual(left: FieldValue, right: FieldValue) {
  return left === right;
}

function getOcrPolygonStyle(block: OcrBlock): CSSProperties {
  const xs = block.polygon.map((point) => point.x);
  const ys = block.polygon.map((point) => point.y);
  const left = Math.min(...xs);
  const top = Math.min(...ys);

  return {
    left: `${left * 100}%`,
    top: `${top * 100}%`,
    width: `${(Math.max(...xs) - left) * 100}%`,
    height: `${(Math.max(...ys) - top) * 100}%`,
  };
}

export default function ReceiptReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const receipt = getReceiptById(params.id);
  const [zoom, setZoom] = useState(95);
  const [rotation, setRotation] = useState(0);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);

  const orderedFields = useMemo(() => {
    if (!receipt) return [];
    return CORE_FIELD_TYPES
      .map((fieldType) => getExtractedField(receipt, fieldType))
      .filter((field): field is ExtractedField => Boolean(field));
  }, [receipt]);

  const initialDrafts = useMemo<FieldDrafts>(() => Object.fromEntries(
    orderedFields.map((field) => [
      field.field_type,
      {
        value: field.effective_value,
        value_status: field.effective_status,
        resolved: !field.effective_needs_review,
      },
    ]),
  ), [orderedFields]);

  const [drafts, setDrafts] = useState<FieldDrafts>(initialDrafts);

  if (!receipt) {
    return (
      <div className="grid min-h-[calc(100dvh-56px)] place-items-center px-4 text-center">
        <div>
          <p className="text-5xl">404</p>
          <h1 className="mt-4 text-2xl font-bold text-slate-900">Không tìm thấy hóa đơn</h1>
          <Link href="/receipts" className="mt-5 inline-flex rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white">Quay lại danh sách</Link>
        </div>
      </div>
    );
  }

  if (orderedFields.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <Link href="/receipts" className="text-sm font-bold text-teal-700">← Quay lại danh sách</Link>
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">{receipt.status}</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-950">{receipt.original_filename}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {receipt.status === "UPLOADED" && "Ảnh đã được lưu. Theo contract v1.3, bước xử lý được bắt đầu riêng qua endpoint process."}
            {receipt.status === "QUEUED" && "Job xử lý đã được chấp nhận và đang chờ worker."}
            {receipt.status === "PROCESSING" && `Worker đang ở giai đoạn ${receipt.processing_stage ?? "không xác định"}.`}
            {receipt.status === "FAILED" && (receipt.last_error?.message ?? "Pipeline đã dừng do lỗi xử lý.")}
          </p>
          {receipt.status === "FAILED" && receipt.last_error && (
            <dl className="mt-5 grid gap-3 rounded-2xl bg-red-50 p-4 text-sm sm:grid-cols-3">
              <div><dt className="text-red-500">Giai đoạn</dt><dd className="mt-1 font-bold text-red-900">{receipt.last_error.stage}</dd></div>
              <div><dt className="text-red-500">Mã lỗi</dt><dd className="mt-1 font-bold text-red-900">{receipt.last_error.code}</dd></div>
              <div><dt className="text-red-500">Có thể thử lại</dt><dd className="mt-1 font-bold text-red-900">{receipt.last_error.retryable ? "Có" : "Không"}</dd></div>
            </dl>
          )}
          <p className="mt-5 text-xs text-slate-400">Ảnh được truy cập qua {apiPaths.receiptImage(receipt.receipt_id)}, không qua đường dẫn Storage nội bộ.</p>
        </section>
      </div>
    );
  }

  const canEdit = receipt.status === "NEEDS_REVIEW";
  const unresolvedCount = orderedFields.filter((field) => !drafts[field.field_type]?.resolved).length;
  const merchant = getExtractedField(receipt, "merchant_name");
  const date = getExtractedField(receipt, "receipt_date");
  const total = getExtractedField(receipt, "total_amount");
  const invoiceId = getExtractedField(receipt, "invoice_id");
  const address = getExtractedField(receipt, "merchant_address");

  function updateDraft(fieldType: FieldType, next: Partial<FieldDraft>) {
    setDrafts((current) => ({
      ...current,
      [fieldType]: { ...current[fieldType]!, ...next },
    }));
    setNotice(null);
  }

  function handleChange(field: ExtractedField, event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const rawValue = event.target.value;
    const value = field.field_type === "total_amount"
      ? rawValue === "" ? null : Number(rawValue)
      : rawValue === "" ? null : rawValue;

    updateDraft(field.field_type, {
      value,
      value_status: value === null ? "UNKNOWN" : "PRESENT",
      resolved: value !== null,
    });
  }

  function handleStatus(fieldType: FieldType, valueStatus: ValueStatus) {
    const current = drafts[fieldType]!;
    const value = valueStatus === "PRESENT" ? current.value : null;
    updateDraft(fieldType, {
      value,
      value_status: valueStatus,
      resolved: valueStatus === "NOT_PRESENT" || valueStatus === "UNREADABLE" || (valueStatus === "PRESENT" && value !== null),
    });
  }

  function verify() {
    if (unresolvedCount > 0) {
      setNotice({ tone: "error", message: `Còn ${unresolvedCount} trường chưa được giải quyết.` });
      return;
    }

    const corrections = orderedFields.flatMap((field) => {
      const draft = drafts[field.field_type]!;
      const changed = field.effective_needs_review
        || draft.value_status !== field.effective_status
        || !valuesEqual(draft.value, field.effective_value);

      return changed
        ? [createFieldCorrectionRequest(field, draft.value, draft.value_status)]
        : [];
    });

    setNotice({
      tone: "success",
      message: corrections.length > 0
        ? `Đã chuẩn bị ${corrections.length} correction hợp lệ và yêu cầu verify.`
        : "Hóa đơn đã ở trạng thái xác minh.",
    });
  }

  return (
    <div className="relative flex h-[calc(100dvh-56px)] min-h-0 flex-col overflow-hidden bg-slate-100 lg:flex-row">
      <section className="flex h-[46%] min-h-0 flex-col border-b border-slate-300 bg-slate-800 lg:h-full lg:w-[58%] lg:border-b-0 lg:border-r" aria-label="Ảnh hóa đơn gốc">
        <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/10 bg-slate-900/90 px-3 text-white sm:px-4">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/receipts" className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/5 text-lg transition hover:bg-white/10" aria-label="Quay lại danh sách">←</Link>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold">{receipt.original_filename}</p>
              <p className="mt-0.5 text-[10px] text-slate-400">Ảnh gốc · {receipt.image_width_px} × {receipt.image_height_px} px</p>
            </div>
          </div>
          <span className={`hidden rounded-full px-2.5 py-1 text-[10px] font-bold sm:inline ${receipt.status === "VERIFIED" ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}`}>
            {receipt.status === "VERIFIED" ? "Đã xác minh bởi người dùng" : `${unresolvedCount} trường chưa giải quyết`}
          </span>
        </div>

        <div className="paper-texture relative min-h-0 flex-1 overflow-auto p-6 sm:p-10">
          <div className="flex min-h-full min-w-full items-start justify-center">
            <div
              className="receipt-edge receipt-shadow relative w-[340px] shrink-0 origin-top bg-[#fffef9] px-8 py-9 font-mono text-[11px] leading-relaxed text-slate-700 transition-transform duration-200 sm:w-[390px] sm:px-10 sm:py-11"
              role="img"
              aria-label={`Bản xem hóa đơn ${String(merchant?.predicted_value ?? "chưa nhận diện")}`}
              style={{ transform: `scale(${zoom / 100}) rotate(${rotation}deg)` }}
            >
              <div className="text-center">
                <p className="font-sans text-base font-black tracking-wide text-slate-900">{merchant?.predicted_value ?? "—"}</p>
                <p className="mx-auto mt-2 max-w-[260px] text-[9px] leading-4 text-slate-500">{address?.predicted_value ?? "—"}</p>
              </div>
              <div className="my-5 border-t border-dashed border-slate-400" />
              <div className="flex justify-between"><span>HÓA ĐƠN BÁN HÀNG</span><span>#{invoiceId?.predicted_value ?? "—"}</span></div>
              <div className="mt-1 flex justify-between"><span>Ngày</span><span>{date?.predicted_value ?? "—"}</span></div>
              <div className="my-5 border-t border-dashed border-slate-400" />
              <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-2">
                <span className="font-bold">Sản phẩm</span><span className="font-bold">SL</span><span className="text-right font-bold">Thành tiền</span>
                <span>Cà phê rang xay</span><span>2</span><span className="text-right">170.000</span>
                <span>Bánh hạnh nhân</span><span>1</span><span className="text-right">85.000</span>
                <span>Nước khoáng</span><span>2</span><span className="text-right">40.000</span>
              </div>
              <div className="my-5 border-t border-dashed border-slate-400" />
              <div className="flex justify-between font-sans text-base font-black text-slate-950"><span>TỔNG CỘNG</span><span>{typeof total?.effective_value === "number" ? `${formatVnd(total.effective_value)} đ` : total?.predicted_value ?? "—"}</span></div>
              <div className="mx-auto my-7 h-11 w-52 bg-[repeating-linear-gradient(90deg,#0f172a_0_1px,transparent_1px_3px,#0f172a_3px_5px,transparent_5px_7px)] opacity-80" />
              <p className="text-center text-[9px] text-slate-500">Cảm ơn quý khách và hẹn gặp lại!</p>
              <div className="pointer-events-none absolute inset-0" aria-hidden="true">
                {receipt.ocr_blocks.map((block) => (
                  <span key={block.block_id} className="absolute border border-cyan-500/70 bg-cyan-300/10" style={getOcrPolygonStyle(block)} />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex h-14 shrink-0 items-center justify-center gap-2 border-t border-white/10 bg-slate-900 px-3 text-white">
          <button type="button" onClick={() => setZoom((value) => Math.max(65, value - 10))} className="grid size-8 place-items-center rounded-lg bg-white/5 text-lg hover:bg-white/10" aria-label="Thu nhỏ">−</button>
          <input type="range" min="65" max="145" step="5" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} className="w-24 accent-teal-400 sm:w-36" aria-label="Mức thu phóng" />
          <button type="button" onClick={() => setZoom((value) => Math.min(145, value + 10))} className="grid size-8 place-items-center rounded-lg bg-white/5 text-lg hover:bg-white/10" aria-label="Phóng to">+</button>
          <span className="w-10 text-center text-[11px] font-bold tabular-nums text-slate-300">{zoom}%</span>
          <span className="mx-1 h-6 w-px bg-white/10" />
          <button type="button" onClick={() => setRotation((value) => value - 90)} className="grid h-8 place-items-center rounded-lg bg-white/5 px-2.5 text-xs font-bold hover:bg-white/10" aria-label="Xoay trái">↶</button>
          <button type="button" onClick={() => setRotation((value) => value + 90)} className="grid h-8 place-items-center rounded-lg bg-white/5 px-2.5 text-xs font-bold hover:bg-white/10" aria-label="Xoay phải">↷</button>
        </div>
      </section>

      <section className="flex min-h-0 flex-1 flex-col bg-white lg:h-full lg:w-[42%]" aria-label="Biểu mẫu kiểm chứng">
        <header className="shrink-0 border-b border-slate-200 px-5 py-4 sm:px-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-teal-700">Bước 2 · Kiểm chứng</p>
          <div className="mt-1.5 flex items-start justify-between gap-4">
            <h1 className="text-xl font-bold tracking-[-0.025em] text-slate-950">Đối chiếu thông tin</h1>
            <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-700">{unresolvedCount}/5 cần xử lý</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">Cảnh báo hiện tại dùng effective_needs_review; confidence chỉ là bằng chứng máy.</p>
        </header>

        <form className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6" onSubmit={(event) => { event.preventDefault(); verify(); }}>
          <div className="space-y-5">
            {orderedFields.map((field) => {
              const draft = drafts[field.field_type]!;
              const style = statusStyles[draft.value_status];
              const isAddress = field.field_type === "merchant_address";
              const commonClass = `w-full rounded-xl border bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition focus:ring-4 disabled:bg-slate-50 disabled:text-slate-500 ${style.border}`;

              return (
                <fieldset key={field.field_id} className="rounded-2xl border border-slate-200 p-3.5">
                  <legend className="px-1 text-sm font-bold text-slate-700">{FIELD_LABELS[field.field_type]}</legend>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-black ring-1 ring-inset ${style.badge}`}>
                      <span className={`size-1.5 rounded-full ${style.dot}`} />
                      {Math.round(field.confidence * 100)}% · {style.label}
                    </span>
                    {field.review_reasons.length > 0 && <span className="text-[10px] font-semibold text-amber-700">{field.review_reasons.map((reason) => reasonLabels[reason]).join(" · ")}</span>}
                  </div>

                  {isAddress ? (
                    <textarea rows={2} value={String(draft.value ?? "")} onChange={(event) => handleChange(field, event)} disabled={!canEdit || draft.value_status !== "PRESENT"} className={`${commonClass} resize-none leading-6`} />
                  ) : (
                    <input
                      type={field.field_type === "receipt_date" ? "date" : field.field_type === "total_amount" ? "number" : "text"}
                      inputMode={field.field_type === "total_amount" ? "numeric" : undefined}
                      min={field.field_type === "total_amount" ? 0 : undefined}
                      value={draft.value ?? ""}
                      onChange={(event) => handleChange(field, event)}
                      disabled={!canEdit || draft.value_status !== "PRESENT"}
                      className={`${commonClass} h-12`}
                    />
                  )}

                  {field.predicted_value !== null && !valuesEqual(field.predicted_value, field.effective_value) && (
                    <p className="mt-2 text-[11px] leading-4 text-slate-500">KIE dự đoán: <span className="font-semibold text-slate-700">{field.predicted_value}</span>. Giá trị này không tự động trở thành effective value.</p>
                  )}

                  {canEdit && (
                    <div className="mt-2 flex items-center gap-2">
                      <select value={draft.value_status} onChange={(event) => handleStatus(field.field_type, event.target.value as ValueStatus)} className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700">
                        {draft.value_status === "AMBIGUOUS" && <option value="AMBIGUOUS" disabled>Mơ hồ – cần quyết định</option>}
                        {draft.value_status === "UNKNOWN" && <option value="UNKNOWN" disabled>Chưa xác định – cần quyết định</option>}
                        <option value="PRESENT">Có giá trị</option>
                        <option value="NOT_PRESENT">Không có trên hóa đơn</option>
                        <option value="UNREADABLE">Có nhưng không đọc được</option>
                      </select>
                      {!draft.resolved && draft.value_status === "PRESENT" && draft.value !== null && (
                        <button type="button" onClick={() => updateDraft(field.field_type, { resolved: true })} className="h-9 rounded-lg bg-teal-50 px-3 text-xs font-bold text-teal-800">Giữ giá trị này</button>
                      )}
                    </div>
                  )}
                </fieldset>
              );
            })}
          </div>
        </form>

        <footer className="shrink-0 border-t border-slate-200 bg-white p-4 sm:px-6">
          <div className="flex gap-3">
            <button type="button" onClick={() => router.push("/receipts")} className="h-11 flex-1 rounded-xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50">Quay lại</button>
            <button type="button" onClick={verify} disabled={!canEdit || unresolvedCount > 0} className="h-11 flex-[1.8] rounded-xl bg-teal-800 px-4 text-sm font-bold text-white shadow-sm transition hover:bg-teal-900 disabled:cursor-not-allowed disabled:opacity-45">
              {receipt.status === "VERIFIED" ? "Đã xác minh" : unresolvedCount > 0 ? `Còn ${unresolvedCount} trường` : "Xác minh & Lưu"}
            </button>
          </div>
        </footer>
      </section>

      <div role="status" aria-live="polite" className={`pointer-events-none fixed bottom-20 right-5 z-[60] max-w-sm rounded-xl px-4 py-3 text-sm font-bold text-white shadow-2xl transition-all duration-300 lg:bottom-5 ${notice ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"} ${notice?.tone === "error" ? "bg-red-700" : "bg-slate-950"}`}>
        {notice?.message ?? ""}
      </div>
    </div>
  );
}
