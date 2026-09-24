"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", Icon: Sun },
  { value: "dark", Icon: Moon },
  { value: "system", Icon: Monitor },
] as const;

/**
 * Three-state theme control: light, dark, or follow the system.
 *
 * Rendered as a radio group rather than a cycling button so the current state
 * is announced correctly and reachable by keyboard in one step. Before the
 * client mounts, the resolved theme is unknown, so the control renders in a
 * disabled placeholder state rather than guessing and flashing the wrong icon.
 */
export function ThemeToggle() {
  const t = useTranslations("theme");
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return (
    <div
      role="radiogroup"
      aria-label={t("label")}
      className="inline-flex items-center gap-0.5 rounded-[var(--radius-full)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5"
    >
      {OPTIONS.map(({ value, Icon }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={t(value)}
            title={t(value)}
            disabled={!mounted}
            onClick={() => setTheme(value)}
            className={cn(
              "grid size-7 place-items-center rounded-[var(--radius-full)]",
              "transition-[background-color,color,opacity] duration-[var(--duration-fast)] ease-[var(--ease-out)]",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
              active
                ? "bg-[var(--bg-elevated)] text-[var(--fg-primary)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg-primary)]",
              !mounted && "opacity-40",
            )}
          >
            <Icon aria-hidden="true" className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}
