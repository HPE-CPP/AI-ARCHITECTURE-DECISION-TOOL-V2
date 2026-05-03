"use client";
import React, { useRef, useState } from "react";
import { motion, useScroll, useTransform, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight, Sparkles, Database, Layers, Cpu, Zap, Fingerprint,
  Shield, TrendingUp, Clock, CheckCircle, Users, FileText,
  MessageSquare, BarChart2, ChevronDown, BookOpen, Target,
  Lock, Globe, Code2, Lightbulb, Award, RefreshCw
} from "lucide-react";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { Magnetic } from "@/components/Magnetic";
import { AuthModal } from "@/components/AuthModal";
import { useAuth } from "@/lib/auth-context";

const riseUp = {
  initial: { y: "110%", opacity: 0 },
  animate: { y: 0, opacity: 1, transition: { duration: 1.4, ease: [0.16, 1, 0.3, 1] } },
} as const;

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ value, label, color = "#01A982", icon }: { value: string; label: string; color?: string; icon?: string }) {
  return (
    <motion.div variants={{ initial: { opacity: 0, y: 20 }, animate: { opacity: 1, y: 0, transition: { duration: 0.6 } } }}
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", borderRadius: 16, padding: "22px 24px", textAlign: "center" }}>
      {icon && <div style={{ fontSize: "1.6rem", marginBottom: 8 }}>{icon}</div>}
      <div style={{ fontSize: "2.2rem", fontWeight: 900, fontFamily: "Space Grotesk,sans-serif", color, letterSpacing: "-2px", marginBottom: 6 }}>{value}</div>
      <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 500 }}>{label}</div>
    </motion.div>
  );
}

// ── Feature Card ──────────────────────────────────────────────────────────────
function FeatureCard({ icon: Icon, title, desc, detail, color }: { icon: any; title: string; desc: string; detail?: string; color: string }) {
  const [hovered, setHovered] = useState(false);
  return (
    <motion.div initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-8% 0px" }}
      transition={{ duration: 0.9, ease: [0.16,1,0.3,1] }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      style={{ padding: 28, borderRadius: 20, border: `1px solid ${hovered ? color + "44" : "var(--border)"}`, background: hovered ? `${color}08` : "var(--glass-bg)", backdropFilter: "blur(24px)", position: "relative", overflow: "hidden", transition: "all 0.3s", transform: hovered ? "translateY(-4px)" : "none", boxShadow: hovered ? `0 16px 40px ${color}18` : "none" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: hovered ? `linear-gradient(90deg, transparent, ${color}, transparent)` : "transparent", transition: "all 0.3s" }} />
      <div style={{ width: 48, height: 48, borderRadius: 12, background: `${color}18`, border: `1px solid ${color}35`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 18 }}>
        <Icon size={22} style={{ color }} />
      </div>
      <h3 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 700, fontSize: "1.05rem", marginBottom: 10, color: "var(--text-primary)" }}>{title}</h3>
      <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", lineHeight: 1.75 }}>{desc}</p>
      {detail && hovered && (
        <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          style={{ marginTop: 12, fontSize: "0.78rem", color, lineHeight: 1.6, padding: "8px 12px", borderRadius: 8, background: `${color}12`, border: `1px solid ${color}25` }}>
          {detail}
        </motion.p>
      )}
    </motion.div>
  );
}

// ── Step Card ─────────────────────────────────────────────────────────────────
function StepCard({ step, icon: Icon, title, desc, detail, color }: { step: string; icon: any; title: string; desc: string; detail: string; color: string }) {
  return (
    <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true, margin: "-5% 0px" }}
      transition={{ duration: 0.8, ease: [0.16,1,0.3,1] }}
      style={{ display: "flex", gap: 24, padding: "28px 32px", borderRadius: 20, border: "1px solid var(--border)", background: "var(--glass-bg)", backdropFilter: "blur(24px)", alignItems: "flex-start", marginBottom: 14 }}>
      <div style={{ fontFamily: "JetBrains Mono,monospace", fontSize: "2.5rem", fontWeight: 900, color, opacity: 0.25, flexShrink: 0, lineHeight: 1, minWidth: 60 }}>{step}</div>
      <div style={{ width: 52, height: 52, borderRadius: 14, background: `${color}18`, border: `1px solid ${color}35`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Icon size={24} style={{ color }} />
      </div>
      <div style={{ flex: 1 }}>
        <h3 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 800, fontSize: "1.1rem", marginBottom: 8, color: "var(--text-primary)" }}>{title}</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.87rem", lineHeight: 1.75, marginBottom: 12 }}>{desc}</p>
        <div style={{ padding: "10px 14px", borderRadius: 10, background: `${color}10`, border: `1px solid ${color}25`, fontSize: "0.78rem", color, lineHeight: 1.65 }}>
          {detail}
        </div>
      </div>
    </motion.div>
  );
}

// ── FAQ Item ──────────────────────────────────────────────────────────────────
function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: "1px solid var(--border)", padding: "20px 0" }}>
      <button onClick={() => setOpen(o => !o)} style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", background: "none", border: "none", cursor: "pointer", color: "var(--text-primary)", textAlign: "left", gap: 16 }}>
        <span style={{ fontWeight: 700, fontSize: "0.97rem", fontFamily: "Space Grotesk,sans-serif", lineHeight: 1.4 }}>{q}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.3 }} style={{ flexShrink: 0 }}>
          <ChevronDown size={18} style={{ color: "var(--text-secondary)" }} />
        </motion.span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }}>
            <p style={{ marginTop: 14, fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.8, paddingRight: 28 }}>{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Architecture Preview Card ──────────────────────────────────────────────────
function ArchCard({ name, short, desc, pros, cons, color, icon }: any) {
  const [flipped, setFlipped] = useState(false);
  return (
    <motion.div whileHover={{ y: -4 }} onClick={() => setFlipped(f => !f)}
      style={{ padding: 24, borderRadius: 20, border: `1px solid ${color}33`, background: flipped ? `${color}10` : "var(--glass-bg)", backdropFilter: "blur(24px)", cursor: "pointer", transition: "all 0.3s", borderTop: `3px solid ${color}`, minHeight: 200, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 12, right: 14, fontSize: "0.6rem", color: "var(--text-muted)", fontFamily: "JetBrains Mono,monospace" }}>
        {flipped ? "← back" : "click for details"}
      </div>
      {!flipped ? (
        <>
          <div style={{ fontSize: "1.8rem", marginBottom: 12 }}>{icon}</div>
          <div style={{ fontWeight: 800, color, fontSize: "1rem", fontFamily: "Space Grotesk,sans-serif", marginBottom: 4 }}>{name}</div>
          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", fontFamily: "JetBrains Mono,monospace", marginBottom: 12 }}>{short}</div>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>{desc}</p>
        </>
      ) : (
        <>
          <div style={{ fontWeight: 800, color, fontSize: "0.9rem", fontFamily: "Space Grotesk,sans-serif", marginBottom: 14 }}>{name} — Strengths & Limitations</div>
          <div style={{ marginBottom: 12 }}>
            {pros.map((p: string) => <div key={p} style={{ fontSize: "0.76rem", color: "#01A982", marginBottom: 4 }}>✓ {p}</div>)}
          </div>
          <div>
            {cons.map((c: string) => <div key={c} style={{ fontSize: "0.76rem", color: "#FF375F", marginBottom: 4 }}>⚠ {c}</div>)}
          </div>
        </>
      )}
    </motion.div>
  );
}

// ── Main Landing Page ─────────────────────────────────────────────────────────
export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start start", "end end"] });
  const { user } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0]);
  const heroY = useTransform(scrollYProgress, [0, 0.15], [0, -50]);

  const advantages = [
    { icon: Zap, title: "Instant Analysis", desc: "Get a scored, traceable architecture recommendation in under 3 seconds. No waiting, no manual evaluation.", detail: "Parallel signal extraction and SHA-256 caching means re-uploading the same document skips the LLM entirely.", color: "#01A982" },
    { icon: Shield, title: "Anti-Hallucination Engine", desc: "Every signal extracted from your document is verified against the actual source text using fuzzy matching.", detail: "Unverified claims get confidence penalty. Signals below 0.1 confidence are discarded before scoring.", color: "#0A84FF" },
    { icon: TrendingUp, title: "Stability Analysis", desc: "Know how confident to be. Sensitivity testing perturbs every signal and shows which inputs change your result.", detail: "If changing 'data_volatility' from high to moderate flips the winner, you'll know exactly that.", color: "#7F35B2" },
    { icon: BarChart2, title: "4 Architecture Scores", desc: "RAG, Fine-Tuning, CAG, and Hybrid scored simultaneously with weighted signal analysis across 10 dimensions.", detail: "Weights: data_volatility (1.35×), accuracy_requirement (1.20×), latency_requirement (1.15×), and 7 more.", color: "#FF8300" },
    { icon: MessageSquare, title: "Smart AI Chat", desc: "Ask follow-up questions. The assistant browses Wikipedia, arXiv, and official docs for up-to-date answers.", detail: "Web-browsed answers are clearly labelled. Context from your analysis is injected into every response.", color: "#01A982" },
    { icon: FileText, title: "Document Upload", desc: "Upload any requirements PDF or TXT. Section detection, parallel chunk extraction, and confidence scoring are automatic.", detail: "Supports: multi-section docs, technical specs, RFPs, system architecture documents.", color: "#0A84FF" },
    { icon: Target, title: "Cost Breakdown", desc: "See monthly cost estimates for all 4 architectures, driven by your actual dataset size and query volume signals.", detail: "Compute + storage + API inference + networking + training costs — all signal-adjusted.", color: "#7F35B2" },
    { icon: RefreshCw, title: "Follow-up Questions", desc: "When a document lacks enough signals, context-aware follow-up questions are generated from what was found.", detail: "Questions reference actual quotes from your document — not generic prompts.", color: "#FF8300" },
    { icon: Lock, title: "Data Privacy", desc: "Documents are processed in memory and deleted immediately after analysis. Nothing is stored server-side.", detail: "Analysis results are stored per-user session. Export as JSON anytime. No third-party data sharing.", color: "#01A982" },
    { icon: Globe, title: "Deployment Ready", desc: "SQLite persistence means zero-config startup. Add PostgreSQL later when you need production scale.", detail: "Docker + docker-compose for one-command deployment. Ollama for free local LLM. OpenAI optional.", color: "#0A84FF" },
    { icon: Code2, title: "Full Traceability", desc: "Every signal comes with source text, page number, and confidence score — every decision step is logged.", detail: "The decision trace shows the complete pipeline: upload → parse → extract → validate → score → recommend.", color: "#7F35B2" },
    { icon: Lightbulb, title: "Hybrid Analysis", desc: "When scores are close, see which features suit which architecture for a custom hybrid split.", detail: "RAG+FT, RAG+CAG, and FT+CAG combos are scored separately with per-feature assignments.", color: "#FF8300" },
  ];

  const steps = [
    {
      step: "01", icon: FileText, color: "#01A982",
      title: "Describe Your System Requirements",
      desc: "Upload a requirements document (PDF or TXT) for fully automatic analysis, or step through our guided 10-question form covering all key architecture decision factors.",
      detail: "Document types supported: Technical specs, system architecture docs, RFPs, product briefs, use-case documents. Questions cover: dataset size, update frequency, latency needs, accuracy requirements, domain specificity, security level, cost sensitivity, deployment preference, query volume, and user scale.",
    },
    {
      step: "02", icon: Fingerprint, color: "#0A84FF",
      title: "AI Extracts & Validates Signals",
      desc: "Our multi-stage extraction pipeline reads your document section by section, identifies key architecture signals, assigns confidence scores, and verifies every claim against the source text.",
      detail: "Anti-hallucination: LLM is instructed to never hallucinate. Every signal source quote is fuzzy-matched against the document. Confidence below 10% → signal discarded. Result: only high-quality, traceable signals reach the scoring stage.",
    },
    {
      step: "03", icon: BarChart2, color: "#7F35B2",
      title: "Deterministic Weighted Scoring",
      desc: "A calibrated scoring engine evaluates all 4 architectures across your signals using weighted rules — no LLM guessing. Contradiction detection catches impossible signal combinations.",
      detail: "10 signals × 4 architectures × signal weights. Signal weights are calibrated against real enterprise deployments. 5 contradiction rules detect conflicts (e.g. ultra-low latency + very large dataset). Stability analysis then perturbs every signal to test how decisive the recommendation is.",
    },
    {
      step: "04", icon: Award, color: "#FF8300",
      title: "Actionable Recommendation + Full Report",
      desc: "Receive a ranked recommendation with confidence scores, stability verdict, cost analysis, risk matrix, implementation tips, and a full decision trace — everything you need to make the call.",
      detail: "Output includes: architecture scores (%), suitability rating, why-not explanations for runner-ups, cost breakdown (monthly/annual), top 3 risk dimensions, 4 implementation steps, hybrid split if scores are close, and a complete step-by-step decision pipeline log.",
    },
  ];

  const architectures = [
    { name: "RAG", short: "Retrieval-Augmented Generation", icon: "🔍", color: "#01A982",
      desc: "Grounds every AI response in live documents retrieved from a vector database. Updates instantly — re-index changed documents, no retraining needed.",
      pros: ["Retrain-free knowledge updates", "Full source citations on every response", "Scales to millions of documents"],
      cons: ["Retrieval adds 200ms–2s latency", "Requires vector DB infrastructure", "Quality bounded by retrieval accuracy"] },
    { name: "Fine-Tuning", short: "Domain-specific model training", icon: "🧠", color: "#7F35B2",
      desc: "Trains a foundation model on your domain dataset, embedding deep specialisation directly into weights. Achieves the lowest inference latency.",
      pros: ["Lowest inference latency (<100ms)", "Learns domain vocabulary & style", "Works offline without external calls"],
      cons: ["Expensive retraining on data change", "High hallucination risk without grounding", "Hard to audit decisions"] },
    { name: "CAG", short: "Context-Augmented Generation", icon: "⚡", color: "#FF8300",
      desc: "Loads your entire knowledge base into the model's context window. Zero vector database infrastructure — simplest possible architecture.",
      pros: ["Zero infrastructure complexity", "Near-instant responses from KV cache", "Perfect for small static knowledge bases"],
      cons: ["Hard context window ceiling", "High per-query token cost at scale", "Stale responses without cache refresh"] },
    { name: "Hybrid", short: "RAG + Fine-Tuning combined", icon: "🔗", color: "#0A84FF",
      desc: "Combines domain expertise from fine-tuning with live document grounding from RAG. Maximum accuracy and freshness for mission-critical systems.",
      pros: ["Best of both worlds", "Handles edge cases neither approach alone can", "Maximum reliability at enterprise scale"],
      cons: ["Highest engineering complexity", "Dual infrastructure cost", "Months longer time-to-production"] },
  ];

  const faqs = [
    { q: "What architectures does this tool evaluate?", a: "We evaluate four AI architectures in depth: RAG (Retrieval-Augmented Generation), Fine-Tuning, CAG (Context-Augmented Generation), and Hybrid (RAG + Fine-Tuning combined). Each is scored across 10 signal dimensions including data volatility, latency requirements, dataset size, accuracy needs, domain specificity, cost sensitivity, security level, query volume, user scale, and deployment preference. Scores are weighted and confidence-adjusted." },
    { q: "Do I need a document to upload? Can I just answer questions?", a: "Both paths work and produce the same quality recommendation. Upload a PDF/TXT for fully automatic signal extraction — our pipeline detects document sections, runs parallel chunk analysis, verifies claims against the source, and scores architectures. Or use the guided 10-question form to manually specify each signal with a single answer. The questionnaire path is recommended when your requirements aren't written down yet." },
    { q: "How does the AI chat work? Can it answer questions beyond the templates?", a: "Yes — the chat assistant is dynamic, not template-based. When you ask a question, it detects the topic, browses relevant web sources (Wikipedia, arXiv, official documentation) in real time using an async HTTP fetcher, then combines that content with your specific analysis results to synthesise a precise answer. If the LLM or web browsing fails, it falls back to a rich local knowledge base. All web-browsed answers are clearly labelled with a 'Web browsed' badge." },
    { q: "How accurate are the recommendations?", a: "The scoring engine is fully deterministic — it uses calibrated weights validated against real enterprise AI deployments. It never guesses. The stability analysis shows you exactly how confident to be: it perturbs every signal to every alternative value and reports if the recommendation changes. If the winner has a clear score gap (>15 points) and stability is confirmed, the recommendation is decisive. If scores are close, we recommend exploring a hybrid approach and show you which features suit which architecture." },
    { q: "Is my data private and secure?", a: "Your document content is processed entirely in memory and deleted immediately after analysis. We do not store document contents on our servers. Analysis results are saved to a local SQLite database associated with your user account — only you can access them. You can export your full analysis as JSON at any time. If you use guest mode (no account), data is session-only and lost on page refresh." },
    { q: "Do I need an OpenAI key or any paid service?", a: "No paid services are required. The backend fully supports Ollama — a free, local LLM runner. Install Ollama, pull the llama3.2 model (free), and the backend uses it automatically. The scoring engine itself is completely deterministic and requires no LLM at all for questionnaire-based analysis. LLM is only used for signal extraction from uploaded documents and for the AI chat. OpenAI is optional and only needed if you prefer GPT-4 quality extraction." },
    { q: "How does sign up / sign in work? Do I need Firebase?", a: "No Firebase required. The platform has a built-in email and password authentication system. Create an account with any email format (Gmail, Yahoo, college, work, or any valid address) and a strong password (min 8 characters with uppercase, number, and special character). Your account is stored securely in your browser. Google Sign-In via Firebase is also available optionally — add your Firebase credentials to enable it. Both paths give you full access to saved analyses and chat history." },
    { q: "Can I use the app without creating an account?", a: "Yes — click 'Skip for now' on any sign-in prompt. You get full access to all analysis features. The only limitation is that your analyses won't be saved across sessions (lost on page refresh). Creating a free account gives you persistent history, saved analyses, and the AI chat assistant with per-user memory." },
  ];

  return (
    <div className="w-full relative flex flex-col items-center overflow-x-hidden" ref={containerRef}>
      <div className="scan-line" />
      <div className="hex-grid" style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", opacity: 0.35 }} />
      {/* Ambient glow orbs */}
      <div style={{ position: "fixed", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle,rgba(1,169,130,0.07),transparent 70%)", top: "-8%", left: "-6%", zIndex: 0, pointerEvents: "none" }} />
      <div style={{ position: "fixed", width: 500, height: 500, borderRadius: "50%", background: "radial-gradient(circle,rgba(127,53,178,0.05),transparent 70%)", bottom: "5%", right: "-4%", zIndex: 0, pointerEvents: "none" }} />

      {/* ── HERO ─────────────────────────────────────────────── */}
      <motion.section style={{ opacity: heroOpacity, y: heroY }}
        className="min-h-screen flex flex-col items-center justify-center pt-24 pb-16 px-6 w-full max-w-6xl mx-auto text-center relative z-10">

        <motion.div initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 18px", borderRadius: 100, border: "1px solid var(--border)", background: "rgba(255,255,255,0.03)", backdropFilter: "blur(12px)", fontSize: "0.68rem", fontWeight: 700, letterSpacing: "2px", color: "var(--text-secondary)", marginBottom: 36, textTransform: "uppercase", fontFamily: "JetBrains Mono,monospace" }}>
            <Sparkles size={11} style={{ color: "var(--primary)" }} />
            AI Architecture Intelligence Platform
            <span style={{ background: "var(--primary)", color: "#fff", padding: "2px 9px", borderRadius: 100, fontSize: "0.6rem", letterSpacing: "1px" }}>v5.0</span>
          </div>
        </motion.div>

        <div style={{ marginBottom: 28, fontSize: "clamp(2.8rem,7.5vw,5.8rem)", fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.06, color: "var(--text-primary)" }}>
          <div style={{ overflow: "hidden", marginBottom: "-0.06em" }}>
            <motion.div variants={riseUp} initial="initial" animate="animate">Stop guessing.</motion.div>
          </div>
          <div style={{ overflow: "hidden" }}>
            <motion.div variants={riseUp} initial="initial" animate="animate"
              transition={{ ...riseUp.animate.transition, delay: 0.13 }}
              className="gradient-green">Start architecting.</motion.div>
          </div>
        </div>

        <AnimatedSection delay={0.85}>
          <p style={{ fontSize: "1.18rem", color: "var(--text-secondary)", maxWidth: 600, lineHeight: 1.8, fontWeight: 400, marginBottom: 44 }}>
            RAG, Fine-Tuning, CAG, or Hybrid? ArchGuide analyses your actual requirements
            through 10 signal dimensions and delivers a scored, fully traceable recommendation
            in under 3 seconds — no guesswork, no opinions.
          </p>
        </AnimatedSection>

        <AnimatedSection delay={1.05}>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            {user ? (
              <Magnetic>
                <Link href="/projects">
                  <button className="btn-primary" style={{ fontSize: "0.97rem", padding: "14px 34px" }}>
                    Open Projects <ArrowRight size={17} />
                  </button>
                </Link>
              </Magnetic>
            ) : (
              <>
                <Magnetic>
                  <button className="btn-primary" onClick={() => setAuthOpen(true)} style={{ fontSize: "0.97rem", padding: "14px 34px" }}>
                    Create Free Account <ArrowRight size={17} />
                  </button>
                </Magnetic>
                <Magnetic>
                  <Link href="/projects">
                    <button className="btn-ghost" style={{ fontSize: "0.97rem", padding: "14px 34px" }}>
                      Try Without Account
                    </button>
                  </Link>
                </Magnetic>
              </>
            )}
          </div>
        </AnimatedSection>

        <AnimatedSection delay={1.25}>
          <motion.div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginTop: 60, maxWidth: 640, width: "100%" }}
            initial="initial" whileInView="animate" viewport={{ once: true }} variants={{ animate: { transition: { staggerChildren: 0.1 } } }}>
            <StatCard value="10" label="Signal Dimensions" color="#01A982" icon="📡" />
            <StatCard value="4" label="Architectures Scored" color="#0A84FF" icon="🏗" />
            <StatCard value="<3s" label="Analysis Time" color="#7F35B2" icon="⚡" />
            <StatCard value="100%" label="Deterministic" color="#FF8300" icon="🎯" />
          </motion.div>
        </AnimatedSection>

        <motion.div animate={{ y: [0, 10, 0] }} transition={{ duration: 2.5, repeat: Infinity }} style={{ marginTop: 60, color: "var(--text-muted)" }}>
          <ChevronDown size={22} />
        </motion.div>
      </motion.section>

      {/* ── ABOUT ──────────────────────────────────────────────── */}
      <section id="about" style={{ width: "100%", padding: "110px 24px", maxWidth: 1140, margin: "0 auto", position: "relative", zIndex: 10 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 64, alignItems: "flex-start" }}>
          <motion.div initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.8 }}>
            <div className="chip chip-green" style={{ marginBottom: 20 }}>About ArchGuide</div>
            <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,3rem)", marginBottom: 22, letterSpacing: "-0.03em", lineHeight: 1.18 }}>
              Built for engineers who need answers, not opinions.
            </h2>
            <p style={{ color: "var(--text-secondary)", lineHeight: 1.85, fontSize: "0.93rem", marginBottom: 18 }}>
              Choosing the wrong AI architecture costs months of engineering time and hundreds of thousands of dollars. Most teams make this decision based on blog posts, hype, or a consultant's preference — not their actual requirements.
            </p>
            <p style={{ color: "var(--text-secondary)", lineHeight: 1.85, fontSize: "0.93rem", marginBottom: 18 }}>
              ArchGuide changes this. Upload your requirements document or answer 10 guided questions, and our signal extraction engine analyses 10 critical decision factors: data volatility, latency constraints, dataset scale, accuracy requirements, domain specificity, security needs, cost sensitivity, deployment preference, query volume, and user scale.
            </p>
            <p style={{ color: "var(--text-secondary)", lineHeight: 1.85, fontSize: "0.93rem", marginBottom: 28 }}>
              Every recommendation is fully traceable — you see exactly which signals drove the decision, what the system's confidence is, and precisely how the recommendation would change if your inputs were different. No black boxes. No guessing.
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {[["✓ Fully Deterministic", "#01A982"], ["✓ Source-Verified", "#0A84FF"], ["✓ No Vendor Lock-in", "#7F35B2"], ["✓ Works Offline", "#FF8300"]].map(([l, c]) => (
                <div key={l} className="chip" style={{ background: `${c}18`, color: c, border: `1px solid ${c}35`, fontSize: "0.72rem" }}>{l}</div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.8, delay: 0.1 }}>
            <div style={{ padding: 6, borderRadius: 22, border: "1px solid var(--border)", background: "var(--glass-bg)", backdropFilter: "blur(24px)" }}>
              {[
                { arch: "RAG", color: "#01A982", label: "Best for dynamic, large-scale knowledge bases", icon: "🔍" },
                { arch: "Fine-Tuning", color: "#7F35B2", label: "Best for static, highly specialised domains", icon: "🧠" },
                { arch: "CAG", color: "#FF8300", label: "Best for small, stable, bounded knowledge bases", icon: "⚡" },
                { arch: "Hybrid", color: "#0A84FF", label: "Best for enterprise-critical accuracy + freshness", icon: "🔗" },
              ].map(({ arch, color, label, icon }) => (
                <div key={arch} style={{ display: "flex", gap: 16, padding: "18px 20px", borderBottom: "1px solid var(--border)", alignItems: "center" }}>
                  <div style={{ width: 46, height: 46, borderRadius: 12, background: `${color}18`, border: `1px solid ${color}30`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.3rem", flexShrink: 0 }}>{icon}</div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: "0.92rem", color, marginBottom: 4, fontFamily: "Space Grotesk,sans-serif" }}>{arch}</div>
                    <div style={{ fontSize: "0.79rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{label}</div>
                  </div>
                </div>
              ))}
              <div style={{ padding: "16px 20px" }}>
                <div style={{ fontFamily: "JetBrains Mono,monospace", fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "1.5px", marginBottom: 10 }}>SIGNAL WEIGHTS</div>
                {[["data_volatility", "1.35×"], ["accuracy_requirement", "1.20×"], ["latency_requirement", "1.15×"], ["domain_specificity", "1.10×"]].map(([s, w]) => (
                  <div key={s} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "JetBrains Mono,monospace" }}>{s}</span>
                    <span style={{ fontSize: "0.75rem", color: "var(--primary)", fontWeight: 700, fontFamily: "JetBrains Mono,monospace" }}>{w}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── ARCHITECTURE OVERVIEW ──────────────────────────────── */}
      <section style={{ width: "100%", padding: "100px 24px", background: "rgba(1,169,130,0.025)", borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)", position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="chip chip-blue" style={{ marginBottom: 18 }}>Architecture Guide</div>
            <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,3rem)", letterSpacing: "-0.03em", marginBottom: 16 }}>
              Four architectures. One decision.
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.93rem", maxWidth: 580, margin: "0 auto", lineHeight: 1.78 }}>
              Click any card to see strengths and limitations. ArchGuide scores all four against your requirements simultaneously.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))", gap: 16 }}>
            {architectures.map(a => <ArchCard key={a.name} {...a} />)}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ───────────────────────────────────────── */}
      <section id="how-it-works" style={{ width: "100%", padding: "110px 24px", maxWidth: 1000, margin: "0 auto", position: "relative", zIndex: 10 }}>
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <div className="chip chip-purple" style={{ marginBottom: 18 }}>How It Works</div>
          <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,3rem)", letterSpacing: "-0.03em", marginBottom: 16 }}>
            From requirements to recommendation in 4 steps.
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.93rem", maxWidth: 560, margin: "0 auto", lineHeight: 1.78 }}>
            Every step is transparent. You see exactly what was extracted, how it was scored, and why the recommendation was made.
          </p>
        </div>
        {steps.map((s, i) => <StepCard key={i} {...s} />)}
      </section>

      {/* ── ADVANTAGES ─────────────────────────────────────────── */}
      <section id="advantages" style={{ width: "100%", padding: "110px 24px", background: "rgba(0,0,0,0.15)", borderTop: "1px solid var(--border)", position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: 1140, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <div className="chip chip-orange" style={{ marginBottom: 18 }}>Why ArchGuide</div>
            <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,3rem)", letterSpacing: "-0.03em", marginBottom: 16 }}>
              Built differently. Works better.
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.93rem", maxWidth: 560, margin: "0 auto", lineHeight: 1.78 }}>
              Every feature is designed around one goal — giving you a recommendation you can actually trust, trace, and act on. Hover each card for technical details.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 18 }}>
            {advantages.map((a, i) => <FeatureCard key={i} {...a} />)}
          </div>
        </div>
      </section>

      {/* ── FAQ ────────────────────────────────────────────────── */}
      <section id="faq" style={{ width: "100%", padding: "110px 24px", position: "relative", zIndex: 10 }}>
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="chip chip-green" style={{ marginBottom: 18 }}>FAQ</div>
            <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,3rem)", letterSpacing: "-0.03em", marginBottom: 16 }}>
              Common questions answered.
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.93rem", maxWidth: 480, margin: "0 auto", lineHeight: 1.78 }}>
              Everything you need to know before getting started.
            </p>
          </div>
          {faqs.map((faq, i) => <FAQItem key={i} q={faq.q} a={faq.a} />)}
        </div>
      </section>

      {/* ── FINAL CTA ──────────────────────────────────────────── */}
      <section style={{ width: "100%", padding: "100px 24px 120px", position: "relative", zIndex: 10 }}>
        <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          style={{ maxWidth: 740, margin: "0 auto", textAlign: "center", padding: "68px 52px", borderRadius: 30, border: "1px solid var(--primary3)", background: "rgba(1,169,130,0.06)", backdropFilter: "blur(28px)", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: "linear-gradient(90deg, transparent, var(--primary), transparent)" }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 1, background: "linear-gradient(90deg, transparent, rgba(1,169,130,0.4), transparent)" }} />
          <div style={{ fontSize: "3.5rem", marginBottom: 20 }}>🚀</div>
          <h2 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 900, fontSize: "clamp(1.9rem,4vw,2.9rem)", letterSpacing: "-0.03em", marginBottom: 20 }}>
            Ready to make the right choice?
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.97rem", lineHeight: 1.82, marginBottom: 38, maxWidth: 520, margin: "0 auto 38px" }}>
            Join teams using ArchGuide to make confident, traceable AI architecture decisions. Free to use. No credit card. No vendor lock-in.
          </p>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            {user ? (
              <Link href="/projects">
                <button className="btn-primary" style={{ fontSize: "1rem", padding: "15px 38px" }}>Open Projects <ArrowRight size={18} /></button>
              </Link>
            ) : (
              <>
                <button className="btn-primary" onClick={() => setAuthOpen(true)} style={{ fontSize: "1rem", padding: "15px 38px" }}>
                  Create Free Account <ArrowRight size={18} />
                </button>
                <Link href="/projects">
                  <button className="btn-ghost" style={{ fontSize: "1rem", padding: "15px 38px" }}>Try Without Account</button>
                </Link>
              </>
            )}
          </div>
        </motion.div>
      </section>

      <AuthModal isOpen={authOpen} onClose={() => setAuthOpen(false)}
        onAuthSuccess={() => setAuthOpen(false)} onSkip={() => setAuthOpen(false)} />
    </div>
  );
}
