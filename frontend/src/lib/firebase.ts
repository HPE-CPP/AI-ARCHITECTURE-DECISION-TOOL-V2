/**
 * firebase.ts — Firebase Google Sign-In (optional)
 * App works fully without this. Only needed for Google OAuth.
 */
import { initializeApp, getApps, getApp, FirebaseApp } from "firebase/app";
import {
  getAuth, GoogleAuthProvider, signInWithPopup,
  signOut, onAuthStateChanged, Auth, User, Unsubscribe,
} from "firebase/auth";

const firebaseConfig = {
  apiKey:            process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain:        process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId:         process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket:     process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId:             process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const isFirebaseConfigured =
  !!firebaseConfig.apiKey &&
  !firebaseConfig.apiKey.startsWith("your_") &&
  firebaseConfig.apiKey !== "your_firebase_api_key_here" &&
  !!firebaseConfig.authDomain &&
  !!firebaseConfig.projectId &&
  !!firebaseConfig.appId;

let auth: Auth | null = null;

if (isFirebaseConfigured) {
  try {
    const app: FirebaseApp = getApps().length ? getApp() : initializeApp(firebaseConfig);
    auth = getAuth(app);
  } catch (e) {
    console.warn("[Firebase] Init failed:", e);
  }
}

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

export async function googleSignIn(): Promise<User> {
  if (!auth) throw Object.assign(new Error("Google Sign-In is not configured."), { code: "auth/configuration-not-found" });
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

export async function googleSignOut(): Promise<void> {
  if (!auth) return;
  try { await signOut(auth); } catch {}
}

export function onFirebaseAuthChange(cb: (user: User | null) => void): Unsubscribe {
  if (!auth) { cb(null); return () => {}; }
  return onAuthStateChanged(auth, cb);
}

export type { User };
