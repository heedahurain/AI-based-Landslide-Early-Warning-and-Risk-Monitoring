import dynamic from "next/dynamic";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArchitectureDiagram } from "@/components/landing/architecture-diagram";
import { CountUp } from "@/components/landing/count-up";
import { LanguageSwitcher } from "@/components/language-switcher";
import { LazyMount } from "@/components/landing/lazy-mount";
import { Reveal } from "@/components/landing/reveal";
import { ThemeToggle } from "@/components/theme-toggle";
import { Link } from "@/i18n/navigation";

/**
 * The landing page.
 *
 * Written in a different register from the operations console on purpose. The
 * console is dense, flat and monospaced because it is read under pressure. This
 * page is read at leisure by someone deciding whether the project is serious,
 * so it uses a display serif, large real imagery and a great deal of air.
 *
 * The imagery is the live elevation model of the ground the system monitors,
 * not stock photography. That keeps the page honest about its subject and
 * avoids putting someone else's licensed photograph on a government pitch.
 *
 * Every number here is measured. Nothing on this page is a forecast.
 */

const HeroTerrain = dynamic(() =>
  import("@/components/landing/hero-terrain").then((m) => m.HeroTerrain),
);

const TerrainStrip = dynamic(() =>
  import("@/components/landing/terrain-strip").then((m) => m.TerrainStrip),
);

const LAYERS = [
  { number: "01", key: "physics", accent: "var(--sev-cyan-mark)" },
  { number: "02", key: "empirical", accent: "var(--sev-green-mark)" },
  { number: "03", key: "ml", accent: "var(--sev-amber-mark)" },
  { number: "04", key: "deformation", accent: "var(--sev-orange-mark)" },
] as const;

const DASHBOARDS = [
  { key: "d1", href: "/map" },
  { key: "d2", href: "/dashboard/roads" },
  { key: "d3", href: "/dashboard/weather" },
  { key: "d4", href: "/dashboard/response" },
  { key: "d5", href: "/dashboard/reports" },
  { key: "d6", href: "/portal" },
] as const;

const TECH = [
  "Next.js 15",
  "React 19",
  "MapLibre GL v5",
  "deck.gl v9",
  "FastAPI",
  "PostGIS",
  "TimescaleDB",
  "Open-Meteo",
  "Copernicus DEM",
  "OpenStreetMap",
  "CAP v1.2",
];

export default async function LandingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations();

  return (
    <div className="editorial-ground grain relative min-h-dvh">
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      {/* ================================================================ */}
      {/* Hero                                                             */}
      {/* ================================================================ */}
      <section className="relative isolate flex min-h-dvh flex-col">
        <HeroTerrain />

        <header className="relative z-10 mx-auto flex w-full max-w-[84rem] items-center gap-4 px-6 py-6 lg:px-10">
          <div className="flex min-w-0 items-baseline gap-3">
            <span className="display text-[length:var(--text-lg)] leading-none">
              {t("app.name")}
            </span>
            <span className="hidden text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase sm:block">
              {t("app.problemStatement")}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <div className="relative z-10 mx-auto flex w-full max-w-[84rem] flex-1 flex-col justify-center px-6 pb-28 lg:px-10">
          <Reveal>
            <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--sev-cyan-text)] uppercase">
              {t("landing.eyebrow")}
            </p>

            <h1 className="display mt-7 max-w-[18ch] text-[clamp(2.75rem,7vw,5.5rem)] leading-[0.98] text-balance">
              {t("landing.headline")}
            </h1>

            <p className="mt-8 max-w-[54ch] text-[length:var(--text-lg)] leading-[1.7] text-[var(--fg-secondary)]">
              {t("landing.subhead")}
            </p>
          </Reveal>

          <Reveal index={2}>
            <div className="mt-11 flex flex-wrap items-center gap-3">
              <Link
                href="/dashboard"
                className="group inline-flex h-12 items-center gap-2.5 rounded-[var(--radius-full)] bg-[var(--fg-primary)] px-7 text-[length:var(--text-base)] font-medium text-[var(--bg-base)] transition-transform duration-[var(--duration-fast)] ease-[var(--ease-out)] hover:scale-[1.02] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)] active:scale-[0.99]"
              >
                Enter the console
                <ArrowRight
                  aria-hidden="true"
                  className="size-4 transition-transform duration-[var(--duration-fast)] group-hover:translate-x-0.5"
                />
              </Link>
              <Link
                href="/map"
                className="inline-flex h-12 items-center gap-2 rounded-[var(--radius-full)] border border-[var(--border-strong)] px-7 text-[length:var(--text-base)] font-medium backdrop-blur transition-colors duration-[var(--duration-fast)] hover:border-[var(--fg-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
              >
                {t("landing.ctaMap")}
              </Link>
            </div>
          </Reveal>

          <p className="mt-14 max-w-[42ch] text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
            {t("landing.terrainCaption")}
          </p>
        </div>
      </section>

      <main id="main">
        {/* ============================================================== */}
        {/* Measured figures                                               */}
        {/* ============================================================== */}
        <section className="relative border-y border-[var(--border-subtle)] bg-[var(--bg-surface)]/40 backdrop-blur">
          <div className="mx-auto grid max-w-[84rem] grid-cols-2 gap-y-10 px-6 py-14 lg:grid-cols-4 lg:px-10">
            <Figure
              value={14714}
              label="Slope units delineated"
              caption="Hydrological hillslopes, not grid cells"
            />
            <Figure
              value={4486}
              suffix=" km²"
              label="Area processed"
              caption="Pilot around Tupul and Noney"
            />
            <Figure value={8} label="States in scope" caption="The full North Eastern Region" />
            <Figure
              value={13}
              suffix="/15"
              label="Sources verified"
              caption="Contacted from the build machine, not assumed"
            />
          </div>
        </section>

        {/* ============================================================== */}
        {/* The problem                                                    */}
        {/* ============================================================== */}
        <section className="mx-auto max-w-[84rem] px-6 py-28 lg:px-10 lg:py-36">
          <div className="grid gap-14 lg:grid-cols-[0.85fr_1fr]">
            <Reveal>
              <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--sev-red-text)] uppercase">
                {t("landing.problemKicker")}
              </p>
              <h2 className="display mt-6 text-[clamp(2rem,3.6vw,3.25rem)] leading-[1.05] text-balance">
                {t("landing.problemHeading")}
              </h2>
            </Reveal>

            <Reveal index={1}>
              <p className="text-[length:var(--text-lg)] leading-[1.75] text-[var(--fg-secondary)]">
                {t("landing.problemBody")}
              </p>

              <div className="mt-12 grid gap-px overflow-hidden rounded-[var(--radius-lg)] bg-[var(--border-subtle)] sm:grid-cols-3">
                <Toll figure="55–61" label={t("landing.statTupulLabel")} />
                <Toll figure="20+" label={t("landing.statAizawlLabel")} />
                <Toll figure="2000–4000" unit="mm a year" label={t("landing.statRainfallLabel")} />
              </div>
            </Reveal>
          </div>
        </section>

        {/* ============================================================== */}
        {/* Terrain band                                                   */}
        {/* ============================================================== */}
        <section className="relative isolate h-[24rem] overflow-hidden md:h-[32rem]">
          <LazyMount className="absolute inset-0">
            <TerrainStrip center={[92.72, 25.57]} zoom={9.2} pitch={68} bearing={-24} />
          </LazyMount>
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,var(--bg-base),transparent_28%,transparent_58%,var(--bg-base))]" />
          <div className="relative z-10 mx-auto flex h-full max-w-[84rem] items-end px-6 pb-12 lg:px-10">
            <p className="display max-w-[24ch] text-[clamp(1.5rem,3vw,2.5rem)] leading-[1.15] text-balance">
              {t("landing.gapHeading")}
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-[84rem] px-6 py-24 lg:px-10">
          <Reveal>
            <p className="max-w-[62ch] text-[length:var(--text-lg)] leading-[1.75] text-[var(--fg-secondary)]">
              {t("landing.gapBody")}
            </p>
          </Reveal>
        </section>

        {/* ============================================================== */}
        {/* The engine                                                     */}
        {/* ============================================================== */}
        <section className="border-t border-[var(--border-subtle)] bg-[var(--bg-surface)]/30">
          <div className="mx-auto max-w-[84rem] px-6 py-28 lg:px-10 lg:py-36">
            <Reveal>
              <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--sev-cyan-text)] uppercase">
                {t("landing.engineKicker")}
              </p>
              <h2 className="display mt-6 max-w-[20ch] text-[clamp(2rem,3.6vw,3.25rem)] leading-[1.05] text-balance">
                {t("landing.engineHeading")}
              </h2>
              <p className="mt-6 max-w-[58ch] text-[length:var(--text-md)] leading-[1.7] text-[var(--fg-secondary)]">
                {t("landing.engineBody")}
              </p>
            </Reveal>

            <div className="mt-16 grid gap-px overflow-hidden rounded-[var(--radius-lg)] bg-[var(--border-subtle)] md:grid-cols-2">
              {LAYERS.map((layer, index) => (
                <Reveal key={layer.key} index={index}>
                  <article className="h-full bg-[var(--bg-base)] p-8 lg:p-10">
                    <div className="flex items-baseline gap-3">
                      <span
                        className="figure-lg text-[length:var(--text-lg)]"
                        style={{ color: layer.accent }}
                      >
                        {layer.number}
                      </span>
                      <h3 className="display text-[length:var(--text-xl)]">
                        {t(`landing.layer${cap(layer.key)}Name`)}
                      </h3>
                    </div>
                    <p className="mt-4 text-[length:var(--text-sm)] leading-[1.75] text-[var(--fg-secondary)]">
                      {t(`landing.layer${cap(layer.key)}Detail`)}
                    </p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ============================================================== */}
        {/* Architecture                                                   */}
        {/* ============================================================== */}
        <section className="mx-auto max-w-[84rem] px-6 py-28 lg:px-10">
          <Reveal>
            <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--fg-muted)] uppercase">
              {t("landing.architectureKicker")}
            </p>
            <h2 className="display mt-6 text-[clamp(1.75rem,3vw,2.75rem)] leading-[1.1]">
              {t("landing.architectureHeading")}
            </h2>
            <p className="mt-5 max-w-[58ch] text-[length:var(--text-md)] leading-[1.7] text-[var(--fg-secondary)]">
              {t("landing.architectureBody")}
            </p>
          </Reveal>
          <div className="mt-14">
            <ArchitectureDiagram />
          </div>
        </section>

        {/* ============================================================== */}
        {/* What is running                                                */}
        {/* ============================================================== */}
        <section className="border-t border-[var(--border-subtle)]">
          <div className="mx-auto max-w-[84rem] px-6 py-28 lg:px-10 lg:py-36">
            <Reveal>
              <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--sev-green-text)] uppercase">
                {t("landing.dashboardsKicker")}
              </p>
              <h2 className="display mt-6 text-[clamp(2rem,3.6vw,3.25rem)] leading-[1.05]">
                {t("landing.dashboardsHeading")}
              </h2>
            </Reveal>

            <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {DASHBOARDS.map((item, index) => (
                <Reveal key={item.key} index={index}>
                  <Link
                    href={item.href}
                    className="group flex h-full flex-col rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-7 transition-colors duration-[var(--duration-fast)] hover:border-[var(--border-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
                  >
                    <div className="flex items-start gap-3">
                      <h3 className="display text-[length:var(--text-lg)]">
                        {t(`landing.${item.key}Name`)}
                      </h3>
                      <ArrowUpRight
                        aria-hidden="true"
                        className="ml-auto size-4 shrink-0 text-[var(--fg-muted)] transition-transform duration-[var(--duration-fast)] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-[var(--fg-primary)]"
                      />
                    </div>
                    <p className="mt-3 text-[length:var(--text-sm)] leading-[1.7] text-[var(--fg-secondary)]">
                      {t(`landing.${item.key}Detail`)}
                    </p>
                  </Link>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ============================================================== */}
        {/* Government readiness                                           */}
        {/* ============================================================== */}
        <section className="relative isolate overflow-hidden border-t border-[var(--border-subtle)]">
          <LazyMount className="absolute inset-0">
            <TerrainStrip
              center={[94.35, 27.1]}
              zoom={8.6}
              pitch={62}
              bearing={18}
              drift={-0.005}
            />
          </LazyMount>
          <div className="absolute inset-0 bg-[var(--bg-base)]/80" />
          <div className="relative z-10 mx-auto max-w-[84rem] px-6 py-28 lg:px-10 lg:py-36">
            <Reveal>
              <p className="text-[length:var(--text-2xs)] font-medium tracking-[0.18em] text-[var(--sev-green-text)] uppercase">
                {t("landing.capKicker")}
              </p>
              <h2 className="display mt-6 max-w-[22ch] text-[clamp(2rem,3.6vw,3.25rem)] leading-[1.05] text-balance">
                {t("landing.capHeading")}
              </h2>
              <p className="mt-7 max-w-[60ch] text-[length:var(--text-md)] leading-[1.75] text-[var(--fg-secondary)]">
                {t("landing.capBody")}
              </p>
            </Reveal>

            <div className="rule-fade my-14" />

            <Reveal>
              <ul className="flex flex-wrap gap-2">
                {TECH.map((item) => (
                  <li
                    key={item}
                    className="rounded-[var(--radius-full)] border border-[var(--border-default)] px-3.5 py-1.5 text-[length:var(--text-xs)] text-[var(--fg-secondary)]"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </section>
      </main>

      {/* ================================================================ */}
      <footer className="border-t border-[var(--border-subtle)]">
        <div className="mx-auto max-w-[84rem] px-6 py-16 lg:px-10">
          <div className="flex flex-wrap items-end gap-8">
            <p className="display max-w-[20ch] text-[length:var(--text-2xl)] leading-[1.15]">
              {t("app.tagline")}
            </p>
            <Link
              href="/dashboard"
              className="ml-auto inline-flex h-11 items-center gap-2 rounded-[var(--radius-full)] border border-[var(--border-strong)] px-6 text-[length:var(--text-sm)] font-medium hover:border-[var(--fg-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
            >
              Enter the console
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>

          <div className="rule-fade my-10" />

          <p className="max-w-[70ch] text-[length:var(--text-xs)] leading-relaxed text-[var(--fg-muted)]">
            {t("footer.disclaimer")}
          </p>
          <p className="mt-3 text-[length:var(--text-2xs)] text-[var(--fg-muted)]">
            {t("app.ministry")} · {t("landing.footerNote")}
          </p>
        </div>
      </footer>
    </div>
  );
}

function cap(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function Figure({
  value,
  label,
  caption,
  suffix,
}: {
  value: number;
  label: string;
  caption: string;
  suffix?: string;
}) {
  return (
    <div className="px-2">
      <p className="figure-lg text-[clamp(2.25rem,4vw,3.5rem)] leading-none">
        <CountUp value={value} />
        {suffix && <span className="text-[0.5em] text-[var(--fg-secondary)]">{suffix}</span>}
      </p>
      <p className="mt-3 text-[length:var(--text-sm)] font-medium">{label}</p>
      <p className="mt-1 text-[length:var(--text-2xs)] text-[var(--fg-muted)]">{caption}</p>
    </div>
  );
}

function Toll({ figure, label, unit }: { figure: string; label: string; unit?: string }) {
  return (
    <div className="bg-[var(--bg-base)] p-6">
      <p className="figure-lg text-[length:var(--text-2xl)] leading-none text-[var(--sev-red-text)]">
        {figure}
      </p>
      {unit && <p className="mt-1 text-[length:var(--text-2xs)] text-[var(--fg-muted)]">{unit}</p>}
      <p className="mt-3 text-[length:var(--text-xs)] leading-relaxed text-[var(--fg-secondary)]">
        {label}
      </p>
    </div>
  );
}
