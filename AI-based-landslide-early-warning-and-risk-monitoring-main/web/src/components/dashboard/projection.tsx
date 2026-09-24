"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MethodNote } from "@/components/shell/method-note";
import { DataTable, ErrorRow, LoadingRow, Panel, StatTile } from "@/components/shell/panels";
import { apiUrl, bandCss } from "@/lib/geo";

/**
 * Projected slope stability over the next three days.
 *
 * This is the screen that gives the system lead time. Everything it needs was
 * already present and simply not connected: the forecast rainfall was already
 * being fetched and charted, and the physics layer already had an infiltration
 * model that turns rainfall into a wetness fraction. Joining them turns "here
 * is the state of the ground now" into "here is where it is heading".
 *
 * The limitation is displayed, not hidden. The infiltration model is monotonic
 * in rainfall, so it cannot reproduce the well-documented case of a slope
 * failing hours after the rain stops.
 */

interface ProjectionPoint {
  hours_ahead: number;
  valid_at: string | null;
  cumulative_rain_mm: number;
  wetness_fraction: number;
  unstable: number;
  marginal: number;
  stable: number;
  median_fos: number | null;
  min_fos: number | null;
}

interface ProjectionResponse {
  scored_units: number;
  current_wetness_fraction: number;
  lead_time_hours: number;
  first_deterioration_at_hours: number | null;
  peak_unstable: number;
  peak_at_hours: number | null;
  points: ProjectionPoint[];
  method: string;
  limitation: string;
}

export function ProjectionPanel() {
  const [data, setData] = useState<ProjectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(apiUrl("/projection"));
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        if (!cancelled) setData((await response.json()) as ProjectionResponse);
      } catch (caught) {
        if (!cancelled)
          setError(caught instanceof Error ? caught.message : "Could not build the projection");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const baseline = data?.points[0];
  const growth = data && baseline ? data.peak_unstable - baseline.unstable : null;

  return (
    <>
      <MethodNote summary="How the projection is computed, and what it cannot tell you">
        <p>{data?.method}</p>
        <p className="mt-2">{data?.limitation}</p>
      </MethodNote>

      {loading && <LoadingRow label="Running forecast rainfall through the physics layer" />}
      {error && <ErrorRow message={error} />}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Unstable now"
              value={baseline?.unstable ?? null}
              caption={`of ${data.scored_units.toLocaleString("en-IN")} slope units`}
              tone="red"
            />
            <StatTile
              label={`Unstable at +${data.peak_at_hours ?? 0} h`}
              value={data.peak_unstable}
              caption={growth !== null ? `${growth >= 0 ? "+" : ""}${growth} against now` : ""}
              tone="orange"
            />
            <StatTile
              label="First deterioration"
              value={data.first_deterioration_at_hours}
              unit="h"
              caption={
                data.first_deterioration_at_hours === null
                  ? "No worsening in the forecast window"
                  : "Ahead of now, from forecast rain"
              }
              tone="amber"
            />
            <StatTile
              label="Lead time"
              value={data.lead_time_hours}
              unit="h"
              caption="Forecast horizon available"
              tone="cyan"
            />
          </div>

          <Panel
            title="Where the ground is heading"
            description="Slope units by stability band at each forecast horizon. Marginal means a factor of safety between 1.0 and 1.3; unstable means below 1.0."
          >
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.points} margin={{ top: 8, right: 12, bottom: 24, left: 16 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border-subtle)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="hours_ahead"
                    tickFormatter={(value: number) => `+${value}h`}
                    tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
                    stroke="var(--border-default)"
                    height={44}
                    label={{
                      value: "Hours ahead",
                      position: "insideBottom",
                      offset: -4,
                      style: { fill: "var(--fg-muted)", fontSize: 11 },
                    }}
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
                    contentStyle={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-default)",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "var(--fg-primary)",
                    }}
                    labelFormatter={(value) => `+${value as number} hours`}
                  />
                  <Legend
                    verticalAlign="top"
                    height={28}
                    wrapperStyle={{ fontSize: 11, color: "var(--fg-secondary)" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="unstable"
                    stackId="bands"
                    name="Unstable"
                    stroke={bandCss("unstable")}
                    fill={bandCss("unstable")}
                    fillOpacity={0.55}
                  />
                  <Area
                    type="monotone"
                    dataKey="marginal"
                    stackId="bands"
                    name="Marginal"
                    stroke={bandCss("marginal")}
                    fill={bandCss("marginal")}
                    fillOpacity={0.4}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel
            title="Horizon by horizon"
            description="Every figure below is computed, not interpolated for display."
          >
            <DataTable
              rows={data.points}
              rowKey={(row) => String(row.hours_ahead)}
              columns={[
                {
                  key: "ahead",
                  header: "Horizon",
                  render: (row) => (
                    <span data-numeric className="font-medium">
                      {row.hours_ahead === 0 ? "now" : `+${row.hours_ahead} h`}
                    </span>
                  ),
                },
                {
                  key: "rain",
                  header: "Cumulative rain",
                  align: "right",
                  render: (row) => <span data-numeric>{row.cumulative_rain_mm.toFixed(1)} mm</span>,
                },
                {
                  key: "wetness",
                  header: "Profile wetness",
                  align: "right",
                  render: (row) => (
                    <span data-numeric>{(row.wetness_fraction * 100).toFixed(1)}%</span>
                  ),
                },
                {
                  key: "unstable",
                  header: "Unstable",
                  align: "right",
                  render: (row) => (
                    <span data-numeric style={{ color: bandCss("unstable") }}>
                      {row.unstable.toLocaleString("en-IN")}
                    </span>
                  ),
                },
                {
                  key: "marginal",
                  header: "Marginal",
                  align: "right",
                  render: (row) => <span data-numeric>{row.marginal.toLocaleString("en-IN")}</span>,
                },
                {
                  key: "median",
                  header: "Median FoS",
                  align: "right",
                  render: (row) => <span data-numeric>{row.median_fos?.toFixed(3) ?? "—"}</span>,
                },
              ]}
            />
          </Panel>
        </>
      )}
    </>
  );
}
