const caseVar = (name) => `rgb(var(--case-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#080A0D",
        surface: "#11151B",
        "surface-deep": "#0A0D11",
        "surface-raised": "#191F28",
        "surface-blue": "#101C25",
        "surface-border": "#293240",
        foreground: "#F2F6FA",
        muted: "#A0ADBD",
        status: {
          success: "#92C9AA",
          warning: "#E2B978",
          danger: "#EB999B",
        },
        brand: {
          ink: "#061017",
          50: "#EAF7FF",
          300: "#A6DEFF",
          500: "#79C7F5",
          600: "#389DDD",
        },
        // Case file tokens resolve through CSS variables so the same components render light in the
        // printable document (.case-paper) and in the portal palette inside the guided tour
        // (.case-tour). Values live in app/globals.css.
        paper: {
          DEFAULT: caseVar("paper"),
          raised: caseVar("paper-raised"),
          border: caseVar("paper-border"),
          ink: caseVar("paper-ink"),
          muted: caseVar("paper-muted"),
          sheet: caseVar("paper-sheet"),
        },
        evidence: {
          proven: caseVar("proven"),
          "proven-soft": caseVar("proven-soft"),
          probable: caseVar("probable"),
          "probable-soft": caseVar("probable-soft"),
          reconciled: caseVar("reconciled"),
          "reconciled-soft": caseVar("reconciled-soft"),
          held: caseVar("held"),
          "held-soft": caseVar("held-soft"),
          neutral: caseVar("neutral"),
          "neutral-soft": caseVar("neutral-soft"),
          on: caseVar("evidence-on"),
        },
      },
      boxShadow: {
        panel: "0 24px 80px rgba(0, 0, 0, 0.28)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(121, 199, 245, 0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(121, 199, 245, 0.035) 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid-pattern": "28px 28px",
      },
    },
  },
  plugins: [],
};
