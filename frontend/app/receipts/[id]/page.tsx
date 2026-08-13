"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  type ChangeEvent,
  type CSSProperties,
  useMemo,
  useState,
} from "react";
import { getReceiptById } from "../../../data/mock-receipts";
import {
  createApplyCorrectionRequest,
  createClearCorrectionRequest,
  createVerifyRequest,
} from "../../../lib/vietreceipt-api";
import {
  CORE_FIELD_TYPES,
  FIELD_LABELS,
  VALUE_STATUSES,
  findFieldForSourceBlock,
  getExtractedField,
  type FieldCorrectionRequest,
  type FieldType,
  type FieldValue,
  type OcrBlock,
  type ReceiptField,
  type ReviewReasonCode,
  type ValueStatus,
} from "../../../types/receipt";

interface FieldDraft {
  value: FieldValue;
  value_status: ValueStatus;
  resolved: boolean;
  operation: "APPLY" | "CLEAR" | null;
}

type FieldDrafts = Partial<Record<FieldType, FieldDraft>>;

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
  const receipt = getReceiptById(params.id);
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [activeFieldType, setActiveFieldType] =
    useState<FieldType>("total_amount");
  const [notice, setNotice] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);

  const orderedFields = useMemo(() => {
    if (!receipt?.fields) return [];
    return CORE_FIELD_TYPES.map((fieldType) => receipt.fields![fieldType]);
  }, [receipt]);

  const initialDrafts = useMemo<FieldDrafts>(
    () =>
      Object.fromEntries(
        orderedFields.map((field) => [
          field.field_name,
          {
            value: field.effective_value,
            value_status: field.effective_status,
            resolved: !field.effective_needs_review,
            operation: null,
          },
        ]),
      ),
    [orderedFields],
  );

  const [drafts, setDrafts] = useState<FieldDrafts>(initialDrafts);

  if (!receipt) {
    return (
      <div className="grid min-h-[calc(100dvh-56px)] place-items-center px-4 text-center">
        <div>
          <p className="text-5xl">404</p>
          <h1 className="mt-4 text-2xl font-bold text-slate-900">
            Không tìm thấy hóa đơn
          </h1>
          <Link
            href="/receipts"
            className="mt-5 inline-flex rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white"
          >
            Quay lại danh sách
          </Link>
        </div>
      </div>
    );
  }

  if (!receipt.fields) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <Link href="/receipts" className="text-sm font-bold text-teal-700">
          ← Quay lại danh sách
        </Link>
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
            {receipt.status}
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-950">
            {receipt.original_filename}
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {receipt.status === "UPLOADED" &&
              "Backend đã nhận ảnh và tự kích hoạt OCR/KIE; contract không public endpoint /process."}
            {receipt.status === "PROCESSING" &&
              "Backend đang xử lý OCR/KIE. Field projection chỉ xuất hiện sau khi KIE hoàn tất."}
            {receipt.status === "FAILED" &&
              (receipt.processing_error?.message ??
                "Pipeline đã dừng do lỗi xử lý.")}
          </p>
          {receipt.processing_error && (
            <p className="mt-5 rounded-2xl bg-red-50 p-4 text-sm font-semibold text-red-800">
              {receipt.processing_error.code}: {receipt.processing_error.message}
            </p>
          )}
        </section>
      </div>
    );
  }

  const currentReceipt = receipt;
  const fields = currentReceipt.fields!;
  const canEdit = receipt.status === "NEEDS_REVIEW";
  const unresolvedCount = orderedFields.filter(
    (field) => !drafts[field.field_name]?.resolved,
  ).length;
  const activeField = getExtractedField(receipt, activeFieldType);
  const activeSourceIds = new Set(activeField?.machine.source_block_ids ?? []);

  function updateDraft(fieldType: FieldType, next: Partial<FieldDraft>) {
    setDrafts((current) => ({
      ...current,
      [fieldType]: { ...current[fieldType]!, ...next },
    }));
    setNotice(null);
  }

  function handleChange(
    field: ReceiptField,
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const rawValue = event.target.value;
    const value =
      field.field_name === "total_amount"
        ? rawValue === ""
          ? null
          : Number(rawValue)
        : rawValue === ""
          ? null
          : rawValue;

    updateDraft(field.field_name, {
      value,
      value_status: value === null ? "UNKNOWN" : "PRESENT",
      resolved: value !== null,
      operation: "APPLY",
    });
  }

  function handleStatus(fieldType: FieldType, valueStatus: ValueStatus) {
    const current = drafts[fieldType]!;
    const value = valueStatus === "PRESENT" ? current.value : null;
    updateDraft(fieldType, {
      value,
      value_status: valueStatus,
      resolved:
        valueStatus === "NOT_PRESENT" ||
        valueStatus === "UNREADABLE" ||
        (valueStatus === "PRESENT" && value !== null),
      operation: "APPLY",
    });
  }

  function keepEffectiveValue(field: ReceiptField) {
    const draft = drafts[field.field_name]!;
    updateDraft(field.field_name, {
      resolved: true,
      operation: "APPLY",
      value: draft.value,
      value_status: draft.value_status,
    });
  }

  function clearCorrection(field: ReceiptField) {
    updateDraft(field.field_name, {
      value: field.machine.normalized_value,
      value_status: field.machine.value_status,
      resolved: !field.machine.machine_needs_review,
      operation: "CLEAR",
    });
  }

  function activateBlock(block: OcrBlock) {
    const fieldType = findFieldForSourceBlock(fields, block.block_id);
    if (fieldType) setActiveFieldType(fieldType);
  }

  function verify() {
    if (unresolvedCount > 0) {
      setNotice({
        tone: "error",
        message: `Còn ${unresolvedCount} trường chưa được giải quyết.`,
      });
      return;
    }

    const corrections = orderedFields.reduce<FieldCorrectionRequest[]>(
      (requests, field) => {
        const draft = drafts[field.field_name]!;
        if (draft.operation === "CLEAR") {
          requests.push(createClearCorrectionRequest(field));
          return requests;
        }

        const changed =
          draft.operation === "APPLY" ||
          draft.value_status !== field.effective_status ||
          !valuesEqual(draft.value, field.effective_value);

        if (changed) {
          requests.push(
            createApplyCorrectionRequest(
              field,
              draft.value,
              draft.value_status,
            ),
          );
        }
        return requests;
      },
      [],
    );
    const verifyRequest = createVerifyRequest(currentReceipt);
    const applyCount = corrections.filter(
      (request) => request.operation === "APPLY",
    ).length;
    const clearCount = corrections.filter(
      (request) => request.operation === "CLEAR",
    ).length;

    setNotice({
      tone: "success",
      message: `Đã chuẩn bị ${applyCount} APPLY, ${clearCount} CLEAR và verify với token ${verifyRequest.expected_updated_at}.`,
    });
  }

  return (
    <div className="relative flex min-h-[calc(100dvh-56px)] flex-col bg-slate-100 lg:h-[calc(100dvh-56px)] lg:min-h-0 lg:flex-row lg:overflow-hidden">
      <section
        className="flex min-h-[540px] flex-col border-b border-slate-300 bg-slate-800 lg:h-full lg:min-h-0 lg:w-[58%] lg:border-b-0 lg:border-r"
        aria-label="Ảnh hóa đơn gốc và vùng OCR"
      >
        <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/10 bg-slate-900/90 px-3 text-white sm:px-4">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/receipts"
              className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/5 text-lg hover:bg-white/10"
              aria-label="Quay lại danh sách"
            >
              ←
            </Link>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold">
                {receipt.original_filename}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-400">
                Ảnh fixture thật từ OCR W1 · {receipt.image_width_px} × {receipt.image_height_px} px
              </p>
            </div>
          </div>
          <span className="hidden rounded-full bg-amber-400/10 px-2.5 py-1 text-[10px] font-bold text-amber-300 sm:inline">
            {unresolvedCount} trường chưa giải quyết
          </span>
        </div>

        <div className="relative min-h-0 flex-1 overflow-auto p-6 sm:p-10">
          <div className="flex min-h-full min-w-full items-start justify-center">
            {receipt.image_url ? (
              <div
                className="relative w-full max-w-[465px] shrink-0 origin-top transition-transform duration-200"
                style={{
                  transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
                }}
              >
                <Image
                  src={receipt.image_url}
                  alt="Ảnh hóa đơn gốc MINIMART ANAN từ bộ fixture OCR tuần 1"
                  width={receipt.image_width_px ?? 465}
                  height={receipt.image_height_px ?? 564}
                  className="h-auto w-full rounded-sm bg-white shadow-2xl"
                  priority
                  unoptimized
                />
                {(receipt.ocr_blocks ?? []).map((block) => {
                  const isActive = activeSourceIds.has(block.block_id);
                  const hasField = Boolean(
                    findFieldForSourceBlock(fields, block.block_id),
                  );
                  return (
                    <button
                      key={block.block_id}
                      type="button"
                      onClick={() => activateBlock(block)}
                      onMouseEnter={() => activateBlock(block)}
                      style={getOcrPolygonStyle(block)}
                      className={`absolute border-2 transition ${
                        isActive
                          ? "z-20 border-teal-400 bg-teal-300/30 shadow-[0_0_0_2px_rgba(13,148,136,0.25)]"
                          : hasField
                            ? "z-10 border-amber-300/70 bg-amber-200/10 hover:bg-amber-200/30"
                            : "border-transparent"
                      }`}
                      aria-label={`Nguồn OCR: ${block.text}`}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-600 p-8 text-center text-sm text-slate-300">
                Chưa có ảnh evidence. UI không dựng lại “ảnh gốc” từ giá trị KIE.
              </div>
            )}
          </div>
        </div>

        <div className="flex h-12 shrink-0 items-center justify-center gap-2 border-t border-white/10 bg-slate-900/90 px-3 text-white">
          <button
            type="button"
            onClick={() => setZoom((value) => Math.max(70, value - 10))}
            className="grid size-8 place-items-center rounded-lg bg-white/5 hover:bg-white/10"
            aria-label="Thu nhỏ"
          >
            −
          </button>
          <span className="w-12 text-center text-[11px] font-bold">{zoom}%</span>
          <button
            type="button"
            onClick={() => setZoom((value) => Math.min(160, value + 10))}
            className="grid size-8 place-items-center rounded-lg bg-white/5 hover:bg-white/10"
            aria-label="Phóng to"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => setRotation((value) => (value + 90) % 360)}
            className="ml-2 rounded-lg bg-white/5 px-3 py-2 text-[11px] font-bold hover:bg-white/10"
          >
            Xoay 90°
          </button>
        </div>
      </section>

      <section className="flex min-h-0 flex-1 flex-col bg-white lg:h-full">
        <header className="shrink-0 border-b border-slate-200 px-5 py-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-teal-700">
            Human-in-the-Loop
          </p>
          <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-950">
            Đối chiếu thông tin
          </h1>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Chọn field để highlight nguồn OCR; chọn polygon trên ảnh để quay lại field tương ứng.
          </p>
        </header>

        <div className="min-h-0 flex-1 overflow-auto px-4 py-4 sm:px-5">
          <div className="space-y-3">
            {orderedFields.map((field) => {
              const draft = drafts[field.field_name]!;
              const isAddress = field.field_name === "merchant_address";
              const isActive = activeFieldType === field.field_name;
              return (
                <fieldset
                  key={field.field_name}
                  onFocus={() => setActiveFieldType(field.field_name)}
                  onMouseEnter={() => setActiveFieldType(field.field_name)}
                  className={`rounded-2xl border p-3.5 transition ${
                    isActive
                      ? "border-teal-400 bg-teal-50/40 ring-2 ring-teal-500/10"
                      : "border-slate-200"
                  }`}
                >
                  <legend className="px-1 text-sm font-bold text-slate-700">
                    {FIELD_LABELS[field.field_name]}
                  </legend>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                      Confidence {Math.round(field.machine.confidence * 100)}% · {statusLabels[field.machine.value_status]}
                    </span>
                    {field.machine.review_reasons.length > 0 && (
                      <span className="text-[10px] font-semibold text-amber-700">
                        {field.machine.review_reasons
                          .map((reason) => reasonLabels[reason])
                          .join(" · ")}
                      </span>
                    )}
                  </div>

                  {isAddress ? (
                    <textarea
                      value={draft.value === null ? "" : String(draft.value)}
                      onChange={(event) => handleChange(field, event)}
                      disabled={!canEdit}
                      rows={2}
                      className="w-full resize-none rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10 disabled:bg-slate-50"
                    />
                  ) : (
                    <input
                      type={
                        field.field_name === "receipt_date"
                          ? "date"
                          : field.field_name === "total_amount"
                            ? "number"
                            : "text"
                      }
                      inputMode={
                        field.field_name === "total_amount"
                          ? "numeric"
                          : undefined
                      }
                      min={field.field_name === "total_amount" ? 0 : undefined}
                      value={draft.value === null ? "" : String(draft.value)}
                      onChange={(event) => handleChange(field, event)}
                      disabled={!canEdit}
                      className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-900 outline-none focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10 disabled:bg-slate-50"
                    />
                  )}

                  <p className="mt-2 text-[11px] leading-4 text-slate-500">
                    OCR raw: <span className="font-semibold text-slate-700">{field.machine.raw_text ?? "—"}</span>
                  </p>
                  {field.machine.predicted_value !== null &&
                    !valuesEqual(
                      field.machine.predicted_value,
                      field.effective_value,
                    ) && (
                      <p className="mt-1 text-[11px] leading-4 text-slate-500">
                        KIE dự đoán: <span className="font-semibold text-slate-700">{field.machine.predicted_value}</span>. Giá trị prediction không tự động trở thành effective value.
                      </p>
                    )}
                  <p className="mt-1 text-[10px] text-teal-700">
                    Nguồn: {field.machine.source_block_ids.join(", ") || "không có block"}
                  </p>

                  {canEdit && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <select
                        value={draft.value_status}
                        onChange={(event) =>
                          handleStatus(
                            field.field_name,
                            event.target.value as ValueStatus,
                          )
                        }
                        className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
                      >
                        {VALUE_STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {statusLabels[status]}
                          </option>
                        ))}
                      </select>
                      {field.effective_needs_review && (
                        <button
                          type="button"
                          onClick={() => keepEffectiveValue(field)}
                          className="h-9 rounded-lg bg-teal-50 px-3 text-xs font-bold text-teal-800"
                        >
                          Xác nhận giá trị
                        </button>
                      )}
                      {field.has_correction && (
                        <button
                          type="button"
                          onClick={() => clearCorrection(field)}
                          className="h-9 rounded-lg bg-slate-100 px-3 text-xs font-bold text-slate-700"
                        >
                          Xóa hiệu chỉnh (CLEAR)
                        </button>
                      )}
                    </div>
                  )}
                </fieldset>
              );
            })}
          </div>

          <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
            Cảnh báo hiện tại dùng effective_needs_review; machine_needs_review và review_reasons vẫn được giữ làm bằng chứng bất biến từ KIE.
          </p>
        </div>

        <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-5">
          {notice && (
            <p
              role="status"
              className={`mb-3 rounded-xl px-3 py-2 text-xs font-semibold ${
                notice.tone === "success"
                  ? "bg-emerald-50 text-emerald-800"
                  : "bg-red-50 text-red-800"
              }`}
            >
              {notice.message}
            </p>
          )}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              {unresolvedCount > 0
                ? `${unresolvedCount} trường cần xác nhận`
                : "Tất cả trường đã được giải quyết"}
            </p>
            <button
              type="button"
              onClick={verify}
              disabled={!canEdit}
              className="h-10 rounded-xl bg-teal-800 px-5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              Xác minh hóa đơn
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
