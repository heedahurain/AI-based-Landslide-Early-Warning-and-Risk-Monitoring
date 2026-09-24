import { ArrowLeft } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataChip } from "@/components/ui/data-chip";
import { LanguageSwitcher } from "@/components/language-switcher";
import { SeverityChip } from "@/components/ui/severity-chip";
import { ThemeToggle } from "@/components/theme-toggle";
import { SEVERITY_LEVELS } from "@/lib/severity";

/**
 * Build status page.
 *
 * This is not a dashboard and does not pretend to be one. No model has been
 * trained, so there is no risk number anywhere on it. What it does show is
 * what has actually been built, and the data-source probe results measured
 * when the repository was set up.
 *
 * It is linked from the landing page so a judge can check our claims rather
 * than take them on trust, which is the whole argument of the project.
 */

/**
 * Probe results measured from the build machine on 2026-09-08 and recorded in
 * docs/DATA_SOURCES.md. These are build-time facts about endpoint reachability,
 * not live values, which is why none of them carries a LIVE chip.
 */
const PROBED_SOURCES = [
  {
    name: "Open-Meteo Forecast",
    detail: "Rainfall and five soil-moisture layers",
    status: "verified",
  },
  { name: "Open-Meteo ERA5 Archive", detail: "Antecedent rainfall history", status: "verified" },
  { name: "NASA POWER", detail: "Daily precipitation cross-check", status: "verified" },
  {
    name: "Planetary Computer STAC",
    detail: "Copernicus DEM, Sentinel-1, Sentinel-2",
    status: "verified",
  },
  {
    name: "OpenStreetMap Overpass",
    detail: "Road graph and critical facilities",
    status: "verified",
  },
  { name: "OpenTopography", detail: "Secondary elevation source", status: "key-required" },
  { name: "GPM IMERG", detail: "Satellite rainfall, Earthdata login", status: "key-required" },
  { name: "NASA COOLR", detail: "Historical landslide inventory", status: "unverified" },
] as const;

const STATUS_STYLE = {
  verified: "text-[var(--sev-green-text)]",
  "key-required": "text-[var(--sev-amber-text)]",
  unverified: "text-[var(--fg-muted)]",
} as const;

export default async function StatusPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations();

  return (
    <div className="min-h-dvh bg-[var(--bg-base)]">
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      <header className="sticky top-0 z-[var(--z-topbar)] border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]/95 backdrop-blur">
        <div className="mx-auto flex h-[var(--topbar-h)] max-w-5xl items-center gap-4 px-6">
          <div className="flex min-w-0 flex-col">
            <span className="text-[length:var(--text-md)] leading-none font-semibold tracking-[var(--tracking-tight)]">
              {t("app.name")}
            </span>
            <span className="truncate text-[length:var(--text-2xs)] text-[var(--fg-muted)]">
              {t("app.problemStatement")}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto max-w-5xl px-6 py-12">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-[length:var(--text-xs)] text-[var(--fg-muted)] transition-colors hover:text-[var(--fg-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
        >
          <ArrowLeft aria-hidden="true" className="size-3.5" />
          {t("home.backToLanding")}
        </Link>
        <p className="mt-6 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--sev-cyan-text)] uppercase">
          {t("home.phaseLabel")}
        </p>
        <h1 className="mt-3 text-[length:var(--text-3xl)] leading-[var(--leading-tight)] font-semibold tracking-[var(--tracking-tight)]">
          {t("home.heading")}
        </h1>
        <p className="mt-4 max-w-2xl text-[length:var(--text-md)] leading-[var(--leading-relaxed)] text-[var(--fg-secondary)]">
          {t("app.tagline")}. {t("home.intro")}
        </p>

        <p className="mt-6 max-w-2xl rounded-[var(--radius-lg)] border border-[var(--sev-amber-outline)] bg-[var(--sev-amber-tint)] px-4 py-3 text-[length:var(--text-sm)] text-[var(--sev-amber-text)]">
          {t("home.notLiveYet")}
        </p>

        <section className="mt-12" aria-labelledby="severity-heading">
          <h2
            id="severity-heading"
            className="text-[length:var(--text-lg)] font-semibold tracking-[var(--tracking-tight)]"
          >
            {t("home.severityHeading")}
          </h2>
          <div className="mt-4 flex flex-wrap gap-3">
            {SEVERITY_LEVELS.map((level) => (
              <SeverityChip key={level} severity={level} pulse={level === "red"} />
            ))}
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {SEVERITY_LEVELS.map((level) => (
              <Card key={level}>
                <CardContent className="flex items-start gap-3">
                  <SeverityChip severity={level} showIcon={false} />
                  <p className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                    {t(`severityAction.${level}`)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="mt-12" aria-labelledby="sources-heading">
          <div className="flex flex-wrap items-center gap-3">
            <h2
              id="sources-heading"
              className="text-[length:var(--text-lg)] font-semibold tracking-[var(--tracking-tight)]"
            >
              {t("home.sourcesHeading")}
            </h2>
            <DataChip status="simulated" source="Build-time probe, not a live reading" />
          </div>
          <p className="mt-2 max-w-2xl text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
            {t("home.sourcesNote")}
          </p>

          <Card className="mt-4 overflow-hidden">
            <ul className="divide-y divide-[var(--border-subtle)]">
              {PROBED_SOURCES.map((source) => (
                <li key={source.name} className="flex items-center gap-4 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[length:var(--text-sm)] font-medium">{source.name}</p>
                    <p className="text-[length:var(--text-xs)] text-[var(--fg-muted)]">
                      {source.detail}
                    </p>
                  </div>
                  <span
                    data-numeric
                    className={`text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] uppercase ${STATUS_STYLE[source.status]}`}
                  >
                    {source.status}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>

        <section className="mt-12" aria-labelledby="built-heading">
          <h2
            id="built-heading"
            className="text-[length:var(--text-lg)] font-semibold tracking-[var(--tracking-tight)]"
          >
            {t("home.builtHeading")}
          </h2>
          <Card className="mt-4">
            <CardContent>
              <ul className="grid gap-2 text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                {(["monorepo", "docs", "stack", "tokens", "i18n"] as const).map((key) => (
                  <li key={key} className="flex items-start gap-2">
                    <span
                      aria-hidden="true"
                      className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--sev-green-mark)] ring-1 ring-[var(--sev-green-outline)]"
                    />
                    {t(`home.built.${key}`)}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>

        <section className="mt-12" aria-labelledby="next-heading">
          <Card>
            <CardHeader>
              <CardTitle id="next-heading">{t("home.nextHeading")}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                {t("home.next")}
              </p>
            </CardContent>
          </Card>
        </section>
      </main>

      <footer className="border-t border-[var(--border-subtle)] px-6 py-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-2">
          <p className="text-[length:var(--text-xs)] text-[var(--fg-muted)]">
            {t("footer.disclaimer")}
          </p>
          <p className="text-[length:var(--text-2xs)] text-[var(--fg-muted)]">
            {t("app.ministry")} · <span data-numeric>{t("footer.phase")}</span>
          </p>
        </div>
      </footer>
    </div>
  );
}
