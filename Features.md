# AI-Assisted Satellite Oil-Spill Detection & Investigation System

> **SIH Project — Final Feature Specification**
>
> **Core positioning:** A satellite-first AI-assisted system for detecting oil spills, reconstructing their evolution, estimating probable source regions, correlating vessel activity, and presenting evidence-backed candidate vessels for human investigation.
>
> **Important:** The system is **not an automated enforcement or vessel-accusation system**. It provides investigation support, evidence, candidate ranking, and uncertainty information.

---

# 1. System Overview

The proposed system follows this investigation pipeline:

```text
Satellite Imagery
       ↓
Oil-Spill Detection
       ↓
Look-Alike Rejection
       ↓
Spill Segmentation & Quantification
       ↓
Temporal Change Analysis
       ↓
Spill Evolution Reconstruction
       ↓
Wind + Ocean Current Data
       ↓
Drift / Backtracking
       ↓
Probable Source Region
       ↓
AIS Vessel Correlation
       ↓
Vessel Behaviour & Consistency Analysis
       ↓
Multi-Source Evidence Fusion
       ↓
Candidate Vessel Ranking
       ↓
Uncertainty + Evidence Report
       ↓
Human Investigator
```

The key idea is:

> **Detect → Observe change → Reconstruct movement → Estimate source → Correlate vessels → Fuse evidence → Quantify uncertainty → Let an investigator decide.**

---

# 2. Feature Classification

| Classification        | Meaning                                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **BASELINE**          | A fundamental capability expected in a credible oil-spill detection/investigation system.                                                     |
| **EXISTING**          | A technology or research capability that already exists and is being adopted.                                                                 |
| **IMPROVEMENT**       | An existing capability used in a more useful, robust, or integrated manner.                                                                   |
| **PROPOSED / UNIQUE** | Our proposed system-level differentiation. The underlying algorithms may already exist; the novelty is primarily in the integration/workflow. |
| **FUTURE**            | Useful advanced functionality that is outside the core SIH MVP.                                                                               |

> **Important distinction:** “Unique” does **not** mean we invented a new neural network or a new physics model. Our strongest novelty claim is at the **system/workflow and evidence-fusion level**.

---

# 3. Final Feature List

## F01 — Multi-Source Satellite Data Ingestion

**Classification:** BASELINE / EXISTING
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Provide the satellite imagery required for oil-spill detection and monitoring.

### Primary data source

* Sentinel-1 SAR
* VV polarization initially
* VH polarization where useful

### Optional sources

* Sentinel-2 optical imagery when cloud-free
* Other compatible Earth-observation datasets

### Why we need it

Satellite imagery provides the initial observation of a possible oil slick.

SAR is particularly useful for maritime monitoring because it can operate without daylight and is less affected by cloud cover than optical imagery.

### Technology

* Sentinel-1 SAR
* Copernicus data ecosystem
* Python
* rasterio
* GDAL
* GeoPandas
* Shapely

### SIH implementation

We do **not** need to build a global production satellite ingestion infrastructure.

For the prototype, we can use a prepared set of Sentinel-1 scenes and demonstrate the processing pipeline.

### Limitations

Satellite observations are constrained by:

* revisit intervals
* acquisition geometry
* sea state
* wind conditions
* image quality
* cloud cover for optical imagery

Therefore, the system cannot guarantee continuous observation of every spill.

---

# F02 — AI Oil-Spill Detection & Segmentation

**Classification:** BASELINE / EXISTING
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Detect and segment regions in satellite imagery that are likely to correspond to oil spills.

### Recommended technology

Possible models:

* U-Net
* U-Net++
* DeepLabV3+
* SegFormer

### SIH recommendation

Use a **U-Net-family segmentation model** initially because it is practical to train, explain, and demonstrate within the hackathon timeframe.

### Output

The model produces:

* oil-spill segmentation mask
* spill polygon
* affected area
* model confidence

### Dataset

The Krestenitis dataset is particularly relevant because it uses Sentinel-1 SAR imagery and contains classes including:

* oil spill
* look-alike
* ship
* land
* sea

### Evaluation

Use:

* IoU
* Dice/F1
* Precision
* Recall
* False-positive rate
* False-negative rate

### Honest novelty assessment

We are **not claiming a novel oil-spill segmentation algorithm**.

This is an established research problem and should be treated as a baseline capability.

### Reference

Krestenitis et al., *Oil Spill Identification from Satellite Images Using Deep Neural Networks*, Remote Sensing, 2019.

https://doi.org/10.3390/rs11151762

---

# F03 — SAR Look-Alike Rejection

**Classification:** BASELINE / IMPROVEMENT
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Reduce false positives caused by non-oil regions that appear similar to oil in SAR imagery.

### Possible look-alikes

Depending on environmental conditions:

* low-wind areas
* natural films
* biogenic slicks
* internal waves
* rain effects
* sea-state effects
* other dark SAR formations

### Approach

Combine:

* segmentation model
* contextual image features
* texture
* geometry
* temporal persistence
* environmental conditions
* nearby vessel information

### Why it matters

A SAR dark patch does **not automatically mean oil**.

A useful operational system must distinguish probable oil from look-alike phenomena.

### Honest limitation

Perfect oil/look-alike separation is difficult.

The system should therefore expose uncertainty instead of treating every detection as certain oil.

### Reference

Krestenitis et al.

https://doi.org/10.3390/rs11151762

---

# F04 — Spill Geometry & Quantification

**Classification:** BASELINE
**Importance:** 🟠 HIGH
**SIH MVP:** ✅ YES

### Purpose

Convert the AI segmentation mask into usable geographic information.

### Outputs

* spill polygon
* estimated area
* centroid
* bounding box
* perimeter
* shape descriptors
* affected region

### Technology

* raster-to-vector conversion
* rasterio
* GDAL
* GeoPandas
* Shapely
* PostGIS

### Why it matters

Investigators need a geographic representation of the spill rather than only a classification label.

---

# F05 — Temporal Satellite Change Analysis

**Classification:** IMPROVEMENT / EXISTING RESEARCH
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Compare multiple satellite observations to understand how the detected spill changes over time.

### System compares

* spill location
* spill area
* centroid
* shape
* displacement
* persistence
* expansion
* disappearance

### Example

```text
Observation 1 → 8 km²
Observation 2 → 14 km²
Observation 3 → 21 km²
```

The system can then report:

> "The observed slick expanded from approximately 8 km² to 21 km² across the available satellite observations."

### Why it matters

A single satellite image provides only a snapshot.

Multiple observations provide a **temporal history**.

### Limitations

Satellite revisit intervals mean we normally do not observe the exact moment a spill began.

The system therefore reconstructs the event from discrete observations.

---

# F06 — Spill Evolution Reconstruction

**Classification:** IMPROVEMENT
**Importance:** 🟠 HIGH
**SIH MVP:** ✅ YES

### Purpose

Convert multiple individual detections into one evolving spill event.

### Outputs

* event timeline
* area vs time
* centroid movement
* shape evolution
* observation gaps
* first/last detected observations

### Why it matters

This creates the temporal context needed for source investigation.

Instead of treating every image independently, the system understands them as observations of the same evolving event.

---

# F07 — Environmental Context Layer

**Classification:** BASELINE / EXISTING
**Importance:** 🟠 HIGH
**SIH MVP:** ✅ YES

### Purpose

Provide environmental information required to understand oil movement.

### Inputs

Potentially:

* wind speed
* wind direction
* ocean currents
* waves
* Stokes drift

### Potential data sources

* ECMWF / Copernicus
* NOAA
* appropriate oceanographic datasets

### Why it matters

Oil does not remain stationary.

Its movement is influenced by:

* wind
* currents
* waves
* other physical processes

### Limitation

Environmental datasets also have uncertainty and resolution limitations.

A drift model cannot be more accurate than the environmental information driving it.

---

# F08 — Oil-Spill Drift Simulation

**Classification:** EXISTING / BASELINE
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Simulate the movement of oil under environmental conditions.

### Recommended approach

Use a **Lagrangian particle model**.

For the MVP:

* OpenDrift
* wind forcing
* ocean currents
* particle simulation

### Concept

```text
Initial Spill
     ↓
Wind + Current Data
     ↓
Particle Simulation
     ↓
Predicted Oil Movement
```

### Why it matters

It provides a physical basis for understanding how the observed slick may have moved.

### Important point

Drift simulation is **not new technology**.

We are using an established modelling approach.

### References

OpenDrift / oil-spill trajectory research:

https://doi.org/10.1016/j.marpolbul.2023.115497

https://doi.org/10.1016/j.dsr2.2016.04.002

---

# F09 — Source Backtracking / Probable Source Region

**Classification:** IMPROVEMENT / ADVANCED EXISTING RESEARCH
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Instead of only predicting where the oil will go, estimate where it could have originated.

### Concept

```text
Observed Spill
      ↓
Wind + Current Conditions
      ↓
Backward Particle Trajectories
      ↓
Possible Source Region
      ↓
Candidate Vessels
```

### Output

The system generates:

* probable source region
* uncertainty envelope
* possible source locations
* temporal source window

### Why this is important

Detection answers:

> "Where is the oil?"

Backtracking attempts to answer:

> "Where could it have originated?"

That is much more useful for source investigation.

### Technology

* Lagrangian particles
* backward trajectories
* wind/current forcing
* ensemble simulation
* uncertainty envelope

### Honest novelty assessment

Backtracking itself is **not novel**.

The proposed differentiation is connecting the backtracked source region directly to:

* satellite observations
* spill timeline
* AIS vessel activity
* evidence ranking

### Reference

https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2024.1427604/full

---

# F10 — AIS Vessel Correlation

**Classification:** BASELINE / EXISTING
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Identify vessels whose location and movement are compatible with the estimated spill source region and time.

### AIS fields

Potentially:

* MMSI
* timestamp
* latitude
* longitude
* speed over ground
* course over ground
* heading
* vessel type
* vessel dimensions
* destination

### Candidate filtering

A vessel becomes a candidate based on factors such as:

* spatial proximity
* temporal compatibility
* source-region overlap
* trajectory compatibility
* vessel type
* AIS data quality

### Critical principle

> **AIS is evidence, not ground truth.**

AIS may be:

* missing
* delayed
* noisy
* switched off
* spoofed
* incomplete

### Honest novelty assessment

AIS vessel correlation already exists commercially and academically.

We are **not claiming this as a new technology**.

---

# F11 — Vessel Behaviour / Trajectory Anomaly Analysis

**Classification:** EXISTING / IMPROVEMENT
**Importance:** 🟡 MEDIUM-HIGH
**SIH MVP:** ⚠️ IF TIME

### Purpose

Identify vessel behaviour that deserves additional investigation.

### Possible signals

* unexpected stopping
* unusual course change
* unusual speed change
* AIS gap
* route deviation
* unusual loitering
* presence near source region

### Critical warning

These signals are **not proof of illegal activity**.

For example:

> A vessel stopping does not mean that it dumped oil.

A vessel may stop for completely legitimate reasons.

### Recommended approach

For the MVP:

* transparent rules
* trajectory statistics
* simple anomaly detection

Potential future:

* Isolation Forest
* sequence models
* learned behaviour models

### Domain limitation

What constitutes "suspicious" behaviour requires maritime-domain validation.

We should not invent arbitrary thresholds and present them as maritime facts.

---

# F12 — AIS–Satellite Consistency / Adversarial Check

**Classification:** PROPOSED / UNIQUE SYSTEM FEATURE
**Importance:** 🔴 HIGH
**SIH MVP:** ✅ YES

### Purpose

Detect inconsistencies between AIS information and satellite observations.

### Why it is needed

A vessel may:

* turn off AIS
* have incomplete AIS records
* broadcast inaccurate information
* potentially spoof its location

Therefore, the system should not blindly trust AIS.

### Example

```text
AIS:
Vessel reported 40 km away

Satellite:
Vessel observed near suspected source region

Result:
AIS–Satellite Inconsistency
```

### Important limitation

The system should **not** say:

> "The vessel spoofed AIS."

Instead:

> "AIS and satellite observations are inconsistent; further investigation is required."

### Why this is differentiated

The individual components already exist.

The proposed contribution is treating **cross-source inconsistency as explicit investigation evidence** within the oil-spill workflow.

---

# F13 — Multi-Source Evidence Fusion

**Classification:** PROPOSED / UNIQUE
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

## Core Differentiator

### Purpose

Combine all relevant evidence into one investigation assessment.

### Evidence sources

1. Satellite detection
2. Temporal evolution
3. Spill geometry
4. Environmental conditions
5. Drift simulation
6. Backtracked source region
7. AIS trajectory
8. Vessel proximity
9. Vessel behaviour
10. AIS–satellite consistency
11. Data quality

### Conceptual scoring

```text
Candidate Score
    =
Spatial Compatibility
+ Temporal Compatibility
+ Drift Compatibility
+ Trajectory Compatibility
+ Satellite Consistency
+ Vessel Compatibility
+ Supporting Evidence
- Contradictory Evidence
- Data Quality Penalties
```

### Important

The score should represent:

> **Evidence compatibility**

not:

> **Probability that the vessel is guilty**

### Why this is important

A vessel should not become the top candidate simply because:

* it was nearby
* its AIS track looks unusual
* one model produced a high confidence value

Multiple independent evidence layers should be considered.

### Honest novelty statement

The individual technologies already exist.

The proposed novelty is the **operational evidence-fusion layer connecting them into one investigation pipeline**.

---

# F14 — Evidence Provenance / Explainable Investigation Record

**Classification:** PROPOSED / UNIQUE
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Allow an investigator to understand exactly why a vessel was ranked.

### Each investigation record should contain

* satellite scene ID
* satellite timestamp
* detection mask
* spill polygon
* estimated area
* temporal observations
* environmental data
* drift assumptions
* source-region estimate
* AIS records used
* candidate vessel
* supporting evidence
* contradictory evidence
* model confidence
* data adequacy
* investigator decision

### Example

```text
Candidate Vessel A

Supporting:
✓ Present near estimated source region
✓ Time compatible
✓ Trajectory compatible
✓ Drift simulation intersects vessel track

Contradictory:
⚠ AIS gap during part of the relevant window

Data limitations:
⚠ Satellite observation gap of 8 hours

Assessment:
HIGH EVIDENCE COMPATIBILITY
```

### Why it matters

An investigator should be able to ask:

> "Why did the system rank this vessel?"

and receive an understandable evidence trail.

---

# F15 — Model Uncertainty vs Data Adequacy

**Classification:** PROPOSED / UNIQUE
**Importance:** 🔴 CRITICAL
**SIH MVP:** ⚠️ PROTOTYPE

### Purpose

Separate model uncertainty from insufficient training/observation data.

### Model uncertainty

The model has sufficient relevant data but is uncertain about its prediction.

Example:

> Image is ambiguous between oil and look-alike.

### Data scarcity / inadequacy

The model has insufficient representative examples.

Example:

> Very few training examples exist for this particular class, region, or environmental condition.

### Why this distinction matters

A low model confidence score does not automatically mean:

> "The phenomenon is difficult to detect."

It may mean:

> "The model has insufficient representative training data."

### Proposed output

Instead of only:

```text
Confidence: 42%
```

show:

```text
Detection confidence: 42%
Data adequacy: LIMITED

Reason:
Observation differs from available training distribution.
```

### Honest MVP scope

A fully calibrated uncertainty framework is beyond the hackathon.

For SIH we should:

* expose model confidence
* document training-data limitations
* flag insufficient data where possible
* avoid presenting confidence as probability of guilt

---

# F16 — Candidate Vessel Ranking

**Classification:** PROPOSED / UNIQUE SYSTEM OUTPUT
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Rank vessels according to evidence compatibility.

### Example

| Rank | Vessel   | Assessment                    |
| ---- | -------- | ----------------------------- |
| 1    | Vessel A | Strong evidence compatibility |
| 2    | Vessel B | Moderate compatibility        |
| 3    | Vessel C | Weak / contradictory evidence |

### Terminology

Use:

* Candidate vessel
* Evidence compatibility
* Investigation priority
* Supporting evidence
* Contradictory evidence

Avoid:

* Guilty vessel
* Responsible vessel
* Confirmed polluter

unless independently established by authorized investigation.

### Why

The system is **decision support**, not an automated legal attribution system.

---

# F17 — Human-in-the-Loop Investigation

**Classification:** RESPONSIBLE DEPLOYMENT / BASELINE
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Ensure automated results are reviewed by an authorized human investigator.

### Investigator can

* inspect satellite imagery
* inspect spill mask
* inspect timeline
* inspect drift result
* inspect AIS track
* inspect evidence
* accept candidate for investigation
* reject candidate
* mark uncertain
* add notes

### Investigation status

```text
Detected
   ↓
Under Review
   ↓
Candidate Generated
   ↓
Investigation Ongoing
   ↓
 ┌───────────────┐
 ↓               ↓
Rejected      Confirmed
```

### Why it matters

The AI system does not possess the complete operational, legal, or contextual information needed to make an enforcement decision.

---

# F18 — Correction / Audit Mechanism

**Classification:** PROPOSED / UNIQUE
**Importance:** 🟠 HIGH
**SIH MVP:** ⚠️ PROTOTYPE

### Purpose

Prevent an incorrect automated result from becoming irreversible.

### Store

* original model output
* input data
* model version
* evidence
* ranking
* investigator decision
* correction reason
* timestamp

### Investigator actions

* reject candidate
* change status
* add evidence
* add notes
* record reason

### Important principle

Corrections should not silently delete previous results.

They should create an **auditable investigation history**.

---

# F19 — Missing / Adversarial AIS Handling

**Classification:** IMPROVEMENT / PROPOSED
**Importance:** 🟠 HIGH
**SIH MVP:** ⚠️ PROTOTYPE

### Cases

* AIS switched off
* AIS data gap
* spoofed position
* inconsistent MMSI track
* incomplete history
* satellite/AIS mismatch

### System behaviour

Bad approach:

> "No AIS record → vessel not involved."

Better approach:

> "AIS evidence unavailable or inconsistent; vessel cannot be ruled out based solely on AIS absence."

### Why

This makes the system more robust to incomplete or adversarial data.

---

# F20 — Historical Incident Replay

**Classification:** VALIDATION / PROPOSED
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Validate the complete pipeline against historical incidents.

### Process

```text
Historical Incident
       ↓
Satellite Data
       ↓
Oil Detection
       ↓
Temporal Reconstruction
       ↓
Environmental Data
       ↓
Backtracking
       ↓
AIS Correlation
       ↓
Candidate Ranking
       ↓
Compare Against Known Evidence
```

### Questions to evaluate

1. Did the system detect the spill?
2. Was the estimated spill region reasonable?
3. Was temporal evolution reconstructed correctly?
4. Was the source region plausible?
5. Was the known vessel ranked highly when sufficient evidence existed?
6. Did the system correctly express uncertainty?

### Critical principle

The system should also receive credit for:

> **Correctly refusing to attribute a vessel when evidence is insufficient.**

---

# F21 — Historical Ground-Truth Incident Dataset

**Classification:** EXISTING DATA + PROJECT DATA
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Purpose

Create a small benchmark for end-to-end validation.

### Desired fields

* incident ID
* incident date
* location
* satellite imagery
* spill extent
* known/probable source
* vessel information
* AIS track
* environmental conditions
* independent documentation

### Important classification

Historical incidents should be separated into:

```text
Confirmed source
Probable source
Source unknown
```

These must not be mixed.

### Major limitation

Public oil-spill segmentation datasets do **not necessarily contain confirmed responsible-vessel ground truth**.

Therefore:

* segmentation validation
* source attribution validation

must be treated as separate evaluation problems.

### Dataset reference

Krestenitis et al.:

https://doi.org/10.3390/rs11151762

Recent dataset context:

https://doi.org/10.5194/essd-17-6807-2025

---

# F22 — Investigator Geospatial Dashboard

**Classification:** BASELINE / SYSTEM INTEGRATION
**Importance:** 🔴 CRITICAL
**SIH MVP:** ✅ YES

### Main map

Display:

* satellite imagery
* spill segmentation
* spill polygon
* vessel tracks
* candidate vessels
* probable source region
* drift particles

### Side panel

Display:

* event information
* spill area
* detection confidence
* data adequacy
* candidate ranking
* supporting evidence
* contradictory evidence

### Timeline

Show:

* satellite observations
* spill growth
* vessel positions
* environmental conditions

### Recommended technology

Frontend:

* React
* TypeScript
* MapLibre GL / OpenLayers

Backend:

* FastAPI
* Python
* PostgreSQL/PostGIS

---

# 4. Feature Priority Matrix

| Priority                    | Features                                                                                                                                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 🔴 **CRITICAL — MUST HAVE** | Satellite ingestion, oil detection, look-alike rejection, spill quantification, temporal analysis, environmental context, drift, backtracking, AIS correlation, evidence fusion, candidate ranking, dashboard, historical validation |
| 🟠 **HIGH — SHOULD HAVE**   | Spill evolution, AIS-satellite inconsistency, evidence provenance, uncertainty/data adequacy, human investigation status, correction/audit                                                                                           |
| 🟡 **MEDIUM — IF TIME**     | Vessel behaviour anomaly detection, advanced AIS anomaly analysis                                                                                                                                                                    |
| ⚪ **FUTURE**                | Learned backtracking, advanced uncertainty calibration, global real-time AIS infrastructure, large historical database, advanced adversarial detection                                                                               |

---

# 5. What Is Actually Existing?

The following technologies are **not claimed as our inventions**:

* Sentinel-1 SAR oil-spill detection
* U-Net / semantic segmentation
* oil/look-alike classification
* SAR change detection
* AIS vessel tracking
* vessel trajectory analysis
* vessel anomaly detection
* oil-spill drift modelling
* Lagrangian particle tracking
* oil-spill backtracking
* geospatial visualization

These are established technologies/research areas.

---

# 6. What Is Our Proposed Differentiation?

The strongest differentiation is at the **system level**.

## 6.1 Satellite-First Investigation

Instead of starting with a generic maritime intelligence platform, the workflow starts with:

> **"We observed a possible oil spill from satellite imagery."**

The system then works toward identifying plausible source candidates.

---

## 6.2 Temporal Investigation

The system does not treat a spill as a single image.

It reconstructs:

> **How the spill changed over time.**

---

## 6.3 Source-Oriented Backtracking

Instead of stopping at:

> "Oil detected here."

the system asks:

> "Given observed movement and environmental conditions, what source region is physically plausible?"

---

## 6.4 Cross-Source Evidence Fusion

Satellite, environmental, AIS and temporal information are combined into one investigation assessment.

---

## 6.5 Contradiction-Aware Investigation

The system explicitly records when different evidence sources disagree.

For example:

```text
Satellite:
Vessel observed near source

AIS:
Vessel reported elsewhere

Result:
Evidence conflict / investigate further
```

---

## 6.6 Uncertainty-Aware Attribution

The system does not force a vessel attribution when:

* satellite data is insufficient
* AIS data is missing
* drift uncertainty is high
* model confidence is low
* ground truth is unavailable

---

## 6.7 Evidence Provenance

Every candidate result can be traced back to the observations and assumptions that produced it.

---

# 7. End-to-End Architecture

```text
                         ┌─────────────────────┐
                         │   SATELLITE DATA    │
                         │ Sentinel-1 SAR      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ SAR PREPROCESSING   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ AI OIL-SPILL DETECTION       │
                    │ + LOOK-ALIKE REJECTION      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ SPILL GEOMETRY & QUANTIFICATION│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ TEMPORAL CHANGE ANALYSIS     │
                    │ + SPILL EVOLUTION            │
                    └──────────────┬───────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                         ▼                   ▼
               ┌────────────────┐   ┌────────────────┐
               │ ENVIRONMENTAL  │   │   AIS DATA     │
               │ Wind / Current │   │ Vessel Tracks  │
               └───────┬────────┘   └───────┬────────┘
                       │                    │
                       ▼                    ▼
               ┌────────────────┐   ┌────────────────┐
               │ DRIFT /        │   │ VESSEL         │
               │ BACKTRACKING   │   │ CORRELATION    │
               └───────┬────────┘   └───────┬────────┘
                       │                    │
                       └─────────┬──────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │ MULTI-SOURCE EVIDENCE    │
                    │ FUSION                   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ CANDIDATE VESSEL RANKING │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ EVIDENCE + UNCERTAINTY   │
                    │ REPORT                   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ HUMAN INVESTIGATOR       │
                    └──────────────────────────┘
```

---

# 8. Technology Stack

## Frontend

* React
* TypeScript
* MapLibre GL / OpenLayers
* Charting library

## Backend

* Python
* FastAPI
* PostgreSQL
* PostGIS

## Machine Learning

* PyTorch
* U-Net / U-Net++
* SegFormer if required
* NumPy
* OpenCV

## Geospatial

* GDAL
* rasterio
* GeoPandas
* Shapely
* PostGIS

## Satellite

* Sentinel-1 SAR
* Copernicus data ecosystem

## Environmental

* ECMWF/Copernicus
* NOAA
* wind datasets
* ocean-current datasets
* wave data where available

## Drift

* OpenDrift
* Lagrangian particle modelling

## AIS

* historical AIS dataset
* accessible AIS source/API for prototype

## Deployment

* Docker
* local/server deployment
* optional cloud deployment

---

# 9. Validation Strategy

Validation must occur at **three levels**.

## Level 1 — Component Validation

### Oil detection

Measure:

* IoU
* Dice/F1
* precision
* recall

### Drift

Measure:

* trajectory error
* predicted vs observed displacement
* source-region overlap

### AIS

Measure:

* candidate retrieval
* trajectory matching
* ranking quality

---

# Level 2 — Feature Integration Validation

Test:

```text
Detection
+
Temporal analysis
+
Drift
+
AIS
```

Check whether the outputs remain geographically and temporally consistent.

---

# Level 3 — End-to-End Validation

Start with a known historical event.

Run:

```text
Satellite
→ Detection
→ Temporal Reconstruction
→ Drift
→ Backtracking
→ AIS
→ Candidate Ranking
```

Then compare with independently documented information.

### Metrics

Where ground truth exists:

* Top-1 candidate accuracy
* Top-3 recall
* Mean Reciprocal Rank
* false attribution rate
* source-region overlap
* detection success

### Additional metric

Measure:

> **Correct non-attribution**

Meaning the system correctly refuses to identify a vessel when available evidence is insufficient.

---

# 10. Adversarial Threat Model

The system must consider:

## Threat 1 — AIS spoofing

A vessel broadcasts a misleading position.

### Response

Compare AIS with:

* satellite observations
* trajectory history
* environmental constraints

Flag inconsistencies.

---

## Threat 2 — AIS shutdown

Vessel stops transmitting.

### Response

Do not interpret missing AIS as evidence that the vessel was absent.

---

## Threat 3 — Satellite false positive

SAR dark patch is not oil.

### Response

Use:

* look-alike classification
* contextual features
* temporal evidence
* environmental context

---

## Threat 4 — Incorrect drift assumption

Environmental forcing is inaccurate.

### Response

Use:

* uncertainty envelope
* ensemble particles
* multiple possible trajectories

---

## Threat 5 — Wrong vessel attribution

System ranks the wrong vessel.

### Response

* candidate terminology
* evidence provenance
* contradictory evidence
* human verification
* correction/audit mechanism

---

# 11. Important Design Principle — No Single Source Is Truth

```text
Satellite ≠ Absolute Truth
AIS       ≠ Absolute Truth
Drift     ≠ Absolute Truth
AI Score  ≠ Absolute Truth
```

Instead:

```text
Satellite Evidence
        +
Temporal Evidence
        +
Environmental Evidence
        +
AIS Evidence
        +
Data Quality
        ↓
Evidence Assessment
```

This is fundamental to the system.

---

# 12. What the System Must NOT Claim

We should **not** claim:

❌ "The AI identifies the guilty ship."

❌ "The system proves AIS spoofing."

❌ "The system provides legally valid attribution."

❌ "The model always distinguishes oil from every look-alike."

❌ "The system predicts the exact spill origin."

❌ "The system works perfectly with missing AIS."

❌ "Our segmentation model is a new research breakthrough."

❌ "Our drift model is novel."

❌ "We have a large ground-truth dataset of confirmed responsible vessels" unless we actually obtain one.

---

# 13. Correct System Positioning

## Wrong positioning

> AI system that automatically identifies which ship caused an oil spill.

## Correct positioning

> **AI-assisted satellite intelligence system that detects oil spills, reconstructs their evolution, estimates probable source regions, correlates vessel activity, and presents evidence-backed candidate vessels for human investigation.**

---

# 14. SIH MVP Scope

The hackathon version should focus on one convincing end-to-end pipeline.

## MUST IMPLEMENT

```text
Sentinel-1 Image
       ↓
Oil-Spill Detection
       ↓
Spill Mask
       ↓
Spill Area
       ↓
Multi-Temporal Comparison
       ↓
Environmental Data
       ↓
Backtracking / Drift
       ↓
AIS Correlation
       ↓
Candidate Ranking
       ↓
Evidence Dashboard
```

## CAN BE SIMPLIFIED

* environmental model
* AIS anomaly detection
* uncertainty estimation
* audit mechanism

These can initially use transparent rules rather than advanced research models.

## SHOULD NOT BE ATTEMPTED FOR SIH

* global real-time AIS infrastructure
* new ocean circulation model
* new deep-learning drift model
* fully autonomous legal attribution
* perfect AIS spoofing detection
* production-scale satellite infrastructure

---

# 15. Recommended Demonstration Scenario

## Step 1 — Spill Detection

Load a Sentinel-1 scene.

AI identifies a probable oil slick.

---

## Step 2 — Spill Quantification

System displays:

* spill polygon
* approximate area
* location
* confidence

---

## Step 3 — Temporal Analysis

Load previous and subsequent satellite observations.

Show:

```text
T1 → 8 km²
T2 → 14 km²
T3 → 21 km²
```

---

## Step 4 — Environmental Analysis

Display:

* wind direction
* wind speed
* current direction

---

## Step 5 — Backtracking

Run particles backward from the observed slick.

Generate:

> Probable source region

with uncertainty.

---

## Step 6 — AIS Correlation

Find vessels that were:

* geographically compatible
* temporally compatible
* trajectory-compatible

---

## Step 7 — Evidence Fusion

Example:

```text
Candidate A

Spatial compatibility       ✓
Temporal compatibility      ✓
Drift compatibility         ✓
AIS trajectory              ✓
Satellite consistency       ✓
AIS data gap                ⚠

Overall:
STRONG EVIDENCE COMPATIBILITY
```

---

## Step 8 — Investigator Review

The investigator sees the complete evidence chain and decides whether to:

* investigate
* reject
* mark uncertain

---

# 16. References

## Oil-Spill Detection

### Krestenitis et al. — Oil Spill Identification from Satellite Images Using Deep Neural Networks

Remote Sensing, 2019.

https://doi.org/10.3390/rs11151762

Relevant to:

* Sentinel-1 SAR
* semantic segmentation
* oil-spill detection
* look-alikes
* ships
* land
* sea

---

### Deep-Learning Framework for Oil-Spill Detection

Relevant to:

* SAR imagery
* deep learning
* segmentation
* oil/look-alike classification

https://pmc.ncbi.nlm.nih.gov/articles/PMC8036558/

---

# Oil-Spill Drift / Trajectory

### Preliminary Assessment of an Oil-Spill Trajectory Model

Relevant to:

* wind forcing
* ocean currents
* trajectory modelling
* validation

https://doi.org/10.1016/j.envsoft.2004.04.025

---

### Impact of Currents, Waves and Wind in Modelling Surface Drifters and Oil Spill

Relevant to:

* currents
* wind
* waves
* Stokes drift
* trajectory uncertainty

https://doi.org/10.1016/j.dsr2.2016.04.002

---

### Oil-Spill Modelling with OpenDrift

Relevant to:

* OpenDrift
* wind
* currents
* waves
* oil-spill trajectory modelling

https://doi.org/10.1016/j.marpolbul.2023.115497

---

# Oil-Spill Backtracking

### Prediction and (Back)tracking of Marine Oil Spill Drift and Diffusion

Relevant to:

* prediction
* backtracking
* source estimation
* trajectory modelling
* current research

https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2024.1427604/full

---

# Recent Dataset Context

### Earth System Science Data — Oil Slick / Look-Alike Dataset

Relevant to:

* Sentinel-1
* oil slicks
* look-alikes
* dataset limitations
* benchmark development

https://doi.org/10.5194/essd-17-6807-2025

---

# 17. Final Feature Summary

|  # | Feature                          | Classification         | Importance     | MVP |
| -: | -------------------------------- | ---------------------- | -------------- | :-: |
| 01 | Multi-source satellite ingestion | Baseline / Existing    | 🔴 Critical    |  ✅  |
| 02 | AI oil-spill segmentation        | Baseline / Existing    | 🔴 Critical    |  ✅  |
| 03 | Look-alike rejection             | Baseline / Improvement | 🔴 Critical    |  ✅  |
| 04 | Spill geometry & quantification  | Baseline               | 🟠 High        |  ✅  |
| 05 | Temporal satellite analysis      | Improvement            | 🔴 Critical    |  ✅  |
| 06 | Spill evolution reconstruction   | Improvement            | 🟠 High        |  ✅  |
| 07 | Environmental context            | Existing               | 🟠 High        |  ✅  |
| 08 | Drift simulation                 | Existing               | 🔴 Critical    |  ✅  |
| 09 | Source backtracking              | Improvement            | 🔴 Critical    |  ✅  |
| 10 | AIS vessel correlation           | Existing               | 🔴 Critical    |  ✅  |
| 11 | Vessel behaviour analysis        | Existing / Improvement | 🟡 Medium-High |  ⚠️ |
| 12 | AIS–satellite inconsistency      | Proposed               | 🟠 High        |  ✅  |
| 13 | Multi-source evidence fusion     | Proposed               | 🔴 Critical    |  ✅  |
| 14 | Evidence provenance              | Proposed               | 🔴 Critical    |  ✅  |
| 15 | Confidence vs data adequacy      | Proposed               | 🔴 Critical    |  ⚠️ |
| 16 | Candidate vessel ranking         | Proposed               | 🔴 Critical    |  ✅  |
| 17 | Human-in-the-loop                | Responsible deployment | 🔴 Critical    |  ✅  |
| 18 | Correction / audit mechanism     | Proposed               | 🟠 High        |  ⚠️ |
| 19 | Missing/adversarial AIS handling | Improvement / Proposed | 🟠 High        |  ⚠️ |
| 20 | Historical incident replay       | Validation             | 🔴 Critical    |  ✅  |
| 21 | Historical ground-truth dataset  | Validation             | 🔴 Critical    |  ✅  |
| 22 | Investigator dashboard           | Integration            | 🔴 Critical    |  ✅  |

---

# 18. Final Honest Assessment

The project is strongest when described as a **system-level integration problem**, not as a collection of novel AI algorithms.

### Established

* Satellite oil-spill detection
* SAR segmentation
* Look-alike detection
* AIS tracking
* Vessel anomaly analysis
* Oil-spill drift modelling
* Backtracking
* Geospatial visualization

### Improved

* Temporal spill reconstruction
* Source-oriented investigation
* Cross-source consistency checking
* Uncertainty reporting
* Missing-AIS handling

### Proposed differentiation

* Satellite-first investigation workflow
* Multi-source evidence fusion
* Contradiction-aware evidence
* Evidence provenance
* Candidate ranking rather than automatic accusation
* Human-verifiable investigation workflow

### Core claim

> **We are not claiming to have invented each component. We are proposing an integrated, satellite-first investigation pipeline that turns separate observations — satellite imagery, temporal change, environmental drift and vessel activity — into a transparent evidence assessment for human investigators.**

That is the claim we should defend in the SIH presentation.
