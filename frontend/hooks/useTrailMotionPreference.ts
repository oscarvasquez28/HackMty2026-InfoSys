"use client";

// Motion policy for the money trail player: follow the OS reduced-motion preference by default, but
// let the reader force animations on for this browser session.

import { useCallback, useState } from "react";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

const STORAGE_KEY = "polar.trailMotion";

export interface UseTrailMotionPreferenceReturn {
  /** True when the player may animate: no OS reduced-motion preference, or the reader forced it. */
  motionAllowed: boolean;
  reducedByOs: boolean;
  forced: boolean;
  setForced: (next: boolean) => void;
}

function readForced(): boolean {
  try {
    return typeof window !== "undefined" && window.sessionStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

export function useTrailMotionPreference(): UseTrailMotionPreferenceReturn {
  const reducedByOs = usePrefersReducedMotion();
  const [forced, setForcedState] = useState<boolean>(readForced);

  const setForced = useCallback((next: boolean) => {
    setForcedState(next);
    try {
      if (next) window.sessionStorage.setItem(STORAGE_KEY, "on");
      else window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // storage unavailable (private mode, blocked site data): keep the in-memory choice
    }
  }, []);

  return { motionAllowed: !reducedByOs || forced, reducedByOs, forced, setForced };
}
