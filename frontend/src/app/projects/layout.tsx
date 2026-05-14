import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Projects",
  description: "Manage your AI architecture projects and start new analyses.",
};

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
