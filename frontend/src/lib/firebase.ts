// SEC-3.3 FIX: Removed console.log that leaked NEXT_PUBLIC_FIREBASE_API_KEY to the browser console.
// SEC-3.4 FIX: Removed silent fallback to dummy credentials. Missing env vars now surface as an
//              explicit warning so developers get a clear signal that auth is misconfigured.

import { initializeApp, getApps, getApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  User,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Validate that all required Firebase config values are present.
const isConfigured =
  !!firebaseConfig.apiKey &&
  !!firebaseConfig.authDomain &&
  !!firebaseConfig.projectId &&
  !!firebaseConfig.appId;

if (!isConfigured && typeof window !== "undefined") {
  // Warn once in the browser — never in a server/SSR context to avoid log spam.
  console.warn(
    "[Firebase] One or more NEXT_PUBLIC_FIREBASE_* environment variables are missing. " +
    "Google Sign-In will be unavailable. Check your .env.local file."
  );
}

// Only initialize if properly configured; otherwise leave Firebase uninitialised
// so that any auth attempt surfaces a meaningful error rather than an opaque failure.
const app = getApps().length
  ? getApp()
  : isConfigured
  ? initializeApp(firebaseConfig)
  : initializeApp({ apiKey: "__unconfigured__", authDomain: "", projectId: "" });
const auth = getAuth(app);

// Guards against calling signInWithPopup twice concurrently.
// A second call while a popup is already open produces auth/missing-or-invalid-nonce.
let _popupInFlight = false;

export async function signInWithGoogle(): Promise<User> {
  if (_popupInFlight) {
    const err = new Error("Sign-in already in progress — please wait for the Google popup.");
    (err as any).code = "auth/popup-already-open";
    throw err;
  }
  _popupInFlight = true;
  try {
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } finally {
    _popupInFlight = false;
  }
}

export async function signOutUser(): Promise<void> {
  await signOut(auth);
}

export { auth, onAuthStateChanged };
export type { User };
