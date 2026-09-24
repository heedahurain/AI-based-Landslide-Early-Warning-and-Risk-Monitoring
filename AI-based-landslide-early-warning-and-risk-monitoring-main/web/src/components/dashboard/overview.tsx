"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight } from "lucide-react";

import { Link } from "@/i18n/navigation";
import { PageHeader } from "@/components/shell/app-shell";
import { MethodNote } from "@/components/shell/method-note";
import {
  DataTable,
  ErrorRow,
  LoadingRow,
  Panel,
  SplitBar,
  StatTile,
} from "@/components/shell/panels";
import { apiUrl, bandCss, type FactorOfSafetyResponse, type LithologyOption } from "@/lib/geo";

interface WeatherSummary {
  status: string;
  age_minutes: number;
  rainfall_24h_mm: number;
  rainfall_72h_mm: number;
  rainfall_next_24h_mm: number;
  suggested_wetness_fraction: number;
  current_soil_moisture: { depth: string; volumetric_water_content: number | null }[];
}

interface ConnectivitySummary {
  segments_total: number;
  segments_at_risk: number;
  length_at_risk_km: number;
  facilities_total: number;
  facilities_cut_off: number;
}

/**
 * Situation overview.
 *
 * Answers, in order, the four questions an officer opens a console to ask:
 * how much rain has fallen, how wet is the ground, how many slopes have lost
 * their margin, and what does that do to the roads.
 */
export function Overview() {
  const [weather, setWeather] = useState<WeatherSummary | null>(null);
  const [physics, setPhysics] = useState<FactorOfSafetyResponse | null>(null);
  const [roads, setRoads] = useState<ConnectivitySummary | null>(null);
  const [lithologies, setLithologies] = useState<LithologyOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        // Live rainfall first: the wetness it implies drives everything below,
        // so the physics is run against observed conditions rather than an
        // arbitrary scenario.
        const weatherResponse = await fetch(apiUrl("/weather/forecast"));
        const weatherData = weatherResponse.ok
          ? ((await weatherResponse.json()) as WeatherSummary)
          : null;
        if (cancelled) return;
        setWeather(weatherData);

        const wetness = weatherData?.suggested_wetness_fraction ?? 0.5;

        const [physicsResponse, roadsResponse, lithologyResponse] = await Promise.all([
          fetch(apiUrl(`/risk/factor-of-safety?wetness=${wetness}`)),
          fetch(apiUrl(`/connectivity/roads?wetness=${wetness}`)),
          fetch(apiUrl("/risk/lithology-classes")),
        ]);
        if (cancelled) return;

        if (physicsResponse.ok)
          setPhysics((await physicsResponse.json()) as FactorOfSafetyResponse);
        if (roadsResponse.ok) setRoads((await roadsResponse.json()) as ConnectivitySummary);
        if (lithologyResponse.ok)
          setLithologies((await lithologyResponse.json()) as LithologyOption[]);
      } catch (caught) {
        if (!cancelled)
          setError(
            caught instanceof Error
              ? `${caught.message}. Is the API running on ${apiUrl("")}?`
              : "Could not load the situation summary",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const summary = physics?.summary;
  const wetnessPct = weather ? Math.round(weather.suggested_wetness_fraction * 100) : null;

  // Stability under each material class, which is the comparison that matters
  // most on this terrain.
  const [byMaterial, setByMaterial] = useState<
    { name: string; unstable: number; marginal: number }[]
  >([]);

  useEffect(() => {
    if (!lithologies.length || !weather) return;
    let cancelled = false;

    void (async () => {
      const wetness = weather.suggested_wetness_fraction;
      const results = await Promise.all(
        lithologies.map(async (option) => {
          try {
            const response = await fetch(
              apiUrl(
                `/risk/factor-of-safety?lithology=${encodeURIComponent(option.key)}&wetness=${wetness}`,
              ),
            );
            if (!response.ok) return null;
            const payload = (await response.json()) as FactorOfSafetyResponse;
            return {
              name: option.name.split(",")[0]!,
              unstable: payload.summary.unstable,
              marginal: payload.summary.marginal,
            };
          } catch {
            return null;
          }
        }),
      );
      if (!cancelled)
        setByMaterial(
          results.filter(
            (r): r is { name: string; unstable: number; marginal: number } => r !== null,
          ),
        );
    })();

    return () => {
      cancelled = true;
    };
  }, [lithologies, weather]);

  return (
    <>
      <PageHeader
        title="Situation overview"
        description="Live rainfall and soil moisture from Open-Meteo, run through the physics layer over 14,714 slope units in the Noney and Tupul pilot area."
      >
        <Link
          href="/map"
          className="inline-flex h-9 items-center gap-2 rounded-[var(--radius-md)] bg-[var(--accent)] px-4 text-[length:var(--text-sm)] font-medium text-[var(--accent-fg)] hover:bg-[var(--accent-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
        >
          Open the map
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </PageHeader>

      <div className="space-y-5 p-6">
        {error && <ErrorRow message={error} />}

        <MethodNote summary="Physics layer only, not a forecast">
          <p>
            No learned model has been trained. Stability comes from the infinite-slope factor of
            safety, computed at the wetness implied by observed soil moisture.
          </p>
          <p>
            That makes it a statement about conditions now, not a prediction of whether a slope will
            fail. Geotechnical parameters are regional class averages and soil depth is a terrain
            proxy, so treat every figure as a range.
          </p>
        </MethodNote>

        {/* ------------------------------------------------ headline ---- */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Rain, last 24 hours"
            value={weather?.rainfall_24h_mm ?? null}
            unit="mm"
            caption={
              weather
                ? `Open-Meteo, ${weather.status}, ${weather.age_minutes} min old`
                : "from Open-Meteo"
            }
            tone="cyan"
            loading={loading}
          />
          <StatTile
            label="Rain, last 72 hours"
            value={weather?.rainfall_72h_mm ?? null}
            unit="mm"
            caption="Antecedent rainfall drives pore pressure"
            tone="cyan"
            loading={loading}
          />
          <StatTile
            label="Profile wetness"
            value={wetnessPct}
            unit="%"
            caption="From deep soil moisture, assumed saturation 0.45 m³/m³"
            tone={wetnessPct !== null && wetnessPct > 70 ? "orange" : "default"}
            loading={loading}
          />
          <StatTile
            label="Slopes below FoS 1.3"
            value={summary ? summary.unstable + summary.marginal : null}
            caption={summary ? `of ${summary.scored.toLocaleString()} scored units` : undefined}
            tone={summary && summary.unstable > 0 ? "red" : "amber"}
            loading={loading}
          />
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          {/* --------------------------------------------- stability --- */}
          <Panel
            title="Stability right now"
            description={
              physics
                ? `${physics.lithology.name}, ${Math.round(physics.wetness_fraction * 100)}% saturated`
                : "physics layer"
            }
          >
            {loading && <LoadingRow />}
            {summary && (
              <>
                <SplitBar
                  segments={[
                    { label: "Unstable", value: summary.unstable, colour: bandCss("unstable") },
                    { label: "Marginal", value: summary.marginal, colour: bandCss("marginal") },
                    { label: "Stable", value: summary.stable, colour: bandCss("stable") },
                  ]}
                />
                <dl className="mt-4 grid grid-cols-3 gap-3">
                  <Figure
                    label="Unstable"
                    hint="FoS below 1.0"
                    value={summary.unstable}
                    colour={bandCss("unstable")}
                  />
                  <Figure
                    label="Marginal"
                    hint="1.0 to 1.3"
                    value={summary.marginal}
                    colour={bandCss("marginal")}
                  />
                  <Figure
                    label="Stable"
                    hint="above 1.3"
                    value={summary.stable}
                    colour={bandCss("stable")}
                  />
                </dl>
                <p
                  data-numeric
                  className="mt-4 text-[length:var(--text-xs)] text-[var(--fg-secondary)]"
                >
                  Median factor of safety {summary.median_fos}, lowest {summary.min_fos}
                </p>
              </>
            )}
          </Panel>

          {/* ------------------------------------------------- roads ---- */}
          <Panel title="Road access" description="Segments threatened by the slopes above them">
            {loading && <LoadingRow />}
            {roads && (
              <div className="grid gap-4 sm:grid-cols-2">
                <StatTile
                  label="Segments at risk"
                  value={roads.segments_at_risk}
                  caption={`of ${roads.segments_total.toLocaleString()} in the pilot area`}
                  tone="orange"
                />
                <StatTile
                  label="Road length at risk"
                  value={roads.length_at_risk_km}
                  unit="km"
                  caption="Sum of threatened segments"
                  tone="orange"
                />
                <StatTile
                  label="Facilities affected"
                  value={roads.facilities_cut_off}
                  caption={`of ${roads.facilities_total} hospitals, schools and stations`}
                  tone="red"
                />
                <div className="flex items-end">
                  <Link
                    href="/dashboard/roads"
                    className="text-[length:var(--text-sm)] font-medium text-[var(--sev-cyan-text)] hover:underline"
                  >
                    See which roads →
                  </Link>
                </div>
              </div>
            )}
          </Panel>
        </div>

        {/* -------------------------------------------- by material ---- */}
        <Panel
          title="Which material fails first"
          description="The same 14,714 slopes, same wetness, scored against each material class. Both bands are shown because the headline counts above are marginal, factor of safety below 1.3, while unstable means below 1.0. This spread is the dominant uncertainty in the model."
        >
          {byMaterial.length === 0 ? (
            <LoadingRow label="Scoring each material class" />
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byMaterial} margin={{ top: 8, right: 8, bottom: 28, left: 16 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border-subtle)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
                    stroke="var(--border-default)"
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={78}
                  />
                  <YAxis
                    tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
                    stroke="var(--border-default)"
                    width={64}
                    label={{
                      value: "Slope units",
                      angle: -90,
                      position: "insideLeft",
                      style: { fill: "var(--fg-muted)", fontSize: 11, textAnchor: "middle" },
                    }}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--bg-elevated)" }}
                    contentStyle={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-default)",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "var(--fg-primary)",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: "var(--fg-secondary)" }} />
                  <Bar
                    dataKey="unstable"
                    stackId="bands"
                    name="Unstable, FoS below 1.0"
                    fill={bandCss("unstable")}
                  />
                  <Bar
                    dataKey="marginal"
                    stackId="bands"
                    name="Marginal, FoS 1.0 to 1.3"
                    fill={bandCss("marginal")}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        {/* -------------------------------------------- soil profile --- */}
        <Panel title="Soil moisture profile" description="Observed now, by depth, from Open-Meteo">
          {loading && <LoadingRow />}
          {weather && (
            <DataTable
              rows={weather.current_soil_moisture}
              rowKey={(row) => row.depth}
              columns={[
                { key: "depth", header: "Depth", render: (row) => row.depth },
                {
                  key: "vwc",
                  header: "Water content",
                  align: "right",
                  render: (row) => (
                    <span data-numeric>
                      {row.volumetric_water_content === null
                        ? "—"
                        : `${row.volumetric_water_content.toFixed(3)} m³/m³`}
                    </span>
                  ),
                },
                {
                  key: "bar",
                  header: "Relative to saturation",
                  render: (row) => {
                    const pct = Math.min(
                      100,
                      Math.round(((row.volumetric_water_content ?? 0) / 0.45) * 100),
                    );
                    return (
                      <span className="flex items-center gap-2">
                        <span className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                          <span
                            className="block h-full rounded-full bg-[var(--sev-cyan-mark)]"
                            style={{ width: `${pct}%` }}
                          />
                        </span>
                        <span data-numeric className="text-[var(--fg-muted)]">
                          {pct}%
                        </span>
                      </span>
                    );
                  },
                },
              ]}
            />
          )}
        </Panel>
      </div>
    </>
  );
}

function Figure({
  label,
  hint,
  value,
  colour,
}: {
  label: string;
  hint: string;
  value: number;
  colour: string;
}) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
        <span aria-hidden="true" className="size-2 rounded-full" style={{ background: colour }} />
        {label}
      </dt>
      <dd
        data-numeric
        className="mt-1 text-[length:var(--text-xl)] font-semibold"
        style={{ color: colour }}
      >
        {value.toLocaleString()}
      </dd>
      <p className="text-[length:var(--text-2xs)] text-[var(--fg-muted)]">{hint}</p>
    </div>
  );
}
