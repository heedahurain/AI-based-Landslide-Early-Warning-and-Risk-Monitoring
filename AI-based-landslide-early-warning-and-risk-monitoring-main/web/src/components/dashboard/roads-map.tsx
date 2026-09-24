"use client";

import { useEffect, useRef, useState } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { Map as MapLibreMap } from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

import { bandColour } from "@/lib/geo";

/**
 * The road network, coloured by blockage probability.
 *
 * The table on this screen answers "which segment first"; this map answers
 * "where, and next to what". A ranked list of "unnamed road" rows means
 * nothing on its own, because most segments in OpenStreetMap here genuinely
 * carry no name tag. Seeing them against real terrain, and seeing which ones
 * cluster near a village or a facility, is what makes the ranking legible.
 */

const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

type FeatureCollection = { type: "FeatureCollection"; features: unknown[] };

export function RoadsMap({ data }: { data: FeatureCollection | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let map: MapLibreMap | null = null;

    void (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled) return;

      map = new maplibregl.Map({
        container,
        style: BASEMAP_STYLE,
        center: [93.5, 24.9],
        zoom: 9.6,
        pitch: 0,
        attributionControl: { compact: true },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

      map.on("load", () => {
        if (!map || cancelled) return;
        const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
        map.addControl(overlay);
        overlayRef.current = overlay;
        setReady(true);
      });
    })();

    const resize = new ResizeObserver(() => map?.resize());
    resize.observe(container);

    return () => {
      cancelled = true;
      resize.disconnect();
      overlayRef.current = null;
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    // Data commonly arrives before the map finishes loading and creates the
    // overlay, since the fetch and the tile-style load race independently. Without
    // `ready` as a dependency, setProps runs once against a null ref and the
    // layer is never handed over once the overlay does exist.
    if (!data || !ready) return;
    const layer = new GeoJsonLayer({
      id: "roads-risk",
      data: data as never,
      pickable: true,
      stroked: true,
      filled: false,
      getLineColor: (feature: { properties: { blockage_probability: number } }) =>
        bandColour(
          feature.properties.blockage_probability >= 0.66
            ? "unstable"
            : feature.properties.blockage_probability >= 0.33
              ? "marginal"
              : "stable",
          230,
        ),
      getLineWidth: (feature: { properties: { highway_class?: string } }) => {
        const cls = feature.properties.highway_class ?? "";
        if (cls.startsWith("trunk") || cls.startsWith("primary")) return 4;
        if (cls.startsWith("secondary")) return 3;
        return 1.6;
      },
      lineWidthUnits: "pixels",
      updateTriggers: { getLineColor: [data] },
    });
    overlayRef.current?.setProps({ layers: [layer] });
  }, [data, ready]);

  return (
    <div className="relative h-80 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border-subtle)]">
      {/* h-full inside an absolute wrapper, not `absolute inset-0` on the map
          element itself. maplibre-gl.css forces `position: relative` onto
          .maplibregl-map, which cancels a Tailwind `absolute` class on the
          same element and collapses it to MapLibre's ~300px fallback height.
          Hit this exact bug twice already on the hero and the risk map. */}
      <div className="absolute inset-0">
        <div ref={containerRef} className="h-full w-full" />
      </div>
      <div className="pointer-events-none absolute bottom-2 left-2 flex items-center gap-3 rounded-[var(--radius-md)] bg-[var(--bg-surface)]/90 px-2.5 py-1.5 text-[length:var(--text-2xs)] text-[var(--fg-secondary)] backdrop-blur">
        <Swatch tone="stable" label="Low" />
        <Swatch tone="marginal" label="Elevated" />
        <Swatch tone="unstable" label="High" />
      </div>
    </div>
  );
}

function Swatch({ tone, label }: { tone: "stable" | "marginal" | "unstable"; label: string }) {
  const [r, g, b] = bandColour(tone, 255);
  return (
    <span className="flex items-center gap-1">
      <span
        aria-hidden="true"
        className="h-0.5 w-4"
        style={{ background: `rgb(${r} ${g} ${b})` }}
      />
      {label}
    </span>
  );
}
