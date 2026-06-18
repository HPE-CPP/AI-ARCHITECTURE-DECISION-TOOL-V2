"use client";
import React, { useEffect, useRef, useState } from "react";
import { useTheme } from "./ThemeProvider";

export function GlobalBackground() {
  const vantaRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const vantaEffect = useRef<any>(null);
  const [mounted, setMounted] = useState(false);
  const { theme, resolvedTheme } = useTheme();

  const isDark = (resolvedTheme || theme) === "dark";

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    let cancelled = false;

    const initVanta = async () => {
      // Skip WebGL entirely on mobile — too expensive for CPU/GPU-constrained devices
      if (window.innerWidth < 768) return;
      if (cancelled || !vantaRef.current) return;

      const [THREE, vantaGlobe] = await Promise.all([
        import("three"),
        import("vanta/dist/vanta.globe.min"),
      ]);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const GLOBE = (vantaGlobe as any).default;

      if (cancelled || !vantaRef.current) return;

      if (vantaEffect.current) {
        vantaEffect.current.destroy();
        vantaEffect.current = null;
      }

      const effect = GLOBE({
        el: vantaRef.current,
        THREE,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200,
        minWidth: 200,
        scale: 1,
        scaleMobile: 1,
        color: isDark ? 0xffffff : 0x000000,
        color2: isDark ? 0xffffff : 0x000000,
        backgroundColor: isDark ? 0x000000 : 0xffffff,
        size: 1.2,
      });

      if (cancelled) {
        effect.destroy();
        return;
      }

      vantaEffect.current = effect;

      const renderer = effect.renderer;
      if (renderer) {
        renderer.setClearColor(0x000000, 0);
        renderer.domElement.style.background = "transparent";
        // Cap pixel ratio to reduce GPU load on high-DPI screens
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      }

      if (effect.scene) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        effect.scene.traverse((obj: any) => {
          if (obj.material) {
            if (obj.material.blending === null || obj.material.blending === undefined) {
              obj.material.blending = THREE.NormalBlending;
            }
            obj.material.transparent = true;
            obj.material.opacity = 0.2;
            if (obj.material.color) {
              obj.material.color.set(isDark ? 0xffffff : 0x000000);
            }
            obj.material.needsUpdate = true;
          }
        });
      }
    };

    // Defer init until the browser is idle so it never blocks LCP
    let idleId: number | ReturnType<typeof setTimeout>;
    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      idleId = (window as any).requestIdleCallback(initVanta, { timeout: 2000 });
    } else {
      idleId = setTimeout(initVanta, 200);
    }

    return () => {
      cancelled = true;
      if (typeof window !== "undefined" && "cancelIdleCallback" in window) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).cancelIdleCallback(idleId as number);
      } else {
        clearTimeout(idleId as ReturnType<typeof setTimeout>);
      }
      if (vantaEffect.current) {
        vantaEffect.current.destroy();
        vantaEffect.current = null;
      }
    };
  }, [mounted, isDark]);

  const bgStyle = mounted
    ? { backgroundColor: isDark ? "#000000" : "#ffffff" }
    : {};

  return (
    <div
      ref={vantaRef}
      className="fixed inset-0 z-[-10] w-full h-full transition-colors duration-500"
      style={bgStyle}
    />
  );
}
