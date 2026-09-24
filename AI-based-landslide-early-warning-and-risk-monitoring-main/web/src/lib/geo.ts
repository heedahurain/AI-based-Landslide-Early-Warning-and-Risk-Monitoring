/**
 * Terrain attribute vocabulary and the colour ramp for the map.
 *
 * A deliberate constraint runs through this file: **none of these are risk.**
 * No model has been trained, so the map shows measured terrain properties, and
 * the palette is chosen to look like data rather than an alert. The four-tier
 * severity colours are reserved for actual risk output and must never be used
 * to shade a terrain attribute, or a viewer will read a steep slope as a
 * warning that nobody issued.
 */

export interface SlopeUnitProperties {
  hillslope_id: number;
  area_m2: number;
  slope_deg: number | null;
  slope_max_deg: number | null;
  aspect_deg: number | null;
  twi: number | null;
  tpi: number | null;
  local_relief_m: number | null;
  elevation_mean_m: number | null;
  distance_to_stream_m: number | null;
}

export interface TerrainAttribute {
  key: keyof SlopeUnitProperties;
  label: string;
  unit: string;
  /** Display range for the colour ramp, from the measured pilot distribution. */
  domain: [number, number];
  description: string;
  decimals: number;
}

export const TERRAIN_ATTRIBUTES: TerrainAttribute[] = [
  {
    key: "slope_deg",
    label: "Slope angle",
    unit: "°",
    domain: [0, 45],
    decimals: 1,
    description:
      "Mean gradient of the hillslope. This is beta in the factor-of-safety equation, so it is the single most important terrain input to the physics layer.",
  },
  {
    key: "twi",
    label: "Wetness index",
    unit: "",
    domain: [2, 14],
    decimals: 2,
    description:
      "Topographic wetness. High values mean a large catchment draining onto gentle ground, which stays wet. Wet ground raises pore pressure, which is what pushes a slope towards failure.",
  },
  {
    key: "local_relief_m",
    label: "Local relief",
    unit: " m",
    domain: [0, 900],
    decimals: 0,
    description:
      "Elevation range within a moving window. Separates a steep face on a large hillside from a steep face on a small bank; the two behave very differently.",
  },
  {
    key: "elevation_mean_m",
    label: "Elevation",
    unit: " m",
    domain: [0, 2600],
    decimals: 0,
    description: "Mean elevation of the slope unit above sea level.",
  },
  {
    key: "slope_max_deg",
    label: "Maximum slope",
    unit: "°",
    domain: [0, 70],
    decimals: 1,
    description:
      "Steepest cell inside the unit. A unit that is gentle on average can still contain a scarp.",
  },
  {
    key: "distance_to_stream_m",
    label: "Distance to stream",
    unit: " m",
    domain: [0, 800],
    decimals: 0,
    description:
      "Downslope distance to the nearest channel. Undercutting by a stream is a common trigger at the base of a slope.",
  },
];

/**
 * A perceptually ordered ramp running deep blue to teal to green to yellow.
 *
 * Chosen because it reads as a measurement scale and is distinguishable by
 * most forms of colour vision, and because it shares no colour with the
 * severity palette.
 */
const RAMP: [number, number, number][] = [
  [13, 20, 36],
  [30, 62, 96],
  [32, 105, 128],
  [40, 145, 133],
  [77, 180, 114],
  [149, 208, 84],
  [232, 227, 71],
];

/** Clamp a value into 0..1 across the attribute's display domain. */
export function normalise(value: number | null, domain: [number, number]): number | null {
  if (value === null || !Number.isFinite(value)) return null;
  const [low, high] = domain;
  if (high === low) return 0;
  return Math.min(1, Math.max(0, (value - low) / (high - low)));
}

/** Colour for a normalised 0..1 position, as deck.gl RGBA. */
export function rampColour(t: number | null, alpha = 200): [number, number, number, number] {
  if (t === null) {
    // No measurement is not the same as a low measurement, so unmeasured units
    // are grey rather than the bottom of the ramp.
    return [70, 80, 100, 90];
  }
  const scaled = t * (RAMP.length - 1);
  const index = Math.min(RAMP.length - 2, Math.floor(scaled));
  const frac = scaled - index;
  const from = RAMP[index]!;
  const to = RAMP[index + 1]!;
  return [
    Math.round(from[0] + (to[0] - from[0]) * frac),
    Math.round(from[1] + (to[1] - from[1]) * frac),
    Math.round(from[2] + (to[2] - from[2]) * frac),
    alpha,
  ];
}

/** CSS colour for the legend, which cannot use deck.gl's array form. */
export function rampCss(t: number): string {
  const [r, g, b] = rampColour(t);
  return `rgb(${r} ${g} ${b})`;
}

export function formatAttribute(value: number | null, attribute: TerrainAttribute): string {
  if (value === null || !Number.isFinite(value)) return "not measured";
  return `${value.toFixed(attribute.decimals)}${attribute.unit}`;
}

/** Compass point for an azimuth, which reads faster than a number. */
export function compassPoint(degrees: number | null): string {
  if (degrees === null || !Number.isFinite(degrees)) return "not measured";
  const points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const index = Math.round((((degrees % 360) + 360) % 360) / 45) % 8;
  return `${points[index]} (${degrees.toFixed(0)}°)`;
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function apiUrl(path: string): string {
  return `${API_BASE}/api/v1${path}`;
}

// ---------------------------------------------------------------------------
// Physics layer
// ---------------------------------------------------------------------------

export interface LithologyOption {
  key: string;
  name: string;
  cohesion_kpa: number;
  friction_angle_deg: number;
  unit_weight_kn_m3: number;
  typical_soil_depth_m: number;
  source_reference: string;
  is_default: boolean;
}

export interface StabilitySummary {
  unstable: number;
  marginal: number;
  stable: number;
  median_fos: number | null;
  min_fos: number | null;
  scored: number;
}

export interface FactorOfSafetyResponse {
  run: string;
  lithology: LithologyOption;
  wetness_fraction: number;
  equation: string;
  disclaimer: string;
  summary: StabilitySummary;
  hillslope_ids: number[];
  fos: (number | null)[];
}

export type StabilityBand = "unstable" | "marginal" | "low_margin" | "stable";

/**
 * Stability bands for a factor of safety.
 *
 * Below 1.0 the driving stress exceeds the available strength. 1.0 to 1.3 is
 * the conventional marginal band, where the margin is smaller than the
 * uncertainty in the parameters. Above that the slope has real reserve.
 */
export function stabilityBand(fos: number | null): StabilityBand | null {
  if (fos === null || !Number.isFinite(fos)) return null;
  if (fos < 1.0) return "unstable";
  if (fos < 1.3) return "marginal";
  if (fos < 2.0) return "low_margin";
  return "stable";
}

/**
 * Colours for the stability bands.
 *
 * These are the locked severity hexes, used here because the mapping is
 * genuinely ordinal and a reader already associates red with danger. The
 * legend states plainly that this is a stability class from the physics layer
 * and not an alert level, because only an issued alert may claim that.
 */
const BAND_COLOUR: Record<StabilityBand, [number, number, number]> = {
  unstable: [239, 68, 68],
  marginal: [249, 115, 22],
  low_margin: [245, 158, 11],
  stable: [34, 197, 94],
};

export const BAND_LABEL: Record<StabilityBand, string> = {
  unstable: "Unstable, FoS below 1.0",
  marginal: "Marginal, 1.0 to 1.3",
  low_margin: "Low margin, 1.3 to 2.0",
  stable: "Stable, 2.0 and above",
};

export const BAND_ORDER: StabilityBand[] = ["unstable", "marginal", "low_margin", "stable"];

export function bandColour(
  band: StabilityBand | null,
  alpha = 200,
): [number, number, number, number] {
  if (band === null) return [70, 80, 100, 90];
  const [r, g, b] = BAND_COLOUR[band];
  return [r, g, b, alpha];
}

export function bandCss(band: StabilityBand): string {
  const [r, g, b] = BAND_COLOUR[band];
  return `rgb(${r} ${g} ${b})`;
}

/** Normalised position of a factor of safety for extrusion height. */
export function fosHeightFraction(fos: number | null): number {
  if (fos === null || !Number.isFinite(fos)) return 0;
  // Inverted: the least stable slopes stand tallest, because those are the
  // ones a viewer needs to find first.
  return Math.min(1, Math.max(0, (2.5 - fos) / 2.0));
}

// ---------------------------------------------------------------------------
// All-India location lookup
// ---------------------------------------------------------------------------

export interface NearestUnit {
  hillslope_id: number;
  slope_deg: number;
  elevation_mean_m: number | null;
  factor_of_safety: number;
  stability_class: string;
  lithology: string;
  wetness_fraction: number;
}

export interface StabilitySummary {
  scored_units: number;
  unstable: number;
  marginal: number;
  stable: number;
}

export interface LocationLookupResponse {
  latitude: number;
  longitude: number;
  state: string | null;
  district: string | null;
  within_india_boundary_data: boolean;
  gsi_landslide_prone: boolean;
  gsi_belt: string | null;
  gsi_note: string;
  has_detailed_coverage: boolean;
  detailed_run: string | null;
  nearest_unit: NearestUnit | null;
  nearest_unit_distance_m: number | null;
  stability_summary: StabilitySummary | null;
}
