"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, MapPin, Navigation, XCircle } from "lucide-react";

import { apiUrl, bandCss, type LocationLookupResponse, type StabilityBand } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { ASSUMED_WETNESS_FALLBACK, useLiveWetness } from "@/lib/use-live-wetness";

/**
 * Check any location in India.
 *
 * This is two honest answers, never blended into one invented number.
 *
 * For a point inside the Noney and Tupul pilot area, the answer is the real
 * factor of safety of the nearest of the 14,714 measured slope units, the
 * same computation the map and dashboards use.
 *
 * For everywhere else in India, which is almost every tap this screen will
 * receive, there is no slope-level data. The answer there is a documented
 * fact instead of a guess: whether the Geological Survey of India's National
 * Landslide Susceptibility Mapping programme covers that state, and which
 * of the four hill belts it sits in. That is real information a visitor did
 * not have before, even though it is not a computed risk score.
 */

type Status = "idle" | "locating" | "loading" | "done" | "error";

export function LocationCheck() {
  // Scored at the same live wetness every other screen uses.
  const { live: liveWetness } = useLiveWetness();
  const wetness = liveWetness ?? ASSUMED_WETNESS_FALLBACK;
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<LocationLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [manualLat, setManualLat] = useState("");
  const [manualLon, setManualLon] = useState("");

  const checkPoint = async (lat: number, lon: number) => {
    setStatus("loading");
    setError(null);
    try {
      const response = await fetch(
        apiUrl(`/location/lookup?latitude=${lat}&longitude=${lon}&wetness=${wetness}`),
      );
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setResult((await response.json()) as LocationLookupResponse);
      setStatus("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not check this location");
      setStatus("error");
    }
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setError("This browser does not support geolocation. Enter coordinates instead.");
      setStatus("error");
      return;
    }
    setStatus("locating");
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => void checkPoint(position.coords.latitude, position.coords.longitude),
      (geoError) => {
        setError(
          geoError.code === geoError.PERMISSION_DENIED
            ? "Location permission was denied. Enter coordinates below instead."
            : "Could not read your location. Enter coordinates below instead.",
        );
        setStatus("error");
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const checkManual = () => {
    const lat = Number(manualLat);
    const lon = Number(manualLon);
    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < 6 ||
      lat > 38 ||
      lon < 68 ||
      lon > 98
    ) {
      setError("Enter a latitude and longitude within India, for example 25.578, 91.893.");
      setStatus("error");
      return;
    }
    void checkPoint(lat, lon);
  };

  return (
    <div className="mx-auto max-w-2xl px-5 py-10">
      <p className="text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--sev-cyan-text)] uppercase">
        Anywhere in India
      </p>
      <h1 className="mt-3 text-[length:var(--text-2xl)] font-semibold tracking-[var(--tracking-tight)]">
        Check landslide susceptibility for a location
      </h1>
      <p className="mt-3 max-w-xl text-[length:var(--text-sm)] leading-relaxed text-[var(--fg-secondary)]">
        For the Noney and Tupul pilot area this returns a real, computed factor of safety.
        Everywhere else it returns whether the Geological Survey of India has mapped that state for
        landslide susceptibility, which is real information, not an invented score.
      </p>

      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={useMyLocation}
          disabled={status === "locating" || status === "loading"}
          className="inline-flex h-12 items-center gap-2 rounded-[var(--radius-full)] bg-[var(--accent)] px-6 text-[length:var(--text-base)] font-medium text-[var(--accent-fg)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)] disabled:opacity-60"
        >
          {status === "locating" || status === "loading" ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Navigation aria-hidden="true" className="size-4" />
          )}
          Use my current location
        </button>
      </div>

      <details className="mt-4">
        <summary className="cursor-pointer text-[length:var(--text-sm)] text-[var(--fg-muted)] hover:text-[var(--fg-primary)]">
          Or enter coordinates
        </summary>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
              Latitude
            </span>
            <input
              value={manualLat}
              onChange={(event) => setManualLat(event.target.value)}
              placeholder="25.578"
              inputMode="decimal"
              className="mt-1 h-10 w-32 rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 text-[length:var(--text-sm)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
            />
          </label>
          <label className="block">
            <span className="text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
              Longitude
            </span>
            <input
              value={manualLon}
              onChange={(event) => setManualLon(event.target.value)}
              placeholder="91.893"
              inputMode="decimal"
              className="mt-1 h-10 w-32 rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 text-[length:var(--text-sm)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
            />
          </label>
          <button
            type="button"
            onClick={checkManual}
            className="h-10 rounded-[var(--radius-md)] border border-[var(--border-default)] px-4 text-[length:var(--text-sm)] font-medium hover:border-[var(--border-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
          >
            Check
          </button>
        </div>
      </details>

      {error && (
        <p className="mt-6 rounded-[var(--radius-md)] border border-[var(--sev-red-outline)] bg-[var(--sev-red-tint)] p-3 text-[length:var(--text-sm)] text-[var(--sev-red-text)]">
          {error}
        </p>
      )}

      {result && <ResultCard result={result} />}
    </div>
  );
}

function ResultCard({ result }: { result: LocationLookupResponse }) {
  if (!result.within_india_boundary_data) {
    return (
      <div className="mt-8 rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6">
        <p className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">{result.gsi_note}</p>
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-4">
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6">
        <p className="flex items-center gap-2 text-[length:var(--text-xs)] text-[var(--fg-muted)]">
          <MapPin aria-hidden="true" className="size-3.5" />
          <span data-numeric>
            {result.latitude.toFixed(4)}, {result.longitude.toFixed(4)}
          </span>
        </p>
        <p className="mt-2 text-[length:var(--text-xl)] font-semibold">
          {result.district}, {result.state}
        </p>

        <div className="mt-4 flex items-start gap-2">
          {result.gsi_landslide_prone ? (
            <CheckCircle2
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 text-[var(--sev-amber-text)]"
            />
          ) : (
            <XCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-[var(--fg-muted)]" />
          )}
          <p className="text-[length:var(--text-sm)] leading-relaxed text-[var(--fg-secondary)]">
            {result.gsi_note}
          </p>
        </div>
      </div>

      {result.has_detailed_coverage && result.nearest_unit ? (
        <DetailedResult unit={result.nearest_unit} distance={result.nearest_unit_distance_m} />
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6">
          <p className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
            Slope-level data exists only for the Noney and Tupul pilot area in Manipur, roughly
            4,486 km². Building the same 14,714-unit terrain model for the rest of India is the
            direct next step of this project, not a limitation of the method.
          </p>
        </div>
      )}
    </div>
  );
}

function DetailedResult({
  unit,
  distance,
}: {
  unit: LocationLookupResponse["nearest_unit"];
  distance: number | null;
}) {
  if (!unit) return null;
  const band = unit.stability_class as StabilityBand;
  return (
    <div
      className="rounded-[var(--radius-lg)] border p-6"
      style={{
        borderColor: bandCss(band),
        background: `color-mix(in srgb, ${bandCss(band)} 12%, var(--bg-surface))`,
      }}
    >
      <p className="text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
        Nearest measured slope unit, {distance !== null ? `${Math.round(distance)} m away` : ""}
      </p>
      <p className="mt-2 flex items-baseline gap-2">
        <span
          className="text-[length:var(--text-3xl)] font-semibold"
          style={{ color: bandCss(band) }}
        >
          {unit.factor_of_safety.toFixed(2)}
        </span>
        <span className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
          factor of safety, {unit.stability_class}
        </span>
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-[length:var(--text-xs)]">
        <Row label="Slope angle" value={`${unit.slope_deg.toFixed(1)}°`} />
        <Row
          label="Elevation"
          value={unit.elevation_mean_m !== null ? `${unit.elevation_mean_m.toFixed(0)} m` : "—"}
        />
        <Row label="Material assumed" value={unit.lithology} />
        <Row label="Profile wetness" value={`${(unit.wetness_fraction * 100).toFixed(0)}%`} />
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className={cn("text-[var(--fg-muted)]")}>{label}</dt>
      <dd data-numeric className="mt-0.5 font-medium">
        {value}
      </dd>
    </div>
  );
}
