// Builds a .zip archive entirely in the browser (no server round-trip) so a case file can ship
// every export artifact in a single download. Compression uses fflate's synchronous writer.

import { strToU8, zipSync } from "fflate";

export interface ZipEntry {
  name: string;
  content: string | Uint8Array;
}

export function buildZip(entries: ZipEntry[]): Uint8Array {
  const files: Record<string, Uint8Array> = {};
  for (const { name, content } of entries) {
    files[name] = typeof content === "string" ? strToU8(content) : content;
  }
  return zipSync(files, { level: 6 });
}
