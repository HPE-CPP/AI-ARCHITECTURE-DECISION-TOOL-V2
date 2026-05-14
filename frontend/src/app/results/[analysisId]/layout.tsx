import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analysis Results",
  description: "Your AI architecture recommendation with confidence scores, signal breakdown, and cost analysis.",
};

export default function ResultsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
