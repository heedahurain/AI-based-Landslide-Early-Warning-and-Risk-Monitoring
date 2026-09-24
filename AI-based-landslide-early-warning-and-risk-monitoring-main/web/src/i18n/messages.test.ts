import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { LOCALES, LOCALE_META } from "./routing";
import { SEVERITY_LEVELS } from "@/lib/severity";

const MESSAGES_DIR = path.resolve(__dirname, "../../messages");

function catalogueFor(locale: string): Record<string, Record<string, string>> | null {
  const file = path.join(MESSAGES_DIR, `${locale}.json`);
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, "utf-8"));
}

/**
 * These tests guard the promise in PROJECT_CONTEXT.md §8: citizen-facing and
 * alert strings are real translations, and the switcher never advertises a
 * language it cannot actually render.
 */
describe("message catalogues", () => {
  it("has an English baseline containing every key other locales rely on", () => {
    const en = catalogueFor("en");
    expect(en).not.toBeNull();
    expect(en?.app?.name).toBe("ShailSuraksha");
    for (const level of SEVERITY_LEVELS) {
      expect(en?.severity?.[level], `severity.${level}`).toBeTruthy();
      expect(en?.severityAction?.[level], `severityAction.${level}`).toBeTruthy();
    }
  });

  it("keeps LOCALE_META honest about which catalogues exist", () => {
    // A locale advertised as authored must have a file, and a locale marked
    // fallback must not have one. Otherwise the switcher lies to the user
    // about what language they are about to get.
    for (const locale of LOCALES) {
      const hasFile = existsSync(path.join(MESSAGES_DIR, `${locale}.json`));
      const claimed = LOCALE_META[locale].catalogue === "authored";
      expect(hasFile, `${locale}: catalogue flag says "${LOCALE_META[locale].catalogue}"`).toBe(
        claimed,
      );
    }
  });

  it("gives every authored locale the full citizen-facing safety vocabulary", () => {
    // These are the strings a person reads when deciding whether to leave their
    // house. A partially authored catalogue may omit interface furniture, but
    // never these.
    const authored = LOCALES.filter((l) => LOCALE_META[l].catalogue === "authored");
    expect(authored.length).toBeGreaterThan(1);

    for (const locale of authored) {
      const messages = catalogueFor(locale);
      for (const level of SEVERITY_LEVELS) {
        expect(messages?.severity?.[level], `${locale}.severity.${level}`).toBeTruthy();
        expect(messages?.severityAction?.[level], `${locale}.severityAction.${level}`).toBeTruthy();
      }
      expect(messages?.footer?.disclaimer, `${locale}.footer.disclaimer`).toBeTruthy();
    }
  });

  it("uses valid ICU plural syntax for the data-age string", () => {
    for (const locale of LOCALES) {
      const messages = catalogueFor(locale);
      const age = messages?.provenance?.age;
      if (!age) continue;
      expect(age, `${locale}.provenance.age`).toContain("{minutes, plural,");
      // Balanced braces, since a malformed pattern throws at render time and
      // would break the page in that language only.
      const opens = (age.match(/\{/g) ?? []).length;
      const closes = (age.match(/\}/g) ?? []).length;
      expect(opens, `${locale}.provenance.age brace balance`).toBe(closes);
    }
  });
});
