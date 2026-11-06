import type { Metadata } from "next";
import { Archivo_Narrow, JetBrains_Mono, Libre_Franklin } from "next/font/google";
import "./globals.css";

// A sports page: Franklin Gothic-style headlines and text, condensed agate for tables.
const franklin = Libre_Franklin({ variable: "--font-franklin", subsets: ["latin"] });
const agate = Archivo_Narrow({ variable: "--font-agate", subsets: ["latin"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FastBreak",
  description:
    "Ask anything about the NBA since 2015-16. Every answer shows the query it ran and the rows it came from.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${franklin.variable} ${agate.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full font-sans text-base leading-normal">{children}</body>
    </html>
  );
}
