import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Bricolage_Grotesque, JetBrains_Mono, Public_Sans } from "next/font/google";
import "./globals.css";

const sans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-public",
});

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Computer-use optimisation",
  description:
    "How the browser tool got faster, how each arm runs a task, and the probe numbers behind it.",
};

export const viewport: Viewport = {
  themeColor: "#eef1f6",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
