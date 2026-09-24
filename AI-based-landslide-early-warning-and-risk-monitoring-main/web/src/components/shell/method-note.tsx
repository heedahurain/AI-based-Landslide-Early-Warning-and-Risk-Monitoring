"use client";

import { useState } from "react";
import { ChevronDown, Info } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Method and limits, on demand.
 *
 * Every screen has real caveats and they must stay reachable, but a full-width
 * amber banner on each one shouts the same warning four times and makes a
 * working product read as broken. The compromise used here is the one good
 * instruments use: a quiet, always-present affordance that opens the full
 * statement in one click.
 *
 * The rule this must not break: the caveat is never removed, never softened,
 * and never more than one interaction away from the number it qualifies.
 */
export function MethodNote({
  summary,
  children,
  tone = "neutral",
}: {
  /** One line, shown on the closed chip. Must name the limitation, not hide it. */
  summary: string;
  children: React.ReactNode;
  tone?: "neutral" | "caution";
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="w-full">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-[var(--radius-full)] border px-3 py-1",
          "text-[length:var(--text-xs)] transition-colors duration-[var(--duration-fast)]",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
          tone === "caution"
            ? "border-[var(--sev-amber-outline)] text-[var(--sev-amber-text)] hover:bg-[var(--sev-amber-tint)]"
            : "border-[var(--border-default)] text-[var(--fg-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg-primary)]",
        )}
      >
        <Info aria-hidden="true" className="size-3.5" />
        {summary}
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "size-3.5 transition-transform duration-[var(--duration-fast)]",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="mt-2 rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
          <div className="space-y-2 text-[length:var(--text-sm)] leading-relaxed text-[var(--fg-secondary)]">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * The one-line provenance chip for the top bar.
 *
 * States what the numbers on screen actually are, everywhere, always. It is
 * deliberately not dismissible.
 */
export function ModelStatusChip() {
  return (
    <span
      title="No learned model has been trained. Figures come from measured terrain, live rainfall and the physics layer."
      className="hidden items-center gap-1.5 rounded-[var(--radius-full)] border border-[var(--border-default)] px-2.5 py-1 text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] text-[var(--fg-muted)] uppercase lg:inline-flex"
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-[var(--sev-cyan-mark)]" />
      Physics layer
    </span>
  );
}
