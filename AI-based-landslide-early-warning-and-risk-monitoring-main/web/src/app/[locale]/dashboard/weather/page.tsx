import { setRequestLocale } from "next-intl/server";

import { WeatherDashboard } from "@/components/dashboard/weather";

export const metadata = { title: "Weather" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <WeatherDashboard />;
}
