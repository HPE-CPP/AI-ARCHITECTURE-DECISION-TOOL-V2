import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LenisProvider } from "@/components/LenisProvider";
import { Navbar } from "@/components/Navbar";
import { GlobalBackground } from "@/components/GlobalBackground";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "ArchGuide",
  description:
    "Enterprise-grade AI system for choosing between RAG, Fine-Tuning, CAG, and Hybrid architectures.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased min-h-screen flex flex-col bg-[color:var(--background)] text-[color:var(--text-primary)] overflow-x-hidden">
        <ThemeProvider>
          <LenisProvider>
            <GlobalBackground />

            <Navbar />

            <main className="flex-1 w-full">
              {/* Note: I removed the max-w-7xl constraint here. 
                  It is better to handle padding/width inside individual page components 
                  to allow for full-width sections like Hero or CTA.
              */}
              {children}
            </main>

            <Footer />
          </LenisProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}