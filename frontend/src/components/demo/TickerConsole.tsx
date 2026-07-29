"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { exampleTickers } from "./demoData";

export function TickerConsole({
  value,
  onChange,
  onSubmit,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const [focused, setFocused] = useState(false);

  return (
    <div className="w-full max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className={`flex w-full items-center gap-2 rounded-lg border bg-[rgba(8,8,8,0.72)] p-1.5 backdrop-blur-md transition-all duration-300 ${
          focused
            ? "border-primary/60 shadow-[0_0_0_1px_rgba(57,255,136,0.35),0_0_40px_rgba(57,255,136,0.2)]"
            : "border-[rgba(255,255,255,0.08)]"
        }`}
      >
        <div className="relative flex flex-1 items-center gap-2 px-3 py-2 font-mono text-sm">
          <span className="text-primary/80">$</span>
          <div className="relative flex-1">
            <input
              value={value}
              onChange={(e) => onChange(e.target.value.toUpperCase().slice(0, 6))}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              className="w-full bg-transparent font-mono text-sm tracking-wider text-foreground focus:outline-none"
              aria-label="Enter US stock ticker"
            />
            {!value && (
              <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center font-mono text-sm text-muted-foreground/70">
                AAPL<span className="caret-blink text-primary">_</span>
              </span>
            )}
          </div>
        </div>
        <motion.button
          type="submit"
          disabled={busy}
          whileHover={{ scale: busy ? 1 : 1.02 }}
          whileTap={{ scale: busy ? 1 : 0.97 }}
          className="group inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-all duration-200 neon-glow hover:brightness-110 disabled:opacity-60"
        >
          {busy ? "Analyzing…" : "Analyze"}
          <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
        </motion.button>
      </form>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
          Try
        </span>
        {exampleTickers.map((t) => (
          <motion.button
            key={t}
            type="button"
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => onChange(t)}
            className={`rounded-md border px-3 py-1.5 font-mono text-[11px] tracking-[0.12em] transition-all duration-200 ${
              value === t
                ? "border-primary/60 bg-primary/10 text-primary"
                : "border-[rgba(255,255,255,0.09)] bg-[rgba(255,255,255,0.03)] text-muted-foreground hover:border-primary/35 hover:text-primary"
            }`}
          >
            {t}
          </motion.button>
        ))}
      </div>
    </div>
  );
}