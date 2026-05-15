"use client";
import React from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, PenTool, History } from "lucide-react";
import type { AnalysisHistoryEntry } from "@/lib/projects-store";

const ARCH_SHORT: Record<string, string> = {
  "RAG": "RAG",
  "Fine-Tuning": "FT",
  "CAG": "CAG",
  "Hybrid": "HYB",
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface Props {
  entries: AnalysisHistoryEntry[];
  currentAnalysisId: string;
  projectId: string;
}

export function AnalysisHistory({ entries, currentAnalysisId, projectId }: Props) {
  const router = useRouter();

  if (entries.length < 2) return null;

  const visible = entries.slice(0, 8);

  return (
    <div className="w-full glass-panel border border-[color:var(--border)] rounded-[2rem] p-5 sm:p-6">
      <div className="flex items-center gap-2 mb-4">
        <History size={15} className="text-[color:var(--text-secondary)]" />
        <p className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
          Run History
        </p>
        <span className="ml-auto text-[10px] text-[color:var(--text-secondary)]">
          {entries.length} run{entries.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
        {visible.map((entry, idx) => {
          const isCurrent = entry.analysis_id === currentAnalysisId;
          const runNumber = entries.length - idx;
          const archShort = entry.recommended
            ? (ARCH_SHORT[entry.recommended] ?? entry.recommended)
            : "-";
          const ModeIcon = entry.mode === "upload" ? UploadCloud : PenTool;

          return (
            <button
              key={entry.analysis_id}
              disabled={isCurrent}
              onClick={() =>
                router.push(`/results/${entry.analysis_id}?projectId=${projectId}${entry.mode === "questionnaire" ? "&mode=questionnaire" : ""}`)
              }
              className={`flex-shrink-0 flex flex-col gap-1.5 px-4 py-3 rounded-2xl border transition-all text-left min-w-[120px] ${
                isCurrent
                  ? "border-[color:var(--text-primary)] bg-[color:var(--text-primary)]/10 cursor-default"
                  : "border-[color:var(--border)] bg-[color:var(--surface)] hover:border-[color:var(--text-primary)]/50 cursor-pointer active:scale-95"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`text-[9px] font-black px-1.5 py-0.5 rounded-full ${
                    isCurrent
                      ? "bg-[color:var(--text-primary)] text-[color:var(--background)]"
                      : "bg-[color:var(--border)] text-[color:var(--text-secondary)]"
                  }`}
                >
                  #{runNumber}
                </span>
                <ModeIcon size={10} className="text-[color:var(--text-secondary)]" />
              </div>
              <span className="text-sm font-black tracking-tight text-[color:var(--text-primary)]">
                {archShort}
              </span>
              {entry.confidence !== undefined && (
                <span className="text-[10px] font-semibold text-[color:var(--text-secondary)]">
                  {Math.round(entry.confidence * 100)}% conf.
                </span>
              )}
              <span className="text-[9px] text-[color:var(--text-secondary)] mt-0.5">
                {relativeTime(entry.created_at)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
