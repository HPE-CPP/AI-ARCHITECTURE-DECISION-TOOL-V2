"use client";
import React, { useCallback, useState, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloud, FileText, AlertCircle, CheckCircle2, X,
  Loader2, Clock, Zap, Search, BarChart2, Shield
} from "lucide-react";
import { getProjectKey } from "@/lib/projects-store";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DocumentUploadProps {
  projectId?: string;
  requireAuth?: () => Promise<void>;
  onAnalysisStart?: (analysisId: string) => void;
}

// Status stage display config
const STAGES: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  queued:              { label: "Queued…",             icon: <Clock size={16} />,      color: "#7A8CA0" },
  parsing:             { label: "Parsing document…",   icon: <FileText size={16} />,   color: "#0A84FF" },
  detecting_sections:  { label: "Detecting sections…", icon: <Search size={16} />,     color: "#7F35B2" },
  extracting_signals:  { label: "Extracting signals (heuristic-first — fast!)…",
                                                        icon: <Zap size={16} />,        color: "#FF8300" },
  validating:          { label: "Validating signals…", icon: <Shield size={16} />,     color: "#FF8300" },
  scoring:             { label: "Scoring architectures…",
                                                        icon: <BarChart2 size={16} />,  color: "#01A982" },
  complete:            { label: "Complete!",            icon: <CheckCircle2 size={16}/>,color: "#01A982" },
  error:               { label: "Error",                icon: <AlertCircle size={16} />,color: "#FF375F" },
  needs_followup:      { label: "Follow-up needed",    icon: <AlertCircle size={16} />,color: "#FF8300" },
};

function StatusBar({ status, progress }: { status: string; progress: number }) {
  const stage = STAGES[status] || STAGES["queued"];
  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ color: stage.color, display: "flex", alignItems: "center" }}>{stage.icon}</span>
        <span style={{ fontSize: "0.84rem", fontWeight: 600, color: stage.color }}>{stage.label}</span>
        <span style={{ marginLeft: "auto", fontFamily: "JetBrains Mono,monospace", fontSize: "0.76rem", color: "var(--text-secondary)" }}>{Math.round(progress)}%</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: "rgba(255,255,255,0.07)", overflow: "hidden" }}>
        <motion.div
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          style={{ height: "100%", borderRadius: 3, background: `linear-gradient(90deg, ${stage.color}, ${stage.color}cc)` }}
        />
      </div>
    </div>
  );
}

function AnalysisTraceLog({ trace }: { trace: any[] }) {
  if (!trace?.length) return null;
  return (
    <div style={{ marginTop: 14, padding: "12px 16px", borderRadius: 12, background: "rgba(0,0,0,0.25)", border: "1px solid var(--border)", maxHeight: 160, overflowY: "auto" }}>
      <div style={{ fontFamily: "JetBrains Mono,monospace", fontSize: "0.6rem", letterSpacing: "1.5px", color: "var(--text-muted)", marginBottom: 8 }}>ANALYSIS LOG</div>
      {trace.map((t, i) => (
        <div key={i} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: "0.74rem" }}>
          <span style={{ color: t.status === "complete" ? "#01A982" : t.status === "failed" ? "#FF375F" : "#FF8300", flexShrink: 0, fontFamily: "JetBrains Mono,monospace" }}>
            {t.status === "complete" ? "✓" : t.status === "failed" ? "✗" : "→"}
          </span>
          <span style={{ color: "var(--text-secondary)" }}>{t.step.replace(/_/g, " ")}</span>
          {t.details && <span style={{ color: "var(--text-muted)", marginLeft: "auto", fontFamily: "JetBrains Mono,monospace", fontSize: "0.68rem" }}>{t.details}</span>}
        </div>
      ))}
    </div>
  );
}

export default function DocumentUpload({ projectId, requireAuth, onAnalysisStart }: DocumentUploadProps) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "analyzing" | "done" | "error">("idle");
  const [uploadProgress, setUploadProgress] = useState(0);   // 0-100, real XHR bytes
  const [analysisProgress, setAnalysisProgress] = useState(0); // 0-100, stage-based
  const [analysisStatus, setAnalysisStatus] = useState<string>("queued");
  const [analysisTrace, setAnalysisTrace] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stage → progress mapping
  const stageProgress: Record<string, number> = {
    queued: 8, parsing: 20, detecting_sections: 35,
    extracting_signals: 55, validating: 72, scoring: 88, complete: 100,
  };

  // Poll analysis status
  useEffect(() => {
    if (phase !== "analyzing" || !analysisId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/v1/analysis/${analysisId}`);
        if (!res.ok) return;
        const data = await res.json();
        const status = data.status || "queued";
        setAnalysisStatus(status);
        setAnalysisProgress(stageProgress[status] ?? 50);
        if (data.decision_trace) setAnalysisTrace(data.decision_trace);

        if (status === "complete" || status === "needs_followup") {
          clearInterval(pollRef.current!);
          setPhase("done");
          setTimeout(() => {
            router.push(`/results/${analysisId}${projectId ? `?projectId=${projectId}` : ""}`);
          }, 600);
        } else if (status === "error") {
          clearInterval(pollRef.current!);
          setError(data.error || "Analysis failed. Check backend logs.");
          setPhase("error");
        }
      } catch {}
    };

    poll(); // immediate first poll
    pollRef.current = setInterval(poll, 1200); // poll every 1.2s
    return () => clearInterval(pollRef.current!);
  }, [phase, analysisId, projectId, router]);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFile(accepted[0]);
      setError(null);
      setPhase("idle");
      setUploadProgress(0);
      setAnalysisProgress(0);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
  });

  const handleProcess = async () => {
    if (!file) return;
    try {
      if (requireAuth) await requireAuth();
    } catch { return; }

    setError(null);
    setPhase("uploading");
    setUploadProgress(0);

    const provider = localStorage.getItem("llm_provider") || "ollama";
    const formData = new FormData();
    formData.append("file", file);

    const qs = new URLSearchParams({ provider });
    if (projectId) qs.append("project_id", projectId);

    // Real XHR upload with actual byte progress
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          setUploadProgress(pct);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            const id = data.analysis_id;
            setAnalysisId(id);
            setUploadProgress(100);
            setPhase("analyzing");
            setAnalysisStatus("queued");
            setAnalysisProgress(8);
            onAnalysisStart?.(id);
            if (projectId) {
              localStorage.setItem(getProjectKey(projectId, "analysisId"), id);
              localStorage.setItem(getProjectKey(projectId, "mode"), "upload");
            }
            resolve();
          } catch {
            setError("Invalid server response.");
            setPhase("error");
            reject();
          }
        } else {
          let msg = "Upload failed";
          try { msg = JSON.parse(xhr.responseText).detail || msg; } catch {}
          setError(msg);
          setPhase("error");
          reject();
        }
      };

      xhr.onerror = () => {
        setError("Network error. Is the backend running at " + API + "?");
        setPhase("error");
        reject();
      };

      xhr.open("POST", `${API}/api/v1/upload?${qs.toString()}`);
      xhr.send(formData);
    });
  };

  const handleCancel = () => {
    xhrRef.current?.abort();
    clearInterval(pollRef.current!);
    setFile(null);
    setPhase("idle");
    setUploadProgress(0);
    setAnalysisProgress(0);
    setError(null);
    setAnalysisId(null);
    setAnalysisTrace([]);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="w-full flex flex-col items-center gap-5">
      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ width: "100%", maxWidth: 580, padding: "14px 18px", borderRadius: 14, background: "rgba(255,55,95,0.08)", border: "1px solid rgba(255,55,95,0.25)", color: "var(--danger)", fontSize: "0.84rem", display: "flex", gap: 10, alignItems: "flex-start" }}>
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1 }}>{error}</div>
            <button onClick={() => setError(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)", opacity: 0.7 }}><X size={15} /></button>
          </motion.div>
        )}
      </AnimatePresence>

      {phase === "idle" && !file && (
        /* Drop zone */
        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} style={{ width: "100%" }}>
          <div {...getRootProps()}
            style={{
              width: "100%", borderRadius: 24, border: `2px dashed ${isDragActive ? "var(--primary)" : "var(--border)"}`,
              padding: "52px 24px", textAlign: "center", cursor: "pointer",
              background: isDragActive ? "rgba(1,169,130,0.07)" : "var(--surface)",
              transition: "all 0.25s", transform: isDragActive ? "scale(1.02)" : "scale(1)",
            }}>
            <input {...getInputProps()} />
            <div style={{ width: 72, height: 72, borderRadius: "50%", background: isDragActive ? "var(--primary)" : "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", transition: "all 0.3s" }}>
              <UploadCloud size={32} style={{ color: isDragActive ? "#fff" : "var(--text-secondary)" }} />
            </div>
            <p style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 800, fontSize: "1.3rem", marginBottom: 8 }}>
              {isDragActive ? "Drop your file here" : "Click or drag & drop"}
            </p>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.87rem", lineHeight: 1.6 }}>
              PDF · DOCX · TXT — up to 50MB
            </p>
            <div style={{ marginTop: 18, display: "flex", justifyContent: "center", gap: 10, flexWrap: "wrap" }}>
              {["⚡ Heuristic-first extraction", "🔍 10 signal dimensions", "🎯 4 architectures scored"].map(t => (
                <span key={t} style={{ padding: "4px 12px", borderRadius: 100, background: "rgba(1,169,130,0.08)", border: "1px solid rgba(1,169,130,0.18)", fontSize: "0.72rem", color: "var(--primary)", fontFamily: "JetBrains Mono,monospace" }}>{t}</span>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {file && phase === "idle" && (
        /* File selected — ready to process */
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          style={{ width: "100%", padding: 24, borderRadius: 20, background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 22 }}>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: "rgba(1,169,130,0.1)", border: "1px solid rgba(1,169,130,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <FileText size={26} style={{ color: "var(--primary)" }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</p>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={handleCancel}
              style={{ flex: 1, padding: "12px", borderRadius: 100, border: "1px solid var(--border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontWeight: 600, fontSize: "0.87rem" }}>
              Cancel
            </button>
            <button onClick={handleProcess}
              style={{ flex: 2, padding: "12px", borderRadius: 100, background: "linear-gradient(135deg,var(--primary),#00875A)", color: "#fff", border: "none", cursor: "pointer", fontWeight: 700, fontSize: "0.9rem", boxShadow: "0 0 24px rgba(1,169,130,0.3)" }}>
              Begin Analysis →
            </button>
          </div>
        </motion.div>
      )}

      {phase === "uploading" && (
        /* Real upload progress */
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          style={{ width: "100%", padding: 28, borderRadius: 20, background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <Loader2 size={22} style={{ color: "var(--primary)", animation: "spin 1s linear infinite" }} />
            <div>
              <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 2 }}>Uploading {file?.name}</p>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Sending to analysis server…</p>
            </div>
            <span style={{ marginLeft: "auto", fontFamily: "JetBrains Mono,monospace", fontWeight: 800, fontSize: "1.1rem", color: "var(--primary)" }}>{uploadProgress}%</span>
          </div>
          <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.07)", overflow: "hidden" }}>
            <motion.div animate={{ width: `${uploadProgress}%` }} transition={{ duration: 0.15, ease: "linear" }}
              style={{ height: "100%", borderRadius: 3, background: "linear-gradient(90deg,var(--primary),#00D4FF)", position: "relative", overflow: "hidden" }}>
              <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.3),transparent)", animation: "shimmer 1.5s infinite" }} />
            </motion.div>
          </div>
          <p style={{ marginTop: 10, fontSize: "0.72rem", color: "var(--text-muted)", textAlign: "center", fontFamily: "JetBrains Mono,monospace" }}>
            {((file?.size || 0) * uploadProgress / 100 / 1024).toFixed(0)} KB of {((file?.size || 0) / 1024).toFixed(0)} KB
          </p>
        </motion.div>
      )}

      {phase === "analyzing" && (
        /* Live analysis status */
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          style={{ width: "100%", padding: 28, borderRadius: 20, background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              style={{ width: 28, height: 28, borderRadius: "50%", border: "3px solid rgba(1,169,130,0.2)", borderTop: "3px solid var(--primary)" }} />
            <div>
              <p style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 2 }}>Analysing document…</p>
              <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Heuristic extraction running first — usually 2-8s</p>
            </div>
          </div>
          <StatusBar status={analysisStatus} progress={analysisProgress} />
          <AnalysisTraceLog trace={analysisTrace} />
          <button onClick={handleCancel}
            style={{ marginTop: 16, width: "100%", padding: "10px", borderRadius: 100, border: "1px solid var(--border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.82rem" }}>
            Cancel
          </button>
        </motion.div>
      )}

      {phase === "done" && (
        /* Success flash */
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
          style={{ width: "100%", padding: 32, borderRadius: 20, background: "rgba(1,169,130,0.08)", border: "1px solid rgba(1,169,130,0.3)", textAlign: "center" }}>
          <CheckCircle2 size={48} style={{ color: "var(--primary)", margin: "0 auto 16px" }} />
          <p style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 800, fontSize: "1.2rem", marginBottom: 6 }}>Analysis Complete!</p>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Redirecting to results…</p>
        </motion.div>
      )}

      <style>{`
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes shimmer { 0%{transform:translateX(-100%)} 100%{transform:translateX(200%)} }
      `}</style>
    </div>
  );
}
