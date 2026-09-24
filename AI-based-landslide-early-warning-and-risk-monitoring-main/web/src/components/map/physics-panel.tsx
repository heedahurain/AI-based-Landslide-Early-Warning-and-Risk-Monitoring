"use client";

import { Loader2 } from "lucide-react";

import {
  BAND_LABEL,
  BAND_ORDER,
  bandCss,
  type FactorOfSafetyResponse,
  type LithologyOption,
} from "@/lib/geo";
import { cn } from "@/lib/utils";

/**
 * Controls and readout for the physics layer.
 *
 * The two inputs exposed here, material class and profile wetness, are the two
 * that dominate the factor of safety on this terrain, and neither has been
 * measured for the region. Putting them in the reader's hands is the honest
 * presentation: rather than asserting one number, the interface shows how the
 * answer moves across the plausible range.
 */
import { WetnessControl } from "@/components/shell/wetness-control";

export function PhysicsPanel({
  lithologies,
  selected,
  onSelectLithology,
  wetness,
  onWetnessChange,
  liveWetness,
  result,
  loading,
}: {
  lithologies: LithologyOption[];
  selected: string | null;
  onSelectLithology: (key: string) => void;
  wetness: number;
  onWetnessChange: (value: number) => void;
  /** The live observed fraction, or null when the reading is unavailable. */
  liveWetness: number | null;
  result: FactorOfSafetyResponse | null;
  loading: boolean;
}) {
  const summary = result?.summary;
  const total = summary ? summary.unstable + summary.marginal + summary.stable : 0;

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------ wetness ------- */}
      <div>
        <WetnessControl value={wetness} onChange={onWetnessChange} live={liveWetness} />
        <span className="mt-2 block text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
          The share of the soil profile standing saturated above the failure plane, derived from
          Open-Meteo deep soil moisture against an assumed saturation of 0.45 m&sup3;/m&sup3;.
          Dragging the slider explores a scenario; the tick marks the observed value.
        </span>
      </div>

      {/* ------------------------------------------------ material ------ */}
      <fieldset>
        <legend className="mb-2 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
          Material class
        </legend>
        <div className="grid gap-1">
          {lithologies.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onSelectLithology(option.key)}
              aria-pressed={selected === option.key}
              className={cn(
                "rounded-[var(--radius-md)] px-2.5 py-1.5 text-left text-[length:var(--text-sm)]",
                "transition-colors duration-[var(--duration-fast)]",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                selected === option.key
                  ? "bg-[var(--bg-elevated)] text-[var(--fg-primary)]"
                  : "text-[var(--fg-secondary)] hover:bg-[var(--bg-elevated)]",
              )}
            >
              <span className="block">{option.name}</span>
              <span
                data-numeric
                className="block text-[length:var(--text-2xs)] text-[var(--fg-muted)]"
              >
                c&apos; {option.cohesion_kpa} kPa · φ&apos; {option.friction_angle_deg}°
              </span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
          No lithology map has been joined to the slope units yet, so every unit is scored against
          the class you pick here. Regional published averages, not site tests.
        </p>
      </fieldset>

      {/* ------------------------------------------------ result -------- */}
      <div>
        <p className="mb-2 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
          Stability class
        </p>

        {loading && (
          <p className="flex items-center gap-2 text-[length:var(--text-xs)] text-[var(--fg-muted)]">
            <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
            Recomputing
          </p>
        )}

        {summary && total > 0 && (
          <>
            {/* Proportional bar, so the split is readable at a glance. */}
            <div className="flex h-2.5 w-full overflow-hidden rounded-[var(--radius-full)]">
              {BAND_ORDER.map((band) => {
                const count =
                  band === "unstable"
                    ? summary.unstable
                    : band === "marginal"
                      ? summary.marginal
                      : band === "low_margin"
                        ? 0
                        : summary.stable;
                if (!count) return null;
                return (
                  <span
                    key={band}
                    style={{ width: `${(100 * count) / total}%`, background: bandCss(band) }}
                    title={`${BAND_LABEL[band]}: ${count.toLocaleString()}`}
                  />
                );
              })}
            </div>

            <dl className="mt-3 grid gap-1.5">
              <Line
                label="Unstable, FoS below 1.0"
                value={summary.unstable}
                colour={bandCss("unstable")}
              />
              <Line
                label="Marginal, 1.0 to 1.3"
                value={summary.marginal}
                colour={bandCss("marginal")}
              />
              <Line label="Stable, above 1.3" value={summary.stable} colour={bandCss("stable")} />
            </dl>

            <p
              data-numeric
              className="mt-3 text-[length:var(--text-xs)] text-[var(--fg-secondary)]"
            >
              Median factor of safety {summary.median_fos ?? "—"}, lowest {summary.min_fos ?? "—"}
            </p>
          </>
        )}
      </div>

      {result && (
        <div className="border-t border-[var(--border-subtle)] pt-3">
          <p className="text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
            Equation
          </p>
          <code className="mt-1 block text-[length:var(--text-2xs)] leading-relaxed break-words text-[var(--fg-secondary)]">
            {result.equation}
          </code>
          <p className="mt-2 text-[length:var(--text-2xs)] leading-relaxed text-[var(--sev-amber-text)]">
            {result.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}

function Line({ label, value, colour }: { label: string; value: number; colour: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="size-2.5 shrink-0 rounded-full"
        style={{ background: colour }}
      />
      <dt className="text-[length:var(--text-xs)] text-[var(--fg-secondary)]">{label}</dt>
      <dd data-numeric className="ml-auto text-[length:var(--text-xs)] font-medium">
        {value.toLocaleString()}
      </dd>
    </div>
  );
}
