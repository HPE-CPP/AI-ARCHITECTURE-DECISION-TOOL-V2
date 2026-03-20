"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getQuestionnaireOptions, submitQuestionnaire, QuestionnaireOptions } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, ChevronLeft, Loader2, AlertCircle, Check, FastForward } from "lucide-react";

export default function QuestionnaireForm() {
  const router = useRouter();
  const [optionsData, setOptionsData] = useState<QuestionnaireOptions | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    getQuestionnaireOptions()
      .then(setOptionsData)
      .catch((e) => setError("Failed to load generic options. Ensure backend is running."))
      .finally(() => setLoading(false));
  }, []);

  const signals = optionsData ? Object.entries(optionsData.signals) : [];
  const totalSteps = signals.length;

  const handleNext = () => {
    const [key, schema] = signals[currentStep];
    if (schema.required && !answers[key]) {
      setError("Please select an option to continue.");
      return;
    }
    setError(null);
    if (currentStep < totalSteps - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    setError(null);
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSkip = () => {
    setError(null);
    if (currentStep < totalSteps - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      handleSubmit();
    }
  };

  const handleChange = (key: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
    setError(null);
  };

  const handleSubmit = async () => {
    if (!optionsData) return;
    try {
      setSubmitting(true);
      setError(null);
      const provider = localStorage.getItem("llm_provider") || "openai";
      const result = await submitQuestionnaire(answers, provider);
      
      // Artificial delay for smooth UX
      setTimeout(() => {
        router.push(`/results/${result.analysis_id}`);
      }, 800);
      
    } catch (err: any) {
      setError(err.message || "Submission failed");
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center p-20 min-h-[400px]">
      <div className="w-16 h-16 relative flex items-center justify-center">
        <div className="absolute inset-0 rounded-full border-t-2 border-[color:var(--primary)] animate-spin" />
        <div className="absolute inset-2 rounded-full border-t-2 border-[color:var(--accent)] animate-spin animation-delay-150" />
      </div>
      <p className="mt-6 text-[color:var(--text-secondary)] font-medium blink">Loading Questionnaire...</p>
    </div>
  );

  if (!optionsData || signals.length === 0) return (
    <div className="glass-panel p-10 border-red-500/20 flex flex-col items-center gap-4 text-red-400 rounded-3xl">
      <AlertCircle size={40} /> 
      <span className="font-semibold">{error || "Failed to load"}</span>
    </div>
  );

  const [currentKey, currentSchema] = signals[currentStep];
  const progressPercent = ((currentStep + 1) / totalSteps) * 100;

  return (
    <div className="w-full flex-col items-center relative gap-8">
      {/* Progress Section */}
      <div className="w-full max-w-3xl mx-auto mb-8">
        <div className="flex justify-between items-center mb-3 text-sm font-medium text-[color:var(--text-secondary)] px-2">
          <span>Question {currentStep + 1} of {totalSteps}</span>
          <span className="text-[color:var(--primary)]">{Math.round(progressPercent)}%</span>
        </div>
        <div className="w-full h-px bg-[color:var(--surface)] overflow-hidden border border-[color:var(--border)] relative bg-[color:var(--background)]">
          <motion.div 
            className="h-full absolute top-0 left-0 bg-[color:var(--text-primary)]"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          />
        </div>
      </div>

      <div className="w-full max-w-3xl mx-auto glass-panel p-8 md:p-12 relative overflow-hidden min-h-[450px] flex flex-col shadow-2xl">
        <AnimatePresence mode="popLayout" initial={false}>
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="mb-8 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-500 flex items-center gap-3 text-sm font-medium"
            >
              <AlertCircle size={20} className="shrink-0" />
              <p>{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.div 
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
            className="flex-1 flex flex-col"
          >
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <span className={`text-xs font-bold uppercase tracking-widest px-3 py-1 border ${
                  currentSchema.required 
                    ? "bg-[color:var(--surface)] text-[color:var(--text-primary)] border-[color:var(--border)]" 
                    : "bg-[color:var(--background)] text-[color:var(--text-secondary)] border-[color:var(--border)]"
                }`}>
                  {currentSchema.required ? "Required" : "Optional"}
                </span>
                <span className="text-[color:var(--text-secondary)] text-sm font-bold tracking-widest uppercase">
                  Signal {currentStep + 1}
                </span>
              </div>
              
              <h2 className="text-3xl md:text-4xl font-bold mb-4 tracking-tight leading-tight">
                {currentKey.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
              </h2>
              <p className="text-lg text-[color:var(--text-secondary)] leading-relaxed">
                {currentSchema.description}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 mt-auto">
              {currentSchema.options.map((opt) => {
                const isSelected = answers[currentKey] === opt.value;
                return (
                  <motion.div 
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    key={opt.value}
                    onClick={() => handleChange(currentKey, opt.value)}
                    className={`
                      cursor-pointer p-4 md:p-5 border transition-all flex items-start gap-4 group
                      ${isSelected 
                        ? "border-[color:var(--text-primary)] bg-[color:var(--surface)]" 
                        : "border-[color:var(--border)] bg-[color:var(--background)] hover:border-[color:var(--text-secondary)] hover:bg-[color:var(--surface)]/50"
                      }
                    `}
                  >
                    <div className={`mt-0.5 shrink-0 w-5 h-5 border flex items-center justify-center transition-colors ${
                      isSelected ? "border-[color:var(--text-primary)] bg-[color:var(--text-primary)]" : "border-[color:var(--border)] group-hover:border-[color:var(--text-secondary)]"
                    }`}>
                      {isSelected && <Check size={14} className="text-[color:var(--background)]" />}
                    </div>
                    
                    <div className="flex-1">
                      <div className={`text-base font-bold mb-1 ${isSelected ? "text-[color:var(--primary)]" : "text-[color:var(--text-primary)]"}`}>
                        {opt.label.split(" (")[0]}
                      </div>
                      <div className={`text-sm ${isSelected ? "text-[color:var(--text-primary)] opacity-90" : "text-[color:var(--text-secondary)]"}`}>
                        {opt.label.split(" (")[1]?.replace(")", "") || ""}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </AnimatePresence>

        <div className="mt-12 flex items-center justify-between pt-6 border-t border-[color:var(--border)] relative z-10 w-full">
          <button 
            onClick={handleBack}
            disabled={currentStep === 0 || submitting}
            className="flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--background)] transition-all disabled:opacity-0"
          >
            <ChevronLeft size={20} /> Back
          </button>
          
          <div className="flex items-center gap-3">
            {!currentSchema.required && !answers[currentKey] && !submitting && (
               <button 
                onClick={handleSkip}
                className="flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-[color:var(--text-secondary)] relative hover:text-[color:var(--text-primary)] hover:bg-[color:var(--background)] transition-all group"
              >
                Skip <FastForward size={16} className="group-hover:translate-x-1 transition-transform" />
              </button>
            )}

            <button 
              onClick={handleNext}
              disabled={submitting}
              className={`
                flex items-center gap-2 px-8 py-3 rounded-none font-bold transition-all group border
                ${submitting 
                  ? "bg-[color:var(--surface)] border-[color:var(--border)] text-[color:var(--text-secondary)] cursor-not-allowed" 
                  : "bg-[color:var(--text-primary)] text-[color:var(--background)] border-[color:var(--text-primary)] hover:invert"
                }
              `}
            >
              {submitting ? (
                <><Loader2 className="animate-spin text-[color:var(--text-secondary)]" size={20} /> Analyzing...</>
              ) : currentStep === totalSteps - 1 ? (
                <>Submit <Check size={20} /></>
              ) : (
                <>Next <ChevronRight size={20} className="group-hover:translate-x-1 transition-transform" /></>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
