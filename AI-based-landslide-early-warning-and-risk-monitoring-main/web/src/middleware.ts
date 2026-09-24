import createMiddleware from "next-intl/middleware";

import { routing } from "@/i18n/routing";

export default createMiddleware(routing);

export const config = {
  /**
   * Match every path except Next internals, the API proxy and anything with a
   * file extension. Service-worker and manifest requests must never be locale
   * prefixed, or the offline shell breaks, so they are excluded by the
   * extension rule.
   */
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
