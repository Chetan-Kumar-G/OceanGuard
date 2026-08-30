# OilTrace AI — SIH Evaluation & Marking Schema

## Total Score: 50 Marks

The project is evaluated across five official judging categories:

| Category | Maximum Marks |
|---|---:|
| Innovation & Novelty | 10 |
| Feasibility | 10 |
| Technical Depth | 10 |
| Social Impact | 10 |
| Prototype | 5 |
| PPT / Presentation | 5 |
| **TOTAL** | **50** |

---

# 1. Innovation & Novelty — 10 Marks

## What Judges Are Expected to Evaluate

The novelty score should primarily evaluate whether OilTrace AI provides a meaningful improvement over conventional oil-spill detection and existing maritime-intelligence workflows.

### Scoring Breakdown

| Criterion | Marks |
|---|---:|
| Problem-specific innovation | 2 |
| Multi-source investigation workflow | 2 |
| Competing source hypotheses instead of forced single-source attribution | 2 |
| Cross-source conflict handling | 2 |
| Explainable evidence fusion and human-in-the-loop investigation | 2 |
| **TOTAL** | **10** |

## Our Strongest Novelty

The individual technologies are NOT claimed as novel:

- Sentinel-1 SAR
- Oil-spill segmentation
- U-Net / SegFormer
- AIS tracking
- Drift modelling
- Backward hindcasting
- GIS
- Forecasting

These are established technologies.

### Our System-Level Innovation

OilTrace AI combines these technologies into a spill-centric investigation workflow:

Satellite Observation
↓
Spill Detection
↓
Temporal Reconstruction
↓
Environmental Drift
↓
Multiple Source Hypotheses
↓
Historical AIS
↓
Cross-Source Consistency
↓
Evidence Fusion
↓
Candidate Ranking
↓
Explainable Investigation
↓
Human Decision

## Important Novelty Position

The project should be presented as:

> **System-level innovation rather than claiming invention of individual algorithms.**

### Maximum Novelty Claim We Should Make

> OilTrace AI introduces a hypothesis-driven, evidence-aware workflow for oil-spill investigation that preserves competing explanations, explicitly represents contradictory and missing evidence, and updates candidate assessments as new observations become available.

### Claims We Must Avoid

Do NOT claim:

- We invented oil-spill segmentation.
- We invented AIS analysis.
- We invented drift modelling.
- We invented backward tracking.
- We invented explainable AI.
- No existing commercial system can perform vessel intelligence.
- Our system proves the responsible vessel.
- Our system automatically detects AIS spoofing.

## Estimated Score Potential

**8–9 / 10** if the integration is convincingly demonstrated.

Potential weakness:

Commercial maritime-intelligence systems already perform portions of this workflow, so novelty depends heavily on demonstrating the specific investigation workflow and evidence-handling design rather than simply listing technologies.

---

# 2. Feasibility — 10 Marks

## What Judges Are Expected to Evaluate

Whether the proposed system can realistically be implemented and demonstrated.

### Scoring Breakdown

| Criterion | Marks |
|---|---:|
| Availability of satellite data | 2 |
| Availability / practicality of environmental data | 1.5 |
| Availability / practicality of AIS data | 1.5 |
| Technical implementation feasibility | 2 |
| SIH-timeframe feasibility | 2 |
| Handling of limitations and failure cases | 1 |
| **TOTAL** | **10** |

## Feasible Components

### Highly Feasible

- Sentinel-1 preprocessing
- Satellite image segmentation
- Spill polygon extraction
- Multi-temporal comparison
- GIS visualization
- Historical AIS filtering
- Evidence database
- Candidate ranking
- Investigation dashboard

### Feasible With Integration Work

- OpenDrift
- Environmental forcing integration
- Backward hindcasting
- Cross-source consistency
- Dynamic hypothesis ranking

### Difficult for SIH

- Large-scale operational deployment
- Real-time global satellite ingestion
- Fully calibrated attribution probabilities
- Reliable AIS spoofing detection
- Complete historical confirmed-attribution database
- Operational-grade forecasting
- Fully automated legal evidence generation

## Feasibility Strategy

The SIH prototype should use:

- Public satellite data
- Public / accessible environmental data
- A limited historical AIS dataset
- Predefined historical events
- Established open-source models
- A controlled geographic region

The goal is to demonstrate the workflow rather than build a global operational system.

## Critical Feasibility Rule

The prototype should demonstrate:

> **A complete working pipeline on selected cases**

rather than:

> A partially implemented global system.

## Estimated Score Potential

**8–9 / 10**

Potential weakness:

AIS data access and confirmed historical spill attribution data may be difficult. The system must clearly separate what is demonstrated with available data from what is proposed for operational deployment.

---

# 3. Technical Depth — 10 Marks

## What Judges Are Expected to Evaluate

Whether the project demonstrates meaningful technical understanding rather than being primarily a UI integrating APIs.

### Scoring Breakdown

| Technical Component | Marks |
|---|---:|
| SAR image processing and ML detection | 2 |
| Multi-temporal geospatial analysis | 1.5 |
| Environmental drift / hindcasting | 2 |
| AIS trajectory processing | 1.5 |
| Evidence fusion / hypothesis ranking | 1.5 |
| Uncertainty, validation and failure handling | 1.5 |
| **TOTAL** | **10** |

---

## Technical Pipeline

### Stage 1 — SAR

Sentinel-1
↓
Calibration
↓
Preprocessing
↓
Segmentation
↓
Spill Mask

### Stage 2 — Geospatial

Spill Mask
↓
Polygon Extraction
↓
Area / Centroid / Shape
↓
Temporal Comparison

### Stage 3 — Environmental

Wind
+
Currents
+
Other Relevant Forcing
↓
Drift Model

### Stage 4 — Hindcasting

Observed Spill
↓
Backward Particle Simulation
↓
Source-Compatible Regions
↓
Multiple Hypotheses

### Stage 5 — AIS

Historical AIS
↓
Spatial Filtering
↓
Temporal Filtering
↓
Trajectory Compatibility
↓
Candidate Vessels

### Stage 6 — Evidence Fusion

Satellite Evidence
+
Temporal Evidence
+
Drift Evidence
+
AIS Evidence
+
Cross-Source Consistency
↓
Evidence Compatibility
↓
Candidate Ranking

---

# 4. Evidence Fusion Technical Design

The prototype may use a transparent weighted scoring model.

Example:

| Evidence | Prototype Weight |
|---|---:|
| Spatial compatibility | 25% |
| Temporal compatibility | 20% |
| Drift compatibility | 25% |
| AIS trajectory compatibility | 15% |
| Cross-source consistency | 10% |
| Data quality | 5% |
| **TOTAL** | **100%** |

## Important

These weights are:

> **Prototype assumptions**

They are NOT scientifically validated probabilities.

Production deployment would require:

- Historical validation
- Domain-expert review
- Calibration
- Sensitivity analysis
- Possibly probabilistic modelling

The score should therefore be labelled:

> **Evidence Compatibility Score**

NOT:

> Probability of guilt.

---

# 5. Uncertainty Handling

Technical depth should include explicit treatment of uncertainty.

## Model Uncertainty

Example:

> The model cannot confidently distinguish oil from a SAR look-alike.

## Data Uncertainty

Example:

> Environmental forcing is available only at limited spatial/temporal resolution.

## Observation Uncertainty

Example:

> Satellite revisit gaps prevent continuous observation.

## AIS Uncertainty

Example:

> AIS transmission is unavailable during part of the relevant interval.

## Output

Use:

- HIGH
- MEDIUM
- LIMITED
- UNKNOWN

Avoid unsupported numerical precision.

---

# 6. Social Impact — 10 Marks

## What Judges Are Expected to Evaluate

Whether the solution addresses a meaningful real-world problem and produces useful outcomes.

### Scoring Breakdown

| Impact Area | Marks |
|---|---:|
| Marine environmental protection | 2 |
| Faster spill response | 2 |
| Protection of fisheries/coastal communities | 2 |
| Support for government / maritime authorities | 2 |
| Long-term environmental and economic benefits | 2 |
| **TOTAL** | **10** |

## Primary Users

### Government / Maritime Authorities

Potential users:

- Coast Guard
- Environmental authorities
- Maritime enforcement agencies
- Port authorities
- Government investigation teams

### Secondary Users

- Environmental monitoring organizations
- Researchers
- Marine pollution response teams

## Impact

Oil spills can affect:

- Marine ecosystems
- Fisheries
- Coastal communities
- Ports
- Tourism
- Sensitive coastal areas

The system can help authorities:

1. Detect spills earlier.
2. Understand observed spill evolution.
3. Estimate possible movement.
4. Prioritize investigation.
5. Identify vessels requiring further investigation.
6. Assess potentially affected regions.
7. Maintain an auditable evidence trail.

## Important Social Responsibility

The system must not automatically accuse vessels.

A false attribution can:

- Trigger unnecessary inspections.
- Damage reputation.
- Waste enforcement resources.
- Produce incorrect public claims.

Therefore:

> **Human review is a core safety requirement, not merely a UI feature.**

## Estimated Score Potential

**9–10 / 10**

This category can be one of the project's strongest areas if the presentation clearly connects the technology to environmental protection and government response.

---

# 7. Prototype — 5 Marks

## What Judges Are Expected to Evaluate

Whether the team has a working demonstration rather than only slides.

### Scoring Breakdown

| Prototype Capability | Marks |
|---|---:|
| Working satellite spill detection | 1 |
| Multi-temporal visualization | 0.75 |
| Drift / source-hypothesis demonstration | 1 |
| AIS vessel correlation | 0.75 |
| Evidence fusion + candidate ranking | 0.75 |
| Investigation dashboard / explainability | 0.75 |
| **TOTAL** | **5** |

---

# 8. Minimum Viable Prototype

The prototype should demonstrate ONE complete historical incident or controlled scenario.

## Demo Flow

### Step 1

Load satellite image.

### Step 2

Detect probable spill.

### Step 3

Display spill polygon.

### Step 4

Show previous / subsequent observations.

### Step 5

Run environmental drift simulation.

### Step 6

Generate multiple source hypotheses.

### Step 7

Load historical AIS.

### Step 8

Filter candidate vessels.

### Step 9

Compare satellite + drift + AIS evidence.

### Step 10

Rank candidates.

### Step 11

Display:

- Supporting evidence
- Contradictory evidence
- Missing evidence
- Data quality
- Uncertainty

### Step 12

Human investigator chooses:

- Investigate
- Reject
- Uncertain

---

# 9. Prototype Priority

## MUST DEMONSTRATE

1. Spill detection
2. Spill polygon
3. Temporal comparison
4. Drift / source hypotheses
5. AIS correlation
6. Evidence scoring
7. Explainable candidate ranking

## NICE TO HAVE

- Historical replay
- Forward forecasting
- Impact layers
- Evidence graph
- Dynamic update

## DO NOT SACRIFICE CORE PIPELINE FOR EXTRA UI

A working end-to-end pipeline is more valuable than ten disconnected dashboard features.

---

# 10. PPT / Presentation — 5 Marks

## What Judges Are Expected to Evaluate

Whether the team clearly communicates:

- Problem
- Solution
- Innovation
- Technology
- Feasibility
- Impact
- Prototype

### Scoring Breakdown

| Presentation Component | Marks |
|---|---:|
| Problem clarity | 1 |
| Solution / workflow clarity | 1 |
| Innovation explanation | 1 |
| Technical explanation | 1 |
| Visual quality + demo storytelling | 1 |
| **TOTAL** | **5** |

---

# 11. Recommended PPT Story

## Slide 1 — Problem

### Question

> How can authorities determine what happened after an oil spill is detected?

Show:

Satellite → Spill → Unknown Cause

---

## Slide 2 — Current Gap

Traditional workflow may require analysts to manually combine:

- Satellite imagery
- Historical observations
- Ocean conditions
- AIS
- Vessel information

Show the fragmentation.

---

## Slide 3 — Solution

Show the complete OilTrace AI pipeline.

---

## Slide 4 — Detection

Show:

- Sentinel-1
- Spill mask
- Look-alike handling

---

## Slide 5 — Reconstruction

Show:

T1 → T2 → T3

and explain how the system uses temporal observations.

---

## Slide 6 — Source Hypotheses

Show backward hindcasting.

Important wording:

> "Generates physically plausible source hypotheses."

Not:

> "Finds the exact source."

---

## Slide 7 — Vessel Correlation

Show:

Source Hypothesis
↓
Historical AIS
↓
Candidate Vessels

---

## Slide 8 — Innovation

Focus on:

> **Evidence-aware hypothesis investigation**

Show:

Supporting Evidence
+
Contradictory Evidence
+
Missing Evidence
+
Uncertainty

---

## Slide 9 — Example Investigation

Show one complete case.

---

## Slide 10 — Impact

Show:

Detection
→
Investigation
→
Response
→
Environmental Protection

---

# 12. Overall Expected Score

## Conservative Evaluation

| Category | Expected |
|---|---:|
| Innovation & Novelty | 7–8 / 10 |
| Feasibility | 8 / 10 |
| Technical Depth | 8–9 / 10 |
| Social Impact | 9 / 10 |
| Prototype | 4 / 5 |
| PPT | 4 / 5 |
| **TOTAL** | **40–43 / 50** |

---

# 13. Strong Execution Scenario

If the team successfully demonstrates the complete pipeline with credible data:

| Category | Possible |
|---|---:|
| Innovation & Novelty | 8–9 / 10 |
| Feasibility | 9 / 10 |
| Technical Depth | 9–10 / 10 |
| Social Impact | 9–10 / 10 |
| Prototype | 5 / 5 |
| PPT | 5 / 5 |
| **TOTAL** | **45–48 / 50** |

This requires the prototype to actually work.

---

# 14. Weak Execution Scenario

If the project becomes mostly:

- UI
- Static maps
- Fake AIS
- Hard-coded scores
- Screenshots
- Unsupported claims
- No actual drift modelling
- No real segmentation

then the likely score could fall to:

| Category | Possible |
|---|---:|
| Innovation & Novelty | 4–6 / 10 |
| Feasibility | 6–7 / 10 |
| Technical Depth | 4–6 / 10 |
| Social Impact | 7–8 / 10 |
| Prototype | 2–3 / 5 |
| PPT | 3–4 / 5 |
| **TOTAL** | **26–34 / 50** |

---

# 15. Highest-Value Work for the Team

Given the marking scheme, effort should NOT be distributed equally across every feature.

## Priority 1

### Build the end-to-end investigation pipeline.

Detection
→
Temporal Reconstruction
→
Drift
→
Source Hypotheses
→
AIS
→
Evidence Fusion
→
Candidate Ranking

This simultaneously improves:

- Innovation
- Technical Depth
- Feasibility
- Prototype

---

# 16. Priority 2

## Make the Evidence Fusion Explainable

For every candidate show:

### Supporting

Why the candidate fits.

### Contradictory

Why the candidate may not fit.

### Missing

What evidence is unavailable.

### Uncertainty

What the system cannot confidently determine.

This is more valuable than adding another generic AI model.

---

# 17. Priority 3

## Build One Excellent Demonstration

Do not attempt to prove the system works globally.

Instead:

> Demonstrate the complete pipeline on carefully selected historical or controlled cases.

Show exactly:

1. What the satellite saw.
2. What the model detected.
3. How the spill changed.
4. What the environmental model suggests.
5. What source regions are plausible.
6. Which vessels were present.
7. What evidence supports each candidate.
8. What evidence contradicts each candidate.
9. What remains unknown.
10. What the investigator should investigate next.

---

# 18. Judge-Proof Positioning

If a judge asks:

### "Isn't oil-spill detection already available?"

Answer:

> Yes. We are not claiming that basic oil-spill segmentation is new. Our contribution is the investigation workflow that uses the detected spill as the starting point and connects temporal evidence, environmental hindcasting, AIS and cross-source consistency into competing, explainable source hypotheses.

### "Commercial companies already do vessel analytics. Why build this?"

Answer:

> We acknowledge that commercial maritime-intelligence platforms already provide vessel analytics and related capabilities. Our system is not positioned as a replacement for those platforms. It is a satellite-first oil-spill investigation workflow designed around the specific sequence from observed spill to source hypotheses and evidence-aware investigation.

### "Can you prove the vessel caused the spill?"

Answer:

> No. The system does not claim legal attribution. It ranks evidence compatibility between a spill event, source hypotheses and vessel activity, while explicitly showing contradictions and uncertainty. Final attribution remains with the investigator.

### "What if AIS is spoofed?"

Answer:

> We do not claim to prove spoofing. We detect potential inconsistencies between AIS and other available evidence and flag them for investigation.

### "What if your model is wrong?"

Answer:

> The system preserves model confidence, data adequacy, contradictory evidence and uncertainty instead of presenting the result as absolute truth. It also provides a human review and correction mechanism.

### "What is actually novel?"

Answer:

> The novelty is primarily at the system level: competing source hypotheses, cross-source conflict representation and transparent evidence fusion are integrated into one oil-spill investigation workflow rather than treating detection, drift and AIS analysis as isolated components.

### "Do you have confirmed responsible-vessel datasets?"

Answer:

> Public datasets combining satellite observations, environmental forcing, AIS history and independently confirmed responsible vessels are limited. Therefore we will not claim validation that our available data cannot support. We will separate detection validation, physical validation and attribution-case validation.

---

# 19. Final Evaluation Philosophy

The project should optimize for:

> **Credibility over exaggerated novelty.**

A technically honest system with:

- Real data
- Real models
- Real uncertainty
- Real limitations
- One complete working case

is stronger than a project claiming:

> "AI automatically identifies the ship responsible for every oil spill."

---

# 20. Final Target

## Target Score

**45+ / 50**

### Required Conditions

- Real satellite detection
- Real multi-temporal analysis
- Real drift simulation
- Real AIS correlation where data permits
- Transparent evidence fusion
- Working dashboard
- Strong end-to-end demo
- Honest limitation handling
- Clear novelty positioning
- Strong PPT storytelling

---

# 21. Final One-Line Evaluation Position

> **OilTrace AI is not trying to replace maritime investigators; it turns fragmented satellite, environmental and vessel data into an explainable, uncertainty-aware investigation workflow that helps them decide what evidence to investigate next.**
