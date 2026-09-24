import { setRequestLocale } from "next-intl/server";

import { PublicPortal } from "@/components/portal/public-portal";

export const metadata = { title: "Am I safe right now" };

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <PublicPortal />;
}
