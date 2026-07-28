export default function Loading() {
  return (
    <main className="flex min-h-[70vh] items-center justify-center bg-black text-sm text-zinc-300" aria-live="polite">
      <div className="flex items-center gap-3"><span className="size-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />Loading workspace…</div>
    </main>
  );
}
