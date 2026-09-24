import { setRequestLocale } from "next-intl/server";

import { Overview } from "@/components/dashboard/overview";

export const metadata = { title: "Situation overview" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Overview />;
}
