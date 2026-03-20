"use client"

import React, { useCallback, useMemo, useRef, useState, useEffect } from "react"
import { motion, useAnimationControls } from "framer-motion"
import { v4 as uuidv4 } from "uuid"
import { cn } from "@/lib/utils"

function useDimensions(ref: React.RefObject<HTMLDivElement | null>) {
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 })

    useEffect(() => {
        if (!ref.current) return
        const observeTarget = ref.current
        const resizeObserver = new ResizeObserver((entries) => {
            entries.forEach((entry) => {
                setDimensions({
                    width: entry.contentRect.width,
                    height: entry.contentRect.height,
                })
            })
        })
        resizeObserver.observe(observeTarget)
        return () => resizeObserver.unobserve(observeTarget)
    }, [ref])

    return dimensions
}

interface PixelTrailProps {
    pixelSize?: number
    fadeDuration?: number
    delay?: number
    className?: string
    pixelClassName?: string
    children?: React.ReactNode
}

export const PixelTrail: React.FC<PixelTrailProps> = ({
    pixelSize = 80,
    fadeDuration = 0,
    delay = 1200,
    className,
    pixelClassName,
    children,
}) => {
    const containerRef = useRef<HTMLDivElement>(null)
    const dimensions = useDimensions(containerRef)
    const trailId = useRef(uuidv4())

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLDivElement>) => {
            if (!containerRef.current) return

            const rect = containerRef.current.getBoundingClientRect()
            const x = Math.floor((e.clientX - rect.left) / pixelSize)
            const y = Math.floor((e.clientY - rect.top) / pixelSize)

            const pixelElement = document.getElementById(
                `${trailId.current}-pixel-${x}-${y}`
            )
            if (pixelElement) {
                const animatePixel = (pixelElement as any).__animatePixel
                if (animatePixel) animatePixel()
            }
        },
        [pixelSize]
    )

    const columns = useMemo(
        () => (dimensions.width ? Math.ceil(dimensions.width / pixelSize) : 0),
        [dimensions.width, pixelSize]
    )
    const rows = useMemo(
        () => (dimensions.height ? Math.ceil(dimensions.height / pixelSize) : 0),
        [dimensions.height, pixelSize]
    )

    return (
        <div
            ref={containerRef}
            className={cn("relative w-full h-full", className)}
            onMouseMove={handleMouseMove}
        >
            {/* 1. Content Layer */}
            <div className="relative z-10 w-full h-full">
                {children}
            </div>

            {/* 2. Inversion Overlay Layer */}
            {/* We use z-50 and pointer-events-none so it sits ON TOP of text but doesn't block clicks */}
            <div className="absolute inset-0 w-full h-full pointer-events-none z-50 overflow-hidden">
                {Array.from({ length: rows }).map((_, rowIndex) => (
                    <div key={rowIndex} className="flex">
                        {Array.from({ length: columns }).map((_, colIndex) => (
                            <PixelDot
                                key={`${colIndex}-${rowIndex}`}
                                id={`${trailId.current}-pixel-${colIndex}-${rowIndex}`}
                                size={pixelSize}
                                fadeDuration={fadeDuration}
                                delay={delay}
                                className={pixelClassName}
                            />
                        ))}
                    </div>
                ))}
            </div>
        </div>
    )
}

interface PixelDotProps {
    id: string
    size: number
    fadeDuration: number
    delay: number
    className?: string
}

const PixelDot: React.FC<PixelDotProps> = React.memo(
    ({ id, size, fadeDuration, delay, className }) => {
        const controls = useAnimationControls()
        const timeoutRef = useRef<NodeJS.Timeout | null>(null)

        const animatePixel = useCallback(() => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current)

            // 1. Appear instantly
            controls.set({ opacity: 1 })

            // 2. Wait for the 'delay' duration (the "stay" time)
            timeoutRef.current = setTimeout(() => {
                // 3. Vanish over the 'fadeDuration'
                controls.start({
                    opacity: 0,
                    transition: {
                        duration: fadeDuration / 1000,
                        ease: "linear"
                    },
                })
            }, delay)
        }, [controls, fadeDuration, delay])

        const ref = useCallback(
            (node: HTMLDivElement | null) => {
                if (node) {
                    ; (node as any).__animatePixel = animatePixel
                }
            },
            [animatePixel]
        )

        return (
            <motion.div
                id={id}
                ref={ref}
                className={cn("pointer-events-none", className)}
                style={{
                    width: `${size}px`,
                    height: `${size}px`,
                }}
                initial={{ opacity: 0 }}
                animate={controls}
            />
        )
    }
)

PixelDot.displayName = "PixelDot"