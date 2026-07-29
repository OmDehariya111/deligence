"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { agentSteps } from "./demoData";
import { cn } from "@/lib/utils";

const STATUS_MS = 700;

export function PipelineStepper({ onComplete }: { onComplete: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [statusIndex, setStatusIndex] = useState(0);
  const done = useRef(false);

  const totalStatuses = agentSteps.reduce((a, s) => a + s.statuses.length, 0);
  const completedStatuses =
    agentSteps.slice(0, stepIndex).reduce((a, s) => a + s.statuses.length, 0) +
    statusIndex;
  const progress = Math.min(100, (completedStatuses / totalStatuses) * 100);

  useEffect(() => {
    const id = setTimeout(() => {
      const step = agentSteps[stepIndex];
      if (!step) return;
      if (statusIndex + 1 < step.statuses.length) {
        setStatusIndex((i) => i + 1);
      } else if (stepIndex + 1 < agentSteps.length) {
        setStepIndex((i) => i + 1);
        setStatusIndex(0);
      } else if (!done.current) {
        done.current = true;
        onComplete();
      }
    }, STATUS_MS);
    return () => clearTimeout(id);
  }, [stepIndex, statusIndex, onComplete]);

  const currentStatus =
    agentSteps[stepIndex]?.statuses[statusIndex] ?? "Finalising…";

  return (
    <div className="glass mx-auto w-full max-w-2xl rounded-2xl p-6 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">
          Pipeline running
        </div>
        <div className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {Math.round(progress)}%
        </div>
      </div>

      <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.07)]">
        <motion.div
          className="h-full rounded-full bg-primary"
          style={{ boxShadow: "0 0 12px rgba(57,255,136,0.7)" }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      <ol className="mt-7 space-y-1">
        {agentSteps.map((step, i) => {
          const Icon = step.icon;
          const state = i < stepIndex ? "done" : i === stepIndex ? "active" : "idle";
          return (
            <li key={step.id} className="relative flex gap-4 pb-5 last:pb-0">
              {i < agentSteps.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    "absolute left-[17px] top-9 bottom-0 w-px transition-colors duration-500",
                    state === "done" ? "bg-primary/50" : "bg-[rgba(255,255,255,0.08)]",
                  )}
                />
              )}
              <div
                className={cn(
                  "relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full border bg-background transition-all duration-300",
                  state === "done" && "border-primary text-primary",
                  state === "active" &&
                    "border-primary text-primary shadow-[0_0_18px_rgba(57,255,136,0.5)]",
                  state === "idle" && "border-[rgba(255,255,255,0.10)] text-muted-foreground/60",
                )}
              >
                {state === "done" ? (
                  <Check className="h-4 w-4" />
                ) : state === "active" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
              </div>
              <div className="min-w-0 pt-1.5">
                <div
                  className={cn(
                    "text-sm font-medium transition-colors duration-300",
                    state === "idle" ? "text-muted-foreground/60" : "text-foreground",
                  )}
                >
                  {step.name}
                </div>
                {state === "active" && (
                  <motion.div
                    key={currentStatus}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-1 font-mono text-[11px] text-primary/85"
                  >
                    {currentStatus}
                  </motion.div>
                )}
                {state === "done" && (
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    Complete
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}