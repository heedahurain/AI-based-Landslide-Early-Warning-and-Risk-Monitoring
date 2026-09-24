# ShailSuraksha — Architecture

Status: Phase 0 (foundation). This document describes the target architecture. Components
that do not yet exist in code are marked **(planned, Phase N)** so the diagram never
overstates what is built.

---

## 1. Design principles

1. **Every number is traceable.** A risk probability on screen can be walked back through
   fusion → its three component layers → the features → the source record → the provider
   and its fetch timestamp. This is what survives the "why should I trust this number"
   question.
2. **Degrade, never lie.** Any provider can fail. When it does, the system falls back to
   cache and then to the synthetic engine, and the UI says so with a per-source chip.
3. **The slope unit is the atomic object.** Risk is computed on hydrologically derived
   slope polygons, not on grid cells and not on administrative units. Administrative
   aggregates are derived upward from slope units for reporting.
4. **Accountability is a first-class feature.** Alerts have a lifecycle with
   acknowledgements and escalation, and every state change writes an immutable audit row.
5. **The last mile is the product.** Offline packs, Lite mode, SMS and IVR are not
   fallbacks bolted on at the end; they are the delivery path for the users who most need
   the warning.

---

## 2. C4 Level 1 — System context

```mermaid
C4Context
  title ShailSuraksha — System Context

  Person(citizen, "Citizen / Villager", "Checks local risk, reports hazards from a phone, often offline or on 2G")
  Person(official, "District & Block Officials", "DDMA officers, block officers, village heads. Receive, acknowledge and act on alerts")
  Person(geologist, "Geologist / Analyst", "Tunes geotechnical parameters, audits model behaviour, validates events")
  Person(responder, "Response Teams", "NDRF / SDRF, ambulance and JCB crews acting on prioritised tasks")

  System(shail, "ShailSuraksha", "Landslide early-warning and risk-monitoring platform for the eight NER states")

  System_Ext(weather, "Weather & Reanalysis APIs", "Open-Meteo Forecast, Open-Meteo ERA5 Archive, NASA POWER")
  System_Ext(satellite, "Satellite & Terrain", "Planetary Computer STAC: Sentinel-1 RTC, Sentinel-2 L2A, Copernicus DEM GLO-30, ESA WorldCover. GPM IMERG via GES DISC")
  System_Ext(osm, "OpenStreetMap", "Road network, buildings, hospitals, schools, helipads via Overpass and osmnx")
  System_Ext(gov, "Government Reference", "GSI Bhusanket and the National Landslide Susceptibility Map, Bhuvan WMS, IMD")
  System_Ext(channels, "Delivery Channels", "SMS gateway, WhatsApp Business, IVR, web push, siren and PA webhooks")
  System_Ext(sachet, "NDMA SACHET / CAP consumers", "Consume our CAP v1.2 feed")

  Rel(citizen, shail, "Checks risk, files geotagged reports", "HTTPS / PWA / SMS")
  Rel(official, shail, "Monitors, issues and acknowledges alerts", "HTTPS / WebSocket")
  Rel(geologist, shail, "Tunes parameters, audits explanations", "HTTPS")
  Rel(responder, shail, "Receives tasks, updates status", "HTTPS / SMS")

  Rel(shail, weather, "Rainfall forecast, ERA5 history, soil moisture", "HTTPS JSON")
  Rel(shail, satellite, "DEM, backscatter change, NDVI, land cover", "STAC / COG")
  Rel(shail, osm, "Road graph and critical facilities", "Overpass API")
  Rel(shail, gov, "Susceptibility baseline, reference basemaps", "WMS / portal")
  Rel(shail, channels, "Dispatches multi-channel alerts", "Provider APIs")
  Rel(shail, sachet, "Publishes CAP v1.2 alerts", "CAP XML feed")
```

## 3. C4 Level 2 — Containers

```mermaid
C4Container
  title ShailSuraksha — Container Diagram

  Person(citizen, "Citizen")
  Person(official, "Official / Geologist")

  Container_Boundary(edge, "Edge") {
    Container(web, "Web App", "Next.js 15, React 19, TypeScript", "Five dashboards, public portal, Lite mode, PWA with offline district packs")
    Container(sw, "Service Worker", "Serwist + Dexie/IndexedDB", "Offline shell, district pack cache, background sync queue for reports and acknowledgements")
  }

  Container_Boundary(app, "Application") {
    Container(api, "API Service", "FastAPI, Pydantic v2, SQLAlchemy 2.0 async", "REST v1, auth and RBAC, alert engine, CAP generation, WebSocket hub")
    Container(worker, "Celery Worker", "Celery", "Ingestion, feature building, risk inference, alert dispatch, escalation timers")
    Container(beat, "Celery Beat", "Celery Beat", "Forecast 30 min, observations 15 min, satellite daily, aggregates hourly, inference 30 min")
    Container(mqttc, "MQTT Consumer", "asyncio + paho/gmqtt", "Subscribes to field sensor topics, writes readings, maintains sensor health")
  }

  Container_Boundary(data, "Data") {
    ContainerDb(pg, "PostgreSQL 16", "PostGIS 3.4 + TimescaleDB", "Admin hierarchy, slope units, terrain profiles, hypertables for rainfall, soil moisture and sensor readings, risk assessments, alerts, audit log")
    ContainerDb(redis, "Redis 7", "Redis", "Provider cache with TTL, Celery broker, pub/sub alert bus, rate limiting")
    ContainerDb(minio, "MinIO", "S3-compatible", "COG terrain derivatives, PMTiles, citizen media, model artefacts")
    Container(mqtt, "Mosquitto", "MQTT broker", "Field sensor telemetry, real and simulated")
    Container(mlflow, "MLflow", "Tracking + registry", "Experiments, metrics, model versions")
  }

  Container_Boundary(pipelines, "Pipelines (code, run by worker)") {
    Container(ingest, "ingest/", "Python", "Provider registry, retry and fallback, synthetic generator, sensor simulator")
    Container(ml, "ml/", "Python", "Physics, empirical, ML and deformation layers, fusion, SHAP explanation")
  }

  Rel(citizen, web, "HTTPS")
  Rel(official, web, "HTTPS + WebSocket")
  Rel(web, sw, "Registers, reads offline packs")
  Rel(web, api, "REST, WebSocket, SSE fallback", "JSON")
  Rel(api, pg, "Async SQL", "asyncpg")
  Rel(api, redis, "Cache, pub/sub")
  Rel(api, minio, "Signed URLs, tiles")
  Rel(worker, ingest, "Runs providers")
  Rel(worker, ml, "Runs inference")
  Rel(beat, worker, "Enqueues scheduled tasks", "Redis broker")
  Rel(worker, pg, "Writes observations, features, risk")
  Rel(worker, mlflow, "Logs runs, loads registered models")
  Rel(mqttc, mqtt, "Subscribes")
  Rel(mqttc, pg, "Writes sensor readings")
  Rel(api, worker, "Dispatch and escalation tasks", "Redis broker")
```

## 4. Data flow — source to acknowledgement

The spine of the system. Read left to right; each arrow is a place where provenance is
recorded.

```mermaid
flowchart LR
  subgraph S["1 · Sources"]
    A1["Open-Meteo<br/>forecast + soil moisture"]
    A2["ERA5 archive<br/>NASA POWER"]
    A3["Sentinel-1 / 2<br/>Copernicus DEM"]
    A4["MQTT field sensors"]
    A5["Citizen reports"]
    A6["Synthetic engine<br/>(seeded, labelled)"]
  end

  subgraph I["2 · Ingest"]
    B1["Provider registry<br/>toggle · retry · TTL cache"]
    B2{"Healthy?"}
    B3["Status: LIVE / CACHED / SIMULATED"]
  end

  subgraph F["3 · Feature store"]
    C1["Hypertables<br/>rainfall · soil moisture · sensors"]
    C2["Continuous aggregates<br/>3 / 7 / 15 / 30 day"]
    C3["Terrain profile<br/>slope · TWI · curvature"]
  end

  subgraph M["4 · Risk engine"]
    D1["Physics<br/>Factor of Safety"]
    D2["Empirical<br/>I–D threshold + API"]
    D3["ML<br/>susceptibility + TCN hazard"]
    D4["Deformation<br/>InSAR change + inverse velocity"]
    D5["Calibrated fusion<br/>+ uncertainty band"]
    D6["SHAP explanation"]
  end

  subgraph AL["5 · Alerting"]
    E1["Tier rules<br/>GREEN · YELLOW · ORANGE · RED"]
    E2["Fatigue controls<br/>hysteresis · dwell · dedupe · confidence gate"]
    E3["CAP v1.2 XML"]
  end

  subgraph CH["6 · Channels"]
    F1["In-app + WebSocket"]
    F2["Web push"]
    F3["SMS / IVR"]
    F4["WhatsApp / email"]
    F5["Siren + PA webhook"]
    F6["Public CAP feed → SACHET"]
  end

  subgraph K["7 · Accountability"]
    G1["AlertDelivery<br/>sent · delivered · read · acked"]
    G2["Escalation on SLA breach"]
    G3["Immutable AuditLog"]
  end

  A1 & A2 & A3 & A4 & A5 --> B1
  B1 --> B2
  B2 -- no --> A6
  B2 -- yes --> B3
  A6 --> B3
  B3 --> C1 --> C2
  C3 --> D1
  C2 --> D1 & D2 & D3
  A4 --> D4
  A3 --> D4
  D1 & D2 & D3 & D4 --> D5 --> D6
  D5 --> E1 --> E2 --> E3
  E3 --> F1 & F2 & F3 & F4 & F5 & F6
  F1 & F2 & F3 & F4 --> G1 --> G2
  G1 --> G3
  E2 --> G3
```

### Provenance contract

Every `RiskAssessment` row carries `model_version` and an `explanation_json` that names
the source records and the fetch status behind each feature. A user drilling into a score
sees the provider, its status chip and the age of the data that produced it. If any input
was `SIMULATED`, the assessment is flagged as such all the way to the alert.

## 5. Alert lifecycle

```mermaid
stateDiagram-v2
  [*] --> Evaluated: risk assessment written
  Evaluated --> Suppressed: below tier / inside dwell time / duplicate / low confidence
  Suppressed --> [*]
  Evaluated --> Draft: tier crossed with hysteresis margin
  Draft --> Issued: auto-issue or operator approval
  Draft --> Overridden: operator override with mandatory justification
  Overridden --> Issued
  Issued --> Delivered: channel adapters report accepted
  Delivered --> Read: recipient opened
  Read --> Acknowledged: official acknowledges
  Delivered --> Escalated: SLA elapsed without acknowledgement
  Escalated --> Acknowledged
  Acknowledged --> Acted: response task closed
  Acted --> Cancelled: risk falls below the down-threshold
  Issued --> Updated: new assessment changes severity
  Updated --> Issued
  Cancelled --> [*]
  Acted --> [*]
```

Every transition writes an `AuditLog` row with actor, action, target, before and after
state, IP address and timestamp. `Suppressed` is audited too, because "why was I not
warned" is as important a question as "why was I warned".

## 6. Offline and degraded-network path

```mermaid
flowchart TD
  N{"Network state"}
  N -- "good" --> ONLINE["Full PWA<br/>map, 3D terrain, live WebSocket"]
  N -- "2G / save-data" --> LITE["Lite mode<br/>server-rendered, under 50 KB, no tiles"]
  N -- "offline" --> PACK["District pack from IndexedDB<br/>PMTiles slice, risk polygons, shelters, routes, guidance"]
  N -- "no data network" --> SMS["Two-way SMS<br/>RISK PIN · REPORT PIN code · LANG xx"]
  N -- "no cellular data at all" --> CB["Cell Broadcast<br/>documented last-mile path"]

  PACK --> QUEUE["Reports and acknowledgements<br/>queued in IndexedDB with photos"]
  QUEUE -- "connectivity returns" --> SYNC["Background Sync flush"]
  SYNC --> API["API"]
  ONLINE --> API
  LITE --> API
  SMS --> GW["SMS adapter"] --> API
```

## 7. Deployment topology

```mermaid
flowchart LR
  subgraph Edge
    V["Vercel<br/>Next.js web"]
  end
  subgraph Platform["Railway / Fly.io"]
    A["API (gunicorn + uvicorn workers)"]
    W["Celery worker"]
    B["Celery beat"]
    Q["MQTT consumer"]
  end
  subgraph Managed
    P["PostgreSQL 16<br/>PostGIS + TimescaleDB"]
    R["Redis 7"]
    S["MinIO / S3"]
    M["Mosquitto"]
  end
  V --> A
  A --> P & R & S
  W --> P & R & S
  B --> R
  Q --> M
  Q --> P
```

Local development runs the identical set through `infra/docker-compose.yml`, so the only
difference between a laptop and the deployed system is where the managed services live.

## 8. Key architectural risks

| Risk | Impact | Mitigation | Phase to resolve |
|---|---|---|---|
| deck.gl v9 and MapLibre v5 interop via `MapboxOverlay` | The signature visual fails | Version-pin and spike early in the map phase before building layers on top | 5–6 |
| Risk recomputation for the whole NER exceeding the 90 s budget | The what-if simulator stops feeling live | Vectorise with numpy and xarray over slope-unit arrays instead of per-unit loops; profile from the first implementation | 3, 7 |
| Slope-unit delineation producing too few or too many polygons | Either coarse risk or an unusable map | Target 8,000–20,000 units, tune the drainage threshold, and report the actual count | 1 |
| Geotechnical parameters being effectively guesses | A geologist judge can dismantle the FoS claim | Keep parameters in an editable, sourced, per-lithology table and show sensitivity ranges rather than false precision | 3 |
| Provider rate limits or outages during the live demo | The demo appears broken | Pre-warmed Redis cache, deterministic synthetic fallback, and honest status chips | 2 |
| Translation quality for low-resource languages | The core equity claim weakens | Record every reviewer and mark machine-translated strings explicitly | 9 |

## 9. What exists today (end of Phase 0)

Built: the monorepo skeleton, the documentation set, Docker Compose for the full local
stack, the Makefile and its PowerShell mirror, CI, and the Next.js application shell with
the design tokens, the theme toggle and next-intl wiring.

Not yet built: everything inside the pipelines and the risk engine. Phases 1 through 11
in `PROJECT_CONTEXT.md` §16 fill them in, in that order.
