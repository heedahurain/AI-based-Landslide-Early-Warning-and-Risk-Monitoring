import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";

import { routing, type Locale } from "./routing";

type Messages = Record<string, unknown>;

async function load(locale: string): Promise<Messages> {
  const mod = (await import(`../../messages/${locale}.json`)) as { default: Messages };
  return mod.default;
}

/**
 * Deep-merge an authored catalogue over the English baseline.
 *
 * Several locales are only partially authored while native-speaker review is
 * pending. Merging over English means a missing key renders readable English
 * rather than a raw key or an empty string, and it means a partially reviewed
 * catalogue can ship the strings that *have* been reviewed without waiting for
 * the rest. docs/TRANSLATIONS.md records exactly what is authored.
 */
function mergeOverBaseline(baseline: Messages, override: Messages): Messages {
  const out: Messages = { ...baseline };
  for (const [key, value] of Object.entries(override)) {
    const existing = out[key];
    if (
      typeof value === "object" &&
      value !== null &&
      !Array.isArray(value) &&
      typeof existing === "object" &&
      existing !== null &&
      !Array.isArray(existing)
    ) {
      out[key] = mergeOverBaseline(existing as Messages, value as Messages);
    } else {
      out[key] = value;
    }
  }
  return out;
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale: Locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;

  const baseline = await load(routing.defaultLocale);
  if (locale === routing.defaultLocale) {
    return { locale, messages: baseline };
  }

  try {
    const authored = await load(locale);
    return { locale, messages: mergeOverBaseline(baseline, authored) };
  } catch {
    // No catalogue authored yet for this locale. English is the honest
    // fallback; inventing text in a language nobody on the team reads is not.
    return { locale, messages: baseline };
  }
});
