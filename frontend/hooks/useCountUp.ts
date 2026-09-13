"use client";

// Counts from 0 to `target` once on mount (a tour chapter mounts when it becomes active), easing out
// so the number settles rather than stops. Reduced motion shows the final value immediately.

import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

interface UseCountUpOptions {
  durationMs?: number;
  delayMs?: number;
}

const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

export function useCountUp(target: number, { durationMs = 1200, delayMs = 250 }: UseCountUpOptions = {}): number {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(target)) {
      setValue(target);
      return;
    }
    let start: number | null = null;
    const tick = (now: number) => {
      if (start === null) start = now + delayMs;
      const elapsed = now - start;
      const progress = elapsed <= 0 ? 0 : Math.min(elapsed / durationMs, 1);
      setValue(target * easeOutExpo(progress));
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, durationMs, delayMs]);

  return value;
}
