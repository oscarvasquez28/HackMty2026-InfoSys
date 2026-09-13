import React from "react";
import {
  POLAR_BRAND_COLORS,
  POLAR_LOGO_VIEWBOX,
  POLAR_MARK_BASE_PATH,
  POLAR_MARK_CAP_PATH,
  POLAR_WORDMARK_PATH,
} from "@/lib/brand";

interface PolarLogoProps {
  className?: string;
}

// Full lockup (iceberg mark + "polar" wordmark). Decorative: give the wrapping link an aria-label.
// Size it by height (e.g. "h-7 w-auto"); the viewBox keeps the aspect ratio.
export const PolarLogo: React.FC<PolarLogoProps> = ({ className }) => (
  <svg aria-hidden="true" className={className} viewBox={POLAR_LOGO_VIEWBOX} fill="none">
    <path d={POLAR_MARK_CAP_PATH} fill={POLAR_BRAND_COLORS.ice} />
    <path d={POLAR_MARK_BASE_PATH} fill={POLAR_BRAND_COLORS.blue} />
    <path d={POLAR_WORDMARK_PATH} fill={POLAR_BRAND_COLORS.blue} />
  </svg>
);
