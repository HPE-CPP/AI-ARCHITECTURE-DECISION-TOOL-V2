"use client";
import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface WelcomeBannerProps {
  firstName: string;
  visible: boolean;
  onComplete: () => void;
}

export function WelcomeBanner({ firstName, visible, onComplete }: WelcomeBannerProps) {
  useEffect(() => {
    if (visible) {
      const timer = setTimeout(onComplete, 2800);
      return () => clearTimeout(timer);
    }
  }, [visible, onComplete]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="welcome-banner"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.6 } }}
          transition={{ duration: 0.4 }}
          className="fixed inset-0 z-[200] flex items-center justify-center bg-[color:var(--surface)]/90 backdrop-blur-2xl"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 1.05, y: -20, transition: { duration: 0.6 } }}
            transition={{ type: "spring", stiffness: 260, damping: 22, delay: 0.1 }}
            className="text-center select-none"
          >
            {/* Wave emoji */}
            <motion.div
              animate={{ rotate: [0, 20, -10, 20, 0] }}
              transition={{ delay: 0.3, duration: 0.8 }}
              className="text-5xl mb-6"
            >
              👋
            </motion.div>

            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="text-[color:var(--text-secondary)] text-sm font-bold uppercase tracking-widest mb-2"
            >
              Welcome back
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35, type: "spring", stiffness: 220, damping: 20 }}
              className="text-4xl sm:text-6xl md:text-7xl font-black tracking-tighter text-[color:var(--text-primary)] leading-none"
            >
              {firstName}
            </motion.h1>

            {/* Animated underline */}
            <motion.div
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.55, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="h-0.5 bg-[color:var(--text-primary)] mt-4 mx-auto"
              style={{ width: "100%", transformOrigin: "left" }}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
