"use client";

import { motion } from "framer-motion";

export const SparklesText = ({ text }: { text: string }) => {
  const sparkles = Array.from({ length: 10 }, (_, id) => ({
    id,
    top: `${(id * 29 + 13) % 100}%`,
    left: `${(id * 47 + 5) % 100}%`,
    size: `${5 + ((id * 7) % 10)}px`,
    delay: (id * 0.31) % 2,
  }));

  return (
    <div className="relative inline-block">
      {sparkles.map((sparkle) => (
        <motion.div
          key={sparkle.id}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: [0, 1, 0], scale: [0, 1, 0] }}
          transition={{ duration: 1.5, repeat: Infinity, delay: sparkle.delay }}
          className="absolute z-50 rounded-full bg-yellow-300"
          style={{ top: sparkle.top, left: sparkle.left, width: sparkle.size, height: sparkle.size, filter: 'blur(1px)' }}
        />
      ))}
      <span className="relative z-10 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-600">
        {text}
      </span>
    </div>
  );
};
