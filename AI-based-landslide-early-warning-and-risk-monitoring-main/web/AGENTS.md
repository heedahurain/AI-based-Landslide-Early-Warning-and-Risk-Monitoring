# web/ — agent notes

Read `../PROJECT_CONTEXT.md` first. It is the authoritative spec. This file covers only
what is specific to the Next.js workspace.

## Version facts, verified on 2026-09-08

- **Next.js 15.5.25**, React 19.2.8, Tailwind CSS v4, TypeScript strict.
- `create-next-app` installs Next **16** by default. This project is deliberately pinned
  to **15**, because `PROJECT_CONTEXT.md` §3 names Next.js 15 as non-negotiable and that
  stack list goes into the submission. Do not upgrade to 16 without changing the spec and
  the submission material together.
- Next 15.5.25 has no `node_modules/next/dist/docs/` directory and no
  `generate-agent-files.js`. An earlier version of this file, generated during the brief
  Next 16 install, claimed both existed. It was wrong and has been replaced. If that
  block reappears, someone has reinstalled Next 16.

## Conventions

- **Design tokens live in `src/app/globals.css` and nowhere else.** Never hard-code a hex
  value in a component. If you need a colour that does not exist, add a token.
- **Severity colours are locked** to the five hexes in the spec. A marker uses
  `--sev-*-mark` and must carry `--sev-*-outline`, because several of the locked marks do
  not reach 3:1 on a white surface. Text uses `--sev-*-text`, never `-mark`.
- **Run `node scripts/contrast.mjs` after touching any colour token.** It exits non-zero
  on a WCAG failure and is wired into `npm run test`. Last run: 76 pairs, 0 failing.
- **Numerals use the mono font with `tabular-nums`.** Apply the `tabular` class or a
  `data-numeric` attribute to anything that updates live, so digits do not jitter.
- **Motion is transform and opacity only**, 150–250 ms, and `prefers-reduced-motion` is
  honoured globally in `globals.css`. Never animate layout properties.
- **Theme** is driven by `next-themes` with `attribute="data-theme"`, matching the
  `:root[data-theme="dark"]` token blocks. The two dark blocks must be edited together.

## i18n

- `next-intl` with a `[locale]` route segment. Locales are declared in `src/i18n/routing.ts`.
- Ten languages, eleven locale codes, because Manipuri ships in both Bengali script
  (`mni`) and Meitei Mayek (`mni-Mtei`).
- **Never commit a machine-translated string without recording it in
  `../docs/TRANSLATIONS.md`.** A locale with no catalogue falls back to English, which is
  honest. Inventing text in a language nobody on the team reads is not.

## Testing

- `npm run test` runs vitest plus the contrast audit.
- `npm run typecheck` runs `tsc --noEmit`. Strict mode is on, including
  `noUncheckedIndexedAccess`.
