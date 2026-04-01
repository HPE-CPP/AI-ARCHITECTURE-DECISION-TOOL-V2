"use client";
import React, { useMemo } from "react";
import { AnalysisResult } from "@/lib/api";
import { motion } from "framer-motion";
import {
  Upload, FileQuestion, Search, CheckCircle2, AlertTriangle,
  HelpCircle, BarChart3, Award, ArrowDown, GitBranch,
} from "lucide-react";

interface PipelineStep {
  icon: React.ReactNode;
  label: string;
  detail?: string;
  status: "success" | "warning" | "info" | "highlight";
}

export function DecisionPipeline({ result }: { result: AnalysisResult }) {
  const steps = useMemo<PipelineStep[]>(() => {
    const pipeline: PipelineStep[] = [];
    const trace = result.decision_trace || [];
    const signals = result.signals || {};
    const followups = result.followup_questions || [];

    // Step 1: Input method
    const hasUpload = trace.some(t => t.step === "upload");
    const hasQuestionnaire = trace.some(t => t.step === "questionnaire_input");

    if (hasUpload) {
      const parseStep = trace.find(t => t.step === "parse");
      const parseDetail = parseStep?.details || "";
      pipeline.push({
        icon: <Upload size={18} />,
        label: "Document Uploaded",
        detail: parseDetail || undefined,
        status: "success",
      });
    } else if (hasQuestionnaire) {
      pipeline.push({
        icon: <FileQuestion size={18} />,
        label: "Questionnaire Submitted",
        detail: "Manual signal input",
        status: "success",
      });
    }

    // Step 2: Signal extraction
    const totalSignals = Object.keys(signals).length;
    const extractedCount = Object.values(signals).filter(s => s.value).length;
    const missingCount = totalSignals - extractedCount;

    pipeline.push({
      icon: <Search size={18} />,
      label: "Signal Extraction",
      detail: `Analyzed ${totalSignals} decision factors`,
      status: "info",
    });

    // Step 3: Signals extracted
    pipeline.push({
      icon: <CheckCircle2 size={18} />,
      label: `${extractedCount} Signal${extractedCount !== 1 ? "s" : ""} Extracted`,
      detail: Object.entries(signals)
        .filter(([, s]) => s.value)
        .map(([k]) => k.replace(/_/g, " "))
        .slice(0, 4)
        .join(", ") + (extractedCount > 4 ? ` +${extractedCount - 4} more` : ""),
      status: "success",
    });

    // Step 4: Missing signals (if any)
    if (missingCount > 0) {
      pipeline.push({
        icon: <AlertTriangle size={18} />,
        label: `${missingCount} Signal${missingCount !== 1 ? "s" : ""} Missing`,
        detail: Object.entries(signals)
          .filter(([, s]) => !s.value)
          .map(([k]) => k.replace(/_/g, " "))
          .join(", "),
        status: "warning",
      });
    }

    // Step 5: Follow-up questions (if any)
    if (followups.length > 0) {
      pipeline.push({
        icon: <HelpCircle size={18} />,
        label: `${followups.length} Follow-up Question${followups.length !== 1 ? "s" : ""} Generated`,
        detail: followups.map(q => q.signal.replace(/_/g, " ")).join(", "),
        status: "info",
      });
    }

    // Step 6: Architecture scoring
    const archCount = result.ranking?.length || 4;
    pipeline.push({
      icon: <BarChart3 size={18} />,
      label: "Architecture Scoring",
      detail: `${archCount} architectures evaluated against ${extractedCount} signals`,
      status: "info",
    });

    // Step 7: Recommendation
    const recName = result.architecture_details?.[result.recommended!]?.full_name || result.recommended;
    const score = result.scores?.[result.recommended!];
    const conf = result.confidence;
    pipeline.push({
      icon: <Award size={18} />,
      label: "Recommendation Generated",
      detail: `${recName}${score ? ` — Score: ${score.toFixed(1)}/100` : ""}${conf ? ` — Confidence: ${(conf * 100).toFixed(0)}%` : ""}`,
      status: "highlight",
    });

    return pipeline;
  }, [result]);

  const stagger = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
  };

  const itemVariant = {
    hidden: { opacity: 0, x: -16, filter: "blur(4px)" },
    visible: {
      opacity: 1,
      x: 0,
      filter: "blur(0px)",
      transition: { type: "spring" as const, stiffness: 100, damping: 16 },
    },
  };

  const statusStyles: Record<string, { border: string; bg: string; text: string; icon: string; dot: string }> = {
    success:   { border: "border-emerald-500/25", bg: "bg-emerald-500/5",            text: "text-emerald-500", icon: "bg-emerald-500", dot: "bg-emerald-500" },
    warning:   { border: "border-amber-500/25",   bg: "bg-amber-500/5",              text: "text-amber-500",   icon: "bg-amber-500",   dot: "bg-amber-500" },
    info:      { border: "border-[var(--primary)]/20", bg: "bg-[var(--primary)]/5",  text: "text-[var(--primary)]", icon: "bg-[var(--primary)]", dot: "bg-[var(--primary)]" },
    highlight: { border: "border-[var(--primary)]/40", bg: "bg-[var(--primary)]/10", text: "text-[var(--primary)]", icon: "bg-[var(--primary)]", dot: "bg-[var(--primary)]" },
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5 }}
      className="glass-panel p-6 sm:p-8 rounded-[2rem] overflow-hidden shadow-sm"
    >
      <h3 className="text-2xl font-bold mb-8 tracking-tight flex items-center gap-3">
        <span className="p-2 rounded-xl bg-[var(--text-primary)] text-[var(--background)]">
          <GitBranch size={20} />
        </span>
        Decision Pipeline
      </h3>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.1 }}
        className="relative"
      >
        {steps.map((step, i) => {
          const s = statusStyles[step.status];
          const isLast = i === steps.length - 1;

          return (
            <React.Fragment key={i}>
              <motion.div variants={itemVariant} className="relative flex items-stretch gap-4">
                {/* Vertical rail */}
                <div className="flex flex-col items-center w-9 flex-shrink-0">
                  {/* Dot / icon */}
                  <div className={`relative z-10 w-9 h-9 rounded-full ${s.icon} text-white flex items-center justify-center shadow-lg ${isLast ? "ring-4 ring-[var(--primary)]/20" : ""}`}>
                    {step.icon}
                  </div>
                  {/* Connector line */}
                  {!isLast && (
                    <div className="flex-1 w-px bg-[var(--border)] min-h-[12px]" />
                  )}
                </div>

                {/* Content card */}
                <div className={`flex-1 mb-3 rounded-2xl border ${s.border} ${s.bg} p-4 transition-colors hover:brightness-105`}>
                  <h4 className={`font-bold text-sm sm:text-base ${s.text}`}>
                    {step.label}
                  </h4>
                  {step.detail && (
                    <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-1 leading-relaxed font-medium">
                      {step.detail}
                    </p>
                  )}
                </div>
              </motion.div>

              {/* Arrow connector between steps */}
              {!isLast && (
                <motion.div variants={itemVariant} className="flex items-center pl-[10px] -my-1.5 mb-1">
                  <ArrowDown size={14} className="text-[var(--text-secondary)] opacity-40" />
                </motion.div>
              )}
            </React.Fragment>
          );
        })}
      </motion.div>
    </motion.div>
  );
}
