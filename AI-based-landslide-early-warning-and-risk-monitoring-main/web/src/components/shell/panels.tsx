"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Shared furniture for the dashboard screens.
 *
 * Every figure carries a caption saying what it is and, where relevant, where
 * it came from. A bare number in a console is an invitation to misread it.
 */

export function StatTile({
  label,
  value,
  unit,
  caption,
  tone = "default",
  loading = false,
}: {
  label: string;
  value: string | number | null;
  unit?: string;
  caption?: string;
  tone?: "default" | "green" | "amber" | "orange" | "red" | "cyan";
  loading?: boolean;
}) {
  const toneClass = {
    default: "text-[var(--fg-primary)]",
    green: "text-[var(--sev-green-text)]",
    amber: "text-[var(--sev-amber-text)]",
    orange: "text-[var(--sev-orange-text)]",
    red: "text-[var(--sev-red-text)]",
    cyan: "text-[var(--sev-cyan-text)]",
  }[tone];

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <p className="text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase">
        {label}
      </p>
      <p className="mt-2 flex items-baseline gap-1">
        {loading ? (
          <Loader2 aria-hidden="true" className="size-5 animate-spin text-[var(--fg-muted)]" />
        ) : (
          <>
            <span
              data-numeric
              className={cn(
                "text-[length:var(--text-2xl)] leading-none font-semibold tracking-[var(--tracking-tight)]",
                toneClass,
              )}
            >
              {value === null ? "—" : typeof value === "number" ? value.toLocaleString() : value}
            </span>
            {unit && (
              <span className="text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
                {unit}
              </span>
            )}
          </>
        )}
      </p>
      {caption && (
        <p className="mt-1.5 text-[length:var(--text-2xs)] leading-snug text-[var(--fg-muted)]">
          {caption}
        </p>
      )}
    </div>
  );
}

export function Panel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)]",
        className,
      )}
    >
      <header className="flex flex-wrap items-start gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-[length:var(--text-md)] font-semibold tracking-[var(--tracking-tight)]">
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-[length:var(--text-xs)] text-[var(--fg-secondary)]">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function DataTable<Row>({
  rows,
  columns,
  empty = "Nothing to show",
  rowKey,
}: {
  rows: Row[];
  columns: {
    key: string;
    header: string;
    align?: "left" | "right";
    render: (row: Row) => ReactNode;
  }[];
  empty?: string;
  rowKey: (row: Row, index: number) => string;
}) {
  if (!rows.length) {
    return (
      <p className="py-6 text-center text-[length:var(--text-sm)] text-[var(--fg-muted)]">
        {empty}
      </p>
    );
  }

  return (
    // Wide tables scroll inside their own container so the page never scrolls
    // sideways.
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full min-w-[36rem] border-collapse">
        <thead>
          <tr className="border-b border-[var(--border-subtle)]">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "pb-2 text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase",
                  // Without horizontal padding two adjacent headers abut and
                  // read as a single run-on string.
                  "px-3 first:pl-0 last:pr-0",
                  column.align === "right" ? "text-right" : "text-left",
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)]"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-2.5 text-[length:var(--text-sm)] first:pl-0 last:pr-0",
                    column.align === "right" ? "text-right" : "text-left",
                  )}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A proportion bar, used wherever a total splits into ordered bands. */
export function SplitBar({
  segments,
}: {
  segments: { label: string; value: number; colour: string }[];
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) return null;

  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-[var(--radius-full)] bg-[var(--bg-elevated)]">
      {segments.map((segment) =>
        segment.value > 0 ? (
          <span
            key={segment.label}
            title={`${segment.label}: ${segment.value.toLocaleString()}`}
            style={{ width: `${(100 * segment.value) / total}%`, background: segment.colour }}
          />
        ) : null,
      )}
    </div>
  );
}

export function LoadingRow({ label = "Loading" }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 py-6 text-[length:var(--text-sm)] text-[var(--fg-muted)]">
      <Loader2 aria-hidden="true" className="size-4 animate-spin" />
      {label}
    </p>
  );
}

export function ErrorRow({ message }: { message: string }) {
  return (
    <p className="rounded-[var(--radius-md)] border border-[var(--sev-red-outline)] bg-[var(--sev-red-tint)] p-3 text-[length:var(--text-sm)] text-[var(--sev-red-text)]">
      {message}
    </p>
  );
}
