"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Navbar } from "@/components/site/Navbar";
import { Footer } from "@/components/site/Footer";
import { TickerConsole } from "@/components/demo/TickerConsole";
import { PipelineStepper } from "@/components/demo/PipelineStepper";
import { ReportViewer } from "@/components/demo/ReportViewer";
import { getDemoReport, type DemoReport } from "@/components/demo/demoData";
import { ScrollProgress } from "@/components/site/ScrollProgress";

type Phase = "idle" | "running" | "done";

export default function DemoPage() {
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [report, setReport] = useState<DemoReport | null>(null);

  const start = () => {
    const t = (ticker || "AAPL").toUpperCase();
    setTicker(t);
    setReport(null);
    setPhase("running");
  };

  const handleComplete = useCallback(() => {
    setReport(getDemoReport((ticker || "AAPL").toUpperCase()));
    setPhase("done");
  }, [ticker]);

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <ScrollProgress />
      <Navbar />
      <main className="relative isolate">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[520px]"
          style={{
            background:
              "radial-gradient(55% 60% at 50% 0%, rgba(57,255,136,0.14), transparent 65%)",
          }}
        />

        <section className="mx-auto max-w-7xl px-5 pt-32 pb-10 md:px-8 md:pt-36">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex flex-col items-center text-center"
          >
            <div className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.25em] text-primary">
              <span className="h-px w-6 bg-primary/60" />
              Live Demo
              <span className="h-px w-6 bg-primary/60" />
            </div>
            <h1 className="mt-5 max-w-3xl font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-6xl">
              Analyze any{" "}
              <span className="text-gradient-neon inline-block pr-2 italic">
                US public company.
              </span>
            </h1>
            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
              Enter a ticker and watch the five agents run end to end. This demo uses sample
              data so you can see the full output instantly.
            </p>

            <div className="mt-9 flex justify-center">
              <TickerConsole
                value={ticker}
                onChange={setTicker}
                onSubmit={start}
                busy={phase === "running"}
              />
            </div>
          </motion.div>
        </section>

        <section className="mx-auto max-w-4xl px-5 pb-24 md:px-8 md:pb-32">
          <AnimatePresence mode="wait">
            {phase === "running" && (
              <motion.div
                key="running"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.4 }}
              >
                <PipelineStepper onComplete={handleComplete} />
              </motion.div>
            )}

            {phase === "done" && report && (
              <motion.div
                key="report"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, ease: "easeOut" }}
              >
                <ReportViewer report={report} />
              </motion.div>
            )}

            {phase === "idle" && (
              <motion.p
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-center font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground/70"
              >
                Awaiting ticker · pipeline idle
              </motion.p>
            )}
          </AnimatePresence>
        </section>
      </main>
      <Footer />
    </div>
  );
}
