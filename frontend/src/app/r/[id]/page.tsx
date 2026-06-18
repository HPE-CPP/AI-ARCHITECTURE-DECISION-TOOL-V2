"use client";
import React, { useEffect, useState, use, Suspense } from "react";
import { AnalysisResult } from "@/lib/api";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import { CostAnalysis } from "@/components/CostAnalysis";
import { DecisionPipeline } from "@/components/DecisionPipeline";
import { DecisionTrace } from "@/components/DecisionTrace";
import { AlertCircle, Loader2, ExternalLink } from "lucide-react";
import Link from "next/link";

// Fetch shared analysis — no auth token needed
async function getSharedAnalysis(id: string): Promise<AnalysisResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/v1/share/${id}`);
  if (!res.ok) throw new Error("Analysis not found or not available for sharing");
  return res.json();
}

function SharedResultsInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSharedAnalysis(id)
      .then(setResult)
      .catch((e) => { console.error("[SharedResults] Failed to load analysis:", e); setError("Unable to load this analysis."); })
      .finally(() => setLoading(false));
  }, [id]);

  // --- LOADING ---
  if (loading) {
    return (
      <div className="w-full min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="animate-spin text-[var(--text-secondary)]" size={32} />
          <p className="text-sm text-[var(--text-secondary)] font-medium">Loading shared analysis...</p>
        </div>
      </div>
    );
  }

  // --- ERROR ---
  if (error || !result) {
    return (
      <div className="w-full min-h-screen flex items-center justify-center px-4">
        <div className="glass-panel p-10 rounded-3xl text-center max-w-lg w-full">
          <div className="bg-red-500/10 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 border border-red-500/20">
            <AlertCircle className="text-red-500" size={36} />
          </div>
          <h2 className="text-2xl font-bold text-red-500 mb-3">Analysis Not Found</h2>
          <p className="text-[var(--text-secondary)] text-sm leading-relaxed mb-6">
            This analysis link may be invalid, or the analysis is still processing. Only completed analyses can be shared.
          </p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-[var(--text-primary)] text-[var(--background)] font-bold text-sm hover:opacity-90 transition-opacity"
          >
            Go to ArchGuide
          </Link>
        </div>
      </div>
    );
  }

  // --- SUCCESS ---
  return (
    <div className="w-full max-w-screen-xl mx-auto pt-24 pb-20 px-4 sm:px-6 lg:px-8 space-y-8">

      {/* Read-only banner */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-full border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text-secondary)]">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium">Shared analysis — read only</span>
        </div>
        <Link
          href="/"
          className="flex items-center gap-2 px-4 py-2.5 rounded-full border border-[var(--border)] bg-[var(--surface)] text-sm font-bold text-[var(--text-primary)] hover:bg-[var(--background)] transition-colors"
        >
          Try ArchGuide <ExternalLink size={13} />
        </Link>
      </div>

      {/* Full results — same components as normal results page */}
      <ResultsDashboard result={result} />

      {result.cost_analysis && (
        <CostAnalysis data={result.cost_analysis} result={result} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-start">
        <div className="lg:col-span-8">
          <DecisionPipeline result={result} />
        </div>
        <div className="lg:col-span-4">
          <div className="sticky top-24">
            <DecisionTrace trace={result.decision_trace || []} />
          </div>
        </div>
      </div>

      {/* Footer CTA */}
      <div className="glass-panel p-8 rounded-3xl text-center">
        <h3 className="text-2xl font-bold mb-2">Want to analyse your own project?</h3>
        <p className="text-[var(--text-secondary)] text-sm mb-6">
          Upload your requirements document and get an instant architecture recommendation.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-8 py-3 rounded-full bg-[var(--text-primary)] text-[var(--background)] font-bold hover:opacity-90 transition-opacity"
        >
          Start Free Analysis <ExternalLink size={16} />
        </Link>
      </div>
    </div>
  );
}

export default function SharedResultsPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={
      <div className="w-full min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-[var(--text-secondary)]" size={32} />
      </div>
    }>
      <SharedResultsInner params={params} />
    </Suspense>
  );
}
