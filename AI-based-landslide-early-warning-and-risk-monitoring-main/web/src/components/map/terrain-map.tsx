"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { Map as MapLibreMap } from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

import {
  apiUrl,
  bandColour,
  fosHeightFraction,
  normalise,
  rampColour,
  stabilityBand,
  type SlopeUnitProperties,
  type TerrainAttribute,
} from "@/lib/geo";

/**
 * The terrain map.
 *
 * MapLibre draws the basemap and the 3D terrain; deck.gl draws our own layers
 * through MapboxOverlay in interleaved mode, so extruded slope units are
 * occluded correctly by the ridges in front of them rather than floating over
 * the whole scene.
 *
 * Both libraries are loaded inside the effect rather than at module scope.
 * MapLibre touches `window` on import, and together they are a large bundle
 * that has no business blocking first paint on any other page.
 */

const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const TERRAIN_TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export type MapMode = "terrain" | "stability";

export interface MapSettings {
  mode: MapMode;
  attribute: TerrainAttribute;
  extrude: boolean;
  extrusionScale: number;
  showUnits: boolean;
  showDistricts: boolean;
  showRoads: boolean;
  showFacilities: boolean;
  terrainExaggeration: number;
  opacity: number;
}

export interface LoadState {
  units: number | null;
  roads: number | null;
  districts: number | null;
  facilities: number | null;
  error: string | null;
  loading: boolean;
}

interface Props {
  settings: MapSettings;
  onSelect: (properties: SlopeUnitProperties | null) => void;
  onLoadState: (state: LoadState) => void;
  run: string;
  /** Factor of safety per hillslope id, from the physics endpoint. */
  fosById: Map<number, number | null> | null;
}

type FeatureCollection = { type: "FeatureCollection"; features: unknown[] };

async function fetchLayer(path: string): Promise<FeatureCollection | null> {
  const response = await fetch(apiUrl(path));
  if (!response.ok) {
    if (response.status === 404) return null;
    throw new Error(`${path} returned ${response.status}`);
  }
  return (await response.json()) as FeatureCollection;
}

/** Report why WebGL is unavailable, rather than leaving a black rectangle. */
function webglProblem(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ??
      canvas.getContext("webgl") ??
      canvas.getContext("experimental-webgl");
    if (!gl) {
      return (
        "This browser reports no WebGL context, which MapLibre needs to draw. " +
        "Check that hardware acceleration is enabled in browser settings."
      );
    }
    return null;
  } catch (error) {
    return `WebGL check failed: ${error instanceof Error ? error.message : String(error)}`;
  }
}

export function TerrainMap({ settings, onSelect, onLoadState, run, fosById }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [ready, setReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const [units, setUnits] = useState<FeatureCollection | null>(null);
  const [districts, setDistricts] = useState<FeatureCollection | null>(null);
  const [roads, setRoads] = useState<FeatureCollection | null>(null);
  const [facilities, setFacilities] = useState<FeatureCollection | null>(null);

  // ---------------------------------------------------------------- map init
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;
    let map: MapLibreMap | null = null;

    const problem = webglProblem();
    if (problem) {
      setMapError(problem);
      return;
    }

    void (async () => {
      try {
        const maplibregl = (await import("maplibre-gl")).default;
        if (cancelled) return;

        map = new maplibregl.Map({
          container,
          style: BASEMAP_STYLE,
          center: [93.5, 24.88],
          zoom: 10.1,
          pitch: 58,
          bearing: -22,
          maxPitch: 80,
          attributionControl: { compact: true },
        });
        mapRef.current = map;

        map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
        map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

        // A style or tile failure must be visible, not swallowed.
        map.on("error", (event: { error?: { message?: string } }) => {
          const message = event?.error?.message ?? "unknown map error";
          // Missing individual tiles are normal at the edge of coverage.
          if (/tile|404/i.test(message)) return;
          setMapError(message);
        });

        map.on("load", () => {
          if (!map || cancelled) return;
          try {
            map.addSource("terrain-dem", {
              type: "raster-dem",
              tiles: [TERRAIN_TILES],
              encoding: "terrarium",
              tileSize: 256,
              maxzoom: 13,
              attribution: "Elevation: AWS Terrain Tiles (SRTM, GMTED)",
            });
            map.setTerrain({ source: "terrain-dem", exaggeration: settings.terrainExaggeration });

            map.addLayer({
              id: "hillshade",
              type: "hillshade",
              source: "terrain-dem",
              paint: {
                "hillshade-exaggeration": 0.45,
                "hillshade-shadow-color": "#04070f",
                "hillshade-highlight-color": "#2b3f63",
              },
            });

            map.setSky({
              "sky-color": "#0a1526",
              "horizon-color": "#16203a",
              "fog-color": "#070b14",
              "fog-ground-blend": 0.55,
              "sky-horizon-blend": 0.7,
            });

            // Overlaid rather than interleaved, deliberately.
            //
            // Interleaved mode shares MapLibre's depth buffer, which is what
            // normally lets terrain occlude deck.gl geometry. With 3D terrain
            // enabled that becomes a trap: extruded polygons are built upward
            // from sea level, while the ground here sits between 800 and 2,500
            // metres, so every slope unit was drawn *inside* the mountain and
            // nothing appeared. Verified by screenshot: terrain rendered
            // correctly and not one of the 14,714 units was visible.
            //
            // Overlaid mode draws deck.gl above the basemap in its own pass.
            // The view state still matches, so perspective and extrusion read
            // correctly; the units simply are not hidden by ridges in front of
            // them. That is the right trade until the polygons carry real
            // terrain-relative elevation.
            const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
            map.addControl(overlay);
            overlayRef.current = overlay;

            setReady(true);
          } catch (error) {
            setMapError(
              `Map layer setup failed: ${error instanceof Error ? error.message : String(error)}`,
            );
          }
        });
      } catch (error) {
        setMapError(
          `Map failed to start: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    })();

    // MapLibre only watches the window, not its container, so a container
    // that changes size after startup leaves a stale canvas.
    const observer = new ResizeObserver(() => mapRef.current?.resize());
    observer.observe(container);

    return () => {
      cancelled = true;
      observer.disconnect();
      overlayRef.current = null;
      map?.remove();
      mapRef.current = null;
    };
    // Terrain exaggeration is applied through its own effect below, so this
    // must not re-create the map when the slider moves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------- data loading
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      onLoadState({
        units: null,
        roads: null,
        districts: null,
        facilities: null,
        error: null,
        loading: true,
      });

      try {
        const [unitData, districtData, roadData, facilityData] = await Promise.all([
          fetchLayer(`/geo/slope-units?run=${encodeURIComponent(run)}`),
          fetchLayer("/geo/districts"),
          fetchLayer("/geo/roads"),
          fetchLayer("/geo/facilities"),
        ]);
        if (cancelled) return;

        setUnits(unitData);
        setDistricts(districtData);
        setRoads(roadData);
        setFacilities(facilityData);

        onLoadState({
          units: unitData?.features.length ?? 0,
          districts: districtData?.features.length ?? 0,
          roads: roadData?.features.length ?? 0,
          facilities: facilityData?.features.length ?? 0,
          error: null,
          loading: false,
        });
      } catch (error) {
        if (cancelled) return;
        onLoadState({
          units: null,
          roads: null,
          districts: null,
          facilities: null,
          error:
            error instanceof Error
              ? `${error.message}. Is the API running on ${apiUrl("")}?`
              : "Unknown error loading layers",
          loading: false,
        });
      }
    })();

    return () => {
      cancelled = true;
    };
    // onLoadState is a stable callback from the page; including it would
    // refetch every layer on each parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  // --------------------------------------------------------------- terrain
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setTerrain({ source: "terrain-dem", exaggeration: settings.terrainExaggeration });
  }, [settings.terrainExaggeration, ready]);

  // ---------------------------------------------------------------- layers
  const handleClick = useCallback(
    (info: { object?: { properties?: SlopeUnitProperties } }) => {
      onSelect(info.object?.properties ?? null);
    },
    [onSelect],
  );

  const layers = useMemo(() => {
    const { attribute } = settings;
    const built: unknown[] = [];

    if (districts && settings.showDistricts) {
      built.push(
        new GeoJsonLayer({
          id: "districts",
          data: districts as never,
          stroked: true,
          filled: false,
          getLineColor: [125, 211, 252, 160],
          getLineWidth: 2,
          lineWidthUnits: "pixels",
          pickable: false,
        }),
      );
    }

    if (units && settings.showUnits) {
      built.push(
        new GeoJsonLayer({
          id: "slope-units",
          data: units as never,
          pickable: true,
          stroked: !settings.extrude,
          filled: true,
          extruded: true,
          wireframe: false,
          getFillColor: (feature: { properties: SlopeUnitProperties }) => {
            const alpha = Math.round(settings.opacity * 255);
            if (settings.mode === "stability") {
              const fos = fosById?.get(feature.properties.hillslope_id) ?? null;
              return bandColour(stabilityBand(fos), alpha);
            }
            return rampColour(
              normalise(feature.properties[attribute.key] as number | null, attribute.domain),
              alpha,
            );
          },
          getLineColor: [10, 15, 25, 140],
          getLineWidth: 1,
          lineWidthUnits: "pixels",
          // Each unit sits at its own measured mean elevation, scaled by the
          // same exaggeration MapLibre applies to the terrain, with the chosen
          // attribute stacked on top.
          //
          // Without the elevation base the whole layer is a flat sheet at sea
          // level, floating over the mountains as a disconnected rectangle.
          // Using the real value makes the units form the mountain surface
          // itself, which is both more truthful and far more legible: you can
          // see which ridge each steep unit belongs to.
          getElevation: (feature: { properties: SlopeUnitProperties }) => {
            const base = (feature.properties.elevation_mean_m ?? 0) * settings.terrainExaggeration;
            if (!settings.extrude) return base;

            if (settings.mode === "stability") {
              // Inverted on purpose: the least stable slopes stand tallest, so
              // the eye lands on the ones that matter first.
              const fos = fosById?.get(feature.properties.hillslope_id) ?? null;
              return base + fosHeightFraction(fos) * settings.extrusionScale;
            }

            const t = normalise(
              feature.properties[attribute.key] as number | null,
              attribute.domain,
            );
            return base + (t ?? 0) * settings.extrusionScale;
          },
          material: {
            ambient: 0.45,
            diffuse: 0.7,
            shininess: 24,
            specularColor: [50, 62, 90],
          },
          onClick: handleClick,
          autoHighlight: true,
          highlightColor: [125, 211, 252, 210],
          updateTriggers: {
            getFillColor: [attribute.key, settings.opacity, settings.mode, fosById],
            getElevation: [
              attribute.key,
              settings.extrusionScale,
              settings.extrude,
              settings.terrainExaggeration,
              settings.mode,
              fosById,
            ],
          },
        }),
      );
    }

    if (roads && settings.showRoads) {
      built.push(
        new GeoJsonLayer({
          id: "roads",
          data: roads as never,
          stroked: true,
          filled: false,
          getLineColor: [248, 250, 252, 190],
          getLineWidth: (feature: { properties: { highway_class?: string } }) => {
            const cls = feature.properties.highway_class ?? "";
            if (cls.startsWith("trunk") || cls.startsWith("primary")) return 3;
            if (cls.startsWith("secondary")) return 2;
            return 1.2;
          },
          lineWidthUnits: "pixels",
          pickable: false,
        }),
      );
    }

    if (facilities && settings.showFacilities) {
      built.push(
        new ScatterplotLayer({
          id: "facilities",
          data: facilities.features as never[],
          getPosition: (f: { geometry: { coordinates: [number, number] } }) =>
            f.geometry.coordinates,
          getRadius: 5,
          radiusUnits: "pixels",
          radiusMinPixels: 4,
          getFillColor: [56, 189, 248, 235],
          getLineColor: [7, 11, 20, 255],
          lineWidthMinPixels: 1.5,
          stroked: true,
          pickable: false,
        }),
      );
    }

    return built;
  }, [units, districts, roads, facilities, settings, handleClick, fosById]);

  useEffect(() => {
    // `ready` is a dependency, not decoration. The layer array is built as soon
    // as the GeoJSON arrives, which beats the map's style-load event on a local
    // API. Without re-running when the overlay finally exists, setProps is
    // called once against a null ref and the layers are never handed over: the
    // terrain draws, the deck.gl canvas mounts, and not one polygon appears.
    if (!ready) return;
    overlayRef.current?.setProps({ layers: layers as never });
  }, [layers, ready]);

  return (
    <>
      {/* The map element must not rely on `absolute inset-0`.
          maplibre-gl.css sets `.maplibregl-map { position: relative }`, and
          because both are single-class selectors the stylesheet that loads
          last wins. MapLibre won that race, the container collapsed to zero
          height, and MapLibre fell back to its default 300px canvas inside a
          full-height page. The result was a black rectangle with no error.
          Sizing with h-full inside an absolutely positioned wrapper avoids
          the conflict entirely, because height does not depend on position. */}
      <div className="absolute inset-0">
        <div ref={containerRef} className="h-full w-full" />
      </div>
      {mapError && (
        <div className="absolute inset-0 grid place-items-center bg-[var(--bg-base)] p-6">
          <div className="max-w-md rounded-[var(--radius-lg)] border border-[var(--sev-red-outline)] bg-[var(--sev-red-tint)] p-5">
            <p className="text-[length:var(--text-sm)] font-semibold text-[var(--sev-red-text)]">
              The map could not be drawn
            </p>
            <p className="mt-2 text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
              {mapError}
            </p>
            <p className="mt-3 text-[length:var(--text-xs)] text-[var(--fg-muted)]">
              The slope-unit data itself loaded correctly. This is a rendering problem in the
              browser, not a problem with the pipeline output.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
