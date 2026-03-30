/**
 * PDF report generator — loaded ONLY via dynamic import() on the client.
 * No top-level imports from jspdf/fflate so Turbopack never traces them during SSR.
 */
import { AnalysisResult } from "./api";

// Brand colours (for PDF white background)
const C = {
  primary: [20, 20, 20] as [number, number, number],
  accent: [79, 70, 229] as [number, number, number],
  muted: [107, 114, 128] as [number, number, number],
  success: [16, 185, 129] as [number, number, number],
  warning: [245, 158, 11] as [number, number, number],
  danger: [239, 68, 68] as [number, number, number],
  bg: [249, 250, 251] as [number, number, number],
  white: [255, 255, 255] as [number, number, number],
  border: [229, 231, 235] as [number, number, number],
};

function label(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function checkPage(doc: any, y: number, needed = 30): number {
  if (y + needed > doc.internal.pageSize.getHeight() - 25) {
    doc.addPage();
    return 25;
  }
  return y;
}

export async function generatePdfReport(result: AnalysisResult): Promise<void> {
  // Dynamic-only imports — never resolved at build/SSR time
  const { default: jsPDF } = await import("jspdf");
  const { default: autoTable } = await import("jspdf-autotable");

  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 20;
  const contentW = pageW - margin * 2;
  let y = 20;

  // ── HEADER ──────────────────────────────────────────────────────────────
  doc.setFillColor(...C.primary);
  doc.rect(0, 0, pageW, 52, "F");

  doc.setTextColor(...C.white);
  doc.setFontSize(24);
  doc.setFont("helvetica", "bold");
  doc.text("ArchGuide", margin, 18);

  doc.setFontSize(11);
  doc.setFont("helvetica", "normal");
  doc.text("Architecture Recommendation Report", margin, 26);

  doc.setFontSize(9);
  doc.setTextColor(200, 200, 200);
  const dateStr = result.created_at
    ? new Date(result.created_at).toLocaleString()
    : new Date().toLocaleString();
  doc.text(`Generated: ${dateStr}`, margin, 34);
  doc.text(`Analysis ID: ${result.analysis_id}`, margin, 40);
  doc.text(`Status: ${result.status}`, margin, 46);

  y = 62;

  // ── RECOMMENDATION SUMMARY ──────────────────────────────────────────────
  const topArch = result.architecture_details?.[result.recommended || ""];
  const archName = topArch?.full_name || result.recommended || "N/A";

  doc.setFillColor(...C.bg);
  doc.roundedRect(margin, y, contentW, 38, 3, 3, "F");
  doc.setDrawColor(...C.accent);
  doc.setLineWidth(0.6);
  doc.roundedRect(margin, y, contentW, 38, 3, 3, "S");

  doc.setTextColor(...C.muted);
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("RECOMMENDED ARCHITECTURE", margin + 6, y + 8);

  doc.setTextColor(...C.primary);
  doc.setFontSize(20);
  doc.setFont("helvetica", "bold");
  doc.text(archName, margin + 6, y + 19);

  doc.setTextColor(...C.muted);
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  const descLines = doc.splitTextToSize(topArch?.description || "", contentW - 12);
  doc.text(descLines, margin + 6, y + 27);

  // Confidence & Score badges
  const badgeX = pageW - margin - 55;
  doc.setFillColor(...C.white);
  doc.roundedRect(badgeX, y + 3, 25, 16, 2, 2, "F");
  doc.setTextColor(...C.muted);
  doc.setFontSize(7);
  doc.setFont("helvetica", "bold");
  doc.text("CONFIDENCE", badgeX + 12.5, y + 8, { align: "center" });
  doc.setTextColor(...C.accent);
  doc.setFontSize(14);
  doc.text(`${((result.confidence || 0) * 100).toFixed(0)}%`, badgeX + 12.5, y + 16, { align: "center" });

  doc.setFillColor(...C.white);
  doc.roundedRect(badgeX + 27, y + 3, 25, 16, 2, 2, "F");
  doc.setTextColor(...C.muted);
  doc.setFontSize(7);
  doc.setFont("helvetica", "bold");
  doc.text("SCORE", badgeX + 39.5, y + 8, { align: "center" });
  doc.setTextColor(...C.accent);
  doc.setFontSize(14);
  const topScore = result.scores?.[result.recommended || ""] ?? 0;
  doc.text(`${topScore.toFixed(1)}`, badgeX + 39.5, y + 16, { align: "center" });

  y += 46;

  // ── ARCHITECTURE SCORES ─────────────────────────────────────────────────
  doc.setTextColor(...C.primary);
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.text("Architecture Scores", margin, y);
  y += 8;

  if (result.scores && result.ranking) {
    const scoreRows = result.ranking.map((arch) => [
      arch,
      result.architecture_details?.[arch]?.full_name || arch,
      `${(result.scores![arch] ?? 0).toFixed(1)} / 100`,
      result.suitability?.[arch] || "-",
    ]);

    autoTable(doc, {
      startY: y,
      head: [["Key", "Architecture", "Score", "Suitability"]],
      body: scoreRows,
      margin: { left: margin, right: margin },
      styles: { fontSize: 9, cellPadding: 3, textColor: C.primary, lineColor: C.border, lineWidth: 0.3 },
      headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold" },
      alternateRowStyles: { fillColor: C.bg },
      columnStyles: { 2: { halign: "center", fontStyle: "bold" }, 3: { halign: "center" } },
    });
    y = (doc as any).lastAutoTable.finalY + 10;
  }

  // ── EXTRACTED SIGNALS ───────────────────────────────────────────────────
  y = checkPage(doc, y, 40);
  doc.setTextColor(...C.primary);
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.text("Extracted Signals", margin, y);
  y += 8;

  if (result.signals) {
    const signalRows = Object.entries(result.signals).map(([key, sig]) => [
      label(key),
      sig.value ? label(sig.value) : "MISSING",
      sig.value ? `${(sig.confidence * 100).toFixed(0)}%` : "-",
      sig.source_text || "-",
    ]);

    autoTable(doc, {
      startY: y,
      head: [["Signal", "Value", "Confidence", "Source"]],
      body: signalRows,
      margin: { left: margin, right: margin },
      styles: { fontSize: 8, cellPadding: 3, textColor: C.primary, lineColor: C.border, lineWidth: 0.3, overflow: "linebreak" as const },
      headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold" },
      alternateRowStyles: { fillColor: C.bg },
      columnStyles: {
        0: { fontStyle: "bold", cellWidth: 35 },
        1: { cellWidth: 30 },
        2: { halign: "center", cellWidth: 22 },
        3: { cellWidth: "auto" as any, fontStyle: "italic", textColor: C.muted },
      },
      didParseCell: (data: any) => {
        if (data.section === "body" && data.column.index === 1 && data.cell.raw === "MISSING") {
          data.cell.styles.textColor = C.danger;
          data.cell.styles.fontStyle = "bold";
        }
      },
    });
    y = (doc as any).lastAutoTable.finalY + 10;
  }

  // ── FACTOR BREAKDOWN ────────────────────────────────────────────────────
  if (result.factor_breakdown && result.ranking) {
    y = checkPage(doc, y, 40);
    doc.setTextColor(...C.primary);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("Factor Breakdown", margin, y);
    y += 8;

    const architectures = result.ranking.slice(0, 4);
    const signals = Object.keys(Object.values(result.factor_breakdown)[0] || {});
    const factorRows = signals.map((sig) => {
      const row: string[] = [label(sig)];
      architectures.forEach((arch) => {
        row.push((result.factor_breakdown![arch]?.[sig] ?? 0).toFixed(2));
      });
      return row;
    });

    autoTable(doc, {
      startY: y,
      head: [["Factor", ...architectures]],
      body: factorRows,
      margin: { left: margin, right: margin },
      styles: { fontSize: 8, cellPadding: 3, textColor: C.primary, lineColor: C.border, lineWidth: 0.3 },
      headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold" },
      alternateRowStyles: { fillColor: C.bg },
      columnStyles: { 0: { fontStyle: "bold" } },
    });
    y = (doc as any).lastAutoTable.finalY + 10;
  }

  // ── WHY NOT OTHERS ──────────────────────────────────────────────────────
  if (result.why_not && Object.keys(result.why_not).length > 0) {
    y = checkPage(doc, y, 40);
    doc.setTextColor(...C.primary);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("Why Not Others?", margin, y);
    y += 8;

    autoTable(doc, {
      startY: y,
      head: [["Architecture", "Reason"]],
      body: Object.entries(result.why_not).map(([arch, reason]) => [arch, reason]),
      margin: { left: margin, right: margin },
      styles: { fontSize: 9, cellPadding: 4, textColor: C.primary, lineColor: C.border, lineWidth: 0.3, overflow: "linebreak" as const },
      headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold" },
      alternateRowStyles: { fillColor: C.bg },
      columnStyles: { 0: { fontStyle: "bold", cellWidth: 35 } },
    });
    y = (doc as any).lastAutoTable.finalY + 10;
  }

  // ── ARCHITECTURE DETAILS ────────────────────────────────────────────────
  if (result.architecture_details) {
    y = checkPage(doc, y, 50);
    doc.setTextColor(...C.primary);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("Architecture Details", margin, y);
    y += 8;

    for (const [key, details] of Object.entries(result.architecture_details)) {
      y = checkPage(doc, y, 35);

      doc.setTextColor(...C.accent);
      doc.setFontSize(11);
      doc.setFont("helvetica", "bold");
      doc.text(`${details.full_name} (${key})`, margin, y);
      y += 5;

      doc.setTextColor(...C.muted);
      doc.setFontSize(8);
      doc.setFont("helvetica", "normal");
      const dl = doc.splitTextToSize(details.description, contentW);
      doc.text(dl, margin, y);
      y += dl.length * 4 + 3;

      const maxLen = Math.max(details.strengths.length, details.weaknesses.length);
      const rows: string[][] = [];
      for (let i = 0; i < maxLen; i++) {
        rows.push([
          details.strengths[i] ? `+ ${details.strengths[i]}` : "",
          details.weaknesses[i] ? `- ${details.weaknesses[i]}` : "",
        ]);
      }

      autoTable(doc, {
        startY: y,
        head: [["Strengths", "Weaknesses"]],
        body: rows,
        margin: { left: margin, right: margin },
        styles: { fontSize: 8, cellPadding: 2.5, lineColor: C.border, lineWidth: 0.2 },
        headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold", fontSize: 8 },
        columnStyles: { 0: { textColor: C.success }, 1: { textColor: C.danger } },
      });
      y = (doc as any).lastAutoTable.finalY + 8;
    }
  }

  // ── SENSITIVITY ANALYSIS ────────────────────────────────────────────────
  if (result.sensitivity) {
    y = checkPage(doc, y, 40);
    doc.setTextColor(...C.primary);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("Sensitivity Analysis", margin, y);
    y += 7;

    const stableColor = result.sensitivity.is_stable ? C.success : C.warning;
    doc.setTextColor(...stableColor);
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text(
      `Stability: ${result.sensitivity.is_stable ? "Stable" : "Unstable"}  |  Score: ${(result.sensitivity.stability_score * 100).toFixed(0)}%`,
      margin, y,
    );
    y += 4;

    if (result.sensitivity.warning) {
      doc.setTextColor(...C.warning);
      doc.setFontSize(8);
      doc.setFont("helvetica", "italic");
      doc.text(result.sensitivity.warning, margin, y);
      y += 5;
    }

    if (result.sensitivity.instabilities.length > 0) {
      y += 2;
      autoTable(doc, {
        startY: y,
        head: [["Signal", "Original", "Perturbed", "Orig. Rec.", "New Rec.", "Delta"]],
        body: result.sensitivity.instabilities.map((inst) => [
          label(inst.signal),
          label(inst.original_value || "N/A"),
          label(inst.perturbed_value),
          inst.original_recommendation,
          inst.new_recommendation,
          inst.score_delta > 0 ? `+${inst.score_delta.toFixed(1)}` : inst.score_delta.toFixed(1),
        ]),
        margin: { left: margin, right: margin },
        styles: { fontSize: 7, cellPadding: 2.5, textColor: C.primary, lineColor: C.border, lineWidth: 0.2 },
        headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold", fontSize: 7 },
        alternateRowStyles: { fillColor: C.bg },
      });
      y = (doc as any).lastAutoTable.finalY + 10;
    }
  }

  // ── DECISION TRACE ──────────────────────────────────────────────────────
  if (result.decision_trace && result.decision_trace.length > 0) {
    y = checkPage(doc, y, 30);
    doc.setTextColor(...C.primary);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("Decision Trace", margin, y);
    y += 8;

    autoTable(doc, {
      startY: y,
      head: [["Step", "Status", "Timestamp", "Details"]],
      body: result.decision_trace.map((t) => [
        label(t.step),
        t.status,
        t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : "-",
        t.details || "-",
      ]),
      margin: { left: margin, right: margin },
      styles: { fontSize: 8, cellPadding: 3, textColor: C.primary, lineColor: C.border, lineWidth: 0.3 },
      headStyles: { fillColor: C.primary, textColor: C.white, fontStyle: "bold" },
      alternateRowStyles: { fillColor: C.bg },
    });
  }

  // ── PAGE FOOTERS ────────────────────────────────────────────────────────
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    const pageH = doc.internal.pageSize.getHeight();
    doc.setDrawColor(...C.border);
    doc.setLineWidth(0.3);
    doc.line(margin, pageH - 15, pageW - margin, pageH - 15);
    doc.setFontSize(7);
    doc.setTextColor(...C.muted);
    doc.setFont("helvetica", "normal");
    doc.text("ArchGuide - Architecture Recommendation Report", margin, pageH - 10);
    doc.text(`Page ${i} of ${totalPages}`, pageW - margin, pageH - 10, { align: "right" });
  }

  doc.save(`ArchGuide_Report_${result.analysis_id}.pdf`);
}
