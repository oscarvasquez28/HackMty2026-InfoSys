import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Forensic Auditor | Hub Pericial AML de Alta Precisión",
  description:
    "Plataforma pericial para detección determinista de grafos de lavado de dinero, streaming de razonamiento pericial y dictamen por voz.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="antialiased selection:bg-emerald-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
