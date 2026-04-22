"use client";
import React, { useMemo } from "react";
import { AnalysisResult } from "@/lib/api";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, Legend
} from "recharts";
import { motion } from "framer-motion";
import { CheckCircle, Download, Slash } from "lucide-react";
import { exportAnalysis } from "@/lib/api";

export function ResultsDashboard({ result }: { result: AnalysisResult }) {
  const {
    recommended, scores, confidence, ranking, why_not,
    factor_breakdown, architecture_details
  } = result;

  const radarData = useMemo(() => {
    if (!factor_breakdown) return [];
    const signals = Object.keys(Object.values(factor_breakdown)[0] || {});
    return signals.map(signal => {
      const dataPoint: any = { subject: signal.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) };
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
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="glass-panel p-8 md:p-12 relative overflow-hidden flex flex-col lg:flex-row items-center gap-12 group"
      >
        <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full blur-[120px] bg-white/[0.03] pointer-events-none group-hover:bg-white/[0.05] transition-colors duration-700" />

        <div className="flex-1 text-center lg:text-left z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--text-primary)] bg-[var(--background)] text-[var(--text-primary)] mb-8 font-semibold text-sm shadow-sm backdrop-blur-sm">
            <CheckCircle size={16} /> Analysis Complete
          </div>
          <h2 className="text-[var(--text-secondary)] font-bold tracking-widest uppercase mb-4 opacity-80">Recommended Architecture</h2>
          <h1 className="text-6xl md:text-8xl font-black tracking-tighter text-[var(--text-primary)] mb-6 drop-shadow-xl">
            {topArch?.full_name || recommended}
          </h1>
          <p className="text-xl text-[var(--text-secondary)] leading-relaxed max-w-2xl font-medium">
            {topArch?.description}
          </p>
          <button
            onClick={() => exportAnalysis(result)}
            className="mt-10 flex items-center gap-3 px-8 py-4 rounded-full border border-[var(--border)] bg-[var(--background)] hover:bg-[var(--text-primary)] hover:text-[var(--background)] transition-all font-bold shadow-lg shadow-black/5 hover:-translate-y-0.5 group/btn"
          >
            <Download size={20} className="group-hover/btn:text-[var(--background)] text-[var(--text-primary)] transition-colors" /> Download PDF Report
          </button>
        </div>

        <div className="w-full lg:w-auto flex flex-col sm:flex-row gap-4 z-10">
          {/* Confidence Widget */}
          <div className="flex-1 lg:w-48 p-8 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl transition-colors">
            <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-3">Confidence</span>
            <div className="text-5xl font-black text-[var(--primary)]">
              {(confidence! * 100).toFixed(0)}<span className="text-2xl text-[var(--text-secondary)]">%</span>
            </div>
            <div className="w-full h-px border border-[var(--border)] bg-[var(--background)] relative mt-6 overflow-hidden">
              <motion.div 
                initial={{ width: 0 }} 
                animate={{ width: `${confidence! * 100}%` }} 
                transition={{ duration: 1, delay: 0.8 }} 
                className="absolute top-0 left-0 h-full bg-[var(--text-primary)]" 
              />
            </div>
          </div>

          {/* Overall Score Widget */}
          <div className="flex-1 lg:w-48 p-8 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl transition-colors">
            <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-3">Overall Score</span>
            <div className="text-5xl font-black text-[var(--accent)]">
              {scores[recommended].toFixed(1)}<span className="text-2xl text-[var(--text-secondary)]">/100</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* CHARTS SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Factor Breakdown */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="glass-panel p-8"
        >
          <h3 className="text-2xl font-bold mb-8 tracking-tight">Factor Breakdown</h3>
          <div className="h-[350px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }} />
                <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', borderRadius: '16px', color: 'var(--text-primary)', fontWeight: 'bold' }} />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                {ranking?.slice(0, 3).map((arch, i) => (
                  <Radar 
                    key={arch} 
                    name={arch} 
                    dataKey={arch} 
                    stroke={i === 0 ? "var(--primary)" : i === 1 ? "var(--accent)" : "var(--text-secondary)"} 
                    fill={i === 0 ? "var(--primary)" : i === 1 ? "var(--accent)" : "var(--text-secondary)"} 
                    fillOpacity={i === 0 ? 0.3 : 0.1} 
                    strokeWidth={i === 0 ? 3 : 2} 
                  />
                ))}
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Suitability & Why Not */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col gap-8"
        >
          <div className="glass-panel p-8">
            <h3 className="text-2xl font-bold mb-8 tracking-tight">Suitability Comparison</h3>
            <div className="h-[200px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoresData} layout="vertical" margin={{ top: 0, right: 20, left: 30, bottom: 0 }}>
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: 'var(--text-primary)', fontWeight: 'bold' }} />
                  <Bar dataKey="score" radius={[0, 8, 8, 0]} barSize={24}>
                    {scoresData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? "var(--primary)" : index === 1 ? "var(--accent)" : "var(--text-secondary)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-panel p-8 flex-1 bg-[var(--surface)]">
            <h4 className="font-bold text-xl mb-6 flex items-center gap-3">
              <span className="w-8 h-8 rounded-full bg-[var(--background)] border border-red-500/20 text-red-500 flex items-center justify-center">
                <Slash size={14} className="-rotate-135" />
              </span>
              Why not others?
            </h4>
            <div className="space-y-5">
              {Object.entries(why_not || {}).slice(0, 3).map(([arch, reason]) => (
                <div key={arch} className="flex flex-col border-b border-[var(--border)] pb-4 last:border-0 last:pb-0">
                  <span className="text-sm font-bold text-[var(--primary)] mb-1">{arch}</span>
                  <span className="text-sm text-[var(--text-secondary)] leading-relaxed select-text">{reason}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}