"use client";
import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import GLOBE from "vanta/dist/vanta.globe.min";
import { useTheme } from "./ThemeProvider";

export function GlobalBackground() {
  const vantaRef = useRef<HTMLDivElement>(null);
  const vantaEffect = useRef<any>(null);
  const [mounted, setMounted] = useState(false);
  const { theme, resolvedTheme } = useTheme();

  const isDark = (resolvedTheme || theme) === "dark";

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    // 🔥 Destroy previous instance
    if (vantaEffect.current) {
      vantaEffect.current.destroy();
      vantaEffect.current = null;
    }

    if (!vantaRef.current) return;

    const effect = GLOBE({
      el: vantaRef.current,
      THREE: THREE,

      mouseControls: true,
      touchControls: true,
      gyroControls: false,

      minHeight: 200,
      minWidth: 200,

      scale: 1,
      scaleMobile: 1,

      // ✅ COLORS
      color: isDark ? 0xffffff : 0x000000,
      color2: isDark ? 0xffffff : 0x000000,

      // 🔥 IMPORTANT: match theme instead of forcing black
      backgroundColor: isDark ? 0x000000 : 0xffffff,

      size: 1.2,
    });

    vantaEffect.current = effect;

    // =========================
    // 🔥 TRUE TRANSPARENCY FIX
    // =========================
    const renderer = effect.renderer;

    if (renderer) {
      // Make canvas truly transparent
      renderer.setClearColor(0x000000, 0);
      renderer.domElement.style.background = "transparent";

      renderer.setPixelRatio(window.devicePixelRatio);
    }

    // =========================
    // 🔥 FORCE MATERIAL COLORS
    // =========================
    if (effect.scene) {
      effect.scene.traverse((obj: any) => {
        if (obj.material) {
          // ✅ FIX: Ensure blending is valid (prevents console error)
          if (obj.material.blending === null || obj.material.blending === undefined) {
            obj.material.blending = THREE.NormalBlending;
          }

          obj.material.transparent = true;
          obj.material.opacity = isDark ? 0.2 : 0.2;

          if (obj.material.color) {
            obj.material.color.set(isDark ? 0xffffff : 0x000000);
          }

          obj.material.needsUpdate = true;
        }
      });
    }

    return () => {
      if (vantaEffect.current) {
        vantaEffect.current.destroy();
        vantaEffect.current = null;
      }
    };
  }, [mounted, isDark]);

  // ✅ THIS is the real background controller
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