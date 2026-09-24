import { setRequestLocale } from "next-intl/server";

import { ReportsDashboard } from "@/components/dashboard/reports";

export const metadata = { title: "Citizen reports" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ReportsDashboard />;
}
