AI-Assisted Satellite Oil-Spill Detection & Investigation System

Final Feature Specification --- SIH

Status: Final proposed feature set for SIH prototype
Positioning: AI-assisted investigation and decision-support system
--- not an automated enforcement or vessel-accusation system.
Core principle: No single data source is treated as ground truth.
Satellite observations, temporal evidence, environmental conditions,
AIS, and model confidence are fused and shown with traceability.

1. Executive Summary

The proposed system is a satellite-first oil-spill investigation
platform.

Its job is not merely to detect an oil spill and not to claim
automatically which vessel caused it.

The intended workflow is:

Satellite imagery → Oil-spill detection → Temporal change analysis →
Spill evolution → Environmental/drift analysis → Candidate vessel
correlation → Evidence fusion → Uncertainty-aware ranking → Human
investigator

The system combines established technologies into an operational
workflow. Most individual components are existing research / baseline
capabilities. The main proposed contribution is the system-level
integration and evidence-fusion workflow, especially the way the
system connects satellite observations, temporal evolution,
drift/backtracking, AIS evidence, contradictions, and uncertainty into
one investigation record.

What the system should output

Instead of:

"Vessel X caused the spill."

the system should produce:

"Vessel X is a candidate consistent with the currently available
evidence."

with:

evidence supporting the candidate

evidence contradicting the candidate

estimated spill origin

satellite observations and timestamps

vessel/AIS history

drift/backtracking result

confidence and data-adequacy indicators

known limitations

human investigation status

2. Feature Classification

Label                               Meaning

BASELINE                        Expected/core capability. Similar
functionality is already well
established and should exist in a
credible solution.

IMPROVEMENT                     Existing technology used in a more
useful, robust, integrated, or
investigation-oriented way.

EXISTING                        A known technology/research
capability that we are adopting
rather than claiming as our
invention.

UNIQUE / PROPOSED               The system-level contribution or
workflow differentiation we are
proposing. It does not mean the
underlying algorithms are newly
invented.

3. Final Feature Set

F1. Multi-Source Satellite Ingestion

Classification: BASELINE / EXISTING
Importance: CRITICAL

Purpose

Acquire and standardize satellite imagery used for oil-spill monitoring.

Proposed data

Primary:

Sentinel-1 SAR

VV polarization initially

VH where useful

Optional/secondary:

Sentinel-2 optical imagery when cloud-free

Other compatible satellite products if available

Why it is needed

SAR is particularly valuable for maritime monitoring because it can
observe the ocean surface without relying on daylight and is less
affected by cloud cover than optical imagery.

The Krestenitis oil-spill benchmark uses Sentinel-1 SAR imagery and
contains oil spill, look-alike, ship, land, and sea classes.

Technology

Copernicus Sentinel-1

STAC/catalogue-style metadata where available

Raster processing

GDAL/rasterio

Python

GeoPandas/Shapely for geospatial operations

MVP

Use a prepared set of Sentinel-1 scenes rather than building a
production-scale satellite ingestion service.

Honest limitation

Satellite availability, revisit time, acquisition geometry, sea state,
wind conditions, and image quality can all affect detection. The system
cannot guarantee continuous observation.

References

Krestenitis et al., Oil Spill Identification from Satellite Images
Using Deep Neural Networks (Remote Sensing, 2019):
https://doi.org/10.3390/rs11151762

Recent review/dataset context:
https://essd.copernicus.org/articles/17/6807/2025/

F2. AI Oil-Spill Detection and Segmentation

Classification: BASELINE / EXISTING
Importance: CRITICAL

Purpose

Identify pixels/regions in SAR imagery that are likely to correspond to
oil-spill signatures.

Recommended approach

Use a semantic-segmentation model such as:

U-Net

U-Net++

DeepLabV3+

SegFormer

For SIH, a U-Net-family architecture is the most practical starting
point because it is comparatively easy to train and demonstrate.

Output

Binary or multi-class segmentation mask

Spill polygon

Pixel/region confidence

Estimated affected area

Important dataset issue

Krestenitis et al. provides a five-class semantic segmentation problem
involving:

sea

oil spill

look-alike

ship

land

A later study describes the benchmark as 1112 Sentinel-1 images with
1002 training and 110 test images.

Why this matters

A dark region in SAR is not automatically oil. Look-alikes can occur due
to natural phenomena and observation conditions.

Therefore, look-alike discrimination is part of the baseline detection
problem, not an optional extra.

Honest classification

We are not claiming to invent a new oil-spill segmentation
algorithm.

Evaluation

IoU

Dice/F1

Precision

Recall

False-positive rate

False-negative rate

References

Krestenitis et al.: https://doi.org/10.3390/rs11151762

Deep-learning oil-spill detection framework:
https://pmc.ncbi.nlm.nih.gov/articles/PMC8036558/

F3. Look-Alike Rejection

Classification: BASELINE / IMPROVEMENT
Importance: CRITICAL

Purpose

Reduce false detections caused by SAR dark formations that resemble oil.

Potential look-alikes

Depending on conditions:

low-wind areas

natural films

biogenic slicks

sea-state effects

rain cells

internal waves

other SAR dark formations

Approach

Use:

segmentation model

contextual SAR features

local texture

geometry

proximity to ships

temporal persistence/change

environmental metadata where available

Why it matters

A system that detects every dark SAR patch as oil is not operationally
useful.

Honest limitation

Perfect discrimination between oil and all natural look-alikes is
difficult. The system should expose uncertainty rather than claiming
certainty.

Reference

The Krestenitis dataset explicitly includes a look-alike class:

https://doi.org/10.3390/rs11151762

F4. Spill Geometry and Quantification

Classification: BASELINE
Importance: HIGH

Purpose

Convert the segmentation mask into investigation-ready geographic
information.

Outputs

spill polygon

estimated area

centroid

bounding box

perimeter

shape descriptors

approximate affected region

Technology

Raster-to-vector conversion

GeoPandas

Shapely

rasterio/GDAL

GIS map visualization

Why it matters

The investigation system needs a geographic object, not just a
classification label.

F5. Temporal Satellite Change Analysis

Classification: IMPROVEMENT / EXISTING RESEARCH
Importance: CRITICAL

Purpose

Use observations from multiple satellite acquisitions to determine how a
detected slick changes over time.

Outputs

first detected time

subsequent observations

expansion/contraction

displacement

persistence

disappearance

new spill regions

change in estimated area

Why it is important

A single image provides a snapshot.

Multiple observations provide a timeline.

The timeline helps distinguish:

persistent phenomena

newly appearing slicks

spreading slicks

disappearing slicks

multiple possible release events

Technology

Image registration/co-registration

segmentation on each acquisition

polygon overlap

centroid displacement

area-change calculation

temporal GIS

Honest limitation

Satellite revisit intervals mean the system usually does not observe the
exact moment a spill starts. It estimates evolution between available
observations.

F6. Spill Evolution / Event Reconstruction

Classification: IMPROVEMENT
Importance: HIGH

Purpose

Turn individual satellite detections into a single evolving spill event.

Example

Instead of:

Image A: 8 km²

Image B: 14 km²

Image C: 21 km²

the system presents:

"Observed slick expanded from approximately 8 km² to 21 km² over the
available observations."

Outputs

event timeline

area-vs-time graph

centroid trajectory

shape evolution

observation gaps

Why it matters

This creates the temporal context required for source investigation.

Honest limitation

The system is reconstructing from discrete observations; it does not
observe every intermediate state.

F7. Environmental Context Layer

Classification: BASELINE / EXISTING
Importance: HIGH

Purpose

Provide environmental information required to interpret spill movement.

Inputs

Potentially:

wind speed

wind direction

ocean currents

waves / Stokes drift where available

sea-state information

Sources

Potential sources include:

ECMWF/Copernicus marine products

NOAA products

other appropriate oceanographic datasets

Why it matters

An oil slick does not remain stationary. Its movement is influenced by
wind, currents and other physical processes.

Honest limitation

Environmental products themselves contain uncertainty. Drift predictions
can diverge substantially from observations when forcing fields are
inaccurate.

F8. Oil-Spill Drift Simulation

Classification: EXISTING / BASELINE
Importance: CRITICAL

Purpose

Estimate where the observed slick could move under environmental
forcing.

Technology options

For an MVP:

Lagrangian particle tracking

OpenDrift

wind + ocean-current forcing

particle ensemble

Potential future:

GNOME

higher-resolution hydrodynamic models

wave/Stokes-drift forcing

ensemble modelling

Why it matters

Forward drift helps answer:

"If oil originated here, where could it move?"

Important research basis

Oil-spill trajectory models commonly combine wind forcing and ocean
currents. Research has shown that incorporating currents and other
forcing can materially affect trajectory accuracy.

OpenDrift has also been implemented and validated for oil-spill
modelling using wind, currents and waves.

References

OpenDrift oil-spill implementation:
https://doi.org/10.1016/j.marpolbul.2023.115497

Multi-model oil-spill/drifter assessment:
https://doi.org/10.1016/j.dsr2.2016.04.002

Oil-spill trajectory model assessment:
https://doi.org/10.1016/j.envsoft.2004.04.025

F9. Backtracking / Source-Region Estimation

Classification: IMPROVEMENT / ADVANCED EXISTING RESEARCH
Importance: CRITICAL

Purpose

Instead of only forecasting where a spill will go, work backward from
the observed slick to estimate possible source regions.

Concept

Observed slick ↓ Environmental conditions ↓ Backward particle
trajectories ↓ Possible source region ↓ Candidate vessels in that
region/time

Why this is one of the most valuable features

Detection tells us:

"There is oil here."

Backtracking attempts to answer:

"Where could it have originated?"

That is much more useful for investigation.

Technology

Reverse/ensemble particle trajectories

Wind/current forcing

multiple initial conditions

uncertainty envelopes

candidate source-area generation

Honest novelty statement

Backtracking itself is not new. Marine oil-spill backtracking is an
active research topic.

Our proposed contribution is to connect the backtracked source region
directly to the satellite event timeline and vessel evidence in the
investigation workflow.

Reference

Recent research overview on marine oil-spill prediction and
backtracking:

https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2024.1427604/full

F10. AIS Vessel Correlation

Classification: BASELINE / EXISTING
Importance: CRITICAL

Purpose

Identify vessels whose location and movement are temporally and
spatially compatible with the estimated spill/source region.

AIS fields

Potentially:

MMSI

timestamp

latitude

longitude

speed over ground

course over ground

heading where available

vessel type

vessel dimensions

destination where available

Candidate filtering

A vessel becomes a candidate when factors such as:

proximity to estimated source region

time compatibility

trajectory compatibility

vessel type

AIS data quality

are consistent with the observed event.

Important principle

AIS is evidence, not ground truth.

AIS can be:

missing

delayed

noisy

switched off

spoofed

incomplete

Honest classification

AIS-vessel correlation is an existing capability. We are not claiming it
as a novel algorithm.

F11. Vessel Behavior / Trajectory Anomaly Analysis

Classification: EXISTING / IMPROVEMENT
Importance: MEDIUM-HIGH

Purpose

Identify vessel behavior that deserves investigation.

Possible signals

unexpected stopping

unusual course change

unusual speed change

AIS gap

route deviation

unusual loitering

presence near estimated source region

Critical rule

These signals must not be interpreted individually as evidence of
guilt.

For example:

"The vessel stopped" does not mean "the vessel dumped oil."

A vessel may stop for legitimate operational reasons.

Proposed use

Use anomalies as supporting evidence in candidate ranking, not as an
accusation.

Technology

trajectory feature extraction

rule-based anomaly detection initially

statistical baseline

Isolation Forest / similar methods only if justified by data

Honest limitation

Defining "suspicious maritime behavior" requires domain expertise and
historical validation. For SIH, explicit rules and literature-backed
features are safer than inventing arbitrary behavioral assumptions.

F12. AIS--Satellite Consistency / Adversarial Check

Classification: UNIQUE / PROPOSED SYSTEM FEATURE
Importance: HIGH

Purpose

Handle the possibility that AIS information is incomplete, misleading or
spoofed.

Concept

Compare:

satellite-observed vessel position

AIS position

AIS trajectory

satellite spill location

estimated source region

time

Example

If:

AIS says vessel was 40 km away

satellite evidence places a vessel near the suspected source

the timestamps are compatible

the system should not declare spoofing.

Instead:

AIS--satellite inconsistency detected --- investigate.

Why this is valuable

It prevents the system from blindly trusting AIS.

What it cannot do

It cannot prove deliberate spoofing.

The system can identify inconsistency, not intent.

Classification rationale

The underlying ingredients are existing. The proposed uniqueness is
using the inconsistency as an explicit evidence type inside the
oil-spill investigation workflow.

F13. Multi-Source Evidence Fusion

Classification: UNIQUE / PROPOSED
Importance: CRITICAL --- CORE DIFFERENTIATOR

Purpose

Combine independent evidence sources instead of allowing one model to
determine the result.

Evidence layers

Satellite spill detection

Temporal evolution

Estimated source region

Drift/backtracking

AIS trajectory

Vessel proximity

Vessel behavior signals

AIS--satellite consistency

Environmental compatibility

Data quality

Proposed output

A candidate vessel receives an evidence score, not a guilt score.

Example conceptual structure:

Candidate Score =

source-region compatibility

temporal compatibility

trajectory compatibility

drift compatibility

satellite consistency

vessel metadata compatibility

anomaly evidence

minus:

contradictory evidence

missing/poor-quality data

Important design principle

The exact weighting should be calibrated on historical data. For the SIH
prototype, a transparent rule-based scoring model is preferable to
claiming a fully learned causal attribution model.

Why this is our strongest differentiator

Most individual components already exist in research.

The system contribution is the operational evidence-fusion layer
connecting them into a single investigation workflow.

F14. Evidence Provenance / Explainable Investigation Record

Classification: UNIQUE / PROPOSED
Importance: CRITICAL

Purpose

Every candidate result should be traceable to the evidence that produced
it.

Investigation record should contain

satellite scene IDs

acquisition timestamps

detection mask

estimated spill area

temporal observations

environmental data timestamps

drift assumptions

estimated source region

AIS records used

candidate vessel information

supporting evidence

contradictory evidence

model confidence

data adequacy

analyst decisions

investigation status

Why it matters

A government investigator should be able to ask:

"Why did the system rank this vessel?"

and receive an evidence trail.

Why this is important for responsible AI

It prevents the system from becoming an unexplained "black-box
accusation engine."

F15. Model Confidence vs Data Adequacy

Classification: UNIQUE / PROPOSED
Importance: CRITICAL

Purpose

Separate:

Model uncertainty

from:

Data scarcity / data inadequacy

Example

Low confidence may happen because:

the image is ambiguous

the model sees a look-alike

the observation is outside the training distribution

But low performance can also happen because:

the training class has too few representative pixels

a particular geographic region is underrepresented

environmental conditions are poorly represented

These are not the same problem.

Proposed reporting

Instead of:

Confidence = 42%

report:

Detection confidence: 0.42

Data adequacy: Limited

Reason: observation differs from training distribution /
insufficient representative examples

Why this matters

This prevents false precision.

Honest MVP implementation

A complete uncertainty-calibration system is beyond the hackathon.

For SIH:

expose model confidence

record training-data coverage limitations

flag out-of-distribution / low-data situations where feasible

avoid presenting confidence as probability of guilt

F16. Candidate Ranking --- Not Automated Attribution

Classification: UNIQUE / PROPOSED
Importance: CRITICAL

Purpose

Rank candidate vessels according to available evidence.

Output

Example:

Rank   Vessel        Evidence status

1      Candidate A   Strong temporal + spatial compatibility
2      Candidate B   Moderate compatibility
3      Candidate C   Weak compatibility / contradictory evidence

Important terminology

Use:

Candidate

Evidence compatibility

Investigation priority

Confidence

Supporting/contradictory evidence

Avoid:

Guilty vessel

Responsible vessel

Confirmed polluter

unless independently confirmed by authorized investigators.

Why

The system is decision support, not a legal attribution system.

F17. Human-in-the-Loop Investigation

Classification: BASELINE FOR RESPONSIBLE DEPLOYMENT / IMPROVEMENT
Importance: CRITICAL

Purpose

Ensure that automated results are reviewed by an authorized human.

Investigator actions

inspect satellite imagery

inspect spill mask

inspect timeline

inspect drift result

inspect AIS track

inspect evidence

accept candidate for investigation

reject candidate

mark uncertain

add analyst notes

Investigation states

Detected

Under review

Candidate generated

Investigation ongoing

Rejected

Confirmed by external investigation

Why it matters

The model cannot understand all operational/legal context.

F18. Correction / Appeal / Audit Mechanism

Classification: UNIQUE / PROPOSED
Importance: HIGH

Purpose

Prevent a wrong AI result from becoming an irreversible accusation.

Mechanism

Every automated result is stored with:

original evidence

model version

input data

timestamp

ranking

analyst decision

An investigator can later:

reject candidate

change status

attach additional evidence

record reason

retain previous system output for auditability

Important principle

Corrections should not silently erase historical outputs.

They should create an auditable investigation history.

F19. Adversarial / Missing-AIS Handling

Classification: IMPROVEMENT / PROPOSED
Importance: HIGH

Cases

AIS switched off

AIS gap

spoofed position

inconsistent MMSI trajectory

satellite/AIS mismatch

incomplete vessel history

System behavior

Instead of:

"No AIS evidence → vessel not involved."

the system should say:

"AIS evidence unavailable/inconsistent; candidate cannot be ruled out
on AIS absence alone."

Why

This is more robust against adversarial and incomplete data.

F20. Historical Incident Replay / End-to-End Validation

Classification: UNIQUE / VALIDATION FEATURE
Importance: CRITICAL

Purpose

Test the whole pipeline on historical events.

Test sequence

For each historical case:

Load satellite observations available around the event.

Detect the spill.

Reconstruct temporal evolution.

Obtain environmental forcing.

Estimate possible source region.

Load AIS tracks.

Generate candidate vessels.

Rank candidates.

Compare with independently documented incident information.

Important validation rule

Do not use every historical case for tuning and then call it testing.

Use:

training/development cases

validation cases

held-out final cases

where possible.

What counts as success

Not simply:

"The model detected oil."

The end-to-end question is:

"Can the system reconstruct a historically known incident and produce
a plausible, evidence-supported candidate ranking without excessive
false attribution?"

F21. Historical Ground-Truth Case Dataset

Classification: EXISTING DATA + PROJECT-SPECIFIC DATASET
Importance: CRITICAL

Requirement

Build a small benchmark containing, where available:

confirmed incident

satellite imagery

incident timestamp

location

vessel information

AIS trajectory

environmental conditions

independent confirmation/source

Reality

There is no guarantee that every public spill has a known responsible
vessel.

Therefore cases should be labelled:

Confirmed source

Probable source

Spill detected, source unknown

Do not mix these categories.

Data limitation

Public datasets such as oil-spill segmentation benchmarks are useful for
detection, but they do not automatically provide ground truth for vessel
attribution.

Relevant dataset evidence

Krestenitis et al. used EMSA CleanSeaNet-confirmed oil-spill events for
its SAR segmentation dataset.

Recent datasets also highlight the continuing scarcity of comprehensive,
consistently labelled oil-spill data.

F22. Investigator Dashboard / Geospatial Command Interface

Classification: BASELINE / INTEGRATION
Importance: CRITICAL

Main interface

Large interactive map containing:

satellite image

spill mask

spill polygon

vessel tracks

candidate vessels

source region

drift particles

timeline

Side panel

event information

spill area

detection confidence

data adequacy

candidate ranking

supporting evidence

contradictory evidence

Timeline

satellite observations

spill growth

vessel positions

environmental conditions

Technology

Recommended:

React

TypeScript

MapLibre GL / OpenLayers / Leaflet

FastAPI

PostgreSQL/PostGIS

Python ML backend

4. Features That Are NOT Core SIH MVP

The following should not be promised as fully implemented during the
hackathon:

Advanced learned oil-spill backtracking

Research exists, but implementing and validating a new deep-learning
backtracking model is unnecessary for the MVP.

Use physics-based / particle-based backtracking first.

Real-time global AIS infrastructure

Commercial-grade global AIS infrastructure is outside realistic SIH
scope.

Use a prepared or accessible dataset/API for demonstration.

Production-grade ocean forecasting

Use existing environmental products rather than building an ocean
circulation model.

Automatic legal attribution

Explicitly out of scope.

Automatic enforcement action

Out of scope.

Perfect AIS spoofing detection

Out of scope.

Fully calibrated probabilistic causal attribution

Future research.

5. Technology Architecture

Frontend

React

TypeScript

MapLibre GL / OpenLayers

Charting library

Backend

Python

FastAPI

PostgreSQL

PostGIS

Machine Learning

PyTorch

U-Net / U-Net++

SegFormer as an alternative

NumPy

OpenCV

rasterio

GDAL

Geospatial

GeoPandas

Shapely

rasterio

GDAL

PostGIS

Satellite

Sentinel-1 SAR

Copernicus data ecosystem

VV initially

VH when useful

Environmental

Potentially:

ECMWF/Copernicus products

NOAA products

ocean-current datasets

wave products where available

Drift

OpenDrift initially

particle-based Lagrangian simulation

AIS

historical AIS dataset/API available for the prototype

standardized trajectory processing

Deployment

For SIH:

Docker

local/server deployment

optional cloud deployment

6. Final MVP Architecture

                SATELLITE DATA
                     |
                     v
          +----------------------+
          | SAR Pre-processing   |
          +----------------------+
                     |
                     v
          +----------------------+
          | Oil Spill Detection  |
          | + Look-alike Filter  |
          +----------------------+
                     |
                     v
          +----------------------+
          | Spill Polygon/Area   |
          +----------------------+
                     |
                     v
          +----------------------+
          | Temporal Analysis    |
          | Spill Evolution      |
          +----------------------+
                     |
             +-------+-------+
             |               |
             v               v
       ENVIRONMENT         AIS DATA
       Wind/Currents          |
             |                |
             v                v
       Drift / Backtrack   Vessel Tracks
             |                |
             +-------+--------+
                     |
                     v
          +----------------------+
          | Evidence Fusion      |
          | + Contradictions     |
          | + Data Adequacy      |
          +----------------------+
                     |
                     v
          +----------------------+
          | Candidate Ranking    |
          | NOT Guilt            |
          +----------------------+
                     |
                     v
          +----------------------+
          | Investigator UI      |
          | Evidence + Audit     |
          +----------------------+

7. Importance Priorities

Tier 1 --- MUST HAVE

Satellite ingestion

Oil-spill segmentation

Look-alike rejection

Spill geometry/quantification

Temporal analysis

Environmental context

Drift/backtracking

AIS correlation

Evidence fusion

Candidate ranking

Investigator dashboard

End-to-end validation

Tier 2 --- SHOULD HAVE

Spill evolution timeline

AIS-satellite inconsistency

Model confidence vs data adequacy

Evidence provenance

Human investigation status

Correction/audit mechanism

Vessel behavior anomalies

Tier 3 --- FUTURE / RESEARCH

Advanced learned backtracking

Ensemble uncertainty modelling

Large-scale real-time AIS ingestion

Global historical incident database

Advanced adversarial AIS detection

Fully probabilistic causal attribution

8. What Is Actually Unique?

This needs to be stated carefully.

NOT unique

These are established:

satellite oil-spill detection

SAR segmentation

look-alike classification

satellite change detection

AIS tracking

vessel anomaly detection

oil-spill drift modelling

particle tracking

oil-spill backtracking

map visualization

We should not claim these as inventions.

Proposed differentiation

The strongest proposed differentiation is:

1. Satellite-first investigation workflow

The investigation starts from an observed spill and works backward
toward possible sources.

2. Evidence fusion

Satellite, temporal, environmental and AIS evidence are combined rather
than treated as isolated models.

3. Contradiction-aware investigation

The system explicitly records evidence that disagrees, including
AIS--satellite inconsistencies.

4. Uncertainty-aware attribution

The system distinguishes model confidence from data adequacy and does
not force an attribution when evidence is insufficient.

5. Evidence provenance

The investigator can trace a candidate ranking back to the observations
and data used.

6. Human-verifiable output

The system produces candidates and evidence rather than automated
accusations.

Honest novelty statement:

"Our novelty is primarily at the system and workflow level:
integrating satellite detection, temporal reconstruction,
environmental backtracking, vessel correlation, contradiction handling
and uncertainty-aware evidence ranking into a single investigation
pipeline. We are not claiming that the underlying algorithms are
individually novel."

9. Main Risks and Mitigations

Risk                    Impact                  Mitigation

SAR look-alikes         High                    Look-alike class +
contextual features

Sparse training data    High                    Report data adequacy
separately

Satellite revisit gaps  High                    Show observation gaps
explicitly

AIS missing/spoofed     High                    Treat AIS as evidence,
add inconsistency flag

Drift uncertainty       High                    Ensemble/backtracking +
uncertainty envelope

False vessel            Critical                Candidate ranking + human
attribution                                     verification

Lack of confirmed       Critical                Separate detection
incidents                                       benchmark from
attribution benchmark

Limited SIH time        Critical                Use prepared datasets +
scope control

Commercial competition  Medium                  Position as
satellite-first sovereign
investigation workflow

10. Evaluation Plan

Detection

IoU

Dice/F1

Precision

Recall

false-positive rate

Temporal analysis

area estimation error

centroid displacement

temporal consistency

Drift

distance between predicted and observed slick

trajectory error

source-region overlap

ensemble spread vs error

Candidate ranking

Where confirmed ground truth exists:

Top-1 candidate accuracy

Top-3 recall

Mean reciprocal rank

false attribution rate

End-to-end

For each historical event:

Detection → reconstruction → source-region estimation → candidate
generation → candidate ranking

Report:

detection success

source-region quality

candidate ranking quality

uncertainty

false attribution

cases where the system correctly refuses to attribute

11. The Most Important Evaluation Principle

A successful system should not be defined as:

"It always identifies a vessel."

A better definition is:

"It identifies plausible candidates when the evidence supports
attribution and clearly communicates uncertainty or insufficient
evidence when it does not."

This is essential for a government decision-support system.

12. Recommended SIH Demonstration Scenario

Step 1 --- New satellite scene

System receives Sentinel-1 SAR scene.

Step 2 --- Detection

AI identifies a probable oil slick and produces a segmentation mask.

Step 3 --- Quantification

System calculates approximate spill area and location.

Step 4 --- Historical comparison

Previous satellite observations are loaded.

System shows:

"Slick detected across three observations; estimated area increased
from X to Y."

Step 5 --- Environmental context

Wind and ocean-current information is loaded.

Step 6 --- Backtracking

Particles are run backward from the observed slick.

System generates a probable source region with an uncertainty envelope.

Step 7 --- AIS correlation

Vessels present in/near the source region during the relevant time
window are retrieved.

Step 8 --- Evidence fusion

Each candidate receives:

temporal compatibility

spatial compatibility

drift compatibility

trajectory compatibility

satellite consistency

AIS quality

contradictory evidence

Step 9 --- Investigator review

The dashboard displays:

Candidate A --- Strong evidence compatibility
Candidate B --- Moderate evidence compatibility
Candidate C --- Weak / contradictory evidence

Step 10 --- Human decision

The investigator chooses:

investigate

reject

uncertain

The system stores the decision and evidence trail.

13. What We Should Say in the PPT

One-line product description

AI-assisted satellite intelligence system that detects oil spills,
reconstructs their evolution, traces probable source regions,
correlates vessel activity, and presents evidence-backed candidates
for human investigation.

Core features for PPT

1. AI Spill Detection

Detect and segment probable oil spills from Sentinel-1 SAR imagery.

2. Temporal Spill Reconstruction

Compare multiple satellite observations to understand how the spill
evolves.

3. Drift Backtracking

Use wind and ocean-current information to estimate probable source
regions.

4. Vessel Correlation

Match source regions and timelines against AIS vessel activity.

5. Evidence Fusion

Combine satellite, temporal, environmental and AIS evidence into a
candidate ranking.

6. Uncertainty & Adversarial Awareness

Flag data gaps, uncertainty and AIS--satellite inconsistencies instead
of treating any single source as truth.

7. Explainable Investigation Dashboard

Show the evidence chain and let authorized investigators verify, reject
or update candidate assessments.

14. Final Positioning

The project should not be presented as:

"AI catches the ship that caused an oil spill."

It should be presented as:

"AI-assisted satellite investigation for oil-spill source
identification."

The distinction is important.

The system detects the event automatically, performs evidence-driven
analysis, ranks plausible candidates, and helps investigators understand
why a candidate was ranked.

It does not make an autonomous legal determination.

15. Reference Papers / Resources

Oil-spill detection

Krestenitis et al. --- Oil Spill Identification from Satellite Images Using Deep Neural Networks

Remote Sensing, 2019.

https://doi.org/10.3390/rs11151762

Key relevance:

Sentinel-1 SAR

semantic segmentation

oil spill

look-alikes

ships

land

sea

A Deep-Learning Framework for the Detection of Oil Spills from SAR Data

Sensors, 2021.

https://pmc.ncbi.nlm.nih.gov/articles/PMC8036558/

Key relevance:

Sentinel-1 SAR

preprocessing

semantic segmentation

oil/look-alike/ship/land/sea classes

Oil-spill trajectory / drift

Preliminary Assessment of an Oil-Spill Trajectory Model Using Satellite-Tracked, Oil-Spill-Simulating Drifters

Environmental Modelling & Software.

https://doi.org/10.1016/j.envsoft.2004.04.025

Key relevance:

wind forcing

ocean currents

oil-spill trajectory modelling

trajectory validation

A Multi-Model Assessment of the Impact of Currents, Waves and Wind in Modelling Surface Drifters and Oil Spill

Deep-Sea Research Part II.

https://doi.org/10.1016/j.dsr2.2016.04.002

Key relevance:

currents

wind

waves

Stokes drift

uncertainty

oil-spill/drifter modelling

An Ocean--Wave--Trajectory Forecasting System ... for Oil Spill Modeling

Marine Pollution Bulletin, 2023.

https://doi.org/10.1016/j.marpolbul.2023.115497

Key relevance:

OpenDrift

wind

currents

waves

oil-spill modelling

validation

Oil-spill backtracking

Prediction and (Back)tracking of Marine Oil Spill Drift and Diffusion

Frontiers in Marine Science, 2024.

https://doi.org/10.3389/fmars.2024.1427604

Key relevance:

oil-spill prediction

backtracking

deep-learning approaches

current research direction

Recent dataset context

Dataset of Oil Slicks, Look-Alikes and Remarkable SAR Signatures Obtained from Sentinel-1 Data in the Eastern Mediterranean Sea

Earth System Science Data, 2025.

https://doi.org/10.5194/essd-17-6807-2025

Key relevance:

oil-spill datasets

look-alikes

Sentinel-1

data scarcity

benchmark limitations

16. Final Honesty Statement

This project should make three claims only:

Claim 1 --- Solid

Satellite SAR can be used for oil-spill detection and segmentation, and
this is supported by established research.

Claim 2 --- Solid but engineering-oriented

Combining satellite observations with temporal analysis, environmental
drift and AIS can create a useful investigation workflow.

Claim 3 --- Proposed contribution

The project's differentiation is the evidence-centric integration
layer that connects those sources into a transparent,
uncertainty-aware investigation workflow.

We should not claim:

a new state-of-the-art segmentation architecture

perfect oil-vs-look-alike detection

perfect vessel attribution

reliable automatic AIS spoofing detection

legal proof of responsibility

production-grade global maritime intelligence

a fully validated real-world attribution system without sufficient
historical ground truth

Those are future research/deployment goals, not SIH claims.

17. Final Feature Summary Table

#             Feature               Category               Importance     SIH MVP

1              Multi-source          Baseline               Critical       Yes
satellite ingestion

2              AI oil-spill          Baseline/Existing      Critical       Yes
segmentation

3              Look-alike rejection  Baseline/Improvement   Critical       Yes

4              Spill geometry & area Baseline               High           Yes

5              Temporal satellite    Improvement            Critical       Yes
analysis

6              Spill evolution       Improvement            High           Yes
reconstruction

7              Environmental context Existing               High           Yes

8              Drift simulation      Existing               Critical       Yes

9              Source backtracking   Improvement            Critical       Yes

10             AIS vessel            Existing               Critical       Yes
correlation

11             Vessel behavior       Existing/Improvement   Medium-High    If time
anomaly

12             AIS--satellite        Proposed               High           Yes
inconsistency

13             Multi-source evidence Proposed               Critical       Yes
fusion

14             Evidence provenance   Proposed               Critical       Yes

15             Confidence vs data    Proposed               Critical       Prototype
adequacy

16             Candidate ranking     Proposed               Critical       Yes

17             Human-in-loop         Responsible deployment Critical       Yes
investigation

18             Correction/audit      Proposed               High           Prototype
mechanism

19             Missing/adversarial   Improvement            High           Prototype
AIS handling

20             Historical incident   Validation             Critical       Yes
replay

21             Historical            Validation             Critical       Yes
ground-truth dataset

22             Investigator          Integration            Critical       Yes
dashboard

23             Advanced learned      Future                 Medium         No
backtracking

24             Global real-time AIS  Future                 Medium         No
infrastructure

18. Bottom Line

The strongest version of the project is not a collection of 25 AI
features.

It is one coherent system:

Detect → Observe change → Reconstruct movement → Estimate source
region → Correlate vessels → Fuse evidence → Quantify uncertainty →
Let an investigator decide.
