import type { Metadata } from "next";
import { AuthProvider } from "@/components/providers/auth-provider";
import AppShell from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://deligenx.ai"),
  title: {
    default: "DeligenX | No.1 AI Due Diligence Platform",
    template: "%s | DeligenX",
  },
  description: "Automate financial research, risk assessment, and market intelligence with DeligenX AI. The most advanced due diligence platform for professionals.",
  keywords: ["AI Due Diligence", "Financial Analysis", "Automated Research", "DeligenX", "Investment Intelligence"],
  alternates: { canonical: "/" },
  openGraph: {
    title: "DeligenX | No.1 AI Due Diligence Platform",
    description: "Automate financial research, risk assessment, and market intelligence with DeligenX AI.",
    url: "https://deligenx.ai",
    siteName: "DeligenX",
    locale: "en_US",
    type: "website",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "DeligenX AI due diligence platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "DeligenX | AI Due Diligence",
    description: "Automate financial research and risk assessment.",
    images: ["/opengraph-image"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className="antialiased min-h-screen bg-background text-foreground"
      >
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
