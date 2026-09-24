# ShailSuraksha — Data Sources

**Probe date: 2026-09-08.** Every status below was measured from this build machine on
that date with a plain HTTP request, not assumed. Re-run `make probe-sources` to refresh
the evidence before a demo.

Status vocabulary, used identically in this document, in the provider registry and on the
UI chips:

| Status | Meaning |
|---|---|
| `verified` | The endpoint answered as documented from this machine, and the response shape was inspected. |
| `key-required` | The endpoint exists and answered, but returns data only with a credential we do not yet hold. |
| `reachable` | The host answered, but we have not yet exercised the specific data path we intend to use. |
| `unverified` | Could not be confirmed at build time. Routed to the synthetic fallback and labelled in the UI. |

**Rule that overrides everything else in this file:** no provider may present synthetic
output as live. The registry attaches `LIVE`, `CACHED` or `SIMULATED` to every payload and
the UI renders it as a chip. See `PROJECT_CONTEXT.md` §4.

---

## 1. Weather, rainfall and soil moisture

### 1.1 Open-Meteo Forecast — `verified` — **primary live source**

- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Key:** none required.
- **Probe result:** HTTP 200. A request for the full hourly variable set returned real
  values with units `mm` for precipitation, `m³/m³` for every soil moisture layer and
  `°C` for soil temperature.
- **Variables pulled:** `precipitation`, `rain`, `precipitation_probability`,
  `relative_humidity_2m`; soil moisture `soil_moisture_0_to_1cm`, `1_to_3cm`, `3_to_9cm`,
  `9_to_27cm`, `27_to_81cm`; soil temperature `0cm`, `6cm`, `18cm`, `54cm`.
- **Why it matters:** this single source supplies forecast rainfall *and* modelled soil
  moisture, which makes it the backbone of the live demo and the direct input to the
  pore-pressure term in the physics layer.
- **Cadence:** refresh every 30 minutes. Redis TTL 30 minutes.
- **Batching:** up to 100 coordinates per call for the grid nodes.
- **Licence:** free for non-commercial use with attribution; data derived from national
  weather services. Confirm the current terms before any commercial deployment.
- **Fallback:** synthetic monsoon generator, labelled `SIMULATED`.

### 1.2 Open-Meteo Historical / ERA5 Archive — `verified`

- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Key:** none. **Probe result:** HTTP 200 for an hourly precipitation window covering
  the Noney event dates in June 2022.
- **Use:** antecedent rainfall history, the Intensity–Duration threshold fit, and
  back-testing against known landslide dates.
- **Cadence:** on demand, cached for 24 hours. ERA5 lags real time by roughly five days,
  so it is a training and validation source, never a nowcast source.
- **Fallback:** synthetic history.

### 1.3 NASA POWER — `verified`

- **Endpoint:** `https://power.larc.nasa.gov/api/temporal/daily/point`
- **Key:** none. **Probe result:** HTTP 200 for `PRECTOTCORR` over a June 2022 window.
- **Use:** daily precipitation as an independent cross-validation series. The forecast
  dashboard shows Open-Meteo against NASA POWER and flags divergence, which is a direct
  answer to "why should I trust this number".
- **Cadence:** daily. **Licence:** NASA open data, freely redistributable.

### 1.4 NASA GPM IMERG — `key-required`

- **Host:** `https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/` answered HTTP 200, but
  data access requires an Earthdata Login and an authorised application.
- **Use:** half-hourly satellite precipitation, the basis of the "satellite rainfall"
  claim.
- **Setup:** register at Earthdata, authorise the GES DISC application, then set
  `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`. Full steps belong in the Phase 2 provider
  docstring.
- **Behaviour without credentials:** the provider reports `key-required`, does not fail
  the pipeline, and the UI shows the satellite rainfall layer as unavailable rather than
  substituting another source silently.

### 1.5 India Meteorological Department — `reachable`, display and reference only

- **Host:** `https://mausam.imd.gov.in` answered HTTP 200.
- There is no open, documented public API we can rely on. IMD is cited as the
  authoritative national forecaster and as the body whose warnings ours must never
  contradict or replace. Treated as reference, not as a compute source.

---

## 2. Terrain, satellite and land cover

### 2.1 Microsoft Planetary Computer STAC — `verified` — **primary geospatial source**

- **Endpoint:** `https://planetarycomputer.microsoft.com/api/stac/v1`
- **Probe result:** HTTP 200, 136 collections listed. Every collection we depend on was
  confirmed present by name:

| Collection | Confirmed | Use |
|---|---|---|
| `cop-dem-glo-30` | yes | 30 m Copernicus DEM, the basis of all terrain derivatives |
| `cop-dem-glo-90` | yes | coarse fallback |
| `nasadem` | yes | secondary DEM cross-check |
| `sentinel-1-rtc` | yes | backscatter change detection for the deformation layer |
| `sentinel-2-l2a` | yes | NDVI time series, vegetation loss, post-event scar detection |
| `esa-worldcover` | yes | 10 m land cover |
| `io-lulc-annual-v02` | yes | alternative annual land use and land cover |

- **Key:** anonymous access works for search; a free subscription key raises rate limits.
  Signed asset URLs are obtained through the Planetary Computer SAS endpoint.
- **Throughput problem, measured 2026-09-09.** Search and signing work reliably, but the
  Azure blob host that serves the DEM assets delivered only 0.10 MB/s from this machine
  and then stopped entirely at exactly 5 MiB, twice. A single 46 MB tile never completed.
  The Phase 1 pipeline therefore falls back to AWS Terrain Tiles (§2.5) and records which
  source produced every run. This is a network-path problem rather than a fault in the
  dataset, and it should be re-tested from the deployment environment.
- **Cadence:** DEM once, then on demand. Sentinel-1 and Sentinel-2 daily.
- **Licence:** Copernicus data is free and open with attribution. ESA WorldCover is
  CC BY 4.0.

### 2.2 OpenTopography — `key-required`

- **Endpoint:** `https://portal.opentopography.org/API/globaldem`
- **Probe result:** HTTP 401. The endpoint is live but now requires a free API key.
- **Consequence:** Planetary Computer is the primary DEM path and OpenTopography is the
  secondary. Because the primary needs no key, the missing key is **not blocking**.
- **Setup:** register for a free OpenTopography key and set `OPENTOPOGRAPHY_API_KEY`.

### 2.4b GSI National Landslide Susceptibility Mapping (NLSM) — `reachable`, categorical only

- **What it is:** GSI's programme that has mapped roughly 4.3 lakh km2 across 179 districts
  in 19 states and union territories at 1:50,000 scale.
- **Verified 2026-09-09** by cross-checking press coverage of the programme (Business
  Standard, ETV Bharat) rather than by obtaining the underlying susceptibility rasters,
  which GSI has not published in an open, machine-readable form. See
  `api/app/api/v1/location.py` for the 19-state list, grouped into the four hill belts GSI
  itself uses: north-western Himalaya, sub-Himalayan North East, Western Ghats, Eastern
  Ghats.
- **Used for:** the all-India `/check` location tool. For a state on this list, the tool
  states that GSI has mapped it and names the belt. **This is a categorical fact about
  where GSI has published mapping, never a computed risk score**, and the interface says
  so explicitly. Real, computed risk is shown only inside the Noney and Tupul pilot area,
  where the 14,714-unit physics model actually applies.

### 2.4c Material class, terrain-derived — `derived, not acquired`

- **What it is:** a per-slope-unit regolith class assigned from landform position by
  `ingest/ingest/terrain/materials.py`. Four classes: engineered cut (within 60 m of a
  road and steeper than 15 degrees), alluvium (within 150 m of a channel and flatter than
  10 degrees), colluvium (topographic position index at or below -0.05 and not steeper
  than 30 degrees), and residual soil as the default.
- **Measured distribution over the Noney run**, 14,714 units: residual soil 8,816
  (59.9%), colluvium 2,914 (19.8%), engineered cut 2,560 (17.4%), alluvium 424 (2.9%).
- **What it is NOT:** a geological map. Terrain resolves where material accumulates and
  where it weathers in place. It does not resolve bedrock type, and gneiss, sandstone and
  shale have materially different friction angles. The bedrock class remains a choice a
  geologist makes, or a real lithological polygon set supplies.
- **Upgrade path:** join a lithology polygon set here and let it take priority for the
  bedrock-derived classes. Nothing downstream changes, because the API already reads a
  per-unit `material_class` column. GSI has not published the NLSM susceptibility layers
  in an open machine-readable form as of the 2026-09-09 probe.

### 2.5 AWS Terrain Tiles — `verified` — **elevation fallback, and what Phase 1 actually used**

- **Endpoint:** `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`
- **Key:** none. **Probe result:** HTTP 200, tiles of roughly 50 KB returned promptly.
  240 tiles for the Noney pilot completed in about six minutes on the same connection
  where one Copernicus tile could not finish at all.
- **Encoding:** terrarium, where `elevation_m = (R * 256 + G + B / 256) - 32768`.
- **Underlying data:** a blend of SRTM, GMTED and other public sources, not Copernicus.
  At zoom 13 and the latitude of the region the native ground sample is about 17 m, which
  is resampled to the requested pipeline resolution.
- **Honest statement of the trade:** this is a different dataset from Copernicus GLO-30,
  assembled from a global tile pyramid rather than a single authoritative product. Every
  run manifest records `dem_source`, and no output may be described as Copernicus-derived
  unless the manifest says so.
- **Also used by** the landing page hero terrain.

### 2.3 ESA WorldCover via Terrascope — `unverified`

- `https://services.terrascope.be/stac/` did not answer from this machine.
- WorldCover is consumed through Planetary Computer instead, which is verified. This entry
  exists so nobody re-adds the Terrascope path assuming it works.

### 2.4 Bhuvan, NRSC/ISRO — `reachable`, display layer only

- **Host:** `https://bhuvan.nrsc.gov.in` answered HTTP 200.
- **Use:** WMS reference basemaps and thematic layers, shown as a selectable basemap. It
  gives the product an Indian geospatial provenance a judge will recognise.
- **Explicitly not** a compute source. The specific WMS layer names must be confirmed
  against the live GetCapabilities document in Phase 2 before any are hard-coded.

---

## 3. Landslide inventory and susceptibility baseline

### 3.1 GSI Bhusanket and the National Landslide Susceptibility Map — `reachable`

- **Host:** `https://bhusanket.gsi.gov.in` answered HTTP 200.
- **Role:** the Geological Survey of India is the authoritative national body for landslide
  susceptibility and inventory. Our susceptibility output is positioned as **compared
  against** the GSI baseline, never as replacing it.
- **Related portal:** Bhukosh, the GSI data portal that hosts the 1:50,000 National
  Landslide Susceptibility Map, did not answer when probed on 2026-09-08. Treat it as
  `unverified` and try it by hand before relying on it.
- **Status of the data itself:** we have not yet obtained machine-readable inventory
  polygons. Until we do, the inventory used for training is generated by the physics model
  over the synthetic history and **must be labelled provisional in the UI, in the model
  card and in the pitch**. See open question Q5 in `PROJECT_CONTEXT.md`.
- **How we differ from GSI:** GSI publishes a static, macro-scale susceptibility baseline.
  ShailSuraksha adds the time dimension, a slope-unit scale, live rainfall and soil
  moisture, per-prediction explanation, and an accountable last-mile alert path with
  acknowledgement. That contrast is the answer to judge question four.

### 3.2 NASA LHASA — `verified` — reference model, not a data source

- **Repository:** `https://github.com/nasa/lhasa` answered HTTP 200.
- **What it is:** the open-source Landslide Hazard Assessment for Situational Awareness
  model, NASA's global landslide nowcast.
- **How we use it:** as a **benchmark and a citation**, not as an input. Reading it before
  building our own model is due diligence, and being able to say how our approach differs
  from the published state of the art is a strong answer in questioning. LHASA is global
  and coarse; we are regional and slope-scale, add the physics layer, and add the
  last-mile alerting that a nowcast model does not attempt.
- **Licence:** NASA open source. Check the repository licence before reusing any code.

### 3.3 NASA Global Landslide Catalog / COOLR — `unverified`

- The dataset export page at `catalog.data.gov` answered HTTP 200, but the direct API path
  we tried at `data.nasa.gov` returned HTTP 404, and the NASA NCCS ArcGIS host did not
  answer.
- **Consequence:** no COOLR-derived event is cited as fact until the file is actually
  downloaded and inspected. The provider is registered with status `unverified` and routes
  to the synthetic inventory.
- **Action:** resolve the current download URL in Phase 2 by hand before wiring it.

### 3.4 Documented reference events

These are used in product copy and the pitch narrative, and are recorded here so their
provenance is visible rather than implied:

| Event | Date | Reported toll | Note |
|---|---|---|---|
| Tupul / Noney, Manipur | June 2022 | approximately 55–61 killed | Railway construction cut slope; buried a Territorial Army camp |
| Aizawl, Mizoram | May 2024 | 20+ killed in a single day | During Cyclone Remal remnant rainfall |
| Assam, Arunachal, Manipur | mid-2025 | 20+ deaths across states within days | Simultaneous floods and landslides |

Tolls from contemporaneous reporting vary by a few counts between sources. Ranges are
shown as ranges, never rounded into a single false-precision figure.

---

## 4. Administrative boundaries and infrastructure

### 4.1 datameet/maps — `verified` — **primary boundary source**

- **URL probed:** `https://raw.githubusercontent.com/datameet/maps/.../india-composite.geojson`
  answered HTTP 200.
- **Use:** state and district boundaries for the eight NER states.
- **File actually used:** `Districts/Census_2011/2011_Dist.shp` with its `.shx`, `.dbf`
  and `.prj` companions. 641 districts nationally, EPSG:4326, Census 2011 vintage.
- **Loaded for the region:** 8 states, 86 districts, 260,629 km2 total. That is within
  half a percent of the roughly 262,000 km2 usually published for the eight states, which
  is a useful independent check that nothing was dropped.
- **A trap worth knowing about.** The source spells Arunachal Pradesh as **"Arunanchal
  Pradesh"**. Filtering on state names silently drops the largest state in the region, and
  the failure is invisible: the load succeeds, the map renders, and one state is simply
  missing. The loader therefore matches on Census state codes 11 to 18, which are stable,
  and supplies canonical names itself.
- **Vintage caveat:** Census 2011 predates many district reorganisations. Several
  districts created since are absent, and district counts will not match current
  administrative lists. Newer boundaries are needed before operational use.
- **Licence:** the repository publishes community-maintained open data. The exact licence
  must be confirmed per file before any commercial or redistributed use, and the source
  must be attributed in the UI.
- **Caveat that must reach the UI:** community boundary data can disagree with official
  Survey of India boundaries, particularly along the international and interstate borders
  of the North East. Boundaries are shown as **indicative for operational use, not as an
  authoritative depiction of any border**, and that disclaimer ships in the map legend.

### 4.2 GADM 4.1 — `verified`, fallback only

- `https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IND_2.json.zip` answered HTTP 200.
- **Licence restriction:** GADM is free for academic and other non-commercial use, and
  redistribution is restricted. For that reason it is the fallback, not the primary, and
  its geometry must not be re-published from our API.

### 4.3 Block and village boundaries — `unverified`

No open, verified source for NER block and village polygons has been confirmed. Phase 1
will either locate one or generate simplified but geographically correct polygons that are
**marked provisional in the database, in the API response and in the UI**. They will never
be presented as official geometry.

### 4.4 OpenStreetMap via Overpass — `verified`

- `https://overpass-api.de/api/status` answered HTTP 200.
- **Use:** the road graph for the connectivity dashboard, plus hospitals, schools,
  buildings and helipads. Consumed with osmnx and networkx.
- **Licence:** ODbL. Attribution is mandatory and share-alike applies to derived
  geometric databases, which matters if road-graph derivatives are ever published.
- **Etiquette:** Overpass is a shared community resource. Extracts are cached to disk and
  fetched at low frequency, never per request.
- **Query shape matters, measured 2026-09-09.** Two forms returned HTTP 504 from every
  mirror even on a 0.6 degree box: twelve node and way statements in one query, and a
  single `nwr` statement using a regular-expression alternation. Splitting the work into
  one exact-match query per category answers in well under a second. Regular expressions
  force a scan instead of a tag-index lookup, and `nwr` pulls in relations as well.
- **Pilot result:** 741 road segments totalling 1,689 km, and 22 critical facilities, for
  the Noney area. The helipad and fire-station categories failed on the day and are
  recorded as gaps rather than as zero.

---

## 5. Basemap and tiles

| Source | Status | Note |
|---|---|---|
| CARTO Dark Matter GL style | `verified`, HTTP 200 | Free dark basemap style; CARTO and OSM attribution required |
| MapLibre demotiles | `verified`, HTTP 200 | Development fallback only, very low detail |
| Protomaps hosted API | `key-required`, HTTP 403 | Not needed; we build and self-host our own PMTiles in Phase 1 |

Our own vector layers, meaning admin boundaries, slope units and roads, are built into
PMTiles with tippecanoe and served from the API with ETag caching. Self-hosting removes
the demo's dependence on a third-party tile service.

---

## 6. Synthetic engine — the labelled fallback

The synthetic generator is not a shortcut. It is the guarantee that the demo works when a
conference network fails, and it produces the physics-consistent training set.

- **Determinism:** seeded. The same seed reproduces the same five years, hour for hour.
- **Rainfall:** monsoon-seasonal Markov wet/dry chain with Gamma-distributed wet-spell
  intensity, an orographic multiplier as a function of elevation and windward aspect, and
  injectable cyclone-remnant events matched to the reference events above.
- **Soil moisture:** a two-layer bucket model with infiltration, drainage and
  evapotranspiration, so moisture lags rainfall the way it does in the field.
- **Inventory:** failures are sampled probabilistically from the physics model run over
  that history, which makes the labels internally consistent with the FoS layer.
- **Sensors:** 60 or more virtual stations, meaning rain gauges, tiltmeters, piezometers,
  soil-moisture probes and extensometers, publishing over MQTT with realistic noise,
  drift, battery decay and roughly two percent dropout.
- **Labelling:** every record carries `source = synthetic`. The API returns
  `status: SIMULATED`, and the UI renders a blue chip. There is no code path that strips
  this label.

---

## 7. Provider registry summary

| Provider | Status | Key | Cadence | Fallback |
|---|---|---|---|---|
| `open_meteo_forecast` | verified | none | 30 min | synthetic |
| `open_meteo_archive` | verified | none | on demand, 24 h cache | synthetic |
| `nasa_power` | verified | none | daily | synthetic |
| `gpm_imerg` | key-required | Earthdata | 30 min when enabled | disabled, layer hidden |
| `planetary_computer_dem` | verified | optional | once, then on demand | bundled coarse DEM |
| `sentinel1_rtc` | verified | optional | daily | deformation layer degrades to sensors only |
| `sentinel2_l2a` | verified | optional | daily | last good NDVI, marked cached |
| `esa_worldcover` | verified | optional | static | bundled raster |
| `opentopography` | key-required | free key | on demand | Planetary Computer |
| `osm_overpass` | verified | none | weekly | cached extract |
| `bhuvan_wms` | reachable | none | display only | basemap switch |
| `gsi_bhusanket` | reachable | none | manual | provisional inventory, labelled |
| `nasa_coolr` | unverified | none | manual | synthetic inventory, labelled |
| `nasa_lhasa` | verified | none | reference only | n/a, benchmark not an input |
| `gsi_bhukosh` | unverified | portal | manual | provisional inventory, labelled |
| `datameet_boundaries` | verified | none | static | GADM, then provisional geometry |
| `synthetic` | always available | none | on demand | n/a, this is the floor |

---

## 8. Refresh procedure

`make probe-sources` re-runs the exact HTTP probes behind this document and prints a
status table. Run it before every demo and before every judging session, and update the
probe date at the top of this file. A source that has silently changed is worse than a
source that is known to be down.
