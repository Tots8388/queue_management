import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

/**
 * Inter, self-hosted rather than fetched from Google Fonts.
 *
 * `next/font/google` downloads the font at *build* time. The clinic machine is
 * on the Medical Center's LAN with no internet dependency by design, so a build
 * there would fail on a font — which is a silly reason to be unable to deploy.
 * Shipping the woff2 in the repo makes the build work anywhere, and keeps the
 * typography identical to the approved design.
 *
 * It also means no request leaves the building to render a page, which is the
 * behaviour the on-premise decision was made for in the first place.
 */
const inter = localFont({
  src: "../../../shared/ui/fonts/Inter-Variable.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: {
    default: "Staff — Kabarak University Medical Center",
    template: "%s — Staff — Kabarak University Medical Center",
  },
  description:
    "Staff dashboards for the outpatient queue at Kabarak University " +
    "Medical Center.",
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
