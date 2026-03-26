"use client";
import React, { useEffect, useState, use, Suspense } from "react";
import { getAnalysis, submitFollowUp, AnalysisResult } from "@/lib/api";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import { DecisionTrace } from "@/components/DecisionTrace";
import { Loader2, ArrowRight, ArrowLeft, Search, Activity, HelpCircle, AlertCircle, FileText } from "lucide-react";
import { motion } from "framer-motion";
import { useRouter, useSearchParams } from "next/navigation";
import { updateProject } from "@/lib/projects-store";

function ResultsPageInner({ params }: { params: Promise<{ analysisId: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [followUpAnswers, setFollowUpAnswers] = useState<Record<string, string>>({});
  const [submittingFollowUp, setSubmittingFollowUp] = useState(false);

  // 1. Fetch data
  useEffect(() => {
    let interval: NodeJS.Timeout;

    const fetchResult = async () => {
      try {
        const data = await getAnalysis(resolvedParams.analysisId);
        setResult(data);

        if (data.status === "complete" || data.status === "error") {
          setLoading(false);
          clearInterval(interval);
        }
      } catch (err: any) {
        setError(err.message || "Failed to fetch analysis");
        setLoading(false);
        clearInterval(interval);
      }
    };

    fetchResult();
    interval = setInterval(fetchResult, 1500);

    return () => clearInterval(interval);
  }, [resolvedParams.analysisId]);

  // 2. Scroll to top + mark project completed when results arrive
  useEffect(() => {
    if (!loading && result?.status === "complete") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      // Mark project as completed
      if (projectId) {
        updateProject(projectId, {
          status: "completed",
          analysisId: resolvedParams.analysisId,
        });
      }
    }
  }, [loading, result?.status, projectId, resolvedParams.analysisId]);

  const handleFollowUpChange = (signal: string, val: string) => {
    setFollowUpAnswers(prev => ({ ...prev, [signal]: val }));
  };

  const handleFollowUpSubmit = async () => {
    try {
      setSubmittingFollowUp(true);
      const data = await submitFollowUp(resolvedParams.analysisId, followUpAnswers);
      setResult(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmittingFollowUp(false);
    }
  };

  // --- LOADING STATE ---
  if (loading || ["queued", "parsing", "extracting_signals", "scoring", "validating", "detecting_sections"].includes(result?.status || "")) {
    return (
      <div className="w-full min-h-screen pt-24 pb-12 px-4 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center text-center max-w-lg mb-12">
          <div className="relative w-24 h-24 mb-8 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-t-2 border-[color:var(--primary)] animate-spin" />
            <div className="absolute inset-2 rounded-full border-t-2 border-[color:var(--accent)] animate-spin animation-delay-150" />
            <Activity className="text-[color:var(--primary)] animate-pulse" size={32} />
          </div>
          <h2 className="text-4xl font-bold mb-4 tracking-tight drop-shadow-sm">Analyzing Architecture</h2>
          <p className="text-[color:var(--text-secondary)] text-lg leading-relaxed">
            Please wait while our engine deterministically evaluates patterns...
          </p>
        </div>

        {result?.decision_trace && (
          <div className="w-full max-w-3xl">
            <DecisionTrace trace={result.decision_trace} />
          </div>
        )}
      </div>
    );
  }

  // --- ERROR STATE ---
  if (error || result?.status === "error") {
    return (
      <div className="w-full min-h-screen pt-24 px-4 flex items-center justify-center">
        <div className="glass-panel p-10 rounded-3xl border-red-500/20 text-center max-w-lg shadow-2xl w-full">
          <div className="bg-red-500/10 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner border border-red-500/20">
            <AlertCircle className="text-red-500" size={40} />
          </div>
          <h2 className="text-3xl font-bold text-red-500 mb-4 tracking-tight">Analysis Failed</h2>
          <p className="text-[color:var(--text-secondary)] font-medium leading-relaxed">
            {error || result?.error || "Unknown error occurred"}
          </p>
          <button
            onClick={() => router.back()}
            className="mt-8 px-6 py-2 bg-red-500/20 text-red-500 rounded-lg hover:bg-red-500/30 transition-colors font-bold"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!result) return null;

  // --- SUCCESS RESULTS STATE ---
  return (
    <div className="w-full max-w-screen-2xl mx-auto pt-24 pb-20 px-4 sm:px-6 lg:px-8 space-y-8">

      {/* Back / Edit Button */}
      <div className="flex items-center justify-between w-full">
        <button
          onClick={() => {
            const modeKey = projectId ? `project_${projectId}_mode` : "analyze_mode";
            const currentMode = localStorage.getItem(modeKey);
            const base = projectId ? `/analyze?projectId=${projectId}` : "/analyze";

            if (currentMode === "upload") {
              router.push(base);
            } else {
              // Pre-fill questionnaire answers
              const answersKey = projectId ? `project_${projectId}_answers` : "questionnaire_answers";
              if (result?.signals) {
                const answers: Record<string, string> = {};
                Object.entries(result.signals).forEach(([key, sig]) => {
                  if (sig.value) answers[key] = sig.value;
                });
                localStorage.setItem(answersKey, JSON.stringify(answers));
              }
              if (!projectId) localStorage.setItem("analyze_mode", "questionnaire");
              router.push(base);
            }
          }}
          className="group flex items-center gap-2 text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors font-medium"
        >
          <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
          Edit Inputs
        </button>

        {projectId && (
          <button
            onClick={() => router.push("/projects")}
            className="group flex items-center gap-2 text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors font-medium text-sm"
          >
            My Projects
            <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
          </button>
        )}
      </div>

      <ResultsDashboard result={result} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-start">
        <div className="lg:col-span-8 space-y-10 min-w-0">

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-panel p-6 sm:p-8 rounded-[2rem] overflow-hidden w-full shadow-sm"
          >
            <h3 className="text-2xl font-bold mb-6 tracking-tight flex items-center gap-3">
              <span className="p-2 rounded-xl bg-[color:var(--text-primary)] text-[color:var(--background)]">
                <Search size={20} />
              </span>
              Extracted Signals
            </h3>

            <div className="w-full overflow-x-auto rounded-xl border border-[color:var(--border)]">
              <table className="w-full text-left border-collapse min-w-[600px]">
                <thead className="bg-[color:var(--surface)]">
                  <tr className="border-b border-[color:var(--border)] text-[color:var(--text-secondary)] text-xs sm:text-sm uppercase tracking-wider">
                    <th className="py-4 px-4 sm:px-6 font-bold">Signal</th>
                    <th className="py-4 px-4 sm:px-6 font-bold">Value</th>
                    <th className="py-4 px-4 sm:px-6 font-bold min-w-[150px]">Confidence</th>
                    <th className="py-4 px-4 sm:px-6 font-bold">Source Context</th>
                  </tr>
                </thead>
                <tbody className="bg-[color:var(--background)]">
                  {Object.entries(result.signals || {}).map(([key, sig]) => (
                    <tr key={key} className={`border-b border-[color:var(--border)]/50 transition-colors group ${!sig.value ? "bg-red-500/5 hover:bg-red-500/10" : "hover:bg-[color:var(--surface)]"}`}>
                      <td className="py-4 px-4 sm:px-6 font-bold text-xs sm:text-sm uppercase tracking-widest text-[color:var(--text-secondary)]">
                        {key.replace(/_/g, " ")}
                      </td>
                      <td className="py-4 px-4 sm:px-6 font-bold text-sm">
                        {sig.value ? (
                          <span className="text-[color:var(--text-primary)]">{sig.value.replace(/_/g, " ")}</span>
                        ) : (
                          <span className="text-red-500 flex items-center gap-1 text-xs"><AlertCircle size={14} /> MISSING</span>
                        )}
                      </td>
                      <td className="py-4 px-4 sm:px-6">
                        {sig.value && (
                          <div className="flex items-center gap-3">
                            <div className="text-xs font-bold w-8 text-right">{(sig.confidence * 100).toFixed(0)}%</div>
                            <div className="flex-1 h-1.5 rounded-full bg-[color:var(--surface)] border border-[color:var(--border)] overflow-hidden">
                              <div className={`h-full rounded-full ${sig.confidence > 0.7 ? "bg-emerald-500" : sig.confidence > 0.4 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${sig.confidence * 100}%` }} />
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-4 sm:px-6">
                        {sig.source_text ? (
                          <div className="text-xs text-[color:var(--text-secondary)] italic max-w-[200px] xl:max-w-xs truncate cursor-help group-hover:text-[color:var(--text-primary)] transition-colors relative" title={sig.source_text}>
                            "{sig.source_text}"
                          </div>
                        ) : (
                          <span className="text-xs text-[color:var(--text-muted)]">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>

          {/* FollowUp Questions */}
          {result.followup_questions && result.followup_questions.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-8 md:p-12 rounded-[2rem] relative overflow-hidden group shadow-lg border-[color:var(--border)]"
            >
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 blur-[80px] pointer-events-none rounded-full" />

              <h3 className="text-3xl font-bold mb-3 tracking-tight flex items-center gap-3">
                <span className="p-2 rounded-2xl bg-[color:var(--text-primary)] text-[color:var(--background)]"><HelpCircle size={28} /></span>
                Refine Architecture
              </h3>
              <p className="text-lg text-[color:var(--text-secondary)] mb-10 font-medium">
                Answer these follow-ups on missing signals to increase recommendation certainty.
              </p>

              <div className="space-y-8 relative z-10">
                {result.followup_questions.map((q, i) => (
                  <div key={q.signal} className="p-8 rounded-3xl bg-[color:var(--surface)] border border-[color:var(--border)] shadow-sm">
                    <div className="mb-6">
                      <h4 className="font-bold text-xl tracking-tight text-[color:var(--text-primary)] mb-2">{q.question}</h4>
                      {q.context && (
                        <div className="flex items-start gap-2 p-3 rounded-xl bg-[color:var(--background)] border border-[color:var(--border)] mt-3">
                          <FileText size={16} className="text-[color:var(--text-secondary)] shrink-0 mt-0.5" />
                          <p className="text-sm text-[color:var(--text-secondary)] italic font-medium">"{q.context}"</p>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                      {q.options.map(opt => {
                        const isSelected = followUpAnswers[q.signal] === opt.value;
                        return (
                          <label
                            key={opt.value}
                            className={`
                    flex flex-col p-4 rounded-xl border-2 cursor-pointer transition-all select-none
                    ${isSelected
                                ? "border-[color:var(--text-primary)] bg-[color:var(--surface)] text-[color:var(--text-primary)] shadow-md"
                                : "border-[color:var(--border)] bg-[color:var(--background)] hover:border-[color:var(--text-secondary)] hover:bg-[color:var(--surface)] text-[color:var(--text-primary)]"
                              }
                  `}
                            // Use onClick on the label to intercept the click even if the radio is already checked
                            onClick={(e) => {
                              e.preventDefault(); // Prevent double triggers from label + input
                              const newValue = isSelected ? "" : opt.value;
                              handleFollowUpChange(q.signal, newValue);
                            }}
                          >
                            <input
                              type="radio"
                              name={q.signal}
                              value={opt.value}
                              checked={isSelected}
                              readOnly // Managed via onClick on the parent label
                              className="sr-only"
                            />
                            <span className="font-bold text-base leading-snug mb-1">{opt.label.split("(")[0]}</span>
                            <span className={`text-xs font-medium ${isSelected ? "opacity-90" : "text-[color:var(--text-secondary)]"}`}>{opt.label.split("(")[1]?.replace(")", "")}</span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-10 flex justify-end">
                <button
                  onClick={handleFollowUpSubmit}
                  disabled={submittingFollowUp || Object.keys(followUpAnswers).filter(k => followUpAnswers[k]).length === 0}
                  className="flex items-center gap-3 px-10 py-4 rounded-full bg-white text-black border border-gray-200 font-bold text-lg hover:bg-gray-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed group/btn shadow-sm"
                >
                  {submittingFollowUp ? (
                    <>
                      <Loader2 className="animate-spin text-black" size={20} />
                      Updating...
                    </>
                  ) : (
                    "Update Recommendation"
                  )}
                  <ArrowRight size={20} className="group-hover/btn:translate-x-1 transition-transform" />
                </button>
              </div>
            </motion.div>
          )}
        </div>

        <div className="lg:col-span-4 w-full relative">
          <div className="sticky top-24 w-full">
            <DecisionTrace trace={result.decision_trace || []} />
          </div>
        </div>

      </div>
    </div>
  );
}

export default function ResultsPage({ params }: { params: Promise<{ analysisId: string }> }) {
  return (
    <Suspense fallback={
      <div className="w-full min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-t-[color:var(--text-primary)] border-[color:var(--border)] animate-spin" />
      </div>
    }>
      <ResultsPageInner params={params} />
    </Suspense>
  );
}