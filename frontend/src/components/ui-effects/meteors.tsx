"use client";

import { cn } from "@/lib/utils";

export const Meteors = ({
  number = 20,
  className,
}: {
  number?: number;
  className?: string;
}) => {
  const meteors = Array.from({ length: number }, (_, index) => ({
    top: `${(index * 37 + 11) % 100}%`,
    left: `${(index * 61 + 7) % 100}%`,
    animationDelay: `${0.2 + ((index * 17) % 60) / 100}s`,
    animationDuration: `${2 + ((index * 13) % 8)}s`,
  }));

  return (
    <>
      {meteors.map((el, idx) => (
        <span
          key={"meteor" + idx}
          className={cn(
            "animate-meteor-effect absolute h-0.5 w-0.5 rounded-[9999px] bg-slate-300 shadow-[0_0_0_1px_#ffffff20] rotate-[215deg]",
            "before:content-[''] before:absolute before:top-1/2 before:transform before:-translate-y-[50%] before:w-[100px] before:h-[2px] before:bg-gradient-to-r before:from-[#cbd5e1] before:to-transparent",
            className
          )}
          style={{
            top: el.top,
            left: el.left,
            animationDelay: el.animationDelay,
            animationDuration: el.animationDuration,
          }}
        ></span>
      ))}
    </>
  );
};
