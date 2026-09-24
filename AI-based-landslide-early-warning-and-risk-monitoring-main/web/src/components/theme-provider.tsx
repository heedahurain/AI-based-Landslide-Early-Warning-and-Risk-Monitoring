"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/**
 * Theme plumbing.
 *
 * `attribute="data-theme"` is not incidental: the token blocks in globals.css
 * are written as `:root[data-theme="dark"]` and
 * `:root:not([data-theme="light"])` under a prefers-color-scheme query, so the
 * toggle wins in both directions and the system default still works when the
 * user has expressed no preference.
 */
export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="data-theme"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
