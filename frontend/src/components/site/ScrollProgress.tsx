"use client";

import { motion, useScroll, useSpring } from "framer-motion";

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 240,
    damping: 34,
    restDelta: 0.001,
  });

  return (
    <motion.div
      aria-hidden
      style={{
        scaleX,
        transformOrigin: "0% 50%",
        boxShadow: "0 0 12px rgba(57,255,136,0.7)",
      }}
      className="fixed inset-x-0 top-0 z-[70] h-[2px] bg-primary"
    />
  );
}