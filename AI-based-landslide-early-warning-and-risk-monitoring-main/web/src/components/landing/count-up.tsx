"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * A figure that counts up once, the first time it scrolls into view.
 *
 * Two rules from the design direction apply here. Numerals use the mono font
 * with tabular figures so the width does not jump as digits change, and the
 * whole animation is skipped when the reader has asked for reduced motion,
 * showing the final value immediately rather than a fast version of the
 * animation.
 */
export interface CountUpProps {
  value: number;
  /** Rendered before the number, for example a currency or a plus sign. */
  prefix?: string;
  /** Rendered after the number, for example "mm" or "+". */
  suffix?: string;
  decimals?: number;
  durationMs?: number;
  className?: string;
}

export function CountUp({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  durationMs = 1400,
  className,
}: CountUpProps) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(reduced ? value : 0);
  const hasRun = useRef(false);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return;
    }

    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting || hasRun.current) return;
        hasRun.current = true;

        const start = performance.now();
        let raf = 0;

        const step = (now: number) => {
          const elapsed = now - start;
          const progress = Math.min(1, elapsed / durationMs);
          // Ease-out cubic, matching the --ease-out token's character.
          const eased = 1 - Math.pow(1 - progress, 3);
          setDisplay(value * eased);
          if (progress < 1) raf = requestAnimationFrame(step);
        };

        raf = requestAnimationFrame(step);
        observer.disconnect();
        return () => cancelAnimationFrame(raf);
      },
      { threshold: 0.4 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [value, durationMs, reduced]);

  return (
    <span ref={ref} data-numeric className={cn("tabular", className)}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}
