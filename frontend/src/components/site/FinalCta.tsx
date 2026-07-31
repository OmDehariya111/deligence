"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function FinalCta() {
  return (
    <section className="relative isolate overflow-hidden py-28 md:py-36">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 45%, rgba(57,255,136,0.14), transparent 65%), radial-gradient(ellipse 40% 40% at 15% 90%, rgba(57,255,136,0.07), transparent 70%)",
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-10% 0px" }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="mx-auto flex max-w-3xl flex-col items-center gap-7 px-5 text-center md:px-8"
      >
        <h2
          className="font-sans font-semibold tracking-[-0.03em] text-foreground"
          style={{ fontSize: "clamp(2.25rem, 5.5vw, 4rem)", lineHeight: 1.03 }}
        >
          Your next due diligence report is{" "}
          <span className="text-gradient-neon inline-block pr-2 italic">one ticker away.</span>
        </h2>
        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground neon-glow transition-all duration-200 hover:brightness-110"
          >
            Launch Platform
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      </motion.div>
    </section>
  );
}