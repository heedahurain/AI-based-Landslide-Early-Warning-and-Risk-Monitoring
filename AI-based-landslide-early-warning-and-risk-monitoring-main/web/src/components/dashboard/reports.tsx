"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, MapPin, X } from "lucide-react";

import { PageHeader } from "@/components/shell/app-shell";
import { MethodNote } from "@/components/shell/method-note";
import { DataTable, ErrorRow, LoadingRow, Panel, StatTile } from "@/components/shell/panels";
import { apiUrl } from "@/lib/geo";
import { cn } from "@/lib/utils";

interface Report {
  id: string;
  latitude: number;
  longitude: number;
  category: string;
  category_label: string;
  description: string;
  severity_self_assessed: number;
  reporter_name: string | null;
  submitted_at: string;
  verification_status: "unverified" | "verified" | "rejected";
  demo_seed?: boolean;
}

/**
 * Citizen report moderation.
 *
 * Reports arrive unverified and stay that way until a human acts. There is no
 * automatic classification here: the on-device vision model is a later phase,
 * and until it exists and has been evaluated, a machine guess presented beside
 * a citizen's photo would carry more authority than it has earned.
 */
export function ReportsDashboard() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unverified" | "verified" | "rejected">("all");

  const load = useCallback(async () => {
    try {
      const response = await fetch(apiUrl("/reports"));
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setReports((await response.json()) as Report[]);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load reports");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (id: string, status: "verified" | "rejected") => {
    try {
      await fetch(apiUrl(`/reports/${id}/verify?status=${status}`), { method: "POST" });
      await load();
    } catch {
      setError("Could not record that decision");
    }
  };

  const visible =
    filter === "all" ? reports : reports.filter((r) => r.verification_status === filter);
  const counts = {
    unverified: reports.filter((r) => r.verification_status === "unverified").length,
    verified: reports.filter((r) => r.verification_status === "verified").length,
    rejected: reports.filter((r) => r.verification_status === "rejected").length,
  };

  return (
    <>
      <PageHeader
        title="Citizen reports"
        description="Hazard observations submitted from the public portal, awaiting a moderator decision."
      />

      <div className="space-y-5 p-6">
        {error && <ErrorRow message={error} />}

        <MethodNote summary="Every report is judged by a person">
          <p>
            There is no automatic image classification. The on-device vision model is a later phase,
            and until it has been evaluated a machine guess should not sit next to a citizen&apos;s
            photograph carrying more authority than it has earned.
          </p>
        </MethodNote>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile label="Total reports" value={reports.length} loading={loading} />
          <StatTile
            label="Awaiting review"
            value={counts.unverified}
            tone={counts.unverified > 0 ? "amber" : "default"}
            loading={loading}
          />
          <StatTile label="Verified" value={counts.verified} tone="green" loading={loading} />
          <StatTile label="Rejected" value={counts.rejected} loading={loading} />
        </div>

        <Panel
          title="Moderation queue"
          description="Verify promotes a report into the operational picture. Reject records the decision."
          actions={
            <div className="flex gap-1">
              {(["all", "unverified", "verified", "rejected"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setFilter(option)}
                  aria-pressed={filter === option}
                  className={cn(
                    "rounded-[var(--radius-md)] px-2.5 py-1 text-[length:var(--text-xs)] capitalize",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                    filter === option
                      ? "bg-[var(--bg-elevated)] text-[var(--fg-primary)]"
                      : "text-[var(--fg-muted)] hover:text-[var(--fg-primary)]",
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          }
        >
          {loading ? (
            <LoadingRow />
          ) : (
            <DataTable
              rows={visible}
              rowKey={(row) => row.id}
              empty="No reports yet. Submit one from the public portal."
              columns={[
                {
                  key: "category",
                  header: "Hazard",
                  render: (row) => (
                    <div>
                      <p className="flex items-center gap-1.5 font-medium">
                        {row.category_label}
                        {row.demo_seed && (
                          <span
                            title="Seeded to demonstrate the moderation queue. Not a real citizen submission."
                            className="rounded-[var(--radius-full)] border border-[var(--border-default)] px-1.5 py-px text-[length:var(--text-2xs)] font-normal text-[var(--fg-muted)]"
                          >
                            seed
                          </span>
                        )}
                      </p>
                      {row.description && (
                        <p className="mt-0.5 max-w-md text-[length:var(--text-xs)] text-[var(--fg-muted)]">
                          {row.description}
                        </p>
                      )}
                    </div>
                  ),
                },
                {
                  key: "where",
                  header: "Location",
                  render: (row) => (
                    <span
                      data-numeric
                      className="flex items-center gap-1 text-[length:var(--text-xs)] text-[var(--fg-secondary)]"
                    >
                      <MapPin aria-hidden="true" className="size-3" />
                      {row.latitude.toFixed(4)}, {row.longitude.toFixed(4)}
                    </span>
                  ),
                },
                {
                  key: "severity",
                  header: "Reported as",
                  render: (row) => (
                    <span className="text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
                      {["", "Minor", "Moderate", "Serious", "Severe"][row.severity_self_assessed]}
                    </span>
                  ),
                },
                {
                  key: "when",
                  header: "Submitted",
                  render: (row) => (
                    <span
                      data-numeric
                      className="text-[length:var(--text-xs)] text-[var(--fg-muted)]"
                    >
                      {row.submitted_at.slice(0, 16).replace("T", " ")}
                    </span>
                  ),
                },
                {
                  key: "status",
                  header: "Status",
                  align: "right",
                  render: (row) =>
                    row.verification_status === "unverified" ? (
                      <span className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => void decide(row.id, "verified")}
                          className="inline-flex items-center gap-1 rounded-[var(--radius-md)] border border-[var(--sev-green-outline)] px-2 py-1 text-[length:var(--text-xs)] text-[var(--sev-green-text)] hover:bg-[var(--sev-green-tint)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
                        >
                          <Check aria-hidden="true" className="size-3" />
                          Verify
                        </button>
                        <button
                          type="button"
                          onClick={() => void decide(row.id, "rejected")}
                          className="inline-flex items-center gap-1 rounded-[var(--radius-md)] border border-[var(--border-default)] px-2 py-1 text-[length:var(--text-xs)] text-[var(--fg-muted)] hover:text-[var(--fg-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
                        >
                          <X aria-hidden="true" className="size-3" />
                          Reject
                        </button>
                      </span>
                    ) : (
                      <span
                        className={cn(
                          "rounded-[var(--radius-full)] px-2 py-0.5 text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] uppercase",
                          row.verification_status === "verified"
                            ? "bg-[var(--sev-green-tint)] text-[var(--sev-green-text)]"
                            : "bg-[var(--bg-elevated)] text-[var(--fg-muted)]",
                        )}
                      >
                        {row.verification_status}
                      </span>
                    ),
                },
              ]}
            />
          )}
        </Panel>
      </div>
    </>
  );
}
