"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const reveal = (delay: number) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-10% 0px" },
  transition: { duration: 0.55, delay, ease: "easeOut" as const },
});

const tiers = [
  {
    name: "Starter",
    price: "Free",
    note: "For getting your first memo out",
    features: ["5 reports / month", "Core risk scorecard", "Standard support"],
    cta: "Start free",
    popular: false,
  },
  {
    name: "Professional",
    price: "$49",
    suffix: "/mo",
    note: "For analysts running real coverage",
    features: [
      "Unlimited reports",
      "Full trading comps table",
      "Deal-breaker alerts",
      "Priority processing",
    ],
    cta: "Go Professional",
    popular: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    note: "For desks and platforms",
    features: [
      "API access",
      "White-label memos",
      "Dedicated support",
      "Custom risk models",
    ],
    cta: "Talk to us",
    popular: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5 md:px-8">
        <motion.div {...reveal(0)} className="mx-auto max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.25em] text-primary">
            <span className="h-px w-6 bg-primary/60" />
            Pricing
            <span className="h-px w-6 bg-primary/60" />
          </div>
          <h2 className="mt-5 font-sans text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-foreground md:text-5xl">
            Start free.{" "}
            <span className="text-gradient-neon inline-block pr-2 italic">
              Scale when you're ready.
            </span>
          </h2>
        </motion.div>

        <div className="mt-14 grid gap-6 md:mt-20 md:grid-cols-3">
          {tiers.map((t, i) => (
            <motion.div
              key={t.name}
              {...reveal(0.08 + i * 0.08)}
              className={cn(
                "glass group relative flex flex-col rounded-2xl p-7 transition-all duration-300 hover:-translate-y-1",
                t.popular
                  ? "border-primary/45 shadow-[0_30px_90px_-40px_rgba(57,255,136,0.5)] md:-mt-4 md:pb-10"
                  : "hover:border-[rgba(255,255,255,0.16)]",
              )}
            >
              {t.popular && (
                <span className="absolute -top-3 left-7 rounded-full border border-primary/40 bg-primary/15 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
                  Most popular
                </span>
              )}
              <div className="text-sm font-medium text-foreground">{t.name}</div>
              <div className="mt-4 flex items-end gap-1">
                <span className="font-mono text-4xl font-bold tracking-tight text-foreground">
                  {t.price}
                </span>
                {t.suffix && (
                  <span className="pb-1 font-mono text-sm text-muted-foreground">
                    {t.suffix}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{t.note}</p>

              <ul className="mt-7 flex-1 space-y-3">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                href="/demo"
                className={cn(
                  "mt-8 inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition-all duration-200 active:scale-[0.98]",
                  t.popular
                    ? "bg-primary text-primary-foreground neon-glow hover:brightness-110"
                    : "border border-[rgba(255,255,255,0.12)] text-foreground hover:border-primary/40 hover:text-primary",
                )}
              >
                {t.cta}
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}