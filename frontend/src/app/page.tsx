"use client";
import React, { useRef, useEffect } from "react";
import { motion, useScroll, useTransform, useIsPresent } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Sparkles, Database, Layers, Cpu, Zap, Fingerprint } from "lucide-react";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { Magnetic } from "@/components/Magnetic";

// Refined "Rise Up" variant for the Hero to ensure smoothness
const heroRiseVariant = {
  initial: { y: "110%", opacity: 0 },
  animate: {
    y: 0,
    opacity: 1,
    transition: {
      duration: 1.4,
      ease: [0.16, 1, 0.3, 1], // Custom cubic-bezier for luxury feel
    }
  }
} as const;

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start start", "end end"] });

  useEffect(() => {
    window.scrollTo(0, 0);
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  // Scroll Transforms
  const heroOpacity = useTransform(scrollYProgress, [0, 0.75, 0.82], [1, 1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.75, 0.82], [1, 1, 0.98]);
  const heroBlur = useTransform(scrollYProgress, [0, 0.78, 0.82], ["blur(0px)", "blur(0px)", "blur(20px)"]);

  const featuresOpacity = useTransform(scrollYProgress, [0.2, 0.65, 0.72], [1, 1, 0]);
  const featuresScale = useTransform(scrollYProgress, [0.2, 0.65, 0.72], [1, 1, 0.98]);
  const featuresBlur = useTransform(scrollYProgress, [0.2, 0.68, 0.72], ["blur(0px)", "blur(0px)", "blur(20px)"]);

  const processOpacity = useTransform(scrollYProgress, [0.55, 0.88, 0.92], [1, 1, 0]);
  const processScale = useTransform(scrollYProgress, [0.55, 0.88, 0.92], [1, 1, 0.98]);
  const processBlur = useTransform(scrollYProgress, [0.55, 0.9, 0.92], ["blur(0px)", "blur(0px)", "blur(20px)"]);

  const ctaOpacity = useTransform(scrollYProgress, [0.6, 0.7], [0, 1]);

  return (
    <div className="w-full relative min-h-screen flex flex-col items-center overflow-x-hidden pt-0" ref={containerRef}>

      {/* HERO SECTION */}
      <motion.section
        id="home"
        style={{ opacity: heroOpacity, scale: heroScale, filter: heroBlur }}
        className="min-h-screen flex flex-col items-center justify-center pt-24 px-4 w-full max-w-5xl mx-auto text-center z-10"
      >
        <AnimatedSection delay={0.1}>
          <div className="mb-8 inline-flex items-center gap-3 px-4 py-1.5 rounded-full border border-[color:var(--border)] text-[0.65rem] font-bold uppercase tracking-widest bg-[color:var(--surface)]/50 backdrop-blur-md text-[color:var(--text-secondary)]">
            <Sparkles size={12} className="text-[color:var(--text-primary)]" />
            <span>Architecture Intelligence</span>
          </div>
        </AnimatedSection>

        <div className="mb-10 text-[min(12vw,6rem)] leading-[1.15] font-black tracking-[-0.04em] text-[color:var(--text-primary)] relative">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[color:var(--text-primary)]/5 blur-[120px] rounded-full -z-10 pointer-events-none" />

          <h1 className="flex flex-col items-center">
            <span className="block overflow-hidden h-[1.2em] -mb-[0.1em]">
              <motion.span
                className="block"
                variants={heroRiseVariant}
                initial="initial"
                animate="animate"
              >
                Design your
              </motion.span>
            </span>
            <span className="block overflow-hidden h-[1.2em]">
              <motion.span
                className="block text-[color:var(--text-secondary)]"
                variants={heroRiseVariant}
                initial="initial"
                animate="animate"
                transition={{ ...heroRiseVariant.animate.transition, delay: 0.15 }}
              >
                AI architecture.
              </motion.span>
            </span>
          </h1>
        </div>

        <AnimatedSection delay={1.4} className="mt-4">
          <p className="text-lg sm:text-xl text-[color:var(--text-secondary)] max-w-xl mx-auto font-medium leading-relaxed tracking-tight">
            Stop guessing between RAG, Fine-Tuning, or CAG. <br className="hidden md:block" />
            Let our deterministic intelligence validate your use case instantly.
          </p>
        </AnimatedSection>

        <AnimatedSection delay={1.6} className="mt-12">
          <Magnetic>
            <Link href="/analyze">
              <button className="px-10 py-5 rounded-full text-[color:var(--background)] bg-[color:var(--primary)] font-bold text-sm hover:invert transition-all flex items-center justify-center gap-3 shadow-2xl active:scale-95">
                Begin Analysis <ArrowRight size={18} />
              </button>
            </Link>
          </Magnetic>
        </AnimatedSection>
      </motion.section>

      {/* LUXURY SCROLL GAP */}
      <div className="h-[20vh] w-full" />

      {/* FEATURES SECTION */}
      <motion.section
        id="features"
        style={{ opacity: featuresOpacity, scale: featuresScale, filter: featuresBlur }}
        className="w-full py-24 min-h-screen flex flex-col justify-center items-center z-20"
      >
        <div className="max-w-6xl mx-auto px-6 w-full">
          <div className="mb-20 flex flex-col items-center text-center">
            <h2 className="text-4xl md:text-6xl font-black tracking-tighter mb-6 leading-[1.2] flex flex-col">
              <span className="block overflow-hidden">
                <motion.span
                  className="block"
                  initial={{ y: "100%" }}
                  whileInView={{ y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] as const }}
                >
                  Unparalleled
                </motion.span>
              </span>
              <span className="block overflow-hidden">
                <motion.span
                  className="block opacity-30"
                  initial={{ y: "100%" }}
                  whileInView={{ y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: 0.1, ease: [0.16, 1, 0.3, 1] as const }}
                >
                  Precision.
                </motion.span>
              </span>
            </h2>
            <p className="text-[color:var(--text-secondary)] text-lg md:text-xl max-w-2xl mx-auto tracking-tight font-medium">
              Mapping your constraints against state-of-the-art benchmarks.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { title: "RAG", desc: "Retrieval-Augmented Generation for dynamic data without hallucination.", icon: Database },
              { title: "Fine-Tuning", desc: "Teach models domains, structural behaviors, and specialized tasks.", icon: Cpu },
              { title: "CAG", desc: "Context caching and multi-tier architectures for enterprise scale.", icon: Layers }
            ].map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-10% 0px" }}
                transition={{ duration: 1, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] as const }}
                className="relative z-10 p-10 text-left group transition-all h-full bg-[color:var(--surface)]/50 backdrop-blur-3xl border border-[color:var(--border)] rounded-[3rem] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] duration-700 cursor-default shadow-xl"
              >
                <div className="w-14 h-14 rounded-2xl border border-[color:var(--border)] flex items-center justify-center mb-8 group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <feature.icon className="w-6 h-6 text-[color:var(--text-primary)]" />
                </div>
                <h3 className="text-3xl font-black mb-4 tracking-tighter overflow-hidden">
                  <motion.span
                    initial={{ y: "100%" }}
                    whileInView={{ y: 0 }}
                    viewport={{ once: true }}
                    className="block"
                    transition={{ duration: 0.8, ease: "circOut" }}
                  >
                    {feature.title}
                  </motion.span>
                </h3>
                <p className="text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] transition-colors duration-500 font-medium">
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      {/* HOW IT WORKS SECTION */}
      <motion.section
        id="how-it-works"
        style={{ opacity: processOpacity, scale: processScale, filter: processBlur }}
        className="w-full py-24 min-h-screen flex flex-col justify-center items-center z-30"
      >
        <div className="max-w-4xl mx-auto px-6 w-full">
          <h2 className="text-5xl md:text-7xl font-black tracking-tighter mb-16 text-center leading-[1.1] flex flex-col items-center">
            <span className="block overflow-hidden">
              <motion.span
                className="block"
                initial={{ y: "100%" }}
                whileInView={{ y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] as const }}
              >
                The <span className="opacity-20">Process.</span>
              </motion.span>
            </span>
          </h2>

          <div className="grid grid-cols-1 gap-5">
            {[
              { step: "01", title: "Context Injection", desc: "Handshake architecture req-docs through proprietary signal extraction.", icon: Fingerprint },
              { step: "02", title: "Signal Analysis", desc: " Engine maps constraints into deterministic signal vectorization.", icon: Zap },
              { step: "03", title: "Output Logic", desc: "A mathematically proven recommendation with factor-based rationale.", icon: Layers }
            ].map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-5% 0px" }}
                transition={{ duration: 1, delay: i * 0.1 }}
                className="flex flex-col md:flex-row items-start md:items-center gap-8 p-10 md:p-12 rounded-[3.5rem] border border-[color:var(--border)] bg-[color:var(--surface)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all duration-500 group cursor-default shadow-xl"
              >
                <div className="text-5xl font-black text-[color:var(--text-secondary)] opacity-10 group-hover:opacity-100 group-hover:text-[color:var(--background)] transition-all duration-500 font-mono tracking-tighter min-w-[80px]">
                  {step.step}
                </div>
                <div className="w-16 h-16 rounded-full border border-[color:var(--border)] flex items-center justify-center shrink-0 group-hover:bg-[color:var(--background)] group-hover:border-transparent transition-all duration-500">
                  <step.icon size={28} className="text-[color:var(--text-primary)] group-hover:text-[color:var(--text-primary)]" />
                </div>
                <div className="flex-1">
                  <h3 className="text-3xl font-black mb-2 tracking-tighter overflow-hidden">
                    <motion.span
                      className="block"
                      initial={{ y: "100%" }}
                      whileInView={{ y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.8, ease: "circOut" }}
                    >
                      {step.title}
                    </motion.span>
                  </h3>
                  <p className="text-lg font-medium text-[color:var(--text-secondary)] group-hover:text-[color:var(--background)] transition-colors duration-500">
                    {step.desc}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      {/* READY TO ARCHITECT (CTA) */}
      <motion.section
        style={{ opacity: ctaOpacity }}
        className="w-full min-h-screen flex flex-col justify-center items-center py-24 px-6 text-center z-[999] relative isolate"
      >
        <div className="absolute inset-0 bg-[color:var(--background)] z-[-1]" />

        <div className="max-w-4xl mx-auto w-full flex flex-col items-center relative z-10">
          <h2 className="text-6xl md:text-8xl font-black tracking-tighter mb-10 leading-[1.15] flex flex-col">
            <span className="block overflow-hidden h-[1.2em] -mb-[0.1em]">
              <motion.span
                className="block"
                initial={{ y: "100%" }}
                whileInView={{ y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] as const }}
              >
                Ready to
              </motion.span>
            </span>
            <span className="block overflow-hidden h-[1.2em]">
              <motion.span
                className="block opacity-30 text-[0.8em]"
                initial={{ y: "100%" }}
                whileInView={{ y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 1.2, delay: 0.15, ease: [0.16, 1, 0.3, 1] as const }}
              >
                architect.
              </motion.span>
            </span>
          </h2>

          <p className="text-xl text-[color:var(--text-secondary)] mb-14 max-w-xl mx-auto tracking-tight font-medium">
            Join engineers accelerating deployments intelligently.
          </p>

          <Magnetic>
            <Link href="/analyze">
              <button className="px-12 py-5 text-xl font-bold rounded-full bg-[color:var(--primary)] text-[color:var(--background)] hover:invert hover:scale-105 transition-all duration-500 flex items-center gap-6 shadow-2xl">
                Begin Analysis <ArrowRight size={24} />
              </button>
            </Link>
          </Magnetic>
        </div>
      </motion.section>
    </div>
  );
}