import { setRequestLocale } from "next-intl/server";

import { RoadsDashboard } from "@/components/dashboard/roads";

export const metadata = { title: "Roads and access" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RoadsDashboard />;
}
