'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { motion, MotionValue } from 'framer-motion';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

// --- Magnetic Component ---
const Magnetic = ({ children }: { children: React.ReactNode }) => {
    return <motion.div whileHover={{ scale: 1.05 }}>{children}</motion.div>;
};

// --- DottedSurface Component ---
type DottedSurfaceProps = {
    className?: string;
};

export function DottedSurface({ className }: DottedSurfaceProps) {
    const { theme } = useTheme();
    const containerRef = useRef<HTMLDivElement>(null);
    const sceneRef = useRef<{
        scene: THREE.Scene;
        renderer: THREE.WebGLRenderer;
        animationId: number;
    } | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        const SEPARATION = 140;
        const AMOUNTX = 50;
        const AMOUNTY = 50;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 1, 10000);
        camera.position.set(0, 300, 1000);

        // Renderer Setup
        const renderer = new THREE.WebGLRenderer({
            alpha: false, // Made false for complete opacity
            antialias: true
        });

        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(containerRef.current.offsetWidth, containerRef.current.offsetHeight);

        // Match the background of the Three.js canvas to the container inversion
        const bgColor = theme === 'dark' ? 0xffffff : 0x000000;
        renderer.setClearColor(bgColor, 1);

        containerRef.current.appendChild(renderer.domElement);

        const numParticles = AMOUNTX * AMOUNTY;
        const positions = new Float32Array(numParticles * 3);
        const colors = new Float32Array(numParticles * 3);

        // Dots: Black dots on White bg (Dark Mode), White dots on Black bg (Light Mode)
        const dotColor = theme === 'dark' ? new THREE.Color(0, 0, 0) : new THREE.Color(1, 1, 1);

        let i = 0;
        for (let ix = 0; ix < AMOUNTX; ix++) {
            for (let iy = 0; iy < AMOUNTY; iy++) {
                positions[i * 3] = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2;
                positions[i * 3 + 1] = 0;
                positions[i * 3 + 2] = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2;

                colors[i * 3] = dotColor.r;
                colors[i * 3 + 1] = dotColor.g;
                colors[i * 3 + 2] = dotColor.b;
                i++;
            }
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({
            size: 8,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
        });

        const particles = new THREE.Points(geometry, material);
        scene.add(particles);

        let count = 0;
        let animationId: number = 0;

        const animate = () => {
            animationId = requestAnimationFrame(animate);
            const positionAttribute = geometry.attributes.position;
            const posArray = positionAttribute.array as Float32Array;

            let i = 0;
            for (let ix = 0; ix < AMOUNTX; ix++) {
                for (let iy = 0; iy < AMOUNTY; iy++) {
                    posArray[i * 3 + 1] = Math.sin((ix + count) * 0.3) * 60 + Math.sin((iy + count) * 0.5) * 60;
                    i++;
                }
            }
            positionAttribute.needsUpdate = true;
            renderer.render(scene, camera);
            count += 0.04;
        };

        const handleResize = () => {
            if (!containerRef.current) return;
            const width = containerRef.current.offsetWidth;
            const height = containerRef.current.offsetHeight;
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
            renderer.setSize(width, height);
        };

        window.addEventListener('resize', handleResize);
        animate();

        sceneRef.current = { scene, renderer, animationId };

        return () => {
            window.removeEventListener('resize', handleResize);
            cancelAnimationFrame(animationId);
            geometry.dispose();
            material.dispose();
            renderer.dispose();
            if (containerRef.current?.contains(renderer.domElement)) {
                containerRef.current.removeChild(renderer.domElement);
            }
        };
    }, [theme]);

    return <div ref={containerRef} className={cn('absolute inset-0 pointer-events-none', className)} />;
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

    // Default to "dark" during SSR to match ThemeProvider's defaultTheme
    const currentTheme = mounted ? theme : "dark";

    return (
        <div className="w-full px-6 py-20">
            <motion.section
                style={{ opacity: ctaOpacity }}
                className={cn(
                    "relative max-w-6xl mx-auto min-h-[500px] flex flex-col justify-center items-center text-center",
                    "rounded-[3rem] md:rounded-[5rem] overflow-hidden isolate shadow-2xl border transition-colors duration-500",
                    // DARK MODE: White Section, Black Text
                    // LIGHT MODE: Black Section, White Text
                    currentTheme === 'dark'
                        ? "bg-white text-black border-black/5"
                        : "bg-black text-white border-white/10"
                )}
            >
                {/* BACKGROUND EFFECT */}
                <DottedSurface className="z-[-1]" />

                <div className="max-w-4xl mx-auto w-full px-8 py-20 flex flex-col items-center relative z-10">
                    <h2 className="text-5xl md:text-7xl font-black tracking-tighter mb-8 leading-[1.1] flex flex-col">
                        <span className="block overflow-hidden h-[1.2em] -mb-[0.1em]">
                            <motion.span
                                className="block"
                                initial={{ y: "100%" }}
                                whileInView={{ y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                            >
                                Stop Guessing.
                            </motion.span>
                        </span>
                        <span className="block overflow-hidden h-[1.2em]">
                            <motion.span
                                className="block opacity-30 text-[0.85em]"
                                initial={{ y: "100%" }}
                                whileInView={{ y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 1.2, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
                            >
                                Start Building.
                            </motion.span>
                        </span>
                    </h2>

                    <p className="text-lg md:text-xl opacity-60 mb-12 max-w-md mx-auto tracking-tight font-medium">
                        Transform your business needs into the right AI strategy with precision.
                    </p>

                    <Magnetic>
                        <Link href="/analyze">
                            <button className={cn(
                                "px-10 py-5 text-lg font-bold rounded-full transition-all duration-500 flex items-center gap-4 shadow-xl",
                                // Button flips to opposite of the section color
                                currentTheme === 'dark'
                                    ? "bg-black text-white hover:bg-zinc-800"
                                    : "bg-white text-black hover:bg-zinc-200"
                            )}>
                                Begin Analysis <ArrowRight size={22} />
                            </button>
                        </Link>
                    </Magnetic>
                </div>
            </motion.section>
        </div>
    );
}