"use client";
import React, { createContext, useContext, useEffect, useState } from "react";
import { auth, onAuthStateChanged, signInWithGoogle, signOutUser, User } from "@/lib/firebase";

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
