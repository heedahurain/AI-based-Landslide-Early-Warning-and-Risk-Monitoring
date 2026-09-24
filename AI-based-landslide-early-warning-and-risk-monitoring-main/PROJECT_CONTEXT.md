# ShailSuraksha — Project Context

> **Every session starts by reading this file.** It is the condensed, authoritative spec.
> If a decision here conflicts with your memory of a previous session, this file wins.
> When you take a new architectural decision, append it to §13 in the same session.

---

## 1. What this is

**ShailSuraksha** is an AI-based landslide early-warning and risk-monitoring platform for
the eight North Eastern states of India: Arunachal Pradesh, Assam, Manipur, Meghalaya,
Mizoram, Nagaland, Sikkim, Tripura.

- **Event:** Smart India Hackathon 2026
- **Problem statement:** SIH26001, category Software, theme Disaster Management
- **Issuing body:** Ministry of Development of North Eastern Region (MDoNER), Government of India
- **Intended operator:** a District Disaster Management Authority (DDMA) during monsoon

### Deadline

| Item | Value |
|---|---|
| Idea submission deadline | 30 September 2026 |
| Ideas submitted against the 500 cap, when this pack was written | 15 |

**The idea submission is judged on the write-up, not the code.** Submit early: a crowded
problem statement is harder to win from, and the field fills up near the deadline. The
write-up sections map onto this file as follows.

| Submission section | Source |
|---|---|
| Proposed solution | §2 and §6. Lead with the four-layer hybrid engine and the slope-unit scale, never with "we use AI/ML" |
| Technical approach | §3, plus the container diagram in `docs/ARCHITECTURE.md` |
| Feasibility and viability | `docs/DATA_SOURCES.md`, every source free or open, plus the CAP interoperability argument |
| Impact and benefits | The three reference events in §2, population exposed, and lead time as the headline metric |
| Research and references | Bhusanket, NASA LHASA, the GSI National Landslide Susceptibility Map, Iverson transient infiltration, Fukuzono inverse velocity, Varnes classification |

`docs/PITCH.md` holds the demo script, the problem-statement coverage matrix and the
judge question-and-answer defence pack.

This is **not a CRUD demo**. It is built as a production disaster-management system.
Judges are geologists, IAS officers and senior engineers. Every design decision must
survive these four questions:

1. Where does your data come from?
2. Why should I trust this number?
3. What happens when the network dies?
4. How is this different from what GSI already does?

## 2. The problem, in real terms

The NER receives 2000–4000 mm of rain a year on young, tectonically active, deeply
weathered Himalayan and Patkai-Naga slopes. Road-cutting, unplanned hill construction,
jhum cultivation and railway/highway earthworks have destabilised slopes further.

Reference events (use these in product copy and the pitch):

| Event | When | Toll | Attributed cause |
|---|---|---|---|
| Tupul / Noney, Manipur | Jun 2022 | ~55–61 killed | Extreme rainfall on deforested, unstabilised railway cut slopes; buried a Territorial Army camp |
| Aizawl, Mizoram | May 2024 | 20+ killed in one day | Quarry and hillside collapse during Cyclone Remal remnants |
| Assam / Arunachal / Manipur | mid-2025 | 20+ deaths across states in days | Record rainfall, simultaneous floods and landslides |

**The gap is not rainfall data.** It is the absence of a slope-scale, village-scale,
road-scale translation of that rainfall into an **actionable, acknowledged, auditable**
warning that reaches the right person, in a language they read, on a phone with two bars
of signal. That gap is the product.

## 3. Stack (non-negotiable)

**Frontend** — Next.js 15 (App Router, React 19, TS strict), Turbopack · Tailwind v4 +
shadcn/ui (Radix) + CVA · MapLibre GL v5 + deck.gl v9 via `MapboxOverlay` · MapLibre
native terrain (RGB DEM) + deck.gl `TerrainLayer` · visx or Recharts (never a themed
chart lib) · Framer Motion 11 (transform/opacity only) · Zustand + TanStack Query v5 +
nuqs · WebSocket with SSE fallback · Serwist PWA + Dexie/IndexedDB + Background Sync ·
next-intl.

**Backend** — Python 3.12 · FastAPI + Pydantic v2 · uvicorn/gunicorn · SQLAlchemy 2.0
async + Alembic · PostgreSQL 16 + PostGIS 3.4 + TimescaleDB · Redis 7 (cache, alert-bus
pub/sub, Celery broker) · Celery + Beat · MQTT (Mosquitto) · MinIO.

**ML/Geo** — scikit-learn, XGBoost, LightGBM, PyTorch · SHAP (mandatory) · rasterio,
rioxarray, xarray, geopandas, shapely, pyproj, richdem, whitebox · scipy/numpy/pandas ·
osmnx + networkx · MLflow.

**Infra** — Docker Compose (`make up` brings everything online) · GitHub Actions
(ruff + mypy + pytest + vitest + playwright + docker build) · Vercel (web) +
Railway/Fly.io (api, worker, db).

## 4. Data policy — real first, synthetic as labelled fallback

Every source implements `fetch(bbox, time_range) -> xarray.Dataset | GeoDataFrame`, is
toggleable by env var, cached in Redis with a TTL, and falls back to the synthetic
generator on timeout / error / rate-limit.

**The UI must always show a per-source status chip: LIVE (green) / CACHED (amber, with
age) / SIMULATED (blue).** Never let the UI imply simulated data is live. That honesty
is a scoring advantage, not a weakness.

Verified-reachable at Phase 0 (see `docs/DATA_SOURCES.md` for evidence and the full
list): Open-Meteo Forecast, Open-Meteo ERA5 Archive, NASA POWER, Microsoft Planetary
Computer STAC (`sentinel-1-rtc`, `sentinel-2-l2a`, `cop-dem-glo-30`, `esa-worldcover`
all confirmed present), Overpass/OSM, GSI Bhusanket portal, Bhuvan portal.
Key-gated or unverified: OpenTopography (HTTP 401, needs a free key), GPM IMERG
(Earthdata login), NASA COOLR (endpoint did not resolve at build time).

**Synthetic engine** must be deterministic and seeded: monsoon Markov wet/dry chain with
Gamma intensities, orographic multiplier by elevation and windward aspect, injectable
cyclone events, two-layer bucket soil-moisture model, 5 years hourly over ~250 grid
nodes, plus 60+ virtual MQTT sensor stations with noise, drift, battery decay and
dropout. The labelled inventory is generated by running the physics model over that
history, so the training set is internally consistent with physics.

## 5. Domain model

PostGIS geometry in EPSG:4326; area and distance computation in EPSG:32646.

`State · District · Block · Village` — admin hierarchy with population and households.
`SlopeUnit` — **the atomic risk object**: hydrologically derived slope polygons, not grid
cells. `TerrainProfile` — slope, aspect, plan/profile curvature, TWI, TPI, relief,
lithology, soil depth, land cover, distance to road/stream/fault.
`RainfallObservation`, `RainfallForecast`, `SoilMoistureState`, `SensorStation`,
`SensorReading`, `SensorHealth` — time series on TimescaleDB hypertables.
`RiskAssessment` — probability, factor of safety, severity, confidence band, model
version, explanation JSON, per horizon (6/24/72 h). `LandslideEvent` — historical and
confirmed, with Varnes classification. `CitizenReport` — geometry, EXIF coordinates,
media, AI class and confidence, verification status, reporter hash, votes.
`RoadSegment`, `RoadBlockage`, `ConnectivityImpact`. `Alert` (CAP v1.2) +
`AlertDelivery`. `Incident`, `ResponseTask`, `Resource`. `User`, `Role`, `AuditLog`.

Roles: `citizen · volunteer · village_head · block_officer · district_admin ·
state_admin · geologist · super_admin`.

## 6. The AI engine — four layers, all inspectable

Every other team ships one black-box classifier. We ship four layers and expose each.

1. **Physics** — infinite-slope Factor of Safety with transient pore pressure:
   `FoS = [c' + (γ·z·cos²β − u)·tan φ'] / (γ·z·sin β·cos β)`, with `u` from a simplified
   Iverson / Green–Ampt infiltration response. FoS below 1.0 is failure, 1.0–1.3 is
   marginal. Geotechnical parameters live in a seeded, database-backed table that the
   geologist role can edit in the UI.
2. **Empirical** — regional rainfall Intensity–Duration thresholds `I = α·D^−β` per state
   with bootstrap confidence bands, Antecedent Precipitation Index (k=0.85), 3/7/15/30-day
   cumulative rainfall, a tank-model Soil Water Index, and an exceedance ratio.
3. **ML** — susceptibility via an XGBoost + LightGBM ensemble evaluated with
   **leave-one-district-out spatial cross-validation** (random k-fold leaks spatially and
   inflates AUC; a judge may know this). Temporal hazard via a PyTorch TCN or GRU over 30
   days of rainfall, soil moisture, sensor deltas and the FoS series, predicting 6/24/72 h
   probability, trained with focal loss, calibrated with isotonic regression, with
   MC-dropout uncertainty.
4. **Deformation** — Sentinel-1 backscatter and coherence change over slope units, plus
   inverse-velocity (Fukuzono) time-of-failure estimation from tiltmeter and extensometer
   series with an R² quality gate that suppresses noisy fits.

**Fusion** is a calibrated blend that always returns the three components separately.
**Uncertainty is mandatory** — a confident-looking wrong number is a disaster here.

**Explainability (mandatory).** Clicking any risk score opens: a SHAP waterfall in plain
language, the FoS formula with real numbers substituted, the I–D plot with today's point,
a one-paragraph natural-language summary in the user's language, and the nearest
historical analogue event.

**Citizen vision model** — EfficientNet/MobileNetV3 transfer-learned to classify tension
crack, slope bulge, debris flow, road damage, retaining-wall failure, water seepage,
tilted tree or pole, and no hazard. Exported to ONNX and run in-browser via
onnxruntime-web so it works offline. EXIF GPS is validated against the reported location.
Confirmed reports feed a human-in-the-loop retraining queue.

## 7. Alerting — CAP v1.2, multi-channel, accountable

Every alert is a valid **CAP v1.2 XML** document with a "View CAP XML" button and a
public feed. This makes ShailSuraksha interoperable with the NDMA SACHET pipeline and any
CAP-consuming SDMA. It is the single detail that signals government-readiness most.

Four tiers, colour-locked product-wide: **GREEN** Normal · **YELLOW** Watch ·
**ORANGE** Warning · **RED** Evacuate.

Alert-fatigue controls are a scoring feature, so state them explicitly: hysteresis
(different up and down thresholds), minimum dwell time per level, confidence gating,
geographic de-duplication, and an operator override with mandatory justification written
to the audit log.

Channels: in-app over WebSocket, web push, SMS (Twilio and MSG91 adapters plus a stub
provider), WhatsApp, IVR by phrase concatenation per language, email, a public JSON/CAP
feed, and a siren/PA webhook. Officials must acknowledge; un-acknowledged ORANGE and RED
alerts auto-escalate up the hierarchy after the SLA. The dashboard shows the funnel:
issued → delivered → read → acknowledged → acted.

Two-way SMS grammar: `RISK <PIN>`, `REPORT <PIN> <code>`, `STOP`, `LANG <xx>`.

## 8. Multilingual and low-connectivity (PS-critical; most teams fake this)

Ten languages: English, Hindi, Assamese, Bengali, Manipuri/Meitei (both Bengali script and
Meitei Mayek), Mizo, Khasi, Nagamese, Nepali, Bodo. Citizen-facing and alert strings must
be **real translations**, never lorem-ipsum, with reviewers recorded in
`docs/TRANSLATIONS.md`. Noto font stack per script, subsetted.

Offline: an installable PWA with an offline shell; a **district pack** (PMTiles slice,
risk polygons, shelters, routes, contacts, guidance) in IndexedDB with visible size and
age; reports composed offline queue with their photos and flush via Background Sync; a
**Lite mode** under 50 KB, server-rendered, no map, auto-offered on 2G or save-data; an
SMS-first fallback; and a documented Cell Broadcast path.

## 9. The five dashboards (the problem statement names them)

1. **Risk severity** — the 3D map command centre, extruded slope-unit prisms, a time
   scrubber from −7 days to +72 hours, a layer switcher, and a click-to-explain drawer.
2. **Road and connectivity** — the OSM road graph, per-segment blockage probability,
   graph-cut isolation analysis, alternate routes, and a criticality ranking by
   betweenness centrality.
3. **Weather-linked forecast** — nowcast and forecast panels, the live I–D plot,
   cumulative gauges, a 72 h trajectory with a confidence ribbon, and the **what-if
   simulator**, the demo's climax: drag rainfall, recompute the surface server-side in
   under 3 seconds, morph the map.
4. **Response prioritisation** — a transparent, tunable multi-criteria index, a Kanban
   queue with SLA timers, a resource map, and isochrones that collapse when roads block.
5. **Citizen reports** — a moderation queue, AI class and confidence, EXIF badge,
   duplicate clustering, reporter trust score, and promote-to-incident.

Plus a **public citizen portal** with no login: "Am I safe right now?"

## 10. Design direction

**Positioning: "ISRO mission control meets Linear."** Dark, dense, precise, calm.
Not a bootstrap admin template, not neon cyberpunk. Restraint reads as competence.

Base `#070B14`, surface `#0D1424`, elevated `#16203A`, with a genuine light mode.
Severity locked: green `#22C55E`, amber `#F59E0B`, orange `#F97316`, red `#EF4444`, and
interactive cyan `#38BDF8`. All must be **verified** against WCAG AA on both surfaces.
Inter or Geist for UI, JetBrains Mono for all numerals with `tabular-nums`. A 4 px grid,
12 px radius, one shadow token per elevation. Motion of 150–250 ms, ease-out,
transform and opacity only, with full `prefers-reduced-motion` support.

Accessibility is not optional in a government product: keyboard navigation, visible focus
rings, ARIA on every custom control, `aria-live="assertive"` for RED alerts, a
colour-blind-safe mode with pattern fills, and a high-contrast mode.

## 11. Non-functional requirements

JWT access (15 min) and refresh (7 d), argon2 hashing, RBAC on every route, rate limiting.
**Every state-changing action writes an immutable AuditLog row** — disaster systems live
or die on accountability. OpenAPI 3.1, RFC 7807 errors, cursor pagination, ETag on geo
routes. structlog JSON logging, Prometheus metrics, health and readiness endpoints, and a
status page per provider. pytest for the physics and threshold math with known answers (a
wrong FoS is a credibility catastrophe), vitest for utilities, and Playwright for the
citizen report, alert issue and acknowledgement, and risk drill-down journeys. Targets:
LCP under 2.0 s, 60 fps map interaction, API p95 under 300 ms, and full NER risk
recomputation under 90 s. CSP headers, signed uploads, EXIF stripping on public media,
and no secrets in the repository.

## 12. Repository layout

```
web/     Next.js app (App Router, src/)
api/     FastAPI service + Alembic migrations
ml/      training, feature engineering, notebooks, model registry
ingest/  data providers, Celery tasks, synthetic generator
infra/   docker-compose, Dockerfiles, mosquitto/postgres config, CI templates
docs/    architecture, data sources, model card, data dictionary, design
```

## 13. Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D1 | Monorepo of plain directories, no Nx or Turborepo | Two languages but only one deployable JS app. A JS monorepo tool would manage `web/` alone and add CI noise. |
| D2 | npm, not pnpm | pnpm is absent on the build machine; npm 11 ships with Node 22 here. Revisit only if install time hurts. |
| D3 | The real `Makefile` sits at the repo root, compose and Dockerfiles under `infra/` | The spec requires `make up` to work from the root. `make` is absent on this Windows machine, so `make.ps1` mirrors every target. |
| D4 | Python 3.12 pinned in Docker and CI | The local interpreter is 3.13 and several geo and ML wheels (richdem, whitebox, some GDAL builds) lag a release. The container is the source of truth. |
| D5 | `next-themes` with `attribute="data-theme"` | Matches the §10 token strategy (`:root[data-theme="dark"]`) exactly and keeps the first paint flash-free. |
| D6 | MapLibre and deck.gl deferred to the map phases | Phase 0 is foundation only. Their version compatibility is tracked as a risk rather than silently assumed. |
| D7 | Admin boundaries from datameet/maps, GADM as fallback | Both verified reachable. The GADM licence restricts redistribution, so datameet leads. Provisional geometry must be labelled in the UI. |
| D8 | Synthetic data is always labelled, never silently substituted | Judge question one is "where does your data come from". Honesty is the differentiator. |
| D9 | Next.js pinned to 15.5.25, downgraded from the 16 that `create-next-app` installs | §3 names Next 15 as non-negotiable and that stack list goes into the submission. The scaffold also left a `web/AGENTS.md` describing Next 16 internals that do not exist in 15; it was replaced with accurate notes. Upgrading to 16 means changing the spec and the submission together. |
| D13 | WhiteboxTools is the terrain engine, not richdem | richdem publishes no distribution for Python 3.12 or 3.13, so it cannot be installed at all. WhiteboxTools ships a self-contained binary, covers every derivative the phase needs, and provides `hillslopes`, which produces genuine hydrological slope units rather than a grid. |
| D14 | Rasters fed to WhiteboxTools are written uncompressed and untiled | Measured, not assumed. With a DEFLATE-compressed tiled DEM, the slope tool returned 8,527 valid pixels out of 5.2 million and depression breaching produced elevations up to 3.9e37, while still exiting 0. Uncompressed, the same tool returned 5,203,183 valid pixels and a mean slope of 21.6 degrees. WhiteboxTools uses its own GeoTIFF reader, and the corruption is silent. Published COGs use predictor 3 for floats, never 2. |
| D15 | Elevation falls back from Copernicus GLO-30 to AWS Terrain Tiles | The Planetary Computer blob host served DEM assets at 0.10 MB/s and stalled at exactly 5 MiB twice, so a 46 MB tile never completed. AWS Terrain Tiles are keyless and fast enough. `dem_source` is recorded in every run manifest and no output may be presented as Copernicus-derived unless the manifest says so. |
| D16 | Administrative boundaries are matched on Census state codes, never on names | The datameet source spells Arunachal Pradesh as "Arunanchal Pradesh". Name filtering silently drops the region's largest state while the pipeline still succeeds. Codes 11 to 18 are stable; canonical names are supplied by our own code. |
| D23 | Health chip requires three consecutive failed polls before showing offline | One timed-out request on a weak connection is not an outage. A red "API offline" chip appeared on a single page mid-review while every other page was fine, which reads as a broken build. Failures must repeat to be believed; a success is trusted immediately. |
| D22 | Forecast rainfall is run through the physics layer to project stability forward, at /projection | The forecast rainfall and the infiltration model both already existed and were simply not joined. This is what turns a nowcast into warning lead time. The infiltration model is monotonic in rainfall and cannot reproduce a failure occurring after the rain stops; that limitation ships in the API response and on screen. |
| D21 | Material class is assigned per slope unit from landform position, not chosen globally | Scoring all 14,714 units against one cohesion and one friction angle left slope angle as the only thing varying across the map, which is why the risk layer read as a uniform wash. Terrain honestly resolves regolith type by position (valley floor, footslope, road cutting, in-place weathering) but NOT bedrock type, so only those four classes are assigned. Result: 2,387 distinct factor-of-safety values where there had been far fewer. |
| D20 | Road blockage uses a reliability model and runout reachability, ranked by expected count | The previous metric returned exactly 1.00 for every one of 741 segments and therefore ranked nothing. Two causes: mapping FoS to failure probability with clip(2-FoS,0,1) gave a stable slope a 61 percent failure chance, and combining ~40 contributors as independent events saturates at 1 regardless. Now: lognormal FoS reliability (COV 0.25), angle-of-reach weighting between 22 and 35 degrees, expected count as the ranking metric, and probability over only the top 5 contributors. |
| D19 | All stability screens initialise their wetness slider from the live reading | The overview ran on live soil moisture while the map, roads and response pages booted at a hardcoded 0.75, so navigating between pages silently changed every derived figure. A reviewer who sees the same named quantity take two values concludes the numbers are invented. The live value is now the default, marked on the slider track, with one click back to it; scenario mode is opt-in. |
| D18 | Added an all-India `/check` location tool, geolocation-first | Requested directly: check any location in India, using the visitor's current position. Outside the Noney pilot there is no slope-level data for anywhere in India, so rather than inventing a score the tool reports a real, citable fact instead: whether GSI's National Landslide Susceptibility Mapping programme covers that state, and which of its four hill belts. Verified against press coverage of the programme on 2026-09-09. |
| D17 | Default stream threshold is 30,000 cells | Measured on the pilot and extrapolated by area: 400 cells gives about 855,000 units region-wide, 30,000 gives about 10,200, which is inside the brief's 8,000 to 20,000 target. The tension is worth stating: units of roughly 24 km2 are catchment scale while a shallow landslide is 0.1 to 10 hectares, so the parameter is exposed on the command line rather than buried. |
| D11 | The Phase 5 landing page was built early, out of phase order, at the user's direction | Phase 0 delivered a status page, which read as a styled README and understated the project. The landing page depends only on the design system and public elevation tiles, not on phases 1 to 4, so it could be pulled forward. The live "highest risk district" ticker is deliberately **omitted** rather than faked, and returns when the risk engine exists. The rest of Phase 5, meaning the full primitive set, the app shell, the styleguide route and the contrast report, is still outstanding. |
| D12 | Hero terrain uses AWS Terrain Tiles and the CARTO dark style, both keyless | Both were probed and answered before any code was written. MapLibre is imported inside the effect rather than at module scope, because it touches `window` on import and would break server rendering, and this also keeps it out of the initial payload. If WebGL or the tile host is unavailable, the hero falls back to a terrain-toned gradient and the copy still reads. |
| D10 | Severity marker colours keep their locked hexes and gain a `--sev-*-outline` token | Measurement, not assumption: four of the five locked marks fail the WCAG 3:1 non-text threshold on a white surface (green 2.28, amber 2.15, orange 2.80, cyan 2.14). Changing them would break the colour lock, so markers are never drawn bare. Light-theme amber and red text were darkened to `#854d0e` and `#b91c1c`. All 76 pairs now pass, audited by `web/scripts/contrast.mjs` in CI. |

## 14. Open questions

- **Q1** Team name and member list for the landing page credits (Phase 5).
- **Q2** Native-speaker reviewers per language. Phase 9 requires named reviewers in `docs/TRANSLATIONS.md`, and machine-translated strings must be marked as such.
- **Q3** Deployment targets. Confirm the Vercel project, and Railway versus Fly.io for the API, worker and database, before the deploy phase.
- **Q4** Whether an Earthdata login and an OpenTopography key will be available. Both are free but they gate GPM IMERG and direct DEM download. Planetary Computer covers the DEM without a key, so this is not blocking.
- **Q5** Whether any real GSI inventory polygons can be obtained for the region. Until then the inventory is generated and must be labelled provisional everywhere it appears.

## 15. Standing rules for every session

1. **Never fabricate** an API endpoint, dataset URL, citation or accuracy number. If it is unverified, label it `unverified`.
2. **Never leave a TODO in a demo path.**
3. **Every number shown in the UI must be traceable** to a computation or a source.
4. **Prefer fewer, finished features** over many broken ones.
5. Write code a reviewer would enjoy reading: typed, small functions, named constants, and comments only where the *domain* is non-obvious.
6. Print measured metrics. Never invent them.

## 16. Phase tracker

| Phase | Scope | Status |
|---|---|---|
| 0 | Monorepo, docs, compose, CI, design tokens, app shell | **Complete** |
| 1 | Geospatial foundation, DEM derivatives, slope units, PMTiles | **Mostly complete.** Migration, boundaries, DEM pipeline, derivatives, slope units, COGs, OSM, CLI and tests all done and run on a pilot. Outstanding: ESA WorldCover land cover, PMTiles generation (needs the container), regional-scale run, and loading into a live database. |
| 2 | Weather, satellite and sensor ingestion, synthetic engine, MQTT | Not started |
| 3 | The four-layer AI engine and explainability | **Physics layer complete** and served live: factor of safety, pore pressure, six geotech classes, 27 known-answer tests, sensitivity analysis, wired into the map. Empirical, ML and deformation layers not started. |
| 4 | API surface, auth, CAP v1.2 alert engine, delivery channels | Not started |
| 5 | Design system, shell, landing page | **Landing page and app shell delivered.** Sidebar navigation, top bar with live clock and API connection state, stat tiles, panels, tables and charts. Missing: the styleguide route, command palette and the published contrast report. |
| 6 | Dashboard 1, the 3D risk command centre | **Core delivered.** 14,714 slope units on 3D terrain, terrain and stability modes, material and wetness controls, click-to-inspect with the worked equation. Missing: time scrubber, WebSocket updates, alert issue action. |
| 7 | Dashboards 2 and 3, connectivity and weather/what-if | **Both delivered in first form.** Roads screen computes blockage from adjacent slope stability with live controls. Weather screen serves genuinely live Open-Meteo rainfall and soil moisture. Missing: the road graph cut with networkx, isolated-village analysis, and the I-D threshold chart. |
| 8 | Dashboards 4 and 5, response and citizen reports | **Both delivered in first form.** Response ranks segments by blockage times route weight with the weights shown. Citizen reports run end to end: submit from the portal, moderate in the console. Missing: population and vulnerability terms, isochrones, the Kanban board, on-device classification and EXIF checks. |
| 9 | Citizen PWA, offline packs, Lite mode, ten languages, accessibility pass | **Public portal delivered**: live status, plain-language actions, working report form. Missing: the service worker, offline district pack, Lite mode, web push and the remaining six language catalogues. |
| 10 | Alert operations console, stub delivery inbox, admin surfaces, analytics, PDF and CSV reports | Not started |
| 11 | Hardening, the five Playwright journeys, performance, security, `make demo` seed, full docs | Not started |
| D | Deploy: Vercel for web, Railway or Fly.io for API, worker, beat, Redis, Postgres | Not started |

**Current phase: 1 mostly complete, the Phase 3 physics layer complete, and the Phase 5
landing page plus the Phase 6 map core delivered.**

Phase 1 ran end to end on the Noney pilot: 14,714 slope units over 4,486 km2, mean
slope 21.1 degrees. See `data/terrain/noney_30m/report.json` for the measured run.

Run each phase prompt one at a time and in order. After each phase, run the app and
screenshot it. If a phase's acceptance criteria are not met, re-prompt that phase rather
than moving on, because broken foundations compound.
