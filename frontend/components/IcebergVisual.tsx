import React from "react";

export const IcebergVisual: React.FC = () => (
  <figure className="relative mx-auto w-full max-w-[620px]" aria-labelledby="iceberg-caption">
    <div className="absolute left-1/2 top-[44%] h-52 w-52 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-500/10 blur-3xl" />
    <svg
      viewBox="0 0 720 660"
      role="img"
      aria-labelledby="iceberg-title iceberg-description"
      className="relative w-full"
      fill="none"
    >
      <title id="iceberg-title">Transaction risk below the surface</title>
      <desc id="iceberg-description">
        A technical wireframe iceberg with hidden transaction paths below a waterline.
      </desc>
      <defs>
        <linearGradient id="ice-fill" x1="360" y1="75" x2="360" y2="590" gradientUnits="userSpaceOnUse">
          <stop stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="0.48" stopColor="currentColor" stopOpacity="0.1" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="surface-line" x1="40" y1="0" x2="680" y2="0" gradientUnits="userSpaceOnUse">
          <stop stopColor="currentColor" stopOpacity="0" />
          <stop offset="0.2" stopColor="currentColor" stopOpacity="0.75" />
          <stop offset="0.8" stopColor="currentColor" stopOpacity="0.75" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>

      <g className="text-brand-500">
        <path d="M181 257 346 66l55 80 55 38 82 73H181Z" fill="url(#ice-fill)" stroke="currentColor" strokeWidth="1.3" />
        <path d="m181 257 85 233 103 109 91-77 78-265H181Z" fill="url(#ice-fill)" stroke="currentColor" strokeOpacity="0.65" strokeWidth="1.2" />
        <path d="m346 66-17 191M401 146l-72 111m127-73-39 73M266 490l63-233 40 342m91-77-43-265 121 0" stroke="currentColor" strokeOpacity="0.34" strokeWidth="1" />
        <path d="M181 257h357" stroke="currentColor" strokeOpacity="0.85" strokeWidth="1.4" />
        <path d="M42 257h636" stroke="url(#surface-line)" strokeWidth="1" />
        <path d="M42 267h636" stroke="url(#surface-line)" strokeOpacity="0.2" strokeWidth="1" strokeDasharray="3 7" />
      </g>

      <g className="iceberg-path text-brand-300" stroke="currentColor" strokeWidth="1.6" strokeDasharray="5 8">
        <path d="M274 365 390 326 468 412 352 493 274 365Z" />
        <path d="m390 326-8 150" />
      </g>
      <g className="text-brand-300" fill="currentColor">
        <circle cx="274" cy="365" r="4.5" />
        <circle cx="390" cy="326" r="4.5" />
        <circle cx="468" cy="412" r="4.5" />
        <circle cx="352" cy="493" r="4.5" />
        <circle cx="382" cy="476" r="4.5" />
      </g>
      <g className="text-muted" fill="currentColor" fontSize="11" letterSpacing="1.6" fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace">
        <text x="52" y="238">VISIBLE ACTIVITY</text>
        <text x="52" y="292">HIDDEN PATTERN</text>
        <text x="517" y="400">CIRCULAR FLOW</text>
        <text x="517" y="418" opacity="0.6">SIGNAL 01</text>
      </g>
      <path d="M475 411h31" className="text-muted" stroke="currentColor" strokeOpacity="0.55" />
    </svg>
    <figcaption id="iceberg-caption" className="sr-only">
      Polar reveals connected financial risk that is not visible in isolated transactions.
    </figcaption>
  </figure>
);
