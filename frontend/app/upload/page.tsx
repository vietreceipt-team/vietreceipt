"use client";

import { useMemo, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { createBrowserVietReceiptApi, getApiErrorMessage } from "../../lib/vietreceipt-api";

type UploadState = "IDLE" | "SELECTED" | "UPLOADING" | "UPLOAD_SUCCESS" | "UPLOAD_ERROR";

const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxFileSize = 10 * 1024 * 1024;

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function validateFile(file: File) {
  if (!allowedTypes.has(file.type)) return "Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.";
  if (file.size > maxFileSize) return "File vượt quá giới hạn 10 MiB của Frontend.";
  return null;
}

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const api = useMemo(() => createBrowserVietReceiptApi(), []);
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("IDLE");
  const [message, setMessage] = useState<string | null>(null);

  function selectFile(nextFile: File) {
    const validationError = validateFile(nextFile);
    if (validationError) {
      setFile(null);
      setState("UPLOAD_ERROR");
      setMessage(validationError);
      return;
    }
    setFile(nextFile);
    setState("SELECTED");
    setMessage(null);
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (selected) selectFile(selected);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const selected = event.dataTransfer.files[0];
    if (selected) selectFile(selected);
  }

  function handleDropzoneKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  async function submit() {
    if (!file || state === "UPLOADING") return;
    setState("UPLOADING");
    setMessage(null);
    try {
      const receipt = await api.uploadReceipt(file);
      setState("UPLOAD_SUCCESS");
      setMessage("Ảnh và metadata đã được lưu. Đang mở trạng thái xử lý...");
      router.push(`/receipts/${encodeURIComponent(receipt.receipt_id)}`);
    } catch (error) {
      setState("UPLOAD_ERROR");
      setMessage(getApiErrorMessage(error));
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-teal-700">Bước 1 · Thu thập dữ liệu</p>
        <h1 className="text-3xl font-bold tracking-[-0.035em] text-slate-950 sm:text-4xl">Tải hóa đơn lên</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
          Frontend chỉ gửi ảnh tới Backend. Backend lưu dữ liệu và tự schedule xử lý; không có lời gọi OCR, KIE hay <code>/process</code> từ trình duyệt.
        </p>
      </header>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="p-5 sm:p-7">
          <div
            role="button"
            tabIndex={0}
            aria-label="Chọn hoặc kéo thả hóa đơn để tải lên"
            onClick={() => inputRef.current?.click()}
            onKeyDown={handleDropzoneKey}
            onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`grid min-h-72 place-items-center rounded-2xl border-2 border-dashed px-6 py-12 text-center outline-none transition ${
              isDragging
                ? "border-teal-600 bg-teal-50"
                : "border-slate-200 bg-slate-50/70 hover:border-teal-500 hover:bg-teal-50/50 focus-visible:ring-4 focus-visible:ring-teal-600/10"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleInput}
              className="sr-only"
            />
            <div>
              <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl border border-teal-100 bg-white text-3xl text-teal-700 shadow-sm">↑</div>
              <h2 className="text-lg font-bold text-slate-900">{isDragging ? "Thả tệp tại đây" : "Kéo thả hóa đơn vào đây"}</h2>
              <p className="mt-2 text-sm text-slate-500">hoặc <span className="font-bold text-teal-700">chọn tệp từ thiết bị</span></p>
              <p className="mt-4 text-xs text-slate-400">JPEG, PNG hoặc WebP · Tối đa 10 MiB</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-100 bg-slate-50/60 p-5 sm:p-7">
          {file ? (
            <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-teal-50 text-xs font-black uppercase text-teal-800">
                  {file.name.split(".").pop()?.slice(0, 4) ?? "Ảnh"}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-slate-900">{file.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatBytes(file.size)} · {state}</p>
                </div>
                {state !== "UPLOADING" && (
                  <button
                    type="button"
                    onClick={() => { setFile(null); setState("IDLE"); setMessage(null); }}
                    className="rounded-lg px-3 py-2 text-xs font-bold text-slate-500 hover:bg-red-50 hover:text-red-700"
                  >
                    Bỏ chọn
                  </button>
                )}
              </div>
              {state === "UPLOADING" && (
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-label="Đang tải lên">
                  <div className="h-full w-1/3 animate-[upload_1.2s_ease-in-out_infinite] rounded-full bg-teal-600" />
                </div>
              )}
            </article>
          ) : (
            <p className="rounded-2xl border border-dashed border-slate-200 bg-white p-5 text-center text-sm text-slate-400">Chưa chọn hóa đơn.</p>
          )}

          {message && (
            <p role={state === "UPLOAD_ERROR" ? "alert" : "status"} className={`mt-3 rounded-xl px-4 py-3 text-sm font-semibold ${state === "UPLOAD_ERROR" ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-800"}`}>
              {message}
            </p>
          )}

          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={() => void submit()}
              disabled={!file || state === "UPLOADING" || state === "UPLOAD_SUCCESS"}
              className="inline-flex h-11 items-center justify-center rounded-xl bg-teal-800 px-5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {state === "UPLOADING" ? "Đang tải lên..." : "Tải và mở hóa đơn"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
