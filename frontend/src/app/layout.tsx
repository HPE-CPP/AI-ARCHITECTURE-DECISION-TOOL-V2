import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { LenisProvider } from "@/components/LenisProvider";
import { Navbar } from "@/components/Navbar";
import { GlobalBackground } from "@/components/GlobalBackground";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/lib/auth-context";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata: Metadata = {
  title: {
    default: "ArchGuide",
    template: "%s | ArchGuide",
  },
  description:
    "Stop guessing between RAG, Fine-Tuning, CAG, and Hybrid. ArchGuide analyses your requirements and recommends the right AI architecture instantly.",
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
          <AuthProvider>
            <LenisProvider>
              <GlobalBackground />

              <Navbar />

              <main className="flex-1 w-full">
                <ErrorBoundary>
                  {children}
                </ErrorBoundary>
              </main>

              <Footer />
            </LenisProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}