"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/shell/app-shell";
import { MethodNote } from "@/components/shell/method-note";
import { DataTable, ErrorRow, LoadingRow, Panel, StatTile } from "@/components/shell/panels";
import { apiUrl, bandCss, type LithologyOption } from "@/lib/geo";
import { ASSUMED_WETNESS_FALLBACK, useLiveWetness } from "@/lib/use-live-wetness";
import { WetnessControl } from "@/components/shell/wetness-control";

const RoadsMap = dynamic(() => import("@/components/dashboard/roads-map").then((m) => m.RoadsMap), {
  ssr: false,
  loading: () => (
    <div className="flex h-80 items-center justify-center rounded-[var(--radius-lg)] border border-[var(--border-subtle)] text-[length:var(--text-xs)] text-[var(--fg-muted)]">
      Loading map
    </div>
  ),
});

interface RoadRisk {
  osm_id: string | null;
  name: string | null;
  highway_class: string;
  length_m: number;
  blockage_probability: number;
  expected_blockages: number;
  contributing_units: number;
}

type FeatureCollection = { type: "FeatureCollection"; features: unknown[] };

interface ConnectivityResponse {
  wetness_fraction: number;
  lithology: string;
  buffer_m: number;
  threshold: number;
  segments_total: number;
  segments_at_risk: number;
  length_at_risk_km: number;
  facilities_total: number;
  facilities_cut_off: number;
  by_class: Record<string, number>;
  top_segments: RoadRisk[];
  method: string;
}

/**
 * Road and access impact.
 *
 * The question this screen exists to answer is not "which road is steep" but
 * "which road is under a slope that is about to fail", and then "who loses
 * their route to a hospital when it does".
 */
export function RoadsDashboard() {
  const [data, setData] = useState<ConnectivityResponse | null>(null);
  const [lithologies, setLithologies] = useState<LithologyOption[]>([]);
  // Defaults to the per-unit assignment, matching the API default. Forcing one
  // class across all 14,714 units leaves slope angle as the only thing that
  // varies, which is what made the risk layer read as a uniform wash.
  const [lithology, setLithology] = useState("terrain_derived");
  // Null means "follow the live reading". The slider only pins a value once
  // someone deliberately drags it, so this page and the overview cannot
  // disagree about how wet the ground currently is.
  const { live: liveWetness, loading: wetnessLoading } = useLiveWetness();
  const [wetnessOverride, setWetnessOverride] = useState<number | null>(null);
  const wetness = wetnessOverride ?? liveWetness ?? ASSUMED_WETNESS_FALLBACK;
  const [threshold, setThreshold] = useState(0.35);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(apiUrl("/risk/lithology-classes"));
        if (response.ok) setLithologies((await response.json()) as LithologyOption[]);
      } catch {
        // The screen still works with the default class.
      }
    })();
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tableResponse, geoResponse] = await Promise.all([
        fetch(
          apiUrl(
            `/connectivity/roads?lithology=${encodeURIComponent(lithology)}` +
              `&wetness=${wetness}&threshold=${threshold}&limit=40`,
          ),
        ),
        fetch(
          apiUrl(
            `/connectivity/roads.geojson?lithology=${encodeURIComponent(lithology)}&wetness=${wetness}`,
          ),
        ),
      ]);
      if (!tableResponse.ok) throw new Error(`API returned ${tableResponse.status}`);
      setData((await tableResponse.json()) as ConnectivityResponse);
      if (geoResponse.ok) setGeo((await geoResponse.json()) as FeatureCollection);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not compute road blockage");
    } finally {
      setLoading(false);
    }
  }, [lithology, wetness, threshold]);

  useEffect(() => {
    // Wait for the live reading before the first fetch, otherwise the page
    // loads once at the fallback wetness and again at the live one, and the
    // figures visibly jump.
    if (wetnessLoading) return;
    const timer = setTimeout(() => void load(), 200);
    return () => clearTimeout(timer);
  }, [load, wetnessLoading]);

  return (
    <>
      <PageHeader
        title="Roads and access"
        description="Expected blocking failures per segment, from the slope units above it that can physically reach the road."
      />

      <div className="space-y-5 p-6">
        {error && <ErrorRow message={error} />}

        <MethodNote summary="How blockage probability is computed, and what it is not">
          <p>
            Slope units within 250 m of a segment contribute their instability, combined as
            independent probabilities so a single failing slope is never averaged away. Instability
            is 2 minus the factor of safety, clipped to 0 and 1.
          </p>
          <p>
            It is not calibrated against observed road closures, because no closure record has been
            obtained for the area. Treat the ranking as a way to order inspection, not as a
            probability that a particular road will shut.
          </p>
        </MethodNote>

        {/* ------------------------------------------------- controls --- */}
        <Panel title="Assumptions" description="Every number below moves with these three inputs">
          <div className="grid gap-5 md:grid-cols-3">
            <WetnessControl value={wetness} onChange={setWetnessOverride} live={liveWetness} />

            <label className="block">
              <span className="flex justify-between text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
                At-risk threshold
                <span data-numeric className="text-[var(--fg-muted)]">
                  {threshold.toFixed(2)}
                </span>
              </span>
              <input
                type="range"
                min={0.05}
                max={0.95}
                step={0.05}
                value={threshold}
                onChange={(event) => setThreshold(Number(event.target.value))}
                className="mt-2 w-full accent-[var(--accent)]"
              />
            </label>

            <label className="block">
              <span className="text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
                Material class
              </span>
              <select
                value={lithology}
                onChange={(event) => setLithology(event.target.value)}
                className="mt-2 h-9 w-full rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 text-[length:var(--text-sm)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
              >
                {lithologies.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </Panel>

        {loading && !data && <LoadingRow label="Computing blockage across 741 segments" />}

        {data && (
          <>
            <RoadsMap data={geo} />

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile
                label="Segments at risk"
                value={data.segments_at_risk}
                caption={`of ${data.segments_total.toLocaleString()} total`}
                tone="orange"
              />
              <StatTile
                label="Length at risk"
                value={data.length_at_risk_km}
                unit="km"
                caption="Sum of threatened segments"
                tone="orange"
              />
              <StatTile
                label="Facilities affected"
                value={data.facilities_cut_off}
                caption={`of ${data.facilities_total} within 1 km of a threatened road`}
                tone="red"
              />
              <StatTile
                label="Search buffer"
                value={data.buffer_m}
                unit="m"
                caption="Slope units this close can reach the road"
              />
            </div>

            <div className="grid gap-5 xl:grid-cols-[1fr_20rem]">
              <Panel
                title="Fix these first"
                description="Ranked by the expected number of failures that reach the segment. A trunk or primary road carries the traffic an ambulance needs."
              >
                <DataTable
                  rows={data.top_segments}
                  rowKey={(row, index) => `${row.osm_id ?? "seg"}-${index}`}
                  empty="No segments above the threshold"
                  columns={[
                    {
                      key: "name",
                      header: "Segment",
                      render: (row) => (
                        <span className="font-medium">
                          {row.name ?? `${row.highway_class} segment`}
                        </span>
                      ),
                    },
                    {
                      key: "class",
                      header: "Class",
                      render: (row) => (
                        <span className="text-[var(--fg-secondary)]">{row.highway_class}</span>
                      ),
                    },
                    {
                      key: "length",
                      header: "Length",
                      align: "right",
                      render: (row) => (
                        <span data-numeric>{(row.length_m / 1000).toFixed(2)} km</span>
                      ),
                    },
                    {
                      key: "units",
                      header: "Slopes in reach",
                      align: "right",
                      render: (row) => <span data-numeric>{row.contributing_units}</span>,
                    },
                    {
                      key: "expected",
                      header: "Expected blockages",
                      align: "right",
                      render: (row) => (
                        <span data-numeric className="font-medium">
                          {row.expected_blockages.toFixed(2)}
                        </span>
                      ),
                    },
                    {
                      key: "probability",
                      header: "P(any of top 5)",
                      align: "right",
                      render: (row) => (
                        <span className="flex items-center justify-end gap-2">
                          <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                            <span
                              className="block h-full rounded-full"
                              style={{
                                width: `${row.blockage_probability * 100}%`,
                                background:
                                  row.blockage_probability > 0.66
                                    ? bandCss("unstable")
                                    : row.blockage_probability > 0.33
                                      ? bandCss("marginal")
                                      : bandCss("low_margin"),
                              }}
                            />
                          </span>
                          <span data-numeric className="w-10 text-right font-medium">
                            {(row.blockage_probability * 100).toFixed(0)}%
                          </span>
                        </span>
                      ),
                    },
                  ]}
                />
              </Panel>

              <Panel title="By road class" description="Where the risk concentrates">
                <ul className="grid gap-2">
                  {Object.entries(data.by_class)
                    .sort((a, b) => b[1] - a[1])
                    .map(([name, count]) => (
                      <li key={name} className="flex items-center gap-2">
                        <span className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                          {name}
                        </span>
                        <span
                          data-numeric
                          className="ml-auto text-[length:var(--text-sm)] font-medium"
                        >
                          {count}
                        </span>
                      </li>
                    ))}
                </ul>
                <p className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-[length:var(--text-2xs)] leading-relaxed text-[var(--fg-muted)]">
                  {data.method}
                </p>
              </Panel>
            </div>
          </>
        )}
      </div>
    </>
  );
}
