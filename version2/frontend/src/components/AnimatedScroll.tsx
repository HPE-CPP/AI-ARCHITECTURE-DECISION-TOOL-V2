"use client";
import React, { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface AnimatedTextProps {
  text: string;
  className?: string;
  el?: React.ElementType;
  once?: boolean;
}

export function AnimatedText({ text, className = "", el: Wrapper = "p" as any, once = false }: AnimatedTextProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, margin: "-10% 0px" });
  const lines = text.split("|").map(s => s.trim());

  return (
    <Wrapper ref={ref} className={className}>
      <span className="sr-only">{text.replace(/\|/g, " ")}</span>
      <span aria-hidden="true" className="block">
        {lines.map((line, lineIndex) => (
          <span key={`line-${lineIndex}`} className="block overflow-hidden pb-1">
            <motion.span
              className="block"
              initial={{ y: "150%", opacity: 0, rotate: 2 }}
              animate={
                isInView
                  ? { y: 0, opacity: 1, rotate: 0 }
                  : { y: "150%", opacity: 0, rotate: 2 }
              }
              transition={{
                duration: 0.8,
                ease: [0.16, 1, 0.3, 1] as const,
                delay: lineIndex * 0.1,
              }}
            >
              {line}
            </motion.span>
          </span>
        ))}
      </span>
    </Wrapper>
  );
}

export function AnimatedSection({ children, className = "", delay = 0, once = false }: { children: React.ReactNode, className?: string, delay?: number, once?: boolean }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, margin: "-10% 0px", amount: 0.1 });

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 20 }} // Removed initial blur
      animate={
        isInView
          ? { opacity: 1, y: 0 }
          : { opacity: 0, y: 20 }
      }
      transition={{
        duration: 0.8,
        ease: [0.16, 1, 0.3, 1] as const,
        delay: delay,
      }}
    >
      {children}
    </motion.div>
  );
}