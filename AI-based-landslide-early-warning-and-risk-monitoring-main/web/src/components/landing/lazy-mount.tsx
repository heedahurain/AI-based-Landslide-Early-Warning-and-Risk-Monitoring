"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Render children only once they are near the viewport.
 *
 * The landing page carries three separate MapLibre instances. Mounting all of
 * them at once put three tile-fetching maps on one connection, and on a slow
 * link the hero, the one the reader is actually looking at, lost the race and
 * timed out. Deferring the lower two until they are approaching means the hero
 * gets the bandwidth first and the others are ready by the time they are seen.
 *
 * Once mounted, a child stays mounted. Tearing a map down and rebuilding it on
 * every scroll past would be worse than keeping it.
 */
export function LazyMount({
  children,
  rootMargin = "600px",
  className,
}: {
  children: ReactNode;
  /** How far ahead of the viewport to start. */
  rootMargin?: string;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (shown) return;
    const node = ref.current;
    if (!node) return;

    // No IntersectionObserver means an older browser, and a blank section
    // would be worse than an eager one.
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [shown, rootMargin]);

  return (
    <div ref={ref} className={className}>
      {shown ? children : null}
    </div>
  );
}
