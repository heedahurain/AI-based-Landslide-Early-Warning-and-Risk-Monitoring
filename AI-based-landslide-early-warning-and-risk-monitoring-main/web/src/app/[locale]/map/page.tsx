import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { MapWorkspace } from "@/components/map/map-workspace";

export const metadata: Metadata = {
  title: "Terrain map",
  description: "Hydrological slope units and their measured terrain attributes over 3D terrain.",
};

/**
 * The terrain map screen.
 *
 * This renders the actual Phase 1 output: 14,714 hydrological slope units
 * delineated from a 30 m elevation model, each carrying the slope, wetness,
 * relief and elevation the pipeline measured for it.
 *
 * It is not yet the Phase 6 risk command centre. There are no risk
 * probabilities, no time scrubber and no alerts, because no model has been
 * trained. What it does prove is that the geospatial foundation is real and
 * inspectable rather than a set of files nobody can see.
 */
export default async function MapPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <MapWorkspace />;
}
