"use client";
import React, { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { UploadCloud, PenTool, ArrowRight } from "lucide-react";
import DocumentUpload from "@/components/DocumentUpload";
import QuestionnaireForm from "@/components/QuestionnaireForm";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { AuthModal } from "@/components/AuthModal";
import { WelcomeBanner } from "@/components/WelcomeBanner";
import { useAuth } from "@/lib/auth-context";
import { getProject, updateProject, getProjectKey } from "@/lib/projects-store";
import { useSearchParams, useRouter } from "next/navigation";

function AnalyzePageInner() {
  const [mode, setMode] = useState<"upload" | "questionnaire" | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const { user, signIn, signOut } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");
  const project = projectId ? getProject(projectId) : null;

  const [provider, setProvider] = useState<"openai" | "ollama">("ollama");

  // Auth modal state
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const [welcomeVisible, setWelcomeVisible] = useState(false);
  const [welcomeName, setWelcomeName] = useState("");

  useEffect(() => {
    window.scrollTo(0, 0);
    const savedProvider = localStorage.getItem("llm_provider") as any;
    if (savedProvider) setProvider(savedProvider);

    // Force user to pick a mode unless they explicitly navigate via Edit Inputs (with a ?mode= param)
    const modeParam = searchParams.get("mode") as "upload" | "questionnaire" | null;
    if (modeParam === "upload" || modeParam === "questionnaire") {
      setMode(modeParam);
    } else {
      setMode(null); // Clear mode to prevent accidentally jumping into a previous session's mode
    }
  }, [projectId, searchParams]);

  const handleModeChange = (newMode: "upload" | "questionnaire" | null) => {
    setMode(newMode);
    const modeKey = projectId ? getProjectKey(projectId, "mode") : "analyze_mode";
    if (newMode) {
      localStorage.setItem(modeKey, newMode);
    } else {
      localStorage.removeItem(modeKey);
      const answersKey = projectId ? getProjectKey(projectId, "answers") : "questionnaire_answers";
      localStorage.removeItem(answersKey);
    }
  };

  const handleProviderChange = (newProvider: "openai" | "ollama") => {
    setProvider(newProvider);
    localStorage.setItem("llm_provider", newProvider);
  };

  /**
   * Called just before analysis starts. If user is not signed in, show auth modal.
   * Returns a promise that resolves when auth is complete (or skipped).
   */
  const requireAuth = useCallback((): Promise<void> => {
    if (user) return Promise.resolve(); // Already signed in
    return new Promise((resolve) => {
      setPendingAction(() => resolve);
      setAuthModalOpen(true);
    });
  }, [user]);

  const handleAuthSuccess = async (u: { displayName: string | null }) => {
    setAuthModalOpen(false);
    const firstName = u.displayName?.split(" ")[0] || "there";
    setWelcomeName(firstName);
    setWelcomeVisible(true);
    // pendingAction will be resolved after welcome banner
  };

  const handleWelcomeComplete = () => {
    setWelcomeVisible(false);
    if (pendingAction) {
      pendingAction();
      setPendingAction(null);
    } else {
      router.push("/projects");
    }
  };

  const handleSkip = () => {
    setAuthModalOpen(false);
    if (pendingAction) {
      pendingAction();
      setPendingAction(null);
    }
  };

  const handleAuthModalClose = () => {
    setAuthModalOpen(false);
    setPendingAction(null);
  };

  // Mark project as in_progress once analysis starts
  const handleAnalysisStart = useCallback((analysisId: string) => {
    if (projectId) {
      updateProject(projectId, {
        status: "in_progress",
        analysisId,
        mode: mode ?? undefined,
      });
    }
  }, [projectId, mode]);

  // Header transforms
  const headerOpacity = useTransform(scrollYProgress, [0, 0.15, 0.25], [1, 1, 0]);
  const headerY = useTransform(scrollYProgress, [0, 0.1, 0.2], ["0px", "0px", "-50px"]);
  const headerBlur = useTransform(scrollYProgress, [0, 0.1, 0.2], ["blur(0px)", "blur(0px)", "blur(15px)"]);

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.98 },
    visible: { opacity: 1, scale: 1, transition: { duration: 1, ease: [0.16, 1, 0.3, 1] } },
  } as const;

  return (
    <div className="w-full relative min-h-screen flex flex-col items-center overflow-x-hidden pt-0" ref={containerRef}>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={handleAuthModalClose}
        onAuthSuccess={handleAuthSuccess}
        onSkip={handleSkip}
        signIn={signIn}
        signOut={signOut}
      />

      {/* Welcome Banner */}
      <WelcomeBanner
        firstName={welcomeName}
        visible={welcomeVisible}
        onComplete={handleWelcomeComplete}
      />

      {/* HEADER SECTION */}
      <motion.div
        style={{ opacity: headerOpacity, y: headerY, filter: headerBlur }}
        className="w-full max-w-5xl mx-auto flex flex-col items-center justify-center pt-24 sm:pt-32 pb-12 sm:pb-16 px-4 relative z-10 text-center"
      >
        <AnimatedSection delay={0.1}>
          <div className="inline-flex items-center gap-2 px-4 sm:px-5 py-1.5 rounded-full border border-[color:var(--border)] text-[0.55rem] sm:text-[0.65rem] font-bold uppercase tracking-widest text-[color:var(--text-secondary)] mb-6 sm:mb-8 bg-[color:var(--surface)]/50 backdrop-blur-md">
            {project ? `Project: ${project.name}` : "Analysis Initialized"}
          </div>
        </AnimatedSection>

        {/* MODEL PROVIDER SELECTOR */}
        <AnimatedSection delay={0.2}>
          <div className="flex items-center gap-1 p-1 bg-[color:var(--surface)]/80 backdrop-blur-xl border border-[color:var(--border)] rounded-full shadow-2xl mb-10 scale-90 sm:scale-100">
            <button
              onClick={() => handleProviderChange("ollama")}
              className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest transition-all ${provider === "ollama"
                ? "bg-[color:var(--text-primary)] text-[color:var(--background)] shadow-lg"
                : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                }`}
            >
              Ollama 3.2
            </button>
            <button
              onClick={() => handleProviderChange("openai")}
              className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest transition-all ${provider === "openai"
                ? "bg-[color:var(--text-primary)] text-[color:var(--background)] shadow-lg"
                : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                }`}
            >
              OpenAI
            </button>
          </div>
        </AnimatedSection>

        <h1 className="text-4xl sm:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.9] mb-6 text-[color:var(--text-primary)]">
          Select Your <br />
          <span className="opacity-30">Input Method.</span>
        </h1>

        <AnimatedSection delay={0.3}>
          <p className="text-base sm:text-xl text-[color:var(--text-secondary)] max-w-2xl mx-auto font-medium leading-relaxed tracking-tight px-4">
            Provide your requirements by uploading a document or answering a guided set of questions.
          </p>
        </AnimatedSection>
      </motion.div>

      <div className="w-full max-w-6xl mx-auto px-3 sm:px-4 pb-32">
        <AnimatePresence mode="wait">
          {!mode ? (
            <motion.div
              key="selection"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, scale: 0.95, filter: "blur(20px)", transition: { duration: 0.5 } }}
              className="grid grid-cols-2 md:grid-cols-2 gap-3 sm:gap-8 w-full max-w-5xl mx-auto"
            >
              {/* UPLOAD CARD */}
              <div
                onClick={() => handleModeChange("upload")}
                className="group relative cursor-pointer p-5 sm:p-10 border border-[color:var(--border)] rounded-[2rem] sm:rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[320px] sm:h-[480px] shadow-2xl active:scale-[0.98]"
              >
                <div className="w-12 h-12 sm:w-20 sm:h-20 mb-6 sm:mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <UploadCloud size={24} className="text-[color:var(--text-primary)] sm:w-8 sm:h-8" />
                </div>
                <h2 className="text-xl sm:text-4xl font-black mb-3 sm:mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                  Document
                </h2>
                <p className="text-xs sm:text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-2 sm:px-6 max-w-sm">
                  Upload your requirements document and let the system automatically extract key signals for analysis.
                </p>
                <div className="absolute bottom-6 sm:bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-2 sm:gap-3 uppercase tracking-tighter text-[10px] sm:text-sm">
                  BEGIN <ArrowRight size={14} className="sm:w-5 sm:h-5" />
                </div>
              </div>

              {/* QUESTIONNAIRE CARD */}
              <div
                onClick={() => handleModeChange("questionnaire")}
                className="group relative cursor-pointer p-5 sm:p-10 border border-[color:var(--border)] rounded-[2rem] sm:rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[320px] sm:h-[480px] shadow-2xl active:scale-[0.98]"
              >
                <div className="w-12 h-12 sm:w-20 sm:h-20 mb-6 sm:mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <PenTool size={24} className="text-[color:var(--text-primary)] sm:w-8 sm:h-8" />
                </div>
                <h2 className="text-xl sm:text-4xl font-black mb-3 sm:mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                  Guided Flow
                </h2>
                <p className="text-xs sm:text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-2 sm:px-6 max-w-sm">
                  Answer a few structured questions to help us understand your use case and recommend the best architecture.
                </p>
                <div className="absolute bottom-6 sm:bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-2 sm:gap-3 uppercase tracking-tighter text-[10px] sm:text-sm">
                  START <ArrowRight size={14} className="sm:w-5 sm:h-5" />
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="active-mode"
              initial={{ opacity: 0, scale: 0.95, filter: "blur(20px)" }}
              animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: 20, filter: "blur(10px)" }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-4xl mx-auto"
            >
              <div className="mb-10 flex justify-center">
                <button
                  onClick={() => handleModeChange(null)}
                  className="px-6 sm:px-8 py-3 sm:py-4 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)] text-[color:var(--text-primary)] font-bold text-[10px] sm:text-xs uppercase tracking-widest hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all shadow-xl active:scale-95"
                >
                  ← Reset Workspace
                </button>
              </div>

              <div className="w-full relative z-10 glass-panel border border-[color:var(--border)] rounded-[2.5rem] sm:rounded-[4rem] p-6 sm:p-20 bg-[color:var(--surface)]/70 backdrop-blur-3xl shadow-2xl">
                {mode === "upload" && (
                  <DocumentUpload
                    projectId={projectId ?? undefined}
                    requireAuth={requireAuth}
                    onAnalysisStart={handleAnalysisStart}
                  />
                )}
                {mode === "questionnaire" && (
                  <QuestionnaireForm
                    projectId={projectId ?? undefined}
                    requireAuth={requireAuth}
                    onAnalysisStart={handleAnalysisStart}
                  />
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense fallback={
      <div className="w-full min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-t-[color:var(--text-primary)] border-[color:var(--border)] animate-spin" />
      </div>
    }>
      <AnalyzePageInner />
    </Suspense>
  );
}