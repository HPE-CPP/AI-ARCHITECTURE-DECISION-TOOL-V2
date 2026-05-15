"use client";
import dynamic from "next/dynamic";

const GlobalBackground = dynamic(
  () => import("@/components/GlobalBackground").then(m => ({ default: m.GlobalBackground })),
  { ssr: false }
);

export function GlobalBackgroundLoader() {
  return <GlobalBackground />;
}
