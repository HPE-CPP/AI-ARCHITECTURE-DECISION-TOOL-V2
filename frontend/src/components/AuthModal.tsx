"use client";
import React, { useState } from "react";
import { motion, AnimatePresence, Variants } from "framer-motion";
import { X, Chrome, AlertTriangle } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: { displayName: string | null; uid: string; email: string | null }) => void;
  onSkip: () => void;
  /** Pass the signIn function from useAuth() */
  signIn: () => Promise<{ displayName: string | null; uid: string; email: string | null }>;
  /** Pass the signOut function from useAuth() */
  signOut: () => Promise<void>;
  mode?: "default" | "project-limit" | "questionnaire-required";
}

export function AuthModal({ isOpen, onClose, onAuthSuccess, onSkip, signIn, signOut, mode = "default" }: AuthModalProps) {
  const [step, setStep] = useState<"main" | "skip-confirm" | "transfer" | "transfer-confirm" | "transfer-collision">("main");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signedInUser, setSignedInUser] = useState<any>(null);
  const [anonProject, setAnonProject] = useState<any>(null);
  const [collidingProjectId, setCollidingProjectId] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    try {
      setLoading(true);
      setError(null);
      const user = await signIn();
      
      const { getProjects } = await import("@/lib/projects-store");
      const anonProjects = await getProjects(null);
      
      if (anonProjects.length > 0) {
        setSignedInUser(user);
        setAnonProject(anonProjects[0]);
        setStep("transfer");
      } else {
        onAuthSuccess(user);
      }
    } catch (err: any) {
      // Handle user closing popup gracefully
      if (err?.code === "auth/popup-closed-by-user" || err?.code === "auth/cancelled-popup-request") {
        setError(null);
      } else if (err?.code === "auth/configuration-not-found" || err?.code === "auth/invalid-api-key") {
        setError("Firebase is not configured. Please add your Firebase credentials to .env.local or skip to continue.");
      } else {
        setError(err?.message || "Sign-in failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSkipRequest = () => setStep("skip-confirm");
  const handleGoBack = () => { setStep("main"); setError(null); };
  const handleContinueAnyway = () => { onSkip(); };

  const handleAcceptTransfer = async () => {
    const { updateProject, getProjects } = await import("@/lib/projects-store");
    if (anonProject && signedInUser) {
      // Check for collision
      const userProjects = await getProjects(signedInUser.uid);
      const collision = userProjects.find(p => p.name.trim().toLowerCase() === anonProject.name.trim().toLowerCase());
      
      if (collision) {
        setCollidingProjectId(collision.id);
        setStep("transfer-collision");
        return;
      }

      await updateProject(anonProject.id, { userId: signedInUser.uid });
    }
    onAuthSuccess(signedInUser);
  };

  const handleReplaceAndTransfer = async () => {
    const { updateProject, deleteProject } = await import("@/lib/projects-store");
    if (anonProject && signedInUser && collidingProjectId) {
      await deleteProject(collidingProjectId);
      await updateProject(anonProject.id, { userId: signedInUser.uid });
    }
    onAuthSuccess(signedInUser);
  };

  const handleSignOutAndRename = async () => {
    await signOut();
    onClose();
  };

  const handleRejectTransfer = () => setStep("transfer-confirm");

  const handleConfirmRejection = async () => {
    const { deleteProject } = await import("@/lib/projects-store");
    if (anonProject) {
      await deleteProject(anonProject.id);
    }
    onAuthSuccess(signedInUser);
  };

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
                  {/* Decorative glow */}
                  <div className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-white/5 blur-3xl pointer-events-none" />
                  <div className="absolute -bottom-20 -left-20 w-60 h-60 rounded-full bg-white/3 blur-3xl pointer-events-none" />

                  <div className="relative z-10 p-5 sm:p-8 lg:p-10">
                    {/* Close button */}
                    <button
                      id="auth-modal-close-btn"
                      onClick={onClose}
                      aria-label="Close sign-in dialog"
                      className="absolute top-5 right-5 w-8 h-8 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)]/5 transition-all"
                    >
                      <X size={14} />
                    </button>

                    {/* Icon */}
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

                    {/* Error */}
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

                    {/* Google Sign-In */}
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

                    {/* Skip / Cancel */}
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
                className="relative w-full max-w-sm"
              >
                <div
                  className="relative overflow-hidden rounded-[2.5rem] border border-[color:var(--border)] shadow-2xl"
                  style={{ background: "var(--surface)", backdropFilter: "blur(40px)" }}
                >
                  <div className="p-8 text-center flex flex-col items-center">
                    <div className="w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/20 flex items-center justify-center mb-5">
                      <Chrome size={26} className="text-blue-400" />
                    </div>
                    <h3 className="text-xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
                      Transfer Project?
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-7 leading-relaxed">
                      Do you want to transfer your unsaved project <span className="text-[color:var(--text-primary)] font-bold">"{anonProject?.name}"</span> to this account?
                    </p>
                    <div className="flex flex-col gap-2 w-full">
                      <button
                        onClick={handleAcceptTransfer}
                        className="w-full py-3.5 px-6 rounded-full border border-[color:var(--border)] text-[color:var(--background)] bg-[color:var(--text-primary)] font-bold text-sm hover:opacity-90 transition-all active:scale-[0.98]"
                      >
                        Yes, Transfer It
                      </button>
                      <button
                        onClick={handleRejectTransfer}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-red-400 transition-colors"
                      >
                        No, Discard It
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : step === "transfer-collision" ? (
              <motion.div
                key="transfer-collision"
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
                      Project Already Exists
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-7 leading-relaxed">
                      Your account already has a project named <span className="text-[color:var(--text-primary)] font-bold">"{anonProject?.name}"</span>. Do you want to replace it?
                    </p>
                    <div className="flex flex-col gap-2 w-full">
                      <button
                        onClick={handleReplaceAndTransfer}
                        className="w-full py-3.5 px-6 rounded-full border border-[color:var(--border)] text-[color:var(--background)] bg-[color:var(--text-primary)] font-bold text-sm hover:opacity-90 transition-all active:scale-[0.98]"
                      >
                        Yes, Replace It
                      </button>
                      <button
                        onClick={handleSignOutAndRename}
                        className="w-full py-3 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
                      >
                        Go Back and Rename
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="transfer-confirm"
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
                      Discard Unsaved Work?
                    </h3>
                    <p className="text-[color:var(--text-secondary)] text-sm font-medium mb-7 leading-relaxed">
                      You will instantly lose this work and it cannot be recovered. Are you sure?
                    </p>
                    <div className="flex flex-col gap-2 w-full">
                      <button
                        onClick={handleConfirmRejection}
                        className="w-full py-3.5 px-6 rounded-full border border-red-500/20 bg-red-500/10 text-red-500 font-bold text-sm hover:bg-red-500/20 transition-all active:scale-[0.98]"
                      >
                        Yes, I'm sure
                      </button>
                      <button
                        onClick={() => setStep("transfer")}
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
