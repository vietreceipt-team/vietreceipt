"use client";

/* eslint-disable @next/next/no-img-element -- image URLs come from the backend and need native error fallback. */

import { useState } from "react";
import { ReceiptText } from "lucide-react";

export function ReceiptThumbnail({ label, src }: { label: string; src?: string | null }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const imageFailed = Boolean(src && failedSrc === src);

  if (src && !imageFailed) {
    return (
      <img
        src={src}
        alt={`Ảnh thu nhỏ ${label}`}
        onError={() => setFailedSrc(src)}
        className="h-14 w-12 shrink-0 rounded-lg border border-slate-200 bg-white object-cover shadow-sm"
      />
    );
  }

  return (
    <div
      className="relative grid h-14 w-12 shrink-0 place-items-center overflow-hidden rounded-lg border border-slate-200 bg-[#fffdf8] shadow-sm"
      role="img"
      aria-label={`Ảnh thu nhỏ ${label}`}
    >
      <ReceiptText className="size-6 text-slate-400" aria-hidden="true" />
    </div>
  );
}
