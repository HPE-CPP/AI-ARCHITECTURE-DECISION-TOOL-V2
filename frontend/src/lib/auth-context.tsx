"use client";
import React, { createContext, useContext, useEffect, useState } from "react";
import { auth, onAuthStateChanged, signInWithGoogle, signOutUser, User } from "@/lib/firebase";
import { getApiBase } from "@/lib/api-base";

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
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signIn = async () => {
    const u = await signInWithGoogle();
    setUser(u);
    
    // FIX FE-004: Backend sync with retry — do NOT fire-and-forget silently
    // If all retries fail, the user is warned. Projects will fail with FK errors otherwise.
    if (u) {
      const payload = {
        uid: u.uid,
        email: u.email,
        displayName: u.displayName,
        photoURL: u.photoURL,
      };
      const apiUrl = getApiBase();
      const MAX_RETRIES = 3;
      let lastError: unknown;
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          const res = await fetch(`${apiUrl}/api/v1/users/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (res.ok) break; // success
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
          "Projects created by this user may fail due to missing DB record.",
          lastError,
        );
      }
    }
    
    return u;
  };

  const signOut = async () => {
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
