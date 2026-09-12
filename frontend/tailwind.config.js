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
        paper: {
          DEFAULT: "#FBFAF7",
          raised: "#F2EFE8",
          border: "#D8D2C6",
          ink: "#161B22",
          muted: "#5A6270",
        },
        evidence: {
          proven: "#8E1B1F",
          "proven-soft": "#F6E1DF",
          probable: "#9A5A06",
          "probable-soft": "#FBEBD2",
          reconciled: "#1E6A3B",
          "reconciled-soft": "#DFF0E3",
          held: "#1C4F8C",
          "held-soft": "#E2EBF6",
          neutral: "#4B5563",
          "neutral-soft": "#ECEAE5",
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
