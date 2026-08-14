"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/upload", label: "Tải hóa đơn" },
  { href: "/receipts", label: "Hóa đơn" },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 h-14 border-b border-slate-200/90 bg-white/95 backdrop-blur">
      <div className="flex h-full w-full items-center gap-3 px-5">
        <Link
          href="/receipts"
          className="flex shrink-0 items-center gap-2.5 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2"
          aria-label="VietReceipt — Trang hóa đơn"
        >
          <span className="grid size-9 place-items-center rounded-xl bg-teal-800 text-base font-black tracking-tight text-white shadow-sm shadow-teal-900/20">
            V
          </span>
          <span className="hidden text-lg font-bold tracking-[-0.025em] text-slate-950 sm:inline">
            VietReceipt
          </span>
        </Link>

        <nav className="ml-1 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:ml-6" aria-label="Điều hướng chính">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
                  isActive
                    ? "bg-teal-50 text-teal-800"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden text-right md:block">
            <span className="block text-xs font-bold leading-4 text-slate-800">Nguyễn An</span>
            <span className="block text-[11px] leading-3 text-slate-400">Kiểm duyệt viên</span>
          </span>
          <Link
            href="/login"
            className={`grid size-9 place-items-center rounded-full text-xs font-bold leading-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ${
              pathname === "/login"
                ? "bg-teal-800 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
            aria-label="Mở trang đăng nhập"
          >
            NA
          </Link>
        </div>
      </div>
    </header>
  );
}
