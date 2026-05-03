"use client";
import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Eye, EyeOff, AlertTriangle, CheckCircle, Sparkles, Chrome } from "lucide-react";
import {
  checkPasswordStrength, validateEmail, emailExists,
  STRONG_PASSWORDS, PasswordStrength,
} from "@/lib/auth-local";
import { useAuth } from "@/lib/auth-context";

// ── Password strength bar ─────────────────────────────────────────────────────
function StrengthBar({ strength }: { strength: PasswordStrength }) {
  const bars = [1, 2, 3, 4];
  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
        {bars.map(i => (
          <motion.div key={i}
            animate={{ background: i <= strength.score ? strength.color : "rgba(255,255,255,0.08)" }}
            transition={{ duration: 0.3 }}
            style={{ flex: 1, height: 3, borderRadius: 2 }} />
        ))}
      </div>
      {strength.label && (
        <div style={{ fontSize: "0.7rem", color: strength.color, fontFamily: "JetBrains Mono,monospace", fontWeight: 700 }}>
          {strength.label}
        </div>
      )}
    </div>
  );
}

// ── Requirements checklist ────────────────────────────────────────────────────
function Requirements({ password }: { password: string }) {
  const c = checkPasswordStrength(password).checks;
  const items = [
    ["8+ characters", c.length],
    ["Uppercase letter (A–Z)", c.uppercase],
    ["Number (0–9)", c.number],
    ["Special character (!@#$...)", c.special],
  ] as const;
  return (
    <div style={{ marginTop: 10, padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}>
      {items.map(([label, ok]) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
          <span style={{ color: ok ? "var(--primary)" : "var(--text-muted)", fontSize: "0.72rem", fontWeight: 700, flexShrink: 0 }}>
            {ok ? "✓" : "○"}
          </span>
          <span style={{ fontSize: "0.72rem", color: ok ? "var(--text-primary)" : "var(--text-secondary)" }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Password suggestions ──────────────────────────────────────────────────────
function PasswordSuggestions({ onPick }: { onPick: (pw: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 8 }}>
      <button type="button" onClick={() => setOpen(o => !o)}
        style={{ fontSize: "0.72rem", color: "var(--accent)", cursor: "pointer", background: "none", border: "none", display: "flex", alignItems: "center", gap: 5, fontFamily: "Plus Jakarta Sans,sans-serif" }}>
        <Sparkles size={11} /> {open ? "Hide" : "Suggest a strong password"}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            style={{ marginTop: 8, padding: 12, borderRadius: 10, background: "var(--glass-bg)", border: "1px solid var(--border)" }}>
            <div style={{ fontSize: "0.63rem", color: "var(--text-secondary)", fontFamily: "JetBrains Mono,monospace", letterSpacing: "1.5px", marginBottom: 8 }}>SUGGESTED PASSWORDS</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {STRONG_PASSWORDS.slice(0, 4).map((pw, i) => (
                <motion.button key={pw} type="button" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  onClick={() => { onPick(pw); setOpen(false); }}
                  style={{ fontFamily: "JetBrains Mono,monospace", fontSize: "0.78rem", padding: "7px 12px", borderRadius: 8, background: "rgba(1,169,130,0.07)", border: "1px solid rgba(1,169,130,0.2)", color: "var(--primary)", cursor: "pointer", textAlign: "left", transition: "all 0.2s", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{pw}</span>
                  <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>click to use</span>
                </motion.button>
              ))}
            </div>
            <div style={{ marginTop: 8, fontSize: "0.66rem", color: "var(--text-muted)" }}>
              💡 Save this password somewhere safe before using it.
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Input field ───────────────────────────────────────────────────────────────
function Field({
  label, type, value, onChange, onBlur, placeholder, error, success, hint, rightEl, autoComplete,
}: {
  label: string; type: string; value: string; onChange: (v: string) => void;
  onBlur?: () => void; placeholder?: string; error?: string; success?: string;
  hint?: string; rightEl?: React.ReactNode; autoComplete?: string;
}) {
  const hasError = !!error;
  const hasSuccess = !!success && !hasError;
  return (
    <div>
      <label style={{ fontSize: "0.76rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>{label}</label>
      <div style={{ position: "relative" }}>
        <input type={type} value={value} placeholder={placeholder} autoComplete={autoComplete}
          onChange={e => onChange(e.target.value)} onBlur={onBlur}
          style={{
            width: "100%", padding: "11px 14px", paddingRight: rightEl ? 44 : 14,
            borderRadius: 10, border: `1px solid ${hasError ? "var(--danger)" : hasSuccess ? "var(--primary)" : "var(--border)"}`,
            background: "rgba(255,255,255,0.04)", color: "var(--text-primary)",
            fontFamily: "Plus Jakarta Sans,sans-serif", fontSize: "0.87rem", outline: "none",
            boxShadow: hasError ? "0 0 0 3px rgba(255,55,95,0.1)" : hasSuccess ? "0 0 0 3px rgba(1,169,130,0.1)" : "none",
            transition: "all 0.2s",
          }} />
        {rightEl && (
          <div style={{ position: "absolute", right: 13, top: "50%", transform: "translateY(-50%)" }}>
            {rightEl}
          </div>
        )}
      </div>
      <AnimatePresence>
        {hasError && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ marginTop: 5, fontSize: "0.72rem", color: "var(--danger)", display: "flex", gap: 4, alignItems: "center" }}>
            <AlertTriangle size={11} /> {error}
          </motion.div>
        )}
        {hasSuccess && !hasError && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ marginTop: 5, fontSize: "0.72rem", color: "var(--primary)", display: "flex", gap: 4, alignItems: "center" }}>
            <CheckCircle size={11} /> {success}
          </motion.div>
        )}
      </AnimatePresence>
      {hint && !hasError && !hasSuccess && (
        <div style={{ marginTop: 4, fontSize: "0.68rem", color: "var(--text-muted)" }}>{hint}</div>
      )}
    </div>
  );
}

// ── Main Modal ────────────────────────────────────────────────────────────────
interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (user: any) => void;
  onSkip: () => void;
  signIn?: () => Promise<any>;
  signOut?: () => Promise<void>;
  mode?: "default" | "project-limit";
}

type Tab = "signin" | "signup";

export function AuthModal({ isOpen, onClose, onAuthSuccess, onSkip, mode = "default" }: AuthModalProps) {
  const { signInWithEmail, signUpWithEmail, signInWithGoogle, firebaseConfigured } = useAuth();

  const [tab, setTab] = useState<Tab>("signin");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState<"auth" | "skip-confirm">("auth");

  // Sign-in fields
  const [siEmail, setSiEmail] = useState("");
  const [siPw, setSiPw] = useState("");
  const [siPwVisible, setSiPwVisible] = useState(false);
  const [siTouched, setSiTouched] = useState({ email: false, pw: false });

  // Sign-up fields
  const [suName, setSuName] = useState("");
  const [suEmail, setSuEmail] = useState("");
  const [suPw, setSuPw] = useState("");
  const [suPwConfirm, setSuPwConfirm] = useState("");
  const [suPwVisible, setSuPwVisible] = useState(false);
  const [suConfirmVisible, setSuConfirmVisible] = useState(false);
  const [suTouched, setSuTouched] = useState({ name: false, email: false, pw: false, confirm: false });

  const switchTab = (t: Tab) => { setTab(t); setError(""); };

  // ── Derived validation ─────────────────────────────────────────────────────
  const siEmailErr   = siTouched.email && !validateEmail(siEmail).valid ? validateEmail(siEmail).error : "";
  const siPwErr      = siTouched.pw && !siPw ? "Password is required" : "";

  const suEmailVal   = validateEmail(suEmail);
  const suEmailErr   = suTouched.email && !suEmailVal.valid ? suEmailVal.error : "";
  const suEmailExists = suTouched.email && suEmailVal.valid && emailExists(suEmail) ? "Account already exists — please sign in." : "";
  const suPwStrength = checkPasswordStrength(suPw);
  const suPwErr      = suTouched.pw && suPwStrength.errors.length > 0 ? suPwStrength.errors[0] : "";
  const suConfirmErr = suTouched.confirm && suPw !== suPwConfirm ? "Passwords do not match" : "";
  const suNameErr    = suTouched.name && !suName.trim() ? "Name is required" : "";

  const canSignIn = siEmail && siPw && !siEmailErr;
  const canSignUp = suName.trim() && suEmail && suPw && suPwConfirm && suPwStrength.errors.length === 0 && suPw === suPwConfirm && suEmailVal.valid && !suEmailExists;

  // ── Submit handlers ────────────────────────────────────────────────────────
  const handleSignIn = async () => {
    setSiTouched({ email: true, pw: true });
    if (!canSignIn) return;
    setLoading(true); setError("");
    try {
      const user = await signInWithEmail(siEmail, siPw);
      onAuthSuccess(user);
    } catch (e: any) {
      setError(e.message || "Sign in failed. Please try again.");
    } finally { setLoading(false); }
  };

  const handleSignUp = async () => {
    setSuTouched({ name: true, email: true, pw: true, confirm: true });
    if (!canSignUp) return;
    setLoading(true); setError("");
    try {
      const user = await signUpWithEmail(suEmail, suPw, suName);
      onAuthSuccess(user);
    } catch (e: any) {
      setError(e.message || "Sign up failed. Please try again.");
    } finally { setLoading(false); }
  };

  const handleGoogle = async () => {
    setLoading(true); setError("");
    try {
      const user = await signInWithGoogle();
      onAuthSuccess(user);
    } catch (e: any) {
      if (e?.code === "auth/popup-closed-by-user" || e?.code === "auth/cancelled-popup-request") {
        setError("");
      } else if (e?.code === "auth/configuration-not-found") {
        setError("Google Sign-In is not configured. Please use email/password above.");
      } else {
        setError(e?.message?.replace(/^Firebase:\s*/i, "") || "Google sign-in failed.");
      }
    } finally { setLoading(false); }
  };

  // ── Transfer anon project ─────────────────────────────────────────────────
  const [anonProject, setAnonProject] = useState<any>(null);

  const checkAndTransfer = async (user: any) => {
    const { getProjects } = await import("@/lib/projects-store");
    const anon = await getProjects(null);
    if (anon.length > 0) {
      setAnonProject(anon[0]);
      // auto-transfer
      const { updateProject } = await import("@/lib/projects-store");
      await updateProject(anon[0].id, { userId: user.uid }).catch(() => {});
    }
    onAuthSuccess(user);
  };

  // ── Animation variants ─────────────────────────────────────────────────────
  const modal = {
    hidden:  { opacity: 0, scale: 0.93, y: 24 },
    visible: { opacity: 1, scale: 1,    y: 0,  transition: { type: "spring", stiffness: 320, damping: 28 } },
    exit:    { opacity: 0, scale: 0.97, y: 10, transition: { duration: 0.18 } },
  };

  const tabSlide = {
    enter: (dir: number) => ({ x: dir > 0 ? 40 : -40, opacity: 0 }),
    center: { x: 0, opacity: 1, transition: { duration: 0.28, ease: [0.16,1,0.3,1] } },
    exit: (dir: number) => ({ x: dir > 0 ? -40 : 40, opacity: 0, transition: { duration: 0.18 } }),
  };
  const dir = tab === "signup" ? 1 : -1;

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
        style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)", background: "rgba(0,0,0,0.72)" }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}>

        <AnimatePresence mode="wait">
          {step === "skip-confirm" ? (
            <motion.div key="skip" variants={modal} initial="hidden" animate="visible" exit="exit"
              style={{ width: "100%", maxWidth: 380, borderRadius: 28, border: "1px solid var(--border)", background: "var(--surface)", padding: 36, textAlign: "center" }}>
              <div style={{ width: 52, height: 52, borderRadius: 14, background: "rgba(255,131,0,0.12)", border: "1px solid rgba(255,131,0,0.2)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                <AlertTriangle size={24} style={{ color: "var(--orange)" }} />
              </div>
              <h3 style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 800, fontSize: "1.2rem", marginBottom: 10 }}>Continue Without Saving?</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: 1.7, marginBottom: 28 }}>
                Your analyses won't be saved and will be lost when you leave the page.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <button onClick={onSkip} style={{ padding: "12px", borderRadius: 100, border: "1px solid var(--border)", background: "transparent", color: "var(--text-primary)", cursor: "pointer", fontWeight: 700, fontSize: "0.87rem" }}>Continue Anyway</button>
                <button onClick={() => setStep("auth")} style={{ padding: "10px", background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>← Go Back</button>
              </div>
            </motion.div>
          ) : (
            <motion.div key="auth" variants={modal} initial="hidden" animate="visible" exit="exit"
              style={{ width: "100%", maxWidth: 460, borderRadius: 28, border: "1px solid var(--border)", background: "var(--surface)", overflow: "hidden", position: "relative" }}>

              {/* Top accent */}
              <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "linear-gradient(90deg, transparent, var(--primary), transparent)" }} />

              {/* Close */}
              <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, width: 30, height: 30, borderRadius: "50%", border: "1px solid var(--border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s", zIndex: 10 }}>
                <X size={14} />
              </button>

              <div style={{ padding: "32px 32px 28px" }}>
                {/* Brand */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 12, background: "linear-gradient(135deg,var(--primary),var(--accent))", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="white"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" /></svg>
                  </div>
                  <div>
                    <div style={{ fontFamily: "Space Grotesk,sans-serif", fontWeight: 800, fontSize: "0.95rem", color: "var(--primary)" }}>ArchGuide</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontFamily: "JetBrains Mono,monospace", letterSpacing: "1px" }}>INTELLIGENCE PLATFORM</div>
                  </div>
                </div>

                {/* Tab switcher */}
                <div style={{ display: "flex", background: "rgba(255,255,255,0.04)", borderRadius: 12, padding: 4, marginBottom: 28, border: "1px solid var(--border)" }}>
                  {([["signin","Sign In"],["signup","Create Account"]] as const).map(([t, label]) => (
                    <button key={t} onClick={() => switchTab(t)}
                      style={{ flex: 1, padding: "9px 8px", borderRadius: 9, border: "none", cursor: "pointer", fontFamily: "Space Grotesk,sans-serif", fontWeight: 700, fontSize: "0.82rem", transition: "all 0.25s",
                        background: tab === t ? "var(--primary)" : "transparent",
                        color: tab === t ? "#fff" : "var(--text-secondary)",
                        boxShadow: tab === t ? "0 2px 12px rgba(1,169,130,0.35)" : "none",
                      }}>
                      {label}
                    </button>
                  ))}
                </div>

                {/* Error banner */}
                <AnimatePresence>
                  {error && (
                    <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      style={{ marginBottom: 16, padding: "10px 14px", borderRadius: 10, background: "rgba(255,55,95,0.08)", border: "1px solid rgba(255,55,95,0.22)", color: "var(--danger)", fontSize: "0.8rem", display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      {error}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Form content */}
                <AnimatePresence mode="wait" custom={dir}>
                  {tab === "signin" ? (
                    <motion.div key="signin" custom={dir} variants={tabSlide} initial="enter" animate="center" exit="exit">
                      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        <Field label="Email Address" type="email" value={siEmail} onChange={setSiEmail}
                          onBlur={() => setSiTouched(t => ({ ...t, email: true }))}
                          placeholder="you@any-domain.com"
                          autoComplete="email"
                          error={siEmailErr}
                          success={siTouched.email && validateEmail(siEmail).valid ? "Valid email ✓" : ""}
                          hint="Accepts any email — Gmail, Yahoo, college, work" />
                        <Field label="Password" type={siPwVisible ? "text" : "password"} value={siPw} onChange={setSiPw}
                          onBlur={() => setSiTouched(t => ({ ...t, pw: true }))}
                          placeholder="Enter your password" autoComplete="current-password"
                          error={siPwErr}
                          rightEl={
                            <button type="button" onClick={() => setSiPwVisible(v => !v)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", display: "flex" }}>
                              {siPwVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          } />
                      </div>

                      <motion.button whileTap={{ scale: 0.97 }} onClick={handleSignIn} disabled={loading}
                        style={{ width: "100%", marginTop: 22, padding: "13px", borderRadius: 100, border: "none", cursor: loading ? "not-allowed" : "pointer", background: canSignIn ? "linear-gradient(135deg,var(--primary),#00875A)" : "rgba(255,255,255,0.07)", color: canSignIn ? "#fff" : "var(--text-muted)", fontWeight: 700, fontSize: "0.92rem", fontFamily: "Space Grotesk,sans-serif", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, boxShadow: canSignIn ? "0 0 28px rgba(1,169,130,0.3)" : "none", transition: "all 0.3s" }}>
                        {loading ? <><span className="dot-1" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /><span className="dot-2" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /><span className="dot-3" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /></>
                          : "Sign In →"}
                      </motion.button>

                      <div style={{ marginTop: 14, textAlign: "center", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        No account yet?{" "}
                        <button onClick={() => switchTab("signup")} style={{ color: "var(--primary)", background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}>Create one free</button>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div key="signup" custom={dir} variants={tabSlide} initial="enter" animate="center" exit="exit">
                      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                        <Field label="Full Name" type="text" value={suName} onChange={setSuName}
                          onBlur={() => setSuTouched(t => ({ ...t, name: true }))}
                          placeholder="Your name" autoComplete="name"
                          error={suNameErr}
                          success={suTouched.name && suName.trim() ? "Looking good!" : ""} />

                        <Field label="Email Address" type="email" value={suEmail} onChange={setSuEmail}
                          onBlur={() => setSuTouched(t => ({ ...t, email: true }))}
                          placeholder="you@any-domain.com" autoComplete="email"
                          error={suEmailErr || suEmailExists}
                          success={suTouched.email && suEmailVal.valid && !suEmailExists ? "Valid email ✓" : ""}
                          hint="Gmail · Yahoo · Outlook · College · Work — any format" />

                        <div>
                          <Field label="Password" type={suPwVisible ? "text" : "password"} value={suPw} onChange={v => { setSuPw(v); setSuTouched(t => ({ ...t, pw: true })); }}
                            onBlur={() => setSuTouched(t => ({ ...t, pw: true }))}
                            placeholder="Min 8 chars, A-Z, 0-9, !@#" autoComplete="new-password"
                            error={suPwErr}
                            rightEl={
                              <button type="button" onClick={() => setSuPwVisible(v => !v)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", display: "flex" }}>
                                {suPwVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                              </button>
                            } />
                          {suPw && <div style={{ marginTop: 8 }}><StrengthBar strength={suPwStrength} /></div>}
                          {suPw && <Requirements password={suPw} />}
                          <PasswordSuggestions onPick={pw => { setSuPw(pw); setSuPwConfirm(pw); setSuTouched(t => ({ ...t, pw: true, confirm: true })); }} />
                        </div>

                        <Field label="Confirm Password" type={suConfirmVisible ? "text" : "password"} value={suPwConfirm}
                          onChange={v => { setSuPwConfirm(v); setSuTouched(t => ({ ...t, confirm: true })); }}
                          onBlur={() => setSuTouched(t => ({ ...t, confirm: true }))}
                          placeholder="Repeat your password" autoComplete="new-password"
                          error={suConfirmErr}
                          success={suTouched.confirm && suPwConfirm && suPw === suPwConfirm ? "Passwords match ✓" : ""}
                          rightEl={
                            <button type="button" onClick={() => setSuConfirmVisible(v => !v)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", display: "flex" }}>
                              {suConfirmVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          } />
                      </div>

                      <motion.button whileTap={{ scale: 0.97 }} onClick={handleSignUp} disabled={loading}
                        style={{ width: "100%", marginTop: 22, padding: "13px", borderRadius: 100, border: "none", cursor: loading ? "not-allowed" : "pointer", background: canSignUp ? "linear-gradient(135deg,var(--primary),#00875A)" : "rgba(255,255,255,0.07)", color: canSignUp ? "#fff" : "var(--text-muted)", fontWeight: 700, fontSize: "0.92rem", fontFamily: "Space Grotesk,sans-serif", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, boxShadow: canSignUp ? "0 0 28px rgba(1,169,130,0.3)" : "none", transition: "all 0.3s" }}>
                        {loading ? <><span className="dot-1" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /><span className="dot-2" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /><span className="dot-3" style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} /></>
                          : "Create Account →"}
                      </motion.button>

                      <div style={{ marginTop: 14, textAlign: "center", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        Already have an account?{" "}
                        <button onClick={() => switchTab("signin")} style={{ color: "var(--primary)", background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}>Sign in</button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Divider + Google */}
                <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0 14px" }}>
                  <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "JetBrains Mono,monospace" }}>OR</span>
                  <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                </div>

                <motion.button whileTap={{ scale: 0.97 }} onClick={handleGoogle} disabled={loading}
                  style={{ width: "100%", padding: "12px", borderRadius: 100, border: "1px solid var(--border)", background: "rgba(255,255,255,0.04)", color: "var(--text-primary)", cursor: "pointer", fontWeight: 600, fontSize: "0.87rem", display: "flex", alignItems: "center", justifyContent: "center", gap: 10, transition: "all 0.2s", fontFamily: "Plus Jakarta Sans,sans-serif" }}>
                  <GoogleIcon />
                  Continue with Google
                  {!firebaseConfigured && <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginLeft: 4 }}>(setup required)</span>}
                </motion.button>

                <button onClick={() => mode === "project-limit" ? onClose() : setStep("skip-confirm")} disabled={loading}
                  style={{ width: "100%", marginTop: 12, padding: "10px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.82rem", fontWeight: 500 }}>
                  {mode === "project-limit" ? "Cancel" : "Skip for now — continue as guest"}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </AnimatePresence>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  );
}
