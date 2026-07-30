import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Queue — Kabarak University Medical Center",
    template: "%s — Kabarak University Medical Center",
  },
  description:
    "Digital queue and patient-flow management for outpatient visits at " +
    "Kabarak University Medical Center.",
  // Nothing here is public-web content; keep it out of search indexes.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Patients must be able to zoom — do not set maximumScale or userScalable.
  themeColor: "#16653f",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-KE" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <a
          href="#main"
          className="sr-only-focusable absolute left-4 top-4 z-50 rounded bg-brand-600 px-4 py-2 font-medium text-white"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
