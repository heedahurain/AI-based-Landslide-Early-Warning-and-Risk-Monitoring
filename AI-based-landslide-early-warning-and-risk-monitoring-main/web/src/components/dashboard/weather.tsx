"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/shell/app-shell";
import { ErrorRow, LoadingRow, Panel, StatTile } from "@/components/shell/panels";
import { apiUrl } from "@/lib/geo";
import { ProjectionPanel } from "@/components/dashboard/projection";

interface WeatherResponse {
  status: string;
  fetched_at: string;
  age_minutes: number;
  source: string;
  timezone: string | null;
  times: string[];
  precipitation_mm: (number | null)[];
  precipitation_probability: (number | null)[];
  humidity_pct: (number | null)[];
  soil_moisture_surface: (number | null)[];
  soil_moisture_deep: (number | null)[];
  rainfall_24h_mm: number;
  rainfall_72h_mm: number;
  rainfall_next_24h_mm: number;
  current_soil_moisture: { depth: string; volumetric_water_content: number | null }[];
  suggested_wetness_fraction: number;
  note: string;
}

const PAST_DAYS = 7;

/**
 * Weather and soil moisture.
 *
 * This is the only screen driven by genuinely live data today. Everything is
 * labelled with its provenance and its age, and the boundary between observed
 * and forecast is drawn on the chart rather than left for the reader to guess.
 */
export function WeatherDashboard() {
  const [data, setData] = useState<WeatherResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(apiUrl(`/weather/forecast?past_days=${PAST_DAYS}`));
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        if (!cancelled) setData((await response.json()) as WeatherResponse);
      } catch (caught) {
        if (!cancelled)
          setError(caught instanceof Error ? caught.message : "Could not load weather");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const series = useMemo(() => {
    if (!data) return [];
    return data.times.map((time, index) => ({
      time,
      label: time.slice(5, 16).replace("T", " "),
      rain: data.precipitation_mm[index] ?? 0,
      probability: data.precipitation_probability[index] ?? null,
      surface: data.soil_moisture_surface[index] ?? null,
      deep: data.soil_moisture_deep[index] ?? null,
      isForecast: index >= PAST_DAYS * 24,
    }));
  }, [data]);

  const boundaryLabel = series[PAST_DAYS * 24]?.label;

  return (
    <>
      <PageHeader
        title="Weather and soil moisture"
        description="Hourly rainfall and modelled soil moisture at the centre of the pilot area, from Open-Meteo."
      >
        {data && (
          <span
            className={`inline-flex items-center gap-1.5 rounded-[var(--radius-full)] border px-2.5 py-1 text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] uppercase ${
              data.status === "live"
                ? "border-[var(--sev-green-outline)] text-[var(--sev-green-text)]"
                : "border-[var(--sev-amber-outline)] text-[var(--sev-amber-text)]"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                data.status === "live" ? "bg-[var(--sev-green-mark)]" : "bg-[var(--sev-amber-mark)]"
              }`}
            />
            {data.status}
            {data.status === "cached" && <span data-numeric>{data.age_minutes} min</span>}
          </span>
        )}
      </PageHeader>

      <div className="space-y-5 p-6">
        {error && <ErrorRow message={error} />}
        <ProjectionPanel />

        {loading && <LoadingRow label="Fetching rainfall from Open-Meteo" />}

        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile
                label="Rain, last 24 hours"
                value={data.rainfall_24h_mm}
                unit="mm"
                caption="Observed"
                tone="cyan"
              />
              <StatTile
                label="Rain, last 72 hours"
                value={data.rainfall_72h_mm}
                unit="mm"
                caption="The antecedent window that matters most"
                tone="cyan"
              />
              <StatTile
                label="Forecast, next 24 hours"
                value={data.rainfall_next_24h_mm}
                unit="mm"
                caption="Open-Meteo forecast"
                tone={data.rainfall_next_24h_mm > 50 ? "orange" : "default"}
              />
              <StatTile
                label="Implied wetness"
                value={Math.round(data.suggested_wetness_fraction * 100)}
                unit="%"
                caption="Feeds the physics layer"
                tone={data.suggested_wetness_fraction > 0.7 ? "orange" : "default"}
              />
            </div>

            <Panel
              title="Hourly rainfall"
              description={`Seven days observed, three days forecast. ${
                boundaryLabel ? `The dashed line at ${boundaryLabel} is now.` : ""
              }`}
            >
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={series} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border-subtle)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "var(--fg-muted)", fontSize: 10 }}
                      stroke="var(--border-default)"
                      interval={23}
                    />
                    <YAxis
                      tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
                      stroke="var(--border-default)"
                      label={{
                        value: "mm",
                        angle: -90,
                        position: "insideLeft",
                        fill: "var(--fg-muted)",
                        fontSize: 11,
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
                    {boundaryLabel && (
                      <ReferenceLine
                        x={boundaryLabel}
                        stroke="var(--sev-cyan-mark)"
                        strokeDasharray="4 4"
                        label={{ value: "now", fill: "var(--sev-cyan-text)", fontSize: 11 }}
                      />
                    )}
                    <Bar dataKey="rain" name="Rainfall" fill="var(--sev-cyan-mark)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel
              title="Soil moisture"
              description="Surface and deep layers. Deep moisture lags rainfall and is what sustains pore pressure."
            >
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border-subtle)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "var(--fg-muted)", fontSize: 10 }}
                      stroke="var(--border-default)"
                      interval={23}
                    />
                    <YAxis
                      tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
                      stroke="var(--border-default)"
                      domain={[0, 0.5]}
                      label={{
                        value: "m³/m³",
                        angle: -90,
                        position: "insideLeft",
                        fill: "var(--fg-muted)",
                        fontSize: 11,
                      }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border-default)",
                        borderRadius: 8,
                        fontSize: 12,
                        color: "var(--fg-primary)",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, color: "var(--fg-secondary)" }} />
                    <Area
                      type="monotone"
                      dataKey="surface"
                      name="Surface, 0 to 1 cm"
                      stroke="var(--sev-cyan-mark)"
                      fill="var(--sev-cyan-mark)"
                      fillOpacity={0.2}
                    />
                    <Area
                      type="monotone"
                      dataKey="deep"
                      name="Deep, 27 to 81 cm"
                      stroke="var(--sev-orange-mark)"
                      fill="var(--sev-orange-mark)"
                      fillOpacity={0.2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-3 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
                {data.note}
              </p>
            </Panel>
          </>
        )}
      </div>
    </>
  );
}
