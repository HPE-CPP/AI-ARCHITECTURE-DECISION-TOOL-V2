import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LenisProvider } from "@/components/LenisProvider";
import { Navbar } from "@/components/Navbar";
import { GlobalBackground } from "@/components/GlobalBackground";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "ArchGuide — AI Architecture Intelligence Platform",
  description: "Choose between RAG, Fine-Tuning, CAG, and Hybrid AI architectures with confidence. Signal-based, deterministic, fully traceable recommendations in under 3 seconds.",
  keywords: "RAG, Fine-Tuning, CAG, AI architecture, LLM, enterprise, decision system",
  openGraph: {
    title: "ArchGuide — AI Architecture Intelligence",
    description: "Make the right AI architecture decision. Scored, traced, and justified.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased min-h-screen flex flex-col overflow-x-hidden"
        style={{ background: "var(--background)", color: "var(--text-primary)" }}>
        <ThemeProvider>
          <AuthProvider>
            <LenisProvider>
              <GlobalBackground />
              <div className="scan-line" />
              <Navbar />
              <main className="flex-1 w-full">
                {children}
              </main>
              <Footer />
            </LenisProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
