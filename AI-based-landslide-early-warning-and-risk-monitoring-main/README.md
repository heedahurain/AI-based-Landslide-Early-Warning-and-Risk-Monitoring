# ShailSuraksha

**AI-based landslide early warning and risk monitoring for the eight North Eastern states
of India.**

Smart India Hackathon 2026 · Problem statement **SIH26001** · Ministry of Development of
North Eastern Region, Government of India.

> A decision-support tool. Not a substitute for official warnings from the Geological
> Survey of India or the India Meteorological Department.

---

## The problem

The North Eastern Region receives 2000–4000 mm of rain a year on young, tectonically
active, deeply weathered slopes, made worse by road cutting, unplanned hill construction
and railway earthworks.

| Event | When | Toll |
|---|---|---|
| Tupul / Noney, Manipur | June 2022 | approximately 55–61 killed |
| Aizawl, Mizoram | May 2024 | 20+ killed in a single day |
| Assam, Arunachal, Manipur | mid-2025 | 20+ deaths across states within days |

**The gap is not rainfall data.** It is the absence of a slope-scale, village-scale,
road-scale translation of that rainfall into an actionable, acknowledged, auditable
warning that reaches the right person, in a language they read, on a phone with two bars
of signal.

## What makes this different

- **Four inspectable layers, not one black box.** Physics (infinite-slope factor of
  safety with transient pore pressure), empirical (rainfall intensity–duration
  thresholds), machine learning (susceptibility ensemble plus a temporal hazard network)
  and deformation (InSAR change detection plus inverse-velocity failure timing). Fusion
  always returns the components separately.
- **Every number is traceable.** Click a risk score and see the SHAP contributions in
  plain language, the factor-of-safety formula with real numbers substituted, the
  threshold plot with today's point, and the nearest historical analogue.
- **Honest provenance.** Every value carries a chip: LIVE, CACHED with its age, or
  SIMULATED. No code path strips that label.
- **CAP v1.2 alerts**, making the system interoperable with the NDMA SACHET pipeline and
  any CAP-consuming state authority.
- **Accountability.** Alerts require acknowledgement, unacknowledged high-tier alerts
  escalate, and every state change writes an immutable audit row, including suppressions.
- **The last mile is the product.** Ten languages, offline district packs, a sub-50 KB
  Lite mode, two-way SMS and IVR.

## Repository layout

```
web/     Next.js 15 app (App Router, React 19, Tailwind v4)
api/     FastAPI service and Alembic migrations
ml/      training, feature engineering, notebooks, model registry
ingest/  data providers, Celery tasks, synthetic generator
infra/   docker-compose, Dockerfiles, service configuration
docs/    architecture, data sources, model card, data dictionary, translations
scripts/ operational scripts, including the data source probe
```

## Getting started

**Prerequisites:** Docker Desktop, Node 22, Python 3.12 or newer, and GNU make (optional
on Windows, see below).

```bash
cp .env.example .env
make up
```

That brings up PostgreSQL 16 with PostGIS and TimescaleDB, Redis, Mosquitto, MinIO, the
API and the web app.

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| MinIO console | http://localhost:9002 |

**On Windows without make**, every target has a mirror:

```powershell
./make.ps1 up
./make.ps1 test
./make.ps1 help
```

### Working without Docker

```bash
make install-py     # creates .venv and installs dev dependencies
make install-web    # npm ci in web/
make test           # Python and web suites, plus the WCAG contrast audit
```

## Verifying the data sources

Run this before every demo and before every judging session:

```bash
python scripts/probe_sources.py
```

It contacts every upstream source and prints what actually answered, distinguishing a
source that is down from one that is merely gated behind a free credential, and from a
stale certificate store on your own machine. Update the probe date at the top of
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) after a run.

## Documentation

| Document | What it covers |
|---|---|
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | The condensed authoritative spec. **Read this first.** |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | C4 diagrams, the data flow, the alert lifecycle, known risks |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Every provider, its status as measured, licence and fallback |
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | Intended use, limitations, failure modes, ethics |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | The domain model, entity by entity |
| [docs/TRANSLATIONS.md](docs/TRANSLATIONS.md) | Which languages are authored, and who reviewed them |
| [docs/PITCH.md](docs/PITCH.md) | Demo script, coverage matrix, judge defence pack |

## Project status

**Phase 0 of 11 complete: the foundation.** The monorepo, documentation, container stack,
CI and the application shell with its design tokens exist and are verified. No risk model
has been trained, and nothing in the interface is a forecast yet.

The eleven-phase plan and the deploy step are in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) §16.
The idea submission is due **30 September 2026**, and it is judged on the write-up rather
than the code. [docs/PITCH.md](docs/PITCH.md) holds the demo script and the defence pack.

## Testing

```bash
make test        # everything
make test-api    # pytest
make test-web    # vitest plus the WCAG contrast audit
make lint
make typecheck
```

The contrast audit fails the build if any design token pair drops below WCAG AA. In a
warning system, colour is a safety property rather than a matter of taste.

## Licence

To be decided before publication. Note that some upstream data carries redistribution
restrictions: GADM is non-commercial, and OpenStreetMap is ODbL with share-alike
obligations on derived geometric databases. See
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
