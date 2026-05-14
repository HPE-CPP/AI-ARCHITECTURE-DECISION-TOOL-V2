import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analyze",
  description: "Upload a requirements document or answer guided questions to get your AI architecture recommendation.",
};

export default function AnalyzeLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
