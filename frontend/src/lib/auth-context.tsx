"use client";
import React, { createContext, useContext, useEffect, useState } from "react";
import { User, onFirebaseAuthChange, googleSignIn, googleSignOut, isFirebaseConfigured } from "@/lib/firebase";
import { LocalUser, localSignIn, localSignUp, localSignOut, getSession } from "@/lib/auth-local";

// Unified user type that works for both Firebase and local auth
export type AppUser = {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  provider: "google" | "local";
};

interface AuthContextValue {
  user: AppUser | null;
  loading: boolean;
  firebaseConfigured: boolean;
  // Email/password auth
  signUpWithEmail: (email: string, password: string, name?: string) => Promise<AppUser>;
  signInWithEmail: (email: string, password: string) => Promise<AppUser>;
  // Google auth (optional - only works if Firebase configured)
  signInWithGoogle: () => Promise<AppUser>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: false,
  firebaseConfigured: false,
  signUpWithEmail: async () => { throw new Error("not mounted"); },
  signInWithEmail: async () => { throw new Error("not mounted"); },
  signInWithGoogle: async () => { throw new Error("not mounted"); },
  signOut: async () => {},
});

function toAppUser(u: User | LocalUser): AppUser {
  if ("provider" in u && u.provider === "local") {
    return { uid: u.uid, email: u.email, displayName: u.displayName, photoURL: u.photoURL, provider: "local" };
  }
  const fu = u as User;
  return { uid: fu.uid, email: fu.email, displayName: fu.displayName, photoURL: fu.photoURL, provider: "google" };
}

async function syncToBackend(user: AppUser) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    await fetch(`${apiUrl}/api/v1/users/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: user.uid, email: user.email, displayName: user.displayName, photoURL: user.photoURL }),
    });
  } catch {}
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. Restore local session first (synchronous)
    const session = getSession();
    if (session) {
      setUser(toAppUser(session));
      setLoading(false);
    }

    // 2. Also listen for Firebase Google auth state (if configured)
    const unsub = onFirebaseAuthChange((firebaseUser) => {
      if (firebaseUser) {
        const appUser = toAppUser(firebaseUser);
        setUser(appUser);
        syncToBackend(appUser);
      } else if (!getSession()) {
        // Only clear if no local session either
        setUser(null);
      }
      setLoading(false);
    });

    return unsub;
  }, []);

  const signUpWithEmail = async (email: string, password: string, name?: string): Promise<AppUser> => {
    const { user: localUser } = await localSignUp(email, password, name);
    const appUser = toAppUser(localUser);
    setUser(appUser);
    syncToBackend(appUser);
    return appUser;
  };

  const signInWithEmail = async (email: string, password: string): Promise<AppUser> => {
    const { user: localUser } = await localSignIn(email, password);
    const appUser = toAppUser(localUser);
    setUser(appUser);
    syncToBackend(appUser);
    return appUser;
  };

  const signInWithGoogle = async (): Promise<AppUser> => {
    const googleUser = await googleSignIn();
    const appUser = toAppUser(googleUser);
    setUser(appUser);
    syncToBackend(appUser);
    return appUser;
  };

  const signOut = async () => {
    localSignOut();
    await googleSignOut();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user, loading, firebaseConfigured: isFirebaseConfigured,
      signUpWithEmail, signInWithEmail, signInWithGoogle, signOut,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
