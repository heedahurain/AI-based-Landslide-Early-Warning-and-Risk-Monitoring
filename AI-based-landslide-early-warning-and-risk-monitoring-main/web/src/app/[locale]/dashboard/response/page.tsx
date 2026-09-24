import { setRequestLocale } from "next-intl/server";

import { ResponseDashboard } from "@/components/dashboard/response";

export const metadata = { title: "Response prioritisation" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ResponseDashboard />;
}
