"use client";

import { RotateCcw } from "lucide-react";

/**
 * The profile wetness slider, with the live observed value marked on the track.
 *
 * The tick is the point of this component. A slider alone gives no way to tell
 * whether the current position is the measured state of the ground or a
 * scenario someone dragged to, and that ambiguity is exactly what made the
 * dashboards look untrustworthy. Marking the live reading, and offering one
 * click back to it, makes scenario mode visibly a departure from reality
 * rather than the default.
 */
export function WetnessControl({
  value,
  onChange,
  live,
  label = "Profile wetness",
}: {
  value: number;
  onChange: (next: number) => void;
  /** The live observed fraction, or null if the reading is unavailable. */
  live: number | null;
  label?: string;
}) {
  const isLive = live !== null && Math.abs(value - live) < 0.005;
  const livePct = live !== null ? Math.round(live * 100) : null;

  return (
    <div className="block">
      <div className="flex items-baseline justify-between gap-2 text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
        <span>{label}</span>
        <span className="flex items-center gap-1.5">
          <span data-numeric className="text-[var(--fg-primary)]">
            {(value * 100).toFixed(0)}%
          </span>
          {isLive ? (
            <span className="rounded-[var(--radius-full)] bg-[var(--sev-green-tint)] px-1.5 py-0.5 text-[length:var(--text-2xs)] font-medium text-[var(--sev-green-text)]">
              live
            </span>
          ) : (
            <span className="rounded-[var(--radius-full)] bg-[var(--sev-amber-tint)] px-1.5 py-0.5 text-[length:var(--text-2xs)] font-medium text-[var(--sev-amber-text)]">
              scenario
            </span>
          )}
        </span>
      </div>

      <div className="relative mt-2">
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          aria-label={label}
          className="w-full accent-[var(--accent)]"
        />
        {live !== null && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-full -translate-x-1/2"
            style={{ left: `${live * 100}%` }}
          >
            <span className="block h-1.5 w-px bg-[var(--sev-green-mark)]" />
          </span>
        )}
      </div>

      <div className="mt-2 flex min-h-5 items-center justify-between gap-2 text-[length:var(--text-2xs)]">
        {livePct !== null ? (
          <span className="text-[var(--fg-muted)]">
            Live reading{" "}
            <span data-numeric className="text-[var(--sev-green-text)]">
              {livePct}%
            </span>{" "}
            from soil moisture
          </span>
        ) : (
          <span className="text-[var(--fg-muted)]">
            Live reading unavailable, this is a stated assumption
          </span>
        )}
        {live !== null && !isLive && (
          <button
            type="button"
            onClick={() => onChange(live)}
            className="inline-flex shrink-0 items-center gap-1 rounded-[var(--radius-full)] border border-[var(--border-default)] px-2 py-0.5 font-medium text-[var(--fg-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--fg-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
          >
            <RotateCcw aria-hidden="true" className="size-3" />
            Back to live
          </button>
        )}
      </div>
    </div>
  );
}
