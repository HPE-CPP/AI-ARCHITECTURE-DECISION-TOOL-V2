"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Loader2 } from "lucide-react";

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string, description: string) => Promise<void> | void;
  initialName?: string;
  initialDescription?: string;
  mode?: "create" | "edit";
}

const MAX_NAME = 60;
const MAX_DESC = 200;

export function CreateProjectModal({
  isOpen,
  onClose,
  onSubmit,
  initialName = "",
  initialDescription = "",
  mode = "create",
}: CreateProjectModalProps) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [loading, setLoading] = useState(false);
  const [nameError, setNameError] = useState("");

  // Reset form when modal opens with new initial values
  React.useEffect(() => {
    if (isOpen) {
      setName(initialName);
      setDescription(initialDescription);
      setNameError("");
      setLoading(false);
    }
  }, [isOpen, initialName, initialDescription]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setNameError("Project name is required."); return; }
    if (name.trim().length > MAX_NAME) { setNameError(`Name must be ${MAX_NAME} characters or fewer.`); return; }
    try {
      setLoading(true);
      await onSubmit(name.trim(), description.trim());
      onClose();
    } catch (err: any) {
      console.error("[CreateProject] Failed to save project:", err);
      setNameError("Unable to save project right now.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[90] flex items-center justify-center p-4"
          style={{ backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", background: "rgba(0,0,0,0.65)" }}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 10 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            className="w-full max-w-md"
          >
            <div
              className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
              style={{ background: "var(--surface)" }}
            >
              {/* Glow accent */}
              <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-white/5 blur-3xl pointer-events-none" />

              <div className="relative z-10 p-5 sm:p-8">
                {/* Header */}
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-black tracking-tight text-[color:var(--text-primary)]">
                      {mode === "create" ? "New Project" : "Edit Project"}
                    </h2>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mt-1">
                      {mode === "create" ? "Start analyzing your architecture use case." : "Update your project details."}
                    </p>
                  </div>
                  <button
                    onClick={onClose}
                    className="w-8 h-8 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)]/5 transition-all shrink-0 mt-0.5"
                  >
                    <X size={14} />
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                  {/* Project Name */}
                  <div>
                    <label className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)] mb-1.5 block">
                      Project Name <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="project-name-input"
                      type="text"
                      value={name}
                      onChange={(e) => { setName(e.target.value); setNameError(""); }}
                      placeholder="e.g. RAG Pipeline for Customer Support"
                      maxLength={MAX_NAME}
                      className="w-full px-5 py-3.5 rounded-full border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--text-primary)] text-sm font-medium placeholder:text-[color:var(--text-secondary)]/50 focus:outline-none focus:border-[color:var(--text-primary)] transition-colors"
                      autoFocus
                    />
                    <div className="flex items-center justify-between mt-1.5 px-1">
                      <AnimatePresence>
                        {nameError && (
                          <motion.p
                            initial={{ opacity: 0, y: -4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className="text-red-400 text-xs font-medium"
                          >
                            {nameError}
                          </motion.p>
                        )}
                      </AnimatePresence>
                      <span className="text-[color:var(--text-secondary)] text-[10px] font-medium ml-auto">
                        {name.length}/{MAX_NAME}
                      </span>
                    </div>
                  </div>

                  {/* Description */}
                  <div>
                    <label className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)] mb-1.5 block">
                      Description <span className="opacity-50">(optional)</span>
                    </label>
                    <textarea
                      id="project-description-input"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Briefly describe the use case or requirements..."
                      maxLength={MAX_DESC}
                      rows={3}
                      className="w-full px-5 py-3.5 rounded-2xl border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--text-primary)] text-sm font-medium placeholder:text-[color:var(--text-secondary)]/50 focus:outline-none focus:border-[color:var(--text-primary)] transition-colors resize-none"
                    />
                    <div className="flex justify-end mt-1 px-1">
                      <span className="text-[color:var(--text-secondary)] text-[10px] font-medium">
                        {description.length}/{MAX_DESC}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 mt-2">
                    <button
                      type="button"
                      onClick={onClose}
                      className="flex-1 py-3.5 rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] font-bold text-sm hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]/30 transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={loading || !name.trim()}
                      id="create-project-submit"
                      className="flex-[2] py-3.5 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
                    >
                      {loading ? (
                        <><Loader2 className="animate-spin" size={16} /> Saving...</>
                      ) : mode === "create" ? (
                        "Create Project"
                      ) : (
                        "Save Changes"
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
