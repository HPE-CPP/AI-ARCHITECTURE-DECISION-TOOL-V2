"use client";
import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import { UploadCloud, PenTool, ArrowRight } from "lucide-react";
import DocumentUpload from "@/components/DocumentUpload";
import QuestionnaireForm from "@/components/QuestionnaireForm";
import { AnimatedSection } from "@/components/AnimatedScroll";

export default function AnalyzePage() {
  const [mode, setMode] = useState<"upload" | "questionnaire" | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

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

      {/* HEADER SECTION */}
      <motion.div
        style={{ opacity: headerOpacity, y: headerY, filter: headerBlur }}
        className="w-full max-w-5xl mx-auto flex flex-col items-center justify-center pt-32 pb-16 px-4 relative z-10 text-center"
      >
        <AnimatedSection delay={0.1}>
          <div className="inline-flex items-center gap-2 px-5 py-1.5 rounded-full border border-[color:var(--border)] text-[0.65rem] font-bold uppercase tracking-widest text-[color:var(--text-secondary)] mb-8 bg-[color:var(--surface)]/50 backdrop-blur-md">
            Analysis Initialized
          </div>
        </AnimatedSection>

        <h1 className="text-5xl sm:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.9] mb-6 text-[color:var(--text-primary)]">
          Select Context <br />
          <span className="opacity-30">Injector.</span>
        </h1>

        <AnimatedSection delay={0.3}>
          <p className="text-lg sm:text-xl text-[color:var(--text-secondary)] max-w-2xl mx-auto font-medium leading-relaxed tracking-tight">
            Handshake document handshake or a <br className="hidden md:block" /> deterministic guided flow.
          </p>
        </AnimatedSection>
      </motion.div>

      <div className="w-full max-w-6xl mx-auto px-4 pb-32">
        <AnimatePresence mode="wait">
          {!mode ? (
            <motion.div
              key="selection"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, scale: 0.95, filter: "blur(20px)", transition: { duration: 0.5 } }}
              className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-5xl mx-auto"
            >
              {/* UPLOAD CARD */}
              <div
                onClick={() => setMode("upload")}
                className="group relative cursor-pointer p-10 border border-[color:var(--border)] rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[480px] shadow-2xl active:scale-[0.98]"
              >
                {/* Icon Container: Flips background but icon color stays primary */}
                <div className="w-20 h-20 mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <UploadCloud size={32} className="text-[color:var(--text-primary)]" />
                </div>

                <h2 className="text-4xl font-black mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                  Document
                </h2>
                <p className="text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-6 max-w-sm">
                  Handshake architecture req-docs through proprietary signal extraction.
                </p>
                <div className="absolute bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-3 uppercase tracking-tighter text-sm">
                  BEGIN HANDSHAKE <ArrowRight size={20} />
                </div>
              </div>

              {/* QUESTIONNAIRE CARD */}
              <div
                onClick={() => setMode("questionnaire")}
                className="group relative cursor-pointer p-10 border border-[color:var(--border)] rounded-[3.5rem] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] transition-colors duration-500 ease-in-out overflow-hidden flex flex-col items-center justify-center text-center h-[480px] shadow-2xl active:scale-[0.98]"
              >
                {/* Icon Container: Flips background but icon color stays primary */}
                <div className="w-20 h-20 mb-10 rounded-full border border-[color:var(--border)] flex items-center justify-center group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <PenTool size={32} className="text-[color:var(--text-primary)]" />
                </div>

                <h2 className="text-4xl font-black mb-5 tracking-tighter text-[color:var(--text-primary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                  Guided Flow
                </h2>
                <p className="text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] opacity-80 transition-colors duration-500 px-6 max-w-sm">
                  Proprietary context flow maps constraints into vector signals.
                </p>
                <div className="absolute bottom-10 opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-500 font-bold text-[color:var(--background)] flex items-center gap-3 uppercase tracking-tighter text-sm">
                  START GUIDED <ArrowRight size={20} />
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
                  onClick={() => setMode(null)}
                  className="px-8 py-4 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)] text-[color:var(--text-primary)] font-bold text-xs uppercase tracking-widest hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all shadow-xl active:scale-95"
                >
                  ← Reset Workspace
                </button>
              </div>

              <div className="w-full relative z-10 glass-panel border border-[color:var(--border)] rounded-[4rem] p-10 sm:p-20 bg-[color:var(--surface)]/70 backdrop-blur-3xl shadow-2xl">
                {mode === "upload" && <DocumentUpload />}
                {mode === "questionnaire" && <QuestionnaireForm />}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}