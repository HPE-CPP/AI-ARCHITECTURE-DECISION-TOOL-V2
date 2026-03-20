"use client";
import React from "react";
import { TraceStep } from "@/lib/api";
import { CheckCircle2, Clock, PlayCircle, XCircle } from "lucide-react";
import { motion } from "framer-motion";

export function DecisionTrace({ trace }: { trace: TraceStep[] }) {
  if (!trace || trace.length === 0) return null;

  return (
    <div className="glass-panel p-8 rounded-3xl relative overflow-hidden">
      <h3 className="text-xl font-bold mb-8 tracking-tight flex items-center gap-3">
        <span className="w-8 h-8 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center shadow-lg">
          <Clock size={16} />
        </span>
        Decision Trace
      </h3>

      <div className="relative pl-6 space-y-8">
        {/* Connecting Line */}
        <div className="absolute top-2 bottom-2 left-[11px] w-0.5 bg-[color:var(--border)]" />

        {trace.map((step, index) => {
          const isComplete = step.status === "complete";
          const isInProgress = step.status === "in_progress";
          const isFailed = step.status === "failed";
          const isQueued = step.status === "queued";

          return (
            <motion.div 
              key={`${step.step}-${index}`}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1, duration: 0.5 }}
              className="relative"
            >
              {/* Node Icon */}
              <div className={`absolute -left-[30px] top-1 rounded-full p-1 bg-[color:var(--surface)] border-2 z-10 ${
                isComplete ? "border-emerald-500 shadow-lg shadow-emerald-500/20" : 
                isInProgress ? "border-[color:var(--primary)] shadow-lg shadow-indigo-500/30" : 
                isFailed ? "border-red-500" : "border-[color:var(--border)]"
              }`}>
                {isComplete && <CheckCircle2 size={16} className="text-emerald-500" />}
                {isInProgress && <PlayCircle size={16} className="text-[color:var(--primary)] animate-pulse" />}
                {isFailed && <XCircle size={16} className="text-red-500" />}
                {isQueued && <div className="w-4 h-4 rounded-full bg-[color:var(--border)]" />}
              </div>

              {/* Content */}
              <div className={`p-5 rounded-2xl border transition-all ${
                isComplete ? "border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-500/40" : 
                isInProgress ? "border-[color:var(--primary)]/30 bg-[color:var(--primary)]/5 hover:border-[color:var(--primary)]/50" : 
                isFailed ? "border-red-500/30 bg-red-500/5 hover:border-red-500/50" : "border-[color:var(--border)] bg-[color:var(--surface)] opacity-70"
              }`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                  <h4 className={`font-bold capitalize text-lg ${
                    isComplete ? "text-emerald-500" :
                    isInProgress ? "text-[color:var(--primary)]" :
                    isFailed ? "text-red-500" : "text-[color:var(--text-secondary)]"
                  }`}>
                    {step.step.replace(/_/g, " ")}
                  </h4>
                  {step.timestamp && (
                    <span className="text-xs font-medium text-[color:var(--text-secondary)] font-mono tracking-wider bg-[color:var(--background)] px-2 py-1 rounded-md border border-[color:var(--border)]">
                      {new Date(step.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second:'2-digit' })}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-md border ${
                    isComplete ? 'border-emerald-500/30 text-emerald-500 bg-emerald-500/10' : 
                    isInProgress ? 'border-[color:var(--primary)]/30 text-[color:var(--primary)] bg-[color:var(--primary)]/10' : 
                    isFailed ? 'border-red-500/30 text-red-500 bg-red-500/10' : 'border-[color:var(--border)] text-[color:var(--text-secondary)] bg-[color:var(--background)]'
                  }`}>
                    {step.status.replace(/_/g, " ")}
                  </span>
                  {step.details && (
                    <span className="text-sm font-medium text-[color:var(--text-primary)] opacity-90 leading-relaxed">
                      {step.details}
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
