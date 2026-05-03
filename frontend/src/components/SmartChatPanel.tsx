"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Mic, MicOff, Globe, Sparkles, Trash2, StopCircle, Loader } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  source?: string;
  web_browsed?: boolean;
  topic?: string;
  timestamp: number;
  thinking?: boolean;
}

interface Props {
  uid?: string;
  analysisId?: string;
  analysisResult?: any;
  sessionId?: string;
}

// ── Quick question suggestions ────────────────────────────────────────────────
const QUICK_QUESTIONS = [
  "Why was this architecture recommended?",
  "What are the step-by-step implementation steps?",
  "How much will this cost monthly?",
  "What are the main risks and how to mitigate them?",
  "How does this compare to the other architectures?",
  "Is a hybrid approach worth considering?",
  "What metrics should I track?",
  "Can you explain the confidence score?",
];

// ── Thinking animation ────────────────────────────────────────────────────────
function ThinkingDots() {
  return (
    <div style={{ display: "flex", gap: 5, alignItems: "center", padding: "12px 16px" }}>
      <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", fontFamily: "JetBrains Mono,monospace" }}>AI thinking</span>
      {[0, 1, 2].map(i => (
        <motion.span key={i} animate={{ y: [0, -5, 0], opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18 }}
          style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
      ))}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";

  // Parse **bold** and newlines
  const formatted = msg.content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>');

  return (
    <motion.div initial={{ opacity: 0, y: 12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      style={{
        maxWidth: "86%", alignSelf: isUser ? "flex-end" : "flex-start",
        display: "flex", flexDirection: "column", gap: 4,
      }}>
      {!isUser && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, paddingLeft: 4, marginBottom: 2 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: "linear-gradient(135deg,var(--primary),var(--accent))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.65rem" }}>🤖</div>
          <span style={{ fontSize: "0.62rem", fontFamily: "JetBrains Mono,monospace", color: "var(--primary)", letterSpacing: "1px" }}>ARCHGUIDE AI</span>
          {msg.web_browsed && (
            <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: "0.58rem", color: "var(--accent)", background: "rgba(10,132,255,0.1)", padding: "1px 7px", borderRadius: 100, border: "1px solid rgba(10,132,255,0.2)" }}>
              <Globe size={8} /> web
            </span>
          )}
          {msg.source === "llm" || msg.source === "llm+web" ? (
            <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: "0.58rem", color: "var(--primary)", background: "var(--primary2)", padding: "1px 7px", borderRadius: 100, border: "1px solid var(--primary3)" }}>
              <Sparkles size={8} /> live AI
            </span>
          ) : null}
        </div>
      )}
      <div style={{
        padding: isUser ? "11px 16px" : "14px 18px",
        borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
        background: isUser ? "rgba(1,169,130,0.15)" : "rgba(255,255,255,0.05)",
        border: isUser ? "1px solid rgba(1,169,130,0.3)" : "1px solid var(--border)",
        fontSize: "0.87rem", lineHeight: 1.7, color: "var(--text-primary)",
      }}>
        {msg.thinking ? <ThinkingDots /> : (
          <div dangerouslySetInnerHTML={{ __html: formatted }} />
        )}
      </div>
      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", paddingLeft: isUser ? 0 : 4, paddingRight: isUser ? 4 : 0, textAlign: isUser ? "right" : "left" }}>
        {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </div>
    </motion.div>
  );
}

// ── Voice Recorder ────────────────────────────────────────────────────────────
function useVoiceInput(onTranscript: (text: string) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState("");
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<any>(null);

  // Check browser support
  const hasBrowserSpeech = typeof window !== "undefined" &&
    ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);

  const startBrowserRecognition = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    let finalTranscript = "";

    recognition.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          finalTranscript += e.results[i][0].transcript;
        }
      }
    };

    recognition.onend = () => {
      setIsRecording(false);
      setIsProcessing(false);
      if (finalTranscript.trim()) {
        onTranscript(finalTranscript.trim());
      }
    };

    recognition.onerror = (e: any) => {
      setError(e.error === "not-allowed" ? "Microphone access denied." : "Voice recognition failed.");
      setIsRecording(false);
      setIsProcessing(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
    setError("");
  }, [onTranscript]);

  const startMediaRecorder = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        setIsProcessing(true);
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach(t => t.stop());

        // Send to backend Whisper endpoint
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        try {
          const res = await fetch(`${API}/api/v1/voice/transcribe`, { method: "POST", body: formData });
          const data = await res.json();
          if (data.transcript) {
            onTranscript(data.transcript);
          } else {
            setError(data.message || "Could not transcribe audio.");
          }
        } catch {
          setError("Transcription failed. Try typing instead.");
        }
        setIsProcessing(false);
        setIsRecording(false);
      };

      mediaRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setError("");
    } catch (e: any) {
      setError("Microphone access denied. Please allow microphone permissions.");
    }
  }, [onTranscript]);

  const start = useCallback(() => {
    // Prefer browser speech recognition (faster, no server needed)
    if (hasBrowserSpeech) {
      startBrowserRecognition();
    } else {
      startMediaRecorder();
    }
  }, [hasBrowserSpeech, startBrowserRecognition, startMediaRecorder]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    mediaRef.current?.stop();
    setIsRecording(false);
  }, []);

  return { isRecording, isProcessing, error, start, stop, hasBrowserSpeech };
}

// ── Main Chat Panel ───────────────────────────────────────────────────────────
export function SmartChatPanel({ uid, analysisId, analysisResult, sessionId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [showQuick, setShowQuick] = useState(true);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => endRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleVoiceTranscript = useCallback((text: string) => {
    setInput(text);
    setVoiceTranscript(text);
    inputRef.current?.focus();
  }, []);

  const voice = useVoiceInput(handleVoiceTranscript);

  // Load history on mount
  useEffect(() => {
    if (!uid || loaded) return;
    fetch(`${API}/api/v1/chat/${uid}/history?limit=30`)
      .then(r => r.json())
      .then(d => {
        if (d.messages?.length > 0) {
          setMessages(d.messages.map((m: any, i: number) => ({
            id: `hist_${i}`, role: m.role, content: m.content,
            source: m.source, timestamp: m.created_at ? m.created_at * 1000 : Date.now(),
          })));
          setShowQuick(false);
        } else {
          const rec = analysisResult?.recommended || "your architecture";
          const conf = analysisResult?.confidence ? Math.round(analysisResult.confidence * 100) : null;
          setMessages([{
            id: "welcome", role: "assistant", timestamp: Date.now(),
            source: "system",
            content: `Hello! I'm your ArchGuide AI assistant — powered by a live LLM that genuinely **thinks** through your questions.\n\n${rec !== "your architecture" ? `Your analysis recommended **${rec}**${conf ? ` with ${conf}% confidence` : ""}. ` : ""}I can answer anything about:\n• Why this architecture was chosen\n• Step-by-step implementation\n• Cost estimates and trade-offs\n• Risks and how to mitigate them\n• Any AI/ML question you have\n\nI also browse the web for up-to-date answers. Ask me anything!`,
          }]);
        }
        setLoaded(true);
      })
      .catch(() => {
        setMessages([{ id: "welcome", role: "assistant", timestamp: Date.now(), source: "system", content: "Hello! I'm your ArchGuide AI assistant. Ask me anything about your architecture recommendation!" }]);
        setLoaded(true);
      });
  }, [uid, loaded, analysisResult]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    if (!uid) {
      setMessages(m => [...m, {
        id: `err_${Date.now()}`, role: "assistant", timestamp: Date.now(),
        content: "Please sign in to use the AI chat assistant with persistent memory.",
      }]);
      return;
    }

    const userMsg: Message = { id: `u_${Date.now()}`, role: "user", content: text.trim(), timestamp: Date.now() };
    const thinkingMsg: Message = { id: `t_${Date.now()}`, role: "assistant", content: "", timestamp: Date.now(), thinking: true };

    setMessages(m => [...m, userMsg, thinkingMsg]);
    setInput(""); setLoading(true); setShowQuick(false);

    try {
      const res = await fetch(`${API}/api/v1/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          uid,
          content: text.trim(),
          analysis_id: analysisId,
          session_id: sessionId || uid,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Replace thinking message with real response
      setMessages(m => m.map(msg =>
        msg.thinking ? {
          ...msg, thinking: false, content: data.content,
          source: data.source, web_browsed: data.web_browsed,
          topic: data.topic, id: `a_${Date.now()}`,
        } : msg
      ));
    } catch (e) {
      setMessages(m => m.map(msg =>
        msg.thinking ? {
          ...msg, thinking: false,
          content: "I encountered an error connecting to the AI. Please check that the backend is running at " + API,
        } : msg
      ));
    }
    setLoading(false);
    setTimeout(scrollToBottom, 100);
    inputRef.current?.focus();
  };

  const clearHistory = async () => {
    if (!uid) return;
    await fetch(`${API}/api/v1/chat/${uid}/clear`, { method: "DELETE" }).catch(() => {});
    const rec = analysisResult?.recommended || "your architecture";
    setMessages([{ id: `clear_${Date.now()}`, role: "assistant", timestamp: Date.now(), content: `Chat cleared. Ready to help with your **${rec}** analysis!` }]);
    setShowQuick(true);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 520, maxHeight: 680 }}>
      {/* ── Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 20px", borderBottom: "1px solid var(--border)", flexShrink: 0, background: "rgba(255,255,255,0.02)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: "50%", background: "linear-gradient(135deg,var(--primary),var(--accent))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.1rem", boxShadow: "0 0 16px rgba(1,169,130,0.3)" }}>🤖</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: "0.92rem", fontFamily: "Space Grotesk,sans-serif" }}>ArchGuide AI</div>
            <div style={{ fontSize: "0.63rem", color: "var(--primary)", fontFamily: "JetBrains Mono,monospace", display: "flex", alignItems: "center", gap: 5 }}>
              <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 2, repeat: Infinity }}
                style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
              Live · Thinks dynamically · Browses web
            </div>
          </div>
        </div>
        <button onClick={clearHistory} title="Clear chat history"
          style={{ padding: "6px 12px", borderRadius: 8, background: "rgba(255,55,95,0.08)", border: "1px solid rgba(255,55,95,0.2)", color: "var(--danger)", fontSize: "0.72rem", cursor: "pointer", display: "flex", alignItems: "center", gap: 5 }}>
          <Trash2 size={12} /> Clear
        </button>
      </div>

      {/* ── Messages ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px", display: "flex", flexDirection: "column", gap: 14 }}>
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}

        {/* Quick questions */}
        <AnimatePresence>
          {showQuick && messages.length <= 1 && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "JetBrains Mono,monospace", letterSpacing: "1.5px" }}>SUGGESTED QUESTIONS</div>
              {QUICK_QUESTIONS.slice(0, 5).map(q => (
                <motion.button key={q} whileHover={{ x: 4 }} onClick={() => sendMessage(q)}
                  style={{ padding: "9px 14px", borderRadius: 10, background: "rgba(1,169,130,0.06)", border: "1px solid rgba(1,169,130,0.18)", color: "var(--text-secondary)", fontSize: "0.82rem", cursor: "pointer", textAlign: "left", transition: "all 0.2s", fontFamily: "Plus Jakarta Sans,sans-serif", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: "var(--primary)", flexShrink: 0 }}>→</span> {q}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={endRef} />
      </div>

      {/* ── Voice error ── */}
      <AnimatePresence>
        {voice.error && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ margin: "0 18px", padding: "8px 14px", borderRadius: 8, background: "rgba(255,55,95,0.08)", border: "1px solid rgba(255,55,95,0.2)", fontSize: "0.76rem", color: "var(--danger)" }}>
            ⚠ {voice.error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Voice recording indicator ── */}
      <AnimatePresence>
        {(voice.isRecording || voice.isProcessing) && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 18px", background: voice.isRecording ? "rgba(255,55,95,0.08)" : "rgba(1,169,130,0.08)", borderTop: "1px solid var(--border)" }}>
            {voice.isRecording ? (
              <>
                <motion.div animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }} transition={{ duration: 0.8, repeat: Infinity }}
                  style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--danger)" }} />
                <span style={{ fontSize: "0.78rem", color: "var(--danger)", fontWeight: 600 }}>Recording… speak now</span>
                <button onClick={voice.stop} style={{ marginLeft: "auto", padding: "4px 10px", borderRadius: 8, background: "rgba(255,55,95,0.15)", border: "1px solid rgba(255,55,95,0.3)", color: "var(--danger)", fontSize: "0.72rem", cursor: "pointer" }}>
                  <StopCircle size={12} style={{ display: "inline" }} /> Stop
                </button>
              </>
            ) : (
              <>
                <Loader size={14} style={{ color: "var(--primary)", animation: "spin 1s linear infinite" }} />
                <span style={{ fontSize: "0.78rem", color: "var(--primary)" }}>Processing audio…</span>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Input bar ── */}
      <div style={{ padding: "12px 16px 16px", borderTop: "1px solid var(--border)", display: "flex", gap: 8, flexShrink: 0, alignItems: "center" }}>
        {/* Voice button */}
        <motion.button whileTap={{ scale: 0.9 }} title={voice.isRecording ? "Stop recording" : "Voice input"}
          onClick={voice.isRecording ? voice.stop : voice.start}
          disabled={voice.isProcessing || loading}
          style={{
            width: 42, height: 42, borderRadius: "50%", flexShrink: 0, cursor: "pointer",
            border: "1px solid",
            background: voice.isRecording ? "rgba(255,55,95,0.15)" : "rgba(255,255,255,0.04)",
            borderColor: voice.isRecording ? "rgba(255,55,95,0.4)" : "var(--border)",
            color: voice.isRecording ? "var(--danger)" : "var(--text-secondary)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: voice.isRecording ? "0 0 16px rgba(255,55,95,0.3)" : "none",
            transition: "all 0.2s",
          }}>
          {voice.isProcessing ? <Loader size={16} style={{ animation: "spin 1s linear infinite" }} /> :
            voice.isRecording ? <MicOff size={16} /> : <Mic size={16} />}
        </motion.button>

        {/* Text input */}
        <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
          placeholder={voice.isRecording ? "Listening…" : "Ask anything — I think and learn dynamically…"}
          disabled={loading || voice.isRecording || voice.isProcessing}
          style={{
            flex: 1, padding: "11px 16px", borderRadius: 100,
            border: `1px solid ${input ? "var(--primary)" : "var(--border)"}`,
            background: "rgba(255,255,255,0.04)", color: "var(--text-primary)",
            fontFamily: "Plus Jakarta Sans,sans-serif", fontSize: "0.87rem", outline: "none",
            transition: "border-color 0.2s", boxShadow: input ? "0 0 0 2px rgba(1,169,130,0.12)" : "none",
          }} />

        {/* Send button */}
        <motion.button whileTap={{ scale: 0.92 }} onClick={() => sendMessage(input)}
          disabled={!input.trim() || loading || voice.isRecording}
          style={{
            width: 42, height: 42, borderRadius: "50%", flexShrink: 0,
            background: input.trim() && !loading ? "linear-gradient(135deg,var(--primary),#00875A)" : "rgba(255,255,255,0.06)",
            border: "none", cursor: input.trim() && !loading ? "pointer" : "not-allowed",
            color: input.trim() && !loading ? "#fff" : "var(--text-muted)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: input.trim() && !loading ? "0 0 20px rgba(1,169,130,0.35)" : "none",
            transition: "all 0.25s",
          }}>
          <Send size={16} />
        </motion.button>
      </div>

      <style>{`@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }`}</style>
    </div>
  );
}
