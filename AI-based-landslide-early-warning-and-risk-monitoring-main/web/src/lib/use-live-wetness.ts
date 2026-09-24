"use client";

import { useEffect, useState } from "react";

import { apiUrl } from "@/lib/geo";

/**
 * The live profile wetness implied by observed soil moisture.
 *
 * Every screen that scores slope stability needs this same number. Before this
 * hook existed the overview computed its figures from the live value while the
 * map, roads and response screens each booted their own slider at a hardcoded
 * 0.75. The result was that navigating between two pages silently changed the
 * count of marginal slopes, the median factor of safety, the segments at risk
 * and the facilities affected, with nothing on screen to explain why. That
 * reads as fabricated data, which is worse than being wrong.
 *
 * So there is now exactly one source. Controls initialise from it, show it as a
 * labelled tick, and offer a way back to it. Scenario exploration is something
 * the user opts into, not the state the page boots in.
 */
export function useLiveWetness(): { live: number | null; loading: boolean } {
  const [live, setLive] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(apiUrl("/weather/forecast"));
        if (!response.ok) throw new Error(String(response.status));
        const payload = (await response.json()) as { suggested_wetness_fraction?: number };
        if (cancelled) return;
        const value = payload.suggested_wetness_fraction;
        setLive(typeof value === "number" ? value : null);
      } catch {
        // Leaving `live` null is the honest failure. Callers fall back to a
        // stated assumption and label it as such rather than implying the
        // number came from an observation.
        if (!cancelled) setLive(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { live, loading };
}

/** The value to use before the live reading arrives, stated openly wherever shown. */
export const ASSUMED_WETNESS_FALLBACK = 0.75;
