"use client";
import React, { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { UploadCloud, PenTool, ArrowRight, Mic } from "lucide-react";
import DocumentUpload from "@/components/DocumentUpload";
import QuestionnaireForm from "@/components/QuestionnaireForm";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { AuthModal } from "@/components/AuthModal";
import { WelcomeBanner } from "@/components/WelcomeBanner";
import { useAuth } from "@/lib/auth-context";
import { getProject, updateProject, getProjectKey } from "@/lib/projects-store";
import { useSearchParams, useRouter, useParams } from "next/navigation";

// ── Voice Input Mode ────────────────────────────────────────────────────────
function VoiceInputMode({
  onComplete,
  onBack,
}: {
  onComplete: (text: string) => void;
  onBack: () => void;
}) {
  const [isRecording, setIsRecording] = React.useState(false);
  const [transcript, setTranscript] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "recording" | "done">("idle");
  const recognitionRef = React.useRef<any>(null);

  const startRecording = () => {
    const SR =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert(
        "Voice input requires Chrome or Edge. Please use a different input method."
      );
      return;
    }
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    let final = "";

    recognition.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + " ";
      }
      setTranscript(final.trim());
    };
    recognition.onend = () => {
      setIsRecording(false);
      if (final.trim()) setStatus("done");
    };
    recognition.onerror = () => setIsRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
    setStatus("recording");
  };

  const stopRecording = () => {
    recognitionRef.current?.stop();
    setIsRecording(false);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 24,
        padding: "20px 0",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <h2
          style={{
            fontFamily: "Space Grotesk,sans-serif",
            fontWeight: 800,
            fontSize: "1.6rem",
            marginBottom: 10,
          }}
        >
          Voice Input
        </h2>
        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "0.9rem",
            maxWidth: 480,
            lineHeight: 1.7,
          }}
        >
          Describe your system requirements out loud. Speak naturally — mention
          data size, latency needs, update frequency, domain, and any technical
          constraints.
        </p>
      </div>

      <div style={{ position: "relative", padding: 40 }}>
        {isRecording &&
          [1, 2, 3].map((i) => (
            <motion.div
              key={i}
              animate={{ scale: [1, 1 + i * 0.3], opacity: [0.4, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.3 }}
              style={{
                position: "absolute",
                inset: -(i * 16),
                borderRadius: "50%",
                border: "2px solid var(--danger)",
                zIndex: 0,
              }}
            />
          ))}
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={isRecording ? stopRecording : startRecording}
          style={{
            position: "relative",
            zIndex: 1,
            width: 90,
            height: 90,
            borderRadius: "50%",
            border: `3px solid ${isRecording ? "var(--danger)" : "var(--primary)"}`,
            background: isRecording
              ? "rgba(255,55,95,0.15)"
              : "rgba(1,169,130,0.12)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "2.2rem",
            boxShadow: isRecording
              ? "0 0 40px rgba(255,55,95,0.4)"
              : "0 0 30px rgba(1,169,130,0.3)",
            transition: "all 0.3s",
          }}
        >
          {isRecording ? "⏹" : "🎤"}
        </motion.button>
      </div>

      <div
        style={{
          fontSize: "0.85rem",
          fontWeight: 600,
          color: isRecording
            ? "var(--danger)"
            : status === "done"
            ? "var(--primary)"
            : "var(--text-secondary)",
        }}
      >
        {isRecording
          ? "● Recording… speak now"
          : status === "done"
          ? "✓ Captured! Review below"
          : "Click mic to start"}
      </div>

      {transcript && (
        <div
          style={{
            width: "100%",
            maxWidth: 560,
            padding: "16px 20px",
            borderRadius: 14,
            background: "rgba(255,255,255,0.04)",
            border: "1px solid var(--border)",
            fontSize: "0.87rem",
            lineHeight: 1.7,
            color: "var(--text-primary)",
            minHeight: 80,
          }}
        >
          {transcript}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        <button
          onClick={onBack}
          style={{
            padding: "10px 24px",
            borderRadius: 100,
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          ← Back
        </button>
        {transcript && (
          <button
            onClick={() => onComplete(transcript)}
            style={{
              padding: "10px 24px",
              borderRadius: 100,
              background: "linear-gradient(135deg,var(--primary),#00875A)",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Use This → Continue to Questions
          </button>
        )}
      </div>

      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--text-muted)",
          textAlign: "center",
          maxWidth: 420,
          lineHeight: 1.65,
        }}
      >
        Example: "We have a large medical knowledge base with 500K documents
        that updates daily. We need sub-second responses and accuracy is
        critical."
      </div>
    </div>
  );
}

// ── Analyze Page Inner ──────────────────────────────────────────────────────
function AnalyzePageInner({ projectId }: { projectId: string }) {
  const [mode, setMode] = useState<
    "upload" | "questionnaire" | "voice" | null
  >(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const { user, signInWithGoogle, signOut } = useAuth();
  const signIn = signInWithGoogle;
  const router = useRouter();
  const searchParams = useSearchParams();
  const [project, setProject] = useState<any>(null);
  const [provider, setProvider] = useState<"openai" | "ollama">("ollama");

  // Auth modal state
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
  const [welcomeVisible, setWelcomeVisible] = useState(false);
  const [welcomeName, setWelcomeName] = useState("");

  useEffect(() => {
    if (projectId) {
      getProject(projectId).then(setProject);
    }
  }, [projectId]);

  useEffect(() => {
    window.scrollTo(0, 0);
    const savedProvider = localStorage.getItem("llm_provider") as any;
    if (savedProvider) setProvider(savedProvider);

    const modeParam = searchParams.get("mode") as
      | "upload"
      | "questionnaire"
      | null;
    if (modeParam === "upload" || modeParam === "questionnaire") {
      setMode(modeParam);
    } else {
      setMode(null);
    }
  }, [projectId, searchParams]);

  const handleModeChange = (
    newMode: "upload" | "questionnaire" | "voice" | null
  ) => {
    setMode(newMode);
    const modeKey = projectId
      ? getProjectKey(projectId, "mode")
      : "analyze_mode";
    if (newMode && newMode !== "voice") {
      localStorage.setItem(modeKey, newMode);
    } else if (!newMode) {
      localStorage.removeItem(modeKey);
      const answersKey = projectId
        ? getProjectKey(projectId, "answers")
        : "questionnaire_answers";
      localStorage.removeItem(answersKey);
    }
  };

  const requireAuth = useCallback((): Promise<void> => {
    if (user) return Promise.resolve();
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

  const handleAnalysisStart = useCallback(
    (analysisId: string) => {
      if (projectId) {
        updateProject(projectId, {
          status: "in_progress",
          analysisId,
          mode: mode ?? undefined,
        });
      }
    },
    [projectId, mode]
  );

  const headerOpacity = useTransform(
    scrollYProgress,
    [0, 0.15, 0.25],
    [1, 1, 0]
  );
  const headerY = useTransform(
    scrollYProgress,
    [0, 0.1, 0.2],
    ["0px", "0px", "-50px"]
  );
  const headerBlur = useTransform(
    scrollYProgress,
    [0, 0.1, 0.2],
    ["blur(0px)", "blur(0px)", "blur(15px)"]
  );

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.98 },
    visible: {
      opacity: 1,
      scale: 1,
      transition: { duration: 1, ease: [0.16, 1, 0.3, 1] },
    },
  } as const;

  return (
    <div
      className="w-full relative min-h-screen flex flex-col items-center overflow-x-hidden pt-0"
      ref={containerRef}
    >
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
        isVisible={welcomeVisible}
        onComplete={handleWelcomeComplete}
      />

      {/* Page content */}
      <motion.div
        className="w-full flex flex-col items-center px-4 sm:px-6 lg:px-8 pb-24"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Header */}
        <motion.div
          style={{ opacity: headerOpacity, y: headerY, filter: headerBlur }}
          className="w-full max-w-5xl pt-16 sm:pt-24 pb-12 sm:pb-20 flex flex-col items-center text-center"
        >
          <AnimatedSection>
            <div className="flex items-center gap-2 mb-6">
              <div
                style={{
                  padding: "4px 14px",
                  borderRadius: 100,
                  border: "1px solid var(--border)",
                  background: "rgba(255,255,255,0.03)",
                  fontSize: "0.65rem",
                  fontFamily: "JetBrains Mono,monospace",
                  letterSpacing: "2px",
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                }}
              >
                {project?.name ?? "New Analysis"}
              </div>
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.1}>
            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-none mb-6">
              <span className="gradient-text">Choose your</span>
              <br />
              input method.
            </h1>
          </AnimatedSection>

          <AnimatedSection delay={0.2}>
            <p
              style={{
                color: "var(--text-secondary)",
                fontSize: "1rem",
                maxWidth: 540,
                lineHeight: 1.75,
              }}
            >
              Provide your requirements by uploading a document, speaking your
              requirements by voice, or answering a guided set of questions.
            </p>
          </AnimatedSection>
        </motion.div>

        {/* Mode Selector / Active mode */}
        <div className="w-full max-w-5xl">
          <AnimatePresence mode="wait">
            {mode === null ? (
              /* ── Selection screen ─────────────────────────────────────── */
              <motion.div
                key="selection"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                {/* Upload + Questionnaire cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 sm:gap-8">
                  {/* Upload Card */}
                  <div
                    onClick={() => handleModeChange("upload")}
                    className="group relative cursor-pointer p-5 sm:p-10 border border-[color:var(--border)] rounded-[2rem] sm:rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[320px] sm:h-[480px] shadow-2xl active:scale-[0.98]"
                  >
                    <div className="w-12 h-12 sm:w-20 sm:h-20 mb-6 sm:mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                      <UploadCloud
                        size={24}
                        className="text-[color:var(--text-primary)] sm:w-8 sm:h-8"
                      />
                    </div>
                    <h2 className="text-xl sm:text-4xl font-black mb-3 sm:mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                      Document Upload
                    </h2>
                    <p className="text-xs sm:text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-2 sm:px-6 max-w-sm">
                      Upload your requirements document and let the system
                      automatically extract key signals for analysis.
                    </p>
                    <div className="absolute bottom-6 sm:bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-2 sm:gap-3 uppercase tracking-tighter text-[10px] sm:text-sm">
                      START <ArrowRight size={14} className="sm:w-5 sm:h-5" />
                    </div>
                  </div>

                  {/* Questionnaire Card */}
                  <div
                    onClick={() => handleModeChange("questionnaire")}
                    className="group relative cursor-pointer p-5 sm:p-10 border border-[color:var(--border)] rounded-[2rem] sm:rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[320px] sm:h-[480px] shadow-2xl active:scale-[0.98]"
                  >
                    <div className="w-12 h-12 sm:w-20 sm:h-20 mb-6 sm:mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                      <PenTool
                        size={24}
                        className="text-[color:var(--text-primary)] sm:w-8 sm:h-8"
                      />
                    </div>
                    <h2 className="text-xl sm:text-4xl font-black mb-3 sm:mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                      Guided Flow
                    </h2>
                    <p className="text-xs sm:text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-2 sm:px-6 max-w-sm">
                      Answer a few structured questions to help us understand
                      your use case and recommend the best architecture.
                    </p>
                    <div className="absolute bottom-6 sm:bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-2 sm:gap-3 uppercase tracking-tighter text-[10px] sm:text-sm">
                      START <ArrowRight size={14} className="sm:w-5 sm:h-5" />
                    </div>
                  </div>
                </div>

                {/* Voice option */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    marginTop: 28,
                  }}
                >
                  <button
                    onClick={() => handleModeChange("voice")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "13px 30px",
                      borderRadius: 100,
                      border: "1px solid var(--border)",
                      background: "rgba(255,255,255,0.04)",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontSize: "0.88rem",
                      fontFamily: "Plus Jakarta Sans,sans-serif",
                      transition: "all 0.25s",
                    }}
                    onMouseEnter={(e) => {
                      const el = e.currentTarget;
                      el.style.borderColor = "var(--primary)";
                      el.style.color = "var(--primary)";
                      el.style.background = "rgba(1,169,130,0.06)";
                    }}
                    onMouseLeave={(e) => {
                      const el = e.currentTarget;
                      el.style.borderColor = "var(--border)";
                      el.style.color = "var(--text-secondary)";
                      el.style.background = "rgba(255,255,255,0.04)";
                    }}
                  >
                    <Mic size={16} />
                    Or describe your requirements by voice
                  </button>
                </motion.div>
              </motion.div>
            ) : (
              /* ── Active mode ──────────────────────────────────────────── */
              <motion.div
                key="active-mode"
                initial={{ opacity: 0, scale: 0.95, filter: "blur(20px)" }}
                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: 20, filter: "blur(10px)" }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-4xl mx-auto"
              >
                {/* Reset button */}
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
                  {mode === "voice" && (
                    <VoiceInputMode
                      onComplete={() => {
                        handleModeChange("questionnaire");
                      }}
                      onBack={() => handleModeChange(null)}
                    />
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}

// ── Page entry point ────────────────────────────────────────────────────────
export default function AnalyzePage() {
  const params = useParams();
  const projectId =
    typeof params?.projectId === "string"
      ? params.projectId
      : Array.isArray(params?.projectId)
      ? params.projectId[0]
      : "";

  if (!projectId) {
    if (typeof window !== "undefined") window.location.href = "/projects";
    return null;
  }

  return (
    <Suspense
      fallback={
        <div className="w-full min-h-screen flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-t-[color:var(--text-primary)] border-[color:var(--border)] animate-spin" />
        </div>
      }
    >
      <AnalyzePageInner projectId={projectId} />
    </Suspense>
  );
}
