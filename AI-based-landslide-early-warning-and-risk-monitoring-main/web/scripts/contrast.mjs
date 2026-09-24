/**
 * WCAG contrast auditor for the ShailSuraksha token set.
 *
 * Run: node scripts/contrast.mjs
 *
 * Phase 5 pipes this into docs/DESIGN.md. It exists in Phase 0 so no token
 * ships without its ratio being measured. Colour choices in a warning system
 * are a safety property, not a taste question.
 */

const AA_NORMAL = 4.5;
const AA_LARGE = 3.0;
const AA_NON_TEXT = 3.0;

/** @param {string} hex */
function toRgb(hex) {
  const h = hex.replace("#", "").trim();
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ];
}

/** Relative luminance per WCAG 2.1. */
function luminance(hex) {
  const [r, g, b] = toRgb(hex).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(fg, bg) {
  const a = luminance(fg);
  const b = luminance(bg);
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

const light = {
  name: "light",
  base: "#f5f7fa",
  surface: "#ffffff",
  elevated: "#ffffff",
  fg: "#0b1220",
  fgSecondary: "#46536b",
  fgMuted: "#6b7891",
  accent: "#0369a1",
  border: "#cbd5e1",
  sev: {
    green: { text: "#15803d", mark: "#22c55e", tint: "#dcfce7", outline: "#15803d" },
    amber: { text: "#854d0e", mark: "#f59e0b", tint: "#fef3c7", outline: "#854d0e" },
    orange: { text: "#c2410c", mark: "#f97316", tint: "#ffedd5", outline: "#c2410c" },
    red: { text: "#b91c1c", mark: "#ef4444", tint: "#fee2e2", outline: "#b91c1c" },
    cyan: { text: "#0369a1", mark: "#38bdf8", tint: "#e0f2fe", outline: "#0369a1" },
  },
};

const dark = {
  name: "dark",
  base: "#070b14",
  surface: "#0d1424",
  elevated: "#16203a",
  fg: "#e8eefc",
  fgSecondary: "#9fb0cc",
  fgMuted: "#6b7d9c",
  accent: "#38bdf8",
  border: "#263250",
  sev: {
    green: { text: "#4ade80", mark: "#22c55e", tint: "#072a16", outline: "#4ade80" },
    amber: { text: "#fbbf24", mark: "#f59e0b", tint: "#2e1e04", outline: "#fbbf24" },
    orange: { text: "#fb923c", mark: "#f97316", tint: "#2f1607", outline: "#fb923c" },
    red: { text: "#f87171", mark: "#ef4444", tint: "#350f0f", outline: "#f87171" },
    cyan: { text: "#7dd3fc", mark: "#38bdf8", tint: "#07253a", outline: "#7dd3fc" },
  },
};

/** @type {{theme:string,pair:string,fg:string,bg:string,ratio:number,need:number,pass:boolean}[]} */
const rows = [];

function check(theme, pair, fg, bg, need) {
  const r = ratio(fg, bg);
  rows.push({ theme, pair, fg, bg, ratio: r, need, pass: r >= need });
}

for (const t of [light, dark]) {
  for (const [surfaceName, surface] of [
    ["base", t.base],
    ["surface", t.surface],
    ["elevated", t.elevated],
  ]) {
    check(t.name, `fg-primary on ${surfaceName}`, t.fg, surface, AA_NORMAL);
    check(t.name, `fg-secondary on ${surfaceName}`, t.fgSecondary, surface, AA_NORMAL);
    check(t.name, `fg-muted on ${surfaceName}`, t.fgMuted, surface, AA_LARGE);
    check(t.name, `accent on ${surfaceName}`, t.accent, surface, AA_NORMAL);
  }
  check(t.name, "border-default on surface", t.border, t.surface, 1.0);

  for (const [level, c] of Object.entries(t.sev)) {
    check(t.name, `sev-${level}-text on surface`, c.text, t.surface, AA_NORMAL);
    check(t.name, `sev-${level}-text on base`, c.text, t.base, AA_NORMAL);
    check(t.name, `sev-${level}-text on its tint`, c.text, c.tint, AA_NORMAL);
    // The -mark hexes are locked by the spec (#22C55E, #F59E0B, #F97316,
    // #EF4444, #38BDF8) and several fall short of 3:1 on a white surface. They
    // are therefore never drawn bare: every marker carries the -outline token,
    // and it is the outline that must satisfy the non-text requirement.
    check(t.name, `sev-${level}-outline on surface (non-text)`, c.outline, t.surface, AA_NON_TEXT);
    check(t.name, `sev-${level}-outline on base (non-text)`, c.outline, t.base, AA_NON_TEXT);
  }
}

const failures = rows.filter((r) => !r.pass);

const pad = (s, n) => String(s).padEnd(n);
console.log(`\n${pad("THEME", 6)} ${pad("PAIR", 40)} ${pad("RATIO", 8)} ${pad("NEED", 6)} RESULT`);
console.log("-".repeat(76));
for (const r of rows) {
  console.log(
    `${pad(r.theme, 6)} ${pad(r.pair, 40)} ${pad(r.ratio.toFixed(2), 8)} ${pad(
      r.need.toFixed(1),
      6,
    )} ${r.pass ? "PASS" : "FAIL"}`,
  );
}
console.log("-".repeat(76));
console.log(`${rows.length} pairs checked, ${failures.length} failing.\n`);

if (failures.length > 0) {
  console.error("Failing pairs:");
  for (const f of failures) {
    console.error(`  ${f.theme}: ${f.pair} = ${f.ratio.toFixed(2)} (needs ${f.need})`);
  }
  process.exit(1);
}
