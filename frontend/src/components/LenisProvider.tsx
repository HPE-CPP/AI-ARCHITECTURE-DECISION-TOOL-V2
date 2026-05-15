"use client";
import { useEffect, type ReactNode } from "react";
import { LazyMotion, domMax } from "framer-motion";
import Lenis from "lenis";

export function LenisProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    let lenis: Lenis | null = null;
    let rafId: number;

    const init = () => {
      // Skip Lenis on mobile — native touch inertia is better and Lenis adds JS overhead
      if (window.innerWidth < 768) return;

      lenis = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: "vertical",
        gestureOrientation: "vertical",
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 2,
      });

      const raf = (time: number) => {
        lenis!.raf(time);
        rafId = requestAnimationFrame(raf);
      };
      rafId = requestAnimationFrame(raf);
    };

    // Defer so Lenis RAF loop never competes with the initial paint / LCP
    const timeout = setTimeout(init, 300);

    return () => {
      clearTimeout(timeout);
      if (rafId) cancelAnimationFrame(rafId);
      lenis?.destroy();
    };
  }, []);

  // LazyMotion loads only the domAnimation feature set (~45 KB) instead of
  // the full framer-motion bundle (~65 KB). All m.* components in the app
  // share this single context without re-loading the engine.
  return <LazyMotion features={domMax}>{children}</LazyMotion>;
}
