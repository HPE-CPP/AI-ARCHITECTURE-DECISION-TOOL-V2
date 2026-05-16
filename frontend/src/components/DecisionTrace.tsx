"use client";
import React from "react";
import { TraceStep } from "@/lib/api";
import { CheckCircle2, Clock, PlayCircle, XCircle, AlertTriangle } from "lucide-react";
import { motion, Variants } from "framer-motion";

export function DecisionTrace({ trace }: { trace: TraceStep[] }) {
  if (!trace || trace.length === 0) return null;

  const stepVariants: Variants = {
    hidden: {
      opacity: 0,
      x: -20,
      scale: 0.95,
      filter: "blur(4px)"
    },
    visible: (i: number) => ({
      opacity: 1,
      x: 0,
      scale: 1,
      filter: "blur(0px)",
      transition: {
        type: "spring",
        stiffness: 90,
        damping: 15,
        delay: 0.05,
        duration: 0.5
      }
    }),
  };

  return (
    // Reduced padding on mobile (p-4) vs desktop (p-8)
    <div className="glass-panel p-4 sm:p-8 rounded-2xl sm:rounded-3xl relative overflow-hidden">
      <h3 className="text-lg sm:text-xl font-bold mb-6 sm:mb-8 tracking-tight flex items-center gap-3">
        <span className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center shadow-lg">
          <Clock size={14} className="sm:hidden" />
          <Clock size={16} className="hidden sm:block" />
        </span>
        Decision Trace
      </h3>

      {/* Reduced vertical spacing on mobile (space-y-4) vs desktop (space-y-8) */}
      <div className="relative pl-5 sm:pl-6 space-y-4 sm:space-y-8">
        {/* Connecting Line */}
        <div className="absolute top-2 bottom-2 left-[10px] sm:left-[11px] w-0.5 bg-[color:var(--border)]" />

        {trace.map((step, index) => {
          let displayStatus = step.status;
          
          // Fix: Backend sometimes leaves 'scoring' as 'in_progress' even after it finishes.
          // If the 'recommend' step exists, scoring is definitely complete.
          if (step.step === "scoring" && step.status === "in_progress") {
            const hasRecommend = trace.some(t => t.step.toLowerCase().includes("recommend"));
            if (hasRecommend) {
              displayStatus = "complete";
            }
          }

          const isComplete = displayStatus === "complete";
          const isInProgress = displayStatus === "in_progress";
          const isFailed = displayStatus === "failed";
          const isWarning = displayStatus === "warning";
          const isQueued = displayStatus === "queued";

          return (
            <motion.div
              key={`${step.step}-${index}`}
              custom={index}
              variants={stepVariants}
              initial="hidden"
              whileInView="visible"
              exit="hidden"
              viewport={{
                // FIX FE-011: once: true stops the animation from replaying on every
                // scroll in/out, which was expensive and visually jarring for return visits
                once: true,
                amount: 0.1,
                margin: "0px 0px -5% 0px"
              }}
              className="relative"
            >
              {/* Node Icon - Scaled down for mobile */}
              <div className={`absolute -left-[27px] sm:-left-[30px] top-1/2 -translate-y-1/2 rounded-full p-0.5 sm:p-1 bg-[color:var(--surface)] border-2 z-10 ${
                  isComplete ? "border-emerald-500 shadow-lg shadow-emerald-500/20" :
                  isWarning ? "border-amber-500 shadow-lg shadow-amber-500/20" :
                  isInProgress ? "border-[color:var(--primary)] shadow-lg shadow-indigo-500/30" :
                    isFailed ? "border-red-500 shadow-lg shadow-red-500/20" : 
                  "border-[color:var(--text-secondary)] shadow-sm"
                }`}>
                {isComplete && <CheckCircle2 size={14} className="text-emerald-500 sm:w-4 sm:h-4" />}
                {isWarning && <AlertTriangle size={14} className="text-amber-500 sm:w-4 sm:h-4" />}
                {isInProgress && <PlayCircle size={14} className="text-[color:var(--primary)] animate-pulse sm:w-4 sm:h-4" />}
                {isFailed && <XCircle size={14} className="text-red-500 sm:w-4 sm:h-4" />}
                {isQueued && <div className="w-3 h-3 sm:w-4 sm:h-4 rounded-full bg-[color:var(--text-secondary)]" />}
              </div>

              {/* Content Card - Slimmer padding and text on mobile */}
              <motion.div
                className={`p-3 sm:p-5 rounded-xl sm:rounded-2xl border transition-all duration-300 ${
                    isComplete ? "border-emerald-500/20 bg-emerald-500/5 hover:bg-emerald-500/10 hover:border-emerald-500/40" :
                    isWarning ? "border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 hover:border-amber-500/50" :
                    isInProgress ? "border-[color:var(--primary)]/30 bg-[color:var(--primary)]/5 hover:bg-[color:var(--primary)]/10 hover:border-[color:var(--primary)]/50" :
                    isFailed ? "border-red-500/30 bg-red-500/5 hover:bg-red-500/10 hover:border-red-500/50" : 
                    "border-[color:var(--border)] bg-[color:var(--surface)] opacity-80 hover:opacity-100 hover:border-[color:var(--text-secondary)]/40"
                  }`}
              >
                <div className="flex flex-row items-center justify-between gap-2 mb-1.5 sm:mb-2">
                  <h4 className={`font-bold capitalize text-sm sm:text-lg truncate ${
                      isComplete ? "text-emerald-500" :
                      isWarning ? "text-amber-500" :
                      isInProgress ? "text-[color:var(--primary)]" :
                      isFailed ? "text-red-500" : "text-[color:var(--text-primary)]"
                    }`}>
                    {step.step.replace(/_/g, " ")}
                  </h4>
                  {step.timestamp && (
                    <span className="text-[9px] sm:text-xs font-medium text-[color:var(--text-secondary)] font-mono tracking-wider bg-[color:var(--background)] px-1.5 py-0.5 rounded border border-[color:var(--border)] whitespace-nowrap">
                      {new Date(step.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 sm:gap-3">
                  <span className={`text-[8px] sm:text-[10px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border whitespace-nowrap ${
                      isComplete ? 'border-emerald-500/30 text-emerald-500 bg-emerald-500/10' :
                      isWarning ? 'border-amber-500/40 text-amber-500 bg-amber-500/10' :
                      isInProgress ? 'border-[color:var(--primary)]/40 text-[color:var(--primary)] bg-[color:var(--primary)]/10' :
                      isFailed ? 'border-red-500/40 text-red-500 bg-red-500/10' : 
                      'border-[color:var(--border)] text-[color:var(--text-primary)] bg-[color:var(--surface)]'
                    }`}>
                    {displayStatus.replace(/_/g, " ")}
                  </span>
                  {step.details && (
                    <span className="text-xs sm:text-sm font-medium text-[color:var(--text-primary)] opacity-90 leading-tight sm:leading-relaxed line-clamp-1 sm:line-clamp-none">
                      {step.details}
                    </span>
                  )}
                </div>
              </motion.div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}