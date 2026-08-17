"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { StatusBadge } from "../../../components/status-badge";
import {
  OptimisticConcurrencyError,
  createApplyCorrectionRequest,
  createClearCorrectionRequest,
  createVerifyRequest,
  getApiErrorMessage,
} from "../../../lib/vietreceipt-api";
import {
  canVerifyReceipt,
  createFieldInteractionState,
  getAdjacentField,
  getReceiptStatePresentation,
  parseCorrectionInput,
  reduceFieldInteraction,
  replaceReceiptField,
  type FieldInteractionAction,
  type FieldInteractionState,
} from "../../../lib/receipt-workflow";
import {
  createReviewTelemetryEvent,
  emitReviewTelemetry,
} from "../../../lib/review-telemetry";
import { useReceiptWorkflow } from "../../../lib/use-receipt-workflow";
import {
  CORE_FIELD_TYPES,
  FIELD_LABELS,
  VALUE_STATUSES,
  findFieldForSourceBlock,
  type FieldType,
  type OcrBlock,
  type ReceiptDetail,
  type ReceiptField,
  type ReviewReasonCode,
  type ValueStatus,
} from "../../../types/receipt";

type FieldStates = Partial<Record<FieldType, FieldInteractionState>>;

const statusLabels: Record<ValueStatus, string> = {
  PRESENT: "Có dữ liệu",
  NOT_PRESENT: "Không có trên hóa đơn",
  UNREADABLE: "Không đọc được",
  AMBIGUOUS: "Mơ hồ",
  UNKNOWN: "Chưa xác định",
};

const reasonLabels: Record<ReviewReasonCode, string> = {
  NO_CANDIDATE: "Không tìm thấy ứng viên",
  LOW_CONFIDENCE: "Độ tin cậy thấp",
  MULTIPLE_CANDIDATES: "Có nhiều ứng viên",
  AMBIGUOUS_FORMAT: "Định dạng mơ hồ",
  UNREADABLE_SOURCE: "Nguồn không đọc được",
  UNSUPPORTED_CURRENCY: "Đơn vị tiền chưa hỗ trợ",
  NEGATIVE_AMOUNT: "Số tiền âm",
  MISSING_DATE_COMPONENT: "Ngày thiếu thành phần",
  UNSUPPORTED_TWO_DIGIT_YEAR: "Năm hai chữ số chưa hỗ trợ",
  SOURCE_ROLE_UNCLEAR: "Vai trò nguồn chưa rõ",
  NORMALIZATION_FAILED: "Không chuẩn hóa an toàn",
};

function createStates(receipt: ReceiptDetail): FieldStates {
  if (!receipt.fields) return {};
  return Object.fromEntries(
    CORE_FIELD_TYPES.map((fieldName) => [
      fieldName,
      createFieldInteractionState(receipt.fields![fieldName]),
    ]),
  );
}

function formatValue(field: ReceiptField, value = field.effective_value) {
  if (value === null) return "—";
  if (field.field_name === "total_amount" && typeof value === "number") {
    return `${new Intl.NumberFormat("vi-VN").format(value)} VND`;
  }
  return String(value);
}

function polygonPoints(block: OcrBlock) {
  return block.polygon.map((point) => `${point.x},${point.y}`).join(" ");
}

function blockHitArea(block: OcrBlock): CSSProperties {
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
  const receiptId = params.id;
  const {
    receipt,
    initialLoading,
    polling,
    error,
    pollingError,
    api,
    reload,
    replaceReceipt,
    updateReceipt,
  } = useReceiptWorkflow(receiptId);
  const [fieldStateStore, setFieldStateStore] = useState<{
    receiptId: string;
    states: FieldStates;
  }>({ receiptId, states: {} });
  const [activeFieldType, setActiveFieldType] = useState<FieldType>("total_amount");
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [verifying, setVerifying] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [staleState, setStaleState] = useState<{ receiptId: string; message: string } | null>(null);
  const [noticeState, setNoticeState] = useState<{ receiptId: string; tone: "success" | "error"; message: string } | null>(null);
  const fieldRefs = useRef<Partial<Record<FieldType, HTMLInputElement | HTMLTextAreaElement | null>>>({});
  const reviewStartedRef = useRef<string | null>(null);
  const previousReceiptRef = useRef<string | null>(null);

  const fieldStates = fieldStateStore.receiptId === receiptId
    ? fieldStateStore.states
    : {};
  const staleMessage = staleState?.receiptId === receiptId ? staleState.message : null;
  const notice = noticeState?.receiptId === receiptId ? noticeState : null;

  function setFieldStates(next: FieldStates | ((current: FieldStates) => FieldStates)) {
    setFieldStateStore((current) => {
      const currentStates = current.receiptId === receiptId ? current.states : {};
      return {
        receiptId,
        states: typeof next === "function" ? next(currentStates) : next,
      };
    });
  }

  function setStaleMessage(message: string | null) {
    setStaleState(message ? { receiptId, message } : null);
  }

  function setNotice(next: { tone: "success" | "error"; message: string } | null) {
    setNoticeState(next ? { receiptId, ...next } : null);
  }

  useEffect(() => {
    if (!receipt) return;
    if (previousReceiptRef.current && previousReceiptRef.current !== receipt.receipt_id) {
      emitReviewTelemetry(createReviewTelemetryEvent("RECEIPT_CHANGED", receipt.receipt_id));
    }
    previousReceiptRef.current = receipt.receipt_id;
    if (
      receipt.status === "NEEDS_REVIEW" &&
      reviewStartedRef.current !== receipt.receipt_id
    ) {
      reviewStartedRef.current = receipt.receipt_id;
      emitReviewTelemetry(createReviewTelemetryEvent("REVIEW_STARTED", receipt.receipt_id));
    }
  }, [receipt]);

  const orderedFields = useMemo(
    () => receipt?.fields
      ? CORE_FIELD_TYPES.map((fieldName) => receipt.fields![fieldName])
      : [],
    [receipt],
  );

  function dispatchField(fieldName: FieldType, action: FieldInteractionAction) {
    setFieldStates((current) => {
      const existing = current[fieldName] ?? (
        receipt?.fields ? createFieldInteractionState(receipt.fields[fieldName]) : undefined
      );
      if (!existing) return current;
      return { ...current, [fieldName]: reduceFieldInteraction(existing, action) };
    });
  }

  function activateField(fieldName: FieldType) {
    if (activeFieldType !== fieldName && receipt) {
      emitReviewTelemetry(
        createReviewTelemetryEvent("FIELD_FOCUSED", receipt.receipt_id, { field_name: fieldName }),
      );
    }
    setActiveFieldType(fieldName);
  }

  function editField(field: ReceiptField, rawValue: string) {
    const value = parseCorrectionInput(field.field_name, rawValue);
    dispatchField(field.field_name, {
      type: "EDIT",
      value,
      valueStatus: value === null ? "UNKNOWN" : "PRESENT",
    });
    if (receipt) {
      emitReviewTelemetry(
        createReviewTelemetryEvent("FIELD_EDITED", receipt.receipt_id, { field_name: field.field_name }),
      );
    }
  }

  function editStatus(fieldName: FieldType, valueStatus: ValueStatus) {
    const state = fieldStates[fieldName];
    if (!state) return;
    dispatchField(fieldName, {
      type: "EDIT",
      value: valueStatus === "PRESENT" ? state.value : null,
      valueStatus,
    });
  }

  async function refreshAuthoritativeReceipt() {
    const latest = await reload();
    setFieldStates(createStates(latest));
    setStaleMessage(null);
    return latest;
  }

  async function applyCorrection(field: ReceiptField) {
    const state = fieldStates[field.field_name];
    if (!receipt || !state || state.phase === "SAVING") return;
    dispatchField(field.field_name, { type: "SAVE" });
    setNotice(null);
    try {
      const request = createApplyCorrectionRequest(field, state.value, state.valueStatus);
      const savedField = await api.applyCorrection(
        receipt.receipt_id,
        field.field_name,
        request,
      );
      updateReceipt((current) => replaceReceiptField(current, savedField));
      dispatchField(field.field_name, { type: "SAVED", field: savedField });
      emitReviewTelemetry(
        createReviewTelemetryEvent("CORRECTION_APPLIED", receipt.receipt_id, {
          field_name: field.field_name,
          operation: "APPLY",
        }),
      );
      try {
        await refreshAuthoritativeReceipt();
      } catch (reloadError) {
        setStaleMessage("Correction đã được Backend lưu nhưng chưa lấy được receipt.updated_at mới. Hãy tải phiên bản mới trước khi verify.");
        setNotice({ tone: "error", message: getApiErrorMessage(reloadError) });
        return;
      }
      setNotice({ tone: "success", message: `${FIELD_LABELS[field.field_name]} đã được lưu theo response Backend.` });
    } catch (caught) {
      const message = getApiErrorMessage(caught);
      dispatchField(field.field_name, caught instanceof OptimisticConcurrencyError
        ? { type: "STALE", message }
        : { type: "SAVE_ERROR", message });
      if (caught instanceof OptimisticConcurrencyError) setStaleMessage(message);
    }
  }

  async function clearCorrection(field: ReceiptField) {
    if (!receipt || fieldStates[field.field_name]?.phase === "SAVING") return;
    dispatchField(field.field_name, { type: "SAVE" });
    setNotice(null);
    try {
      const savedField = await api.clearCorrection(
        receipt.receipt_id,
        field.field_name,
        createClearCorrectionRequest(field),
      );
      updateReceipt((current) => replaceReceiptField(current, savedField));
      dispatchField(field.field_name, { type: "SAVED", field: savedField });
      emitReviewTelemetry(
        createReviewTelemetryEvent("CORRECTION_CLEARED", receipt.receipt_id, {
          field_name: field.field_name,
          operation: "CLEAR",
        }),
      );
      try {
        await refreshAuthoritativeReceipt();
      } catch (reloadError) {
        setStaleMessage("CLEAR đã được Backend lưu nhưng chưa lấy được receipt.updated_at mới. Hãy tải phiên bản mới trước khi verify.");
        setNotice({ tone: "error", message: getApiErrorMessage(reloadError) });
        return;
      }
      setNotice({ tone: "success", message: "Đã CLEAR correction; effective value được lấy lại từ response Backend." });
    } catch (caught) {
      const message = getApiErrorMessage(caught);
      dispatchField(field.field_name, caught instanceof OptimisticConcurrencyError
        ? { type: "STALE", message }
        : { type: "SAVE_ERROR", message });
      if (caught instanceof OptimisticConcurrencyError) setStaleMessage(message);
    }
  }

  async function verifyReceipt() {
    if (!receipt || verifying || !canVerifyReceipt(receipt)) return;
    setVerifying(true);
    setNotice(null);
    try {
      const verified = await api.verifyReceipt(
        receipt.receipt_id,
        createVerifyRequest(receipt),
      );
      replaceReceipt(verified);
      setFieldStates(createStates(verified));
      emitReviewTelemetry(createReviewTelemetryEvent("RECEIPT_VERIFIED", receipt.receipt_id));
      setNotice({ tone: "success", message: "Hóa đơn đã được Backend xác minh và chuyển sang read-only." });
    } catch (caught) {
      const message = getApiErrorMessage(caught);
      if (caught instanceof OptimisticConcurrencyError) setStaleMessage(message);
      setNotice({ tone: "error", message });
    } finally {
      setVerifying(false);
    }
  }

  async function retryReceipt() {
    if (!receipt || retrying) return;
    setRetrying(true);
    setNotice(null);
    try {
      await api.retryReceipt(receipt.receipt_id);
      emitReviewTelemetry(createReviewTelemetryEvent("RECEIPT_RETRIED", receipt.receipt_id));
      await refreshAuthoritativeReceipt();
      setNotice({ tone: "success", message: "Backend đã chấp nhận yêu cầu retry. Trạng thái mới được tải lại từ Backend." });
    } catch (caught) {
      setNotice({ tone: "error", message: getApiErrorMessage(caught) });
    } finally {
      setRetrying(false);
    }
  }

  function handleFieldKeys(event: KeyboardEvent<HTMLElement>, field: ReceiptField) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      void applyCorrection(field);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      dispatchField(field.field_name, { type: "RESET", field });
      return;
    }
    if (event.altKey && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      const next = getAdjacentField(field.field_name, event.key === "ArrowDown" ? 1 : -1);
      activateField(next);
      fieldRefs.current[next]?.focus();
    }
  }

  if (initialLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12" aria-label="Đang tải hóa đơn">
        <div className="h-9 w-64 animate-pulse rounded-xl bg-slate-200" />
        <div className="mt-6 h-[520px] animate-pulse rounded-3xl bg-slate-200" />
      </div>
    );
  }

  if (error || !receipt) {
    return (
      <div className="grid min-h-[calc(100dvh-56px)] place-items-center px-4 text-center">
        <div className="max-w-lg rounded-3xl border border-red-200 bg-white p-8 shadow-sm">
          <p className="text-4xl">!</p>
          <h1 className="mt-3 text-2xl font-bold text-slate-900">Không thể tải hóa đơn</h1>
          <p role="alert" className="mt-3 text-sm leading-6 text-red-700">{error ?? "Không có dữ liệu."}</p>
          <div className="mt-5 flex justify-center gap-3">
            <Link href="/receipts" className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold">Quay lại</Link>
            <button type="button" onClick={() => void reload().catch(() => undefined)} className="rounded-xl bg-teal-800 px-4 py-2 text-sm font-bold text-white">Tải lại</button>
          </div>
        </div>
      </div>
    );
  }

  const presentation = getReceiptStatePresentation(receipt.status, receipt.processing_stage ?? null);

  if (!receipt.fields) {
    const canRetry = receipt.status === "FAILED" && receipt.processing_error?.retryable === true;
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <Link href="/receipts" className="text-sm font-bold text-teal-700">← Quay lại danh sách</Link>
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <StatusBadge status={receipt.status} />
            {polling && <span className="text-xs font-semibold text-sky-700">Đang theo dõi trạng thái...</span>}
          </div>
          <h1 className="mt-5 text-2xl font-bold text-slate-950">{receipt.original_filename}</h1>
          <h2 className="mt-7 text-lg font-bold text-slate-900">{presentation.title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{presentation.description}</p>

          {receipt.status === "PROCESSING" && (
            <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100" aria-label="Đang xử lý, Backend chưa cung cấp phần trăm">
              <div className="h-full w-1/3 animate-[upload_1.2s_ease-in-out_infinite] rounded-full bg-sky-500" />
            </div>
          )}

          {receipt.processing_error && (
            <dl className="mt-6 grid gap-3 rounded-2xl bg-red-50 p-5 text-sm sm:grid-cols-2">
              <div><dt className="font-bold text-red-900">Giai đoạn</dt><dd className="mt-1 text-red-700">{receipt.processing_error.stage}</dd></div>
              <div><dt className="font-bold text-red-900">Mã lỗi</dt><dd className="mt-1 text-red-700">{receipt.processing_error.code}</dd></div>
              <div className="sm:col-span-2"><dt className="font-bold text-red-900">Thông báo</dt><dd className="mt-1 text-red-700">{receipt.processing_error.message}</dd></div>
            </dl>
          )}

          {pollingError && (
            <p role="status" className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
              Polling tạm lỗi: {pollingError} <button type="button" onClick={() => void reload().catch(() => undefined)} className="font-bold underline">Tải ngay</button>
            </p>
          )}
          {notice && <p role="status" className={`mt-4 rounded-xl p-3 text-sm font-semibold ${notice.tone === "success" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>{notice.message}</p>}

          {canRetry && (
            <button type="button" disabled={retrying} onClick={() => void retryReceipt()} className="mt-6 rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white disabled:bg-slate-300">
              {retrying ? "Đang gửi yêu cầu..." : "Thử xử lý lại"}
            </button>
          )}
          {receipt.status === "FAILED" && !canRetry && (
            <p className="mt-5 text-sm font-semibold text-slate-500">Backend đánh dấu lỗi này không thể retry.</p>
          )}
        </section>
      </div>
    );
  }

  const fields = receipt.fields;
  const canEdit = receipt.status === "NEEDS_REVIEW";
  const activeField = fields[activeFieldType];
  const activeSourceIds = new Set(activeField.machine.source_block_ids);
  const unresolvedCount = orderedFields.filter((field) => field.effective_needs_review).length;
  const mutationInProgress = Object.values(fieldStates).some((state) => state?.phase === "SAVING");
  const verifyEnabled = canVerifyReceipt(receipt) && !mutationInProgress && !staleMessage;

  return (
    <div className="relative flex min-h-[calc(100dvh-56px)] flex-col bg-slate-100 lg:h-[calc(100dvh-56px)] lg:min-h-0 lg:flex-row lg:overflow-hidden">
      <section className="flex min-h-[540px] flex-col border-b border-slate-300 bg-slate-800 lg:h-full lg:min-h-0 lg:w-[56%] lg:border-b-0 lg:border-r" aria-label="Ảnh hóa đơn gốc và vùng OCR">
        <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/10 bg-slate-900/90 px-4 text-white">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/receipts" className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/5 hover:bg-white/10" aria-label="Quay lại danh sách">←</Link>
            <div className="min-w-0"><p className="truncate text-xs font-bold">{receipt.original_filename}</p><p className="mt-0.5 text-[10px] text-slate-400">Evidence do Backend/OCR trả về · {receipt.image_width_px} × {receipt.image_height_px} px</p></div>
          </div>
          <StatusBadge status={receipt.status} />
        </div>

        <div className="relative min-h-0 flex-1 overflow-auto p-6 sm:p-10">
          <div className="flex min-h-full min-w-full items-start justify-center">
            {receipt.image_url ? (
              <div className="relative w-full max-w-[620px] shrink-0 origin-top transition-transform duration-200" style={{ transform: `scale(${zoom / 100}) rotate(${rotation}deg)` }}>
                {/* Authenticated/short-lived URLs are runtime data and cannot be enumerated in next/image remotePatterns. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={receipt.image_url} alt={`Ảnh hóa đơn gốc ${receipt.original_filename}`} width={receipt.image_width_px} height={receipt.image_height_px} className="h-auto w-full rounded-sm bg-white shadow-2xl" />
                <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-label="Các polygon OCR">
                  {(receipt.ocr_blocks ?? []).map((block) => {
                    const isActive = activeSourceIds.has(block.block_id);
                    const fieldName = findFieldForSourceBlock(fields, block.block_id);
                    return (
                      <polygon
                        key={block.block_id}
                        points={polygonPoints(block)}
                        vectorEffect="non-scaling-stroke"
                        className="pointer-events-none"
                        fill={isActive ? "rgba(45,212,191,.32)" : fieldName ? "rgba(251,191,36,.08)" : "transparent"}
                        stroke={isActive ? "#2dd4bf" : fieldName ? "rgba(252,211,77,.7)" : "transparent"}
                        strokeWidth={isActive ? 3 : 2}
                      />
                    );
                  })}
                </svg>
                <div className="absolute inset-0">
                  {(receipt.ocr_blocks ?? []).map((block) => {
                    const fieldName = findFieldForSourceBlock(fields, block.block_id);
                    if (!fieldName) return null;
                    return (
                      <button
                        key={block.block_id}
                        type="button"
                        style={blockHitArea(block)}
                        onClick={() => activateField(fieldName)}
                        className="absolute z-10 bg-transparent outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
                        aria-label={`Bằng chứng OCR cho ${FIELD_LABELS[fieldName]}: ${block.text}`}
                      />
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-600 p-8 text-center text-sm text-slate-300">Backend chưa cung cấp image_url. Frontend không dựng lại ảnh từ OCR/KIE.</div>
            )}
          </div>
        </div>
        <div className="flex h-12 shrink-0 items-center justify-center gap-2 border-t border-white/10 bg-slate-900/90 px-3 text-white">
          <button type="button" onClick={() => setZoom((value) => Math.max(70, value - 10))} className="grid size-8 place-items-center rounded-lg bg-white/5" aria-label="Thu nhỏ">−</button>
          <span className="w-12 text-center text-[11px] font-bold">{zoom}%</span>
          <button type="button" onClick={() => setZoom((value) => Math.min(160, value + 10))} className="grid size-8 place-items-center rounded-lg bg-white/5" aria-label="Phóng to">+</button>
          <button type="button" onClick={() => setRotation((value) => (value + 90) % 360)} className="ml-2 rounded-lg bg-white/5 px-3 py-2 text-[11px] font-bold">Xoay 90°</button>
        </div>
      </section>

      <section className="flex min-h-0 flex-1 flex-col bg-white lg:h-full">
        <header className="shrink-0 border-b border-slate-200 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-teal-700">Human-in-the-Loop</p><h1 className="mt-1 text-xl font-bold tracking-tight text-slate-950">{presentation.title}</h1></div>
            {receipt.status === "VERIFIED" && receipt.verified_at && <span className="text-right text-[10px] font-semibold text-emerald-700">Read-only<br />{new Date(receipt.verified_at).toLocaleString("vi-VN")}</span>}
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{presentation.description}</p>
        </header>

        <div className="min-h-0 flex-1 overflow-auto px-4 py-4 sm:px-5">
          {staleMessage && (
            <div role="alert" className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-bold">Dữ liệu hóa đơn đã được cập nhật ở nơi khác.</p>
              <p className="mt-1">{staleMessage}</p>
              <button type="button" onClick={() => void refreshAuthoritativeReceipt().catch((caught) => setNotice({ tone: "error", message: getApiErrorMessage(caught) }))} className="mt-3 rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white">Tải phiên bản mới</button>
            </div>
          )}

          <div className="space-y-3">
            {orderedFields.map((field) => {
              const state = fieldStates[field.field_name] ?? createFieldInteractionState(field);
              const isActive = activeFieldType === field.field_name;
              const isSaving = state.phase === "SAVING";
              const machineValue = field.machine.normalized_value;
              return (
                <fieldset
                  key={field.field_name}
                  onFocus={() => activateField(field.field_name)}
                  className={`rounded-2xl border p-3.5 transition ${isActive ? "border-teal-400 bg-teal-50/40 ring-2 ring-teal-500/10" : "border-slate-200"}`}
                >
                  <legend className="px-1 text-sm font-bold text-slate-700">{FIELD_LABELS[field.field_name]}</legend>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{statusLabels[field.machine.value_status]} · {state.phase}</span>
                    {field.effective_needs_review && <span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-800">Cần kiểm tra</span>}
                  </div>

                  {field.field_name === "merchant_address" ? (
                    <textarea ref={(element) => { fieldRefs.current[field.field_name] = element; }} value={state.value === null ? "" : String(state.value)} onChange={(event) => editField(field, event.target.value)} onKeyDown={(event) => handleFieldKeys(event, field)} disabled={!canEdit || isSaving} rows={2} className="w-full resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold outline-none focus:border-teal-600 disabled:bg-slate-50" />
                  ) : (
                    <input
                      ref={(element) => { fieldRefs.current[field.field_name] = element; }}
                      type={field.field_name === "receipt_date" ? "date" : "text"}
                      inputMode={field.field_name === "total_amount" ? "numeric" : undefined}
                      value={state.value === null ? "" : String(state.value)}
                      onChange={(event: ChangeEvent<HTMLInputElement>) => editField(field, event.target.value)}
                      onKeyDown={(event) => handleFieldKeys(event, field)}
                      disabled={!canEdit || isSaving}
                      className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm font-semibold outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10 disabled:bg-slate-50"
                    />
                  )}

                  <dl className="mt-3 grid gap-1.5 rounded-xl bg-slate-50 p-3 text-[11px] leading-4">
                    <div className="flex gap-2"><dt className="w-28 shrink-0 font-bold text-slate-500">Machine normalized</dt><dd className="font-semibold text-slate-800">{formatValue(field, machineValue)}</dd></div>
                    <div className="flex gap-2"><dt className="w-28 shrink-0 font-bold text-slate-500">Human corrected</dt><dd className="font-semibold text-slate-800">{field.has_correction ? formatValue(field, field.corrected_value) : "Chưa có"}</dd></div>
                    <div className="flex gap-2"><dt className="w-28 shrink-0 font-bold text-teal-700">Effective</dt><dd className="font-bold text-teal-900">{formatValue(field)}</dd></div>
                    <div className="flex gap-2"><dt className="w-28 shrink-0 font-bold text-slate-500">OCR raw</dt><dd className="font-semibold text-slate-700">{field.machine.raw_text ?? "—"}</dd></div>
                  </dl>

                  {field.machine.review_reasons.length > 0 && <p className="mt-2 text-[10px] font-semibold text-amber-700">{field.machine.review_reasons.map((reason) => reasonLabels[reason]).join(" · ")}</p>}
                  <p className="mt-2 text-[10px] text-teal-700">Nguồn ({field.machine.source_block_ids.length} block): {field.machine.source_block_ids.join(", ")}</p>

                  {state.error && <p role="alert" className="mt-2 rounded-lg bg-red-50 p-2 text-xs font-semibold text-red-700">{state.error}</p>}

                  {canEdit && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <select value={state.valueStatus} disabled={isSaving} onChange={(event) => editStatus(field.field_name, event.target.value as ValueStatus)} className="h-9 min-w-40 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700">
                        {VALUE_STATUSES.map((valueStatus) => <option key={valueStatus} value={valueStatus}>{statusLabels[valueStatus]}</option>)}
                      </select>
                      <button type="button" disabled={isSaving} onClick={() => void applyCorrection(field)} className="h-9 rounded-lg bg-teal-800 px-3 text-xs font-bold text-white disabled:bg-slate-300">{isSaving ? "Đang lưu..." : field.effective_needs_review && state.phase === "VIEW" ? "Xác nhận bằng APPLY" : "Lưu APPLY"}</button>
                      {field.has_correction && <button type="button" disabled={isSaving} onClick={() => void clearCorrection(field)} className="h-9 rounded-lg bg-slate-100 px-3 text-xs font-bold text-slate-700 disabled:opacity-50">CLEAR</button>}
                    </div>
                  )}
                  {canEdit && <p className="mt-2 text-[10px] text-slate-400">Ctrl/⌘ + Enter: lưu · Esc: hoàn tác draft · Alt + ↑/↓: chuyển field</p>}
                </fieldset>
              );
            })}
          </div>

          <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">Warning hiện tại dùng <code>effective_needs_review</code>. Confidence chỉ hiển thị provenance; Frontend không auto-verify, không ẩn field và không selective-skip.</p>
        </div>

        <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-5">
          {notice && <p role="status" className={`mb-3 rounded-xl px-3 py-2 text-xs font-semibold ${notice.tone === "success" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>{notice.message}</p>}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">{receipt.status === "VERIFIED" ? "Đã xác minh · chỉ đọc" : unresolvedCount > 0 ? `${unresolvedCount} trường cần xác nhận` : "Tất cả trường đã được giải quyết"}</p>
            <button type="button" onClick={() => void verifyReceipt()} disabled={!verifyEnabled || verifying || receipt.status === "VERIFIED"} className="h-10 rounded-xl bg-teal-800 px-5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300">{verifying ? "Đang xác minh..." : "Xác nhận hóa đơn"}</button>
          </div>
        </footer>
      </section>
    </div>
  );
}
