"use client";

import { useEffect, useRef } from "react";

export function CursorGlow() {
  const orbRef = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: 0, y: 0 });
  const target = useRef({ x: 0, y: 0 });

  useEffect(() => {
    // Start slightly offscreen to avoid jump
    pos.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    target.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 };

    const handleMouseMove = (e: MouseEvent) => {
      target.current = { x: e.clientX, y: e.clientY };
    };

    window.addEventListener("mousemove", handleMouseMove);

    let animationFrameId: number;

    const render = () => {
      // Smooth interpolation
      pos.current.x += (target.current.x - pos.current.x) * 0.15;
      pos.current.y += (target.current.y - pos.current.y) * 0.15;

      if (orbRef.current) {
        orbRef.current.style.transform = `translate3d(${pos.current.x}px, ${pos.current.y}px, 0) translate(-50%, -50%)`;
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div
      ref={orbRef}
      className="pointer-events-none fixed top-0 left-0 z-[9999] h-48 w-48 rounded-full bg-emerald-500/25 blur-[50px]"
      style={{ transform: "translate(-50%, -50%)" }}
    />
  );
}
