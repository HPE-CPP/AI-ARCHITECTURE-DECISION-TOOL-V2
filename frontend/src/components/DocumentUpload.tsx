"use client";
import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, AlertCircle, Loader2, CheckCircle2, X } from "lucide-react";
import { uploadDocument } from "@/lib/api";
import { getProjectKey } from "@/lib/projects-store";

interface DocumentUploadProps {
  projectId?: string;
  requireAuth?: () => Promise<void>;
  onAnalysisStart?: (analysisId: string) => void;
}

export default function DocumentUpload({ projectId, requireAuth, onAnalysisStart }: DocumentUploadProps) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
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
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const handleProcess = async () => {
    if (!file) return;
    try {
      // Show auth gate if provided
      if (requireAuth) await requireAuth();

      setUploading(true);
      setError(null);
      setProgress(10);

      const provider = localStorage.getItem("llm_provider") || "ollama";

      // Simulating progress while uploading
      const progressInterval = setInterval(() => {
        setProgress(p => Math.min(p + 15, 90));
      }, 500);

      const res = await uploadDocument(file, provider, projectId);

      clearInterval(progressInterval);
      setProgress(100);

      // Notify parent of analysis start for project tracking
      onAnalysisStart?.(res.analysis_id);

      // Per-project storage
      if (projectId) {
        localStorage.setItem(getProjectKey(projectId, "analysisId"), res.analysis_id);
        localStorage.setItem(getProjectKey(projectId, "mode"), "upload");
      }

      setTimeout(() => {
        router.push(`/results/${res.analysis_id}${projectId ? `?projectId=${projectId}` : ""}`);
      }, 500);

    } catch (err: any) {
      setError(err.message || "Failed to upload document");
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="w-full flex flex-col items-center">
      <AnimatePresence mode="wait">
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-start gap-3 text-sm w-full max-w-xl"
          >
            <AlertCircle size={20} className="shrink-0 mt-0.5" />
            <p className="flex-1">{error}</p>
            <button onClick={() => setError(null)} className="opacity-70 hover:opacity-100">
              <X size={16} />
            </button>
          </motion.div>
        )}
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
              rounded-3xl border-2 border-dashed p-12 text-center overflow-hidden
              ${isDragActive
                ? "border-[color:var(--primary)] bg-[color:var(--primary)]/5 scale-[1.02]"
                : "border-[color:var(--border)] hover:border-[color:var(--primary)]/50 bg-[color:var(--surface)] hover:bg-[color:var(--surface)]/80"
              }
            `}
          >
            <div className="absolute inset-0 bg-white opacity-0 group-hover:opacity-[0.02] transition-opacity" />
            <input {...getInputProps()} />

            <div className={`w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 transition-all duration-500 ${isDragActive ? "bg-[color:var(--primary)] text-[color:var(--background)] scale-110" : "bg-[color:var(--background)] group-hover:scale-110 shadow-inner group-hover:bg-[color:var(--primary)] group-hover:text-[color:var(--background)]"
              }`}>
              <UploadCloud size={40} className={`transition-colors duration-300 ${isDragActive ? "" : "text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)]"
                }`} />
            </div>

            <p className="text-2xl font-bold mb-3 text-[color:var(--text-primary)]">
              {isDragActive ? "Drop your file here" : "Click or drag & drop"}
            </p>
            <p className="text-[color:var(--text-secondary)] font-medium max-w-sm mx-auto">
              Supported formats: PDF, DOCX, TXT. Maximum file size 50MB.
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full relative overflow-hidden rounded-3xl bg-[color:var(--surface)] border border-[color:var(--border)] shadow-xl"
        >
          {/* Progress Bar Background */}
          {uploading && (
            <div className="absolute top-0 left-0 w-full h-1 bg-[color:var(--background)]">
              <motion.div
                className="h-full bg-[color:var(--primary)]"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          )}

          <div className="p-8">
            <div className="flex items-center gap-6 mb-8">
              <div className="w-16 h-16 rounded-2xl bg-[color:var(--background)] flex items-center justify-center border border-[color:var(--border)] shrink-0 shadow-sm">
                <FileText size={32} className="text-[color:var(--primary)]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-xl truncate mb-1 text-[color:var(--text-primary)]">
                  {file.name}
                </p>
                <p className="text-[color:var(--text-secondary)] font-medium">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
              {progress === 100 && (
                <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                  <CheckCircle2 size={32} className="text-[color:var(--primary)]" />
                </motion.div>
              )}
            </div>

            <div className="flex gap-4">
              <button
                id="cancel-upload-btn"
                onClick={() => { setFile(null); setError(null); }}
                disabled={uploading}
                className="flex-1 py-4 px-6 rounded-full font-semibold border border-[color:var(--border)] hover:bg-[color:var(--background)] transition-all disabled:opacity-50 text-[color:var(--text-primary)]"
              >
                Cancel
              </button>
              <button
                id="begin-analysis-btn"
                onClick={handleProcess}
                disabled={uploading}
                className="flex-[2] py-4 px-6 rounded-full font-bold bg-[color:var(--primary)] text-[color:var(--background)] shadow-lg hover:invert transition-all flex items-center justify-center gap-2 disabled:opacity-80 disabled:cursor-not-allowed disabled:transform-none"
              >
                {uploading ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    {progress < 100 ? `Analyzing... ${progress}%` : "Finalizing..."}
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
