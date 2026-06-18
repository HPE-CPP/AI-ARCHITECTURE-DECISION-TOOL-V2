"use client";
import React, { useMemo, useRef, useEffect, useState } from "react";
import { AnalysisResult, CostAnalysisData, exportCostAnalysis } from "@/lib/api";
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { motion } from "framer-motion";
import { IndianRupee, Download, TrendingUp, Zap, AlertTriangle } from "lucide-react";

/** Format integer with Indian comma notation: 1,00,000 */
function fmtInr(n: number): string {
  const s = Math.round(n).toString();
  if (s.length <= 3) return `Rs. ${s}`;
  let result = s.slice(-3);
  let remaining = s.slice(0, -3);
  while (remaining.length > 0) {
    const chunk = remaining.length >= 2 ? remaining.slice(-2) : remaining;
    result = chunk + "," + result;
    remaining = remaining.length >= 2 ? remaining.slice(0, -2) : "";
  }
  return `Rs. ${result}`;
}

/** Short form: Rs. 1.5L, Rs. 2.3Cr, Rs. 45K */
function fmtInrShort(n: number): string {
  if (n === 0) return "Rs. 0";
  if (n >= 10_000_000) return `Rs. ${(n / 10_000_000).toFixed(1)} Cr`;
  if (n >= 100_000) return `Rs. ${(n / 100_000).toFixed(1)} L`;
  if (n >= 1000) return `Rs. ${Math.round(n / 1000)}K`;
  return `Rs. ${n}`;
}

function fmtRange(r: [number, number]): string {
  if (r[0] === r[1]) return fmtInr(r[0]);
  return `${fmtInrShort(r[0])} - ${fmtInrShort(r[1])}`;
}

function fmtAvg(r: [number, number]): number {
  return Math.round((r[0] + r[1]) / 2);
}

const CustomYAxisTick = (props: { x?: number | string; y?: number | string; payload?: { value?: string }; isNarrow?: boolean }) => {
  const { x, y, payload, isNarrow } = props;
  const name = payload?.value || "";
  let line1 = name;
  let line2 = "";

  if (name.length > 15) {
    const spaceIdx = name.indexOf(" ");
    if (spaceIdx > 0 && spaceIdx < 22) {
      line1 = name.slice(0, spaceIdx);
      line2 = name.slice(spaceIdx + 1);
    }
  }

  const xVal = typeof x === 'number' ? x : Number(x) || 0;
  const yVal = typeof y === 'number' ? y : Number(y) || 0;

  return (
    <g transform={`translate(${xVal - 8},${yVal})`}>
      <text x={0} y={0} dy={line2 ? -4 : 4} textAnchor="end" fill="var(--text-primary)" fontSize={isNarrow ? 9 : 11} fontWeight={600}>
        {line1}
      </text>
      {line2 && (
        <text x={0} y={0} dy={isNarrow ? 8 : 10} textAnchor="end" fill="var(--text-primary)" fontSize={isNarrow ? 9 : 11} fontWeight={600}>
          {line2}
        </text>
      )}
    </g>
  );
};

export function CostAnalysis({ data, result }: { data: CostAnalysisData; result: AnalysisResult }) {
  const { architectures, summary, cost_recommendations } = data;

  const comparisonData = useMemo(() => {
    return Object.entries(architectures)
      .map(([key, arch]) => ({
        name: arch.full_name,
        key,
        monthly_low: arch.monthly_total[0],
        monthly_high: arch.monthly_total[1],
        monthly_avg: fmtAvg(arch.monthly_total),
        setup: fmtAvg(arch.setup_cost),
        is_recommended: arch.is_recommended,
      }))
      .sort((a, b) => a.monthly_avg - b.monthly_avg);
  }, [architectures]);

  const breakdownData = useMemo(() => {
    const rec = architectures[summary.recommended];
    if (!rec) return [];
    const totalAvg = fmtAvg(rec.monthly_total);
    return Object.entries(rec.breakdown)
      .map(([, item]) => ({
        name: item.label,
        cost: fmtAvg(item.monthly),
        range: item.monthly,
        pct: totalAvg > 0 ? Math.round((fmtAvg(item.monthly) / totalAvg) * 100) : 0,
      }))
      .filter(d => d.cost > 0)
      .sort((a, b) => b.cost - a.cost);
  }, [architectures, summary.recommended]);

  const efficiencyData = useMemo(() => {
    return Object.entries(summary.efficiency_scores)
      .map(([key, score]) => ({
        name: architectures[key]?.full_name || key,
        key,
        efficiency: score,
        is_best: key === summary.best_value,
      }))
      .sort((a, b) => b.efficiency - a.efficiency);
  }, [summary, architectures]);

  // Measure the chart container so YAxis width and labels adapt to the available space.
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(600);
  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      setChartWidth(entries[0]?.contentRect.width ?? 600);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const recArch = architectures[summary.recommended];
  if (!recArch) return null;

  const isNarrow = chartWidth < 420;
  // YAxis label column width: wide enough to read on desktop, minimal on mobile
  const yAxisWidth = isNarrow ? 90 : 160;
  // Only render the right-side cost labels when there's room for them
  const showBarLabels = chartWidth > 380;

  return (
    <div className="w-full flex flex-col gap-8">
      {/* COST OVERVIEW HERO */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="glass-panel p-6 sm:p-8 md:p-12 relative overflow-hidden group"
      >
        <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full blur-[120px] bg-white/[0.03] pointer-events-none group-hover:bg-white/[0.05] transition-colors duration-700" />

        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-8 z-10 relative">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--border)] bg-[var(--background)] text-[var(--text-primary)] mb-6 font-semibold text-sm">
              <IndianRupee size={16} /> Cost Analysis
            </div>
            <h2 className="text-[var(--text-secondary)] font-bold tracking-widest uppercase mb-3 text-sm opacity-80">
              Estimated Cost for {summary.recommended_name}
            </h2>
            <div className="text-3xl sm:text-5xl md:text-6xl font-black tracking-tighter text-[var(--text-primary)] mb-3 sm:mb-4">
              {fmtRange(recArch.monthly_total)}
              <span className="text-xl text-[var(--text-secondary)] font-medium">{" / month"}</span>
            </div>
            <p className="text-lg text-[var(--text-secondary)] font-medium">
              Annual estimate (incl. setup): {fmtRange(recArch.annual_total)}
            </p>
            <button
              onClick={() => exportCostAnalysis(result)}
              className="mt-6 sm:mt-8 flex items-center gap-3 px-6 sm:px-8 py-3.5 sm:py-4 rounded-full border border-[var(--border)] bg-[var(--background)] hover:bg-[var(--text-primary)] hover:text-[var(--background)] transition-all font-bold shadow-lg shadow-black/5 hover:-translate-y-0.5 group/btn text-sm sm:text-base"
            >
              <Download size={20} className="group-hover/btn:text-[var(--background)] text-[var(--text-primary)] transition-colors" />
              Download Cost Report
            </button>
          </div>

          <div className="flex flex-col sm:flex-row gap-4">
            {/* Setup Cost Widget */}
            <div className="lg:w-44 p-6 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl">
              <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">Setup Cost</span>
              <div className="text-3xl font-black text-[var(--primary)] flex flex-col items-center leading-tight">
                <span>Rs.</span>
                <span>{fmtInrShort(fmtAvg(recArch.setup_cost)).replace('Rs. ', '')}</span>
              </div>
              <span className="text-xs text-[var(--text-secondary)] mt-1">one-time</span>
            </div>

            {/* Cost Per Query Widget */}
            <div className="lg:w-44 p-6 rounded-[2rem] bg-[var(--surface)] border border-[var(--border)] flex flex-col items-center justify-center text-center shadow-xl">
              <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-2">Per Query</span>
              <div className="text-3xl font-black text-[var(--primary)] flex flex-col items-center leading-tight">
                <span>Rs.</span>
                <span>{recArch.cost_per_query[0].toFixed(3)}</span>
              </div>
              <span className="text-xs text-[var(--text-secondary)] mt-1">estimated avg</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* CHARTS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Monthly Cost Comparison */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="glass-panel p-8"
        >
          <h3 className="text-2xl font-bold mb-8 tracking-tight flex items-center gap-3">
            <IndianRupee size={20} /> Monthly Cost Comparison
          </h3>
          <div className="h-[300px] w-full" ref={chartContainerRef}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={comparisonData}
                layout="vertical"
                margin={{ top: 4, right: showBarLabels ? 56 : 8, left: 0, bottom: 4 }}
              >
                <XAxis
                  type="number"
                  tickFormatter={(v) => fmtInrShort(v)}
                  tick={{ fill: 'var(--text-secondary)', fontSize: isNarrow ? 9 : 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickCount={isNarrow ? 3 : 5}
                />
                <YAxis
                  dataKey="name"
                  type="category"
                  width={yAxisWidth}
                  axisLine={false}
                  tickLine={false}
                  tick={(props) => <CustomYAxisTick {...props} isNarrow={isNarrow} />}
                />
                <Tooltip
                  formatter={(value) => [fmtInr(Number(value)), 'Avg Monthly']}
                  contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', borderRadius: '16px', color: 'var(--text-primary)', fontWeight: 'bold' }}
                />
                <Bar
                  dataKey="monthly_avg"
                  radius={[0, 8, 8, 0]}
                  barSize={26}
                  label={showBarLabels ? {
                    position: 'right',
                    formatter: (v: unknown) => fmtInrShort(Number(v)),
                    fill: 'var(--text-secondary)',
                    fontSize: 11,
                    fontWeight: 600,
                  } : false}
                >
                  {comparisonData.map((entry, index) => {
                    const rank = comparisonData.length - 1 - index;
                    const opacities = [100, 75, 50, 25];
                    const opacity = opacities[rank] || 15;
                    return (
                      <Cell
                        key={`cell-${index}`}
                        fill={`color-mix(in srgb, var(--primary) ${opacity}%, transparent)`}
                      />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Cost Breakdown — Recommended */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="glass-panel p-8"
        >
          <h3 className="text-2xl font-bold mb-8 tracking-tight flex items-center gap-3">
            <TrendingUp size={20} /> Breakdown - {summary.recommended_name}
          </h3>
          <div className="space-y-4">
            {breakdownData.map((item, i) => (
              <div key={item.name}>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-bold text-[var(--text-primary)]">{item.name}</span>
                  <span className="text-sm font-bold text-[var(--text-secondary)]">
                    {fmtRange(item.range as [number, number])}
                    <span className="text-xs ml-2 opacity-60">({item.pct}%)</span>
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-[var(--surface)] border border-[var(--border)] overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${item.pct}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, delay: 0.1 * i }}
                    className="h-full rounded-full"
                    style={{
                      backgroundColor: `color-mix(in srgb, var(--primary) ${[100, 85, 70, 55, 40, 25][i] || 15}%, transparent)`
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* EFFICIENCY & RECOMMENDATIONS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Cost Efficiency */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="glass-panel p-8"
        >
          <h3 className="text-2xl font-bold mb-3 tracking-tight flex items-center gap-3">
            <Zap size={20} /> Cost Efficiency
          </h3>
          <p className="text-sm text-[var(--text-secondary)] mb-6">
            Ratio of suitability score to average monthly cost. Higher is better value.
          </p>
          <div className="space-y-4">
            {efficiencyData.map((item, i) => {
              const maxEff = efficiencyData[0]?.efficiency || 1;
              return (
                <div key={item.key} className={`p-4 rounded-2xl border ${item.is_best ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-[var(--border)] bg-[var(--surface)]'}`}>
                  <div className="flex justify-between items-center mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-[var(--text-primary)]">{item.name}</span>
                      {item.is_best && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-500 text-[10px] font-bold uppercase">Best Value</span>
                      )}
                    </div>
                    <span className="text-lg font-black text-[var(--text-primary)]">{item.efficiency.toFixed(2)}</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[var(--background)] border border-[var(--border)] overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${(item.efficiency / maxEff) * 100}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.8, delay: 0.1 * i }}
                      className={`h-full rounded-full ${item.is_best ? 'bg-emerald-500' : 'bg-[var(--primary)]'}`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* Cost Recommendations */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="glass-panel p-8 flex flex-col"
        >
          <h3 className="text-2xl font-bold mb-6 tracking-tight flex items-center gap-3">
            <AlertTriangle size={20} /> Cost Insights
          </h3>
          <div className="space-y-4 flex-1">
            {cost_recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-3 p-4 rounded-2xl bg-[var(--surface)] border border-[var(--border)]">
                <div className="w-6 h-6 rounded-full bg-[var(--primary)] text-[var(--background)] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold">{i + 1}</span>
                </div>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed font-medium">{rec}</p>
              </div>
            ))}
          </div>

          {/* Quick comparison table — scrollable on mobile */}
          <div className="mt-6 rounded-xl border border-[var(--border)] overflow-x-auto">
            <table className="w-full text-left min-w-[280px]">
              <thead className="bg-[var(--surface)]">
                <tr className="text-[var(--text-secondary)] text-xs uppercase tracking-wider">
                  <th className="py-3 px-4 font-bold">Architecture</th>
                  <th className="py-3 px-4 font-bold text-right whitespace-nowrap">Monthly</th>
                  <th className="py-3 px-4 font-bold text-right whitespace-nowrap hidden sm:table-cell">Setup</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(architectures).map(([key, arch]) => (
                  <tr
                    key={key}
                    className={`border-t border-[var(--border)] transition-colors ${arch.is_recommended ? 'bg-[var(--primary)]/5' : 'hover:bg-[var(--surface)]'}`}
                  >
                    <td className="py-3 px-4 text-sm font-bold text-[var(--text-primary)]">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>{arch.full_name}</span>
                        {arch.is_recommended && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--primary)] text-[var(--background)] text-[9px] font-bold shrink-0">REC</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm font-bold text-right text-[var(--text-secondary)] whitespace-nowrap">{fmtRange(arch.monthly_total)}</td>
                    <td className="py-3 px-4 text-sm text-right text-[var(--text-secondary)] whitespace-nowrap hidden sm:table-cell">{fmtRange(arch.setup_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
