"use client";
import React, { useMemo, memo } from "react";
import { AnalysisResult } from "@/lib/api";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import { motion } from "framer-motion";
import { CheckCircle, Download, Slash } from "lucide-react";
import { exportAnalysis } from "@/lib/api";

// B-14 FIX: Wrap in React.memo to prevent expensive Recharts SVG re-renders
// when the parent component re-renders (e.g. on each polling tick) but the
// result data hasn't actually changed.
export const ResultsDashboard = memo(function ResultsDashboard({ result }: { result: AnalysisResult }) {
  const {
    recommended, scores, confidence, ranking, why_not,
    factor_breakdown, architecture_details, suitability
  } = result;

  const radarData = useMemo(() => {
    if (!factor_breakdown) return [];
    const signals = Object.keys(Object.values(factor_breakdown)[0] || {});
    return signals.map(signal => {
      const dataPoint: Record<string, unknown> = { subject: signal.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) };
      Object.keys(factor_breakdown).forEach(arch => {
        dataPoint[arch] = factor_breakdown[arch][signal];
      });
      return dataPoint;
    });
  }, [factor_breakdown]);

  const scoresData = useMemo(() => {
    if (!scores) return [];
    return Object.entries(scores)
      .map(([name, score]) => ({ name, score }))
      .sort((a, b) => b.score - a.score);
  }, [scores]);

  if (!recommended || !scores) return null;
  const topArch = architecture_details?.[recommended];

  return (
    <div className="w-full flex flex-col gap-8">
      {/* RECOMMENDATION CARD */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="glass-panel p-6 sm:p-8 md:p-12 relative overflow-hidden flex flex-col lg:flex-row items-center gap-8 sm:gap-12 group"
      >
        <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full blur-[120px] bg-white/[0.03] pointer-events-none group-hover:bg-white/[0.05] transition-colors duration-700" />

        <div className="flex-1 text-center lg:text-left z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--text-primary)] bg-[var(--background)] text-[var(--text-primary)] mb-8 font-semibold text-sm shadow-sm backdrop-blur-sm">
            <CheckCircle size={16} /> Analysis Complete
          </div>
          <h2 className="text-[var(--text-secondary)] font-bold tracking-widest uppercase mb-4 opacity-80">Recommended Architecture</h2>
          <h1 className="text-4xl sm:text-6xl md:text-8xl font-black tracking-tighter text-[var(--text-primary)] mb-4 sm:mb-6 drop-shadow-xl">
            {topArch?.full_name || recommended}
          </h1>
          <p className="text-xl text-[var(--text-secondary)] leading-relaxed max-w-2xl font-medium">
            {topArch?.description}
          </p>
          <button
            id="download-pdf-btn"
            onClick={async () => {
              try {
                await exportAnalysis(result);
              } catch (e: unknown) {
                // Export failures are non-fatal: the user stays on the results page.
                // A future iteration can surface a toast notification here.
                console.error("[ResultsDashboard] PDF export failed:", e);
              }
            }}
            className="mt-6 sm:mt-10 flex items-center gap-3 px-6 sm:px-8 py-3.5 sm:py-4 rounded-full border border-[var(--border)] bg-[var(--background)] hover:bg-[var(--text-primary)] hover:text-[var(--background)] transition-all font-bold shadow-lg shadow-black/5 hover:-translate-y-0.5 group/btn text-sm sm:text-base"
          >
            <Download size={20} className="group-hover/btn:text-[var(--background)] text-[var(--text-primary)] transition-colors" /> Download PDF Report
          </button>
        </div>

        <div className="w-full lg:w-auto flex flex-col sm:flex-row gap-4 z-10">
          {/* Confidence Widget */}
          <div className="flex-1 lg:w-48 p-5 sm:p-8 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl transition-colors">
            <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-3">Confidence</span>
            <div className="text-4xl sm:text-5xl font-black text-[var(--primary)]">
              {/* FIX FE-003: Use (confidence ?? 0) instead of confidence! to prevent crash */}
              {(((confidence ?? 0) * 100).toFixed(0))}<span className="text-2xl">%</span>
            </div>
            <div className="w-full h-px border border-[var(--border)] bg-[var(--background)] relative mt-6 overflow-hidden">
              <motion.div 
                initial={{ width: 0 }} 
                animate={{ width: `${(confidence ?? 0) * 100}%` }} 
                transition={{ duration: 1, delay: 0.8 }} 
                className="absolute top-0 left-0 h-full bg-[var(--text-primary)]" 
              />
            </div>
          </div>

          {/* Overall Score Widget */}
          <div className="flex-1 lg:w-48 p-5 sm:p-8 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl transition-colors">
            <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-3">Overall Score</span>
            <div className="text-4xl sm:text-5xl font-black text-[var(--primary)]">
              {scores[recommended].toFixed(1)}<span className="text-2xl">/100</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* CHARTS SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Factor Breakdown — use animate always (not whileInView) so jsdom tests can detect it */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="glass-panel p-8"
        >
          <h3 className="text-2xl font-bold mb-8 tracking-tight">Factor Breakdown</h3>
          <div className="h-[280px] sm:h-[380px] w-full" data-testid="radar-container">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="48%" outerRadius="60%" data={radarData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 11, fontWeight: 600 }}
                  tickLine={false}
                />
                <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', borderRadius: '16px', color: 'var(--text-primary)', fontWeight: 'bold' }} />
                <Legend wrapperStyle={{ paddingTop: '16px', fontSize: '12px' }} />
                {ranking?.slice(0, 3).map((arch, i) => {
                  const opacities = [1, 0.75, 0.5];
                  const opacity = opacities[i] || 0.25;
                  return (
                    <Radar
                      key={arch}
                      name={arch}
                      dataKey={arch}
                      stroke="var(--primary)"
                      strokeOpacity={opacity}
                      fill="var(--primary)"
                      fillOpacity={opacity * 0.3}
                      strokeWidth={i === 0 ? 3 : 2}
                    />
                  );
                })}
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Suitability & Why Not — use animate always (not whileInView) for jsdom compatibility */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col gap-8"
        >
          <div className="glass-panel p-8">
            <h3 className="text-2xl font-bold mb-6 tracking-tight">Architecture Ranking</h3>
            <div className="space-y-3" data-testid="bar-container">
              {scoresData.map((entry, index) => {
                const suit = suitability?.[entry.name] ?? "";
                const isRec = entry.name === recommended;
                const suitColor = suit.toLowerCase().includes("highly")
                  ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/20"
                  : suit.toLowerCase().includes("not")
                  ? "text-red-500 bg-red-500/10 border-red-500/20"
                  : suit.toLowerCase().includes("moderate")
                  ? "text-amber-500 bg-amber-500/10 border-amber-500/20"
                  : "text-[var(--primary)] bg-[var(--primary)]/10 border-[var(--primary)]/20";
                const opacities = [100, 80, 60, 40];
                const bgOpacity = opacities[index] || 20;
                const barColor = `color-mix(in srgb, var(--primary) ${bgOpacity}%, transparent)`;
                const textColor = index > 1 ? "var(--primary)" : "var(--background)";
                const fullName = architecture_details?.[entry.name]?.full_name || entry.name;
                return (
                  <div key={entry.name} className={`p-3 rounded-xl border transition-colors ${isRec ? "border-[var(--primary)]/30 bg-[var(--primary)]/5" : "border-[var(--border)] bg-[var(--surface)]"}`}>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0"
                        style={{ backgroundColor: barColor, color: textColor }}>
                        {index + 1}
                      </span>
                      <span className="text-sm font-bold text-[var(--text-primary)] flex-1 truncate">{fullName}</span>
                      <span className="text-sm font-black text-[var(--text-primary)]">{entry.score.toFixed(1)}/100</span>
                      {suit && (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border hidden sm:inline ${suitColor}`}>
                          {suit}
                        </span>
                      )}
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-[var(--background)] border border-[var(--border)] overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${entry.score}%`, backgroundColor: barColor }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* FIX FE-010: Only render why_not section if there are entries to show */}
          {why_not && Object.keys(why_not).length > 0 && (
            <div className="glass-panel p-8 flex-1 bg-[var(--surface)]">
              <h4 className="font-bold text-xl mb-6 flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-[var(--background)] border border-red-500/20 text-red-500 flex items-center justify-center">
                  <Slash size={14} className="-rotate-135" />
                </span>
                Why not others?
              </h4>
              <div className="space-y-5">
                {Object.entries(why_not).slice(0, 3).map(([arch, reason]) => (
                  <div key={arch} className="flex flex-col border-b border-[var(--border)] pb-4 last:border-0 last:pb-0">
                    <span className="text-sm font-bold text-[var(--primary)] mb-1">
                      {architecture_details?.[arch]?.full_name || arch}
                    </span>
                    <span className="text-sm text-[var(--text-secondary)] leading-relaxed select-text">{reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
});
