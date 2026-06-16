"use client";
import React, { useState } from "react";
import { Share2, Check, Copy, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ShareButtonProps {
  analysisId: string;
}

export default function ShareButton({ analysisId }: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const shareUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/r/${analysisId}`
      : `/r/${analysisId}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback for browsers that block clipboard
      const input = document.createElement("input");
      input.value = shareUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--background)] transition-colors text-sm font-semibold text-[var(--text-primary)]"
      >
        <Share2 size={15} />
        Share
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-12 z-50 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-2xl shadow-xl p-4"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-bold text-[var(--text-primary)]">Share this analysis</p>
              <button
                onClick={() => setOpen(false)}
                className="w-6 h-6 rounded-full flex items-center justify-center hover:bg-[var(--background)] transition-colors"
              >
                <X size={13} className="text-[var(--text-secondary)]" />
              </button>
            </div>

            <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">
              Anyone with this link can view the full results — no login required.
            </p>

            {/* URL row */}
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-[var(--background)] border border-[var(--border)] mb-3">
              <span className="text-xs text-[var(--text-secondary)] truncate flex-1 font-mono">
                {shareUrl}
              </span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--text-primary)] text-[var(--background)] text-xs font-bold hover:opacity-90 transition-opacity flex-shrink-0"
              >
                {copied ? (
                  <><Check size={11} /> Copied!</>
                ) : (
                  <><Copy size={11} /> Copy</>
                )}
              </button>
            </div>

            {/* Note */}
            <p className="text-[10px] text-[var(--text-secondary)] opacity-60 leading-relaxed">
              The shared page is read-only. Sliders, chat, and edit features are not available to viewers.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
