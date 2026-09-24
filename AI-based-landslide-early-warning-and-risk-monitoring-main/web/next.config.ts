import path from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/**
 * Security headers.
 *
 * A government warning system is a credible phishing target, so these are set
 * from the first commit rather than retrofitted. The Content-Security-Policy is
 * deliberately absent here: it needs the map tile, style and worker origins
 * that arrive in the map phases, and a placeholder policy that everyone
 * disables is worse than an explicit one added when its sources are known.
 * Tracked in PROJECT_CONTEXT.md as part of the Phase 10 hardening scope.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-DNS-Prefetch-Control", value: "on" },
  {
    key: "Permissions-Policy",
    // Geolocation is required by the citizen portal, camera by hazard reports.
    value: "geolocation=(self), camera=(self), microphone=(self), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  // The development indicator defaults to the bottom left, where it sits
  // directly on top of the sidebar's Collapse control and appears in every
  // screenshot. It is a development-only overlay and never ships, but it makes
  // demo captures look broken, so move it clear of the sidebar.
  devIndicators: { position: "bottom-right" },
  reactStrictMode: true,
  poweredByHeader: false,
  // Traced standalone server, required by infra/docker/web.Dockerfile. Vercel
  // ignores this, so the same config serves both deployment targets.
  output: "standalone",
  // Without an explicit root, Next walks upward looking for a workspace and can
  // land far above the repository, which nests the traced output under the
  // whole absolute path and leaves server.js where the Dockerfile cannot find
  // it. Pinning it to this workspace keeps the output at
  // .next/standalone/server.js in every environment.
  outputFileTracingRoot: path.resolve(process.cwd()),
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default withNextIntl(nextConfig);
