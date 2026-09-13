import React from "react";
import {
  POLAR_BRAND_COLORS,
  POLAR_MARK_BASE_PATH,
  POLAR_MARK_CAP_PATH,
  POLAR_MARK_VIEWBOX,
} from "@/lib/brand";

interface PolarMarkProps {
  className?: string;
}

export const PolarMark: React.FC<PolarMarkProps> = ({ className }) => (
  <svg aria-hidden="true" className={className} viewBox={POLAR_MARK_VIEWBOX} fill="none">
    <path d={POLAR_MARK_CAP_PATH} fill={POLAR_BRAND_COLORS.ice} />
    <path d={POLAR_MARK_BASE_PATH} fill={POLAR_BRAND_COLORS.blue} />
  </svg>
);
