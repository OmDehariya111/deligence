"use client";

import { usePathname } from "next/navigation";
import Navbar from "@/components/layout/Navbar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hasDedicatedChrome = pathname.startsWith("/job/") || pathname === "/login" || pathname === "/signup";

  return (
    <div className="relative min-h-screen bg-black text-white selection:bg-accent/30 selection:text-white">
      {!hasDedicatedChrome && <Navbar />}
      <div className={hasDedicatedChrome ? "relative z-10" : "relative z-10 pt-20"}>{children}</div>
    </div>
  );
}
