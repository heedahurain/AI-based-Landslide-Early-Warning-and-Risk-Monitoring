"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/shell/app-shell";
import { MethodNote } from "@/components/shell/method-note";
import { DataTable, ErrorRow, LoadingRow, Panel, StatTile } from "@/components/shell/panels";
import { apiUrl, bandCss, type FactorOfSafetyResponse } from "@/lib/geo";
import { ASSUMED_WETNESS_FALLBACK, useLiveWetness } from "@/lib/use-live-wetness";

interface RoadRisk {
  name: string | null;
  highway_class: string;
  length_m: number;
  blockage_probability: number;
  contributing_units: number;
}

interface ConnectivityResponse {
  segments_at_risk: number;
  facilities_cut_off: number;
  facilities_total: number;
  top_segments: RoadRisk[];
}

/**
 * Response prioritisation.
 *
 * The index below is deliberately simple and completely visible. Two of the
 * inputs the brief asks for, exposed population and vulnerable groups, are not
 * present: no population figures have been obtained for the pilot area. Rather
 * than invent them, the screen ranks on what is measured and says plainly which
 * terms are missing, because a weighting built on invented population counts
 * would be worse than a narrower index that is honest.
 */
export function ResponseDashboard() {
  const [physics, setPhysics] = useState<FactorOfSafetyResponse | null>(null);
  const [roads, setRoads] = useState<ConnectivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Scored at the live wetness, the same value the overview uses. This page
  // previously hardcoded 0.75, which made its queue disagree with the overview
  // for no reason a reader could see.
  const { live: liveWetness, loading: wetnessLoading } = useLiveWetness();
  const wetness = liveWetness ?? ASSUMED_WETNESS_FALLBACK;

  useEffect(() => {
    if (wetnessLoading) return;
    let cancelled = false;
    void (async () => {
      try {
        const [physicsResponse, roadsResponse] = await Promise.all([
          fetch(apiUrl(`/risk/factor-of-safety?wetness=${wetness}`)),
          fetch(apiUrl(`/connectivity/roads?wetness=${wetness}&limit=15`)),
        ]);
        if (cancelled) return;
        if (physicsResponse.ok)
          setPhysics((await physicsResponse.json()) as FactorOfSafetyResponse);
        if (roadsResponse.ok) setRoads((await roadsResponse.json()) as ConnectivityResponse);
      } catch (caught) {
        if (!cancelled)
          setError(caught instanceof Error ? caught.message : "Could not build the queue");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [wetness, wetnessLoading]);

  // Priority combines how likely the road is to be cut with how much traffic
  // its class carries. Both terms are shown so the ranking can be argued with.
  const CLASS_WEIGHT: Record<string, number> = {
    trunk: 1.0,
    primary: 0.9,
    secondary: 0.7,
    tertiary: 0.5,
    unclassified: 0.35,
    residential: 0.3,
  };

  const tasks = (roads?.top_segments ?? [])
    .map((segment) => {
      const importance = CLASS_WEIGHT[segment.highway_class] ?? 0.3;
      return {
        ...segment,
        importance,
        priority: segment.blockage_probability * importance,
      };
    })
    .sort((a, b) => b.priority - a.priority);

  return (
    <>
      <PageHeader
        title="Response prioritisation"
        description="A transparent, tunable ranking of where to send limited inspection and clearance capacity first."
      />

      <div className="space-y-5 p-6">
        {error && <ErrorRow message={error} />}

        <MethodNote summary="Two ranking terms are missing" tone="caution">
          <p>
            The brief asks for exposed population and vulnerable groups in this index. No population
            figures have been obtained for the pilot area, so neither term is present and the
            ranking uses blockage probability and road class alone.
          </p>
          <p>
            It will therefore under-rank a quiet road serving a large village and over-rank a busy
            road serving nobody. Adding village population is the single change that would most
            improve this screen.
          </p>
        </MethodNote>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Slopes needing inspection"
            value={physics ? physics.summary.unstable + physics.summary.marginal : null}
            caption="Factor of safety below 1.3"
            tone="amber"
            loading={loading}
          />
          <StatTile
            label="Road segments at risk"
            value={roads?.segments_at_risk ?? null}
            caption="Above the blockage threshold"
            tone="orange"
            loading={loading}
          />
          <StatTile
            label="Facilities affected"
            value={roads?.facilities_cut_off ?? null}
            caption={roads ? `of ${roads.facilities_total} in the area` : undefined}
            tone="red"
            loading={loading}
          />
          <StatTile
            label="Tasks in the queue"
            value={tasks.length}
            caption="Derived from the ranking below"
            loading={loading}
          />
        </div>

        <Panel
          title="Action queue"
          description="Priority is blockage probability multiplied by the traffic weight of the road class. Both factors are shown so the order can be challenged."
        >
          {loading ? (
            <LoadingRow />
          ) : (
            <DataTable
              rows={tasks}
              rowKey={(row, index) => `${row.name ?? "segment"}-${index}`}
              empty="Nothing above the threshold"
              columns={[
                {
                  key: "rank",
                  header: "#",
                  render: (_row) => null,
                },
                {
                  key: "target",
                  header: "Target",
                  render: (row) => (
                    <div>
                      <p className="font-medium">
                        {row.name ?? <span className="text-[var(--fg-muted)]">unnamed road</span>}
                      </p>
                      <p className="text-[length:var(--text-xs)] text-[var(--fg-muted)]">
                        {row.highway_class} · {(row.length_m / 1000).toFixed(2)} km ·{" "}
                        {row.contributing_units} slopes above
                      </p>
                    </div>
                  ),
                },
                {
                  key: "blockage",
                  header: "Blockage",
                  align: "right",
                  render: (row) => (
                    <span data-numeric>{(row.blockage_probability * 100).toFixed(0)}%</span>
                  ),
                },
                {
                  key: "importance",
                  header: "Route weight",
                  align: "right",
                  render: (row) => <span data-numeric>{row.importance.toFixed(2)}</span>,
                },
                {
                  key: "priority",
                  header: "Priority",
                  align: "right",
                  render: (row) => (
                    <span className="flex items-center justify-end gap-2">
                      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                        <span
                          className="block h-full rounded-full"
                          style={{
                            width: `${Math.min(100, row.priority * 100)}%`,
                            background:
                              row.priority > 0.6
                                ? bandCss("unstable")
                                : row.priority > 0.3
                                  ? bandCss("marginal")
                                  : bandCss("low_margin"),
                          }}
                        />
                      </span>
                      <span data-numeric className="w-10 text-right font-medium">
                        {row.priority.toFixed(2)}
                      </span>
                    </span>
                  ),
                },
              ]}
            />
          )}
        </Panel>

        <Panel
          title="Index weights"
          description="Shown because an opaque score is not usable by an official"
        >
          <DataTable
            rows={Object.entries(CLASS_WEIGHT)}
            rowKey={([name]) => name}
            columns={[
              { key: "class", header: "Road class", render: ([name]) => name },
              {
                key: "weight",
                header: "Traffic weight",
                align: "right",
                render: ([, weight]) => <span data-numeric>{weight.toFixed(2)}</span>,
              },
            ]}
          />
        </Panel>
      </div>
    </>
  );
}
