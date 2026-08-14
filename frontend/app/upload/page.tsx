"use client";

import { ChangeEvent, DragEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";

type UploadStatus = "waiting" | "uploading" | "complete";

interface UploadItem {
  id: string;
  name: string;
  size: string;
  progress: number;
  status: UploadStatus;
}

const initialFiles: UploadItem[] = [
  { id: "sample-1", name: "hoa-don-an-nam-001.jpg", size: "1,8 MB", progress: 100, status: "complete" },
  { id: "sample-2", name: "cafe-moc-aug11.png", size: "2,4 MB", progress: 68, status: "uploading" },
  { id: "sample-3", name: "nha-thuoc-minh-tam.jpg", size: "824 KB", progress: 0, status: "waiting" },
];

const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
const maxFileSize = 10 * 1024 * 1024;

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<UploadItem[]>(initialFiles);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setFiles((current) =>
        current.map((file) => {
          if (file.status !== "uploading") return file;
          const progress = Math.min(100, file.progress + 8);
          return { ...file, progress, status: progress === 100 ? "complete" : "uploading" };
        }),
      );
    }, 650);

    return () => window.clearInterval(timer);
  }, []);

  function addFiles(selectedFiles: FileList | File[]) {
    const selected = Array.from(selectedFiles);
    const validFiles = selected.filter((file) => allowedTypes.includes(file.type) && file.size <= maxFileSize);
    const rejectedCount = selected.length - validFiles.length;

    setValidationMessage(
      rejectedCount > 0
        ? `${rejectedCount} tệp không hợp lệ. Tuần 1 chỉ hỗ trợ JPEG/PNG/WebP tối đa 10 MiB.`
        : null,
    );

    const additions = validFiles.map((file, index) => ({
      id: `${file.name}-${file.lastModified}-${index}`,
      name: file.name,
      size: formatBytes(file.size),
      progress: 4,
      status: "uploading" as const,
    }));
    setFiles((current) => [...additions, ...current]);
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files?.length) addFiles(event.target.files);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  }

  function handleDropzoneKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  function removeFile(id: string) {
    setFiles((current) => current.filter((file) => file.id !== id));
  }

  const completeCount = files.filter((file) => file.status === "complete").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-teal-700">Bước 1 · Thu thập dữ liệu</p>
          <h1 className="text-3xl font-bold tracking-[-0.035em] text-slate-950 sm:text-4xl">Tải hóa đơn lên</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
            Thêm ảnh hóa đơn rõ nét. Sau khi tải xong, hóa đơn ở trạng thái UPLOADED và sẵn sàng bắt đầu xử lý.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
          <span className="font-bold text-slate-950">{completeCount}/{files.length}</span>
          <span className="ml-1.5 text-slate-500">tệp đã tải xong</span>
        </div>
      </header>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
        <div className="p-4 sm:p-6">
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
            className={`group grid min-h-72 place-items-center rounded-2xl border-2 border-dashed px-6 py-12 text-center outline-none transition ${
              isDragging
                ? "border-teal-600 bg-teal-50"
                : "border-slate-200 bg-slate-50/70 hover:border-teal-500 hover:bg-teal-50/50 focus-visible:border-teal-600 focus-visible:ring-4 focus-visible:ring-teal-600/10"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={handleInput}
              className="sr-only"
            />
            <div>
              <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl border border-teal-100 bg-white text-3xl text-teal-700 shadow-sm transition group-hover:-translate-y-1">
                ↑
              </div>
              <h2 className="text-lg font-bold text-slate-900">
                {isDragging ? "Thả tệp tại đây" : "Kéo thả hóa đơn vào đây"}
              </h2>
              <p className="mt-2 text-sm text-slate-500">hoặc <span className="font-bold text-teal-700">chọn tệp từ thiết bị</span></p>
              <p className="mt-4 text-xs text-slate-400">JPEG, PNG hoặc WebP · Tối đa 10 MiB mỗi tệp</p>
            </div>
          </div>
          {validationMessage && (
            <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {validationMessage}
            </p>
          )}
        </div>

        <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-5 sm:px-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-sm font-bold text-slate-900">Danh sách tải lên</h2>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="text-xs font-bold text-teal-700 hover:text-teal-900"
            >
              + Thêm tệp
            </button>
          </div>

          <div className="space-y-2">
            {files.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-400">Chưa có tệp nào.</div>
            ) : files.map((file) => (
              <article key={file.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm shadow-slate-100/60">
                <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-black uppercase text-slate-500">
                  {file.name.split(".").pop()?.slice(0, 3) ?? "Tệp"}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-bold text-slate-800">{file.name}</p>
                    <span className={`shrink-0 text-xs font-bold ${file.status === "complete" ? "text-emerald-700" : file.status === "uploading" ? "text-teal-700" : "text-slate-400"}`}>
                      {file.status === "complete" ? "Hoàn tất" : file.status === "uploading" ? `${file.progress}%` : "Đang chờ"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${file.status === "complete" ? "bg-emerald-500" : "bg-teal-600"}`}
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                    <span className="w-14 shrink-0 text-right text-[11px] text-slate-400">{file.size}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(file.id)}
                  className="grid size-8 shrink-0 place-items-center rounded-lg text-lg text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                  aria-label={`Xóa ${file.name}`}
                >
                  ×
                </button>
              </article>
            ))}
          </div>
        </div>
      </section>

      <div className="mt-6 flex flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center">
        <p className="text-xs leading-5 text-slate-400">Tệp chỉ được mô phỏng cục bộ; bản tích hợp sẽ upload bằng multipart field “file”.</p>
        <Link
          href="/receipts"
          className="inline-flex h-11 items-center justify-center rounded-xl bg-teal-800 px-5 text-sm font-bold text-white shadow-sm transition hover:bg-teal-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
        >
          Xem danh sách hóa đơn <span className="ml-2" aria-hidden="true">→</span>
        </Link>
      </div>
    </div>
  );
}
