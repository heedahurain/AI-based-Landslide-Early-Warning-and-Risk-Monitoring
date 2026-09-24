import { defineRouting } from "next-intl/routing";

/**
 * Ten languages, eleven locale codes.
 *
 * Manipuri (Meiteilon) is written in two scripts that are both in active use:
 * the Bengali script (`mni`) and Meitei Mayek (`mni-Mtei`), which is the
 * official script taught in Manipur schools. Shipping only one would exclude
 * readers of the other, so both are first-class locales.
 *
 * Codes follow BCP 47 using ISO 639-3 where no two-letter code exists.
 */
export const LOCALES = [
  "en", // English
  "hi", // Hindi
  "as", // Assamese
  "bn", // Bengali
  "mni", // Manipuri / Meiteilon, Bengali script
  "mni-Mtei", // Manipuri / Meiteilon, Meitei Mayek script
  "lus", // Mizo
  "kha", // Khasi
  "nag", // Nagamese
  "ne", // Nepali
  "brx", // Bodo
] as const;

export type Locale = (typeof LOCALES)[number];

/**
 * Display metadata for the language switcher. `native` is what a speaker
 * actually calls the language, which is the only name that helps someone who
 * cannot read the current interface language.
 *
 * `catalogue` records how complete the message file is. Nothing here is
 * decorative: a locale marked `fallback` genuinely renders English, and
 * docs/TRANSLATIONS.md must agree with this table.
 */
export const LOCALE_META: Record<
  Locale,
  { native: string; english: string; script: string; catalogue: "authored" | "fallback" }
> = {
  en: { native: "English", english: "English", script: "Latin", catalogue: "authored" },
  hi: { native: "हिन्दी", english: "Hindi", script: "Devanagari", catalogue: "authored" },
  as: { native: "অসমীয়া", english: "Assamese", script: "Bengali-Assamese", catalogue: "authored" },
  bn: { native: "বাংলা", english: "Bengali", script: "Bengali-Assamese", catalogue: "authored" },
  ne: { native: "नेपाली", english: "Nepali", script: "Devanagari", catalogue: "authored" },
  mni: { native: "মৈতৈলোন্", english: "Manipuri", script: "Bengali", catalogue: "fallback" },
  "mni-Mtei": {
    native: "ꯃꯤꯇꯩ ꯂꯣꯟ",
    english: "Manipuri (Meitei Mayek)",
    script: "Meetei Mayek",
    catalogue: "fallback",
  },
  lus: { native: "Mizo ṭawng", english: "Mizo", script: "Latin", catalogue: "fallback" },
  kha: { native: "Ka Ktien Khasi", english: "Khasi", script: "Latin", catalogue: "fallback" },
  nag: { native: "Nagamese", english: "Nagamese", script: "Latin", catalogue: "fallback" },
  brx: { native: "बड़ो", english: "Bodo", script: "Devanagari", catalogue: "fallback" },
};

export const routing = defineRouting({
  locales: LOCALES,
  defaultLocale: "en",
  // The public citizen portal must live at "/" so a shared link is as short as
  // possible for someone on a slow connection, hence no prefix for English.
  localePrefix: "as-needed",
});
