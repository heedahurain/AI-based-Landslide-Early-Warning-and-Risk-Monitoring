# Data dictionary

The domain model, entity by entity. Geometry is stored in **EPSG:4326**; areas,
distances and buffers are computed in **EPSG:32646** (UTM 46N), which covers the
North Eastern Region with acceptable distortion.

Status: this is the target schema. Alembic migrations arrive with their phases,
noted per section. Nothing here exists in the database at the end of Phase 0.

## Conventions

- Primary keys are `UUID` unless a natural key exists and is stable.
- Every table carries `created_at` and `updated_at` with server-side defaults, so
  a timestamp never depends on which process wrote the row.
- Time series live in TimescaleDB hypertables with 7-day chunks.
- Every geometry column gets a **GIST** index; every hypertable time column gets
  a **BRIN** index.
- `source` on any observed value records where it came from, and is one of
  `live`, `cached` or `synthetic`. This column is the database half of the
  promise that the UI never presents simulated data as live.

---

## 1. Administrative hierarchy — Phase 1

### `state`, `district`, `block`, `village`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `name` | text | |
| `name_local` | jsonb | Name per locale, so a village appears in the reader's script |
| `code` | text | Census or LGD code where known |
| `parent_id` | UUID | Null for `state` |
| `geom` | `geometry(MultiPolygon, 4326)` | GIST indexed |
| `population` | integer | Nullable; source recorded in `attributes` |
| `households` | integer | Nullable |
| `provisional` | boolean | **True when geometry is not from an official source** |
| `attributes` | jsonb | Source, vintage, licence |

`provisional` is not decorative. Community boundary data can disagree with
official Survey of India boundaries, especially along the international and
interstate borders of the North East, and the UI must label such geometry as
indicative rather than authoritative. See `docs/DATA_SOURCES.md` §4.

---

## 2. Terrain — Phase 1

### `slope_unit`

The atomic risk object. Hydrologically derived half-basins split by drainage and
divide lines, **not** grid cells: a grid cell has no physical meaning, while a
slope unit fails or holds as a unit. Target 8,000–20,000 units for the region.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `geom` | `geometry(Polygon, 4326)` | GIST indexed |
| `area_m2` | double | Computed in EPSG:32646 |
| `centroid` | `geometry(Point, 4326)` | For fast label and camera placement |
| `village_id` | UUID | Nullable; a unit may span or fall outside a village |
| `district_id` | UUID | Denormalised for the leave-one-district-out split |

### `terrain_profile`

One row per slope unit, joined at ingest so inference never recomputes terrain.

| Column | Type | Unit | Notes |
|---|---|---|---|
| `slope_unit_id` | UUID | | Primary key |
| `slope_deg` | double | degrees | Mean; also `slope_max_deg` |
| `aspect_deg` | double | degrees | Circular mean |
| `plan_curvature` | double | 1/m | Convergence of flow |
| `profile_curvature` | double | 1/m | Acceleration of flow |
| `twi` | double | — | Topographic wetness index |
| `tpi` | double | — | Topographic position index |
| `flow_accumulation` | double | cells | |
| `local_relief_m` | double | m | |
| `distance_to_stream_m` | double | m | |
| `distance_to_road_m` | double | m | Proxy for cut-slope destabilisation |
| `distance_to_fault_m` | double | m | Nullable where no fault data |
| `lithology_class` | text | | Foreign key to `geotech_parameter` |
| `soil_depth_m` | double | m | **Estimated**, a leading error source |
| `land_cover_class` | smallint | | ESA WorldCover code |

---

## 3. Weather and soil — Phase 2

### `rainfall_observation` (hypertable)

| Column | Type | Notes |
|---|---|---|
| `grid_node_id` | UUID | |
| `ts` | timestamptz | Partition key, 7-day chunks |
| `mm` | real | Accumulation in the interval |
| `source` | text | Provider key, plus `live`/`cached`/`synthetic` |

Continuous aggregates: hourly, daily, and rolling 3, 7, 15 and 30-day totals.
These are what the empirical layer reads, so the antecedent indices never
require a full scan during inference.

### `rainfall_forecast` (hypertable)

Adds `issued_at`, `valid_at` and `member`, so a forecast is always attributable
to the run that produced it and skill can be scored after the fact.

### `soil_moisture_state` (hypertable)

`slope_unit_id`, `ts`, `layer` (the five Open-Meteo depths), `vwc` in m³/m³,
`source`. Drives the pore-pressure term in the physics layer.

---

## 4. Sensors — Phase 2

### `sensor_station`

`id`, `code`, `geom`, `station_type` (`rain_gauge`, `tiltmeter`, `piezometer`,
`soil_moisture`, `extensometer`), `slope_unit_id`, `installed_at`, `is_virtual`.

`is_virtual` is true for simulated stations. It is never hidden in the UI.

### `sensor_reading` (hypertable)

`station_id`, `ts`, `metric`, `value`, `quality` (`ok`, `suspect`, `stale`).

### `sensor_health`

`station_id`, `last_seen_at`, `battery_pct`, `drift_estimate`, `dropout_rate`,
`state`. Unhealthy stations are excluded from inference rather than silently
feeding it corrupted features.

---

## 5. Risk — Phase 3

### `geotech_parameter`

Editable by the geologist role, with every edit audited.

| Column | Type | Unit | Notes |
|---|---|---|---|
| `lithology_class` | text | | Primary key |
| `cohesion_kpa` | double | kPa | Effective cohesion `c'` |
| `friction_angle_deg` | double | degrees | Effective friction angle `φ'` |
| `unit_weight_kn_m3` | double | kN/m³ | `γ` |
| `ksat_m_s` | double | m/s | Saturated hydraulic conductivity |
| `typical_soil_depth_m` | double | m | |
| `source_reference` | text | | Citation for the values |

### `risk_assessment`

| Column | Type | Notes |
|---|---|---|
| `slope_unit_id` | UUID | |
| `issued_at` | timestamptz | Hypertable partition key |
| `horizon_h` | smallint | 6, 24 or 72 |
| `probability` | real | Fused, calibrated |
| `confidence_low`, `confidence_high` | real | 90% interval; never null |
| `factor_of_safety` | real | Physics layer output |
| `empirical_exceedance` | real | Position against the I–D threshold |
| `ml_probability` | real | ML layer alone |
| `severity` | text | `green`, `yellow`, `orange`, `red` |
| `model_version` | text | MLflow version, so a decision is reproducible |
| `explanation_json` | jsonb | SHAP contributions, substituted FoS terms, analogue event |
| `inputs_simulated` | boolean | True if any input was synthetic; propagates to the alert |

The three component columns exist so the UI can always show the fusion split.
`confidence_low` and `confidence_high` are `NOT NULL` by design: a prediction
without an uncertainty band must not be storable.

### `landslide_event`

Historical and confirmed events: `geom`, `occurred_on`, `fatalities`, `volume_m3`,
`varnes_type`, `source`, `is_provisional`. Trigger attribution where known.

---

## 6. Citizen reports — Phase 8

`citizen_report`: `geom`, `exif_lat`, `exif_lon`, `media_keys`, `category`,
`ai_classification`, `ai_confidence`, `verification_status`, `reporter_hash`,
`votes`, `submitted_offline_at`.

`reporter_hash` stores a hash, never an identity. EXIF is stripped from any
publicly served copy while the original is retained for moderation.

---

## 7. Connectivity — Phase 7

`road_segment` (`geom`, `osm_id`, `highway_class`, `betweenness_centrality`),
`road_blockage` (`probability`, `assessed_at`, `contributing_slope_units`),
`connectivity_impact` (isolated villages, population cut off, alternate route
and added travel time).

---

## 8. Alerting — Phase 4

### `alert`

CAP v1.2 fields are stored as columns, not generated at render time, so the XML
served is exactly the record that was issued: `identifier`, `sender`, `sent`,
`status`, `msg_type`, `scope`, `category`, `event`, `urgency`, `severity`,
`certainty`, `area_geom`, `area_geocodes`, `parameters`, `expires`.

Plus lifecycle: `state`, `issued_by`, `override_justification`,
`superseded_by_id`.

### `alert_delivery`

`alert_id`, `channel`, `recipient_group`, `language`, `sent_at`, `delivered_at`,
`read_at`, `acknowledged_at`, `failure_reason`. This table is the acknowledgement
funnel and the answer to "was anyone actually told".

---

## 9. Response — Phase 8

`incident`, `response_task` (with SLA timers), `resource` (NDRF and SDRF teams,
JCBs, ambulances, relief camps with capacity).

---

## 10. Identity and audit — Phase 4

`user`, `role`, and `audit_log`.

`audit_log` is append-only: `actor_id`, `action`, `target_type`, `target_id`,
`before`, `after`, `ip`, `ts`. Alert **suppressions** are audited alongside
issuances, because "why was I not warned" is as important a question as "why was
I warned".
