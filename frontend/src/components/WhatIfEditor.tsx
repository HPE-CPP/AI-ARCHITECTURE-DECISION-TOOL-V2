"use client";
import React, { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import { SlidersHorizontal, RotateCcw, Zap } from "lucide-react";
import { scorePreview, ScorePreviewResult, AnalysisResult } from "@/lib/api";

// ── Signal config — mirrors SCORING_RULES keys exactly ───────────────────────

const SIGNAL_CONFIG: Record<string, { label: string; options: string[]; optionLabels: string[] }> = {
  dataset_size: {
    label: "Dataset size",
    options: ["small", "medium", "large", "very_large"],
    optionLabels: ["Small", "Medium", "Large", "Very large"],
  },
  query_volume: {
    label: "Query volume",
    options: ["low", "medium", "high", "very_high"],
    optionLabels: ["Low", "Medium", "High", "Very high"],
  },
  latency_requirement: {
    label: "Latency requirement",
    options: ["relaxed", "moderate", "strict", "ultra_low"],
    optionLabels: ["Relaxed", "Moderate", "Strict", "Ultra low"],
  },
  data_volatility: {
    label: "Data volatility",
    options: ["static", "low", "moderate", "high"],
    optionLabels: ["Static", "Low", "Moderate", "High"],
  },
  accuracy_requirement: {
    label: "Accuracy requirement",
    options: ["moderate", "high", "very_high", "critical"],
    optionLabels: ["Moderate", "High", "Very high", "Critical"],
  },
  domain_specificity: {
    label: "Domain specificity",
    options: ["general", "moderate", "specialized", "highly_specialized"],
    optionLabels: ["General", "Moderate", "Specialized", "Highly specialized"],
  },
  security_level: {
    label: "Security level",
    options: ["standard", "elevated", "high", "critical"],
    optionLabels: ["Standard", "Elevated", "High", "Critical"],
  },
  cost_sensitivity: {
    label: "Cost sensitivity",
    options: ["low", "moderate", "high", "very_high"],
    optionLabels: ["Low", "Moderate", "High", "Very high"],
  },
  deployment_preference: {
    label: "Deployment preference",
    options: ["cloud", "on_premise", "hybrid", "edge"],
    optionLabels: ["Cloud", "On-premise", "Hybrid", "Edge"],
  },
  user_scale: {
    label: "User scale",
    options: ["small", "medium", "large", "enterprise"],
    optionLabels: ["Small", "Medium", "Large", "Enterprise"],
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Build initial slider state from the existing analysis signals */
function buildInitialValues(result: AnalysisResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [key, cfg] of Object.entries(SIGNAL_CONFIG)) {
    const existingValue = result.signals?.[key]?.value ?? null;
    const idx = existingValue ? cfg.options.indexOf(existingValue) : -1;
    out[key] = idx >= 0 ? idx : Math.floor(cfg.options.length / 2); // default to middle
  }
  return out;
}

function sliderValuesToSignals(values: Record<string, number>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, idx] of Object.entries(values)) {
    out[key] = SIGNAL_CONFIG[key].options[idx];
  }
  return out;
}

function buildRadarData(factor_breakdown: Record<string, Record<string, number>>) {
  const signals = Object.keys(Object.values(factor_breakdown)[0] || {});
  return signals.map(signal => {
    const point: Record<string, string | number> = {
      subject: signal.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
    };
    for (const arch of Object.keys(factor_breakdown)) {
      point[arch] = factor_breakdown[arch][signal];
    }
    return point;
  });
}

const ARCH_COLOR_MAP: Record<string, string> = {
  RAG: "#10b981",
  FineTuning: "#3b82f6",
  CAG: "#f59e0b",
  Hybrid: "#f97316",
};

// ── Main Component ────────────────────────────────────────────────────────────

interface WhatIfEditorProps {
  result: AnalysisResult;
}

export default function WhatIfEditor({ result }: WhatIfEditorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sliderValues, setSliderValues] = useState<Record<string, number>>(
    () => buildInitialValues(result)
  );
  const [previewResult, setPreviewResult] = useState<ScorePreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced API call — fires 300ms after user stops dragging
  const fetchPreview = useCallback(async (values: Record<string, number>) => {
    setLoading(true);
    try {
      const signals = sliderValuesToSignals(values);
      const res = await scorePreview(signals);
      setPreviewResult(res);
    } catch (e) {
      console.error("[WhatIfEditor] score-preview failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSliderChange = useCallback(
    (signalKey: string, rawValue: number) => {
      const updated = { ...sliderValues, [signalKey]: rawValue };
      setSliderValues(updated);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchPreview(updated), 300);
    },
    [sliderValues, fetchPreview]
  );

  const handleReset = useCallback(() => {
    const initial = buildInitialValues(result);
    setSliderValues(initial);
    setPreviewResult(null);
  }, [result]);

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    // Fetch baseline preview immediately on open
    fetchPreview(sliderValues);
  }, [sliderValues, fetchPreview]);

  // Determine what to show in charts
  const displayResult = previewResult ?? null;
  const displayScores = displayResult?.scores ?? result.scores ?? {};
  const displayRecommended = displayResult?.recommended ?? result.recommended ?? "";
  const displayRanking = displayResult?.ranking ?? result.ranking ?? [];
  const displayFactorBreakdown = displayResult?.factor_breakdown ?? result.factor_breakdown ?? {};

  const radarData = buildRadarData(displayFactorBreakdown);
  const scoresData = Object.entries(displayScores)
    .map(([name, score]) => ({ name, score }))
    .sort((a, b) => b.score - a.score);

  const recommendationChanged =
    displayResult && displayResult.recommended !== result.recommended;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass-panel p-6 sm:p-8"
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center">
            <SlidersHorizontal size={14} className="text-[var(--primary)]" />
          </div>
          <div>
            <h3 className="text-xl font-bold tracking-tight">What-If Signal Editor</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Drag any slider to explore how signal changes affect the recommendation
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--background)] transition-colors"
          >
            <RotateCcw size={12} /> Reset
          </button>
          <button
            onClick={() => setIsOpen(v => !v)}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--background)] transition-colors"
          >
            {isOpen ? "Hide sliders" : "Show sliders"}
          </button>
        </div>
      </div>

      {/* Live recommendation banner — shown when something changes */}
      <AnimatePresence>
        {recommendationChanged && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 p-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 flex items-center gap-3"
          >
            <Zap size={16} className="text-amber-500 flex-shrink-0" />
            <p className="text-sm font-semibold text-amber-500">
              Recommendation changed:{" "}
              <span className="line-through opacity-60">{result.recommended}</span>
              {" → "}
              <span className="text-[var(--text-primary)]">{displayRecommended}</span>
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sliders — collapsible */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="mb-8 overflow-hidden"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5 pt-2">
              {Object.entries(SIGNAL_CONFIG).map(([key, cfg]) => {
                const idx = sliderValues[key] ?? 0;
                const label = cfg.optionLabels[idx];
                return (
                  <div key={key}>
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-sm text-[var(--text-secondary)]">{cfg.label}</span>
                      <span className="text-sm font-bold text-[var(--text-primary)]">{label}</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={cfg.options.length - 1}
                      step={1}
                      value={idx}
                      onChange={e => handleSliderChange(key, Number(e.target.value))}
                      className="w-full accent-[var(--primary)]"
                      style={{ accentColor: "var(--primary)" }}
                    />
                    <div className="flex justify-between text-[10px] text-[var(--text-secondary)] mt-0.5 opacity-60">
                      <span>{cfg.optionLabels[0]}</span>
                      <span>{cfg.optionLabels[cfg.optionLabels.length - 1]}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live results — always visible once there's data */}
      <div className={`grid grid-cols-1 lg:grid-cols-2 gap-6 ${loading ? "opacity-60 pointer-events-none" : ""} transition-opacity`}>
        {/* Radar chart */}
        {radarData.length > 0 && (
          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6">
            <h4 className="text-sm font-bold mb-4 text-[var(--text-secondary)] uppercase tracking-widest">
              Factor breakdown
            </h4>
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="48%" outerRadius="60%" data={radarData}>
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: "var(--text-secondary)", fontSize: 10, fontWeight: 600 }}
                    tickLine={false}
                  />
                  <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface)",
                      borderColor: "var(--border)",
                      borderRadius: "12px",
                      color: "var(--text-primary)",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ paddingTop: "12px", fontSize: "11px" }} />
                  {displayRanking.slice(0, 3).map((arch, i) => {
                    const opacities = [1, 0.7, 0.45];
                    return (
                      <Radar
                        key={arch}
                        name={arch}
                        dataKey={arch}
                        stroke={ARCH_COLOR_MAP[arch] ?? "var(--primary)"}
                        strokeOpacity={opacities[i] ?? 0.3}
                        fill={ARCH_COLOR_MAP[arch] ?? "var(--primary)"}
                        fillOpacity={(opacities[i] ?? 0.3) * 0.2}
                        strokeWidth={i === 0 ? 2.5 : 1.5}
                      />
                    );
                  })}
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Score bars */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6">
          <h4 className="text-sm font-bold mb-4 text-[var(--text-secondary)] uppercase tracking-widest">
            Live ranking
          </h4>
          <div className="space-y-3">
            {scoresData.map((entry, index) => {
              const isRec = entry.name === displayRecommended;
              const color = ARCH_COLOR_MAP[entry.name] ?? "var(--primary)";
              const archDetails = result.architecture_details?.[entry.name];
              return (
                <div
                  key={entry.name}
                  className={`p-3 rounded-xl border transition-all duration-300 ${
                    isRec
                      ? "border-[var(--primary)]/30 bg-[var(--primary)]/5"
                      : "border-[var(--border)] bg-[var(--background)]"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span
                      className="w-5 h-5 rounded-full text-[10px] font-black flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: color + "30", color }}
                    >
                      {index + 1}
                    </span>
                    <span className="text-sm font-bold text-[var(--text-primary)] flex-1 truncate">
                      {archDetails?.full_name ?? entry.name}
                    </span>
                    <span className="text-sm font-black text-[var(--text-primary)]">
                      {entry.score.toFixed(1)}
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[var(--background)] border border-[var(--border)] overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${entry.score}%` }}
                      transition={{ duration: 0.4, ease: "easeOut" }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Tip */}
          {!isOpen && (
            <p className="mt-4 text-xs text-[var(--text-secondary)] text-center opacity-60">
              Click "Show sliders" above to explore different signal values
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}
