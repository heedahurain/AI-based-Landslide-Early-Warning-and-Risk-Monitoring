"use client";

import { useTransition } from "react";
import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import { LOCALES, LOCALE_META, type Locale } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/**
 * Language switcher.
 *
 * Each option is labelled in its own language and script, because the name of
 * a language in English is no help to someone who cannot read the current
 * interface. Locales whose catalogue is not yet authored are marked, so a user
 * is never surprised to find English behind a native-language label.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const t = useTranslations("language");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function onChange(next: string) {
    startTransition(() => {
      router.replace(pathname, { locale: next as Locale });
    });
  }

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <Languages
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 size-3.5 text-[var(--fg-muted)]"
      />
      <select
        aria-label={t("label")}
        value={locale}
        disabled={isPending}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "h-8 appearance-none rounded-[var(--radius-md)] border border-[var(--border-subtle)]",
          "bg-[var(--bg-surface)] py-0 pr-3 pl-8 text-[length:var(--text-xs)] text-[var(--fg-primary)]",
          "transition-[border-color,opacity] duration-[var(--duration-fast)] ease-[var(--ease-out)]",
          "hover:border-[var(--border-strong)]",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)]",
          isPending && "opacity-60",
        )}
      >
        {LOCALES.map((code) => {
          const meta = LOCALE_META[code];
          return (
            <option key={code} value={code}>
              {meta.native}
              {meta.catalogue === "fallback" ? " · EN" : ""}
            </option>
          );
        })}
      </select>
    </div>
  );
}
