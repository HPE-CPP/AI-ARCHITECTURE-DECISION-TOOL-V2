"use client";
import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface TypewriterProps {
  text: string;
  speed?: number;
  delay?: number;
  className?: string;
  cursor?: boolean;
}

export function Typewriter({ text, speed = 50, delay = 0, className = "", cursor = true }: TypewriterProps) {
  const [displayedText, setDisplayedText] = useState("");
  const [started, setStarted] = useState(false);

  const [prevText, setPrevText] = useState(text);

  // FIX FE-007: When the `text` prop changes, reset animation state from scratch.
  // Using derived state pattern (calling setState during render) to avoid cascading renders.
  if (text !== prevText) {
    setPrevText(text);
    setDisplayedText("");
    setStarted(false);
  }

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (!started) {
      timeoutId = setTimeout(() => {
        setStarted(true);
      }, delay);
      return () => clearTimeout(timeoutId);
    }

    if (displayedText.length < text.length) {
      timeoutId = setTimeout(() => {
        setDisplayedText(text.slice(0, displayedText.length + 1));
      }, speed);
    }

    return () => clearTimeout(timeoutId);
  }, [displayedText, started, text, speed, delay]);

  return (
    <span className={className}>
      {displayedText}
      {cursor && (
        <motion.span
          animate={{ opacity: [1, 0] }}
          transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
          className="inline-block w-[0.1em] h-[1em] bg-[color:var(--text-primary)] ml-[0.1em] align-middle"
        />
      )}
    </span>
  );
}
