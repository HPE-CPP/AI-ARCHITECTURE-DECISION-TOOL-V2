"use client";
import React, { useEffect, useState, use } from "react";
import { getAnalysis, submitFollowUp, AnalysisResult } from "@/lib/api";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import { DecisionTrace } from "@/components/DecisionTrace";
import { Loader2, ArrowRight, Search, Activity, HelpCircle, AlertCircle, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function ResultsPage({ params }: { params: Promise<{ analysisId: string }> }) {
  const resolvedParams = use(params);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [followUpAnswers, setFollowUpAnswers] = useState<Record<string, string>>({});
  const [submittingFollowUp, setSubmittingFollowUp] = useState(false);

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

  const handleFollowUpChange = (signal: string, val: string) => {
    setFollowUpAnswers(prev => ({ ...prev, [signal]: val }));
  };

  const handleFollowUpSubmit = async () => {
    try {
      setSubmittingFollowUp(true);
      const data = await submitFollowUp(resolvedParams.analysisId, followUpAnswers);
      setResult(data);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmittingFollowUp(false);
    }
  };

  if (loading || result?.status === "queued" || result?.status === "parsing" || result?.status === "extracting_signals" || result?.status === "scoring" || result?.status === "validating" || result?.status === "detecting_sections") {
    return (
      <div className="w-full min-h-[70vh] flex flex-col items-center justify-center p-4">
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
        
        {/* Render trace while loading to show progress */}
        {result?.decision_trace && (
          <div className="w-full max-w-2xl translate-y-4">
            <DecisionTrace trace={result.decision_trace} />
          </div>
        )}
      </div>
    );
  }

  if (error || result?.status === "error") {
    return (
      <div className="w-full flex items-center justify-center p-12 min-h-[60vh]">
        <div className="glass-panel p-10 rounded-3xl border-red-500/20 text-center max-w-lg shadow-2xl">
          <div className="bg-red-500/10 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner border border-red-500/20">
            <AlertCircle className="text-red-500" size={40} />
          </div>
          <h2 className="text-3xl font-bold text-red-500 mb-4 tracking-tight">Analysis Failed</h2>
          <p className="text-[color:var(--text-secondary)] font-medium leading-relaxed">{error || result?.error || "Unknown error occurred"}</p>
        </div>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="w-full space-y-12 pb-16">
      <ResultsDashboard result={result} />

      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Main View Area */}
        <div className="flex-1 w-full space-y-12">
          
          {/* Extracted Signals Table */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-panel p-8 rounded-[2rem] overflow-hidden"
          >
            <h3 className="text-2xl font-bold mb-6 tracking-tight flex items-center gap-3">
              <span className="p-2 rounded-xl bg-[color:var(--text-primary)] text-[color:var(--background)]"><Search size={20} /></span>
              Extracted Signals
            </h3>
            
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[600px]">
                <thead>
                  <tr className="border-b border-[color:var(--border)] text-[color:var(--text-secondary)] text-sm uppercase tracking-wider">
                    <th className="py-4 px-4 font-bold">Signal</th>
                    <th className="py-4 px-4 font-bold">Value</th>
                    <th className="py-4 px-4 font-bold min-w-[150px]">Confidence</th>
                    <th className="py-4 px-4 font-bold">Source Context</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.signals || {}).map(([key, sig]) => (
                    <tr key={key} className={`border-b border-[color:var(--border)]/50 transition-colors group ${!sig.value ? "bg-red-500/5 hover:bg-red-500/10" : "hover:bg-[color:var(--surface)]"}`}>
                      <td className="py-4 px-4 font-bold text-sm uppercase tracking-widest text-[color:var(--text-secondary)]">
                        {key.replace(/_/g, " ")}
                      </td>
                      <td className="py-4 px-4 font-bold">
                        {sig.value ? (
                          <span className="text-[color:var(--text-primary)]">{sig.value.replace(/_/g, " ")}</span>
                        ) : (
                          <span className="text-red-500 flex items-center gap-1 text-xs"><AlertCircle size={14}/> MISSING</span>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        {sig.value && (
                          <div className="flex items-center gap-3">
                            <div className="text-xs font-bold w-8 text-right">{(sig.confidence * 100).toFixed(0)}%</div>
                            <div className="flex-1 h-1.5 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] overflow-hidden">
                              <div className={`h-full rounded-full ${sig.confidence > 0.7 ? "bg-emerald-500" : sig.confidence > 0.4 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${sig.confidence * 100}%` }} />
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        {sig.source_text ? (
                          <div className="text-xs text-[color:var(--text-secondary)] italic max-w-xs truncate cursor-help group-hover:text-[color:var(--text-primary)] transition-colors relative" title={sig.source_text}>
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
                          >
                            <input 
                              type="radio" 
                              name={q.signal} 
                              value={opt.value} 
                              checked={isSelected}
                              onChange={(e) => handleFollowUpChange(q.signal, e.target.value)}
                              className="sr-only" 
                            />
                            <span className="font-bold text-base leading-snug mb-1">{opt.label.split("(")[0]}</span>
                            <span className={`text-xs font-medium ${isSelected ? "opacity-90" : "text-[color:var(--text-secondary)]"}`}>{opt.label.split("(")[1]?.replace(")","")}</span>
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
                  disabled={submittingFollowUp || Object.keys(followUpAnswers).length === 0}
                  className="flex items-center gap-3 px-10 py-4 rounded-none border border-[color:var(--text-primary)] bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-lg hover:invert transition-all disabled:opacity-50 disabled:cursor-not-allowed group/btn"
                >
                  {submittingFollowUp ? <><Loader2 className="animate-spin text-[color:var(--background)]" size={20}/> Updating...</> : "Update Recommendation"}
                  <ArrowRight size={20} className="group-hover/btn:translate-x-1 transition-transform" />
                </button>
              </div>
            </motion.div>
          )}
        </div>

        {/* Sidebar */}
        <div className="w-full lg:w-96 flex-shrink-0">
          <DecisionTrace trace={result.decision_trace || []} />
        </div>
      </div>
    </div>
  );
}
