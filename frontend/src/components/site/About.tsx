"use client";

import { motion } from "framer-motion";
import { Cpu } from "lucide-react";

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-10% 0px" },
  transition: { duration: 0.55, delay, ease: "easeOut" as const },
});

const stack = [
  "Next.js App Router",
  "FastAPI",
  "CrewAI",
  "PostgreSQL",
  "Redis & Celery",
  "ChromaDB",
  "FastMCP",
  "yfinance & SEC EDGAR"
];

export function About() {
  return (
    <section id="about" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-4xl px-5 md:px-8">
        <motion.h2
          {...reveal(0)}
          className="font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl"
        >
          Built for{" "}
          <span className="text-gradient-neon inline-block pr-2 pb-1 italic">institutional scale.</span>
        </motion.h2>

        <motion.p {...reveal(0.08)} className="mt-6 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
          DeligenX was engineered from the ground up to solve the most complex challenge in modern finance: asymmetric information processing. By orchestrating a five-agent autonomous AI pipeline, we eliminate human cognitive bias, fatigue, and error. Every metric, from SEC EDGAR ingestion to composite risk scoring, is handled deterministically. The result is unprecedented speed, uncompromising accuracy, and a definitive edge for institutional investors.
        </motion.p>

        <motion.div {...reveal(0.14)} className="mt-9 flex flex-wrap gap-2">
          {stack.map((s) => (
            <span
              key={s}
              className="rounded-md border border-[rgba(255,255,255,0.09)] bg-[rgba(255,255,255,0.03)] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground transition-colors hover:border-primary/35 hover:text-primary"
            >
              {s}
            </span>
          ))}
        </motion.div>

        <motion.div
          {...reveal(0.2)}
          className="glass mt-10 flex items-center gap-4 rounded-xl p-5"
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-foreground">System Architecture</div>
            <div className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
              Fully Autonomous · Deterministic Execution
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}