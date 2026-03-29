console.log("ENV CHECK:", process.env.NEXT_PUBLIC_FIREBASE_API_KEY);

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
  apiKey: "AIzaSyDppGFKIq33u6CWyohik7Q07w10O0jmY0U",
  authDomain: "hpe-project-73adc.firebaseapp.com",
  projectId: "hpe-project-73adc",
  storageBucket: "hpe-project-73adc..appspot.com",
  messagingSenderId: "527313395755",
  appId: "1:527313395755:web:42525fd7a4207d782c0a6e",
  measurementId: "G-PBVT0QB05H"
};

// Prevent duplicate app initialization in dev (hot reload)
const isConfigured =
  !!firebaseConfig.apiKey &&
  !!firebaseConfig.authDomain &&
  !!firebaseConfig.projectId &&
  !!firebaseConfig.appId;
const fallbackConfig = { apiKey: "dummy-key", authDomain: "dummy.firebaseapp.com", projectId: "dummy-project" };

const app = getApps().length ? getApp() : initializeApp(isConfigured ? firebaseConfig : fallbackConfig);
const auth = getAuth(app);

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

export async function signInWithGoogle(): Promise<User> {
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

export async function signOutUser(): Promise<void> {
  await signOut(auth);
}

export { auth, onAuthStateChanged };
export type { User };
