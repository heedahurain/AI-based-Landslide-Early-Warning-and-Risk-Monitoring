"use client";

import { useEffect, useState } from "react";
import {
  CloudRain,
  LayoutDashboard,
  LifeBuoy,
  MapPinned,
  MessageSquareWarning,
  Mountain,
  PanelLeftClose,
  PanelLeftOpen,
  Route,
  ShieldCheck,
} from "lucide-react";

import { Link, usePathname } from "@/i18n/navigation";
import { apiUrl } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ModelStatusChip } from "@/components/shell/method-note";

/**
 * The operations console shell.
 *
 * A disaster console is used under time pressure by someone who already knows
 * where things are, so the navigation is always present, the current screen is
 * unambiguous, and the connection state and clock are visible without asking.
 */

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, phase: null },
  { href: "/map", label: "Risk severity", icon: Mountain, phase: null },
  { href: "/check", label: "Check a location", icon: MapPinned, phase: null },
  { href: "/dashboard/roads", label: "Roads and access", icon: Route, phase: null },
  { href: "/dashboard/weather", label: "Weather", icon: CloudRain, phase: null },
  { href: "/dashboard/response", label: "Response", icon: ShieldCheck, phase: null },
  { href: "/dashboard/reports", label: "Citizen reports", icon: MessageSquareWarning, phase: null },
  { href: "/portal", label: "Public portal", icon: LifeBuoy, phase: null },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [now, setNow] = useState<Date | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  // Rendered only after mount. A clock rendered on the server disagrees with
  // the browser and produces a hydration mismatch.
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll the API's own health endpoint rather than navigator.onLine, which only
  // reports whether a network exists, not whether our service answers.
  //
  // A single failed poll is not an outage. On a weak connection one request
  // times out routinely, and flipping the chip to a red "API offline" on that
  // evidence is both wrong and alarming: it appeared mid-demo on one page while
  // every other page was fine, which reads as a broken build. So a failure has
  // to repeat before it is believed, while a success is trusted immediately.
  useEffect(() => {
    let cancelled = false;
    let consecutiveFailures = 0;
    const FAILURES_BEFORE_OFFLINE = 3;

    const check = async () => {
      let healthy = false;
      try {
        const response = await fetch(apiUrl("/health"), { cache: "no-store" });
        healthy = response.ok;
      } catch {
        healthy = false;
      }
      if (cancelled) return;

      if (healthy) {
        consecutiveFailures = 0;
        setOnline(true);
        return;
      }
      consecutiveFailures += 1;
      if (consecutiveFailures >= FAILURES_BEFORE_OFFLINE) setOnline(false);
    };

    void check();
    const timer = setInterval(() => void check(), 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--bg-base)]">
      {/* ------------------------------------------------------- sidebar */}
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)]",
          "transition-[width] duration-[var(--duration-normal)] ease-[var(--ease-out)]",
          collapsed ? "w-[var(--sidebar-w-collapsed)]" : "w-[var(--sidebar-w)]",
        )}
      >
        <div className="flex h-[var(--topbar-h)] items-center gap-2 border-b border-[var(--border-subtle)] px-3">
          <span className="grid size-7 shrink-0 place-items-center rounded-[var(--radius-md)] bg-[var(--accent)] text-[var(--accent-fg)]">
            <Mountain aria-hidden="true" className="size-4" />
          </span>
          {!collapsed && (
            <span className="truncate text-[length:var(--text-sm)] font-semibold">
              ShailSuraksha
            </span>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto p-2" aria-label="Main">
          <ul className="grid gap-0.5">
            {NAV.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/dashboard" && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-[var(--radius-md)] px-2.5 py-2",
                      "text-[length:var(--text-sm)] transition-colors duration-[var(--duration-fast)]",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
                      active
                        ? "bg-[var(--bg-elevated)] font-medium text-[var(--fg-primary)]"
                        : "text-[var(--fg-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg-primary)]",
                    )}
                  >
                    <Icon aria-hidden="true" className="size-4 shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {active && (
                      <span
                        aria-hidden="true"
                        className="ml-auto h-4 w-0.5 rounded-full bg-[var(--accent)]"
                      />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-[var(--border-subtle)] p-2">
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center gap-2.5 rounded-[var(--radius-md)] px-2.5 py-2 text-[length:var(--text-sm)] text-[var(--fg-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]"
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" className="size-4" />
            ) : (
              <PanelLeftClose aria-hidden="true" className="size-4" />
            )}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* --------------------------------------------------------- main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[var(--topbar-h)] shrink-0 items-center gap-3 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4">
          <p className="text-[length:var(--text-sm)] font-medium">
            Noney and Tupul, Manipur
            <span className="ml-2 text-[length:var(--text-xs)] font-normal text-[var(--fg-muted)]">
              pilot area
            </span>
          </p>

          <div className="ml-auto flex items-center gap-3">
            <ModelStatusChip />
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-[var(--radius-full)] border px-2.5 py-1",
                "text-[length:var(--text-2xs)] tracking-[var(--tracking-caps)] uppercase",
                online === null
                  ? "border-[var(--border-default)] text-[var(--fg-muted)]"
                  : online
                    ? "border-[var(--sev-green-outline)] text-[var(--sev-green-text)]"
                    : "border-[var(--sev-red-outline)] text-[var(--sev-red-text)]",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "size-1.5 rounded-full",
                  online === null
                    ? "bg-[var(--fg-muted)]"
                    : online
                      ? "bg-[var(--sev-green-mark)]"
                      : "bg-[var(--sev-red-mark)]",
                )}
              />
              {online === null ? "checking" : online ? "API online" : "API offline"}
            </span>

            <span
              data-numeric
              className="hidden text-[length:var(--text-xs)] text-[var(--fg-secondary)] sm:block"
              suppressHydrationWarning
            >
              {now
                ? `${now.toLocaleTimeString("en-GB", { hour12: false })} IST · ${now
                    .toISOString()
                    .slice(11, 19)} UTC`
                : "--:--:--"}
            </span>

            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

/** Standard page header used by every dashboard screen. */
export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start gap-4 border-b border-[var(--border-subtle)] px-6 py-5">
      <div className="min-w-0">
        <h1 className="text-[length:var(--text-xl)] font-semibold tracking-[var(--tracking-tight)]">
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-3xl text-[length:var(--text-sm)] text-[var(--fg-secondary)]">
            {description}
          </p>
        )}
      </div>
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  );
}
