'use client';

import React, { useEffect, useRef, useState } from 'react';
import { m, MotionValue } from 'framer-motion';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

// --- Magnetic Component ---
const Magnetic = ({ children }: { children: React.ReactNode }) => {
    return <m.div whileHover={{ scale: 1.05 }}>{children}</m.div>;
};

// --- DottedSurface Component ---
type DottedSurfaceProps = {
    className?: string;
};

export function DottedSurface({ className }: DottedSurfaceProps) {
    const { theme } = useTheme();
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        let animationId = 0;
        let renderer: any = null;
        let geometry: any = null;
        let material: any = null;
        let cancelled = false;

        const init = async () => {
            // Skip heavy WebGL particles on mobile
            if (window.innerWidth < 768) return;
            const THREE = await import("three");
            if (cancelled || !container) return;

            const SEPARATION = 140;
            const AMOUNTX = 50;
            const AMOUNTY = 50;

            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 1, 10000);
            camera.position.set(0, 300, 1000);

            renderer = new THREE.WebGLRenderer({ alpha: false, antialias: true });
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
            renderer.setSize(container.offsetWidth, container.offsetHeight);

            const bgColor = theme === 'dark' ? 0xffffff : 0x000000;
            renderer.setClearColor(bgColor, 1);
            container.appendChild(renderer.domElement);

            const numParticles = AMOUNTX * AMOUNTY;
            const positions = new Float32Array(numParticles * 3);
            const colors = new Float32Array(numParticles * 3);

            const dotColor = theme === 'dark'
                ? new THREE.Color(0, 0, 0)
                : new THREE.Color(1, 1, 1);

            let i = 0;
            for (let ix = 0; ix < AMOUNTX; ix++) {
                for (let iy = 0; iy < AMOUNTY; iy++) {
                    positions[i * 3]     = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2;
                    positions[i * 3 + 1] = 0;
                    positions[i * 3 + 2] = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2;
                    colors[i * 3]     = dotColor.r;
                    colors[i * 3 + 1] = dotColor.g;
                    colors[i * 3 + 2] = dotColor.b;
                    i++;
                }
            }

            geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geometry.setAttribute('color',    new THREE.BufferAttribute(colors, 3));

            material = new THREE.PointsMaterial({
                size: 8,
                vertexColors: true,
                transparent: true,
                opacity: 0.8,
            });

            const particles = new THREE.Points(geometry, material);
            scene.add(particles);

            let count = 0;

            const animate = () => {
                if (cancelled) return;
                animationId = requestAnimationFrame(animate);
                const positionAttribute = geometry.attributes.position;
                const posArray = positionAttribute.array as Float32Array;

                let j = 0;
                for (let ix = 0; ix < AMOUNTX; ix++) {
                    for (let iy = 0; iy < AMOUNTY; iy++) {
                        posArray[j * 3 + 1] =
                            Math.sin((ix + count) * 0.3) * 60 +
                            Math.sin((iy + count) * 0.5) * 60;
                        j++;
                    }
                }
                positionAttribute.needsUpdate = true;
                renderer.render(scene, camera);
                count += 0.04;
            };

            const handleResize = () => {
                if (!container) return;
                const w = container.offsetWidth;
                const h = container.offsetHeight;
                camera.aspect = w / h;
                camera.updateProjectionMatrix();
                renderer.setSize(w, h);
            };

            window.addEventListener('resize', handleResize);
            animate();

            // Store resize handler so we can remove it on cleanup
            (renderer as any).__handleResize = handleResize;
        };

        // Defer so it never blocks LCP
        const timeout = setTimeout(init, 300);

        return () => {
            cancelled = true;
            clearTimeout(timeout);
            if (animationId) cancelAnimationFrame(animationId);
            if (renderer?.__handleResize) {
                window.removeEventListener('resize', renderer.__handleResize);
            }
            geometry?.dispose();
            material?.dispose();
            if (renderer) {
                renderer.dispose();
                if (container.contains(renderer.domElement)) {
                    container.removeChild(renderer.domElement);
                }
            }
        };
    }, [theme]);

    return (
        <div
            ref={containerRef}
            className={cn('absolute inset-0 pointer-events-none', className)}
        />
    );
}

// --- Main CTA Component ---
interface ReadyToArchitectProps {
    ctaOpacity?: MotionValue<number> | number;
}

export function ReadyToArchitect({ ctaOpacity }: ReadyToArchitectProps) {
    const { theme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const currentTheme = mounted ? theme : "dark";

    return (
        <div className="w-full px-4 md:px-6 py-12 md:py-20">
            <m.section
                style={{ opacity: ctaOpacity }}
                className={cn(
                    "relative max-w-6xl mx-auto min-h-[600px] md:min-h-[500px] flex flex-col justify-center items-center text-center",
                    "rounded-[2.5rem] md:rounded-[5rem] overflow-hidden isolate shadow-2xl border transition-colors duration-500",
                    currentTheme === 'dark'
                        ? "bg-white text-black border-black/5"
                        : "bg-black text-white border-white/10"
                )}
            >
                <DottedSurface className="z-[-1]" />

                <div className="max-w-4xl mx-auto w-full px-6 md:px-8 py-16 md:py-20 flex flex-col items-center relative z-10">
                    <h2 className="text-5xl md:text-7xl font-black tracking-tighter mb-6 md:mb-8 leading-[1.1] flex flex-col">
                        <span className="block overflow-hidden h-auto md:h-[1.2em] py-1">
                            <m.span
                                className="block"
                                initial={{ y: "100%" }}
                                whileInView={{ y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                            >
                                Stop Guessing.
                            </m.span>
                        </span>

                        <span className="block overflow-hidden h-auto md:h-[1.2em] py-1">
                            <m.span
                                className="block opacity-30 text-[0.85em]"
                                initial={{ y: "100%" }}
                                whileInView={{ y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 1.2, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
                            >
                                Start Building.
                            </m.span>
                        </span>
                    </h2>

                    <p className="text-base md:text-xl opacity-60 mb-10 md:mb-12 max-w-xs md:max-w-md mx-auto tracking-tight font-medium leading-relaxed">
                        Transform your business needs into the right AI strategy with precision.
                    </p>

                    <Magnetic>
                        <Link href="/projects">
                            <button className={cn(
                                "px-8 md:px-10 py-4 md:py-5 text-base md:text-lg font-bold rounded-full transition-all duration-500 flex items-center gap-3 md:gap-4 shadow-xl active:scale-95",
                                currentTheme === 'dark'
                                    ? "bg-black text-white hover:bg-zinc-800"
                                    : "bg-white text-black hover:bg-zinc-200"
                            )}>
                                Begin Analysis{" "}
                                <ArrowRight size={22} />
                            </button>
                        </Link>
                    </Magnetic>
                </div>
            </m.section>
        </div>
    );
}
