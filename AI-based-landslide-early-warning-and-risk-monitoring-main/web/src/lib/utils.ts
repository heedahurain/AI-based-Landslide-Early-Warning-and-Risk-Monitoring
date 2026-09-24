import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, with later Tailwind utilities winning. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number for the operations console.
 *
 * Every figure on screen is traceable to a computation, so precision is stated
 * rather than guessed at, and grouping follows the active locale. Pair this
 * with the `tabular` class so digits do not jitter as values update.
 */
export function formatNumber(
  value: number,
  locale: string,
  options: Intl.NumberFormatOptions = {},
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

/**
 * Render a probability as a whole-number percentage.
 *
 * Deliberately no decimal places: the model's calibration does not support
 * implying tenths of a percent, and false precision is a credibility problem
 * in this domain.
 */
export function formatProbability(probability: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(probability);
}

/**
 * Compact relative age, for data-freshness chips such as "updated 14 min ago".
 * Returns the unit and value so the caller can localise it.
 */
export function ageInMinutes(timestamp: Date, now: Date = new Date()): number {
  return Math.max(0, Math.floor((now.getTime() - timestamp.getTime()) / 60_000));
}
