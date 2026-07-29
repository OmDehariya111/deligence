import type { Metadata } from "next";
import { AuthProvider } from "@/components/providers/auth-provider";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://deligenx.vercel.app"),
  title: {
    default: "DeligenX — Autonomous AI Financial Due Diligence",
    template: "%s | DeligenX",
  },
  description:
    "DeligenX turns any US public ticker into an institutional-grade investment memorandum in minutes — autonomous 5-agent AI pipeline, SEC-cited, zero human intervention.",
  keywords: [
    "AI Due Diligence",
    "Financial Analysis",
    "Investment Memo",
    "SEC Filings",
    "Risk Assessment",
    "DeligenX",
  ],
  authors: [{ name: "DeligenX" }],
  openGraph: {
    title: "DeligenX — Autonomous AI Financial Due Diligence",
    description:
      "Institutional-grade investment memos in minutes, not weeks. Autonomous multi-agent AI, SEC filings, deterministic risk models.",
    type: "website",
    siteName: "DeligenX",
  },
  twitter: {
    card: "summary_large_image",
    title: "DeligenX — AI Due Diligence",
    description:
      "Automate financial research and risk assessment with a 5-agent AI pipeline.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="antialiased min-h-screen bg-background text-foreground">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
