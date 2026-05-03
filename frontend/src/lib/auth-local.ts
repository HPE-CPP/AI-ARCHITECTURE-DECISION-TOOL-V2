/**
 * auth-local.ts — Local email/password authentication
 * No Firebase needed. Accounts stored securely in localStorage.
 * Works fully offline. Supports any email format.
 */

export interface LocalUser {
  uid: string;
  email: string;
  displayName: string | null;
  photoURL: string | null;
  provider: "local";
  createdAt: string;
}

const USERS_KEY = "archguide_users";
const SESSION_KEY = "archguide_session";

// ── Password validation ───────────────────────────────────────────────────────
export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4;
  label: "Too weak" | "Weak" | "Fair" | "Good" | "Strong";
  color: string;
  checks: {
    length: boolean;
    uppercase: boolean;
    number: boolean;
    special: boolean;
    longEnough: boolean;
  };
  errors: string[];
}

export function checkPasswordStrength(password: string): PasswordStrength {
  const checks = {
    length:    password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    number:    /[0-9]/.test(password),
    special:   /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password),
    longEnough: password.length >= 12,
  };

  const errors: string[] = [];
  if (!checks.length)    errors.push("At least 8 characters");
  if (!checks.uppercase) errors.push("One uppercase letter (A–Z)");
  if (!checks.number)    errors.push("One number (0–9)");
  if (!checks.special)   errors.push("One special character (!@#$...)");

  const score = [checks.length, checks.uppercase, checks.number, checks.special, checks.longEnough]
    .filter(Boolean).length;

  const scoreMap: PasswordStrength["score"][] = [0, 1, 1, 2, 3, 4];
  const labelMap: PasswordStrength["label"][] = ["Too weak","Weak","Weak","Fair","Good","Strong"];
  const colorMap = ["#FF375F","#FF375F","#FF8300","#FFD60A","#01A982","#01A982"];

  const s = scoreMap[score] ?? 0;
  return { score: s, label: labelMap[score] as PasswordStrength["label"], color: colorMap[score], checks, errors };
}

// Suggested strong passwords
export const STRONG_PASSWORDS = [
  "Arch#Guide2024!",
  "SecureAI$Hub99",
  "Data@Flow2024!",
  "Quantum#Mind88",
  "Neural$Net2024",
  "Cloud@HPE2024!",
  "Edge#AI2024!",
  "Deep$Learn99!",
];

// ── Email validation ───────────────────────────────────────────────────────────
export function validateEmail(email: string): { valid: boolean; error?: string } {
  const trimmed = email.trim().toLowerCase();
  if (!trimmed) return { valid: false, error: "Email is required" };
  // Accept any valid email format: @gmail, @yahoo, @bmsce, @company.co.in etc.
  const re = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
  if (!re.test(trimmed)) return { valid: false, error: "Enter a valid email address" };
  return { valid: true };
}

// ── Simple hash (not cryptographic — for demo; use bcrypt in production) ─────
function simpleHash(str: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (Math.imul(h, 0x01000193) >>> 0);
  }
  // Add a pepper + second pass
  const salted = str + "archguide_salt_2024";
  let h2 = 0x2166f3;
  for (let i = 0; i < salted.length; i++) {
    h2 ^= salted.charCodeAt(i);
    h2 = (Math.imul(h2, 16777619) >>> 0);
  }
  return (h >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(8, "0");
}

function uid(): string {
  return `local_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// ── Storage helpers ───────────────────────────────────────────────────────────
function getUsers(): Record<string, { uid: string; email: string; displayName: string; hash: string; createdAt: string }> {
  try { return JSON.parse(localStorage.getItem(USERS_KEY) || "{}"); } catch { return {}; }
}

function saveUsers(users: ReturnType<typeof getUsers>) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function saveSession(user: LocalUser) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function getSession(): LocalUser | null {
  try {
    const s = localStorage.getItem(SESSION_KEY);
    return s ? JSON.parse(s) : null;
  } catch { return null; }
}

// ── Auth operations ───────────────────────────────────────────────────────────

export async function localSignUp(
  email: string,
  password: string,
  displayName?: string
): Promise<{ user: LocalUser }> {
  const emailCheck = validateEmail(email);
  if (!emailCheck.valid) throw new Error(emailCheck.error);

  const pwCheck = checkPasswordStrength(password);
  if (pwCheck.errors.length > 0) throw new Error(`Password must include: ${pwCheck.errors.join(", ")}`);

  const normalizedEmail = email.trim().toLowerCase();
  const users = getUsers();

  if (users[normalizedEmail]) {
    throw new Error("An account with this email already exists. Please sign in.");
  }

  const user: LocalUser = {
    uid: uid(),
    email: normalizedEmail,
    displayName: displayName?.trim() || normalizedEmail.split("@")[0],
    photoURL: null,
    provider: "local",
    createdAt: new Date().toISOString(),
  };

  users[normalizedEmail] = { uid: user.uid, email: user.email, displayName: user.displayName!, hash: simpleHash(password), createdAt: user.createdAt };
  saveUsers(users);
  saveSession(user);
  return { user };
}

export async function localSignIn(email: string, password: string): Promise<{ user: LocalUser }> {
  const normalizedEmail = email.trim().toLowerCase();
  const users = getUsers();
  const stored = users[normalizedEmail];

  if (!stored) throw new Error("No account found with this email. Please create an account.");
  if (stored.hash !== simpleHash(password)) throw new Error("Incorrect password. Please try again.");

  const user: LocalUser = {
    uid: stored.uid,
    email: stored.email,
    displayName: stored.displayName,
    photoURL: null,
    provider: "local",
    createdAt: stored.createdAt,
  };
  saveSession(user);
  return { user };
}

export function localSignOut() {
  clearSession();
}

export function emailExists(email: string): boolean {
  const users = getUsers();
  return !!users[email.trim().toLowerCase()];
}
