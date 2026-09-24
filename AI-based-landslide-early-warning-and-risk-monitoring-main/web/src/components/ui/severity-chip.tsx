"use client";

import { AlertTriangle, ArrowUpRight, ShieldCheck, Siren } from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";
import { ariaLiveFor, type Severity } from "@/lib/severity";

/**
 * The severity chip. This is the single most repeated element in the product,
 * so its rules are strict.
 *
 * - Colour is never the only carrier of meaning. Every tier has a distinct icon
 *   and, in colour-blind-safe mode, a distinct pattern fill driven by the
 *   `data-severity` attribute in globals.css.
 * - Text uses the `-text` token, the dot uses the locked `-mark` token with its
 *   `-outline`, because several locked marks do not reach 3:1 on white.
 * - RED announces itself assertively to screen readers.
 */

const ICONS = {
  green: ShieldCheck,
  yellow: ArrowUpRight,
  orange: AlertTriangle,
  red: Siren,
} as const;

const STYLES: Record<Severity, string> = {
  green: "bg-[var(--sev-green-tint)] text-[var(--sev-green-text)]",
  yellow: "bg-[var(--sev-amber-tint)] text-[var(--sev-amber-text)]",
  orange: "bg-[var(--sev-orange-tint)] text-[var(--sev-orange-text)]",
  red: "bg-[var(--sev-red-tint)] text-[var(--sev-red-text)]",
};

const DOTS: Record<Severity, string> = {
  green: "bg-[var(--sev-green-mark)] ring-[var(--sev-green-outline)]",
  yellow: "bg-[var(--sev-amber-mark)] ring-[var(--sev-amber-outline)]",
  orange: "bg-[var(--sev-orange-mark)] ring-[var(--sev-orange-outline)]",
  red: "bg-[var(--sev-red-mark)] ring-[var(--sev-red-outline)]",
};

export interface SeverityChipProps {
  severity: Severity;
  /** Renders the slow emissive breath used for active RED units. */
  pulse?: boolean;
  showIcon?: boolean;
  className?: string;
}

export function SeverityChip({
  severity,
  pulse = false,
  showIcon = true,
  className,
}: SeverityChipProps) {
  const t = useTranslations("severity");
  const Icon = ICONS[severity];

  return (
    <span
      data-severity={severity}
      aria-live={ariaLiveFor(severity)}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[var(--radius-full)] px-2.5 py-1",
        "text-[length:var(--text-xs)] font-medium tracking-[var(--tracking-wide)] uppercase",
        STYLES[severity],
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-2 rounded-full ring-1",
          DOTS[severity],
          pulse && severity === "red" && "risk-pulse",
        )}
      />
      {showIcon && <Icon aria-hidden="true" className="size-3.5" />}
      {t(severity)}
    </span>
  );
}
