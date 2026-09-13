"use client";

// Reports once when an element first scrolls into view, so long tour chapters reveal their blocks as
// the reader reaches them. Without IntersectionObserver, or with reduced motion, it is revealed at once.

import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

export interface UseRevealOnViewReturn<T extends Element> {
  ref: React.RefObject<T>;
  revealed: boolean;
}

export function useRevealOnView<T extends Element>(threshold = 0.12): UseRevealOnViewReturn<T> {
  const ref = useRef<T>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || revealed) return;
    if (prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
      setRevealed(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [revealed, threshold]);

  return { ref, revealed };
}
