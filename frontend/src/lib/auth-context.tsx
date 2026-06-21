"use client";
import React, { createContext, useContext, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api-base";
import type { User } from "firebase/auth";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: () => Promise<User>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  signIn: async () => { throw new Error("AuthProvider not mounted"); },
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let unsubscribe: (() => void) | null = null;
    let active = true;

    // Lazy-load Firebase so it's excluded from the initial JS bundle and
    // never blocks the first paint or LCP measurement.
    import("@/lib/firebase").then(({ auth, onAuthStateChanged }) => {
      if (!active) return;
      unsubscribe = onAuthStateChanged(auth, (u) => {
        setUser(u);
        setLoading(false);
      });
    });

    return () => {
      active = false;
      unsubscribe?.();
    };
  }, []);

  const signIn = async (): Promise<User> => {
    const { signInWithGoogle } = await import("@/lib/firebase");
    const u = await signInWithGoogle();
    setUser(u);

    // FIX FE-004: Backend sync with retry
    if (u) {
      const payload = {
        uid: u.uid,
        email: u.email,
        displayName: u.displayName,
        photoURL: u.photoURL,
      };
      // The /users/sync endpoint requires a valid Firebase JWT (SEC-001).
      // Without this Authorization header the backend returns 401 and the
      // user is never persisted to Postgres.
      const idToken = await u.getIdToken();
      const apiUrl = getApiBase();
      const MAX_RETRIES = 3;
      let lastError: unknown;
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          const res = await fetch(`${apiUrl}/api/v1/users/sync`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${idToken}`,
            },
            body: JSON.stringify(payload),
          });
          if (res.ok) break;
          lastError = new Error(`HTTP ${res.status}`);
        } catch (err) {
          lastError = err;
        }
        if (attempt < MAX_RETRIES) {
          await new Promise((r) => setTimeout(r, 1000 * attempt));
        }
      }
      if (lastError) {
        console.warn(
          "[AuthContext] Failed to sync user to backend after all retries.",
          lastError,
        );
      }
    }

    return u;
  };

  const signOut = async () => {
    const { signOutUser } = await import("@/lib/firebase");
    await signOutUser();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
