"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Layers, Loader2, Mountain, X } from "lucide-react";

import {
  BAND_LABEL,
  TERRAIN_ATTRIBUTES,
  apiUrl,
  bandCss,
  compassPoint,
  formatAttribute,
  normalise,
  rampCss,
  stabilityBand,
  type FactorOfSafetyResponse,
  type LithologyOption,
  type SlopeUnitProperties,
} from "@/lib/geo";
import { PhysicsPanel } from "@/components/map/physics-panel";
import { ASSUMED_WETNESS_FALLBACK, useLiveWetness } from "@/lib/use-live-wetness";
import { cn } from "@/lib/utils";
import type { LoadState, MapSettings } from "@/components/map/terrain-map";

const TerrainMap = dynamic(() => import("@/components/map/terrain-map").then((m) => m.TerrainMap), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 grid place-items-center bg-[var(--bg-base)]">
      <div className="flex items-center gap-2 text-[length:var(--text-sm)] text-[var(--fg-muted)]">
        <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        Loading map engine
      </div>
    </div>
  ),
});

const RUN = "noney_30m";

export function MapWorkspace() {
  const [settings, setSettings] = useState<MapSettings>({
    mode: "stability",
    attribute: TERRAIN_ATTRIBUTES[0]!,
    extrude: true,
    extrusionScale: 350,
    showUnits: true,
    showDistricts: true,
    showRoads: true,
    showFacilities: true,
    terrainExaggeration: 1.5,
    opacity: 0.82,
  });
  const [selected, setSelected] = useState<SlopeUnitProperties | null>(null);
  const [load, setLoad] = useState<LoadState>({
    units: null,
    districts: null,
    roads: null,
    facilities: null,
    error: null,
    loading: true,
  });
  const [panelOpen, setPanelOpen] = useState(true);

  const [lithologies, setLithologies] = useState<LithologyOption[]>([]);
  const [lithology, setLithology] = useState<string | null>(null);
  // Null means "follow the live reading"; a number means someone has chosen a
  // scenario. Keeping the distinction is what stops this map from quietly
  // disagreeing with the overview about how many slopes are marginal.
  const { live: liveWetness, loading: wetnessLoading } = useLiveWetness();
  const [wetnessOverride, setWetnessOverride] = useState<number | null>(null);
  const wetness = wetnessOverride ?? liveWetness ?? ASSUMED_WETNESS_FALLBACK;
  const [physics, setPhysics] = useState<FactorOfSafetyResponse | null>(null);
  const [physicsLoading, setPhysicsLoading] = useState(false);

  // The parameter table, fetched once. It is published by the API so the
  // numbers behind any factor of safety on screen are inspectable.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(apiUrl("/risk/lithology-classes"));
        if (!response.ok) return;
        const options = (await response.json()) as LithologyOption[];
        if (cancelled) return;
        setLithologies(options);
        setLithology((current) => current ?? options[0]?.key ?? null);
      } catch {
        // The terrain view still works without the physics layer.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Recompute when the material or the wetness changes. Debounced, because the
  // wetness control is a slider and every intermediate value would otherwise
  // become a request.
  useEffect(() => {
    if (settings.mode !== "stability" || !lithology) return;
    let cancelled = false;
    setPhysicsLoading(true);

    const timer = setTimeout(() => {
      void (async () => {
        try {
          const url = apiUrl(
            `/risk/factor-of-safety?run=${encodeURIComponent(RUN)}` +
              `&lithology=${encodeURIComponent(lithology)}&wetness=${wetness}`,
          );
          const response = await fetch(url);
          if (!response.ok) throw new Error(String(response.status));
          const payload = (await response.json()) as FactorOfSafetyResponse;
          if (!cancelled) setPhysics(payload);
        } catch {
          if (!cancelled) setPhysics(null);
        } finally {
          if (!cancelled) setPhysicsLoading(false);
        }
      })();
    }, 180);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [lithology, wetness, wetnessLoading, settings.mode]);

  // Keyed by hillslope id so the map can look up a unit in constant time.
  const fosById = useMemo(() => {
    if (!physics) return null;
    const map = new Map<number, number | null>();
    physics.hillslope_ids.forEach((id, index) => map.set(id, physics.fos[index] ?? null));
    return map;
  }, [physics]);

  const selectedFos = selected && fosById ? (fosById.get(selected.hillslope_id) ?? null) : null;

  const onLoadState = useCallback((state: LoadState) => setLoad(state), []);
  const onSelect = useCallback((p: SlopeUnitProperties | null) => setSelected(p), []);

  const update = <K extends keyof MapSettings>(key: K, value: MapSettings[K]) =>
    setSettings((s) => ({ ...s, [key]: value }));

  const legendStops = useMemo(() => [0, 0.25, 0.5, 0.75, 1], []);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-[var(--bg-base)]">
      <TerrainMap
        settings={settings}
        onSelect={onSelect}
        onLoadState={onLoadState}
        run={RUN}
        fosById={fosById}
      />

      {/* A compact statement of what is on screen, in the same position as
          before but sized as a chip rather than a full-width alarm. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[var(--z-topbar)] flex justify-center p-3">
        <p className="pointer-events-auto rounded-[var(--radius-full)] border border-[var(--border-default)] bg-[var(--bg-surface)]/92 px-3 py-1 text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-secondary)] uppercase backdrop-blur">
          {settings.mode === "stability"
            ? "Physics layer · factor of safety at the live profile wetness"
            : "Measured terrain · no model trained"}
        </p>
      </div>

      {/* ------------------------------------------------------ left panel */}
      <div className="absolute top-3 left-3 z-[var(--z-panel)] flex max-h-[calc(100dvh-1.5rem)] w-[19rem] flex-col">
        <div className="overflow-y-auto rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)]/95 shadow-[var(--shadow-3)] backdrop-blur">
          <button
            type="button"
            onClick={() => setPanelOpen((o) => !o)}
            aria-expanded={panelOpen}
            className="flex w-full items-center gap-2 border-b border-[var(--border-subtle)] px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
          >
            <Mountain aria-hidden="true" className="size-4 text-[var(--sev-cyan-text)]" />
            <span className="text-[length:var(--text-sm)] font-semibold">
              Noney and Tupul, Manipur
            </span>
            <Layers aria-hidden="true" className="ml-auto size-4 text-[var(--fg-muted)]" />
          </button>

          {panelOpen && (
            <div className="space-y-5 p-4">
              {/* -------------------------------------------- run stats */}
              <div className="grid grid-cols-2 gap-2">
                <Stat label="Slope units" value={load.units} />
                <Stat label="Roads" value={load.roads} />
                <Stat label="Districts" value={load.districts} />
                <Stat label="Facilities" value={load.facilities} />
              </div>

              {load.loading && (
                <p className="flex items-center gap-2 text-[length:var(--text-xs)] text-[var(--fg-muted)]">
                  <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                  Loading layers from the API
                </p>
              )}
              {load.error && (
                <p className="rounded-[var(--radius-md)] border border-[var(--sev-red-outline)] bg-[var(--sev-red-tint)] p-2 text-[length:var(--text-xs)] text-[var(--sev-red-text)]">
                  {load.error}
                </p>
              )}

              {/* ------------------------------------------- mode switch */}
              <div
                role="radiogroup"
                aria-label="Map mode"
                className="grid grid-cols-2 gap-1 rounded-[var(--radius-md)] bg-[var(--bg-elevated)] p-1"
              >
                {(
                  [
                    ["stability", "Stability"],
                    ["terrain", "Terrain"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={settings.mode === value}
                    onClick={() => update("mode", value)}
                    className={cn(
                      "rounded-[var(--radius-sm)] px-2 py-1.5 text-[length:var(--text-sm)] font-medium",
                      "transition-colors duration-[var(--duration-fast)]",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                      settings.mode === value
                        ? "bg-[var(--bg-surface)] text-[var(--fg-primary)]"
                        : "text-[var(--fg-muted)] hover:text-[var(--fg-primary)]",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {settings.mode === "stability" && (
                <PhysicsPanel
                  lithologies={lithologies}
                  selected={lithology}
                  onSelectLithology={setLithology}
                  wetness={wetness}
                  onWetnessChange={setWetnessOverride}
                  liveWetness={liveWetness}
                  result={physics}
                  loading={physicsLoading}
                />
              )}

              {settings.mode === "terrain" && (
                <fieldset>
                  <legend className="mb-2 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
                    Colour and height by
                  </legend>
                  <div className="grid gap-1">
                    {TERRAIN_ATTRIBUTES.map((attribute) => (
                      <button
                        key={attribute.key}
                        type="button"
                        onClick={() => update("attribute", attribute)}
                        aria-pressed={settings.attribute.key === attribute.key}
                        className={cn(
                          "rounded-[var(--radius-md)] px-2.5 py-1.5 text-left text-[length:var(--text-sm)]",
                          "transition-colors duration-[var(--duration-fast)]",
                          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                          settings.attribute.key === attribute.key
                            ? "bg-[var(--bg-elevated)] text-[var(--fg-primary)]"
                            : "text-[var(--fg-secondary)] hover:bg-[var(--bg-elevated)]",
                        )}
                      >
                        {attribute.label}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[length:var(--text-xs)] leading-[var(--leading-relaxed)] text-[var(--fg-muted)]">
                    {settings.attribute.description}
                  </p>

                  {/* ---------------------------------------------- legend */}
                  <div className="mt-4">
                    <div
                      className="h-2.5 w-full rounded-[var(--radius-full)]"
                      style={{
                        background: `linear-gradient(to right, ${legendStops
                          .map((t) => rampCss(t))
                          .join(", ")})`,
                      }}
                    />
                    <div className="mt-1 flex justify-between text-[length:var(--text-2xs)] text-[var(--fg-muted)]">
                      <span data-numeric>
                        {settings.attribute.domain[0]}
                        {settings.attribute.unit}
                      </span>
                      <span data-numeric>
                        {settings.attribute.domain[1]}
                        {settings.attribute.unit}
                      </span>
                    </div>
                  </div>
                </fieldset>
              )}

              {/* ------------------------------------------------ toggles */}
              <fieldset className="grid gap-1.5">
                <legend className="mb-1 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
                  Layers
                </legend>
                <Toggle
                  label="Slope units"
                  checked={settings.showUnits}
                  onChange={(v) => update("showUnits", v)}
                />
                <Toggle
                  label="District boundaries"
                  checked={settings.showDistricts}
                  onChange={(v) => update("showDistricts", v)}
                />
                <Toggle
                  label="Roads"
                  checked={settings.showRoads}
                  onChange={(v) => update("showRoads", v)}
                />
                <Toggle
                  label="Facilities"
                  checked={settings.showFacilities}
                  onChange={(v) => update("showFacilities", v)}
                />
                <Toggle
                  label="Add attribute height"
                  checked={settings.extrude}
                  onChange={(v) => update("extrude", v)}
                />
              </fieldset>

              {/* ------------------------------------------------ sliders */}
              <div className="grid gap-3">
                <Slider
                  label="Attribute height"
                  value={settings.extrusionScale}
                  min={0}
                  max={2000}
                  step={50}
                  suffix=" m"
                  onChange={(v) => update("extrusionScale", v)}
                />
                <Slider
                  label="Terrain exaggeration"
                  value={settings.terrainExaggeration}
                  min={1}
                  max={3}
                  step={0.1}
                  suffix="x"
                  decimals={1}
                  onChange={(v) => update("terrainExaggeration", v)}
                />
                <Slider
                  label="Fill opacity"
                  value={settings.opacity}
                  min={0.2}
                  max={1}
                  step={0.02}
                  suffix=""
                  decimals={2}
                  onChange={(v) => update("opacity", v)}
                />
              </div>

              <p className="border-t border-[var(--border-subtle)] pt-3 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
                Elevation from AWS Terrain Tiles. Boundaries from datameet Census 2011, provisional.
                Roads from OpenStreetMap, ODbL.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------- inspector */}
      {selected && (
        <aside className="absolute top-3 right-3 z-[var(--z-drawer)] max-h-[calc(100dvh-1.5rem)] w-[20rem] overflow-y-auto rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)]/96 shadow-[var(--shadow-4)] backdrop-blur">
          <div className="flex items-start gap-2 border-b border-[var(--border-subtle)] p-4">
            <div>
              <p className="text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
                Slope unit
              </p>
              <p data-numeric className="text-[length:var(--text-lg)] font-semibold">
                #{selected.hillslope_id}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              aria-label="Close inspector"
              className="ml-auto rounded-[var(--radius-md)] p-1 text-[var(--fg-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>

          {settings.mode === "stability" && physics && (
            <div className="border-b border-[var(--border-subtle)] p-4">
              {(() => {
                const band = stabilityBand(selectedFos);
                return (
                  <>
                    <div className="flex items-baseline gap-2">
                      <span
                        data-numeric
                        className="text-[length:var(--text-3xl)] font-semibold"
                        style={{ color: band ? bandCss(band) : "var(--fg-muted)" }}
                      >
                        {selectedFos === null ? "—" : selectedFos.toFixed(2)}
                      </span>
                      <span className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                        factor of safety
                      </span>
                    </div>
                    <p
                      className="mt-1 text-[length:var(--text-sm)] font-medium"
                      style={{ color: band ? bandCss(band) : "var(--fg-muted)" }}
                    >
                      {band ? BAND_LABEL[band] : "Not scored"}
                    </p>

                    {/* The equation with this unit's own numbers in it. This is
                        the answer to "why should I trust this number": every
                        term is visible and checkable. */}
                    <div className="mt-3 rounded-[var(--radius-md)] bg-[var(--bg-elevated)] p-3">
                      <p className="text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
                        Worked for this unit
                      </p>
                      <dl
                        data-numeric
                        className="mt-2 grid gap-1 text-[length:var(--text-2xs)] text-[var(--fg-secondary)]"
                      >
                        <Term
                          symbol="β"
                          name="slope angle"
                          value={`${(selected.slope_deg ?? 0).toFixed(1)}°`}
                        />
                        <Term
                          symbol="z"
                          name="soil depth, terrain proxy"
                          value={`${estimateDepth(selected.slope_deg).toFixed(2)} m`}
                        />
                        <Term
                          symbol="c'"
                          name="effective cohesion"
                          value={`${physics.lithology.cohesion_kpa} kPa`}
                        />
                        <Term
                          symbol="φ'"
                          name="friction angle"
                          value={`${physics.lithology.friction_angle_deg}°`}
                        />
                        <Term
                          symbol="γ"
                          name="unit weight"
                          value={`${physics.lithology.unit_weight_kn_m3} kN/m³`}
                        />
                        <Term
                          symbol="m"
                          name="profile wetness"
                          value={`${(physics.wetness_fraction * 100).toFixed(0)}%`}
                        />
                      </dl>
                      <p className="mt-2 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
                        {physics.lithology.name}. Parameters are regional class averages and soil
                        depth is a terrain proxy, so treat this as a range, not a measurement.
                      </p>
                    </div>
                  </>
                );
              })()}
            </div>
          )}

          <dl className="divide-y divide-[var(--border-subtle)]">
            <Row label="Area" value={`${(selected.area_m2 / 1e4).toFixed(1)} ha`} />
            {TERRAIN_ATTRIBUTES.map((attribute) => {
              const raw = selected[attribute.key] as number | null;
              const t = normalise(raw, attribute.domain);
              return (
                <Row
                  key={attribute.key}
                  label={attribute.label}
                  value={formatAttribute(raw, attribute)}
                  swatch={t === null ? undefined : rampCss(t)}
                  emphasis={attribute.key === settings.attribute.key}
                />
              );
            })}
            <Row label="Aspect" value={compassPoint(selected.aspect_deg)} />
          </dl>

          <p className="p-4 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
            Every value here was computed by the Phase 1 pipeline from the elevation model. None of
            it is a forecast. The factor of safety, rainfall thresholds and failure probability
            arrive with the risk engine in Phase 3.
          </p>
        </aside>
      )}

      {!selected && !load.loading && !load.error && (
        <p className="pointer-events-none absolute bottom-4 left-1/2 z-[var(--z-panel)] -translate-x-1/2 rounded-[var(--radius-full)] bg-[var(--bg-surface)]/90 px-4 py-1.5 text-[length:var(--text-xs)] text-[var(--fg-secondary)] backdrop-blur">
          Click any slope unit to inspect its measured terrain
        </p>
      )}
    </div>
  );
}

/** Mirrors estimate_soil_depth in ml/physics/slope_stability.py, for display only. */
function estimateDepth(slopeDeg: number | null): number {
  const beta = slopeDeg ?? 0;
  const fraction = Math.min(1, Math.max(0, beta / 45));
  return 2.5 - (2.5 - 0.3) * fraction;
}

function Term({ symbol, name, value }: { symbol: string; name: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-5 shrink-0 font-semibold text-[var(--fg-primary)]">{symbol}</span>
      <span className="text-[var(--fg-muted)]">{name}</span>
      <span className="ml-auto font-medium text-[var(--fg-primary)]">{value}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-[var(--radius-md)] bg-[var(--bg-elevated)] px-2.5 py-2">
      <p data-numeric className="text-[length:var(--text-lg)] leading-none font-semibold">
        {value === null ? "—" : value.toLocaleString()}
      </p>
      <p className="mt-1 text-[length:var(--text-2xs)] text-[var(--fg-muted)]">{label}</p>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-3.5 accent-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
      />
      {label}
    </label>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  decimals = 0,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  decimals?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="flex justify-between text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
        {label}
        <span data-numeric className="text-[var(--fg-muted)]">
          {value.toFixed(decimals)}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full accent-[var(--accent)]"
      />
    </label>
  );
}

function Row({
  label,
  value,
  swatch,
  emphasis = false,
}: {
  label: string;
  value: string;
  swatch?: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={cn("flex items-center gap-2 px-4 py-2.5", emphasis && "bg-[var(--bg-elevated)]")}
    >
      {swatch ? (
        <span
          aria-hidden="true"
          className="size-2.5 shrink-0 rounded-full ring-1 ring-[var(--border-default)]"
          style={{ background: swatch }}
        />
      ) : (
        <span aria-hidden="true" className="size-2.5 shrink-0" />
      )}
      <dt className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">{label}</dt>
      <dd data-numeric className="ml-auto text-[length:var(--text-sm)] font-medium">
        {value}
      </dd>
    </div>
  );
}
