import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polar | Financial Risk Intelligence",
  description:
    "Polar reveals connected risk hidden inside complex transaction records through focused, graph-based financial investigation.",
  openGraph: {
    title: "Polar | See beneath the surface",
    description:
      "Financial pattern intelligence for focused investigations.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased selection:bg-brand-500 selection:text-brand-ink">
        {children}
      </body>
    </html>
  );
}
