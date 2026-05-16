"use client";
import React, { useEffect, useState, useRef, use, Suspense, useMemo } from "react";
import { getAnalysis, submitFollowUp, AnalysisResult, getQuestionnaireOptions, QuestionnaireOptions } from "@/lib/api";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import { CostAnalysis } from "@/components/CostAnalysis";
import { DecisionPipeline } from "@/components/DecisionPipeline";
import { DecisionTrace } from "@/components/DecisionTrace";
import { Loader2, ArrowRight, ArrowLeft, Search, Activity, HelpCircle, AlertCircle, FileText, ShieldCheck, ShieldAlert, BookOpen, CheckCircle, ChevronLeft, ChevronRight, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, useSearchParams } from "next/navigation";
import { updateProject, updateAnalysisHistoryEntry, getAnalysisHistory, AnalysisHistoryEntry } from "@/lib/projects-store";
import { useAuth } from "@/lib/auth-context";
import { AnalysisHistory } from "@/components/AnalysisHistory";
import { ArchGuideChat } from "@/components/ArchGuideChat";

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

// Stages for document upload flow
const ANALYSIS_STAGES = [
  {
    statuses: ["queued", "detecting_sections", "parsing"],
    label: "Parsing Document",
    shortLabel: "Parsing",
    desc: "Identifying structure and content sections",
    Icon: FileText,
  },
  {
    statuses: ["extracting_signals"],
    label: "Extracting Signals",
    shortLabel: "Signals",
    desc: "Locating key technical requirements",
    Icon: Search,
  },
  {
    statuses: ["scoring"],
    label: "Scoring Architectures",
    shortLabel: "Scoring",
    desc: "Running deterministic scoring engine",
    Icon: Activity,
  },
  {
    statuses: ["validating"],
    label: "Validating Results",
    shortLabel: "Validating",
    desc: "Verifying consistency and confidence levels",
    Icon: ShieldCheck,
  },
] as const;

// Stages for guided questionnaire flow (synchronous — no document parsing)
const QUESTIONNAIRE_STAGES = [
  {
    statuses: ["queued", "processing"],
    label: "Processing Answers",
    shortLabel: "Processing",
    desc: "Converting your responses into analysis signals",
    Icon: BookOpen,
  },
  {
    statuses: ["scoring"],
    label: "Scoring Architectures",
    shortLabel: "Scoring",
    desc: "Running deterministic scoring engine",
    Icon: Activity,
  },
  {
    statuses: ["validating"],
    label: "Validating Results",
    shortLabel: "Validating",
    desc: "Verifying consistency and confidence levels",
    Icon: ShieldCheck,
  },
] as const;

type StageList = typeof ANALYSIS_STAGES | typeof QUESTIONNAIRE_STAGES;

function getStageIndex(status: string, stages: StageList): number {
  const idx = (stages as readonly { statuses: readonly string[] }[]).findIndex(s =>
    s.statuses.includes(status)
  );
  return idx === -1 ? 0 : idx;
}

// Time thresholds for document flow (seconds per stage: Parsing/Extracting/Scoring/Validating)
const STAGE_TIME_THRESHOLDS = [0, 14, 38, 54];

function getDisplayStageIndex(backendStatus: string, elapsedSeconds: number, stages: StageList): number {
  const backendIndex = getStageIndex(backendStatus, stages);
  let timeIndex = 0;
  for (let i = STAGE_TIME_THRESHOLDS.length - 1; i >= 0; i--) {
    if (elapsedSeconds >= STAGE_TIME_THRESHOLDS[i]) { timeIndex = i; break; }
  }
  return Math.max(backendIndex, Math.min(timeIndex, stages.length - 1));
}

function ResultsPageInner({ params }: { params: Promise<{ analysisId: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");
  const isQuestionnaire = searchParams.get("mode") === "questionnaire";
  const activeStages: StageList = isQuestionnaire ? QUESTIONNAIRE_STAGES : ANALYSIS_STAGES;

  // Wait for Firebase auth to finish restoring its state before the first
  // API call. Without this guard, a page refresh fires getAnalysis() while
  // auth.currentUser is still null (lazy Firebase not yet initialised),
  // causing the backend to return 401 → "Analysis Failed" error screen.
  const { loading: authLoading } = useAuth();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [followUpAnswers, setFollowUpAnswers] = useState<Record<string, string>>({});
  const [submittingFollowUp, setSubmittingFollowUp] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const loadingStartRef = useRef<number>(Date.now());
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryEntry[]>([]);
  const [resultReady, setResultReady] = useState(false);
  const [forcedStageIndex, setForcedStageIndex] = useState<number | null>(null);

  const [showEditOptions, setShowEditOptions] = useState(false);
  const [isEditingInputs, setIsEditingInputs] = useState(false);
  const [questionnaireOptions, setQuestionnaireOptions] = useState<QuestionnaireOptions | null>(null);
  const [editAnswers, setEditAnswers] = useState<Record<string, string>>({});
  const [currentEditStep, setCurrentEditStep] = useState(0);

  const sortedEditSignals = useMemo(() => {
    if (!questionnaireOptions) return [];
    return Object.entries(questionnaireOptions.signals).sort((a, b) => {
      const aReq = a[1].required ? 1 : 0;
      const bReq = b[1].required ? 1 : 0;
      return bReq - aReq;
    });
  }, [questionnaireOptions]);

  useEffect(() => {
    getQuestionnaireOptions()
      .then(setQuestionnaireOptions)
      .catch(err => console.error("Failed to load questionnaire options", err));
  }, []);

  // Load history on mount so returning to a completed result shows the panel immediately
  useEffect(() => {
    if (projectId) setAnalysisHistory(getAnalysisHistory(projectId));
  }, [projectId]);

  // 1. Fetch data with exponential backoff and a maximum retry cap
  // FIX FE-009: The flat 1.5s interval with no retry cap caused infinite polling
  // for stuck sessions. Now uses exponential backoff: 1.5s → 3s → 6s → max 15s,
  // and hard-stops after MAX_POLLS attempts (~3 minutes).
  useEffect(() => {
    // Don't start polling until Firebase auth has finished initialising.
    // On a hard refresh, auth.currentUser is null for ~200-500ms while
    // Firebase restores the session — firing the API call during this window
    // sends no token and the backend returns 401.
    if (authLoading) return;

    const MAX_POLLS = 40;
    let pollCount = 0;
    let timeoutRef: NodeJS.Timeout;
    let interval = 1500;
    const MAX_INTERVAL = 15000;

    const fetchResult = async () => {
      pollCount++;
      try {
        const data = await getAnalysis(resolvedParams.analysisId);
        setResult(data);

        if (data.status === "complete" || data.status === "error") {
          if (data.status === "error") {
            setLoading(false);
          } else if (isQuestionnaire) {
            // Questionnaire is synchronous — backend is already done.
            // Skip the stage animation and show results immediately.
            setLoading(false);
          } else {
            setResultReady(true); // trigger stage fast-forward before revealing results
          }
          return; // stop polling
        }
      } catch (err: any) {
        setError(err.message || "Failed to fetch analysis");
        setLoading(false);
        return; // stop polling on error
      }

      if (pollCount >= MAX_POLLS) {
        setError(
          "Analysis is taking unusually long. " +
          "Please check the backend or try again."
        );
        setLoading(false);
        return;
      }

      // Exponential backoff: double interval each time up to MAX_INTERVAL
      interval = Math.min(interval * 1.5, MAX_INTERVAL);
      timeoutRef = setTimeout(fetchResult, interval);
    };

    fetchResult();
    return () => clearTimeout(timeoutRef);
  }, [resolvedParams.analysisId, authLoading]);

  // 2. When result is ready, fast-forward through any unseen stages (700ms each) then reveal
  useEffect(() => {
    if (!resultReady) return;
    const currentStage = forcedStageIndex ?? getDisplayStageIndex(result?.status || "queued", elapsedSeconds, activeStages);
    const lastStage = activeStages.length - 1;
    if (currentStage >= lastStage) {
      const t = setTimeout(() => setLoading(false), 600);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setForcedStageIndex(currentStage + 1), 700);
    return () => clearTimeout(t);
  }, [resultReady, forcedStageIndex, result?.status, elapsedSeconds, activeStages]);

  // 3. Scroll to top + mark project completed + update history when results arrive
  useEffect(() => {
    if (!loading && result?.status === "complete") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      if (projectId) {
        updateProject(projectId, {
          status: "completed",
          analysisId: resolvedParams.analysisId,
        });
        updateAnalysisHistoryEntry(projectId, resolvedParams.analysisId, {
          recommended: result.recommended,
          confidence: result.confidence,
        });
        setAnalysisHistory(getAnalysisHistory(projectId));
      }
    }
  }, [loading, result?.status, projectId, resolvedParams.analysisId, result?.recommended, result?.confidence]);

  // 3. Elapsed-time counter — ticks every second while loading so the screen
  // never looks frozen even when the backend status hasn't changed.
  useEffect(() => {
    if (!loading) return;
    loadingStartRef.current = Date.now();
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - loadingStartRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [loading]);

  const handleFollowUpChange = (signal: string, val: string) => {
    setFollowUpAnswers(prev => ({ ...prev, [signal]: val }));
  };

  const handleFollowUpSubmit = async () => {
    try {
      setSubmittingFollowUp(true);
      setError(null); // clear previous errors
      const data = await submitFollowUp(resolvedParams.analysisId, followUpAnswers);
      setResult(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err: any) {
      // FIX: use component error state instead of native alert() which blocks the thread
      setError(err.message || "Failed to submit follow-up answers");
    } finally {
      setSubmittingFollowUp(false);
    }
  };

  const handleEditInputsClick = () => {
    setShowEditOptions(true)
  };

  const handleSelectQuestionnaire = () => {
    setShowEditOptions(false);
    if (!result?.signals) return;
    const initialAnswers: Record<string, string> = {};
    Object.entries(result.signals).forEach(([k, v]) => {
      if (v.value) initialAnswers[k] = v.value;
    });
    setEditAnswers(initialAnswers);
    setCurrentEditStep(0);
    setIsEditingInputs(true);
  };

  const handleEditChange = (key: string, val: string) => {
    setEditAnswers(prev => ({ ...prev, [key]: prev[key] === val ? "" : val }));
  };

  const handleSelectReupload = () => {
    setShowEditOptions(false);
    if (projectId) {
      router.push(`/projects/${projectId}/analyze?mode=upload`);
    } else {
      router.back();
    }
  };

  const handleEditSubmit = async () => {
    try {
      setSubmittingFollowUp(true);
      setError(null);
      const data = await submitFollowUp(resolvedParams.analysisId, editAnswers);
      setResult(data);
      setIsEditingInputs(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err: any) {
      setError(err.message || "Failed to update inputs");
    } finally {
      setSubmittingFollowUp(false);
    }
  };

  const handleEditNext = () => {
    if (currentEditStep < sortedEditSignals.length - 1) {
      setCurrentEditStep(prev => prev + 1);
    } else {
      handleEditSubmit();
    }
  };

  const handleEditBack = () => {
    if (currentEditStep > 0) {
      setCurrentEditStep(prev => prev - 1);
    } else {
      setIsEditingInputs(false);
    }
  };

  // --- LOADING STATE ---
  if (loading || ["queued", "processing", "parsing", "extracting_signals", "scoring", "validating", "detecting_sections"].includes(result?.status || "")) {
    const currentStatus = result?.status || "queued";
    const activeIndex = forcedStageIndex ?? getDisplayStageIndex(currentStatus, elapsedSeconds, activeStages);
    const activeStage = activeStages[activeIndex];
    const ActiveIcon = activeStage.Icon;

    return (
      <div className="w-full min-h-screen pt-24 pb-12 px-4 flex flex-col items-center justify-center">
        <div className="w-full max-w-2xl flex flex-col items-center text-center gap-12">

          {/* Spinning icon + current stage label */}
          <div className="flex flex-col items-center gap-5">
            <div className="relative w-20 h-20 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-t-2 border-[color:var(--primary)] animate-spin" />
              <div className="absolute inset-2 rounded-full border-t-2 border-[color:var(--accent)] animate-spin [animation-duration:1.8s]" />
              <ActiveIcon className="text-[color:var(--primary)] animate-pulse" size={28} />
            </div>
            <div>
              <div className="flex items-center justify-center gap-3 mb-2">
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">{activeStage.label}</h2>
                {elapsedSeconds > 0 && (
                  <span className="px-2.5 py-1 rounded-full bg-[color:var(--surface)] border border-[color:var(--border)] text-xs font-bold text-[color:var(--text-secondary)] tabular-nums">
                    {formatElapsed(elapsedSeconds)}
                  </span>
                )}
              </div>
              <p className="text-[color:var(--text-secondary)] text-base sm:text-lg font-medium">{activeStage.desc}</p>
            </div>

            {/* Reassurance message — only for document flow which can take minutes */}
            {!isQuestionnaire && elapsedSeconds >= 35 && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-500 text-xs font-semibold"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
                Still running - complex documents can take up to 3 minutes
              </motion.div>
            )}
          </div>

          {/* Progress pipeline — steps match the active flow (document or questionnaire) */}
          <div className="w-full px-2">
            <div className="flex items-start w-full">
              {activeStages.map((stage, index) => {
                const isCompleted = index < activeIndex;
                const isActive = index === activeIndex;
                const isPending = index > activeIndex;
                const StageIcon = stage.Icon;

                return (
                  <React.Fragment key={stage.label}>
                    <div className="flex flex-col items-center gap-2.5 flex-shrink-0">
                      {/* Circle */}
                      <div className={`
                        relative w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500
                        ${isCompleted ? "bg-[color:var(--text-primary)]" : ""}
                        ${isActive ? "border-2 border-[color:var(--primary)] bg-[color:var(--surface)]" : ""}
                        ${isPending ? "border border-[color:var(--border)] bg-[color:var(--surface)]" : ""}
                      `}>
                        {isActive && (
                          <div className="absolute inset-0 rounded-full border-2 border-[color:var(--primary)] animate-ping opacity-30" />
                        )}
                        {isCompleted ? (
                          <CheckCircle size={18} className="text-[color:var(--background)]" />
                        ) : (
                          <StageIcon
                            size={15}
                            className={
                              isActive
                                ? "text-[color:var(--primary)]"
                                : "text-[color:var(--text-secondary)] opacity-30"
                            }
                          />
                        )}
                      </div>

                      {/* Label */}
                      <span className={`
                        text-[10px] sm:text-xs font-bold text-center leading-tight max-w-[64px] sm:max-w-[80px] transition-colors duration-500
                        ${isCompleted ? "text-[color:var(--text-primary)]" : ""}
                        ${isActive ? "text-[color:var(--primary)]" : ""}
                        ${isPending ? "text-[color:var(--text-secondary)] opacity-30" : ""}
                      `}>
                        <span className="sm:hidden">{stage.shortLabel}</span>
                        <span className="hidden sm:inline">{stage.label}</span>
                      </span>
                    </div>

                    {/* Connector line */}
                    {index < activeStages.length - 1 && (
                      <div className={`
                        flex-1 h-px mx-2 sm:mx-3 mt-5 transition-colors duration-500
                        ${index < activeIndex ? "bg-[color:var(--text-primary)]" : "bg-[color:var(--border)]"}
                      `} />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Live activity log — shown as soon as the backend starts emitting trace steps */}
          {result?.decision_trace && result.decision_trace.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full glass-panel p-6 rounded-2xl"
            >
              <div className="flex items-center gap-2 mb-4">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-bold uppercase tracking-widest text-[color:var(--text-secondary)]">
                  Live Activity
                </span>
              </div>
              <DecisionTrace trace={result.decision_trace} />
            </motion.div>
          )}
        </div>
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
    <div className="w-full max-w-screen-xl mx-auto pt-24 pb-20 px-4 sm:px-6 lg:px-8 space-y-8">

      {/* Back / Edit Button */}
      <div className="flex items-center justify-between w-full">
        <button
          onClick={handleEditInputsClick}
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

      {showEditOptions ? (
        <div className="w-full flex flex-col items-center max-w-2xl mx-auto mt-10 min-h-[50vh]">
          <h2 className="text-3xl font-bold mb-8 text-center tracking-tight">How would you like to edit inputs?</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full">
            <button 
              onClick={handleSelectQuestionnaire} 
              className="p-8 rounded-[2rem] bg-[color:var(--surface)] border border-[color:var(--border)] hover:border-[color:var(--text-primary)] hover:shadow-lg transition-all flex flex-col items-center text-center gap-4 group"
            >
              <div className="w-16 h-16 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors">
                 <CheckCircle size={24} />
              </div>
              <h3 className="text-xl font-bold text-[color:var(--text-primary)]">Complete via Questionnaire</h3>
              <p className="text-[color:var(--text-secondary)] text-sm font-medium">Review extracted signals and answer questions to complete missing ones.</p>
            </button>
            <button 
              onClick={handleSelectReupload} 
              className="p-8 rounded-[2rem] bg-[color:var(--surface)] border border-[color:var(--border)] hover:border-[color:var(--text-primary)] hover:shadow-lg transition-all flex flex-col items-center text-center gap-4 group"
            >
              <div className="w-16 h-16 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors">
                 <FileText size={24} />
              </div>
              <h3 className="text-xl font-bold text-[color:var(--text-primary)]">Upload New Document</h3>
              <p className="text-[color:var(--text-secondary)] text-sm font-medium">Upload a new document to extract signals and re-run analysis.</p>
            </button>
          </div>
          <button 
            onClick={() => setShowEditOptions(false)} 
            className="mt-8 px-6 py-2 rounded-full text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--surface)] font-bold text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      ) : isEditingInputs && questionnaireOptions && sortedEditSignals.length > 0 ? (
        <div className="w-full flex flex-col items-center max-w-2xl mx-auto">
          {/* Progress Bar */}
          <div className="w-full mb-6">
            <div className="flex justify-between items-center mb-1 text-[10px] font-bold uppercase tracking-widest text-[color:var(--text-secondary)]">
              <span>{currentEditStep + 1} / {sortedEditSignals.length}</span>
              <span>{Math.round(((currentEditStep + 1) / sortedEditSignals.length) * 100)}%</span>
            </div>
            <div className="w-full h-1 bg-[color:var(--surface)] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-[color:var(--text-primary)]"
                initial={{ width: 0 }}
                animate={{ width: `${((currentEditStep + 1) / sortedEditSignals.length) * 100}%` }}
              />
            </div>
          </div>

          <div className="w-full glass-panel p-6 md:p-10 rounded-[2.5rem] shadow-xl flex flex-col min-h-fit">
            <AnimatePresence mode="wait">
              {(() => {
                const [key, schema] = sortedEditSignals[currentEditStep];
                const originalSignal = result.signals?.[key];
                const isMissing = !originalSignal?.value;
                const currentValue = editAnswers[key];
                const isSuccessfullyExtracted = originalSignal?.value && !isMissing;

                return (
                  <motion.div
                    key={currentEditStep}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    className="flex flex-col"
                  >
                    <div className="mb-6">
                      <div className="flex flex-wrap items-center gap-2 mb-3">
                        <span className={`px-3 py-0.5 rounded-full text-[9px] font-bold uppercase border ${
                          schema.required
                            ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-[color:var(--text-primary)]"
                            : "bg-[color:var(--surface)] text-[color:var(--text-secondary)] border-[color:var(--border)]"
                        }`}>
                          {schema.required ? "Required" : "Optional"}
                        </span>
                        
                        {isMissing && !currentValue && (
                          <span className="px-3 py-0.5 rounded-full bg-red-500/10 text-red-500 border border-red-500/20 text-[9px] font-bold uppercase flex items-center gap-1">
                            <AlertCircle size={10} /> Missing
                          </span>
                        )}
                        {isSuccessfullyExtracted && (
                          <span className="px-3 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-[9px] font-bold uppercase flex items-center gap-1">
                            <ShieldCheck size={10} /> Extracted
                          </span>
                        )}
                        <span className="text-[color:var(--text-secondary)] text-[9px] font-bold uppercase tracking-widest ml-auto">
                          Signal {currentEditStep + 1}
                        </span>
                      </div>

                      <h2 className="text-2xl md:text-3xl font-bold tracking-tight mb-2">
                        {key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                      </h2>
                      <p className="text-sm md:text-base text-[color:var(--text-secondary)] leading-relaxed">
                        {schema.description}
                      </p>
                    </div>

                    <div className="flex flex-col gap-3 mb-8">
                      {schema.options.map((opt) => {
                        const isSelected = currentValue === opt.value;
                        const [title, desc] = opt.label.split(" (");
                        return (
                          <motion.button
                            key={opt.value}
                            whileTap={{ scale: 0.99 }}
                            onClick={() => handleEditChange(key, opt.value)}
                            className={`
                              w-full px-6 py-4 rounded-full border text-left transition-all duration-200
                              ${isSelected
                                ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-[color:var(--text-primary)] shadow-md"
                                : "bg-transparent border-[color:var(--border)] text-[color:var(--text-primary)] hover:border-[color:var(--text-secondary)] hover:bg-[color:var(--surface)]"
                              }
                            `}
                          >
                            <div className="flex flex-col">
                              <span className="text-base font-bold leading-tight">{title}</span>
                              {desc && (
                                <span className={`text-xs mt-0.5 leading-tight opacity-70 ${isSelected ? "text-[color:var(--background)]" : "text-[color:var(--text-secondary)]"}`}>
                                  {desc.replace(")", "")}
                                </span>
                              )}
                            </div>
                          </motion.button>
                        );
                      })}
                    </div>
                  </motion.div>
                );
              })()}
            </AnimatePresence>

            <div className="flex items-center justify-between pt-6 border-t border-[color:var(--border)] mt-auto">
              <button
                onClick={handleEditBack}
                disabled={submittingFollowUp}
                className="flex items-center gap-1 text-xs font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] p-2 transition-colors"
              >
                <ChevronLeft size={16} /> {currentEditStep === 0 ? "Cancel" : "Back"}
              </button>

              <button
                onClick={handleEditNext}
                disabled={submittingFollowUp}
                className={`
                  flex items-center gap-2 px-8 py-3 rounded-full font-bold text-xs transition-all shadow-lg
                  ${submittingFollowUp
                    ? "bg-[color:var(--surface)] text-[color:var(--text-secondary)] cursor-not-allowed border border-[color:var(--border)]"
                    : "bg-[color:var(--text-primary)] text-[color:var(--background)] hover:scale-105"
                  }
                `}
              >
                {submittingFollowUp ? (
                  <><Loader2 className="animate-spin" size={14} /> Recalculating</>
                ) : currentEditStep === sortedEditSignals.length - 1 ? (
                  <>Recalculate <Activity size={14} /></>
                ) : (
                  <>Next Signal <ChevronRight size={14} /></>
                )}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          <ResultsDashboard result={result} />

      {/* Analysis History strip — shown when project has 2+ runs */}
      {projectId && analysisHistory.length >= 2 && (
        <AnalysisHistory
          entries={analysisHistory}
          currentAnalysisId={resolvedParams.analysisId}
          projectId={projectId}
        />
      )}

      {/* Cost Analysis Section */}
      {result.cost_analysis && (
        <CostAnalysis data={result.cost_analysis} result={result} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-start">
        <div className="lg:col-span-8 space-y-10 min-w-0">

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-panel p-6 sm:p-8 rounded-[2rem] overflow-hidden w-full shadow-sm"
          >
            <h3 className="text-2xl font-bold mb-2 tracking-tight flex items-center gap-3">
              <span className="p-2 rounded-xl bg-[color:var(--text-primary)] text-[color:var(--background)]">
                <Search size={20} />
              </span>
              Extracted Signals
            </h3>
            <p className="text-sm text-[color:var(--text-secondary)] mb-6 font-medium">
              Each signal is traced back to its source in the document to prevent hallucination.
            </p>

            <div className="space-y-4">
              {Object.entries(result.signals || {}).map(([key, sig]) => {
                const isMissing = !sig.value;
                const isVerified = sig.source_verified === true;
                const hasSource = !!sig.source_text;

                return (
                  <div
                    key={key}
                    className={`rounded-2xl border transition-colors ${
                      isMissing
                        ? "border-red-500/20 bg-red-500/5"
                        : "border-[color:var(--border)] bg-[color:var(--surface)] hover:border-[color:var(--text-secondary)]/30"
                    }`}
                  >
                    {/* Signal header row */}
                    <div className="flex flex-wrap items-center gap-3 px-5 py-4">
                      {/* Signal name */}
                      <span className="text-xs sm:text-sm font-bold uppercase tracking-widest text-[color:var(--text-secondary)] min-w-[140px]">
                        {key.replace(/_/g, " ")}
                      </span>

                      {/* Value badge */}
                      {sig.value ? (
                        <span className="px-3 py-1 rounded-lg bg-[color:var(--background)] border border-[color:var(--border)] text-sm font-bold text-[color:var(--text-primary)]">
                          {sig.value.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                        </span>
                      ) : (
                        <span className="px-3 py-1 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-bold text-red-500 flex items-center gap-1">
                          <AlertCircle size={12} /> MISSING
                        </span>
                      )}

                      {/* Confidence bar */}
                      {sig.value && (
                        <div className="flex items-center gap-2 ml-auto">
                          <div className="text-xs font-bold text-[color:var(--text-secondary)]">
                            {(sig.confidence * 100).toFixed(0)}%
                          </div>
                          <div className="w-20 h-1.5 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                sig.confidence > 0.7
                                  ? "bg-emerald-500"
                                  : sig.confidence > 0.4
                                  ? "bg-amber-500"
                                  : "bg-red-500"
                              }`}
                              style={{ width: `${sig.confidence * 100}%` }}
                            />
                          </div>

                          {/* Verification badge */}
                          {hasSource && (
                            isVerified ? (
                              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-[10px] font-bold uppercase" title="Source verified in document">
                                <ShieldCheck size={10} /> Verified
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-500 text-[10px] font-bold uppercase" title="Source could not be exactly matched in document">
                                <ShieldAlert size={10} /> Unverified
                              </span>
                            )
                          )}
                        </div>
                      )}
                    </div>

                    {/* Source traceability section */}
                    {hasSource && (
                      <div className="px-5 pb-4">
                        <div className="rounded-xl bg-[color:var(--background)] border border-[color:var(--border)] p-4">
                          <div className="flex items-start gap-3">
                            <BookOpen size={14} className="text-[color:var(--text-secondary)] shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs font-bold text-[color:var(--text-secondary)] uppercase tracking-wider mb-1.5">
                                Source
                                {sig.page_number > 0 && (
                                  <span className="ml-2 px-1.5 py-0.5 rounded bg-[color:var(--surface)] border border-[color:var(--border)] text-[10px] font-bold normal-case">
                                    Page {sig.page_number}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-[color:var(--text-primary)] italic leading-relaxed break-words select-text">
                                &ldquo;{sig.source_text}&rdquo;
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
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

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
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
          <div className="sticky top-24 w-full space-y-8">
            <DecisionPipeline result={result} />
            <DecisionTrace trace={result.decision_trace || []} />
          </div>
        </div>

      </div>
        </>
      )}

      {/* Floating chat widget */}
      {result.recommended && (
        <ArchGuideChat
          analysisId={resolvedParams.analysisId}
          result={result}
        />
      )}
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