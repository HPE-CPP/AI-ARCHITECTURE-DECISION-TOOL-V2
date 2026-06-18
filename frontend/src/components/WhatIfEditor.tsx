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
  citation_requirement: {
  label: "Explainability requirement",
  options: ["low", "moderate", "high", "critical"],
  optionLabels: ["Low", "Moderate", "High", "Critical"],
},
context_size: {
  label: "Context size",
  options: ["small", "medium", "large", "very_large"],
  optionLabels: ["Small", "Medium", "Large", "Very large"],
},
};

const ARCH_COLOR_MAP: Record<string, string> = {
  RAG: "#10b981",
  FineTuning: "#3b82f6",
  CAG: "#f59e0b",
  Hybrid: "#f97316",
};

// ── Cost estimation (mirrors cost_analysis.py) ───────────────────────────────
const _INFRA_COST: Record<string, Record<string, Record<string, Record<string, [number, number]>>>> = {
  compute: {
    dataset_size: {
      small:      { RAG: [17000, 42000],     FineTuning: [67000, 168000],    CAG: [8500, 25000],     Hybrid: [84000, 210000] },
      medium:     { RAG: [42000, 126000],    FineTuning: [168000, 420000],   CAG: [17000, 50000],    Hybrid: [210000, 504000] },
      large:      { RAG: [126000, 336000],   FineTuning: [420000, 1008000],  CAG: [42000, 126000],   Hybrid: [504000, 1260000] },
      very_large: { RAG: [336000, 840000],   FineTuning: [1008000, 2520000], CAG: [126000, 336000],  Hybrid: [1260000, 2940000] },
    },
    query_volume: {
      low:       { RAG: [8500, 25000],    FineTuning: [4200, 12600],    CAG: [4200, 12600],    Hybrid: [12600, 33600] },
      medium:    { RAG: [25000, 67000],   FineTuning: [12600, 33600],   CAG: [12600, 42000],   Hybrid: [33600, 84000] },
      high:      { RAG: [67000, 168000],  FineTuning: [33600, 84000],   CAG: [42000, 126000],  Hybrid: [84000, 210000] },
      very_high: { RAG: [168000, 420000], FineTuning: [84000, 210000],  CAG: [126000, 336000], Hybrid: [210000, 504000] },
    },
  },
  storage: {
    dataset_size: {
      small:      { RAG: [1700, 4200],    FineTuning: [4200, 12600],   CAG: [420, 1700],     Hybrid: [5900, 16800] },
      medium:     { RAG: [4200, 16800],   FineTuning: [12600, 33600],  CAG: [840, 4200],     Hybrid: [16800, 42000] },
      large:      { RAG: [16800, 50400],  FineTuning: [33600, 84000],  CAG: [2500, 8400],    Hybrid: [42000, 126000] },
      very_large: { RAG: [50400, 168000], FineTuning: [84000, 252000], CAG: [8400, 33600],   Hybrid: [126000, 336000] },
    },
  },
  api_inference: {
    query_volume: {
      low:       { RAG: [8400, 25000],    FineTuning: [2500, 8400],    CAG: [6700, 21000],    Hybrid: [10900, 29400] },
      medium:    { RAG: [25000, 84000],   FineTuning: [8400, 29400],   CAG: [21000, 67000],   Hybrid: [29400, 100800] },
      high:      { RAG: [84000, 252000],  FineTuning: [29400, 84000],  CAG: [67000, 210000],  Hybrid: [100800, 294000] },
      very_high: { RAG: [252000, 672000], FineTuning: [84000, 252000], CAG: [210000, 588000], Hybrid: [294000, 756000] },
    },
  },
  networking: {
    user_scale: {
      small:      { RAG: [1700, 4200],   FineTuning: [840, 2500],    CAG: [840, 2500],    Hybrid: [2500, 5900] },
      medium:     { RAG: [4200, 12600],  FineTuning: [2500, 6700],   CAG: [2500, 6700],   Hybrid: [5900, 16800] },
      large:      { RAG: [12600, 33600], FineTuning: [6700, 16800],  CAG: [6700, 16800],  Hybrid: [16800, 42000] },
      enterprise: { RAG: [33600, 84000], FineTuning: [16800, 42000], CAG: [16800, 42000], Hybrid: [42000, 100800] },
    },
  },
};

const _TRAINING_COST: Record<string, Record<string, Record<string, [number, number]>>> = {
  dataset_size: {
    small:      { RAG: [0, 0], FineTuning: [42000, 168000],    CAG: [0, 0], Hybrid: [42000, 168000] },
    medium:     { RAG: [0, 0], FineTuning: [168000, 504000],   CAG: [0, 0], Hybrid: [168000, 504000] },
    large:      { RAG: [0, 0], FineTuning: [504000, 1260000],  CAG: [0, 0], Hybrid: [504000, 1260000] },
    very_large: { RAG: [0, 0], FineTuning: [1260000, 3360000], CAG: [0, 0], Hybrid: [1260000, 3360000] },
  },
  data_volatility: {
    static:   { RAG: [0, 0], FineTuning: [0, 0],          CAG: [0, 0], Hybrid: [0, 0] },
    low:      { RAG: [0, 0], FineTuning: [16800, 67000],   CAG: [0, 0], Hybrid: [16800, 67000] },
    moderate: { RAG: [0, 0], FineTuning: [67000, 210000],  CAG: [0, 0], Hybrid: [67000, 210000] },
    high:     { RAG: [0, 0], FineTuning: [210000, 504000], CAG: [0, 0], Hybrid: [210000, 504000] },
  },
};

const _MAINTENANCE_MULTIPLIER: Record<string, Record<string, number>> = {
  cloud:      { RAG: 1.0, FineTuning: 1.0, CAG: 1.0, Hybrid: 1.0 },
  on_premise: { RAG: 1.4, FineTuning: 1.3, CAG: 1.2, Hybrid: 1.5 },
  hybrid:     { RAG: 1.2, FineTuning: 1.2, CAG: 1.1, Hybrid: 1.3 },
  edge:       { RAG: 1.5, FineTuning: 1.4, CAG: 1.3, Hybrid: 1.6 },
};

const _SECURITY_MULTIPLIER: Record<string, number> = {
  standard: 1.0, elevated: 1.1, high: 1.25, critical: 1.5,
};

function _lookupInfra(category: string, signal: string, value: string, arch: string): [number, number] {
  return (_INFRA_COST[category]?.[signal]?.[value]?.[arch] as [number, number]) ?? [0, 0];
}
function _lookupTraining(signal: string, value: string, arch: string): [number, number] {
  return (_TRAINING_COST[signal]?.[value]?.[arch] as [number, number]) ?? [0, 0];
}
function _sumRanges(ranges: [number, number][]): [number, number] {
  return [ranges.reduce((s, r) => s + r[0], 0), ranges.reduce((s, r) => s + r[1], 0)];
}

/** Estimate monthly cost range for a given arch + signal map (mirrors cost_analysis.py). */
function estimateMonthlyCost(signals: Record<string, string>, arch: string): [number, number] {
  const dataset_size   = signals.dataset_size   ?? "medium";
  const query_volume   = signals.query_volume   ?? "medium";
  const user_scale     = signals.user_scale     ?? "medium";
  const data_vol       = signals.data_volatility ?? "low";
  const deployment     = signals.deployment_preference ?? "cloud";
  const security       = signals.security_level ?? "standard";

  const secMult   = _SECURITY_MULTIPLIER[security]   ?? 1.0;
  const maintMult = (_MAINTENANCE_MULTIPLIER[deployment] ?? _MAINTENANCE_MULTIPLIER.cloud)[arch] ?? 1.0;

  const compute_ds  = _lookupInfra("compute",       "dataset_size", dataset_size,  arch);
  const compute_qv  = _lookupInfra("compute",       "query_volume", query_volume,  arch);
  const compute: [number, number]     = [compute_ds[0] + compute_qv[0], compute_ds[1] + compute_qv[1]];
  const storage       = _lookupInfra("storage",       "dataset_size", dataset_size,  arch);
  const api_inference = _lookupInfra("api_inference", "query_volume", query_volume,  arch);
  const networking    = _lookupInfra("networking",    "user_scale",   user_scale,    arch);
  const training_ds   = _lookupTraining("dataset_size",    dataset_size, arch);
  const training_vol  = _lookupTraining("data_volatility", data_vol,     arch);
  const training: [number, number]    = [training_ds[0] + training_vol[0], training_ds[1] + training_vol[1]];

  const base = _sumRanges([compute, storage, api_inference, networking, training]);
  const maintenance: [number, number] = [Math.round(base[0] * (maintMult - 1)), Math.round(base[1] * (maintMult - 1))];
  const preSec = _sumRanges([base, maintenance]);
  const secAddn: [number, number] = [Math.round(preSec[0] * (secMult - 1)), Math.round(preSec[1] * (secMult - 1))];
  return _sumRanges([preSec, secAddn]);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function buildInitialValues(result: AnalysisResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [key, cfg] of Object.entries(SIGNAL_CONFIG)) {
    const extractedValue = result.signals?.[key]?.value ?? null;
    const idx = extractedValue ? cfg.options.indexOf(extractedValue) : -1;
    // If signal was extracted, use its exact value
    // If missing, default to index 0 (lowest/safest value)
    out[key] = idx >= 0 ? idx : 0;
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
    <div style={{ minHeight: 320, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--border-radius-lg)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
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

  const handleSliderChange = useCallback(
  (signalKey: string, rawValue: number) => {
    const updated = { ...sliderValues, [signalKey]: rawValue };
    setSliderValues(updated);

    // If all sliders match original extracted values, clear preview
    const initial = buildInitialValues(result);
    const isReset = Object.keys(initial).every(k => initial[k] === updated[k]);
    if (isReset) {
      setPreviewResult(null);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchPreview(updated), 300);
  },
  [sliderValues, fetchPreview, result]
);

  const handleReset = useCallback(() => {
    const initial = buildInitialValues(result);
    setSliderValues(initial);
    setPreviewResult(null);
    setSaveError(null);
  }, [result]);

  const handleOpen = useCallback(() => {
    setIsOpen(true);
  }, []);

  const handleSaveConfirmed = useCallback(async () => {
  setShowConfirm(false);
  setSaving(true);
  setSaveError(null);
  try {
    const signals = sliderValuesToSignals(sliderValues);
    await submitFollowUp(result.analysis_id, signals);
    
    // Re-fetch fresh result instead of using returned value
    const { getAnalysis } = await import("@/lib/api");
    const freshResult = await getAnalysis(result.analysis_id);
// Preserve followup_questions so Refine Architecture stays visible
const mergedResult = {
  ...freshResult,
  followup_questions: result.followup_questions,
};
setPreviewResult(null);
onResultUpdate?.(mergedResult);
  } catch (e: any) {
    console.error("[WhatIfEditor] Save failed:", e);
    setSaveError("Save failed. Please try again later.");
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
  // Compute newArchCost live from current slider signals (not stale cost table)
  const newArchCost: [number, number] | null = previewResult && newArch
    ? estimateMonthlyCost(sliderValuesToSignals(sliderValues), newArch)
    : null;

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
      {/* Current recommendation summary card */}
<div className="mb-4 grid grid-cols-2 gap-3">
  {/* Original */}
  <div className="p-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
    <p className="text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">
      Original
    </p>
    <p className="text-base font-black mb-1" style={{ color: ARCH_COLOR_MAP[originalArch] ?? "var(--text-primary)" }}>
      {result.architecture_details?.[originalArch]?.full_name ?? originalArch}
    </p>
    {originalCost && (
      <p className="text-xs text-[var(--text-secondary)]">
        {formatCost(originalCost[0])} – {formatCost(originalCost[1])}/mo
      </p>
    )}
  </div>

  {/* Current/Live */}
  <div className={`p-4 rounded-2xl border transition-all duration-300 ${
    recommendationChanged
      ? "border-[var(--primary)]/30 bg-[var(--primary)]/5"
      : "border-[var(--border)] bg-[var(--surface)]"
  }`}>
    <p className="text-[10px] font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">
      {recommendationChanged ? "⚡ Changed to" : "Current"}
    </p>
    <p className="text-base font-black mb-1" style={{ color: ARCH_COLOR_MAP[displayRecommended] ?? "var(--text-primary)" }}>
      {result.architecture_details?.[displayRecommended]?.full_name ?? displayRecommended}
    </p>
    {recommendationChanged && newArchCost ? (
      <p className="text-xs text-[var(--text-secondary)]">
        {formatCost(newArchCost[0])} – {formatCost(newArchCost[1])}/mo
      </p>
    ) : originalCost ? (
      <p className="text-xs text-[var(--text-secondary)]">
        {formatCost(originalCost[0])} – {formatCost(originalCost[1])}/mo
      </p>
    ) : null}
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-6 pt-2">
  {Object.entries(SIGNAL_CONFIG).map(([key, cfg]) => {
    const idx = sliderValues[key] ?? 0;
    const total = cfg.options.length;
    const pct = total > 1 ? (idx / (total - 1)) * 100 : 0;
    return (
      <div key={key}>
        {/* Label row */}
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm text-[var(--text-secondary)]">{cfg.label}</span>
          <motion.span
            key={cfg.optionLabels[idx]}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-sm font-bold text-[var(--text-primary)]"
          >
            {cfg.optionLabels[idx]}
          </motion.span>
        </div>

        {/* Custom checkpoint track */}
                    <div className="relative h-8 flex items-center">
                      {/* Hidden native range -- handles drag/keyboard, sits above everything */}
                      <input
                        type="range"
                        min={0}
                        max={total - 1}
                        step={1}
                        value={idx}
                        onChange={e => handleSliderChange(key, Number(e.target.value))}
                        className="absolute inset-0 w-full opacity-0 cursor-pointer"
                        style={{ zIndex: 10 }}
                      />
                      {/* Background track */}
                      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[3px] rounded-full bg-[var(--border)]" />
                      {/* Filled track */}
                      <div
                        className="absolute top-1/2 -translate-y-1/2 h-[3px] rounded-full transition-all duration-200"
                        style={{
                          width: `${pct}%`,
                          background: "var(--primary)",
                        }}
                      />

          {/* Checkpoint dots */}
          {cfg.options.map((_, dotIdx) => {
            const dotPct = total > 1 ? (dotIdx / (total - 1)) * 100 : 0;
            const isActive = dotIdx <= idx;
            const isCurrent = dotIdx === idx;
            return (
              <button
                key={dotIdx}
                onClick={() => handleSliderChange(key, dotIdx)}
                title={cfg.optionLabels[dotIdx]}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 transition-all duration-200 focus:outline-none"
                style={{
                  left: `calc(8px + (100% - 16px) * ${dotPct} / 100)`,
                  width:  isCurrent ? 22 : 16,
                  height: isCurrent ? 22 : 16,
                  borderColor: isActive ? "var(--primary)" : "var(--border)",
                  backgroundColor: isActive ? "var(--primary)" : "var(--surface)",
                  boxShadow: isCurrent ? "0 0 0 3px color-mix(in srgb, var(--primary) 25%, transparent)" : "none",
                  zIndex: isCurrent ? 2 : 1,
                }}
              />
            );
          })}
        </div>

        {/* Checkpoint labels */}
        <div className="relative mt-1.5" style={{ height: 14 }}>
          {cfg.optionLabels.map((label, dotIdx) => {
            const dotPct = total > 1 ? (dotIdx / (total - 1)) * 100 : 0;
            const isCurrent = dotIdx === idx;
            const align = dotIdx === 0 ? "left" : dotIdx === total - 1 ? "right" : "center";
            return (
              <span
                key={dotIdx}
                className="absolute text-[9px] transition-all duration-200 whitespace-nowrap"
                style={{
                  left: `calc(8px + (100% - 16px) * ${dotPct} / 100)`,
                  transform: align === "center" ? "translateX(-50%)" : align === "right" ? "translateX(-100%)" : "none",
                  color: isCurrent ? "var(--primary)" : "var(--text-secondary)",
                  fontWeight: isCurrent ? 700 : 400,
                  opacity: isCurrent ? 1 : 0.5,
                }}
              >
                {label}
              </span>
            );
          })}
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
