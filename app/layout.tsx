import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Figtree, IBM_Plex_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

const sans = Figtree({
  subsets: ["latin"],
  variable: "--font-figtree",
});

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex",
});

export const metadata: Metadata = {
  title: "Computer-use optimisation",
  description:
    "Where the work is stuck, what to do next, and what is still missing.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
