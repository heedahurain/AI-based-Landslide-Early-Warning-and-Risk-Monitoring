/**
 * Severity and data-provenance vocabulary.
 *
 * These two enums are load-bearing domain constants, not presentation details.
 * The four severity tiers are colour-locked across the entire product, and the
 * three provenance states are what stop the UI from ever implying that
 * simulated data is live. See PROJECT_CONTEXT.md §4 and §7.
 *
 * The API returns these exact lowercase strings.
 */

export const SEVERITY_LEVELS = ["green", "yellow", "orange", "red"] as const;
export type Severity = (typeof SEVERITY_LEVELS)[number];

/** Ascending order of concern. Used for comparisons and escalation logic. */
export const SEVERITY_RANK: Record<Severity, number> = {
  green: 0,
  yellow: 1,
  orange: 2,
  red: 3,
};

/**
 * The operational meaning of each tier. The label is a translation key, not
 * display text, because the citizen-facing surfaces render in ten languages.
 */
export const SEVERITY_META: Record<
  Severity,
  { labelKey: string; token: string; requiresAcknowledgement: boolean }
> = {
  green: { labelKey: "severity.green", token: "--sev-green", requiresAcknowledgement: false },
  yellow: { labelKey: "severity.yellow", token: "--sev-amber", requiresAcknowledgement: false },
  orange: { labelKey: "severity.orange", token: "--sev-orange", requiresAcknowledgement: true },
  red: { labelKey: "severity.red", token: "--sev-red", requiresAcknowledgement: true },
};

/** True when an unacknowledged alert at this tier must escalate up the hierarchy. */
export function escalatesWithoutAck(severity: Severity): boolean {
  return SEVERITY_META[severity].requiresAcknowledgement;
}

/** Returns the more severe of two tiers. Used when aggregating slope units upward. */
export function maxSeverity(a: Severity, b: Severity): Severity {
  return SEVERITY_RANK[a] >= SEVERITY_RANK[b] ? a : b;
}

/**
 * Data provenance, rendered as a chip on every surface that shows a number.
 *
 * `live`      the provider answered within its freshness window
 * `cached`    served from Redis; the age must be displayed alongside
 * `simulated` produced by the seeded synthetic engine
 */
export const PROVENANCE_STATES = ["live", "cached", "simulated"] as const;
export type Provenance = (typeof PROVENANCE_STATES)[number];

/**
 * Screen readers must be told when the severity of a region changes. RED is
 * assertive because it interrupts; everything else is polite.
 */
export function ariaLiveFor(severity: Severity): "assertive" | "polite" {
  return severity === "red" ? "assertive" : "polite";
}
