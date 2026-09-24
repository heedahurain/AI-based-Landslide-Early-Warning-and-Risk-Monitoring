"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

/**
 * The hero: a slowly orbiting 3D view of the North Eastern Region.
 *
 * Sources, both verified reachable on 2026-09-08 and neither needing a key:
 *  - Elevation: AWS Terrain Tiles, terrarium-encoded, from the public
 *    elevation-tiles-prod bucket.
 *  - Basemap: the CARTO Dark Matter GL style.
 *
 * This is real terrain, not an illustration. The ridges on screen are the
 * Patkai-Naga and eastern Himalayan slopes the system actually monitors, which
 * is why it earns its place as the first thing a judge sees.
 *
 * MapLibre is imported inside the effect rather than at module scope, because
 * it touches `window` on import and would otherwise break server rendering.
 * That also keeps roughly 800 KB out of the initial payload.
 *
 * Three things stop the orbit being a battery and performance problem: it
 * pauses when the hero scrolls out of view, it pauses when the tab is hidden,
 * and it never starts when the reader prefers reduced motion.
 */

const TERRAIN_TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

// Centred between the Meghalaya plateau and the Patkai ranges, so the opening
// frame contains real relief rather than the Brahmaputra floodplain.
const CENTER: [number, number] = [93.5, 24.9];
const ZOOM = 9.9;
const PITCH = 64;
const TERRAIN_EXAGGERATION = 1.8;
const DEGREES_PER_FRAME = 0.012;

export function HeroTerrain() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let map: MapLibreMap | null = null;
    let raf = 0;
    let cancelled = false;
    let visible = true;
    let onScreen = true;
    let observer: IntersectionObserver | null = null;

    const onVisibility = () => {
      visible = document.visibilityState === "visible";
    };

    void (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        if (cancelled) return;

        const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        map = new maplibregl.Map({
          container,
          style: BASEMAP_STYLE,
          center: CENTER,
          zoom: ZOOM,
          pitch: PITCH,
          bearing: -18,
          // The hero is decorative. The interactive map is the Phase 6 command
          // centre, so this one never captures page scroll or keyboard focus.
          interactive: false,
          attributionControl: { compact: true },
        });

        // Only a fatal error hides the terrain. The blanket handler that used
        // to sit here treated a single timed-out elevation tile as total
        // failure and permanently swapped the hero for its gradient, which is
        // exactly what happened on a slow connection: the map was fine, one
        // tile was late, and the whole hero went dark.
        map.on("error", (event: { error?: { message?: string; status?: number } }) => {
          const message = event?.error?.message ?? "";
          const status = event?.error?.status;
          const isTileIssue =
            /tile|timed out|timeout|abort|failed to fetch/i.test(message) ||
            status === 404 ||
            status === 0;
          if (!isTileIssue) setFailed(true);
        });

        map.on("load", () => {
          if (!map || cancelled) return;

          map.addSource("terrain-dem", {
            type: "raster-dem",
            tiles: [TERRAIN_TILES],
            encoding: "terrarium",
            tileSize: 256,
            // A compromise found by measurement. At maxzoom 13 the hero took
            // 30 to 60 seconds to appear on this connection; at 9 the relief
            // was too coarse to read at this framing. 11 renders legible
            // ridges without the tile storm.
            maxzoom: 11,
            attribution:
              "Elevation: AWS Terrain Tiles (SRTM, GMTED). Basemap: CARTO, OpenStreetMap contributors",
          });

          map.setTerrain({ source: "terrain-dem", exaggeration: TERRAIN_EXAGGERATION });

          map.addLayer({
            id: "hillshade",
            type: "hillshade",
            source: "terrain-dem",
            paint: {
              "hillshade-exaggeration": 0.72,
              "hillshade-shadow-color": "#03060d",
              "hillshade-highlight-color": "#54749f",
              "hillshade-accent-color": "#1b2b45",
            },
          });

          map.setSky({
            "sky-color": "#0a1526",
            "horizon-color": "#16203a",
            "fog-color": "#070b14",
            "fog-ground-blend": 0.6,
            "sky-horizon-blend": 0.7,
          });

          setReady(true);
        });

        if (!prefersReduced) {
          const tick = () => {
            if (visible && onScreen && map) {
              map.setBearing(map.getBearing() + DEGREES_PER_FRAME);
            }
            raf = requestAnimationFrame(tick);
          };
          raf = requestAnimationFrame(tick);
        }

        document.addEventListener("visibilitychange", onVisibility);

        observer = new IntersectionObserver(
          (entries) => {
            onScreen = entries[0]?.isIntersecting ?? true;
          },
          { threshold: 0.05 },
        );
        observer.observe(container);
      } catch {
        // A blocked CDN or an unsupported WebGL context must not take the page
        // down. The gradient below stays, and the copy still reads.
        setFailed(true);
      }
    })();

    // MapLibre watches the window, not its container, so a container that
    // changes size after startup would otherwise keep a stale canvas.
    const resizeObserver = new ResizeObserver(() => map?.resize());
    resizeObserver.observe(container);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      resizeObserver.disconnect();
      observer?.disconnect();
      map?.remove();
    };
  }, []);

  const showMap = ready && !failed;

  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* A terrain-toned gradient stands in until tiles paint, and remains the
          whole visual if the tile service is unreachable or WebGL is absent.
          The hero never shows an empty grey box. */}
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_120%,#16203a_0%,#0d1424_45%,#070b14_100%)]"
        style={{
          opacity: showMap ? 0 : 1,
          transition: "opacity 600ms cubic-bezier(0.16,1,0.3,1)",
        }}
      />
      {/* Sized with h-full inside an absolute wrapper. maplibre-gl.css forces
          `position: relative` onto .maplibregl-map, which cancels a Tailwind
          `absolute` on the same element and collapses it to zero height. */}
      <div
        className="absolute inset-0"
        style={{
          opacity: showMap ? 1 : 0,
          transition: "opacity 900ms cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        <div ref={containerRef} className="h-full w-full" />
      </div>
      {/* Legibility scrim. The headline sits over moving terrain, so its
          contrast has to come from the page rather than from luck. */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(7,11,20,0.92)_0%,rgba(7,11,20,0.62)_45%,rgba(7,11,20,0.25)_100%)]" />
      <div className="absolute inset-x-0 bottom-0 h-56 bg-[linear-gradient(to_bottom,transparent,var(--bg-base))]" />
      <div className="absolute inset-x-0 top-0 h-32 bg-[linear-gradient(to_top,transparent,rgba(7,11,20,0.75))]" />
    </div>
  );
}
