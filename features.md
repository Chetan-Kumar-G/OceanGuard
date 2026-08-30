# OilTrace AI --- Final Features Specification

> **SIH Problem Statement 26143**\
> **AI-Assisted Satellite Oil-Spill Detection, Reconstruction & Vessel
> Investigation**
>
> **Status:** Final feature freeze for SIH prototype planning.
>
> **Core positioning:** OilTrace AI is an AI-assisted investigation and
> decision-support system. It detects and characterizes probable oil
> spills, reconstructs their observed evolution, estimates physically
> plausible source hypotheses using environmental drift modelling,
> correlates historical vessel activity, checks cross-source
> consistency, and produces transparent candidate assessments for human
> investigators.
>
> **Critical limitation:** The system does **not** automatically prove
> the responsible vessel, determine legal responsibility, prove AIS
> spoofing, or guarantee the exact physical source of a spill.

------------------------------------------------------------------------

## 1. Final Feature Set

OilTrace AI is intentionally limited to **8 major features**. Technical
sub-capabilities are grouped under these features rather than being
presented as separate features.

  --------------------------------------------------------------------------------
  \#             Feature            Classification   Importance     SIH
  -------------- ------------------ ---------------- -------------- --------------
  1              AI Oil-Spill       Baseline +       Critical       Yes
                 Detection &        Improvement                     
                 Look-Alike                                         
                 Analysis                                           

  2              Multi-Temporal     Improvement      Critical       Yes
                 Spill                                              
                 Reconstruction &                                   
                 Characterization                                   

  3              Environmental      Existing +       Critical       Yes
                 Drift & Backward   Improvement                     
                 Hindcasting →                                      
                 Source Hypotheses                                  

  4              Historical AIS     Baseline /       Critical       Yes
                 Vessel             Existing                        
                 Reconstruction &                                   
                 Correlation                                        

  5              Cross-Source       Proposed         High           Yes
                 Consistency &      Differentiator                  
                 Evidence Conflict                                  
                 Detection                                          

  6              Evidence Fusion &  Proposed         Critical       Yes
                 Dynamic Hypothesis System-Level                    
                 Ranking            Differentiator                  

  7              Forensic           Proposed         High           Yes
                 Investigation      Workflow                        
                 Graph &            Differentiator                  
                 Explainable                                        
                 Evidence Chain                                     

  8              Forward            Existing +       High           If time /
                 Forecasting,       Improvement +                   validation
                 Impact Assessment  Validation                      
                 & Historical                                       
                 Replay                                             
  --------------------------------------------------------------------------------

### Classification definitions

  -----------------------------------------------------------------------
  Classification                      Meaning
  ----------------------------------- -----------------------------------
  **Baseline**                        Required or expected capability for
                                      a credible solution.

  **Existing**                        Established technology/research
                                      adopted by the system.

  **Improvement**                     Existing technology used in a more
                                      useful or robust workflow.

  **Proposed Differentiator**         Our proposed system-level
                                      contribution; not a claim that the
                                      underlying algorithms are newly
                                      invented.

  **Validation**                      Capability primarily used to test
                                      and demonstrate reliability.

  **Future**                          Potential research/deployment
                                      direction outside the SIH MVP.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 2. System Architecture

``` text
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
Forensic Investigation
        ↓
Human Investigator
        ↓
Investigate / Reject / Insufficient Evidence
```

Response layer:

``` text
Current Observed Spill
        ↓
Forward Drift Forecast
        ↓
Potential Impact Areas
        ↓
Response Prioritization
```

------------------------------------------------------------------------

# FEATURE 1 --- AI Oil-Spill Detection & Look-Alike Analysis

**Classification:** Baseline + Improvement\
**Importance:** Critical\
**SIH MVP:** Yes\
**Feasibility:** High\
**Technical Depth:** High\
**Algorithmic Novelty:** Low

## Purpose

Detect probable oil-spill regions from satellite imagery and reduce
false detections caused by oil-spill look-alikes.

``` text
Satellite Image
      ↓
SAR Preprocessing
      ↓
Segmentation
      ↓
Probable Spill Mask
      ↓
Look-Alike Assessment
      ↓
Spill Polygon
```

## Primary satellite source

### Sentinel-1 SAR

Initial focus:

-   VV polarization
-   VH where useful

Optional secondary source:

-   Sentinel-2 optical imagery when cloud-free and suitable.

## SAR preprocessing

Potential pipeline:

``` text
Raw Sentinel-1
      ↓
Radiometric Calibration
      ↓
Noise / Speckle Handling
      ↓
Geometric Correction
      ↓
Normalization
      ↓
AOI Extraction
      ↓
ML Input
```

Potential technologies:

-   GDAL
-   rasterio
-   NumPy
-   OpenCV
-   GeoPandas
-   SNAP where appropriate

## Segmentation

Recommended SIH starting point:

-   U-Net
-   U-Net++
-   DeepLabV3+
-   SegFormer as an alternative

The priority is reliable segmentation and feasible implementation, not
inventing a new neural-network architecture.

## Dataset

### Krestenitis et al.

The dataset contains Sentinel-1 SAR imagery with classes including:

-   sea
-   oil spill
-   look-alike
-   ship
-   land

Reference:

https://doi.org/10.3390/rs11151762

## Look-alike problem

A dark SAR signature is not automatically oil.

Potential look-alikes include:

-   low-wind areas
-   biogenic films
-   internal waves
-   rain-related effects
-   sea-state effects
-   other dark formations

Therefore:

``` text
Dark SAR Region
      ↓
Possible Oil + Possible Look-Alike
      ↓
Context + Model + Temporal Evidence
      ↓
Probable Oil-Spill Assessment
```

## Output

-   probable spill mask
-   spill polygon
-   estimated area
-   detection confidence
-   look-alike risk
-   data-quality indicator

Example:

``` text
Oil-Spill Detection: HIGH
Look-Alike Risk: MEDIUM
Detection Confidence: HIGH
```

## Important limitation

Do not say:

> "This dark patch is definitely oil."

Use:

> "The observed SAR signature is consistent with a probable oil spill."

## Evaluation

-   IoU
-   Dice/F1
-   Precision
-   Recall
-   false-positive rate
-   false-negative rate

## Honest novelty assessment

Oil-spill segmentation using Sentinel-1 is established research.

**We do not claim a novel segmentation architecture.**

The improvement is its integration with look-alike handling and the
downstream investigation workflow.

------------------------------------------------------------------------

# FEATURE 2 --- Multi-Temporal Spill Reconstruction & Characterization

**Classification:** Improvement\
**Importance:** Critical\
**SIH MVP:** Yes\
**Feasibility:** High\
**Technical Depth:** High\
**Novelty:** Moderate at system level

## Purpose

A single satellite image provides a snapshot. Multiple observations
allow reconstruction of how the observed spill changed over time.

``` text
T1 → Spill Geometry
T2 → Spill Geometry
T3 → Spill Geometry
      ↓
Temporal Comparison
      ↓
Observed Spill Evolution
```

## Characterization

For each observation calculate:

-   area
-   perimeter
-   centroid
-   bounding box
-   dimensions
-   shape
-   geographic coordinates
-   timestamp
-   polygon

## Temporal analysis

Track:

-   area change
-   centroid displacement
-   shape change
-   expansion
-   contraction
-   persistence
-   disappearance
-   observation gaps

Example:

``` text
T1 → 8 km²
T2 → 14 km²
T3 → 21 km²
```

## Spill age / time estimation

Where sufficient observations exist, estimate a **time window** rather
than an exact age.

Do not claim:

> "The spill is exactly 6 hours old."

Use:

> "The spill was first observed within the available satellite
> observation window, with a source-compatible time interval estimated
> using temporal and physical evidence."

## Oil-Spill Time Machine

Optional but valuable interface:

``` text
PAST ←──────── NOW ────────→ FUTURE
```

It can display:

-   historical observations
-   current detected state
-   modelled/reconstructed states
-   forecast states

Clearly distinguish:

``` text
OBSERVED
MODELLED
FORECAST
```

## Limitation

Sentinel-1 provides discrete acquisitions rather than continuous video.

Therefore:

> Multi-temporal reconstruction is not continuous real-time tracking.

## Technologies

-   rasterio
-   GeoPandas
-   Shapely
-   PostGIS
-   image registration
-   temporal GIS
-   satellite metadata

## Validation

Compare:

-   observed area
-   observed centroid
-   polygon overlap
-   temporal displacement

## Honest novelty assessment

Temporal analysis is established research.

The proposed improvement is using temporal evidence as an input to
source-hypothesis and vessel investigation.

------------------------------------------------------------------------

# FEATURE 3 --- Environmental Drift & Backward Hindcasting → Source Hypotheses

**Classification:** Existing + Improvement\
**Importance:** Critical\
**SIH MVP:** Yes\
**Feasibility:** Medium-High\
**Technical Depth:** Very High\
**Algorithmic Novelty:** Low\
**System-Level Value:** High

## Purpose

Estimate how an observed slick could have moved under environmental
conditions and generate **plausible source hypotheses**.

### Critical principle

> **Backtracking does not directly identify the exact source.**

## Environmental inputs

Potential inputs:

-   wind speed
-   wind direction
-   ocean currents
-   waves
-   Stokes drift

Potential sources:

-   Copernicus
-   ECMWF
-   NOAA
-   other suitable oceanographic products

## Drift modelling

Recommended established framework:

**OpenDrift**

Concept:

``` text
Initial / Observed Slick
        +
Wind
        +
Ocean Currents
        ↓
Particle Simulation
        ↓
Possible Trajectory Distribution
```

## Forward simulation

``` text
Possible Source
      ↓
Environmental Conditions
      ↓
Particle Movement
      ↓
Possible Future Slick Location
```

## Backward hindcasting

``` text
Observed Slick
      ↓
Environmental Conditions
      ↓
Backward Particle Trajectories
      ↓
Multiple Possible Source Regions
```

## Source hypotheses

Example:

``` text
Source Hypothesis H1
Region: A
Time Window: X–Y
Compatibility: HIGH

Source Hypothesis H2
Region: B
Time Window: X–Y
Compatibility: MEDIUM

Source Hypothesis H3
Region: C
Compatibility: LOW
```

## Why multiple hypotheses?

The inverse problem may not have a unique solution.

Different:

-   locations
-   times
-   environmental assumptions

may produce similar observed slick patterns.

Therefore the system preserves alternative explanations.

## Correct terminology

Do not use:

-   Exact spill origin
-   Source identified
-   Spill started at coordinate X

Use:

-   Plausible source region
-   Source hypothesis
-   Physically compatible source region
-   Source-compatible time window

## Uncertainty

Potential sources:

-   environmental forcing errors
-   current/wind resolution
-   model assumptions
-   unresolved physical processes
-   satellite observation uncertainty

Represent a region/ensemble rather than one exact line where possible.

## Technologies

-   OpenDrift
-   Lagrangian particle modelling
-   Python
-   NumPy
-   xarray
-   NetCDF
-   Copernicus/ECMWF/NOAA datasets

Reference:

https://opendrift.github.io/

## Honest novelty assessment

Drift and backtracking are established technologies.

The proposed improvement is connecting:

``` text
Satellite
→ Temporal Reconstruction
→ Source Hypotheses
→ AIS
→ Evidence Fusion
```

instead of treating backtracking as the final answer.

------------------------------------------------------------------------

# FEATURE 4 --- Historical AIS Vessel Reconstruction & Correlation

**Classification:** Baseline / Existing\
**Importance:** Critical\
**SIH MVP:** Yes\
**Feasibility:** High\
**Technical Depth:** High\
**Novelty:** Low

## Purpose

Identify vessels whose historical movements are compatible with
generated source hypotheses.

``` text
Source Hypothesis
      +
Source-Compatible Time Window
      ↓
Historical AIS
      ↓
Relevant Vessel Tracks
```

## AIS fields

Potential fields:

-   MMSI
-   timestamp
-   latitude
-   longitude
-   speed over ground
-   course over ground
-   heading
-   vessel type
-   vessel dimensions

## Candidate filtering

### Spatial filtering

Was the vessel near the source hypothesis?

### Temporal filtering

Was it present during the source-compatible time window?

### Trajectory filtering

Did its historical movement intersect the relevant region?

Example:

``` text
47 AIS vessels
      ↓
Spatial filtering
      ↓
12 vessels
      ↓
Temporal filtering
      ↓
7 vessels
      ↓
Trajectory compatibility
      ↓
5 candidates
```

## Critical principle

AIS is:

> **Evidence, not ground truth.**

AIS can contain:

-   gaps
-   noise
-   delayed records
-   transmission failures
-   manipulated positions
-   incomplete coverage

## Commercial-tool challenge

Commercial maritime-intelligence systems already provide sophisticated:

-   AIS tracking
-   vessel analytics
-   vessel behaviour
-   satellite/AIS fusion
-   historical vessel intelligence
-   maritime risk intelligence

Therefore:

> **AIS tracking is not our innovation.**

## Our position

Existing AIS services/data can be treated as inputs.

Our proposed contribution occurs in the investigation layer connecting:

``` text
Spill
+
Source Hypotheses
+
AIS
+
Drift
+
Temporal Evidence
+
Contradictions
```

------------------------------------------------------------------------

# FEATURE 5 --- Cross-Source Consistency & Evidence Conflict Detection

**Classification:** Proposed Differentiator\
**Importance:** High\
**SIH MVP:** Yes\
**Feasibility:** Medium-High\
**Technical Depth:** Very High\
**Novelty:** Moderate system-level

## Purpose

Check whether independent evidence sources agree or conflict.

Sources:

-   satellite observations
-   temporal reconstruction
-   AIS
-   drift
-   environmental data
-   vessel trajectory

## Example

``` text
AIS:
Vessel reported at Location A

Satellite:
Vessel-like observation near Location B

Result:
AIS–Satellite inconsistency
```

## Conflict types

### Spatial conflict

AIS location does not agree with observed satellite position.

### Temporal conflict

Vessel was not present during the relevant source-compatible time.

### Physical conflict

Vessel trajectory is poorly compatible with the drift-derived source
hypothesis.

### Data conflict

Important observations are missing or inconsistent.

## AIS gaps

If AIS disappears:

### Wrong

> "Vessel was not there."

### Correct

> "AIS evidence unavailable during this interval."

## AIS spoofing

Do not claim:

> "AIS spoofing detected."

Use:

> "AIS--satellite inconsistency detected. Possible explanations include
> transmission gaps, timing mismatch, data errors or deliberate
> manipulation. Further investigation is required."

## Why this matters

The system does not blindly trust one source.

It asks:

> **Do the available sources tell a consistent story?**

## Honest novelty claim

Do not claim:

> "Nobody has ever performed AIS/satellite consistency analysis."

The defensible claim is:

> **"OilTrace AI explicitly represents cross-source conflicts inside the
> oil-spill source-hypothesis workflow and propagates those conflicts
> into the evidence assessment."**

------------------------------------------------------------------------

# FEATURE 6 --- Multi-Source Evidence Fusion & Dynamic Hypothesis Ranking

**Classification:** Proposed System-Level Differentiator\
**Importance:** Critical\
**SIH MVP:** Yes\
**Feasibility:** High\
**Technical Depth:** Very High\
**Novelty:** Moderate-High at system level

## Purpose

Combine evidence generated by Features 1--5 into transparent
candidate/hypothesis assessments.

This is the **central investigation layer**.

## Evidence inputs

### Satellite

-   spill detection
-   spill geometry
-   look-alike risk
-   detection confidence

### Temporal

-   observed evolution
-   displacement
-   persistence
-   observation gaps

### Environmental

-   wind
-   currents
-   environmental data quality

### Drift

-   source hypothesis
-   trajectory compatibility
-   uncertainty envelope

### AIS

-   vessel position
-   trajectory
-   timing
-   AIS completeness

### Consistency

-   supporting evidence
-   contradictions
-   missing evidence

## Conceptual model

``` text
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
        -
Contradictory Evidence
        ↓
Evidence Compatibility
```

## Prototype scoring

Possible initial weighting:

  Evidence                         Example Weight
  ------------------------------ ----------------
  Spatial compatibility                       25%
  Temporal compatibility                      20%
  Drift compatibility                         25%
  AIS trajectory compatibility                15%
  Cross-source consistency                    10%
  Data quality                                 5%

### Important

These weights are **prototype assumptions**, not scientifically
established probabilities.

For production use, weights should be validated/calibrated using
appropriate historical cases and domain expertise.

## Candidate ranking

Example:

``` text
Candidate / Hypothesis A
Compatibility: HIGH

Candidate / Hypothesis B
Compatibility: MEDIUM

Candidate / Hypothesis C
Compatibility: LOW
```

## Dynamic ranking

``` text
Initial Evidence
      ↓
Ranking
      ↓
New Satellite Observation
      ↓
New Evidence
      ↓
Recalculate
      ↓
Updated Ranking
```

## No-sufficient-evidence outcome

The system must support:

> **Insufficient evidence for reliable attribution.**

Possible reasons:

-   high look-alike risk
-   insufficient satellite observations
-   high source-region uncertainty
-   major AIS gaps
-   conflicting evidence
-   insufficient historical evidence

## Critical terminology

Do not say:

> Probability that Vessel A is guilty.

Do not say:

> AI proves Vessel A caused the spill.

Use:

-   Evidence compatibility
-   Investigation priority
-   Candidate hypothesis
-   Supporting evidence
-   Contradictory evidence
-   Insufficient evidence

## Evidence dependency

Not all evidence is independent.

Example:

``` text
Satellite
   ↓
Source Region
   ↓
AIS Candidate
```

The AIS candidate's relevance is partly derived from the satellite
result.

Therefore avoid treating correlated signals as independent proofs.

## Honest novelty assessment

Individual evidence sources are not novel.

The proposed contribution is:

> **A transparent spill-centric evidence-fusion layer that preserves
> supporting, contradictory and missing evidence while ranking competing
> source/vessel hypotheses instead of forcing a single attribution.**

------------------------------------------------------------------------

# FEATURE 7 --- Forensic Investigation Graph & Explainable Evidence Chain

**Classification:** Proposed Workflow Differentiator\
**Importance:** High\
**SIH MVP:** Yes for core explanation; advanced graph UI optional\
**Feasibility:** Medium-High\
**Technical Depth:** High\
**Novelty:** Moderate system-level

## Purpose

Provide investigators with an understandable chain showing:

> **Why did the system rank this candidate?**

## Evidence chain

``` text
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
```

## Forensic vessel reconstruction

When an investigator selects a candidate:

``` text
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
```

The investigator can inspect the complete evidence trail.

## Evidence graph

### Nodes

-   incident
-   satellite observation
-   spill polygon
-   source hypothesis
-   environmental condition
-   vessel
-   AIS track
-   evidence item
-   contradiction
-   investigator decision

### Relationships

-   supports
-   contradicts
-   spatially compatible
-   temporally compatible
-   derived from
-   uncertain

Example:

``` text
                    INCIDENT
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
   SATELLITE          DRIFT            AIS
       │               │               │
       ↓               ↓               ↓
   SPILL MASK       SOURCE H1       VESSEL A
       │               │               │
       └───────────────┼───────────────┘
                       ↓
                EVIDENCE FUSION
                       ↓
                 CANDIDATE A
                       ↓
                HUMAN REVIEW
```

## Competing hypotheses

``` text
H1:
Vessel A + Source Region X

H2:
Vessel B + Source Region Y

H3:
Unknown source + Region Z
```

Possible outcomes:

``` text
H1 → High compatibility
H2 → Medium compatibility
H3 → Insufficient evidence
```

## Correction / audit mechanism

If the system incorrectly ranks a vessel:

``` text
AI Assessment
      ↓
Human Review
      ↓
Reject / Uncertain
      ↓
Reason Recorded
      ↓
Audit Trail
```

Store:

-   original result
-   evidence used
-   model version
-   investigator decision
-   correction reason
-   timestamp

Do not silently overwrite historical results.

## Human-in-the-loop

The AI produces:

> Candidate + evidence

The investigator decides:

-   investigate
-   reject
-   uncertain

The system does not make the final legal or enforcement decision.

## Honest novelty assessment

Evidence graphs and explainability are not new technologies.

The proposed differentiation is the **specific spill-centric evidence
representation** connecting:

``` text
Satellite
→ Spill
→ Source Hypothesis
→ Vessel
→ Contradiction
→ Candidate
→ Investigator
```

------------------------------------------------------------------------

# FEATURE 8 --- Forward Forecasting, Impact Assessment & Historical Replay

**Classification:** Existing + Improvement + Validation\
**Importance:** High\
**SIH MVP:** Optional / validation critical\
**Feasibility:** Medium-High\
**Technical Depth:** High

## 8.1 Forward spill forecasting

Use the current observed spill state and environmental forcing to
estimate possible future movement.

``` text
Current Spill
      +
Wind
      +
Currents
      ↓
Drift Model
      ↓
12h / 24h / 48h
Possible Movement
```

## 8.2 Forecast output

Show:

-   predicted trajectory
-   predicted spread
-   uncertainty region
-   potential future locations

Clearly distinguish:

``` text
OBSERVED
MODELLED
FORECAST
```

## 8.3 Forecast correction

When a new satellite observation arrives:

``` text
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
```

A full operational data-assimilation system is beyond SIH scope.

## 8.4 Impact assessment

Potential overlay layers:

-   coastline
-   protected areas
-   fisheries
-   ports
-   environmentally sensitive zones

Output:

> Potentially affected / priority areas

Not:

> Guaranteed contamination.

## 8.5 Historical replay

Historical events can be replayed through the complete pipeline:

``` text
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
```

## 8.6 Why historical replay matters

It allows evaluation of the **end-to-end system**, not only individual
models.

## 8.7 Ground-truth challenge

Detection validation may use:

``` text
Satellite
+
Oil / Look-Alike Labels
```

Attribution validation requires much more:

``` text
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
```

Large public datasets containing all of these fields with confirmed
responsible vessels are difficult to obtain.

Therefore:

> **Do not claim a massive historical attribution dataset.**

Use a small curated validation set where possible.

Classify cases as:

``` text
CONFIRMED
PROBABLE
UNKNOWN
```

Only confirmed cases should support strong attribution-validation
claims.

------------------------------------------------------------------------

# 3. Cross-Cutting Data Quality & Uncertainty

Data quality and uncertainty are **not separate major features**. They
affect every stage.

## Satellite quality

Consider:

-   image quality
-   observation gap
-   look-alike risk
-   geographic coverage

## AIS quality

Consider:

-   coverage
-   missing intervals
-   suspicious jumps
-   reporting gaps

## Environmental quality

Consider:

-   spatial resolution
-   temporal resolution
-   missing data
-   forcing uncertainty

## Drift uncertainty

Consider:

-   environmental forcing uncertainty
-   particle spread
-   model assumptions
-   source-region size

------------------------------------------------------------------------

# 4. Model Uncertainty vs Data Adequacy

These are different concepts.

## Model uncertainty

The model has relevant information but remains uncertain.

Example:

> Oil vs look-alike is ambiguous.

## Data inadequacy

Available data is insufficient or poorly representative.

Example:

> The current geographic/environmental condition is poorly represented
> in the training data.

## SIH implementation

Use qualitative states:

``` text
Data Adequacy:
HIGH
MEDIUM
LIMITED
UNKNOWN
```

Avoid fake precision such as:

``` text
Data Adequacy = 63.27%
```

unless a scientifically justified methodology is implemented.

------------------------------------------------------------------------

# 5. Adversarial & Failure Cases

  -----------------------------------------------------------------------
  Failure                 Potential Result        System Response
  ----------------------- ----------------------- -----------------------
  SAR look-alike          False spill             Look-alike analysis

  Poor image quality      Low confidence          Quality warning

  Satellite revisit gap   Missing event stage     Observation-gap
                                                  indicator

  AIS gap                 Missing vessel evidence "AIS unavailable"

  AIS manipulation        Incorrect declared      Cross-source
                          location                inconsistency

  Drift error             Wrong source hypothesis Uncertainty envelope

  Multiple plausible      Ambiguous attribution   Competing hypotheses
  sources                                         

  Wrong candidate ranking Potential false         Human review
                          investigation           

  Insufficient evidence   Unreliable attribution  No-attribution outcome

  Dataset bias            Poor generalization     Data adequacy warning
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 6. Maritime-Domain Assumptions

The system should not invent maritime rules and present them as
universal truth.

For the SIH prototype:

-   use objective spatial/temporal signals
-   use literature-supported indicators
-   make rules transparent
-   avoid declaring behaviour illegal
-   avoid treating anomalies as proof of wrongdoing

For operational deployment:

> Maritime-domain experts should validate behavioural assumptions,
> thresholds and interpretation.

------------------------------------------------------------------------

# 7. Commercial-System Positioning

Commercial maritime-intelligence systems already provide capabilities
such as:

-   AIS tracking
-   vessel analytics
-   historical vessel reconstruction
-   behavioural analytics
-   satellite/AIS fusion
-   maritime risk intelligence
-   oil-spill-related intelligence

Therefore OilTrace AI does **not** claim:

> "We invented vessel intelligence."

## OilTrace AI position

The system is designed around a:

> **Satellite-first oil-spill investigation workflow.**

``` text
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
```

Existing AIS/intelligence sources can potentially be integrated as data
providers in future deployment.

------------------------------------------------------------------------

# 8. What Is Existing?

The following are established technologies/research areas:

-   Sentinel-1 SAR
-   SAR preprocessing
-   oil-spill segmentation
-   U-Net
-   look-alike classification research
-   spill geometry
-   temporal satellite analysis
-   AIS tracking
-   vessel trajectory analysis
-   drift modelling
-   Lagrangian particles
-   hindcasting
-   forecasting
-   GIS
-   evidence graphs
-   explainability concepts

We do **not** claim to have invented these.

------------------------------------------------------------------------

# 9. What Is Our Proposed Contribution?

The strongest system-level contributions are:

## 9.1 Hypothesis-Based Source Investigation

Instead of:

``` text
Backtracking
↓
One Source
```

use:

``` text
Backtracking
↓
Multiple Source Hypotheses
↓
Evidence Evaluation
```

## 9.2 Cross-Source Conflict Representation

Explicitly represent:

-   agreement
-   contradiction
-   missing evidence

between:

-   satellite
-   AIS
-   drift
-   temporal observations

## 9.3 Evidence Fusion

Combine evidence with:

-   quality
-   uncertainty
-   contradictions
-   dependencies

rather than treating every signal as independent proof.

## 9.4 Dynamic Hypothesis Ranking

New observations can modify candidate/hypothesis rankings.

## 9.5 No-Sufficient-Evidence Outcome

The system can explicitly conclude:

> Insufficient evidence for reliable attribution.

## 9.6 Explainable Investigation

Every candidate should have:

``` text
Supporting Evidence
+
Contradictory Evidence
+
Data Limitations
+
Reason for Ranking
```

------------------------------------------------------------------------

# 10. Claims We Can Defend

-   Sentinel-1 SAR can be used for probable oil-spill detection.
-   Multiple satellite observations can reconstruct observed spill
    evolution.
-   Environmental drift models can generate physically plausible
    movement and source hypotheses.
-   Historical AIS can be correlated with source-compatible regions and
    time windows.
-   Cross-source comparison can expose evidence inconsistencies.
-   Multiple evidence sources can be organized into transparent
    candidate assessments.
-   A human investigator can inspect supporting and contradictory
    evidence behind a candidate.
-   The system can refuse attribution when evidence is insufficient.

------------------------------------------------------------------------

# 11. Claims We Must NOT Make

Do not claim:

-   The system identifies the exact spill source.
-   The system identifies the guilty vessel.
-   The system proves AIS spoofing.
-   A nearby vessel is responsible.
-   AIS absence proves vessel absence.
-   Drift gives the exact physical trajectory.
-   Every SAR dark patch is oil.
-   Confidence is the probability of guilt.
-   Evidence sources are independent proofs.
-   The system provides automatic legal evidence.
-   The system replaces maritime authorities.
-   Our segmentation architecture is novel.
-   Our drift algorithm is novel.
-   Our AIS tracking is novel.
-   Commercial maritime-intelligence platforms do not already perform
    related capabilities.

------------------------------------------------------------------------

# 12. Final SIH Implementation Priority

## Priority 1 --- Must Work

``` text
1. Sentinel-1 preprocessing
2. Spill detection
3. Look-alike analysis
4. Spill characterization
5. Multi-temporal analysis
6. Environmental data
7. Drift modelling
8. Plausible source hypotheses
9. AIS correlation
10. Evidence fusion
11. Candidate ranking
12. Evidence explanation
13. Investigator dashboard
```

## Priority 2 --- Strongly Desirable

``` text
14. Cross-source inconsistency
15. No-attribution outcome
16. Dynamic ranking
17. Historical replay
18. Oil-Spill Time Machine
```

## Priority 3 --- If Time Permits

``` text
19. Evidence Graph UI
20. Forensic Vessel Reconstruction
21. Competing hypothesis visualization
22. Forward forecasting
23. Impact assessment
24. Forecast correction
25. Contextual vessel behaviour
```

------------------------------------------------------------------------

# 13. Explicitly Out of SIH Scope

Do not attempt to build:

-   global real-time AIS infrastructure
-   a new ocean circulation model
-   a new deep-learning drift model
-   a perfect AIS spoofing detector
-   fully autonomous legal attribution
-   a huge historical attribution dataset
-   fully calibrated causal attribution probability
-   global operational satellite processing infrastructure

------------------------------------------------------------------------

# 14. Final User Workflow

## Step 1 --- Spill Detection

Satellite imagery enters the system.

AI detects a probable oil spill.

## Step 2 --- Look-Alike Assessment

The system assesses whether the signature could plausibly be a
look-alike.

## Step 3 --- Characterization

Calculate:

-   area
-   location
-   geometry
-   timestamp

## Step 4 --- Temporal Reconstruction

Compare previous/subsequent satellite observations.

## Step 5 --- Environmental Analysis

Load:

-   wind
-   currents
-   other suitable environmental data

## Step 6 --- Backward Hindcasting

Generate:

> Multiple plausible source hypotheses.

## Step 7 --- AIS Correlation

Search historical vessel activity around:

-   source hypotheses
-   source-compatible time windows

## Step 8 --- Cross-Source Consistency

Check:

``` text
Satellite
vs
AIS
vs
Drift
vs
Timeline
```

## Step 9 --- Evidence Fusion

Combine:

-   supporting evidence
-   contradictions
-   data quality
-   uncertainty

## Step 10 --- Candidate Ranking

Produce:

``` text
Candidate A → HIGH
Candidate B → MEDIUM
Candidate C → LOW
Unknown → POSSIBLE
```

## Step 11 --- Explain

Show:

-   why the candidate ranked highly
-   supporting evidence
-   contradictory evidence
-   missing evidence
-   data limitations

## Step 12 --- Human Decision

Investigator:

-   investigates
-   rejects
-   marks uncertain

------------------------------------------------------------------------

# 15. Example Investigation Output

``` text
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
```

------------------------------------------------------------------------

# 16. Technology Stack

## Frontend

-   React
-   TypeScript
-   MapLibre GL / OpenLayers
-   charting library

## Backend

-   Python
-   FastAPI
-   PostgreSQL
-   PostGIS

## Machine Learning

-   PyTorch
-   U-Net / U-Net++
-   SegFormer if required
-   NumPy
-   OpenCV

## Geospatial

-   GDAL
-   rasterio
-   GeoPandas
-   Shapely
-   PostGIS

## Satellite

-   Sentinel-1
-   Sentinel-2 where useful

## Environmental

-   Copernicus
-   ECMWF
-   NOAA

## Drift

-   OpenDrift
-   Lagrangian particle modelling

## AIS

-   historical AIS datasets
-   accessible AIS APIs/data sources where legally and technically
    appropriate

## Deployment

-   Docker
-   local/server deployment

------------------------------------------------------------------------

# 17. Final SIH Evaluation Strategy

  Evaluation Category         Max                 Target
  ---------------------- -------- ----------------------
  Innovation / Novelty         10                   7--8
  Feasibility                  10                   8--9
  Technical Depth              10                      9
  Social Impact                10                   8--9
  Prototype                     5                   4--5
  PPT                           5                   4--5
  **Total**                **50**   **40--45 potential**

The prototype score is highly dependent on execution.

A working end-to-end investigation story is more valuable than adding
additional theoretical features.

------------------------------------------------------------------------

# 18. Final PPT Feature Names

Use only these 8 names on the main feature slide:

### 01 --- AI Oil-Spill Detection & Look-Alike Analysis

### 02 --- Multi-Temporal Spill Reconstruction & Characterization

### 03 --- Environmental Drift & Backward Hindcasting → Source Hypotheses

### 04 --- Historical AIS Vessel Reconstruction & Correlation

### 05 --- Cross-Source Consistency & Evidence Conflict Detection

### 06 --- Evidence Fusion & Dynamic Hypothesis Ranking

### 07 --- Forensic Investigation Graph & Explainable Evidence Chain

### 08 --- Forward Forecasting, Impact Assessment & Historical Replay

------------------------------------------------------------------------

# 19. One-Line Product Description

> **OilTrace AI detects and reconstructs probable oil spills, generates
> physically plausible source hypotheses, correlates historical vessel
> activity, exposes conflicting evidence, and produces transparent
> candidate assessments for human investigation.**

------------------------------------------------------------------------

# 20. Final Novelty Position

The project should be presented as:

> **System-level innovation, not algorithmic novelty.**

The individual building blocks are established.

The proposed contribution is the investigation layer that connects them
while explicitly handling:

``` text
Multiple Hypotheses
+
Supporting Evidence
+
Contradictory Evidence
+
Missing Evidence
+
Data Adequacy
+
Uncertainty
+
Human Review
```

The central idea is:

> **Do not force incomplete maritime evidence into a single answer.
> Preserve competing explanations and show investigators why each
> candidate is or is not compatible with the available evidence.**

------------------------------------------------------------------------

# 21. Final Architecture

``` text
                         OILTRACE AI
                              │
                              ↓
                    ┌───────────────────┐
                    │ SATELLITE / SAR   │
                    └─────────┬─────────┘
                              ↓
                    ┌───────────────────┐
                    │ SPILL DETECTION   │
                    │ + LOOK-ALIKE      │
                    └─────────┬─────────┘
                              ↓
                    ┌───────────────────┐
                    │ CHARACTERIZATION  │
                    │ + TEMPORAL        │
                    │ RECONSTRUCTION    │
                    └─────────┬─────────┘
                              ↓
               ┌──────────────┴──────────────┐
               ↓                             ↓
       ┌────────────────┐             ┌────────────────┐
       │ WIND / CURRENT │             │ HISTORICAL AIS │
       │ ENVIRONMENT    │             │ + VESSEL DATA  │
       └───────┬────────┘             └───────┬────────┘
               ↓                             ↓
       ┌────────────────┐             ┌────────────────┐
       │ DRIFT /        │             │ VESSEL         │
       │ HINDCASTING    │             │ CORRELATION    │
       └───────┬────────┘             └───────┬────────┘
               ↓                             ↓
       ┌────────────────┐             ┌────────────────┐
       │ SOURCE         │             │ AIS EVIDENCE   │
       │ HYPOTHESES     │             │                │
       └───────┬────────┘             └───────┬────────┘
               └──────────────┬──────────────┘
                              ↓
                 ┌────────────────────────┐
                 │ CROSS-SOURCE            │
                 │ CONSISTENCY / CONFLICT  │
                 └────────────┬───────────┘
                              ↓
                 ┌────────────────────────┐
                 │ EVIDENCE FUSION        │
                 │ + HYPOTHESIS RANKING   │
                 └────────────┬───────────┘
                              ↓
                 ┌────────────────────────┐
                 │ FORENSIC INVESTIGATION │
                 │ + EVIDENCE GRAPH       │
                 └────────────┬───────────┘
                              ↓
                 ┌────────────────────────┐
                 │ HUMAN INVESTIGATOR     │
                 └────────────┬───────────┘
                              ↓
                ┌─────────────┴─────────────┐
                ↓                           ↓
          INVESTIGATE                 INSUFFICIENT
          / REJECT                     EVIDENCE
```

------------------------------------------------------------------------

# 22. Core Principle

``` text
Satellite ≠ Absolute Truth
AIS       ≠ Absolute Truth
Drift     ≠ Absolute Truth
AI Score  ≠ Guilt

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
```

> **OilTrace AI does not accuse. It helps investigators investigate.**

------------------------------------------------------------------------

# 23. Final Freeze

**Do not add more major features unless a new requirement from the SIH
problem statement makes one necessary.**

The final architecture is:

1.  AI Oil-Spill Detection & Look-Alike Analysis
2.  Multi-Temporal Spill Reconstruction & Characterization
3.  Environmental Drift & Backward Hindcasting → Source Hypotheses
4.  Historical AIS Vessel Reconstruction & Correlation
5.  Cross-Source Consistency & Evidence Conflict Detection
6.  Evidence Fusion & Dynamic Hypothesis Ranking
7.  Forensic Investigation Graph & Explainable Evidence Chain
8.  Forward Forecasting, Impact Assessment & Historical Replay

**The project should now move from feature discovery to implementation,
validation, dataset selection, and prototype construction.**
