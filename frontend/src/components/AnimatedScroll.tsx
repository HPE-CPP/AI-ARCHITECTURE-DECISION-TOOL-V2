"use client";
import React, { useRef, useEffect, useState } from "react";
import { m, useInView } from "framer-motion";

interface AnimatedTextProps {
  text: string;
  className?: string;
  el?: React.ElementType;
  once?: boolean;
}

export function AnimatedText({ text, className = "", el: Wrapper = "p" as any, once = true }: AnimatedTextProps) {
  const ref = useRef(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    setIsMobile(window.innerWidth < 768);
  }, []);

  const isInView = useInView(ref, { once, margin: "-10% 0px" });
  const lines = text.split("|").map(s => s.trim());

  if (isMobile) {
    return (
      <Wrapper ref={ref} className={className}>
        {text.replace(/\|/g, " ")}
      </Wrapper>
    );
  }

  return (
    <Wrapper ref={ref} className={className}>
      <span className="sr-only">{text.replace(/\|/g, " ")}</span>
      <span aria-hidden="true" className="block">
        {lines.map((line, lineIndex) => (
          <span key={`line-${lineIndex}`} className="block overflow-hidden pb-1">
            <m.span
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
            </m.span>
          </span>
        ))}
      </span>
    </Wrapper>
  );
}

export function AnimatedSection({
  children,
  className = "",
  delay = 0,
  once = true,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  once?: boolean;
}) {
  const ref = useRef(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    setIsMobile(window.innerWidth < 768);
  }, []);

  const isInView = useInView(ref, { once, margin: "-10% 0px", amount: 0.1 });

  // On mobile: render children immediately with no animation so they are
  // never hidden behind framer-motion's initial opacity:0 state.
  if (isMobile) {
    return (
      <div ref={ref} className={className}>
        {children}
      </div>
    );
  }

  return (
    <m.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{
        duration: 0.8,
        ease: [0.16, 1, 0.3, 1] as const,
        delay,
      }}
    >
      {children}
    </m.div>
  );
}
