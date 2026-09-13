"use client";

// A block that fades and rises into place the first time the reader scrolls to it.

import React from "react";
import { useRevealOnView } from "@/hooks/useRevealOnView";

interface TourRevealProps {
  id?: string;
  className?: string;
  children: React.ReactNode;
}

export const TourReveal: React.FC<TourRevealProps> = ({ id, className, children }) => {
  const { ref, revealed } = useRevealOnView<HTMLDivElement>();
  return (
    <div ref={ref} id={id} data-reveal={revealed ? "shown" : "hidden"} className={className}>
      {children}
    </div>
  );
};
