# web/

The Next.js 15 application: five operational dashboards, the public citizen
portal, Lite mode and the offline PWA.

See [`AGENTS.md`](AGENTS.md) for the conventions that govern this workspace, and
[`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) for the project spec.

## Commands

```bash
npm run dev         # Turbopack dev server
npm run build       # production build, standalone output
npm run test        # vitest plus the WCAG contrast audit
npm run typecheck   # tsc --noEmit, strict
npm run lint
npm run contrast    # WCAG audit alone
```

## Structure

```
src/app/[locale]/   routes, one segment per locale
src/components/     shell and primitives
src/components/ui/  design system primitives
src/i18n/           next-intl routing, request config, locale metadata
src/lib/            domain vocabulary and helpers
messages/           translation catalogues, one file per authored locale
scripts/            the WCAG contrast auditor
```

## Three rules worth repeating

1. **No hard-coded colours.** Every value comes from a token in
   `src/app/globals.css`. Run `npm run contrast` after touching one.
2. **Severity is never carried by hue alone.** Each tier has an icon, and
   colour-blind-safe mode adds a pattern fill.
3. **A locale with no catalogue falls back to English**, and the switcher marks
   it. Never invent text in a language nobody on the team reads. Record every
   translation in [`../docs/TRANSLATIONS.md`](../docs/TRANSLATIONS.md).
