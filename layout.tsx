import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Set construction estimator",
  description: "Turn plain-English set build requests into costed estimates.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <div className="tape" aria-hidden="true" />
        <header className="masthead">
          <Link href="/" className="masthead__title">
            Set construction estimator
          </Link>
          <p className="masthead__sub">Art department build costs, from a plain-English request</p>
        </header>
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
