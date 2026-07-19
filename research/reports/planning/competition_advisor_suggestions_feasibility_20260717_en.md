# Patient-Safety-First Feasibility Study of the Competition, Clinical, and Academic Suggestions

Date: 2026-07-17
Project: Intelligent fluorescence platform software for jaw osteomyelitis
Purpose: competition proposal, innovation rationale, and future joint validation with the company and hospital
Medical boundary: all outputs are research-validation decision-support results requiring physician review. The platform shall not control resection tools or provide an independent diagnosis.

## 1. Executive conclusion

The suggestions can form a coherent and competitive proposal:

1. Patient-safety-gated interpretation of color, ICG fluorescence, and violet-blue bone-activity fluorescence.
2. Clinical-context-conditioned risk calibration and uncertainty estimation.
3. Necrotic candidate, transition/review, and viable candidate regions expressed as a continuous viability spectrum.
4. Microscope calibration and CBCT/3D reference mapping that use magnification, working distance, and synchronized image streams.
5. Automatic fallback to raw images whenever registration, tracking, image quality, or model reliability is insufficient.

| Direction | Feasibility | Competition role | Main safety condition |
| --- | --- | --- | --- |
| Tetracycline/doxycycline bone fluorescence | Medium-high at proposal level | Mechanistic benchmark and future research enhancement | No patient dosing during the competition; prioritize autofluorescence, phantoms, and ex-vivo validation |
| Evans blue | Low for direct use of the original dye | Albumin-binding/permeability design inspiration or preclinical comparator | Low current clinical availability and weak evidence for dead-bone selectivity |
| Demographics, comorbidities, and laboratory data in the model | Technically feasible and data-intensive | Clinical-prior-conditioned segmentation and calibration | Clinical variables provide priors and calibration; image evidence and physician review determine spatial boundaries |
| Necrotic, transition, and viable bone outputs | Feasible and highly innovative | Continuous viability map, three candidate classes, and an uncertainty corridor | The transition label requires reproducible physician/pathology criteria and an abstention mechanism |
| “80% clean resection” | Unsupported by current evidence | Replace with calibrated probability, risk coverage, and review priority | Model confidence cannot be presented as complete-resection, cure, or recurrence probability |
| Magnification/working distance with 3D models | Feasible by maturity level | L0-L2 reference mapping and engineering validation | Full navigation also requires pose tracking, patient registration, synchronization, and error gates |
| Color, fluorescence, and device-overlay outputs | High software value | Synchronized evidence and quality control | Use the raw color and fluorescence streams for algorithms; use the device overlay for visualization and consistency checks |

## 2. Alignment with the official competition documents

The official problem statement requires a complete technical solution covering:

- A new fluorescent contrast-agent concept with mechanism, selectivity, validation evidence, and microscope compatibility.
- Multisource white-light/fluorescence acquisition, registration, fusion, real-time display, or navigation support.
- AI-assisted recognition using white-light and fluorescence information, presented through overlays, risk markings, or decision support.

Allowed deliverables include a technical report, algorithm/model design, validation evidence, and software/system prototypes. A proposal and report can serve as the main submission. Feasibility carries 30% of the score, so the report should include low-risk evidence such as fluorescence-standard or phantom measurements, three-stream synchronization checks, software outputs, a 3D-printed mandible registration plan, and a safety failure matrix.

The official device document confirms 1.3x-17x total magnification, 6.2:1 continuous zoom, a 200-630 mm working distance, 3840x2160 imaging, USB3.0 storage, JPEG images, and MP4 video. Its fluorescence description focuses on ICG excitation around 750-810 nm and emission around 830 nm.

The 2026-07-17 discussion added magnification, working-distance metadata, and color/fluorescence/overlay outputs. The submission should mark the interface details as pending confirmation: microscope model, firmware, SDK, timestamps, synchronization, exposure/gain, cropping/scaling, and geometric calibration.

## 3. Patient-safety architecture

Patient safety should be the top-level design constraint and a visible innovation.

### Mandatory controls

- Outputs represent candidate regions, risk, calibrated confidence, and uncertainty.
- Raw color imagery remains visible, and every overlay has an explicit off switch.
- Poor quality, out-of-distribution data, failed registration, lost tracking, and stream mismatch trigger abstention or fallback.
- Physician confirmation is mandatory for reports, annotation feedback, and training eligibility.
- The competition phase excludes investigational patient dosing.
- Clinical data follow data-minimization, de-identification, traceability, and purpose-limitation rules.
- The platform shall not control instruments or create an autonomous final resection boundary.

### Fallback sequence

```text
Raw images available
  -> stream and quality checks passed
  -> AI signal prompts available
  -> physician review available
  -> 3D reference overlay allowed when registration evidence is complete
  -> navigation exploration allowed when tracking, synchronization, error, and physician gates all pass
```

Any missing critical evidence returns the system to raw images, a fluorescence heatmap, or an unregistered 3D reference view with a visible reason code.

## 4. Tetracycline/doxycycline under UV or violet-blue excitation

### Mechanism and spectrum

Tetracyclines bind calcium and accumulate in mineralizing or remodeling bone. Studies in jaw osteonecrosis and orthopedic infection commonly report bright green or yellow-green fluorescence in viable/remodeling bone and weak or absent fluorescence in necrotic bone. Drug deposition, collagen structure, osteocyte lacunae, and bone autofluorescence all contribute to the signal.

The proposal should use the precise term “near-UV/violet-blue excitation.” Reported systems include 390-410 nm violet illumination and the 400-460 nm VELscope band. Bone fluorescence from tetracycline derivatives is commonly detected in the 500-560 nm range, with peaks around 529 nm reported for tetracycline/doxycycline bone sections.

A 405-460 nm engineering path offers a better initial safety profile. A 365-400 nm UVA path requires stricter controls for ocular, skin, and operative-field radiant exposure.

### Evidence strength

- A 2017 randomized feasibility study included 40 MRONJ patients and found high short-term mucosal-integrity rates in both autofluorescence and tetracycline-fluorescence groups.
- A 2020 mini-pig study found green fluorescence in viable bone and weak/absent fluorescence in necrotic bone, with similar macroscopic boundaries from autofluorescence and tetracycline fluorescence.
- A 2021 three-case septic-hip revision series found histopathology consistent with chronic osteomyelitis in resected nonfluorescent bone.
- A 2025 scoping review summarized 51 patients and 57 lesions, with reported surgical success rates around 89%-100%; sample sizes and study designs remain limited.

These findings support a bone-activity/necrosis boundary aid. Jaw-osteomyelitis target-domain validation remains necessary.

### Safety and regulatory issues

The current doxycycline label highlights tetracycline hypersensitivity, pregnancy/tooth-development concerns, photosensitivity including artificial UV exposure, esophageal irritation, gastrointestinal effects, C. difficile-associated diarrhea, severe skin reactions, intracranial hypertension, and relevant drug interactions. Imaging-driven antibiotic exposure also raises antimicrobial-stewardship concerns.

Published regimens such as doxycycline 100 mg twice daily for seven days are literature evidence only. They shall not become a project dosing recommendation.

### Microscope compatibility

The official ICG optical path cannot directly capture violet-blue bone fluorescence. The extension requires:

- Controlled 405/450 nm excitation and exposure logging.
- Approximately 500-560 nm emission filtering and verified camera sensitivity.
- Tests for excitation leakage, white-light crosstalk, blood absorption, smoke, and saturation.
- Interlocks, exposure timing, power limits, and emergency shutdown.
- Spatial and temporal calibration across color, violet-blue bone fluorescence, and ICG NIR fluorescence.

### Competition recommendation

Use tetracycline/doxycycline as a mechanistic benchmark and future research enhancement. Keep the new-probe concept as a separate design contribution. A safe staged strategy is:

1. Drug-free bone autofluorescence for the first violet-blue validation.
2. ICG as the perfusion and temporal baseline.
3. Doxycycline pre-labeling as a future ethics-approved research path.
4. A new bone-affinity/infection-recognition probe designed with the tetracycline mechanism and ICG device window as references.

## 5. Evans blue

Evans blue strongly binds serum albumin and has a long history in plasma-volume, vascular-permeability, protein-leakage, and lymphatic studies. Literature reports strong absorption near 620 nm and albumin-associated fluorescence near 680 nm. Derivatives, nanoparticles, and radiolabeled forms have been studied for albumin hitchhiking and necrosis-related imaging.

Direct use for jaw dead-bone mapping has major gaps:

- The original dye has weak evidence for jaw-bone or dead-bone selectivity.
- Inflammation, hyperemia, surgical wounds, and vascular leakage can all alter albumin distribution.
- Surface imaging near 680 nm is possible; penetration and background control are generally less favorable than the ICG NIR window.
- A separate red excitation/detection path and a new formulation, pharmacokinetic, toxicology, and regulatory assessment are required.
- A historical FDA injection product is discontinued, and current DailyMed searches return no marketed Evans blue label.

Keep the original dye outside the patient-use mainline. Suitable competition roles are albumin-binding/permeability probe inspiration and in-vitro albumin, tissue-phantom, or compliant preclinical comparison. Evidence for a modified derivative must remain tied to that derivative's actual chemistry and validation.

## 6. Clinical structured data in the segmentation model

Age, sex, comorbidities, and laboratory measurements can be combined with color, fluorescence, temporal curves, and CBCT features.

```text
Color-image encoder
Fluorescence image/video encoder
Clinical tabular encoder
  -> late fusion / FiLM / cross-attention
  -> bone-gating head
  -> viability-spectrum and three-class segmentation head
  -> risk-calibration and uncertainty head
```

Recommended inputs include continuous age, explanatory age bands, sex definitions, diabetes, vascular disease, renal dysfunction, immunosuppression, oncology/radiotherapy/antiresorptive history, WBC, neutrophils, CRP, ESR, hemoglobin, albumin, glucose/HbA1c, renal function, measurement units, collection time, and missingness indicators.

Safety design:

- Image features drive spatial boundaries; clinical data adjust priors, calibration, prioritization, and uncertainty.
- Missing clinical data trigger an image-only fallback with a visible missing-data state.
- Splits occur by patient, institution, and time.
- Ablations compare image-only, dual-image, and image-plus-clinical models.
- Subgroup sensitivity, false-positive rate, calibration, and abstention are reported.
- Shortcut learning from age, sex, hospital, or treatment patterns is explicitly audited.
- During the small-data phase, clinical variables mainly condition the calibration head.

Suggested innovation title: **Clinical-prior-conditioned multimodal bone-viability segmentation and risk calibration**.

## 7. Necrotic, transition, and viable bone

“Partially dead bone” lacks a standardized reproducible label. Use “transition zone,” “uncertain viability,” or “boundary-risk region.”

Recommended outputs:

- `necrotic_candidate_mask`
- `transition_zone_mask`
- `viable_candidate_mask`
- `viability_score_map`
- `uncertainty_map`
- `review_priority_map`

The repository already defines `bone_gate_mask`, `fluorescence_signal_mask`, `risk_mask`, and `uncertain_mask`. The near-term implementation can express the transition zone through `risk_mask + uncertain_mask`; a formal three-class model should follow real physician annotation and pathology mapping.

Reference evidence should combine physician judgment, inter-rater agreement, color appearance, bone texture and punctate bleeding, ICG temporal metrics, violet-blue fluorescence, spatially mapped histopathology/microbiology, and longitudinal outcomes recorded as separate endpoints.

Suitable model families include three-class softmax segmentation, ordinal/continuous viability regression, probabilistic U-Net, ensemble/TTA or evidential uncertainty, multi-rater learning, temperature scaling, Brier/ECE evaluation, and conformal risk-coverage analysis.

## 8. Safe replacement for “80% clean resection”

“80% clean resection” combines complete removal, histologic margins, healing, infection control, and recurrence. Current data cannot validate this compound endpoint. A model probability also depends on its calibration target.

Safe competition language includes:

- “Calibrated confidence of 0.80 that this region belongs to the necrotic-bone candidate class.”
- “The system generates a candidate boundary corridor at a target validation coverage of 80%.”
- “The yellow area is an uncertain boundary region requiring physician review.”
- “Out-of-distribution or low-quality factors reduced confidence and expanded the review region.”
- “Candidate coverage, residual-risk prompt, and viable-bone inclusion risk are displayed separately.”

Report necrotic-candidate recall, viable-bone inclusion rate, transition-zone coverage, boundary distance, per-class Dice/IoU, Boundary F1, HD95, ECE, Brier score, risk-coverage curves, physician edit area, review time, and acceptance rate.

## 9. Magnification, working distance, and 3D navigation

Magnification and working distance provide scale, focal-length relationships, and camera-intrinsic priors. Full 3D registration additionally requires microscope 6-DoF pose, patient/mandible coordinates, CBCT coordinates, and continuous error monitoring. A monocular stream can project candidates onto a known bone surface or reference plane; reliable depth requires stereo, structured light, surface scanning, or another depth constraint.

Required transform chain:

```text
CBCT and physician-reviewed segmentation
  -> CBCT-to-patient bone registration
  -> patient bone to microscope tracking space
  -> microscope extrinsics and zoom/focus-dependent intrinsics
  -> 4K color/fluorescence image plane
  -> 2D candidate to 3D bone-surface reference mapping
```

Required evidence includes camera intrinsics and distortion, zoom/focus/working-distance calibration, microscope tracking, dental-splint/fiducial/bone-surface registration, stream timestamps, depth constraints, FRE/TRE, reprojection error, drift, latency, and recalibration logs.

Risks include zoom/focus changes, microscope or patient movement, mandibular motion relative to the skull, blood/smoke/instrument occlusion, reflection, defocus, and surface changes after resection.

### Navigation maturity

| Level | Definition | Recommended claim |
| --- | --- | --- |
| L0 | CBCT/STL and fluorescence candidates displayed as unregistered references | Current supported state |
| L1 | Static registration and single-frame projection on a 3D-printed mandible | Direct competition validation target |
| L2 | Dynamic microscope AR with tracking, zoom/distance calibration, synchronized streams, drift, and failure injection | Requires company interfaces and tracking hardware |
| L3 | Ethics-approved clinical navigation exploration | Requires hospital, company, regulatory, and physician participation |

The competition proposal should commit to L0/L1 and describe the L2 validation design. L3 remains a future joint-research path.

The AR overlay must hide or freeze when calibration limits, tracking, synchronization, TRE/drift, latency, image quality, or anatomy-change gates fail. Raw imagery remains available.

## 10. Color, fluorescence, and device-overlay streams

The streams have distinct roles:

- Color: anatomy, bone texture, instruments, bleeding, and surface boundaries.
- Raw fluorescence: intensity, background correction, time curves, and quantification.
- Device overlay: physician display, device-algorithm quality control, and evidence comparison.

The device overlay often contains pseudocolor, opacity, resampling, and internal processing. Simultaneous use with both raw streams can create duplicated information, leakage, and vendor-specific shortcuts. The primary model should use raw color and raw fluorescence. The overlay should support visualization, quality gates, and device-consistency checks.

The company should confirm synchronization mode, original intensity preservation, automatic gain, LUT/opacity, registration rules, optical geometry, resolution, distortion, and whether MP4 metadata can carry stream ID, zoom, working distance, exposure, gain, and timestamps.

## 11. Recommended innovation package

1. **Patient-safety-first three-source multispectral bone-activity interpretation**: color anatomy, ICG perfusion, and violet-blue autofluorescence/research doxycycline evidence.
2. **Clinical-prior-conditioned individualized risk calibration**: patient context adjusts ranking, calibration, and distribution-shift detection.
3. **Continuous bone-viability spectrum and transition zone**: necrotic candidate, transition region, viable candidate, calibrated uncertainty, and physician review.
4. **Magnification/working-distance-aware microscope-to-3D reference mapping**: dynamic calibration combined with microscope tracking, patient bone coordinates, and CBCT surfaces.
5. **Auditable safety-degraded navigation**: any registration, tracking, synchronization, image-quality, or model-reliability failure removes spatial overlays and records the reason.

## 12. Action classification

### Directly actionable now

- Add the safety state machine, three-stream contract, and L0-L3 navigation maturity to the proposal.
- Use the existing `risk_mask` and `uncertain_mask` for a transition-zone demonstration.
- Define the clinical-variable dictionary, missingness protocol, time windows, and model interface.
- Design 405-460 nm autofluorescence phantom/ex-vivo tests and 500-560 nm detection requirements.
- Design L1 registration on a 3D-printed mandible with fiducials or a dental splint.

### Requires company, hospital, or laboratory support

- Obtain the microscope model, SDK, zoom/distance interface, and original-stream specification.
- Obtain optical-power, filtering, sensor-response, synchronization, and distortion data.
- Conduct ex-vivo bone, animal, pathology, and multi-physician label validation.
- Obtain ethics, pharmacy, device, and physician approval for any human investigational use.

### Risk-reduction or rationale only

- Bone autofluorescence reduces investigational drug exposure.
- ICG supplies complementary perfusion evidence.
- Evans blue supplies albumin-binding/permeability design inspiration.
- General multimodal, probabilistic-segmentation, and navigation literature supports methodological feasibility.

### No reliable substitute currently available

- Target-domain intraoperative color/fluorescence data for jaw osteomyelitis.
- Spatially mapped physician three-class labels and pathology references.
- Real microscope interfaces and calibration data.
- Clinical follow-up evidence for complete resection, cure, or recurrence probabilities.

## 13. Key references

1. Local official competition PDF: `HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf`, pp. 3-4.
2. Local official device PDF: `research/literature/inventory/official/competition_official_technical_document_20260527.pdf`, pp. 1-2.
3. [Pautke et al., PMID 20006166](https://pubmed.ncbi.nlm.nih.gov/20006166/), DOI 10.1016/j.joms.2009.05.442.
4. [Ristow et al., randomized feasibility study, PMID 27856150](https://pubmed.ncbi.nlm.nih.gov/27856150/), DOI 10.1016/j.ijom.2016.10.008.
5. [Ristow et al., mini-pig study, PMID 32444918](https://pubmed.ncbi.nlm.nih.gov/32444918/), DOI 10.1007/s00784-020-03332-2.
6. [Eight tetracycline derivatives for bone labeling, PMCID PMC2913014](https://pmc.ncbi.nlm.nih.gov/articles/PMC2913014/), DOI 10.1111/j.1469-7580.2010.01237.x.
7. [Septic-hip tetracycline bone labeling, PMID 34084695](https://pubmed.ncbi.nlm.nih.gov/34084695/), DOI 10.5194/jbji-6-85-2021.
8. [DailyMed doxycycline label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4dc319c1-b7ef-40e4-9e66-fb24cfdefea8).
9. [In vivo albumin labeling with Evans blue, PMCID PMC4291643](https://pmc.ncbi.nlm.nih.gov/articles/PMC4291643/), DOI 10.1073/pnas.1414821112.
10. [Evans blue nanocarriers, PMID 25787737](https://pubmed.ncbi.nlm.nih.gov/25787737/), DOI 10.1007/s13346-013-0139-x.
11. [openFDA Evans blue NDA 008041 query](https://api.fda.gov/drug/drugsfda.json?search=products.active_ingredients.name:%22EVANS%20BLUE%22&limit=1).
12. [DailyMed Evans blue query](https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name=evans%20blue).
13. [Probabilistic U-Net uncertainty, PMID 38878632](https://pubmed.ncbi.nlm.nih.gov/38878632/), DOI 10.1016/j.compmedimag.2024.102403.
14. [Multi-rater Prism, PMID 39155196](https://pubmed.ncbi.nlm.nih.gov/39155196/), DOI 10.1016/j.scib.2024.06.037.
15. [Clinical-use evaluation of uncertainty, PMID 40466495](https://pubmed.ncbi.nlm.nih.gov/40466495/), DOI 10.1016/j.compmedimag.2025.102574.
16. [Guo et al., calibration](https://proceedings.mlr.press/v70/guo17a.html).
17. [Angelopoulos and Bates, conformal prediction](https://doi.org/10.1561/2200000101).
18. [Surgical microscope review, PMID 33398948](https://pubmed.ncbi.nlm.nih.gov/33398948/), DOI 10.1117/1.JBO.26.1.010901.
19. [Zoom-lens calibration, PMID 37247472](https://pubmed.ncbi.nlm.nih.gov/37247472/), DOI 10.1016/j.cmpb.2023.107618.
20. [Structured-light microscope AR registration, PMID 39806119](https://pubmed.ncbi.nlm.nih.gov/39806119/), DOI 10.1007/s11517-025-03288-z.
21. [IBIS image-guided neurosurgery, PMID 27581336](https://pubmed.ncbi.nlm.nih.gov/27581336/), DOI 10.1007/s11548-016-1478-0.
22. [ICG angiography with AR, PMID 32640326](https://pubmed.ncbi.nlm.nih.gov/32640326/), DOI 10.1016/j.wneu.2020.06.219.
23. [Markerless maxillofacial AR, PMID 41867658](https://pubmed.ncbi.nlm.nih.gov/41867658/), DOI 10.3389/fbioe.2023.1276338.

## 14. Final recommendation

Organize the submission around one integrated narrative:

> Patient safety governs contrast agents, imaging, AI, and navigation. The platform combines color anatomy, ICG perfusion, violet-blue bone-activity signals, and clinical context to produce necrotic candidates, a transition corridor, viable candidates, and calibrated uncertainty. Magnification and working distance feed dynamic microscope calibration, while CBCT reference mapping and safety fallback establish a traceable route toward future engineering navigation and clinical collaboration.

Near-term priorities are the safety architecture and competition narrative, microscope interface confirmation, autofluorescence/phantom and L1 registration protocols, a clinical-variable schema, transition-zone semantics, and later target-domain calibration with physician review.
