# Pitch, coverage and defence

Everything a presenter needs on the day. Judges decide in the first ninety seconds, so
sequence matters more than feature count.

**Idea submission deadline: 30 September 2026.** The submission is judged on the
write-up, not the code. `PROJECT_CONTEXT.md` §1 maps each write-up section to its source.

---

## 1. Problem statement coverage matrix

Every requirement in SIH26001 must be pointable-at during the demo. Print this.

| PS requirement | Where it lives | Phase |
|---|---|---|
| Rainfall data | Open-Meteo, NASA POWER and GPM IMERG providers | 2 |
| Soil moisture | Open-Meteo soil-moisture stack, bucket model, field probes | 2 |
| Satellite data | Sentinel-1 RTC, Sentinel-2 NDVI, IMERG, Bhuvan layers | 2, 3 |
| Terrain data | Copernicus and SRTM DEM giving slope, aspect, curvature, TWI, TPI | 1 |
| Historical data | NASA Global Landslide Catalog, GSI inventory, ERA5 archive | 2, 3 |
| AI and ML risk prediction | Physics FoS, I–D thresholds, XGBoost and LightGBM, TCN, fused | 3 |
| Real-time alerts to district admin | CAP v1.2, escalation matrix, acknowledgement loop | 4, 10 |
| Real-time alerts to communities | SMS, WhatsApp, IVR, push and siren in ten languages | 4, 9 |
| GIS mapping | MapLibre and deck.gl 3D terrain command centre | 6 |
| Citizen geo-tagged reporting | Offline PWA reporting, on-device ONNX classifier, EXIF check | 8, 9 |
| Risk severity dashboard | Dashboard 1 | 6 |
| Road connectivity dashboard | Dashboard 2, graph-cut isolation analysis | 7 |
| Weather-linked forecast dashboard | Dashboard 3, I–D chart and what-if simulator | 7 |
| Response prioritisation dashboard | Dashboard 4, transparent index, isochrones, Kanban | 8 |
| Multilingual notifications | next-intl, ten languages, per-channel templates | 9 |
| Offline and low-network support | PWA, district pack, Lite mode, SMS grammar | 9 |

---

## 2. The four-minute demo script

### 0:00–0:25 · The stake

Landing page. "In June 2022 a slope above a railway construction site at Tupul, Manipur
failed and buried a Territorial Army camp. Around sixty people. The rainfall data
existed. Nobody had turned it into a warning for *that* slope, in *that* village, in
*that* language." Scroll once through the problem section.

### 0:25–1:10 · The command centre

Launch it. Let the 3D terrain load with the extruded risk prisms. Rotate once. Say what
the judge is looking at: eight states, roughly 14,000 slope units, live rainfall from
Open-Meteo, terrain from the Copernicus DEM, updating every thirty minutes. Point at the
data-status chips. "Green means live, blue means simulated. We never dress up simulated
data as real."

### 1:10–1:55 · Why should I trust it

Click a RED slope unit and open the explanation drawer. "Seventy-two-hour rainfall of
218 mm against a regional threshold of 145 mm is the biggest contributor. Factor of
safety 0.87, below one, computed from slope angle, soil depth, cohesion and pore
pressure. And here is the nearest historical analogue." This is the moment that separates
the project from a black-box classifier.

### 1:55–2:35 · The what-if

Drag the rainfall slider, or hit the Cyclone Remal remnant preset. Watch the surface
recompute. "Four hundred and twelve units cross ORANGE. Fourteen villages become
isolated." Switch to the connectivity dashboard and let the graph-cut animate.

### 2:35–3:15 · The last mile

Fire an alert and show the arc animation out to the villages. Then pick up a phone, open
the citizen portal in Mizo, show the status card, turn on airplane mode, file a photo
report offline, turn the network back on and watch it sync. "Two bars of signal, or none
at all."

### 3:15–3:45 · Government-ready

Open the CAP XML. "Every alert is Common Alerting Protocol v1.2, the same standard the
NDMA SACHET pipeline consumes. This plugs into the existing national alerting stack. It
does not compete with it." Show the acknowledgement funnel and the audit log.

### 3:45–4:00 · The honest close

"GSI forecasts at district scale. We forecast at slope scale, explain every number, and
get it to the person standing on the slope. What is simulated and what is live is
documented in LIMITATIONS.md, along with what we would need for real deployment."

---

## 3. What actually separates this from the other teams

Most teams will build a map, a rainfall chart, a random-forest score and a login. These
seven are the separation.

1. **The factor-of-safety calculation.** A geologist judge can check the physics. Almost
   nobody does physics. Showing the formula with real numbers substituted converts
   scepticism into respect in about ten seconds.
2. **Leave-one-district-out spatial cross-validation.** Saying "we did not use random
   k-fold because it leaks spatially and inflates AUC" tells a technical judge more than
   any slide can.
3. **CAP v1.2 compliance.** It reframes the project from a student app into a system that
   integrates with what the government already runs.
4. **The what-if simulator.** The only part of the demo a judge remembers physically,
   because they touched it.
5. **The connectivity graph-cut.** "Which villages get cut off" is a question officials
   actually ask, and an animation answering it is unforgettable.
6. **Alert fatigue controls.** Hysteresis and dwell times prove the system was thought
   about in month three, not on demo day. It is an operational-maturity signal.
7. **LIMITATIONS.md and honest data chips.** Judges find the gaps anyway. Naming them
   first makes everything else more believable.

Inverse-velocity failure forecasting is the bonus round. If it works, lead with it in
questions, because it is genuinely graduate-level.

---

## 4. Judge question-and-answer defence pack

Rehearse these. The answers matter more than the demo.

### "GSI already runs Bhusanket and a National Landslide Forecasting Centre. Why you?"

GSI forecasts are district-scale and advisory. We operate at slope-unit scale, roughly
14,000 units against about 80 districts. We add road-connectivity and response
prioritisation that GSI does not provide, close the loop with acknowledgement and audit,
and emit CAP so we complement rather than replace the official chain. We are a
district-level decision-support layer sitting under the national forecast.

### "Where does your training data come from? There is not much labelled landslide data."

Correct, and that is the central constraint. It is stated in the model card. We use the
NASA Global Landslide Catalog and the GSI inventory where available, augmented by
physics-generated labels from the factor-of-safety model. That is precisely why the
architecture is hybrid: the physics layer works with no training data at all, and the ML
layer improves as real events accumulate through the citizen-report human-in-the-loop
pipeline.

### "What is your accuracy?"

Quote the measured numbers from the evaluation, with the spatial cross-validation caveat
and the Brier score beside the AUC. Then add: "our calibration curve is in the model
card, because for a warning system a well-calibrated 60% is worth more than an
overconfident 90%."

**Never quote a number that was not measured.** At Phase 0 the honest answer is that no
model is trained yet, and the model card's metric tables are deliberately empty.

### "What happens when there is no network, which is most of Arunachal?"

Show it rather than answer it. Airplane mode, district pack, offline report, sync. Then
mention the two-way SMS grammar and the documented Cell Broadcast path.

### "How do you avoid crying wolf?"

Hysteresis with separate up and down thresholds, a minimum dwell time per level,
confidence gating so low-confidence predictions cannot trigger evacuation tiers,
geographic de-duplication, and an operator override that requires written justification
into the audit log. Plus the acknowledgement funnel, so we can measure whether alerts are
actually being acted on.

### "What would it take to actually deploy this?"

Formal data-sharing agreements with IMD and GSI. A field sensor network, for which the
MQTT ingestion path is already specified. Geotechnical parameters validated per lithology
by state geologists. SDMA sign-off on the escalation matrix. Native-speaker review of
every alert template, tracked in `docs/TRANSLATIONS.md`.

---

## 5. Two rules for demo day

1. **Never let the demo depend on a source that needs a login you might not have on the
   day.** Run `python scripts/probe_sources.py` before every session and pre-warm the
   Redis cache.
2. **Never let the interface print a number the pipeline did not compute.**
