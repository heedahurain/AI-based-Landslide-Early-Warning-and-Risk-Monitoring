# Model Card — ShailSuraksha Landslide Risk Engine

**Version:** 0.1.0 (physics layer measured; no learned model trained yet)
**Last updated:** 2026-09-09
**Owners:** ShailSuraksha team, Smart India Hackathon 2026, problem statement SIH26001

> **Every number in this card came from a run that was actually executed**, and each is
> dated. The physics layer is measured and its results are in §4.3. The machine learning
> and deformation tables are still empty, because nothing has been trained: those stay
> empty until an evaluation produces them. Nothing here is aspirational.

---

## 1. The statement that governs every other statement

**ShailSuraksha is a decision-support tool. It is not a substitute for official warnings
from the Geological Survey of India (GSI) or the India Meteorological Department (IMD),
and it does not carry statutory authority.**

Where our output disagrees with a GSI or IMD warning, the official warning takes
precedence. Nothing in this system authorises, replaces or overrides a statutory
evacuation order. The intended effect is to help an officer decide **where to look first
and whom to call first**, faster than they otherwise could, with the reasoning visible.

Landslide occurrence is governed by subsurface conditions that cannot be observed at the
scale we model. A low predicted probability is **never** evidence that a slope is safe.

---

## 2. Intended use

### Intended users

| User | Use |
|---|---|
| District Disaster Management Authority officers | Prioritising monitoring, pre-positioning resources, issuing and acknowledging alerts |
| Block officers and village heads | Receiving locality-level warnings and confirming ground truth |
| Geologists and analysts | Auditing predictions, tuning geotechnical parameters, validating events |
| Response teams | Working a prioritised task queue during an event |
| Citizens | Checking the current level for their village and reporting observed hazards |

### Intended use cases

- Monsoon-season monitoring of relative landslide hazard across the eight NER states.
- Ranking slope units and road segments so limited inspection capacity goes to the right
  places first.
- Triggering a graded, acknowledged alert workflow with an audit trail.
- Scenario exploration, meaning "what if another 100 mm falls in 24 hours".

### Out-of-scope uses

- **Site-specific engineering design or slope stabilisation design.** The parameters are
  regional class averages, not site investigation data.
- **Legal, insurance or land-title determinations**, or any decision about individual
  property rights.
- **Predicting the exact time, exact location or exact size of a specific failure.** The
  inverse-velocity module estimates a failure *window* for an already-accelerating slope,
  with a quality gate, and nothing more.
- **Use outside the North Eastern Region** without refitting. Thresholds and parameters
  are regional.
- **Unattended automated evacuation.** A human with authority issues every ORANGE and RED
  alert.

---

## 3. Model architecture

Four layers, deliberately not one black box. Each is separately inspectable in the UI, and
fusion always returns the components alongside the combined score.

### 3.1 Physics layer

Infinite-slope stability with transient pore pressure:

```
FoS = [c' + (γ·z·cos²β − u)·tan φ'] / (γ·z·sin β·cos β)
```

`c'` effective cohesion, `φ'` effective friction angle, `γ` unit weight, `z` soil depth,
`β` slope angle, `u` pore water pressure from a simplified Iverson / Green–Ampt transient
infiltration response driven by modelled soil moisture. FoS below 1.0 indicates failure,
1.0 to 1.3 is marginal.

**This layer has no training data and cannot overfit.** It is the defensible floor of the
system. Its weakness is parameter uncertainty, addressed in §6.

### 3.2 Empirical layer

Regional rainfall Intensity–Duration thresholds of the form `I = α·D^−β`, fitted per state
from the event inventory with bootstrap confidence bands, plus the Antecedent
Precipitation Index (k = 0.85), 3, 7, 15 and 30-day cumulative rainfall, and a tank-model
Soil Water Index. Output is an exceedance ratio against the fitted threshold.

### 3.3 Machine learning layer

- **Susceptibility (static):** an XGBoost and LightGBM ensemble over terrain, lithology,
  land cover and distance features, producing a per-slope-unit susceptibility.
- **Temporal hazard (dynamic):** a PyTorch Temporal Convolutional Network with dilated
  causal convolutions over 30 days of rainfall, soil moisture, sensor deltas and the
  physics FoS series, predicting failure probability at 6, 24 and 72 hours. Focal loss for
  class imbalance, isotonic calibration on a held-out set, MC-dropout over 30 passes for
  the uncertainty interval.

### 3.4 Deformation layer

Sentinel-1 backscatter and coherence change over slope units, plus the inverse-velocity
(Fukuzono) method on tiltmeter and extensometer series: fit 1/v against time and
extrapolate to zero to obtain a failure window with a confidence interval. An R² quality
gate suppresses fits that are too noisy to be meaningful, because a confident-looking
failure time from noise would be actively dangerous.

### 3.5 Fusion

A calibrated logistic blend of the physics FoS, the empirical exceedance ratio and the ML
probability. The three components are always returned separately, and the UI shows them
separately. There is no code path that hides the fusion.

---

## 4. Evaluation methodology

### 4.1 Spatial cross-validation, and why random k-fold is wrong here

Evaluation uses **leave-one-district-out** cross-validation.

Landslide inventories are spatially autocorrelated. Slope units near each other share
terrain, lithology, land cover and the same rainfall field. Under random k-fold, a
training-fold unit and a test-fold unit can be neighbours on the same hillside, so the
model is effectively tested on data it has already seen. This inflates AUC substantially
and produces a model that scores well and generalises badly to a district it has never
seen, which is exactly the operational case.

Leave-one-district-out holds out an entire district, so the reported score answers the
question that actually matters: **how well does this work in a district we did not train
on?** Any comparison against a published random k-fold AUC is therefore not
like-for-like, and we say so rather than claiming a higher number.

### 4.2 Metrics to be reported

ROC-AUC, PR-AUC (which matters more than ROC under this class imbalance), Brier score, a
calibration curve, and permutation importance. For the temporal model, metrics are
reported per horizon, and the calibration curve is reported before and after isotonic
regression.

### 4.3 Results

**Not yet measured.** Phase 3 populates the tables below from an evaluation run and
records the MLflow run identifier for each row.

#### Susceptibility model, leave-one-district-out

| District held out | ROC-AUC | PR-AUC | Brier | n units | n positives |
|---|---|---|---|---|---|
| *pending Phase 3* | — | — | — | — | — |

#### Temporal hazard model, by horizon

| Horizon | ROC-AUC | PR-AUC | Brier | Calibration slope | 90% interval coverage |
|---|---|---|---|---|---|
| 6 h | — | — | — | — | — |
| 24 h | — | — | — | — | — |
| 72 h | — | — | — | — | — |

#### Physics layer, known-answer tests — **measured 2026-09-09**

27 tests in `ml/tests/test_slope_stability.py`, all passing. Expected values are
derived by hand from the closed form, not captured from a previous run.

| Case | Expected | Result |
|---|---|---|
| Dry cohesionless, six slope and friction pairs | `tan(phi') / tan(beta)` | matches to 1e-9 |
| Fully saturated, three parameter sets | `(gamma - gamma_w) / gamma * tan(phi') / tan(beta)` | matches to 1e-9 |
| Worked case, beta 30, z 1.5, c' 5, phi' 32, gamma 18.5, m 0.5 | 1.2118 | 1.2118, classed marginal |
| Saturation ratio for gamma 18.5 | 0.470 | 0.470, so wetting halves the margin |
| Flat ground | reported stable, never infinite | ceiling of 10.0 |
| Effective stress under extreme wetness | never negative | clamped at zero |

#### Physics layer applied to the Noney pilot — **measured 2026-09-09**

14,714 slope units, residual soil over gneiss, soil depth from the terrain proxy.

| Wetness | Median FoS | Unstable | Marginal |
|---|---|---|---|
| 0.00 dry | 2.114 | 0 | 0 |
| 0.50 wet | 1.701 | 0 | 0 |
| 0.75 very wet | 1.494 | 0 | 2,769 |
| 1.00 saturated | 1.287 | 0 | 7,622 |

**The important result is not any of those numbers.** Holding slope and depth
fixed and running saturated, the six material classes disagree completely:

| Material class | c' kPa | Median FoS | Unstable units |
|---|---|---|---|
| Weathered shale | 12.0 | 1.834 | 0 |
| Weathered sandstone | 8.0 | 1.681 | 0 |
| Alluvium | 6.0 | 1.291 | 0 |
| Residual soil over gneiss | 5.0 | 1.287 | 0 |
| Road and railway cut slope | 3.0 | 0.983 | 7,776 |
| Colluvium | 2.0 | 0.884 | 9,718 |

Sweeping soil depth instead, holding material fixed at residual soil and
saturated:

| Uniform soil depth | Median FoS | Unstable units |
|---|---|---|
| 0.5 m | 2.306 | 0 |
| 1.5 m | 1.259 | 2,772 |
| 3.0 m | 0.998 | 7,390 |
| 5.0 m | 0.893 | 9,222 |

So on this terrain **the material class and the regolith thickness decide the
answer, and we have measured neither.** Slope angle, the input we do measure
well, matters less than either. That is why the interface exposes both as
controls and reports a range rather than asserting a single factor of safety,
and it is the honest answer to "how many slopes are unstable": it depends
entirely on what they are made of.

---

## 5. Training data

### 5.1 What the model will be trained on

Terrain derivatives from the Copernicus DEM GLO-30, land cover from ESA WorldCover,
rainfall and soil moisture from Open-Meteo forecast and ERA5 archive, cross-checked
against NASA POWER, sensor series from the field or simulated fleet, and a labelled
landslide inventory.

### 5.2 The inventory problem, stated plainly

**At Phase 0 we do not hold a verified, machine-readable landslide inventory for the
region.** The GSI Bhusanket portal is reachable but we have not obtained inventory
polygons from it, and the NASA COOLR endpoint we tried did not resolve. See
`docs/DATA_SOURCES.md` §3.

Until a real inventory is obtained, the training labels are **generated** by running the
physics model over the synthetic rainfall history and sampling failures
probabilistically. The consequences must be stated everywhere this model is presented:

1. The labels are internally consistent with the physics layer **by construction**. A
   model trained on them will appear to agree with the physics layer, and that agreement
   is not independent evidence that either is correct.
2. Metrics from this data measure whether the ML layer **learned the generating process**,
   not whether it predicts real landslides.
3. Any such metric must be reported as **"synthetic-inventory validation"**, never as
   real-world skill. Presenting it as real-world accuracy would be dishonest, and a
   geologist judge would be right to reject the whole system for it.
4. The UI labels the inventory as provisional wherever it appears.

Replacing the generated inventory with a real one, then re-reporting every metric, is the
single highest-value follow-up for this project. It is tracked as open question Q5.

### 5.3 Citizen-report vision model

An EfficientNet or MobileNetV3 fine-tuned to classify tension crack, slope bulge, debris
flow, road damage, retaining-wall failure, water seepage, tilted tree or pole, and no
hazard. Training data, class counts and per-class metrics are recorded in Phase 3. Its
output is **advisory to a human moderator** and never auto-issues an alert on its own.

---

## 6. Limitations

### 6.1 Physical and data limitations

- **Parameter uncertainty dominates the FoS.** Effective cohesion and friction angle are
  regional class averages, not site investigations. FoS is therefore a **relative
  indicator across slope units**, not an absolute engineering safety factor for any one
  slope. The UI shows sensitivity ranges, not false precision.
- **Soil depth is estimated,** typically from a terrain proxy. It appears in the FoS
  numerator and denominator and is a leading source of error.
- **No subsurface data.** Groundwater tables, joint sets, bedding orientation, relict
  shear surfaces and buried structures are invisible to the model and can dominate real
  failures.
- **Anthropogenic triggers are only weakly represented.** Active road cutting, quarrying,
  unregulated construction and drainage interference were the proximate causes of several
  of the reference events, including Tupul and Aizawl. Proxies such as distance to road
  capture only part of this.
- **Seismic triggering is not modelled.** The NER is highly seismically active. This
  system models rainfall-triggered landslides only.
- **DEM resolution.** At 30 m, small but lethal cut-slope failures fall below the
  resolution of the terrain derivatives.
- **Forecast error propagates.** Rainfall forecast error passes into the hazard estimate,
  which is why every prediction carries an uncertainty band.

### 6.2 Modelling limitations

- Slope-unit delineation is a modelling choice. Different drainage thresholds give
  different units and slightly different scores.
- Calibration is only as good as the inventory. With a generated inventory, "70% means
  70%" holds with respect to the generating process, not with respect to reality.
- The temporal model has not been validated across a full monsoon cycle of real events.
- The deformation layer is **change detection, InSAR-ready**, not full InSAR
  interferometry. It is labelled that way in the UI, and no InSAR claim is made.

---

## 7. Failure modes and what happens

| Failure mode | Consequence | Mitigation in the system |
|---|---|---|
| False negative, no warning before a real failure | The most serious possible outcome | Multi-layer fusion so no single layer can silently veto; physics layer runs even when ML is unavailable; citizen reports provide an independent human channel; low probability is never displayed as "safe" |
| False positive, warning with no failure | Alert fatigue, then ignored warnings | Hysteresis, minimum dwell time, confidence gating, geographic de-duplication, and a visible acknowledgement funnel that makes fatigue measurable |
| Provider outage during an event | Stale inputs presented as current | Redis cache with visible age, synthetic fallback, and a mandatory per-source status chip |
| Sensor drift or a stuck sensor | Corrupted features | Sensor health tracking, drift and dropout detection, and exclusion of unhealthy stations from inference |
| Model degradation over time | Slow, invisible loss of skill | MLflow versioning, monitoring of the score distribution, and a human-in-the-loop retraining queue with the last retraining date shown on the model status page |
| Miscalibration | A number that does not mean what it says | Isotonic calibration and a published calibration curve |
| Overconfidence from a noisy inverse-velocity fit | A specific, wrong failure time | R² quality gate that suppresses the estimate entirely rather than showing a weak one |
| Boundary or geometry error | Wrong village alerted | Provisional geometry labelled as such; alerts carry both polygon and geocode |

---

## 8. Ethical considerations

- **Equity of reach.** The people most exposed often have the worst connectivity and do
  not read English or Hindi. Ten languages, Lite mode, offline district packs, SMS and IVR
  are ethical requirements, not features.
- **Warning without capacity to act.** A warning to someone with nowhere to go is of
  limited value. Alerts always carry the nearest shelter and a route, and the response
  dashboard exists so warnings connect to resources.
- **Privacy of reporters.** Citizen reports allow anonymity. Reporter identity is stored
  as a hash, EXIF is stripped from any publicly served copy, and precise location is
  shown to moderators, not to the public feed.
- **Reporter trust scores** could entrench bias against new or infrequent reporters. The
  score weights history but must never be the sole reason to reject a report, and every
  rejection requires a recorded reason.
- **Automation bias.** Officers may over-trust a number on a screen. This is why the
  explanation panel, the uncertainty band and the component breakdown are mandatory rather
  than optional.
- **Land and livelihood consequences.** Persistent high-risk labelling can affect land
  value and settlement decisions. Outputs are hazard indications, not land-use rulings,
  and are labelled that way.
- **Accountability.** Every alert, suppression, override and acknowledgement is audited.
  "Why was I not warned" must be answerable after the fact.

---

## 9. Maintenance

- **Retraining trigger:** new verified events entering the inventory, or a drift in the
  score distribution.
- **Human-in-the-loop:** moderator-verified citizen reports feed the retraining queue. Its
  size and the last retraining date are shown on the model status page.
- **Versioning:** every model is registered in MLflow. Every `RiskAssessment` row stores
  the `model_version` that produced it, so a past decision can always be reproduced.
- **Review:** this card is updated in the same change that alters a model. A model change
  without a card change should fail review.

---

## 10. How to cite the limitations honestly in a presentation

If asked "how accurate is it", the correct answer at Phase 0 is: *"No model is trained
yet. When it is, we will report leave-one-district-out AUC, PR-AUC and a calibration
curve, and because our inventory is currently generated rather than observed, we will
report it as synthetic-inventory validation until we obtain real GSI inventory data."*

That answer is stronger than a confident number, because the confident number would not
survive the follow-up question.
