"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { m, AnimatePresence } from "framer-motion";
import { MessageCircle, X, Send, Bot, User, Loader2, Sparkles, ArrowRight, Plus, Trash2 } from "lucide-react";
import { streamChatMessage, ChatMessageItem, AnalysisResult } from "@/lib/api";

interface Props {
  analysisId: string;
  result: AnalysisResult;
}

const ARCH_DISPLAY: Record<string, string> = {
  RAG: "RAG",
  FineTuning: "Fine-Tuning",
  CAG: "CAG",
  Hybrid: "Hybrid",
};

const C = {
  panel:        "#111113",
  panelBorder:  "rgba(255,255,255,0.10)",
  headerBorder: "rgba(255,255,255,0.08)",
  avatarBot:    "rgba(255,255,255,0.10)",
  avatarUser:   "rgba(255,255,255,0.12)",
  bubbleBot:    "rgba(255,255,255,0.07)",
  bubbleUser:   "#ffffff",
  bubbleUserTx: "#111113",
  textPrimary:  "#f0f0f0",
  textSecond:   "rgba(255,255,255,0.45)",
  inputBg:      "rgba(255,255,255,0.06)",
  inputBorder:  "rgba(255,255,255,0.12)",
  pillBg:       "rgba(255,255,255,0.08)",
  pillBorder:   "rgba(255,255,255,0.14)",
  accent:       "#6366f1",
  dot:          "rgba(255,255,255,0.35)",
  sectionLabel: "rgba(255,255,255,0.30)",
};

// ── Signal value helpers ──────────────────────────────────────────────────────

function sigVal(result: AnalysisResult, key: string): string | null {
  return result.signals?.[key]?.value ?? null;
}

function archScore(result: AnalysisResult, arch: string): number {
  return Math.round(result.scores?.[arch] ?? 0);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(val: string | null): string {
  if (!val) return "";
  return val.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// ── Dynamic follow-up question generator ─────────────────────────────────────
// Questions are generated from the actual extracted signals so they reference
// concrete project facts (e.g. "your strict latency requirement").

function buildFollowUps(lastUserMsg: string, result: AnalysisResult): string[][] {
  const m = lastUserMsg.toLowerCase();
  const rec   = result.recommended ?? "";
  const arch  = ARCH_DISPLAY[rec] ?? rec;
  const ds    = fmt(sigVal(result, "dataset_size"));
  const lat   = fmt(sigVal(result, "latency_requirement"));
  const vol   = fmt(sigVal(result, "data_volatility"));
  const acc   = fmt(sigVal(result, "accuracy_requirement"));
  const dom   = fmt(sigVal(result, "domain_specificity"));
  const sec   = fmt(sigVal(result, "security_level"));
  const cost  = fmt(sigVal(result, "cost_sensitivity"));
  const dep   = fmt(sigVal(result, "deployment_preference"));
  const scale = fmt(sigVal(result, "user_scale"));
  const qv    = fmt(sigVal(result, "query_volume"));
  const conf  = result.confidence ? `${Math.round(result.confidence * 100)}%` : null;

  // ── Why / recommendation ──────────────────────────────────────────────────
  if (m.includes("why") || m.includes("recommend") || m.includes("chose") || m.includes("decision")) {
    return [[
      ds   ? `How does the ${ds} dataset size influence the choice?` : "How does dataset size factor in?",
      lat  ? `Why does a ${lat} latency need point to ${arch}?`      : "How does the latency requirement affect the decision?",
      acc  ? `What role does ${acc} accuracy requirement play?`       : "How does accuracy affect the recommendation?",
      conf ? `The confidence is ${conf} - what would raise it?`       : "What would make this recommendation more confident?",
    ], [
      "Which signals had the biggest impact on the score?",
      "What combination of factors makes this the best fit?",
      dom ? `How does ${dom} domain specificity affect ${arch}?` : "How does domain specificity affect the choice?",
    ]];
  }

  // ── Cost / budget ─────────────────────────────────────────────────────────
  if (m.includes("cost") || m.includes("price") || m.includes("budget") || m.includes("expensive") || m.includes("cheap")) {
    return [[
      "What are the biggest cost drivers for this architecture?",
      "How does the setup cost compare to monthly running cost?",
      cost ? `How does ${cost} cost sensitivity shape the tradeoffs?` : "How does cost sensitivity affect the recommendation?",
    ], [
      "Which alternative architecture is cheapest to run?",
      "Are there ways to reduce cost without switching architectures?",
      scale ? `How does ${scale} user scale affect total cost?` : "How does user scale affect the total cost?",
    ]];
  }

  // ── Tradeoffs / risks / weaknesses ───────────────────────────────────────
  if (m.includes("tradeoff") || m.includes("weakness") || m.includes("downside") || m.includes("risk") || m.includes("con") || m.includes("disadvantage")) {
    return [[
      `What is ${arch}'s biggest weakness for this use case?`,
      "What could go wrong in production with this approach?",
      "What are the hardest engineering challenges to solve?",
    ], [
      "How can the main risks be mitigated?",
      vol ? `How does ${vol} data volatility create risk?` : "How does data volatility create risk?",
      "When would this architecture start to break down?",
    ]];
  }

  // ── Alternatives ──────────────────────────────────────────────────────────
  if (m.includes("alternative") || m.includes("instead") || m.includes("other arch") || m.includes("rag") || m.includes("fine") || m.includes("cag") || m.includes("hybrid")) {
    const others = ["RAG","FineTuning","CAG","Hybrid"].filter(a => a !== rec);
    return [[
      `Why did ${others[0]} score ${archScore(result, others[0])} vs ${arch}'s ${archScore(result, rec)}?`,
      `What would need to change to make ${others[1]} a better fit?`,
      "Could a Hybrid approach combine the best of both?",
    ], [
      `What does ${arch} do that no other option can match here?`,
      "Is there a migration path if requirements change?",
      "What's the switching cost if we change architectures later?",
    ]];
  }

  // ── Performance / latency ────────────────────────────────────────────────
  if (m.includes("latency") || m.includes("performance") || m.includes("speed") || m.includes("fast") || m.includes("slow") || m.includes("response time")) {
    return [[
      lat ? `What does ${lat} latency mean for real users?`           : "What latency can users expect?",
      qv  ? `How does ${qv} query volume affect response times?`      : "How does query volume affect response times?",
      "What are the main performance bottlenecks to watch?",
    ], [
      "How can we optimize latency further?",
      "What caching strategies work well with this architecture?",
      "How does performance scale as data grows?",
    ]];
  }

  // ── Scaling ───────────────────────────────────────────────────────────────
  if (m.includes("scale") || m.includes("traffic") || m.includes("load") || m.includes("grow") || m.includes("concurrent")) {
    return [[
      scale ? `What happens when ${scale} user scale doubles?`       : "How does this architecture scale?",
      qv    ? `What's the ceiling for ${qv} query volume?`           : "What query volume can this handle?",
      "What infrastructure changes are needed to scale?",
    ], [
      "At what point should we re-evaluate the architecture?",
      "How does horizontal vs vertical scaling apply here?",
      "What are the scaling bottlenecks to plan for?",
    ]];
  }

  // ── Security / compliance ─────────────────────────────────────────────────
  if (m.includes("security") || m.includes("compliance") || m.includes("privacy") || m.includes("hipaa") || m.includes("gdpr") || m.includes("pci") || m.includes("safe")) {
    return [[
      sec ? `What does ${sec} security level require in practice?`   : "What security measures are needed?",
      dep ? `How does ${dep} deployment affect data privacy?`        : "How does deployment choice affect privacy?",
      "What compliance certifications are relevant here?",
    ], [
      "How is sensitive data handled at rest and in transit?",
      "What are the audit and logging requirements?",
      "How does access control work with this architecture?",
    ]];
  }

  // ── Deployment / infrastructure ───────────────────────────────────────────
  if (m.includes("deploy") || m.includes("infra") || m.includes("setup") || m.includes("cloud") || m.includes("on-prem") || m.includes("implement")) {
    return [[
      dep ? `What does ${dep} deployment look like in practice?`     : "What does the deployment look like?",
      "What are the key infrastructure dependencies?",
      "How long does a typical implementation take?",
    ], [
      "What team skills and size are needed?",
      "What are the main DevOps/MLOps requirements?",
      sec ? `How does ${sec} security affect the infra choices?`     : "How do security requirements shape the infrastructure?",
    ]];
  }

  // ── Data / knowledge base ────────────────────────────────────────────────
  if (m.includes("data") || m.includes("dataset") || m.includes("corpus") || m.includes("knowledge") || m.includes("document")) {
    return [[
      ds  ? `What are the best practices for managing a ${ds} dataset?` : "How should the dataset be managed?",
      vol ? `With ${vol} data volatility, how often should we update?`   : "How often should data be updated?",
      "How does data quality affect answer quality?",
    ], [
      "What chunking or indexing strategy is recommended?",
      "How do we handle conflicting or outdated information?",
      acc ? `How does ${acc} accuracy need tie to data curation?`    : "How does accuracy need tie to data curation?",
    ]];
  }

  // ── Accuracy / quality ────────────────────────────────────────────────────
  if (m.includes("accuracy") || m.includes("quality") || m.includes("hallucination") || m.includes("reliable") || m.includes("correct") || m.includes("precise")) {
    return [[
      acc ? `How does ${arch} achieve ${acc} accuracy?`              : `How does ${arch} ensure accuracy?`,
      "What are the main sources of errors or hallucinations?",
      "How do you measure and monitor output quality?",
    ], [
      "What evaluation metrics matter most for this use case?",
      "How do you handle edge cases or out-of-scope queries?",
      "What human-in-the-loop checks are recommended?",
    ]];
  }

  // ── Maintenance / operations ──────────────────────────────────────────────
  if (m.includes("maintain") || m.includes("operat") || m.includes("monitor") || m.includes("updat") || m.includes("ongoing")) {
    return [[
      "What does ongoing maintenance look like day-to-day?",
      vol ? `With ${vol} data volatility, what's the update cadence?` : "How often does the system need to be updated?",
      "What monitoring and alerting should be set up?",
    ], [
      "What are the most common failure modes to watch for?",
      "How do you handle model drift over time?",
      "What's the rollback strategy if something breaks?",
    ]];
  }

  // ── Integration ───────────────────────────────────────────────────────────
  if (m.includes("integrat") || m.includes("api") || m.includes("connect") || m.includes("existing") || m.includes("system")) {
    return [[
      "How does this integrate with existing systems?",
      "What APIs or interfaces are exposed to applications?",
      "What's the typical latency for an API call end-to-end?",
    ], [
      "How do you version and manage the API over time?",
      "What authentication and rate-limiting patterns work best?",
      dep ? `How does ${dep} deployment affect integration options?` : "How does deployment affect integration?",
    ]];
  }

  // ── ROI / business value ──────────────────────────────────────────────────
  if (m.includes("roi") || m.includes("return") || m.includes("value") || m.includes("business") || m.includes("benefit")) {
    return [[
      `What's the core business value ${arch} delivers here?`,
      "How quickly can you expect to see measurable results?",
      "What KPIs should be tracked to measure success?",
    ], [
      "How does this compare to a manual/non-AI approach in ROI?",
      "What's the break-even point for the investment?",
      cost ? `How does ${cost} cost sensitivity affect the ROI story?` : "How does cost sensitivity affect the ROI story?",
    ]];
  }

  // ── Strengths ────────────────────────────────────────────────────────────
  if (m.includes("strength") || m.includes("advantage") || m.includes("best") || m.includes("good") || m.includes("pro ") || m.includes("benefit")) {
    return [[
      `What is ${arch}'s single biggest strength for this project?`,
      ds  ? `Why is ${arch} the right fit for a ${ds} dataset?`      : `Why is ${arch} a strong fit here?`,
      "What problems does this architecture solve better than any other?",
    ], [
      "How does this architecture handle the hardest requirements?",
      acc ? `How does ${arch} specifically achieve ${acc} accuracy?` : "How does it achieve high accuracy?",
      "What makes this architecture easy or hard to operate?",
    ]];
  }

  // ── Default / generic ────────────────────────────────────────────────────
  return [[
    `What makes ${arch} uniquely suited to this project?`,
    ds  ? `How does the ${ds} dataset size shape the solution?`      : "How does the dataset size shape the solution?",
    lat ? `What does ${lat} latency mean for the user experience?`   : "What latency can end-users expect?",
  ], [
    cost ? `How does ${cost} cost sensitivity affect architecture choices?` : "How does cost sensitivity affect the choices?",
    sec  ? `What does ${sec} security require in this setup?`              : "What security measures are built in?",
    vol  ? `With ${vol} data volatility, how fresh will answers be?`       : "How fresh and up-to-date will answers be?",
  ]];
}

// ── Initial suggestions — project-aware, kept short so pills wrap in 2 rows ──

function buildInitialSuggestions(result: AnalysisResult): string[] {
  const rec  = result.recommended ?? "";
  const arch = ARCH_DISPLAY[rec] ?? rec;
  const conf = result.confidence ? `${Math.round(result.confidence * 100)}%` : null;
  const ds   = sigVal(result, "dataset_size");
  const acc  = sigVal(result, "accuracy_requirement");

  return [
    conf ? `Why ${arch} with ${conf} confidence?`    : `Why was ${arch} recommended?`,
    ds   ? `Impact of ${fmt(ds)} dataset size?`      : "What drove this recommendation?",
    acc  ? `How is ${fmt(acc)} accuracy achieved?`   : "How accurate will the system be?",
    "What are the biggest risks?",
    "How does cost compare?",
    "What does deployment look like?",
  ];
}

// ─────────────────────────────────────────────────────────────────────────────

export function ArchGuideChat({ analysisId, result }: Props) {
  const [open, setOpen]             = useState(false);
  const [messages, setMessages]     = useState<ChatMessageItem[]>([]);
  const [streamingText, setStreaming] = useState("");   // in-flight token buffer
  const [followUps, setFollowUps]   = useState<string[][]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [showPulse, setShowPulse]   = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const bottomRef        = useRef<HTMLDivElement>(null);
  const inputRef         = useRef<HTMLTextAreaElement>(null);
  const scrollRef        = useRef<HTMLDivElement>(null);
  const lastBotMsgRef    = useRef<HTMLDivElement>(null);
  const streamBubbleRef  = useRef<HTMLDivElement>(null);
  const scrolledToStream = useRef(false);  // fire scroll-to-answer only once per turn

  const archName = ARCH_DISPLAY[result.recommended ?? ""] ?? (result.recommended ?? "");
  const initSuggestions = buildInitialSuggestions(result);

  useEffect(() => {
    const t = setTimeout(() => setShowPulse(true), 2000);
    return () => clearTimeout(t);
  }, []);

  // Scroll to bottom when user sends — shows typing dots
  useEffect(() => {
    const el = scrollRef.current;
    if (el && loading && messages[messages.length - 1]?.role === "user") {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to the answer bubble on first streaming token — once per turn only
  useEffect(() => {
    if (!streamingText) { scrolledToStream.current = false; return; }
    if (scrolledToStream.current) return;
    scrolledToStream.current = true;
    const el = scrollRef.current;
    const bubble = streamBubbleRef.current;
    if (!el || !bubble) return;
    // getBoundingClientRect gives position relative to viewport — subtract container top
    const containerTop = el.getBoundingClientRect().top;
    const bubbleTop    = bubble.getBoundingClientRect().top;
    el.scrollTop = el.scrollTop + (bubbleTop - containerTop) - 12;
  }, [streamingText]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 300);
  }, [open]);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setFollowUps([]);
    setStreaming("");
    const userMsg: ChatMessageItem = { role: "user", content: trimmed };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    let accumulated = "";
    try {
      await streamChatMessage(
        analysisId,
        trimmed,
        messages,
        (token) => {
          accumulated += token;
          setStreaming(accumulated);
        },
      );
      // Final cleanup on the full text (catches any remaining markdown the per-token pass missed)
      const cleaned = accumulated.replace(/\*+/g, "").replace(/#{1,6}\s*/g, "").replace(/\n{3,}/g, "\n\n").trim();
      setMessages(prev => [...prev, { role: "assistant", content: cleaned }]);
      setStreaming("");
      setFollowUps(buildFollowUps(trimmed, result));
    } catch (err: any) {
      setStreaming("");
      console.error("[Chat] Stream failed:", err);
      setError("Unable to process your message right now.");
    } finally {
      setLoading(false);
    }
  }, [analysisId, loading, messages, result]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setStreaming("");
    setFollowUps([]);
    setInput("");
    setError(null);
    setConfirmClear(false);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <>
      {/* Floating trigger button */}
      <m.button
        onClick={() => { setOpen(prev => !prev); setShowPulse(false); }}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center shadow-2xl"
        style={{ background: C.accent, color: "#fff" }}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.93 }}
        aria-label="Open ArchGuide Chat"
      >
        {showPulse && !open && (
          <span className="absolute inset-0 rounded-full animate-ping opacity-40"
            style={{ background: C.accent }} />
        )}
        <MessageCircle size={22} />
        {messages.filter(m => m.role === "assistant").length > 0 && !open && (
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 text-white text-[9px] font-bold flex items-center justify-center">
            {messages.filter(m => m.role === "assistant").length}
          </span>
        )}
      </m.button>

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <m.div
            key="chat-panel"
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ type: "spring", damping: 26, stiffness: 360 }}
            className="fixed bottom-24 right-4 sm:right-6 z-50 w-[calc(100vw-2rem)] max-w-[410px] flex flex-col rounded-2xl shadow-[0_24px_64px_rgba(0,0,0,0.6)]"
            style={{ background: C.panel, border: `1px solid ${C.panelBorder}`, overflow: "hidden" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 shrink-0"
              style={{ borderBottom: `1px solid ${C.headerBorder}` }}>
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                  style={{ background: `${C.accent}25` }}>
                  <Sparkles size={14} style={{ color: C.accent }} />
                </div>
                <div>
                  <p className="text-sm font-bold leading-tight" style={{ color: C.textPrimary }}>
                    ArchGuide AI
                  </p>
                  <p className="text-[11px]" style={{ color: C.textSecond }}>
                    Ask anything about your <span style={{ color: C.accent }}>{archName}</span> recommendation
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* New Chat — immediate fresh start */}
                <button
                  onClick={clearChat}
                  title="New chat"
                  className="w-7 h-7 rounded-lg flex items-center justify-center transition-opacity hover:opacity-60"
                  style={{ color: C.textSecond }}
                  aria-label="New chat"
                >
                  <Plus size={15} />
                </button>

                {/* Clear History — confirmation required */}
                {hasMessages && !confirmClear && (
                  <button
                    onClick={() => setConfirmClear(true)}
                    title="Clear history"
                    className="w-7 h-7 rounded-lg flex items-center justify-center transition-opacity hover:opacity-60"
                    style={{ color: C.textSecond }}
                    aria-label="Clear history"
                  >
                    <Trash2 size={14} />
                  </button>
                )}

                {/* Inline confirm prompt */}
                {confirmClear && (
                  <div className="flex items-center gap-1 text-[11px]" style={{ color: C.textSecond }}>
                    <span>Clear?</span>
                    <button
                      onClick={clearChat}
                      className="px-2 py-0.5 rounded-md font-semibold transition-opacity hover:opacity-80"
                      style={{ background: "rgba(239,68,68,0.18)", color: "rgb(248,113,113)", border: "1px solid rgba(239,68,68,0.30)" }}
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setConfirmClear(false)}
                      className="px-2 py-0.5 rounded-md font-semibold transition-opacity hover:opacity-80"
                      style={{ background: C.pillBg, color: C.textPrimary, border: `1px solid ${C.pillBorder}` }}
                    >
                      No
                    </button>
                  </div>
                )}

                <button onClick={() => setOpen(false)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center transition-opacity hover:opacity-60"
                  style={{ color: C.textSecond }} aria-label="Close chat">
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div
              ref={scrollRef}
              className="archguide-messages px-4 py-4 flex flex-col gap-3"
              style={{
                height: hasMessages ? "320px" : "100px",
                overflowY: hasMessages ? "scroll" : "hidden",
                overflowX: "hidden",
                overscrollBehavior: "contain",
                transition: "height 0.3s ease",
              }}
              onWheel={(e) => e.stopPropagation()}
              onTouchMove={(e) => e.stopPropagation()}
            >
              {/* Welcome */}
              <m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-2.5">
                <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                  style={{ background: C.avatarBot }}>
                  <Bot size={13} style={{ color: C.accent }} />
                </div>
                <div className="rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm leading-relaxed"
                  style={{ background: C.bubbleBot, color: C.textPrimary, maxWidth: "88%", border: `1px solid ${C.panelBorder}` }}>
                  I have your full analysis. Ask me anything about your{" "}
                  <span style={{ color: C.accent, fontWeight: 600 }}>{archName}</span>{" "}
                  recommendation.
                </div>
              </m.div>

              {/* Message list */}
              {messages.map((msg, i) => {
                const isUser = msg.role === "user";
                const isLastBot = !isUser && i === messages.length - 1;
                return (
                  <React.Fragment key={i}>
                    <m.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.16 }}
                      className={`flex gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}
                    >
                      <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                        style={{ background: isUser ? C.avatarUser : C.avatarBot }}>
                        {isUser
                          ? <User size={12} style={{ color: C.textPrimary }} />
                          : <Bot  size={12} style={{ color: C.accent }} />
                        }
                      </div>

                      {/* User bubble — plain white */}
                      {isUser && (
                        <div className="text-sm leading-relaxed whitespace-pre-wrap px-3.5 py-2.5"
                          style={{
                            maxWidth: "84%",
                            background: C.bubbleUser,
                            color: C.bubbleUserTx,
                            borderRadius: "16px 16px 4px 16px",
                          }}>
                          {msg.content}
                        </div>
                      )}

                      {/* Bot answer — accent left border + label */}
                      {!isUser && (
                        <div ref={isLastBot ? lastBotMsgRef : undefined}
                          style={{ maxWidth: "84%", display: "flex", flexDirection: "column", gap: "4px" }}>
                          <span className="text-[10px] font-bold uppercase tracking-widest"
                            style={{ color: C.accent, paddingLeft: "2px" }}>
                            Answer
                          </span>
                          <div className="text-sm leading-relaxed whitespace-pre-wrap px-3.5 py-2.5"
                            style={{
                              background: C.bubbleBot,
                              color: C.textPrimary,
                              borderRadius: "4px 16px 16px 16px",
                              border: `1px solid ${C.panelBorder}`,
                              borderLeft: `3px solid ${C.accent}`,
                            }}>
                            {msg.content}
                          </div>
                        </div>
                      )}
                    </m.div>

                    {/* Follow-up questions — clearly separated section */}
                    {isLastBot && !loading && followUps.length > 0 && (
                      <m.div
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.15, duration: 0.2 }}
                        className="flex flex-col gap-2.5 ml-9 mt-1"
                        style={{
                          padding: "10px 12px",
                          borderRadius: "12px",
                          background: "rgba(99,102,241,0.06)",
                          border: "1px solid rgba(99,102,241,0.18)",
                        }}
                      >
                        {/* Section header */}
                        <div className="flex items-center gap-1.5">
                          <div className="h-px flex-1" style={{ background: "rgba(99,102,241,0.25)" }} />
                          <span className="text-[10px] font-bold uppercase tracking-widest"
                            style={{ color: C.accent }}>
                            Follow-up questions
                          </span>
                          <div className="h-px flex-1" style={{ background: "rgba(99,102,241,0.25)" }} />
                        </div>

                        {/* Pills */}
                        {followUps.map((group, gi) => (
                          <div key={gi} className="flex flex-col gap-1.5">
                            {gi > 0 && (
                              <p className="text-[9px] font-semibold uppercase tracking-widest mt-0.5"
                                style={{ color: C.sectionLabel }}>
                                {gi === 1 ? "Also explore" : "Dig deeper"}
                              </p>
                            )}
                            <div className="flex flex-wrap gap-1.5">
                              {group.map(q => (
                                <button key={q} onClick={() => send(q)} disabled={loading}
                                  className="flex items-center gap-1 text-[11px] px-2.5 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-40 text-left"
                                  style={{
                                    background: "rgba(99,102,241,0.10)",
                                    color: "#a5b4fc",
                                    border: "1px solid rgba(99,102,241,0.28)",
                                  }}
                                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(99,102,241,0.20)")}
                                  onMouseLeave={e => (e.currentTarget.style.background = "rgba(99,102,241,0.10)")}
                                >
                                  <ArrowRight size={10} style={{ flexShrink: 0, opacity: 0.7 }} />
                                  {q}
                                </button>
                              ))}
                            </div>
                          </div>
                        ))}
                      </m.div>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Streaming answer — only while generating, never alongside a completed bubble */}
              {loading && messages[messages.length - 1]?.role === "user" && (
                <m.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-2.5">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                    style={{ background: C.avatarBot }}>
                    <Bot size={12} style={{ color: C.accent }} />
                  </div>
                  {streamingText ? (
                    <div ref={streamBubbleRef} style={{ maxWidth: "84%", display: "flex", flexDirection: "column", gap: "4px" }}>
                      <span className="text-[10px] font-bold uppercase tracking-widest"
                        style={{ color: C.accent, paddingLeft: "2px" }}>Answer</span>
                      <div className="text-sm leading-relaxed whitespace-pre-wrap px-3.5 py-2.5"
                        style={{
                          background: C.bubbleBot,
                          color: C.textPrimary,
                          borderRadius: "4px 16px 16px 16px",
                          border: `1px solid ${C.panelBorder}`,
                          borderLeft: `3px solid ${C.accent}`,
                        }}>
                        {streamingText}
                        <span className="inline-block w-0.5 h-3.5 ml-0.5 align-middle animate-pulse rounded-sm"
                          style={{ background: C.accent }} />
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-2xl rounded-tl-sm px-3.5 py-3 flex items-center gap-1.5"
                      style={{ background: C.bubbleBot, border: `1px solid ${C.panelBorder}` }}>
                      {[0, 1, 2].map(d => (
                        <span key={d} className="w-1.5 h-1.5 rounded-full animate-bounce"
                          style={{ background: C.dot, animationDelay: `${d * 0.15}s` }} />
                      ))}
                    </div>
                  )}
                </m.div>
              )}

              {/* Error */}
              {error && (
                <m.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="text-xs px-3 py-2 rounded-xl text-center mx-1"
                  style={{ background: "rgba(239,68,68,0.12)", color: "rgb(248,113,113)", border: "1px solid rgba(239,68,68,0.25)" }}>
                  {error}
                </m.div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Initial suggestions — project-specific, before first message */}
            {!hasMessages && (
              <div className="shrink-0 px-3 pt-2 pb-2"
                style={{ borderTop: `1px solid ${C.headerBorder}` }}>
                <p className="text-[10px] font-semibold uppercase tracking-widest mb-2"
                  style={{ color: C.textSecond }}>
                  Try asking
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {initSuggestions.map(s => (
                    <button key={s} onClick={() => send(s)} disabled={loading}
                      className="text-[11px] px-2.5 py-1 rounded-full transition-all hover:opacity-90 active:scale-95 disabled:opacity-40"
                      style={{ background: C.pillBg, color: C.textPrimary, border: `1px solid ${C.pillBorder}`, whiteSpace: "nowrap" }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input */}
            <div className="px-3 py-3 shrink-0 flex gap-2 items-end"
              style={{ borderTop: `1px solid ${C.headerBorder}` }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything about this recommendation..."
                rows={1}
                disabled={loading}
                className="archguide-chat-input flex-1 resize-none text-sm px-3.5 py-2.5 rounded-xl outline-none disabled:opacity-50"
                style={{
                  background: C.inputBg,
                  color: C.textPrimary,
                  border: `1px solid ${C.inputBorder}`,
                  maxHeight: "96px",
                  lineHeight: "1.5",
                  caretColor: C.accent,
                }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
                }}
              />
              <button onClick={() => send(input)}
                disabled={!input.trim() || loading}
                className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity disabled:opacity-30"
                style={{ background: C.accent, color: "#fff" }}
                aria-label="Send message">
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              </button>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </>
  );
}
