import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import { Navigation } from "../components/navigation";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;
  const description =
    "Không gian xử lý, kiểm chứng và quản lý hóa đơn tiếng Việt với Human-in-the-Loop.";

  return {
    title: {
      default: "VietReceipt — Số hóa hóa đơn thông minh",
      template: "%s | VietReceipt",
    },
    description,
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title: "VietReceipt — Hóa đơn rõ ràng. Dữ liệu đáng tin.",
      description,
      siteName: "VietReceipt",
      locale: "vi_VN",
      type: "website",
      images: [
        {
          url: `${origin}/og.png`,
          width: 1730,
          height: 909,
          alt: "VietReceipt — Hóa đơn rõ ràng. Dữ liệu đáng tin.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "VietReceipt — Hóa đơn rõ ràng. Dữ liệu đáng tin.",
      description,
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-[#f6f7f9] text-slate-950 antialiased`}
      >
        <a
          href="#main-content"
          className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition-transform focus:translate-y-0"
        >
          Bỏ qua điều hướng
        </a>
        <Navigation />
        <main id="main-content">{children}</main>
      </body>
    </html>
  );
}
