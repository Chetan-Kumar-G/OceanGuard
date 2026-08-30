# OilTrace AI — Final Feature Specification

> **SIH Problem Statement:** 26143  
> **Project:** AI-Assisted Satellite Oil-Spill Detection, Reconstruction & Vessel Investigation

---

## 1. Project Overview

OilTrace AI is an AI-assisted maritime investigation and decision-support system that combines satellite imagery, multi-temporal observations, environmental data, drift modelling, and historical AIS data to:

1. Detect probable oil spills.
2. Reduce false detections caused by SAR look-alikes.
3. Reconstruct observed spill evolution.
4. Generate physically plausible source hypotheses.
5. Correlate source hypotheses with historical vessel activity.
6. Detect conflicts between different evidence sources.
7. Rank competing hypotheses using transparent evidence fusion.
8. Provide an explainable investigation trail for human investigators.

### Critical Limitation

OilTrace AI does **not**:

- Automatically prove the responsible vessel.
- Determine legal responsibility.
- Guarantee the exact physical source of a spill.
- Automatically prove AIS spoofing.
- Replace maritime investigators or authorities.

The system produces **evidence-based investigation hypotheses**, not accusations.

---

# 2. Final Feature Set

| # | Feature | Classification | Importance | SIH MVP |
|---|---|---|---|---|
| 1 | AI Oil-Spill Detection & Look-Alike Analysis | Baseline + Improvement | Critical | Yes |
| 2 | Multi-Temporal Spill Reconstruction & Characterization | Improvement | Critical | Yes |
| 3 | Environmental Drift & Backward Hindcasting → Source Hypotheses | Existing + Improvement | Critical | Yes |
| 4 | Historical AIS Vessel Reconstruction & Correlation | Baseline / Existing | Critical | Yes |
| 5 | Cross-Source Consistency & Evidence Conflict Detection | Proposed Differentiator | High | Yes |
| 6 | Evidence Fusion & Dynamic Hypothesis Ranking | Proposed System-Level Differentiator | Critical | Yes |
| 7 | Forensic Investigation Graph & Explainable Evidence Chain | Proposed Workflow Differentiator | High | Yes |
| 8 | Forward Forecasting, Impact Assessment & Historical Replay | Existing + Improvement + Validation | High | Optional / Validation |

### Classification Definitions

| Classification | Meaning |
|---|---|
| **Baseline** | Expected functionality required for a credible oil-spill investigation system. |
| **Existing** | Established technology or research adopted by the system. |
| **Improvement** | Existing technology applied in a more useful or robust workflow. |
| **Proposed Differentiator** | Proposed system-level contribution; not a claim that the underlying algorithm is newly invented. |
| **Validation** | Capability primarily used to test and demonstrate system reliability. |

---

# 3. Overall System Workflow

Satellite Observation  
↓  
Probable Oil-Spill Detection  
↓  
Look-Alike Analysis  
↓  
Spill Characterization  
↓  
Multi-Temporal Reconstruction  
↓  
Environmental Conditions  
↓  
Drift / Backward Hindcasting  
↓  
Plausible Source Hypotheses  
↓  
Historical AIS Reconstruction  
↓  
Vessel Correlation  
↓  
Cross-Source Consistency  
↓  
Evidence Fusion  
↓  
Hypothesis / Candidate Ranking  
↓  
Explainable Investigation  
↓  
Human Investigator  
↓  
Investigate / Reject / Insufficient Evidence

---

# 4. Feature 1 — AI Oil-Spill Detection & Look-Alike Analysis

**Classification:** Baseline + Improvement  
**Importance:** Critical  
**SIH MVP:** Yes  
**Feasibility:** High  
**Technical Depth:** High  
**Algorithmic Novelty:** Low

## Purpose

Detect probable oil-spill regions from satellite imagery while reducing false detections caused by oil-spill look-alikes.

## Workflow

Satellite Image  
↓  
SAR Preprocessing  
↓  
Segmentation Model  
↓  
Probable Spill Mask  
↓  
Look-Alike Assessment  
↓  
Spill Polygon + Confidence

## Primary Data Source

### Sentinel-1 SAR

Initial focus:

- VV polarization
- VH polarization where useful

Optional secondary source:

- Sentinel-2 optical imagery when suitable and cloud-free.

## SAR Processing

Potential pipeline:

Raw Sentinel-1  
↓  
Radiometric Calibration  
↓  
Speckle / Noise Handling  
↓  
Geometric Correction  
↓  
Normalization  
↓  
AOI Extraction  
↓  
ML Input

### Technologies

- GDAL
- rasterio
- NumPy
- OpenCV
- GeoPandas
- SNAP where appropriate

## ML Model

Recommended starting models:

- U-Net
- U-Net++
- DeepLabV3+
- SegFormer

The SIH prototype should prioritize a reliable and trainable model rather than attempting to invent a new neural-network architecture.

## Dataset

### Krestenitis et al.

The dataset contains Sentinel-1 SAR imagery with classes including:

- Sea
- Oil spill
- Look-alike
- Ship
- Land

Paper:

https://doi.org/10.3390/rs11151762

## Look-Alike Problem

A dark SAR region does not automatically represent oil.

Potential look-alikes include:

- Low-wind areas
- Biogenic films
- Internal waves
- Rain-related effects
- Sea-state effects
- Other dark formations

Therefore:

Dark SAR Region  
↓  
Possible Oil + Possible Look-Alike  
↓  
Context + Model + Temporal Evidence  
↓  
Probable Spill Assessment

## Output

The system produces:

- Spill mask
- Spill polygon
- Estimated area
- Detection confidence
- Look-alike risk
- Data-quality indicator

Example:

Oil-Spill Likelihood: HIGH  
Look-Alike Risk: MEDIUM  
Detection Confidence: HIGH  
Data Adequacy: MEDIUM

## Important Limitation

Do not say:

> "This dark patch is definitely oil."

Use:

> "The observed SAR signature is consistent with a probable oil spill."

## Evaluation

- IoU
- Dice/F1
- Precision
- Recall
- False-positive rate
- False-negative rate

## Honest Novelty Assessment

Oil-spill segmentation using Sentinel-1 is established research.

We do **not** claim a novel segmentation architecture.

Our improvement is integrating detection and look-alike assessment into the larger investigation workflow.

---

# 5. Feature 2 — Multi-Temporal Spill Reconstruction & Characterization

**Classification:** Improvement  
**Importance:** Critical  
**SIH MVP:** Yes  
**Feasibility:** High  
**Technical Depth:** High  
**Novelty:** Moderate at system level

## Purpose

A single satellite image provides a snapshot.

Multiple observations allow the system to reconstruct how the observed spill changed over time.

T1 → Spill Geometry  
T2 → Spill Geometry  
T3 → Spill Geometry  
↓  
Temporal Analysis  
↓  
Observed Spill Evolution

## Characterization

For every suitable observation calculate:

- Area
- Perimeter
- Centroid
- Bounding box
- Dimensions
- Shape
- Geographic coordinates
- Timestamp
- Polygon

## Temporal Analysis

Track:

- Area change
- Centroid displacement
- Shape change
- Expansion
- Contraction
- Persistence
- Disappearance
- Observation gaps

Example:

T1 → 8 km²  
T2 → 14 km²  
T3 → 21 km²

## Time-Window Estimation

Where sufficient observations exist, estimate a plausible source-compatible time window.

Do not claim:

> "The spill is exactly 6 hours old."

Use:

> "The available observations constrain the spill to a source-compatible time window."

## Oil-Spill Time Machine

Optional interface:

PAST ---------------- NOW ---------------- FUTURE

The interface can display:

- Historical observations
- Current observed state
- Modelled states
- Forecast states

Clearly label:

- OBSERVED
- MODELLED
- FORECAST

## Limitation

Sentinel-1 provides discrete observations rather than continuous video.

Therefore:

> Multi-temporal reconstruction is not continuous real-time tracking.

## Technologies

- rasterio
- GeoPandas
- Shapely
- PostGIS
- Image registration
- Temporal GIS
- Satellite metadata

## Honest Novelty Assessment

Temporal satellite analysis is established.

Our improvement is using temporal evidence as an input to source-hypothesis and vessel investigation.

---

# 6. Feature 3 — Environmental Drift & Backward Hindcasting → Source Hypotheses

**Classification:** Existing + Improvement  
**Importance:** Critical  
**SIH MVP:** Yes  
**Feasibility:** Medium-High  
**Technical Depth:** Very High  
**Algorithmic Novelty:** Low

## Purpose

Estimate how an observed slick could have moved under environmental conditions and generate physically plausible source hypotheses.

### Critical Principle

> **Backtracking does not directly identify the exact source.**

## Environmental Inputs

Potential inputs:

- Wind speed
- Wind direction
- Ocean currents
- Waves
- Stokes drift

Potential data sources:

- Copernicus
- ECMWF
- NOAA
- Other suitable oceanographic products

## Drift Model

Recommended established framework:

**OpenDrift**

Reference:

https://opendrift.github.io/

## Forward Simulation

Possible Source  
↓  
Environmental Conditions  
↓  
Particle Simulation  
↓  
Possible Future Movement

## Backward Hindcasting

Observed Spill  
↓  
Environmental Conditions  
↓  
Backward Particle Simulation  
↓  
Multiple Possible Source Regions

## Source Hypotheses

Example:

H1  
Region: A  
Time Window: X–Y  
Compatibility: HIGH

H2  
Region: B  
Time Window: X–Y  
Compatibility: MEDIUM

H3  
Region: C  
Compatibility: LOW

## Why Multiple Hypotheses?

The inverse problem may not have a unique solution.

Different:

- Source locations
- Source times
- Environmental assumptions

may produce similar observed slick positions.

Therefore the system preserves alternative explanations.

## Correct Terminology

Use:

- Plausible source region
- Source hypothesis
- Physically compatible source region
- Source-compatible time window

Avoid:

- Exact spill origin
- Source identified
- Spill definitely started at coordinate X

## Uncertainty

Potential sources:

- Environmental forcing errors
- Current/wind resolution
- Model assumptions
- Unresolved physical processes
- Satellite observation uncertainty

Where possible, represent uncertainty as an area or ensemble rather than a single exact trajectory.

## Technologies

- OpenDrift
- Lagrangian particle modelling
- Python
- NumPy
- xarray
- NetCDF
- Copernicus / ECMWF / NOAA data

## Honest Novelty Assessment

Drift modelling and backward hindcasting are established technologies.

The system-level improvement is:

Satellite  
↓  
Temporal Reconstruction  
↓  
Source Hypotheses  
↓  
AIS Correlation  
↓  
Evidence Fusion

rather than treating backtracking as the final answer.

---

# 7. Feature 4 — Historical AIS Vessel Reconstruction & Correlation

**Classification:** Baseline / Existing  
**Importance:** Critical  
**SIH MVP:** Yes  
**Feasibility:** High  
**Technical Depth:** High  
**Novelty:** Low

## Purpose

Identify vessels whose historical movement is compatible with generated source hypotheses.

Source Hypothesis  
+  
Source-Compatible Time Window  
↓  
Historical AIS  
↓  
Candidate Vessel Tracks

## AIS Fields

Potential fields:

- MMSI
- Timestamp
- Latitude
- Longitude
- Speed Over Ground
- Course Over Ground
- Heading
- Vessel Type
- Vessel Dimensions

## Candidate Filtering

### Spatial Filtering

Was the vessel near the source hypothesis?

### Temporal Filtering

Was it present during the relevant time window?

### Trajectory Filtering

Was its historical movement compatible with the source region?

Example:

47 AIS vessels  
↓  
Spatial Filtering  
↓  
12 vessels  
↓  
Temporal Filtering  
↓  
7 vessels  
↓  
Trajectory Compatibility  
↓  
5 candidates

## Critical Principle

AIS is:

> **Evidence, not ground truth.**

AIS can contain:

- Gaps
- Noise
- Delayed records
- Transmission failures
- Manipulated positions
- Incomplete coverage

## Commercial Tool Reality

Commercial maritime-intelligence systems already provide sophisticated capabilities involving:

- AIS tracking
- Vessel analytics
- Historical vessel reconstruction
- Behavioural analytics
- Satellite/AIS fusion
- Maritime intelligence
- Oil-spill-related intelligence

Therefore:

> **AIS tracking is not our innovation.**

## Our Position

AIS is an input to the investigation layer.

Our proposed contribution occurs when AIS is connected with:

Spill  
+  
Source Hypotheses  
+  
Drift  
+  
Temporal Evidence  
+  
Cross-Source Conflicts

---

# 8. Feature 5 — Cross-Source Consistency & Evidence Conflict Detection

**Classification:** Proposed Differentiator  
**Importance:** High  
**SIH MVP:** Yes  
**Feasibility:** Medium-High  
**Technical Depth:** Very High  
**Novelty:** Moderate System-Level

## Purpose

Check whether different evidence sources agree or conflict.

Sources include:

- Satellite observations
- Temporal reconstruction
- AIS
- Drift
- Environmental data
- Vessel trajectory

## Example

AIS:

> Vessel reported at Location A.

Satellite:

> Vessel-like observation near Location B.

Result:

> AIS-Satellite inconsistency.

## Conflict Types

### Spatial Conflict

AIS position does not agree with the relevant satellite observation.

### Temporal Conflict

Vessel was not present during the source-compatible time window.

### Physical Conflict

Vessel trajectory is poorly compatible with the drift-derived source hypothesis.

### Data Conflict

Important observations are missing or inconsistent.

## AIS Gap Handling

### Wrong

> "The vessel was not there."

### Correct

> "AIS evidence unavailable during this interval."

## AIS Spoofing Handling

Do not claim:

> "AIS spoofing detected."

Use:

> "AIS-satellite inconsistency detected. Possible explanations include transmission gaps, timing mismatch, data errors or deliberate manipulation. Further investigation is required."

## Why This Matters

Instead of blindly trusting one data source, the system asks:

> **Do the available sources tell a consistent story?**

## Honest Novelty Assessment

We do not claim that AIS/satellite consistency checking has never been done.

The defensible contribution is:

> **OilTrace AI explicitly represents cross-source conflicts inside the oil-spill source-hypothesis workflow and propagates those conflicts into the evidence assessment.**

---

# 9. Feature 6 — Evidence Fusion & Dynamic Hypothesis Ranking

**Classification:** Proposed System-Level Differentiator  
**Importance:** Critical  
**SIH MVP:** Yes  
**Feasibility:** High  
**Technical Depth:** Very High  
**Novelty:** Moderate-High at System Level

## Purpose

Combine evidence from Features 1–5 into transparent candidate/hypothesis assessments.

This is the **central investigation layer**.

## Evidence Inputs

### Satellite Evidence

- Spill detection
- Spill geometry
- Look-alike risk
- Detection confidence

### Temporal Evidence

- Observed evolution
- Displacement
- Persistence
- Observation gaps

### Environmental Evidence

- Wind
- Currents
- Environmental data quality

### Drift Evidence

- Source hypothesis
- Trajectory compatibility
- Uncertainty envelope

### AIS Evidence

- Vessel position
- Trajectory
- Timing
- AIS completeness

### Consistency Evidence

- Supporting evidence
- Contradictions
- Missing evidence

## Conceptual Scoring

Spatial Compatibility  
+  
Temporal Compatibility  
+  
Drift Compatibility  
+  
AIS Trajectory Compatibility  
+  
Cross-Source Consistency  
+  
Data Quality  
−  
Contradictory Evidence  
↓  
Evidence Compatibility

## Prototype Weighting

Possible initial prototype weights:

| Evidence | Weight |
|---|---:|
| Spatial compatibility | 25% |
| Temporal compatibility | 20% |
| Drift compatibility | 25% |
| AIS trajectory compatibility | 15% |
| Cross-source consistency | 10% |
| Data quality | 5% |

### Important

These weights are **prototype assumptions**, not scientifically established probabilities.

For production use, they require:

- Domain expert review
- Historical validation
- Calibration
- Sensitivity analysis

## Candidate Ranking

Example:

Candidate A → HIGH  
Candidate B → MEDIUM  
Candidate C → LOW  
Unknown → POSSIBLE

## Dynamic Ranking

Initial Evidence  
↓  
Initial Ranking  
↓  
New Satellite Observation  
↓  
New Evidence  
↓  
Recalculate  
↓  
Updated Ranking

## No-Sufficient-Evidence Outcome

The system must support:

> **Insufficient evidence for reliable attribution.**

Possible reasons:

- High look-alike risk
- Insufficient satellite observations
- High source uncertainty
- Major AIS gaps
- Conflicting evidence
- Insufficient historical evidence

## Terminology

Do NOT use:

> Probability that Vessel A is guilty.

Do NOT use:

> AI proves Vessel A caused the spill.

Use:

- Evidence compatibility
- Investigation priority
- Candidate hypothesis
- Supporting evidence
- Contradictory evidence
- Insufficient evidence

## Evidence Dependency

Not all evidence is statistically independent.

Example:

Satellite  
↓  
Source Region  
↓  
AIS Candidate

Therefore correlated evidence must not be presented as independent proof.

## Honest Novelty Assessment

The individual evidence sources are not novel.

The proposed contribution is:

> **A transparent spill-centric evidence-fusion layer that preserves supporting, contradictory and missing evidence while ranking competing source/vessel hypotheses instead of forcing a single attribution.**

---

# 10. Feature 7 — Forensic Investigation Graph & Explainable Evidence Chain

**Classification:** Proposed Workflow Differentiator  
**Importance:** High  
**SIH MVP:** Yes for core explanation  
**Feasibility:** Medium-High  
**Technical Depth:** High  
**Novelty:** Moderate System-Level

## Purpose

Show investigators:

> **Why did the system rank this candidate?**

## Evidence Chain

Satellite Observation  
↓  
Spill Polygon  
↓  
Temporal Evidence  
↓  
Environmental Conditions  
↓  
Source Hypothesis  
↓  
Vessel Track  
↓  
Supporting Evidence  
↓  
Contradictory Evidence  
↓  
Candidate Assessment  
↓  
Human Decision

## Forensic Vessel Reconstruction

When a candidate is selected:

Vessel A  
↓  
Historical AIS Track  
↓  
Relevant Time Window  
↓  
Source Hypothesis  
↓  
Drift Compatibility  
↓  
Supporting / Contradictory Evidence

## Evidence Graph

### Nodes

- Incident
- Satellite observation
- Spill polygon
- Source hypothesis
- Environmental condition
- Vessel
- AIS track
- Evidence item
- Contradiction
- Investigator decision

### Relationships

- Supports
- Contradicts
- Spatially compatible
- Temporally compatible
- Derived from
- Uncertain

## Example

INCIDENT  
├── SATELLITE  
│   └── SPILL MASK  
├── DRIFT  
│   └── SOURCE H1  
└── AIS  
    └── VESSEL A  
↓  
EVIDENCE FUSION  
↓  
CANDIDATE A  
↓  
HUMAN REVIEW

## Competing Hypotheses

H1:

> Vessel A + Source Region X

H2:

> Vessel B + Source Region Y

H3:

> Unknown Source + Region Z

Possible results:

H1 → High compatibility  
H2 → Medium compatibility  
H3 → Insufficient evidence

## Correction / Audit Mechanism

If the system incorrectly ranks a vessel:

AI Assessment  
↓  
Human Review  
↓  
Reject / Uncertain  
↓  
Reason Recorded  
↓  
Audit Trail

Store:

- Original result
- Evidence used
- Model version
- Investigator decision
- Correction reason
- Timestamp

Do not silently overwrite historical results.

## Human-in-the-Loop

The AI produces:

> Candidate + evidence

The investigator decides:

- Investigate
- Reject
- Uncertain

The system does not make the final legal or enforcement decision.

## Honest Novelty Assessment

Evidence graphs and explainability are established concepts.

We do not claim that graphs themselves are novel.

Our proposed workflow is the specific connection:

Satellite  
↓  
Spill  
↓  
Source Hypothesis  
↓  
Vessel  
↓  
Contradiction  
↓  
Candidate  
↓  
Investigator

---

# 11. Feature 8 — Forward Forecasting, Impact Assessment & Historical Replay

**Classification:** Existing + Improvement + Validation  
**Importance:** High  
**SIH MVP:** Optional / Validation Critical  
**Feasibility:** Medium-High  
**Technical Depth:** High

## 11.1 Forward Spill Forecasting

Use the current observed spill state and environmental forcing to estimate possible future movement.

Current Spill  
+  
Wind  
+  
Currents  
↓  
Drift Model  
↓  
12h / 24h / 48h Possible Movement

## 11.2 Forecast Output

Show:

- Predicted trajectory
- Predicted spread
- Uncertainty region
- Potential future locations

Clearly distinguish:

- OBSERVED
- MODELLED
- FORECAST

## 11.3 Forecast Correction

When a new satellite observation arrives:

Previous Forecast  
↓  
New Observation  
↓  
Compare  
↓  
Forecast Error  
↓  
Update Model State  
↓  
Next Forecast

A full operational data-assimilation system is outside SIH scope.

## 11.4 Impact Assessment

Potential overlay layers:

- Coastline
- Protected areas
- Fisheries
- Ports
- Environmentally sensitive zones

Output:

> Potentially affected / priority areas

Not:

> Guaranteed contamination.

## 11.5 Historical Replay

Historical events can be replayed through:

Historical Event  
↓  
Satellite  
↓  
Detection  
↓  
Temporal Reconstruction  
↓  
Environmental Data  
↓  
Drift  
↓  
Source Hypotheses  
↓  
AIS  
↓  
Evidence Fusion  
↓  
Candidate Ranking

## 11.6 Why Historical Replay Matters

It allows evaluation of the **end-to-end system**, not only individual models.

## 11.7 Ground Truth Challenge

Detection validation can use:

Satellite  
+  
Oil / Look-Alike Labels

Attribution validation requires much more:

Satellite  
+  
Spill Timing  
+  
AIS  
+  
Environmental Data  
+  
Independent Evidence  
+  
Known / Supported Source Vessel

Large public datasets containing all of these fields with confirmed responsible vessels are difficult to obtain.

Therefore:

> **Do not claim a large confirmed attribution dataset unless one is actually obtained and verified.**

Classify historical cases as:

- CONFIRMED
- PROBABLE
- UNKNOWN

Only confirmed cases should support strong attribution-validation claims.

---

# 12. Cross-Cutting Data Quality & Uncertainty

Data quality and uncertainty are not separate major features. They affect every stage.

## Satellite Quality

Consider:

- Image quality
- Observation gaps
- Look-alike risk
- Geographic coverage

## AIS Quality

Consider:

- Coverage
- Missing intervals
- Suspicious jumps
- Reporting gaps

## Environmental Data Quality

Consider:

- Spatial resolution
- Temporal resolution
- Missing data
- Forcing uncertainty

## Drift Uncertainty

Consider:

- Environmental forcing uncertainty
- Particle spread
- Model assumptions
- Source-region size

---

# 13. Model Uncertainty vs Data Adequacy

These are different concepts.

## Model Uncertainty

The model has relevant information but remains uncertain.

Example:

> Oil vs look-alike is ambiguous.

## Data Inadequacy

The available data is insufficient or poorly representative.

Example:

> Environmental conditions for the event are poorly represented by the available forcing data.

## SIH Implementation

Use qualitative states:

- HIGH
- MEDIUM
- LIMITED
- UNKNOWN

Avoid fake precision such as:

> Data Adequacy = 63.27%

unless a scientifically justified methodology is implemented.

---

# 14. Adversarial & Failure Cases

| Failure Case | Potential Result | System Response |
|---|---|---|
| SAR look-alike | False spill | Look-alike analysis |
| Poor image quality | Low confidence | Quality warning |
| Satellite revisit gap | Missing event stage | Observation-gap indicator |
| AIS gap | Missing vessel evidence | "AIS unavailable" |
| AIS manipulation | Incorrect declared location | Cross-source inconsistency |
| Drift error | Wrong source hypothesis | Uncertainty envelope |
| Multiple plausible sources | Ambiguous attribution | Competing hypotheses |
| Wrong candidate ranking | Potential false investigation | Human review |
| Insufficient evidence | Unreliable attribution | No-attribution outcome |
| Dataset bias | Poor generalization | Data adequacy warning |

---

# 15. Maritime-Domain Assumptions

The system should not invent maritime rules and present them as universal facts.

For the SIH prototype:

- Use objective spatial signals.
- Use objective temporal signals.
- Use literature-supported indicators.
- Make thresholds transparent.
- Avoid declaring behaviour illegal.
- Avoid treating anomalies as proof of wrongdoing.

For operational deployment:

> Maritime-domain experts should validate behavioural assumptions, thresholds and interpretation.

---

# 16. Commercial-System Positioning

Commercial maritime-intelligence systems already provide capabilities including:

- AIS tracking
- Vessel analytics
- Historical vessel reconstruction
- Behavioural analytics
- Satellite/AIS fusion
- Maritime risk intelligence
- Oil-spill-related intelligence

Therefore OilTrace AI does **not** claim:

> "We invented vessel intelligence."

Instead, OilTrace AI is positioned as a:

> **Satellite-first oil-spill investigation workflow.**

Observed Spill  
↓  
Spill Reconstruction  
↓  
Environmental Hindcasting  
↓  
Source Hypotheses  
↓  
AIS Correlation  
↓  
Cross-Source Consistency  
↓  
Evidence Fusion  
↓  
Candidate / Hypothesis Ranking  
↓  
Explainable Investigation

Existing AIS/intelligence sources can potentially be integrated as data providers in future deployment.

---

# 17. What Is Existing?

The following technologies are established:

- Sentinel-1 SAR
- SAR preprocessing
- Oil-spill segmentation
- U-Net and related segmentation models
- Look-alike classification research
- Spill geometry extraction
- Multi-temporal satellite analysis
- AIS tracking
- Vessel trajectory analysis
- Drift modelling
- Lagrangian particle modelling
- Hindcasting
- Forecasting
- GIS
- Evidence graphs
- Explainable AI concepts

We do **not** claim to have invented these technologies.

---

# 18. What Is Our Proposed Contribution?

## 18.1 Hypothesis-Based Source Investigation

Instead of:

Backtracking  
↓  
One Source

use:

Backtracking  
↓  
Multiple Source Hypotheses  
↓  
Evidence Evaluation

## 18.2 Cross-Source Conflict Representation

Explicitly represent:

- Agreement
- Contradiction
- Missing evidence

between:

- Satellite
- AIS
- Drift
- Temporal observations

## 18.3 Evidence Fusion

Combine evidence with:

- Data quality
- Uncertainty
- Contradictions
- Evidence dependencies

rather than treating every signal as independent proof.

## 18.4 Dynamic Hypothesis Ranking

New observations can modify candidate/hypothesis rankings.

## 18.5 No-Sufficient-Evidence Outcome

The system can explicitly conclude:

> **Insufficient evidence for reliable attribution.**

## 18.6 Explainable Investigation

Every candidate should have:

- Supporting Evidence
- Contradictory Evidence
- Missing Evidence
- Data Limitations
- Reason for Ranking

---

# 19. Claims We Can Defend

We can reasonably claim that:

1. Sentinel-1 SAR can be used for probable oil-spill detection.
2. Multiple satellite observations can reconstruct observed spill evolution.
3. Environmental drift models can generate physically plausible movement and source hypotheses.
4. Historical AIS can be correlated with source-compatible regions and time windows.
5. Cross-source comparison can expose evidence inconsistencies.
6. Multiple evidence sources can be organized into transparent candidate assessments.
7. Investigators can inspect supporting and contradictory evidence behind a candidate.
8. The system can refuse attribution when evidence is insufficient.

---

# 20. Claims We Must NOT Make

Do not claim:

- The system identifies the exact spill source.
- The system identifies the guilty vessel.
- The system proves AIS spoofing.
- A nearby vessel is responsible.
- AIS absence proves vessel absence.
- Drift gives the exact physical trajectory.
- Every SAR dark patch is oil.
- Confidence is the probability of guilt.
- Evidence sources are independent proofs.
- The system automatically provides legal evidence.
- The system replaces maritime authorities.
- Our segmentation architecture is novel.
- Our drift algorithm is novel.
- Our AIS tracking is novel.
- Commercial maritime-intelligence systems cannot perform related capabilities.

---

# 21. End-to-End User Workflow

## Step 1 — Spill Detection

Satellite imagery enters the system.

The AI detects a probable oil-spill region.

## Step 2 — Look-Alike Assessment

The system checks whether the SAR signature could plausibly be a look-alike.

## Step 3 — Spill Characterization

Calculate:

- Area
- Location
- Geometry
- Timestamp

## Step 4 — Temporal Reconstruction

Compare previous and subsequent observations.

## Step 5 — Environmental Analysis

Load:

- Wind
- Currents
- Relevant environmental data

## Step 6 — Backward Hindcasting

Generate:

> Multiple plausible source hypotheses.

## Step 7 — AIS Correlation

Search historical vessel activity around:

- Source hypotheses
- Source-compatible time windows

## Step 8 — Cross-Source Consistency

Compare:

- Satellite
- AIS
- Drift
- Timeline

## Step 9 — Evidence Fusion

Combine:

- Supporting evidence
- Contradictory evidence
- Missing evidence
- Data quality
- Uncertainty

## Step 10 — Candidate Ranking

Example:

Candidate A → HIGH  
Candidate B → MEDIUM  
Candidate C → LOW  
Unknown → POSSIBLE

## Step 11 — Explain

Show:

- Why the candidate ranked highly
- Supporting evidence
- Contradictory evidence
- Missing evidence
- Data limitations

## Step 12 — Human Decision

The investigator can:

- Investigate
- Reject
- Mark uncertain

---

# 22. Example Investigation Output

```text
==================================================
             OIL SPILL INVESTIGATION
==================================================

EVENT
--------------------------------------------------
First observed: 14:20 UTC
Last observed: 22:40 UTC
Observed area: 18.6 km²

DETECTION
--------------------------------------------------
Oil-Spill Likelihood: HIGH
Look-Alike Risk: MEDIUM
Data Adequacy: MEDIUM

SOURCE HYPOTHESIS
--------------------------------------------------
Region: 7.8 km uncertainty radius
Time Window: 11:30–15:00 UTC
Drift Uncertainty: MEDIUM

--------------------------------------------------
CANDIDATE #1 — VESSEL A
--------------------------------------------------

Evidence Compatibility: HIGH

Supporting:
✓ Spatial compatibility
✓ Temporal compatibility
✓ Drift compatibility
✓ AIS trajectory compatibility

Contradictory:
⚠ AIS gap during relevant interval

Data Limitations:
⚠ Satellite observation gap
⚠ Source-region uncertainty

--------------------------------------------------
CANDIDATE #2 — VESSEL B
--------------------------------------------------

Evidence Compatibility: MEDIUM

Supporting:
✓ Temporal compatibility

Contradictory:
⚠ Poor drift compatibility

--------------------------------------------------
CANDIDATE #3 — VESSEL C
--------------------------------------------------

Evidence Compatibility: LOW

Supporting:
✓ Nearby

Contradictory:
✗ Outside source-compatible time window

==================================================
SYSTEM STATUS:
CANDIDATES FOR HUMAN INVESTIGATION

NOT AN AUTOMATED ATTRIBUTION
==================================================
# 23. End-to-End Validation Strategy

The system should be evaluated at three levels.

## Level 1 — Detection

Metrics:

- IoU
- Dice/F1
- Precision
- Recall
- False-positive rate
- False-negative rate

## Level 2 — Physical / Temporal

### Temporal

- Area-change error
- Centroid displacement error
- Polygon overlap

### Drift

- Trajectory error
- Displacement error
- Source-region overlap
- Ensemble spread

## Level 3 — Investigation

Where appropriate ground truth exists:

- Top-1 candidate accuracy
- Top-3 recall
- Mean Reciprocal Rank
- False-attribution rate
- Correct no-attribution rate

---

# 24. End-to-End Test Plan

## Test A — Clear Spill

Expected:

- High detection
- Low/medium look-alike risk
- Good temporal consistency
- Source hypotheses
- Candidate ranking

## Test B — Look-Alike

Expected:

- Detection uncertainty
- High look-alike risk
- No aggressive attribution

## Test C — AIS Gap

Expected:

- AIS evidence unavailable
- No assumption of vessel absence
- Reduced evidence strength

## Test D — AIS/Satellite Conflict

Expected:

- Cross-source inconsistency
- No automatic spoofing accusation
- Human investigation required

## Test E — Multiple Plausible Sources

Expected:

- H1 → High
- H2 → Medium
- H3 → Low

## Test F — Insufficient Data

Expected:

> INSUFFICIENT EVIDENCE

---

# 25. Technology Stack

## Frontend

- React
- TypeScript
- MapLibre GL / OpenLayers
- Charting library

## Backend

- Python
- FastAPI
- PostgreSQL
- PostGIS

## Machine Learning

- PyTorch
- U-Net / U-Net++
- SegFormer if required
- NumPy
- OpenCV

## Geospatial

- GDAL
- rasterio
- GeoPandas
- Shapely
- PostGIS

## Satellite

- Sentinel-1
- Sentinel-2 where useful

## Environmental

- Copernicus
- ECMWF
- NOAA

## Drift

- OpenDrift
- Lagrangian particle modelling

## AIS

- Historical AIS datasets
- Accessible AIS APIs/data sources where legally and technically appropriate

## Deployment

- Docker
- Local/server deployment

---

# 26. SIH Implementation Priority

## Priority 1 — MUST WORK

1. Sentinel-1 preprocessing
2. Spill detection
3. Look-alike analysis
4. Spill characterization
5. Multi-temporal analysis
6. Environmental data integration
7. Drift modelling
8. Source hypotheses
9. AIS correlation
10. Evidence fusion
11. Candidate ranking
12. Evidence explanation
13. Investigator dashboard

## Priority 2 — STRONGLY DESIRABLE

14. Cross-source inconsistency
15. No-attribution outcome
16. Dynamic ranking
17. Historical replay
18. Oil-Spill Time Machine

## Priority 3 — IF TIME PERMITS

19. Evidence Graph UI
20. Forensic Vessel Reconstruction
21. Competing hypothesis visualization
22. Forward forecasting
23. Impact assessment
24. Forecast correction
25. Contextual vessel behaviour

---

# 27. Explicitly Out of SIH Scope

Do not attempt to build:

- Global real-time AIS infrastructure
- A new ocean circulation model
- A new deep-learning drift model
- A perfect AIS spoofing detector
- Fully autonomous legal attribution
- A huge historical attribution dataset
- Fully calibrated causal attribution probability
- Global operational satellite-processing infrastructure

---

# 28. Final PPT Feature Names

Use these **8 major features** on the main feature slide:

1. **AI Oil-Spill Detection & Look-Alike Analysis**
2. **Multi-Temporal Spill Reconstruction & Characterization**
3. **Environmental Drift & Backward Hindcasting → Source Hypotheses**
4. **Historical AIS Vessel Reconstruction & Correlation**
5. **Cross-Source Consistency & Evidence Conflict Detection**
6. **Evidence Fusion & Dynamic Hypothesis Ranking**
7. **Forensic Investigation Graph & Explainable Evidence Chain**
8. **Forward Forecasting, Impact Assessment & Historical Replay**

---

# 29. Final Novelty Position

OilTrace AI should be presented as:

> **System-level innovation, not algorithmic novelty.**

The individual building blocks are established.

The proposed contribution is the investigation layer that connects them while explicitly handling:

- Multiple hypotheses
- Supporting evidence
- Contradictory evidence
- Missing evidence
- Data adequacy
- Uncertainty
- Human review

The central idea is:

> **Do not force incomplete maritime evidence into a single answer. Preserve competing explanations and show investigators why each candidate is or is not compatible with the available evidence.**

---

# 30. Core Principle

Satellite ≠ Absolute Truth

AIS ≠ Absolute Truth

Drift ≠ Absolute Truth

AI Score ≠ Guilt

↓

MULTI-SOURCE EVIDENCE

↓

SUPPORT + CONTRADICTION

+

DATA QUALITY

+

UNCERTAINTY

+

COMPETING HYPOTHESES

↓

HUMAN INVESTIGATION

> **OilTrace AI does not accuse. It helps investigators investigate.**

---

# 31. Final Feature Freeze

The final system contains **8 major features**:

1. AI Oil-Spill Detection & Look-Alike Analysis
2. Multi-Temporal Spill Reconstruction & Characterization
3. Environmental Drift & Backward Hindcasting → Source Hypotheses
4. Historical AIS Vessel Reconstruction & Correlation
5. Cross-Source Consistency & Evidence Conflict Detection
6. Evidence Fusion & Dynamic Hypothesis Ranking
7. Forensic Investigation Graph & Explainable Evidence Chain
8. Forward Forecasting, Impact Assessment & Historical Replay

**No additional major features should be added unless required by the SIH problem statement.**
