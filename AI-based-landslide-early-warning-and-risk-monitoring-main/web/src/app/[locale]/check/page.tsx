import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { LocationCheck } from "@/components/check/location-check";

export const metadata: Metadata = {
  title: "Check a location",
  description: "Landslide susceptibility information for any point in India.",
};

export default async function CheckPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <LocationCheck />;
}
