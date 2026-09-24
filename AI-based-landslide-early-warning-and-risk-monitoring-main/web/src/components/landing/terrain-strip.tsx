"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

/**
 * A full-bleed band of real terrain, used as section imagery.
 *
 * The reference designs for pages like this lean on large landscape
 * photography. We have no licensed photographs of the North East, and using
 * someone else's would be both a licensing problem and a small dishonesty on a
 * page about a specific place. So the imagery here is the actual elevation
 * model of the actual ground, rendered live: the ridges on screen are the
 * slopes the system monitors.
 *
 * The container is sized with h-full inside an absolute wrapper, because
 * maplibre-gl.css forces `position: relative` onto .maplibregl-map and would
 * otherwise collapse a Tailwind `absolute` element to zero height.
 */

const TERRAIN_TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

export function TerrainStrip({
  center,
  zoom = 9.5,
  pitch = 66,
  bearing = -30,
  drift = 0.006,
  className = "",
}: {
  center: [number, number];
  zoom?: number;
  pitch?: number;
  bearing?: number;
  /** Degrees of bearing per frame. Zero holds a still frame. */
  drift?: number;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let map: MapLibreMap | null = null;
    let raf = 0;
    let cancelled = false;
    let onScreen = true;
    let observer: IntersectionObserver | null = null;

    void (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        if (cancelled) return;

        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        map = new maplibregl.Map({
          container,
          style: BASEMAP_STYLE,
          center,
          zoom,
          pitch,
          bearing,
          interactive: false,
          attributionControl: false,
        });

        map.on("load", () => {
          if (!map || cancelled) return;
          map.addSource("dem", {
            type: "raster-dem",
            tiles: [TERRAIN_TILES],
            encoding: "terrarium",
            tileSize: 256,
            // Coarse for the same reason as the hero: these are background
            // bands, not an inspection tool.
            maxzoom: 9,
          });
          map.setTerrain({ source: "dem", exaggeration: 1.6 });
          map.addLayer({
            id: "hillshade",
            type: "hillshade",
            source: "dem",
            paint: {
              "hillshade-exaggeration": 0.55,
              "hillshade-shadow-color": "#05080f",
              "hillshade-highlight-color": "#3c5578",
            },
          });
          map.setSky({
            "sky-color": "#0b1728",
            "horizon-color": "#1d2b45",
            "fog-color": "#070b14",
            "fog-ground-blend": 0.5,
          });
          setReady(true);
        });

        if (!reduced && drift !== 0) {
          const tick = () => {
            if (onScreen && map) map.setBearing(map.getBearing() + drift);
            raf = requestAnimationFrame(tick);
          };
          raf = requestAnimationFrame(tick);
        }

        observer = new IntersectionObserver(
          (entries) => {
            onScreen = entries[0]?.isIntersecting ?? true;
          },
          { threshold: 0.02 },
        );
        observer.observe(container);
      } catch {
        // The gradient beneath remains the visual. Nothing breaks.
      }
    })();

    const resize = new ResizeObserver(() => map?.resize());
    resize.observe(container);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      observer?.disconnect();
      resize.disconnect();
      map?.remove();
    };
  }, [center, zoom, pitch, bearing, drift]);

  return (
    <div className={`absolute inset-0 overflow-hidden ${className}`} aria-hidden="true">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_120%,#1a2740_0%,#0d1424_45%,#070b14_100%)]" />
      <div
        className="absolute inset-0"
        style={{
          opacity: ready ? 1 : 0,
          transition: "opacity 1200ms cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
