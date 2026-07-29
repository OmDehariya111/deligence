"use client";

import { motion } from "framer-motion";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <motion.svg
        width="26"
        height="26"
        viewBox="0 0 32 32"
        fill="none"
        initial={{ rotate: 0 }}
        animate={{ rotate: 360 }}
        transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
      >
        <defs>
          <linearGradient id="dgx" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#4dffa0" />
            <stop offset="100%" stopColor="#39ff88" />
          </linearGradient>
        </defs>
        <polygon
          points="16,2 29,9 29,23 16,30 3,23 3,9"
          stroke="url(#dgx)"
          strokeWidth="1.5"
          fill="rgba(57,255,136,0.06)"
        />
        <circle cx="16" cy="16" r="3" fill="#39ff88" />
        <circle cx="16" cy="6" r="1.6" fill="#4dffa0" />
        <circle cx="26" cy="12" r="1.6" fill="#4dffa0" />
        <circle cx="26" cy="22" r="1.6" fill="#4dffa0" />
        <circle cx="16" cy="26" r="1.6" fill="#4dffa0" />
        <circle cx="6" cy="22" r="1.6" fill="#4dffa0" />
        <circle cx="6" cy="12" r="1.6" fill="#4dffa0" />
        <g stroke="rgba(77,255,160,0.55)" strokeWidth="0.6">
          <line x1="16" y1="16" x2="16" y2="6" />
          <line x1="16" y1="16" x2="26" y2="12" />
          <line x1="16" y1="16" x2="26" y2="22" />
          <line x1="16" y1="16" x2="16" y2="26" />
          <line x1="16" y1="16" x2="6" y2="22" />
          <line x1="16" y1="16" x2="6" y2="12" />
        </g>
      </motion.svg>
      <span className="font-mono text-[15px] font-semibold tracking-tight text-foreground">
        Deligen<span className="text-primary">X</span>
      </span>
    </div>
  );
}