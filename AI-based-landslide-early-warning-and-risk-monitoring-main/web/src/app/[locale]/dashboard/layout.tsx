import { setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/shell/app-shell";

/**
 * Every operations screen shares the shell: persistent navigation, the current
 * area, the connection state and the clock.
 */
export default async function DashboardLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <AppShell>{children}</AppShell>;
}
