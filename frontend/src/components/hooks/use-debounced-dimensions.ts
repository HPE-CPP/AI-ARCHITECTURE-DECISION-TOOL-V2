"use client";

import { useState, useCallback, useLayoutEffect, RefObject } from "react";

/**
 * useDimensions
 * 
 * Returns the width and height of a React Ref HTMLElement.
 * Updates are debounced to prevent excessive re-renders during resize events.
 * 
 * @param ref - React Ref of the element to measure
 * @param debounceDelay - Milliseconds to wait after last resize event before updating
 * @returns { width: number, height: number }
 */
export function useDimensions(ref: RefObject<HTMLElement | null>, debounceDelay = 100) {
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    const getDimensions = useCallback(() => {
        if (ref.current) {
            const { width, height } = ref.current.getBoundingClientRect();
            setDimensions({ width, height });
        }
    }, [ref]);

    useLayoutEffect(() => {
        if (!ref.current) return;

        // Initialize dimensions
        getDimensions();

        let timeoutId: NodeJS.Timeout;

        const resizeObserver = new ResizeObserver(() => {
            if (debounceDelay === 0) {
                getDimensions();
            } else {
                if (timeoutId) clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    getDimensions();
                }, debounceDelay);
            }
        });

        resizeObserver.observe(ref.current);

        return () => {
            resizeObserver.disconnect();
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [ref, getDimensions, debounceDelay]);

    return dimensions;
}
