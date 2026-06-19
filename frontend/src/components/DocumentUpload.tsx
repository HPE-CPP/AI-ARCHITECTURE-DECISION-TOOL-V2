"use client";
import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, AlertCircle, Loader2, CheckCircle2, X, AlertTriangle, FileX, RefreshCw } from "lucide-react";
import { getProjectKey } from "@/lib/projects-store";
import { uploadDocument } from "@/lib/api";

const MAX_SIZE_BYTES = 50 * 1024 * 1024;
const WARN_SIZE_BYTES = 20 * 1024 * 1024;

interface DocumentUploadProps {
  projectId?: string;
  requireAuth?: () => Promise<void>;
  onAnalysisStart?: (analysisId: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

interface ParsedError {
  title: string;
  body: string;
  action: string;
  Icon: React.ElementType;
  variant: "guidance" | "failure";
}

function parseUploadError(message: string): ParsedError {
  const m = message || "";

  if (m.includes("ArchGuide results report") || m.includes("results report")) {
    return {
      title: "This is an ArchGuide report",
      body: "Looks like you uploaded a PDF that ArchGuide already generated. That file is a results summary, not a requirements document.",
      action: "Go back and upload your original project spec or use-case description instead.",
      Icon: RefreshCw,
      variant: "guidance",
    };
  }
  if (m.includes("too short") || m.includes("too little text") || m.includes("empty")) {
    return {
      title: "Document is too short",
      body: "The file you uploaded does not have enough content to work with.",
      action: "Try uploading a document with at least a few paragraphs describing your system.",
      Icon: FileX,
      variant: "guidance",
    };
  }
  if (m.includes("doesn't appear to be") || m.includes("low_coverage") || m.includes("signal categories")) {
    return {
      title: "Looks like the wrong document",
      body: "This file does not seem to contain AI or software system requirements. It might be a report, invoice, or unrelated document.",
      action: "Upload something that describes your system: data sources, expected users, performance needs, security requirements, or deployment setup.",
      Icon: FileX,
      variant: "guidance",
    };
  }
  if (m.includes("very few technical requirement") || m.includes("keyword matches")) {
    return {
      title: "Not enough technical detail",
      body: "The document mentions very little about system requirements.",
      action: "Include details like how much data your system handles, how many users will use it, how fast it needs to respond, and where it will be deployed.",
      Icon: FileX,
      variant: "guidance",
    };
  }
  if (m.includes("signal(s) could be extracted") || m.includes("minimum 3 required")) {
    return {
      title: "Could not read enough requirements",
      body: "The document passed the first check but the AI could not find enough specific requirements inside it.",
      action: "Add more detail about your use case: expected users, data volume, response time targets, security needs, and where the system will run.",
      Icon: AlertTriangle,
      variant: "guidance",
    };
  }
  if (m.includes("corrupted") || m.includes("password-protected") || m.includes("Unable to read")) {
    return {
      title: "Could not open this file",
      body: "The file appears to be corrupted, password-protected, or saved in a format we cannot read.",
      action: "Try exporting it as a plain PDF, or paste the content into a .txt file and upload that.",
      Icon: FileX,
      variant: "failure",
    };
  }
  if (m.includes("Network error") || m.includes("timed out")) {
    return {
      title: "Connection issue",
      body: "The upload could not reach the server.",
      action: "Check your internet connection and try again.",
      Icon: AlertCircle,
      variant: "failure",
    };
  }
  if (m.includes("too large") || m.includes("exceeds")) {
    return {
      title: "File is too large",
      body: "The file exceeds the 50 MB upload limit.",
      action: "Try splitting the document or removing large images before uploading.",
      Icon: AlertTriangle,
      variant: "failure",
    };
  }
  return {
    title: "Upload failed",
    body: "Something went wrong while processing your document.",
    action: "Try again with a different file, or switch to the Guided Flow option instead.",
    Icon: AlertCircle,
    variant: "failure",
  };
}



export default function DocumentUpload({ projectId, requireAuth, onAnalysisStart }: DocumentUploadProps) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPhase, setUploadPhase] = useState<"uploading" | "processing">("uploading");
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected: (rejections) => {
      const first = rejections[0];
      const code = first?.errors[0]?.code;
      if (code === "file-too-large") {
        setError(`File too large (${formatBytes(first.file.size)}). Maximum allowed size is 50 MB.`);
      } else if (code === "file-invalid-type") {
        setError("Unsupported file type. Please upload a PDF, DOCX, or TXT file.");
      } else {
        setError("File could not be accepted. Check the file type and size.");
      }
    },
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
    maxSize: MAX_SIZE_BYTES,
  });

  const handleProcess = async () => {
    if (!file) return;
    try {
      if (requireAuth) await requireAuth();

      setUploading(true);
      setUploadPhase("processing");
      setError(null);
      setProgress(0);
      setStatusMessage("Contacting server...");

      const providerRaw = localStorage.getItem("llm_provider") || "ollama";
      const provider = providerRaw === "groq" ? "openai" : providerRaw;

      const res = await uploadDocument(file, provider, projectId);

      setStatusMessage("Redirecting to results page...");

      onAnalysisStart?.(res.analysis_id);

      if (projectId) {
        localStorage.setItem(getProjectKey(projectId, "analysisId"), res.analysis_id);
        localStorage.setItem(getProjectKey(projectId, "mode"), "upload");
      }

      router.push(`/results/${res.analysis_id}${projectId ? `?projectId=${projectId}` : ""}`);

    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload document");
      setUploading(false);
      setProgress(0);
      setStatusMessage("");
    }
  };

  const isLargeFile = file && file.size > WARN_SIZE_BYTES;

  return (
    <div className="w-full flex flex-col items-center">
      <AnimatePresence mode="wait">
        {error && (() => {
          const { title, body, action, Icon, variant } = parseUploadError(error);
          const isGuidance = variant === "guidance";
          const colors = isGuidance
            ? { border: "border-red-500/25", bg: "bg-red-500/8", icon: "bg-red-500/15 text-red-400", title: "text-red-400", body: "text-red-400/75", divider: "bg-red-500/15", action: "text-red-400/80" }
            : { border: "border-red-500/25", bg: "bg-red-500/8", icon: "bg-red-500/15 text-red-400", title: "text-red-400", body: "text-red-400/75", divider: "bg-red-500/15", action: "text-red-400/70" };

          return (
            <motion.div
              key="upload-error"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className={`mb-6 w-full max-w-xl rounded-2xl border ${colors.border} ${colors.bg} overflow-hidden`}
            >
              <div className="flex items-start gap-3 p-4 pb-3">
                <div className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center ${colors.icon}`}>
                  <Icon size={17} />
                </div>
                <div className="flex-1 min-w-0 pt-0.5">
                  <p className={`text-sm font-bold leading-snug mb-1 ${colors.title}`}>{title}</p>
                  <p className={`text-xs leading-relaxed ${colors.body}`}>{body}</p>
                </div>
                <button
                  onClick={() => setError(null)}
                  className={`shrink-0 opacity-40 hover:opacity-80 transition-opacity pt-0.5 ${colors.title}`}
                >
                  <X size={14} />
                </button>
              </div>
              <div className={`mx-4 h-px ${colors.divider}`} />
              <div className="px-4 py-3 flex items-start gap-2.5">
                <span className={`text-[9px] font-black uppercase tracking-widest shrink-0 mt-px ${colors.title} opacity-50`}>Fix</span>
                <p className={`text-[11px] leading-relaxed font-medium ${colors.action}`}>{action}</p>
              </div>
            </motion.div>
          );
        })()}
      </AnimatePresence>

      {!file ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full"
        >
          <div
            {...getRootProps()}
            className={`
              w-full relative group cursor-pointer transition-all duration-300
              rounded-3xl border-2 border-dashed p-6 sm:p-12 text-center overflow-hidden
              ${isDragActive
                ? "border-[color:var(--primary)] bg-[color:var(--primary)]/5 scale-[1.02]"
                : "border-[color:var(--border)] hover:border-[color:var(--primary)]/50 bg-[color:var(--surface)] hover:bg-[color:var(--surface)]/80"
              }
            `}
          >
            <div className="absolute inset-0 bg-white opacity-0 group-hover:opacity-[0.02] transition-opacity" />
            <input {...getInputProps()} />

            <div className={`w-16 h-16 sm:w-24 sm:h-24 rounded-full flex items-center justify-center mx-auto mb-4 sm:mb-6 transition-all duration-500 ${
              isDragActive
                ? "bg-[color:var(--primary)] text-[color:var(--background)] scale-110"
                : "bg-[color:var(--background)] group-hover:scale-110 shadow-inner group-hover:bg-[color:var(--primary)] group-hover:text-[color:var(--background)]"
            }`}>
              <UploadCloud size={28} className={`sm:w-10 sm:h-10 transition-colors duration-300 ${
                isDragActive ? "" : "text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)]"
              }`} />
            </div>

            <p className="text-lg sm:text-2xl font-bold mb-2 sm:mb-3 text-[color:var(--text-primary)]">
              {isDragActive ? "Drop your file here" : "Click or drag & drop"}
            </p>
            <p className="text-[color:var(--text-secondary)] font-medium mb-5">
              Upload a document to analyse its architecture requirements
            </p>

            {/* Constraint badges */}
            <div className="flex items-center justify-center gap-3 flex-wrap">
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] text-xs font-bold text-[color:var(--text-secondary)]">
                Max 50 MB
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full bg-[color:var(--background)] border border-[color:var(--border)] text-xs font-bold text-[color:var(--text-secondary)]">
                PDF, DOCX, TXT
              </span>
            </div>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full relative overflow-hidden rounded-3xl bg-[color:var(--surface)] border border-[color:var(--border)] shadow-xl"
        >
          {/* Real upload progress bar */}
          {uploading && (
            <div className="absolute top-0 left-0 w-full h-1 bg-[color:var(--background)]">
              <motion.div
                className={`h-full transition-colors ${uploadPhase === "processing" ? "bg-emerald-500" : "bg-[color:var(--primary)]"}`}
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              />
            </div>
          )}

          <div className="p-4 sm:p-8">
            <div className="flex items-start gap-4 sm:gap-6 mb-6">
              <div className="w-16 h-16 rounded-2xl bg-[color:var(--background)] flex items-center justify-center border border-[color:var(--border)] shrink-0 shadow-sm">
                <FileText size={32} className="text-[color:var(--primary)]" />
              </div>

              <div className="flex-1 min-w-0">
                <p className="font-bold text-xl truncate mb-1 text-[color:var(--text-primary)]">
                  {file.name}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[color:var(--text-secondary)] font-medium text-sm">
                    {formatBytes(file.size)}
                  </span>
                  <span className="text-[color:var(--text-secondary)] opacity-40">·</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-[color:var(--text-secondary)] opacity-60">
                    {file.name.split(".").pop()?.toUpperCase()}
                  </span>
                </div>

                {/* Large file warning */}
                {isLargeFile && !uploading && (
                  <div className="flex items-center gap-1.5 mt-2 text-amber-500 text-xs font-semibold">
                    <AlertTriangle size={12} />
                    Large file - analysis may take a few extra minutes
                  </div>
                )}

                {/* Live upload status */}
                {uploading && (
                  <div className="flex items-center gap-2 mt-2">
                    {uploadPhase === "processing" ? (
                      <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
                    ) : (
                      <Loader2 size={14} className="animate-spin text-[color:var(--primary)] shrink-0" />
                    )}
                    <span className={`text-xs font-bold ${uploadPhase === "processing" ? "text-emerald-500" : "text-[color:var(--text-secondary)]"}`}>
                      {statusMessage}
                    </span>
                  </div>
                )}
              </div>

              {uploadPhase === "processing" && uploading && (
                <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                  <CheckCircle2 size={28} className="text-emerald-500 shrink-0" />
                </motion.div>
              )}
            </div>

            <div className="flex gap-4">
              <button
                id="cancel-upload-btn"
                onClick={() => { setFile(null); setError(null); setProgress(0); setStatusMessage(""); }}
                disabled={uploading}
                className="flex-1 py-3 sm:py-4 px-3 sm:px-6 rounded-full font-semibold border border-[color:var(--border)] hover:bg-[color:var(--background)] transition-all disabled:opacity-40 disabled:cursor-not-allowed text-[color:var(--text-primary)] text-sm sm:text-base"
              >
                Cancel
              </button>
              <button
                id="begin-analysis-btn"
                onClick={handleProcess}
                disabled={uploading}
                className="flex-[2] py-3 sm:py-4 px-3 sm:px-6 rounded-full font-bold bg-[color:var(--primary)] text-[color:var(--background)] shadow-lg hover:invert transition-all flex items-center justify-center gap-2 disabled:opacity-80 disabled:cursor-not-allowed disabled:transform-none text-sm sm:text-base"
              >
                {uploading ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    {uploadPhase === "processing" ? "Redirecting..." : `Processing... ${progress}%`}
                  </>
                ) : (
                  "Begin Analysis"
                )}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
