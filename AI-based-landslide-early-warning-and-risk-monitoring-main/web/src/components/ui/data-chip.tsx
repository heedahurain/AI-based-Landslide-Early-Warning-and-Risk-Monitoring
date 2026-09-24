"use client";

import { Database, Radio, Waves } from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";
import type { Provenance } from "@/lib/severity";

/**
 * The data provenance chip.
 *
 * This component is the visible half of the promise in PROJECT_CONTEXT.md §4:
 * the interface must never imply that simulated data is live. Every panel that
 * shows a number carries one of these.
 *
 * `cached` requires an age. A cached figure without its age is indistinguishable
 * from a live one, which is precisely the failure this chip exists to prevent,
 * so the age is a required prop for that state rather than an optional extra.
 */

const ICONS = {
  live: Radio,
  cached: Database,
  simulated: Waves,
} as const;

const STYLES: Record<Provenance, string> = {
  live: "text-[var(--sev-green-text)] border-[var(--sev-green-outline)]",
  cached: "text-[var(--sev-amber-text)] border-[var(--sev-amber-outline)]",
  simulated: "text-[var(--sev-cyan-text)] border-[var(--sev-cyan-outline)]",
};

export type DataChipProps =
  | { status: "live" | "simulated"; ageMinutes?: never; source?: string; className?: string }
  | { status: "cached"; ageMinutes: number; source?: string; className?: string };

export function DataChip({ status, ageMinutes, source, className }: DataChipProps) {
  const t = useTranslations("provenance");
  const Icon = ICONS[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[var(--radius-full)] border",
        "bg-transparent px-2 py-0.5",
        "text-[length:var(--text-2xs)] font-medium tracking-[var(--tracking-caps)] uppercase",
        STYLES[status],
        className,
      )}
      title={source}
    >
      <Icon aria-hidden="true" className="size-3" />
      {t(status)}
      {status === "cached" && (
        <span data-numeric className="opacity-80">
          {t("age", { minutes: ageMinutes })}
        </span>
      )}
    </span>
  );
}
