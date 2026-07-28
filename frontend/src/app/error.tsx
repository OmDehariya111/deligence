"use client";

import { useEffect } from "react";
import { AlertCircle, RefreshCcw } from "lucide-react";

export default function Error({ error, unstable_retry }: { error: Error & { digest?: string }; unstable_retry: () => void }) {
  useEffect(() => {
    console.error("Route rendering error", error);
  }, [error]);

  return (
    <main className="flex min-h-[70vh] items-center justify-center bg-black px-6 text-center text-white">
      <div className="max-w-md rounded-2xl border border-red-400/20 bg-red-500/10 p-8">
        <AlertCircle className="mx-auto mb-4 size-10 text-red-300" />
        <h1 className="text-2xl font-bold">This workspace hit a temporary issue</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-300">Your data is safe. Please retry the screen, and contact support with reference {error.digest || "unavailable"} if it persists.</p>
        <button type="button" onClick={unstable_retry} className="mt-6 inline-flex items-center rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black hover:bg-zinc-200"><RefreshCcw className="mr-2 size-4" />Try again</button>
      </div>
    </main>
  );
}
