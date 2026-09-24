# Translation status

**Last updated: 2026-09-08 (Phase 0).**

ShailSuraksha warns people in the language they read. That claim is only
credible if the translations are real, so this file records exactly who wrote
and reviewed each one. It is the honest counterpart to a language switcher that
lists ten languages.

## The rule

**No string is presented as a reviewed translation until a named native speaker
has reviewed it.** A locale with no authored catalogue falls back to English,
which is honest. Inventing text in a language nobody on the team reads is not,
and a wrong evacuation instruction is worse than an English one.

The language switcher marks any locale still falling back with `· EN`, so a
user is never surprised by what they get.

## Coverage

| Locale | Language | Script | Catalogue | Author | Native reviewer | Status |
|---|---|---|---|---|---|---|
| `en` | English | Latin | authored | Team | n/a | **Baseline** |
| `hi` | Hindi | Devanagari | authored | Claude (model-generated) | *pending* | **Unreviewed** |
| `bn` | Bengali | Bengali | authored | Claude (model-generated) | *pending* | **Unreviewed** |
| `as` | Assamese | Bengali-Assamese | authored | Claude (model-generated) | *pending* | **Unreviewed** |
| `ne` | Nepali | Devanagari | authored | Claude (model-generated) | *pending* | **Unreviewed** |
| `mni` | Manipuri / Meiteilon | Bengali | none | — | — | Falls back to English |
| `mni-Mtei` | Manipuri / Meiteilon | Meetei Mayek | none | — | — | Falls back to English |
| `lus` | Mizo | Latin | none | — | — | Falls back to English |
| `kha` | Khasi | Latin | none | — | — | Falls back to English |
| `nag` | Nagamese | Latin | none | — | — | Falls back to English |
| `brx` | Bodo | Devanagari | none | — | — | Falls back to English |

**Every authored catalogue above is model-generated and unreviewed.** They must
not be described as reviewed translations in the pitch, the submission document
or the demo until the reviewer column is filled in. Phase 9 completes the
remaining six languages and the review pass.

A test in `web/src/i18n/messages.test.ts` fails the build if this table and the
`catalogue` flags in `web/src/i18n/routing.ts` disagree with which files
actually exist, so the switcher cannot silently start advertising a language it
does not have.

## Why six languages have no catalogue yet

Mizo, Khasi, Nagamese, Bodo and both Manipuri scripts are low-resource
languages. Machine translation into them is unreliable, and the strings in
question tell people whether to leave their homes. Shipping a confident-looking
mistranslation of "Evacuate now" would be worse than shipping English. These
six wait for a speaker.

## What must be translated, in priority order

1. **Severity levels and the action for each** (`severity.*`, `severityAction.*`).
   These are what a person reads when deciding whether to leave. Highest priority.
2. **Alert templates**, including the SMS and IVR phrasings, which have their own
   length and phonetic constraints.
3. **The citizen portal**: "Am I safe right now", shelter and route wording, the
   report flow.
4. **The disclaimer** (`footer.disclaimer`). A legal and ethical statement, so it
   needs a careful reviewer, not a literal one.
5. Operational dashboard interface strings. Lowest priority: officers can work in
   English, villagers frequently cannot.

## Review checklist for a native speaker

For each string, confirm:

- **Accuracy of the instruction**, not the literal words. "Evacuate now" must
  carry urgency and be unambiguous about acting immediately.
- **Register.** A government warning should be respectful and plain, not casual
  and not bureaucratic to the point of being unreadable.
- **Script correctness**, especially Assamese `ৰ` and `ৱ` against the Bengali
  `র` and `ব`, which are frequently confused by automated tools.
- **Length.** Verify the string does not overflow its component. Phase 9 tests
  the longest translation of every label.
- **Terminology consistency.** The word chosen for "landslide", "slope",
  "shelter" and "warning" must be the same everywhere.

## How to contribute a review

1. Edit `web/messages/<locale>.json`.
2. Add your name and the date to the table above.
3. Run `cd web && npm run test` to confirm the catalogue tests still pass.
4. If you authored a new locale, flip its `catalogue` flag to `authored` in
   `web/src/i18n/routing.ts`. The test enforces that the flag matches reality.

## Fonts

The Noto family covers every script here: Noto Sans for Devanagari, Bengali and
Assamese, and Noto Sans Meetei Mayek for `mni-Mtei`. Phase 5 adds the per-script
font strategy with subsetting and measures the payload rather than assuming it.
Latin-script locales (Mizo, Khasi, Nagamese) use the interface font already.
