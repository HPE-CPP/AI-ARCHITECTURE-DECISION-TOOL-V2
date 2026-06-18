"use client";
import React, { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { getQuestionnaireOptions, submitQuestionnaire, QuestionnaireOptions } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, ChevronLeft, Loader2, AlertCircle, Check, FastForward } from "lucide-react";
import { getProjectKey } from "@/lib/projects-store";

interface QuestionnaireFormProps {
  projectId?: string;
  onAnalysisStart?: (analysisId: string) => void;
}

export default function QuestionnaireForm({ projectId, onAnalysisStart }: QuestionnaireFormProps) {
  const router = useRouter();
  const [optionsData, setOptionsData] = useState<QuestionnaireOptions | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [resumed, setResumed] = useState(false);

  // Determine storage keys (per-project if projectId is set)
  const answersKey = projectId ? getProjectKey(projectId, "answers") : "questionnaire_answers";
  const stepKey = projectId ? getProjectKey(projectId, "questionnaire_step") : "questionnaire_step";
  const lastAnswersKey = projectId ? getProjectKey(projectId, "last_answers") : "questionnaire_last_answers";

  useEffect(() => {
    getQuestionnaireOptions()
      .then(setOptionsData)
      .catch(() => setError("Failed to load options. Ensure backend is running."))
      .finally(() => setLoading(false));

    // Restore answers from storage
    const saved = localStorage.getItem(answersKey);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setAnswers(parsed);
      } catch (e) {
        console.error("Failed to parse saved answers", e);
      }
    } else {
      // No in-progress answers — restore last submitted answers so edit mode
      // pre-highlights previously chosen options.
      const lastSaved = localStorage.getItem(lastAnswersKey);
      if (lastSaved) {
        try {
          const parsed = JSON.parse(lastSaved);
          setAnswers(parsed);
        } catch (e) {
          console.error("Failed to parse last submitted answers", e);
        }
      }
    }

    // Restore current step — so closing the tab mid-flow resumes where you left off
    const savedStep = localStorage.getItem(stepKey);
    if (savedStep) {
      const step = parseInt(savedStep, 10);
      if (!isNaN(step) && step > 0) {
        setCurrentStep(step);
        setResumed(true);
      }
    }

    if (projectId) {
      localStorage.removeItem("questionnaire_answers");
    }
  }, [answersKey, stepKey, lastAnswersKey, projectId]);

  // Sort signals: Required first, then Optional
  const sortedSignals = useMemo(() => {
    if (!optionsData) return [];
    return Object.entries(optionsData.signals).sort((a, b) => {
      const aReq = a[1].required ? 1 : 0;
      const bReq = b[1].required ? 1 : 0;
      return bReq - aReq;
    });
  }, [optionsData]);

  const totalSteps = sortedSignals.length;

  const goToStep = (step: number) => {
    setCurrentStep(step);
    localStorage.setItem(stepKey, String(step));
  };

  const handleNext = () => {
    const [key, schema] = sortedSignals[currentStep];
    if (schema.required && !answers[key]) {
      setError("This information is required to proceed.");
      return;
    }
    setError(null);
    setResumed(false); // dismiss resume banner when moving forward
    if (currentStep < totalSteps - 1) {
      goToStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    setError(null);
    if (currentStep > 0) goToStep(currentStep - 1);
  };

  const handleSkip = () => {
    setError(null);
    setResumed(false); // dismiss resume banner when skipping
    if (currentStep < totalSteps - 1) {
      goToStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  };

  // Toggle Logic: clicking same option removes it
  const handleChange = (key: string, value: string) => {
    setAnswers((prev) => {
      const newAnswers = { ...prev };
      if (prev[key] === value) {
        delete newAnswers[key];
      } else {
        newAnswers[key] = value;
      }
      localStorage.setItem(answersKey, JSON.stringify(newAnswers));
      return newAnswers;
    });
    setError(null);
  };

  const handleSubmit = async () => {
    if (!optionsData) return;
    try {
      setSubmitting(true);
      setError(null);
      const providerRaw = localStorage.getItem("llm_provider") || "openai";
      const provider = providerRaw === "groq" ? "openai" : providerRaw;
      const result = await submitQuestionnaire(answers, provider, projectId);

      // Notify parent of analysis ID for project tracking
      onAnalysisStart?.(result.analysis_id);

      // Save answers before clearing so edit mode can restore them later
      localStorage.setItem(lastAnswersKey, JSON.stringify(answers));
      // Clear saved progress now that submission succeeded
      localStorage.removeItem(answersKey);
      localStorage.removeItem(stepKey);

      // Per-project storage
      if (projectId) {
        localStorage.setItem(getProjectKey(projectId, "analysisId"), result.analysis_id);
        localStorage.setItem(getProjectKey(projectId, "mode"), "questionnaire");
      }

      setTimeout(() => {
        const qs = new URLSearchParams({ mode: "questionnaire" });
        if (projectId) qs.append("projectId", projectId);
        router.push(`/results/${result.analysis_id}?${qs.toString()}`);
      }, 800);

    } catch (err: unknown) {
      console.error("[Questionnaire] Submit failed:", err);
      setError("Unable to submit your answers. Please try again.");
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-[300px]">
      <Loader2 className="animate-spin text-[color:var(--primary)]" size={40} />
      <p className="mt-4 text-[color:var(--text-secondary)] font-medium">Loading...</p>
    </div>
  );

  if (!optionsData || sortedSignals.length === 0) return (
    <div className="glass-panel p-6 border-red-500/20 flex flex-col items-center gap-3 text-red-400 rounded-full">
      <AlertCircle size={24} />
      <span className="text-sm font-semibold">{error || "Failed to load"}</span>
    </div>
  );

  const [currentKey, currentSchema] = sortedSignals[currentStep];
  const progressPercent = ((currentStep + 1) / totalSteps) * 100;

  const handleStartOver = () => {
    localStorage.removeItem(answersKey);
    localStorage.removeItem(stepKey);
    localStorage.removeItem(lastAnswersKey);
    setAnswers({});
    setCurrentStep(0);
    setResumed(false);
    setError(null);
  };

  return (
    <div className="w-full flex flex-col items-center max-w-2xl mx-auto px-4">

      {/* Resume banner */}
      <AnimatePresence>
        {resumed && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="w-full mb-4 flex items-center justify-between gap-3 px-4 py-2.5 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--border)] text-sm"
          >
            <span className="text-[color:var(--text-secondary)] font-medium">
              Resuming from question {currentStep + 1}
            </span>
            <button
              onClick={handleStartOver}
              className="text-xs font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors shrink-0"
            >
              Start over
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Compact Progress Bar */}
      <div className="w-full mb-4">
        <div className="flex justify-between items-center mb-1 text-[10px] font-bold uppercase tracking-widest text-[color:var(--text-secondary)]">
          <span>{currentStep + 1} / {totalSteps}</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <div className="w-full h-1 bg-[color:var(--surface)] rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[color:var(--text-primary)]"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      <div className="w-full glass-panel p-5 md:p-7 rounded-[2.5rem] shadow-xl flex flex-col transition-all min-h-fit">
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-4 p-2 px-4 rounded-full bg-red-500/10 border border-red-500/20 text-red-500 flex items-center gap-2 text-xs font-medium"
            >
              <AlertCircle size={14} />
              <p>{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            className="flex flex-col"
          >
            <div className="mb-5">
              <div className="flex items-center gap-2 mb-2">
                <span className={`px-3 py-0.5 rounded-full text-[9px] font-bold uppercase border ${currentSchema.required
                    ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-[color:var(--text-primary)]"
                    : "bg-[color:var(--surface)] text-[color:var(--text-secondary)] border-[color:var(--border)]"
                  }`}>
                  {currentSchema.required ? "Required" : "Optional"}
                </span>
                <span className="text-[color:var(--text-secondary)] text-[9px] font-bold uppercase tracking-widest">
                  Signal {currentStep + 1}
                </span>
              </div>

              <h2 className="text-xl md:text-2xl font-bold tracking-tight mb-1">
                {currentKey.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
              </h2>
              <p className="text-sm text-[color:var(--text-secondary)] leading-snug">
                {currentSchema.description}
              </p>
            </div>

            <div className="flex flex-col gap-2.5 mb-6">
              {currentSchema.options.map((opt) => {
                const isSelected = answers[currentKey] === opt.value;
                const [title, desc] = opt.label.split(" (");
                return (
                  <motion.button
                    key={opt.value}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => handleChange(currentKey, opt.value)}
                    className={`
                      w-full px-6 py-3 rounded-full border text-left transition-all duration-200
                      ${isSelected
                        ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-[color:var(--text-primary)]"
                        : "bg-transparent border-[color:var(--border)] text-[color:var(--text-primary)] hover:border-[color:var(--text-secondary)] hover:bg-[color:var(--surface)]"
                      }
                    `}
                  >
                    <div className="flex flex-col">
                      <span className="text-sm font-bold leading-tight">{title}</span>
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
        </AnimatePresence>

        <div className="flex items-center justify-between pt-4 border-t border-[color:var(--border)] mt-auto">
          <button
            onClick={handleBack}
            disabled={currentStep === 0 || submitting}
            className="flex items-center gap-1 text-xs font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] disabled:invisible p-2"
          >
            <ChevronLeft size={16} /> Back
          </button>

          <div className="flex items-center gap-2">
            {!currentSchema.required && !answers[currentKey] && !submitting && (
              <button
                onClick={handleSkip}
                className="flex items-center gap-1 px-4 py-2 text-xs font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
              >
                Skip <FastForward size={14} />
              </button>
            )}

            <button
              id="questionnaire-next-btn"
              onClick={handleNext}
              disabled={submitting}
              className={`
                flex items-center gap-2 px-6 py-2.5 rounded-full font-bold text-xs transition-all
                ${submitting
                  ? "bg-[color:var(--surface)] text-[color:var(--text-secondary)] cursor-not-allowed border border-[color:var(--border)]"
                  : "bg-[color:var(--text-primary)] text-[color:var(--background)] hover:bg-[#444] dark:hover:bg-[#ccc]"
                }
              `}
            >
              {submitting ? (
                <><Loader2 className="animate-spin" size={14} /> Analyzing</>
              ) : currentStep === totalSteps - 1 ? (
                <>Analyze <Check size={14} /></>
              ) : (
                <>Next <ChevronRight size={14} /></>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}