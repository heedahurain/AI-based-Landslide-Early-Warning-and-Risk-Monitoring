import { describe, expect, it } from "vitest";

import {
  SEVERITY_LEVELS,
  SEVERITY_RANK,
  ariaLiveFor,
  escalatesWithoutAck,
  maxSeverity,
} from "./severity";
import { ageInMinutes, formatProbability } from "./utils";

describe("severity ordering", () => {
  it("ranks the four tiers in ascending order of concern", () => {
    const ranks = SEVERITY_LEVELS.map((level) => SEVERITY_RANK[level]);
    expect(ranks).toEqual([0, 1, 2, 3]);
  });

  it("aggregates upward to the most severe unit", () => {
    // A district takes the severity of its worst slope unit. Averaging would
    // hide a single failing slope inside a calm district, which is exactly the
    // case the system exists to catch.
    expect(maxSeverity("green", "red")).toBe("red");
    expect(maxSeverity("orange", "yellow")).toBe("orange");
    expect(maxSeverity("green", "green")).toBe("green");
  });
});

describe("acknowledgement policy", () => {
  it("requires acknowledgement only for ORANGE and RED", () => {
    expect(escalatesWithoutAck("green")).toBe(false);
    expect(escalatesWithoutAck("yellow")).toBe(false);
    expect(escalatesWithoutAck("orange")).toBe(true);
    expect(escalatesWithoutAck("red")).toBe(true);
  });
});

describe("screen reader announcements", () => {
  it("interrupts only for RED", () => {
    expect(ariaLiveFor("red")).toBe("assertive");
    expect(ariaLiveFor("orange")).toBe("polite");
    expect(ariaLiveFor("green")).toBe("polite");
  });
});

describe("number formatting", () => {
  it("renders probability without implying false precision", () => {
    // The calibration does not support tenths of a percent, so 0.7231 is 72%.
    expect(formatProbability(0.7231, "en")).toBe("72%");
    expect(formatProbability(0, "en")).toBe("0%");
    expect(formatProbability(1, "en")).toBe("100%");
  });

  it("reports data age in whole minutes and never negative", () => {
    const now = new Date("2026-09-08T12:00:00Z");
    expect(ageInMinutes(new Date("2026-09-08T11:46:00Z"), now)).toBe(14);
    expect(ageInMinutes(new Date("2026-09-08T12:00:00Z"), now)).toBe(0);
    // A clock skew between API and browser must not render as "-3 min ago".
    expect(ageInMinutes(new Date("2026-09-08T12:03:00Z"), now)).toBe(0);
  });
});
