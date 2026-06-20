"use client";
import React, { useState } from "react";
import { motion, AnimatePresence, Variants } from "framer-motion";
import { X, Chrome, AlertTriangle, CheckSquare, Square } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: { displayName: string | null; uid: string; email: string | null }) => void;
  onSkip: () => void;
  signIn: () => Promise<{ displayName: string | null; uid: string; email: string | null }>;
  signOut?: () => Promise<void>; // kept for API compat — no longer used inside the modal
  mode?: "default" | "project-limit" | "questionnaire-required";
}

export function AuthModal({ isOpen, onClose, onAuthSuccess, onSkip, signIn, mode = "default" }: AuthModalProps) {
  const [step, setStep] = useState<"main" | "skip-confirm" | "transfer" | "name-conflicts" | "discard-confirm">("main");
  const [loading, setLoading] = useState(false);
  const [transferring, setTransferring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signedInUser, setSignedInUser] = useState<{ displayName: string | null; uid: string; email: string | null } | null>(null);
  const [anonProjects, setAnonProjects] = useState<{ id: string; name: string }[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [conflicts, setConflicts] = useState<{ id: string; name: string; existingId: string }[]>([]);
  const [resolutions, setResolutions] = useState<Record<string, { action: "replace" | "skip" | "rename"; newName: string }>>({});

  const handleGoogleSignIn = async () => {
    try {
      setLoading(true);
      setError(null);
      const user = await signIn();

      const { getProjects, getAllGuestIds } = await import("@/lib/projects-store");

      // Fetch projects from every guest ID this browser has ever used (covers
      // projects created in older sessions where localStorage was different)
      const guestIds = getAllGuestIds();
      const arrays = await Promise.all(guestIds.map((id: string) => getProjects(id)));
      const seen = new Set<string>();
      const projects = arrays.flat().filter((p: { id: string }) => {
        if (seen.has(p.id)) return false;
        seen.add(p.id);
        return true;
      });

      if (projects.length > 0) {
        setSignedInUser(user);
        setAnonProjects(projects);
        setSelectedIds(new Set(projects.map((p: { id: string; name: string }) => p.id)));
        setStep("transfer");
      } else {
        onAuthSuccess(user);
      }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      const code = err?.code ?? "";
      if (
        code === "auth/popup-closed-by-user" ||
        code === "auth/cancelled-popup-request" ||
        code === "auth/popup-already-open"
      ) {
        // User dismissed the popup or clicked twice — not an error, just reset
        setError(null);
      } else if (code === "auth/missing-or-invalid-nonce") {
        // Stale credential from a previous popup attempt — safe to retry
        setError("Something went wrong with Google's login flow. Please click 'Continue with Google' again.");
      } else if (code === "auth/configuration-not-found" || code === "auth/invalid-api-key") {
        setError("Firebase is not configured. Please add your Firebase credentials to .env.local or skip to continue.");
      } else {
        console.error("[Auth] Sign-in failed:", err);
        setError(err?.message || "Sign-in failed. Please try again later.");
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleProject = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === anonProjects.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(anonProjects.map(p => p.id)));
    }
  };

  const doTransfer = async (
    conflictList: { id: string; name: string; existingId: string }[],
    resolutionMap: Record<string, { action: "replace" | "skip" | "rename"; newName: string }>
  ) => {
    const { updateProject, deleteProject } = await import("@/lib/projects-store");
    const conflictById = new Map(conflictList.map(c => [c.id, c]));
    for (const project of anonProjects) {
      if (selectedIds.has(project.id)) {
        const conflict = conflictById.get(project.id);
        if (conflict) {
          const res = resolutionMap[project.id];
          if (!res || res.action === "skip") {
            await deleteProject(project.id);
          } else if (res.action === "replace") {
            await deleteProject(conflict.existingId);
            const ok = await updateProject(project.id, { userId: signedInUser!.uid });
            if (!ok) throw new Error("replace failed");
          } else {
            const ok = await updateProject(project.id, { userId: signedInUser!.uid, name: res.newName.trim() });
            if (!ok) throw new Error("rename failed");
          }
        } else {
          const ok = await updateProject(project.id, { userId: signedInUser!.uid });
          if (!ok) throw new Error("transfer failed");
        }
      } else {
        await deleteProject(project.id);
      }
    }
  };

  const handleTransferSelected = async () => {
    if (!signedInUser) return;
    setTransferring(true);
    setError(null);
    try {
      const { getProjects } = await import("@/lib/projects-store");
      const userProjects = await getProjects(signedInUser.uid);
      const existingByName = new Map(
        userProjects.map((p: { id: string; name: string }) => [p.name.trim().toLowerCase(), p.id as string])
      );

      const foundConflicts: { id: string; name: string; existingId: string }[] = [];
      for (const project of anonProjects) {
        if (selectedIds.has(project.id)) {
          const existingId = existingByName.get(project.name.trim().toLowerCase());
          if (existingId) foundConflicts.push({ id: project.id, name: project.name, existingId });
        }
      }

      if (foundConflicts.length > 0) {
        const defaultResolutions: Record<string, { action: "replace" | "skip" | "rename"; newName: string }> = {};
        for (const c of foundConflicts) {
          defaultResolutions[c.id] = { action: "rename", newName: `${c.name} (Guest)` };
        }
        setConflicts(foundConflicts);
        setResolutions(defaultResolutions);
        setTransferring(false);
        setStep("name-conflicts");
        return;
      }

      await doTransfer([], {});
    } catch {
      setError("Transfer failed. Please try again.");
      setTransferring(false);
      return;
    }
    const { clearGuestIds } = await import("@/lib/projects-store");
    clearGuestIds();
    setTransferring(false);
    onAuthSuccess(signedInUser);
  };

  const handleApplyResolutions = async () => {
    if (!signedInUser) return;
    setTransferring(true);
    setError(null);
    try {
      await doTransfer(conflicts, resolutions);
    } catch {
      setError("Transfer failed. Please try again.");
      setTransferring(false);
      return;
    }
    const { clearGuestIds } = await import("@/lib/projects-store");
    clearGuestIds();
    setTransferring(false);
    onAuthSuccess(signedInUser);
  };

  const handleDiscardAll = async () => {
    if (!signedInUser) return;
    setTransferring(true);
    setError(null);
    try {
      const { deleteProject, clearGuestIds } = await import("@/lib/projects-store");
      for (const project of anonProjects) {
        await deleteProject(project.id);
      }
      clearGuestIds();
      onAuthSuccess(signedInUser);
    } catch {
      setError("Failed to discard projects. Please try again.");
    } finally {
      setTransferring(false);
    }
  };

  const handleSkipRequest = () => setStep("skip-confirm");
  const handleGoBack = () => { setStep("main"); setError(null); };
  const handleContinueAnyway = () => { onSkip(); };

  const backdropVariants: Variants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
  };

  const modalVariants: Variants = {
    hidden: { opacity: 0, scale: 0.92, y: 20 },
    visible: { opacity: 1, scale: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 28 } },
    exit: { opacity: 0, scale: 0.96, y: 10, transition: { duration: 0.2 } },
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={backdropVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", background: "rgba(0,0,0,0.7)" }}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <AnimatePresence mode="wait">
            {step === "main" ? (
              <motion.div
                key="main"
                variants={modalVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="relative w-full max-w-md"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-white/5 blur-3xl pointer-events-none" />
                  <div className="absolute -bottom-20 -left-20 w-60 h-60 rounded-full bg-white/3 blur-3xl pointer-events-none" />

                  <div className="relative z-10 p-5 sm:p-8 lg:p-10">
                    <button
                      id="auth-modal-close-btn"
                      onClick={onClose}
                      aria-label="Close sign-in dialog"
                      className="absolute top-5 right-5 w-8 h-8 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)]/5 transition-all"
                    >
                      <X size={14} />
                    </button>

                    <div className="w-14 h-14 rounded-2xl bg-[color:var(--text-primary)] flex items-center justify-center mb-6 shadow-lg">
                      <svg viewBox="0 0 24 24" className="w-7 h-7 text-[color:var(--background)]" fill="currentColor">
                        <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" />
                      </svg>
                    </div>

                    <h2 className="text-xl sm:text-2xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
                      {mode === "project-limit" || mode === "questionnaire-required"
                        ? "Sign In Required"
                        : "Save Your Progress"}
                    </h2>
                    <p className="text-[color:var(--text-secondary)] font-medium mb-8 leading-relaxed">
                      {mode === "questionnaire-required"
                        ? "The Guided Flow requires an account to submit your answers. Sign in to continue."
                        : mode === "project-limit"
                        ? "Only one project can be created without signing in. Please sign in to create more projects."
                        : "Sign in to save your analyses and access them anytime from any device."}
                    </p>

                    <AnimatePresence>
                      {error && (
                        <motion.div
                          initial={{ opacity: 0, y: -8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium flex items-start gap-2"
                        >
                          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                          {error}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <button
                      id="google-signin-btn"
                      onClick={handleGoogleSignIn}
                      disabled={loading}
                      className="w-full flex items-center justify-center gap-3 py-3.5 px-6 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed shadow-lg mb-3"
                    >
                      {loading ? (
                        <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                      ) : (
                        <Chrome size={18} />
                      )}
                      {loading ? "Connecting..." : "Continue with Google"}
                    </button>

                    <button
                      onClick={mode === "project-limit" ? onClose : mode === "questionnaire-required" ? onSkip : handleSkipRequest}
                      disabled={loading}
                      className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
                    >
                      {mode === "project-limit" || mode === "questionnaire-required" ? "Cancel" : "Skip for now"}
                    </button>
                  </div>
                </div>
              </motion.div>

            ) : step === "skip-confirm" ? (
              <motion.div
                key="confirm"
                variants={modalVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="relative w-full max-w-sm"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="p-8 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-orange-500/15 border border-orange-500/20 flex items-center justify-center mx-auto mb-5">
                      <AlertTriangle size={26} className="text-orange-400" />
                    </div>
                    <h3 className="text-xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
                      Continue Without Saving?
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-7 leading-relaxed">
                      Your analysis will not be saved and will be lost once you refresh or leave the page.
                    </p>
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={handleContinueAnyway}
                        className="w-full py-3.5 px-6 rounded-full border border-[color:var(--border)] text-[color:var(--text-primary)] font-bold text-sm hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all active:scale-[0.98]"
                      >
                        Continue Anyway
                      </button>
                      <button
                        onClick={handleGoBack}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
                      >
                        Go Back
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>

            ) : step === "transfer" ? (
              <motion.div
                key="transfer"
                variants={modalVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="relative w-full max-w-md"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="p-8 flex flex-col">
                    <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/20 flex items-center justify-center mb-5 self-center">
                      <Chrome size={26} className="text-blue-400" />
                    </div>
                    <h3 className="text-xl font-black tracking-tight text-[color:var(--text-primary)] mb-1 text-center">
                      Transfer Projects
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-5 leading-relaxed text-center">
                      Select which guest projects to move to your account. Unselected projects will be discarded.
                    </p>

                    {/* Select all toggle */}
                    <button
                      onClick={toggleAll}
                      className="flex items-center gap-2 text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors mb-2 self-end"
                    >
                      {selectedIds.size === anonProjects.length ? (
                        <CheckSquare size={14} />
                      ) : (
                        <Square size={14} />
                      )}
                      {selectedIds.size === anonProjects.length ? "Deselect all" : "Select all"}
                    </button>

                    {/* Transfer error */}
                    <AnimatePresence>
                      {error && (
                        <motion.div
                          initial={{ opacity: 0, y: -8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium flex items-start gap-2"
                        >
                          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                          {error}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Project checklist */}
                    <div className="flex flex-col gap-2 max-h-52 overflow-y-auto mb-6 pr-1">
                      {anonProjects.map(project => (
                        <button
                          key={project.id}
                          onClick={() => toggleProject(project.id)}
                          className={`flex items-center gap-3 w-full px-4 py-3 rounded-2xl border text-left transition-all ${
                            selectedIds.has(project.id)
                              ? "border-[color:var(--text-primary)]/30 bg-[color:var(--text-primary)]/8"
                              : "border-[color:var(--border)] bg-transparent opacity-50"
                          }`}
                        >
                          {selectedIds.has(project.id) ? (
                            <CheckSquare size={16} className="shrink-0 text-[color:var(--text-primary)]" />
                          ) : (
                            <Square size={16} className="shrink-0 text-[color:var(--text-secondary)]" />
                          )}
                          <span className="text-sm font-semibold text-[color:var(--text-primary)] truncate">
                            {project.name}
                          </span>
                        </button>
                      ))}
                    </div>

                    <div className="flex flex-col gap-2">
                      <button
                        onClick={handleTransferSelected}
                        disabled={transferring || selectedIds.size === 0}
                        className="w-full py-3.5 px-6 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm hover:opacity-90 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      >
                        {transferring ? (
                          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                          </svg>
                        ) : null}
                        {transferring
                          ? "Transferring..."
                          : selectedIds.size === 0
                          ? "Select at least one project"
                          : `Transfer ${selectedIds.size} Project${selectedIds.size > 1 ? "s" : ""}`}
                      </button>
                      <button
                        onClick={() => setStep("discard-confirm")}
                        disabled={transferring}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-red-400 transition-colors disabled:opacity-50"
                      >
                        Discard All
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>

            ) : step === "name-conflicts" ? (
              <motion.div
                key="name-conflicts"
                variants={modalVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="relative w-full max-w-md"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="p-8 flex flex-col">
                    <div className="w-14 h-14 rounded-2xl bg-yellow-500/15 border border-yellow-500/20 flex items-center justify-center mb-5 self-center">
                      <AlertTriangle size={26} className="text-yellow-400" />
                    </div>
                    <h3 className="text-xl font-black tracking-tight text-[color:var(--text-primary)] mb-1 text-center">
                      Name Conflicts
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-5 leading-relaxed text-center">
                      {conflicts.length} project{conflicts.length > 1 ? "s" : ""} already exist{conflicts.length === 1 ? "s" : ""} with the same name in your account. Choose how to handle each.
                    </p>

                    <AnimatePresence>
                      {error && (
                        <motion.div
                          initial={{ opacity: 0, y: -8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium flex items-start gap-2"
                        >
                          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                          {error}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <div className="flex flex-col gap-3 max-h-72 overflow-y-auto mb-6 pr-1">
                      {conflicts.map(conflict => {
                        const res = resolutions[conflict.id] ?? { action: "rename" as const, newName: `${conflict.name} (Guest)` };
                        return (
                          <div key={conflict.id} className="rounded-2xl border border-[color:var(--border)] p-4 flex flex-col gap-2">
                            <p className="text-xs text-[color:var(--text-secondary)] mb-1">
                              Conflict: <span className="font-bold text-[color:var(--text-primary)]">{conflict.name}</span>
                            </p>
                            <button
                              onClick={() => setResolutions(r => ({ ...r, [conflict.id]: { action: "replace", newName: "" } }))}
                              className={`text-left text-xs px-3 py-2 rounded-xl border transition-all ${res.action === "replace" ? "border-[color:var(--text-primary)]/40 bg-[color:var(--text-primary)]/8 text-[color:var(--text-primary)]" : "border-[color:var(--border)] text-[color:var(--text-secondary)]"}`}
                            >
                              <span className="font-semibold">Replace</span>: overwrite your existing project with this guest one
                            </button>
                            <div
                              className={`text-xs rounded-xl border transition-all cursor-pointer ${res.action === "rename" ? "border-[color:var(--text-primary)]/40 bg-[color:var(--text-primary)]/8" : "border-[color:var(--border)]"}`}
                              onClick={() => {
                                if (res.action !== "rename") {
                                  setResolutions(r => ({ ...r, [conflict.id]: { action: "rename", newName: r[conflict.id]?.newName || `${conflict.name} (Guest)` } }));
                                }
                              }}
                            >
                              <div className="px-3 py-2">
                                <span className={`font-semibold ${res.action === "rename" ? "text-[color:var(--text-primary)]" : "text-[color:var(--text-secondary)]"}`}>Rename</span>
                                {res.action !== "rename" && <span className="text-[color:var(--text-secondary)]">: transfer with a different name</span>}
                              </div>
                              {res.action === "rename" && (
                                <div className="px-3 pb-3" onClick={e => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    value={res.newName}
                                    onChange={e => setResolutions(r => ({ ...r, [conflict.id]: { action: "rename", newName: e.target.value } }))}
                                    className="w-full bg-[color:var(--background)]/50 border border-[color:var(--border)] rounded-lg px-2.5 py-1.5 text-xs text-[color:var(--text-primary)] outline-none focus:border-[color:var(--text-primary)]/50 transition-colors"
                                    placeholder="New project name"
                                    autoFocus
                                  />
                                </div>
                              )}
                            </div>
                            <button
                              onClick={() => setResolutions(r => ({ ...r, [conflict.id]: { action: "skip", newName: "" } }))}
                              className={`text-left text-xs px-3 py-2 rounded-xl border transition-all ${res.action === "skip" ? "border-[color:var(--text-primary)]/40 bg-[color:var(--text-primary)]/8 text-[color:var(--text-primary)]" : "border-[color:var(--border)] text-[color:var(--text-secondary)]"}`}
                            >
                              <span className="font-semibold">Skip</span>: keep your existing project, discard this guest one
                            </button>
                          </div>
                        );
                      })}
                    </div>

                    <div className="flex flex-col gap-2">
                      <button
                        onClick={handleApplyResolutions}
                        disabled={transferring || Object.values(resolutions).some(r => r.action === "rename" && !r.newName.trim())}
                        className="w-full py-3.5 px-6 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm hover:opacity-90 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      >
                        {transferring ? (
                          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                          </svg>
                        ) : null}
                        {transferring ? "Transferring..." : "Continue Transfer"}
                      </button>
                      <button
                        onClick={() => setStep("transfer")}
                        disabled={transferring}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors disabled:opacity-50"
                      >
                        Go Back
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>

            ) : (
              <motion.div
                key="discard-confirm"
                variants={modalVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="relative w-full max-w-sm"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="p-8 text-center flex flex-col items-center">
                    <div className="w-14 h-14 rounded-2xl bg-orange-500/15 border border-orange-500/20 flex items-center justify-center mb-5">
                      <AlertTriangle size={26} className="text-orange-400" />
                    </div>
                    <h3 className="text-xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
                      Discard All Projects?
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-7 leading-relaxed">
                      All {anonProjects.length} guest project{anonProjects.length > 1 ? "s" : ""} will be permanently deleted. This cannot be undone.
                    </p>
                    <div className="flex flex-col gap-2 w-full">
                      <button
                        onClick={handleDiscardAll}
                        disabled={transferring}
                        className="w-full py-3.5 px-6 rounded-full border border-red-500/20 bg-red-500/10 text-red-500 font-bold text-sm hover:bg-red-500/20 transition-all active:scale-[0.98] disabled:opacity-50"
                      >
                        Yes, Discard All
                      </button>
                      <button
                        onClick={() => setStep("transfer")}
                        disabled={transferring}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
                      >
                        Go Back
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
