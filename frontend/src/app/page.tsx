"use client";
import React, { useRef, useEffect, useState } from "react";
import { m, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Sparkles, Database, Layers, Cpu, Zap, Fingerprint } from "lucide-react";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { Magnetic } from "@/components/Magnetic";
import { ReadyToArchitect } from "@/components/CTA";


export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start start", "end end"] });

  // Detect desktop after mount — avoids SSR mismatch and skips scroll
  // transforms on mobile where they add JS overhead without visual benefit.
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    if (window.location.hash) {
      setTimeout(() => {
        const id = window.location.hash.substring(1);
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } else {
      window.scrollTo(0, 0);
    }
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDesktop(window.matchMedia('(min-width: 768px)').matches);
  }, []);

  // Scroll Transforms
  const heroOpacity = useTransform(scrollYProgress, [0, 0.75, 0.82], [1, 1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.75, 0.82], [1, 1, 0.98]);

  const featuresOpacity = useTransform(scrollYProgress, [0.2, 0.65, 0.72], [1, 1, 0]);
  const featuresScale = useTransform(scrollYProgress, [0.2, 0.65, 0.72], [1, 1, 0.98]);

  const processOpacity = useTransform(scrollYProgress, [0.55, 0.88, 0.92], [1, 1, 0]);
  const processScale = useTransform(scrollYProgress, [0.55, 0.88, 0.92], [1, 1, 0.98]);

  const ctaOpacity = useTransform(scrollYProgress, [0.6, 0.7], [0, 1]);

  return (
    <div className="w-full relative min-h-screen flex flex-col items-center overflow-x-hidden pt-0" ref={containerRef}>

      {/* HERO SECTION */}
      <m.section
        id="home"
        style={isDesktop ? { opacity: heroOpacity, scale: heroScale } : undefined}
        className="min-h-screen flex flex-col items-center justify-center pt-24 px-4 w-full max-w-5xl mx-auto text-center z-10"
      >
        <AnimatedSection delay={0.1}>
          <div className="mb-8 inline-flex items-center gap-3 px-4 py-1.5 rounded-full border border-[color:var(--border)] text-[0.65rem] font-bold uppercase tracking-widest bg-[color:var(--surface)]/50 backdrop-blur-md text-[color:var(--text-secondary)]">
            <Sparkles size={12} className="text-[color:var(--text-primary)]" />
            <span>Architecture Intelligence</span>
          </div>
        </AnimatedSection>

        <div className="mb-10 text-[min(12vw,6rem)] leading-[1.15] font-black tracking-[-0.04em] text-[color:var(--text-primary)] relative">
          <div className="hidden md:block absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[color:var(--text-primary)]/5 blur-[120px] rounded-full -z-10 pointer-events-none" />

          <h1 className="flex flex-col items-center">
            {/* CSS animation — visible immediately from SSR, no JS required for LCP */}
            <span className="block overflow-hidden h-[1.2em] -mb-[0.1em]">
              <span className="block hero-rise">
                Design Your
              </span>
            </span>
            <span className="block overflow-hidden h-[1.2em]">
              <span className="block text-[color:var(--text-secondary)] hero-rise-delay">
                Architecture.
              </span>
            </span>
          </h1>
        </div>

        <AnimatedSection delay={0.2} className="mt-4">
          <p className="text-lg sm:text-xl text-[color:var(--text-secondary)] max-w-xl mx-auto font-medium leading-relaxed tracking-tight">
            Stop guessing between RAG, Fine-Tuning, or CAG. <br className="hidden md:block" />
            Let our deterministic intelligence validate your use case instantly.
          </p>
        </AnimatedSection>

        <AnimatedSection delay={0.4} className="mt-12">
          <Magnetic>
            <Link href="/projects">
              <button className="px-10 py-5 rounded-full text-[color:var(--background)] bg-[color:var(--primary)] font-bold text-sm hover:invert transition-all flex items-center justify-center gap-3 shadow-2xl active:scale-95">
                Begin Analysis <ArrowRight size={18} />
              </button>
            </Link>
          </Magnetic>
        </AnimatedSection>
      </m.section>

      {/* LUXURY SCROLL GAP */}
      <div className="h-[20vh] w-full" />

      {/* FEATURES SECTION */}
      <m.section
        id="features"
        style={isDesktop ? { opacity: featuresOpacity, scale: featuresScale } : undefined}
        className="w-full py-24 min-h-screen flex flex-col justify-center items-center z-20 isolate"
      >
        <div className="max-w-6xl mx-auto px-6 w-full">

          {/* HEADER */}
          <div className="mb-20 flex flex-col items-center text-center">
            <h2 className="text-3xl sm:text-4xl md:text-6xl font-black tracking-tighter mb-6 leading-[1.2] flex flex-col">

              <span className="block overflow-hidden">
                <m.span
                  className="block"
                  initial={{ y: "100%" }}
                  whileInView={{ y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] as const }}
                >
                  Unparalleled
                </m.span>
              </span>

              <span className="block overflow-hidden">
                <m.span
                  className="block opacity-30"
                  initial={{ y: "100%" }}
                  whileInView={{ y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.1, ease: [0.16, 1, 0.3, 1] as const }}
                >
                  Precision.
                </m.span>
              </span>

            </h2>

            <p className="text-[color:var(--text-secondary)] text-lg md:text-xl max-w-2xl mx-auto tracking-tight font-medium">
              Mapping your constraints against state-of-the-art benchmarks.
            </p>
          </div>

          {/* CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { title: "RAG", desc: "Retrieval-Augmented Generation for dynamic data without hallucination.", icon: Database },
              { title: "Fine - Tuning", desc: "Teach models domains, structural behaviors, and specialized tasks.", icon: Cpu },
              { title: "CAG", desc: "Context caching and multi-tier architectures for enterprise scale.", icon: Layers }
            ].map((feature, i) => (

              <m.div
                key={i}
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-10% 0px" }}
                transition={{ duration: 1, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] as const }}

                className="relative z-10 p-6 sm:p-10 text-left group transition-all h-full
                     bg-gradient-to-br from-[color:var(--surface)]/90 via-[color:var(--surface)]/70 to-[color:var(--surface)]/40
                     md:backdrop-blur-[80px] md:backdrop-saturate-[1.8]
                     
                     border border-black/40 dark:border-white/40
                     
                     rounded-[3rem]
                     hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)]
                     duration-700 cursor-default
                     shadow-[0_20px_50px_rgba(0,0,0,0.3)]
                     overflow-hidden"
              >

                {/* Subtle Inner Glow */}
                <div className="absolute inset-0 bg-gradient-to-tr from-white/[0.05] to-transparent pointer-events-none" />

                {/* ICON */}
                <div className="relative z-10 w-14 h-14 rounded-2xl border border-[color:var(--border)] flex items-center justify-center mb-8 group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <feature.icon className="w-6 h-6 text-[color:var(--text-primary)]" />
                </div>

                {/* TITLE */}
                <h3 className="relative z-10 text-2xl sm:text-3xl font-black mb-4 tracking-tighter overflow-hidden">
                  <m.span
                    initial={{ y: "100%" }}
                    whileInView={{ y: 0 }}
                    viewport={{ once: true }}
                    className="block"
                    transition={{ duration: 0.8, ease: "circOut" }}
                  >
                    {feature.title}
                  </m.span>
                </h3>

                {/* DESCRIPTION */}
                <p className="relative z-10 text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)]/90 transition-colors duration-500 font-medium leading-relaxed">
                  {feature.desc}
                </p>

              </m.div>
            ))}
          </div>
        </div>
      </m.section>

      {/* HOW IT WORKS SECTION */}
      <m.section
        id="how-it-works"
        style={isDesktop ? { opacity: processOpacity, scale: processScale } : undefined}
        className="w-full py-24 min-h-screen flex flex-col justify-center items-center z-30"
      >
        <div className="max-w-4xl mx-auto px-6 w-full">
          <h2 className="text-3xl sm:text-5xl md:text-7xl font-black tracking-tighter mb-10 sm:mb-16 text-center leading-[1.1] flex flex-col items-center">
            <span className="block overflow-hidden">
              <m.span
                className="block"
                initial={{ y: "100%" }}
                whileInView={{ y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] as const }}
              >
                The <span className="opacity-20">Process.</span>
              </m.span>
            </span>
          </h2>

          <div className="grid grid-cols-1 gap-5">
            {[
              { step: "01", title: "Requirements Understanding", desc: "We analyze your inputs, whether through documents or guided questions, to identify key factors like data size, update frequency, and complexity.", icon: Fingerprint },
              { step: "02", title: "Signal Extraction & Evaluation", desc: "Your inputs are converted into structured signals and evaluated using deterministic logic to assess suitability across different AI architectures.", icon: Zap },
              { step: "03", title: "Architecture Recommendation", desc: "Based on the analysis, we provide a clear recommendation with rankings, confidence scores, and detailed reasoning for each option.", icon: Layers }
            ].map((step, i) => (
              <m.div
                key={i}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-5% 0px" }}
                transition={{ duration: 1, delay: i * 0.1 }}
                className="flex flex-col md:flex-row items-start md:items-center gap-6 md:gap-8 p-6 sm:p-10 md:p-12 rounded-[2rem] sm:rounded-[3.5rem] border border-[color:var(--border)] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all duration-500 group cursor-default shadow-xl"
              >
                <div className="text-5xl font-black text-[color:var(--text-secondary)] opacity-10 group-hover:opacity-100 group-hover:text-[color:var(--background)] transition-all duration-500 font-mono tracking-tighter min-w-[80px]">
                  {step.step}
                </div>
                <div className="w-16 h-16 rounded-full border border-[color:var(--border)] flex items-center justify-center shrink-0 group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <step.icon size={28} className="text-[color:var(--text-primary)] group-hover:text-[color:var(--text-primary)]" />
                </div>
                <div className="flex-1">
                  <h3 className="text-xl sm:text-3xl font-black mb-2 tracking-tighter overflow-hidden">
                    <m.span
                      className="block"
                      initial={{ y: "100%" }}
                      whileInView={{ y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.8, ease: "circOut" }}
                    >
                      {step.title}
                    </m.span>
                  </h3>
                  <p className="text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                    {step.desc}
                  </p>
                </div>
              </m.div>
            ))}
          </div>
        </div>
      </m.section>
      {/* CTA SECTION - Renders only on Home */}
      <ReadyToArchitect />


    </div>
  );
}