"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CloudRain, Loader2, MapPin, Send, ShieldCheck } from "lucide-react";

import { apiUrl } from "@/lib/geo";
import { cn } from "@/lib/utils";

/**
 * The public portal: "Am I safe right now?"
 *
 * Designed for a phone held at arm's length in daylight by someone who is
 * worried. Large targets, high contrast, one answer at the top, and concrete
 * actions rather than platitudes.
 *
 * It states its own limits in plain words. No trained model exists, so the
 * status shown is derived from rainfall and slope physics, and the page says
 * so instead of implying an official warning.
 */

const CATEGORIES = [
  { key: "tension_crack", label: "Crack in the ground" },
  { key: "slope_bulge", label: "Bulging slope" },
  { key: "debris_flow", label: "Mud or debris flow" },
  { key: "road_damage", label: "Damaged road" },
  { key: "retaining_wall", label: "Broken retaining wall" },
  { key: "water_seepage", label: "Water seeping out" },
  { key: "tilted_tree", label: "Leaning tree or pole" },
  { key: "other", label: "Something else" },
] as const;

interface Weather {
  rainfall_24h_mm: number;
  rainfall_72h_mm: number;
  rainfall_next_24h_mm: number;
  suggested_wetness_fraction: number;
  status: string;
}

interface Physics {
  summary: { unstable: number; marginal: number; stable: number; scored: number };
  wetness_fraction: number;
}

type Level = "green" | "yellow" | "orange" | "red";

const LEVEL_COPY: Record<Level, { title: string; action: string; colour: string; tint: string }> = {
  green: {
    title: "Conditions are normal",
    action: "No action needed. Stay aware if heavy rain starts.",
    colour: "var(--sev-green-text)",
    tint: "var(--sev-green-tint)",
  },
  yellow: {
    title: "Stay alert",
    action: "Avoid slopes and cut sections after dark. Keep a phone charged.",
    colour: "var(--sev-amber-text)",
    tint: "var(--sev-amber-tint)",
  },
  orange: {
    title: "Prepare to move",
    action: "Keep documents and medicines ready. Agree a meeting point with your family.",
    colour: "var(--sev-orange-text)",
    tint: "var(--sev-orange-tint)",
  },
  red: {
    title: "Leave now",
    action: "Go to the nearest shelter by the marked route. Do not wait for daylight.",
    colour: "var(--sev-red-text)",
    tint: "var(--sev-red-tint)",
  },
};

/**
 * Derive a level from what is actually measured.
 *
 * Rainfall in the last 72 hours and the share of nearby slopes that have lost
 * their margin. The thresholds are stated on screen so nobody has to guess what
 * produced the colour, and they are not calibrated against observed failures,
 * which the page says outright.
 */
function deriveLevel(weather: Weather | null, physics: Physics | null): Level {
  if (!weather || !physics) return "green";
  const atRisk =
    (physics.summary.unstable + physics.summary.marginal) / Math.max(1, physics.summary.scored);

  if (physics.summary.unstable > 0 && weather.rainfall_72h_mm > 100) return "red";
  if (atRisk > 0.4 || weather.rainfall_72h_mm > 100) return "orange";
  if (atRisk > 0.1 || weather.rainfall_72h_mm > 40) return "yellow";
  return "green";
}

export function PublicPortal() {
  const [weather, setWeather] = useState<Weather | null>(null);
  const [physics, setPhysics] = useState<Physics | null>(null);
  const [loading, setLoading] = useState(true);
  const [position, setPosition] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);

  const [category, setCategory] = useState<string>("tension_crack");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const weatherResponse = await fetch(apiUrl("/weather/forecast"));
        const weatherData = weatherResponse.ok ? ((await weatherResponse.json()) as Weather) : null;
        if (cancelled) return;
        setWeather(weatherData);

        const physicsResponse = await fetch(
          apiUrl(
            `/risk/factor-of-safety?wetness=${weatherData?.suggested_wetness_fraction ?? 0.5}`,
          ),
        );
        if (physicsResponse.ok && !cancelled) setPhysics((await physicsResponse.json()) as Physics);
      } catch {
        // The page still renders, with an explicit "cannot check" state.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const locate = () => {
    setLocating(true);
    navigator.geolocation?.getCurrentPosition(
      (result) => {
        setPosition({ lat: result.coords.latitude, lon: result.coords.longitude });
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await fetch(apiUrl("/reports"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latitude: position?.lat ?? 24.9,
          longitude: position?.lon ?? 93.5,
          category,
          description,
          severity_self_assessed: 2,
        }),
      });
      if (!response.ok) {
        // The API answers with an RFC 7807 problem document. Its detail explains
        // exactly why a location was refused, which is far more useful to a
        // citizen than a status code, so show it verbatim.
        let detail = `Submission failed (${response.status})`;
        try {
          const problem = (await response.json()) as { detail?: string; title?: string };
          detail = problem.detail ?? problem.title ?? detail;
        } catch {
          // Keep the status-code message.
        }
        throw new Error(detail);
      }
      setSubmitted(true);
      setDescription("");
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "Could not send the report");
    } finally {
      setSubmitting(false);
    }
  };

  const level = deriveLevel(weather, physics);
  const copy = LEVEL_COPY[level];

  return (
    <div className="min-h-dvh bg-[var(--bg-base)]">
      <header className="border-b border-[var(--border-subtle)] px-5 py-4">
        <p className="text-[length:var(--text-md)] font-semibold">ShailSuraksha</p>
        <p className="text-[length:var(--text-xs)] text-[var(--fg-muted)]">
          Noney and Tupul, Manipur
        </p>
      </header>

      <main className="mx-auto max-w-xl px-5 py-6">
        <h1 className="text-[length:var(--text-2xl)] font-semibold tracking-[var(--tracking-tight)]">
          Am I safe right now?
        </h1>

        {/* -------------------------------------------- status card ---- */}
        <div
          className="mt-5 rounded-[var(--radius-xl)] border p-5"
          style={{ background: copy.tint, borderColor: copy.colour }}
          aria-live="polite"
        >
          {loading ? (
            <p className="flex items-center gap-2 text-[length:var(--text-md)]">
              <Loader2 aria-hidden="true" className="size-5 animate-spin" />
              Checking conditions
            </p>
          ) : (
            <>
              <p
                className="text-[length:var(--text-2xl)] leading-tight font-semibold"
                style={{ color: copy.colour }}
              >
                {copy.title}
              </p>
              <p className="mt-2 text-[length:var(--text-md)] leading-relaxed text-[var(--fg-primary)]">
                {copy.action}
              </p>
            </>
          )}
        </div>

        {/* --------------------------------------------- the numbers --- */}
        {weather && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Fact
              icon={<CloudRain aria-hidden="true" className="size-4" />}
              label="Rain, last 72 hours"
              value={`${weather.rainfall_72h_mm} mm`}
            />
            <Fact
              icon={<CloudRain aria-hidden="true" className="size-4" />}
              label="Expected next 24 hours"
              value={`${weather.rainfall_next_24h_mm} mm`}
            />
            <Fact
              icon={<AlertTriangle aria-hidden="true" className="size-4" />}
              label="Slopes with little margin"
              value={
                physics
                  ? `${(physics.summary.unstable + physics.summary.marginal).toLocaleString()}`
                  : "—"
              }
            />
            <Fact
              icon={<ShieldCheck aria-hidden="true" className="size-4" />}
              label="Ground wetness"
              value={`${Math.round((weather.suggested_wetness_fraction ?? 0) * 100)}%`}
            />
          </div>
        )}

        <p className="mt-4 rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-[length:var(--text-xs)] leading-relaxed text-[var(--fg-secondary)]">
          This status comes from measured rainfall and a slope-stability calculation, not from a
          trained forecast model and not from an official warning. For official warnings follow the
          Geological Survey of India and the India Meteorological Department. If you can see a crack
          opening or hear the ground moving, leave immediately and do not wait for any app.
        </p>

        {/* ------------------------------------------------- report ---- */}
        <section className="mt-8">
          <h2 className="text-[length:var(--text-lg)] font-semibold">Report what you can see</h2>
          <p className="mt-1 text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
            A report from the ground is worth more than any model. It goes to a moderator.
          </p>

          {submitted ? (
            <div className="mt-4 rounded-[var(--radius-lg)] border border-[var(--sev-green-outline)] bg-[var(--sev-green-tint)] p-4">
              <p className="font-medium text-[var(--sev-green-text)]">Report sent. Thank you.</p>
              <button
                type="button"
                onClick={() => setSubmitted(false)}
                className="mt-2 text-[length:var(--text-sm)] underline"
              >
                Send another
              </button>
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-2">
                {CATEGORIES.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => setCategory(option.key)}
                    aria-pressed={category === option.key}
                    className={cn(
                      "min-h-14 rounded-[var(--radius-lg)] border px-3 py-2 text-left text-[length:var(--text-sm)]",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                      category === option.key
                        ? "border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--fg-primary)]"
                        : "border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--fg-secondary)]",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <label className="block">
                <span className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                  Anything else worth knowing
                </span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-3 text-[length:var(--text-md)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
                  placeholder="Where exactly, how big, when you saw it"
                />
              </label>

              <button
                type="button"
                onClick={locate}
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] px-4 text-[length:var(--text-md)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
              >
                {locating ? (
                  <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                ) : (
                  <MapPin aria-hidden="true" className="size-4" />
                )}
                {position
                  ? `Location set: ${position.lat.toFixed(4)}, ${position.lon.toFixed(4)}`
                  : "Use my location"}
              </button>

              {submitError && (
                <p className="text-[length:var(--text-sm)] text-[var(--sev-red-text)]">
                  {submitError}
                </p>
              )}

              <button
                type="button"
                onClick={() => void submit()}
                disabled={submitting}
                className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-[var(--accent)] px-4 text-[length:var(--text-md)] font-semibold text-[var(--accent-fg)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)] disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                ) : (
                  <Send aria-hidden="true" className="size-4" />
                )}
                Send report
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Fact({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
      <p className="flex items-center gap-1.5 text-[length:var(--text-xs)] text-[var(--fg-muted)]">
        {icon}
        {label}
      </p>
      <p data-numeric className="mt-1 text-[length:var(--text-lg)] font-semibold">
        {value}
      </p>
    </div>
  );
}
