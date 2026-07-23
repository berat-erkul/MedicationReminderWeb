import type { Metadata } from "next";
import { Fraunces, Source_Sans_3 } from "next/font/google";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
});

const body = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-source",
});

export const metadata: Metadata = {
  title: "Hatırlat · İlaç Paneli",
  description: "Aileler için self-hosted WhatsApp ilaç hatırlatma paneli",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body className={`${display.variable} ${body.variable} antialiased`}>
        <div className="shell" style={{ fontFamily: "var(--font-source), var(--font-body)" }}>
          <Sidebar />
          <main className="main" style={{ ["--font-display" as string]: "var(--font-fraunces), Georgia, serif" }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
