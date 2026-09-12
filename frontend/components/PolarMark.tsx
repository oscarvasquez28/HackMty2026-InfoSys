import React from "react";

interface PolarMarkProps {
  className?: string;
}

export const PolarMark: React.FC<PolarMarkProps> = ({ className }) => (
  <svg
    aria-hidden="true"
    className={className}
    viewBox="0 0 32 32"
    fill="none"
  >
    <path d="M16 3 27 14H5L16 3Z" fill="currentColor" />
    <path
      d="m5 17 5.5 12h11L27 17H5Z"
      fill="currentColor"
      fillOpacity="0.22"
      stroke="currentColor"
      strokeWidth="1.25"
    />
    <path d="M10.5 17 16 29 21.5 17" stroke="currentColor" strokeWidth="1.25" />
  </svg>
);
