"use client";
import React, { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import { SlidersHorizontal, RotateCcw, Zap, Save, AlertTriangle } from "lucide-react";
import { scorePreview, submitFollowUp, ScorePreviewResult, AnalysisResult } from "@/lib/api";

// ── Signal config ─────────────────────────────────────────────────────────────
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

const ARCH_COLOR_MAP: Record<string, string> = {
  RAG: "#10b981",
  FineTuning: "#3b82f6",
  CAG: "#f59e0b",
  Hybrid: "#f97316",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function buildInitialValues(result: AnalysisResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [key, cfg] of Object.entries(SIGNAL_CONFIG)) {
    const existingValue = result.signals?.[key]?.value ?? null;
    const idx = existingValue ? cfg.options.indexOf(existingValue) : -1;
    out[key] = idx >= 0 ? idx : Math.floor(cfg.options.length / 2);
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

// Format cost in lakhs/crores
function formatCost(amount: number): string {
  if (amount >= 10000000) return `Rs. ${(amount / 10000000).toFixed(1)} Cr`;
  if (amount >= 100000) return `Rs. ${(amount / 100000).toFixed(1)} L`;
  return `Rs. ${amount.toLocaleString("en-IN")}`;
}

// ── Confirmation Modal ────────────────────────────────────────────────────────
interface ConfirmModalProps {
  originalArch: string;
  newArch: string;
  originalCost: [number, number] | null;
  newCost: [number, number] | null;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmModal({ originalArch, newArch, originalCost, newCost, onConfirm, onCancel }: ConfirmModalProps) {
  return (
    <div style={{ minHeight: 320, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--border-radius-lg)", padding: "1rem" }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0">
            <AlertTriangle size={18} className="text-amber-500" />
          </div>
          <div>
            <h4 className="font-bold text-[var(--text-primary)]">Replace saved recommendation?</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">This will update your analysis permanently</p>
          </div>
        </div>

        {/* Arch comparison */}
        <div className="flex items-center gap-3 p-3 rounded-xl bg-[var(--background)] border border-[var(--border)] mb-4">
          <div className="flex-1 text-center">
            <p className="text-xs text-[var(--text-secondary)] mb-1">Current</p>
            <p className="font-bold text-sm line-through opacity-50" style={{ color: ARCH_COLOR_MAP[originalArch] ?? "var(--text-primary)" }}>
              {originalArch}
            </p>
            {originalCost && (
              <p className="text-[10px] text-[var(--text-secondary)] mt-1 line-through opacity-50">
                {formatCost(originalCost[0])} – {formatCost(originalCost[1])}/mo
              </p>
            )}
          </div>
          <span className="text-[var(--text-secondary)] font-bold">→</span>
          <div className="flex-1 text-center">
            <p className="text-xs text-[var(--text-secondary)] mb-1">New</p>
            <p className="font-bold text-sm" style={{ color: ARCH_COLOR_MAP[newArch] ?? "var(--text-primary)" }}>
              {newArch}
            </p>
            {newCost && (
              <p className="text-[10px] text-[var(--text-secondary)] mt-1">
                {formatCost(newCost[0])} – {formatCost(newCost[1])}/mo
              </p>
            )}
          </div>
        </div>

        <p className="text-xs text-[var(--text-secondary)] mb-5 leading-relaxed">
          Your signals will be updated to the slider values and the full analysis will be re-run. The cost report will update automatically.
        </p>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-xl bg-[var(--text-primary)] text-[var(--background)] text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            Yes, save changes
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
interface WhatIfEditorProps {
  result: AnalysisResult;
  onResultUpdate?: (newResult: AnalysisResult) => void;
}

export default function WhatIfEditor({ result, onResultUpdate }: WhatIfEditorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sliderValues, setSliderValues] = useState<Record<string, number>>(() => buildInitialValues(result));
  const [previewResult, setPreviewResult] = useState<ScorePreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const confirmRef = useRef<HTMLDivElement>(null);

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

  const handleSliderChange = useCallback((signalKey: string, rawValue: number) => {
    const updated = { ...sliderValues, [signalKey]: rawValue };
    setSliderValues(updated);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchPreview(updated), 300);
  }, [sliderValues, fetchPreview]);

  const handleReset = useCallback(() => {
    const initial = buildInitialValues(result);
    setSliderValues(initial);
    setPreviewResult(null);
    setSaveError(null);
  }, [result]);

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    fetchPreview(sliderValues);
  }, [sliderValues, fetchPreview]);

  const handleSaveConfirmed = useCallback(async () => {
    setShowConfirm(false);
    setSaving(true);
    setSaveError(null);
    try {
      const signals = sliderValuesToSignals(sliderValues);
      const updated = await submitFollowUp(result.analysis_id, signals);
      setPreviewResult(null);
      onResultUpdate?.(updated);
    } catch (e: any) {
      setSaveError(e.message ?? "Save failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }, [sliderValues, result.analysis_id, onResultUpdate]);

  // What to display
  const displayResult = previewResult ?? null;
  const displayScores = displayResult?.scores ?? result.scores ?? {};
  const displayRecommended = displayResult?.recommended ?? result.recommended ?? "";
  const displayRanking = displayResult?.ranking ?? result.ranking ?? [];
  const displayFactorBreakdown = displayResult?.factor_breakdown ?? result.factor_breakdown ?? {};

  const radarData = buildRadarData(displayFactorBreakdown);
  const scoresData = Object.entries(displayScores)
    .map(([name, score]) => ({ name, score }))
    .sort((a, b) => b.score - a.score);

  const recommendationChanged = previewResult && previewResult.recommended !== result.recommended;

  // Cost data
  const originalArch = result.recommended ?? "";
  const newArch = previewResult?.recommended ?? "";
  const originalCost = result.cost_analysis?.architectures?.[originalArch]?.monthly_total ?? null;
  const newArchCost = result.cost_analysis?.architectures?.[newArch]?.monthly_total ?? null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass-panel p-6 sm:p-8"
    >
      {/* Header */}
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
            onClick={() => { if (!isOpen) handleOpen(); else setIsOpen(false); }}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--background)] transition-colors"
          >
            {isOpen ? "Hide sliders" : "Show sliders"}
          </button>
        </div>
      </div>

      {/* Recommendation changed banner */}
      <AnimatePresence>
        {recommendationChanged && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 p-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 flex items-center justify-between gap-3 flex-wrap"
          >
            <div className="flex items-center gap-3">
              <Zap size={16} className="text-amber-500 flex-shrink-0" />
              <p className="text-sm font-semibold text-amber-500">
                Recommendation changed:{" "}
                <span className="line-through opacity-60">{result.recommended}</span>
                {" → "}
                <span className="text-[var(--text-primary)]">{displayRecommended}</span>
              </p>
            </div>
            <button
              onClick={() => {
                setShowConfirm(true);
                setTimeout(() => {
                  confirmRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                }, 100);
              }}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold bg-[var(--text-primary)] text-[var(--background)] hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <Save size={12} />
              {saving ? "Saving..." : "Save changes"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Cost comparison banner */}
      <AnimatePresence>
        {recommendationChanged && originalCost && newArchCost && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 grid grid-cols-2 gap-3"
          >
            {/* Original cost */}
            <div className="p-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
              <p className="text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">
                Original — {originalArch}
              </p>
              <p className="text-lg font-black line-through opacity-40" style={{ color: ARCH_COLOR_MAP[originalArch] ?? "var(--text-primary)" }}>
                {formatCost(originalCost[0])} – {formatCost(originalCost[1])}
              </p>
              <p className="text-[10px] text-[var(--text-secondary)] mt-1 opacity-60">per month</p>
            </div>
            {/* New cost */}
            <div className="p-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
              <p className="text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">
                New — {newArch}
              </p>
              <p className="text-lg font-black" style={{ color: ARCH_COLOR_MAP[newArch] ?? "var(--text-primary)" }}>
                {formatCost(newArchCost[0])} – {formatCost(newArchCost[1])}
              </p>
              <p className="text-[10px] text-[var(--text-secondary)] mt-1">per month</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Save error */}
      <AnimatePresence>
        {saveError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 p-3 rounded-xl border border-red-500/30 bg-red-500/5 text-sm text-red-500"
          >
            {saveError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sliders */}
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
                return (
                  <div key={key}>
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-sm text-[var(--text-secondary)]">{cfg.label}</span>
                      <span className="text-sm font-bold text-[var(--text-primary)]">{cfg.optionLabels[idx]}</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={cfg.options.length - 1}
                      step={1}
                      value={idx}
                      onChange={e => handleSliderChange(key, Number(e.target.value))}
                      className="w-full"
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

      {/* Live charts */}
      <div className={`grid grid-cols-1 lg:grid-cols-2 gap-6 ${loading || saving ? "opacity-60 pointer-events-none" : ""} transition-opacity`}>
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
                    isRec ? "border-[var(--primary)]/30 bg-[var(--primary)]/5" : "border-[var(--border)] bg-[var(--background)]"
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
                  <motion.div className="w-full h-1.5 rounded-full bg-[var(--background)] border border-[var(--border)] overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${entry.score}%` }}
                      transition={{ duration: 0.4, ease: "easeOut" }}
                    />
                  </motion.div>
                </div>
              );
            })}
          </div>
          {!isOpen && (
            <p className="mt-4 text-xs text-[var(--text-secondary)] text-center opacity-60">
              Click "Show sliders" above to explore different signal values
            </p>
          )}
        </div>
      </div>

      {/* Confirmation modal */}
      <AnimatePresence>
        {showConfirm && (
          <motion.div
            ref={confirmRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-6"
          >
            <ConfirmModal
              originalArch={originalArch}
              newArch={newArch}
              originalCost={originalCost}
              newCost={newArchCost}
              onConfirm={handleSaveConfirmed}
              onCancel={() => setShowConfirm(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
