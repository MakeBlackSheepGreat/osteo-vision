# Feature Specification: Osteo Vision Software Platform Target

**Feature Branch**: `[001-software-platform-target]`

**Created**: 2026-06-15

**Status**: Active implementation target; expanded 2026-07-17

**Input**: User description: "Define the project target from `software_focused_realistic_platform_zh.md`."

## Project Scope Alignment *(mandatory)*

**Platform Layer**: cross-cutting

**Competition Value**: supports pseudo-color fluorescence enhancement, AI-assisted review,
and standardized output/collaboration

**Medical Safety Boundary**: the platform remains a research and competition validation platform,
keeps physician review as the final decision layer, and avoids automatic diagnosis or
unsupported clinical claims

**Out of Scope**: device SDKs, hospital integrations, full patient management, and
automatic clinical diagnosis

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a dual-channel case (Priority: P1)

As a surgeon or reviewer, I can open a case containing white-light and fluorescence inputs,
inspect fused evidence, and identify the main suspicious region for review.

**Why this priority**: This is the core value of the platform and the first thing a reviewer
expects to see in a realistic intraoperative workflow.

**Independent Test**: Open a representative sample case and confirm that fused views, quality
flags, and a suspicious-region summary are shown before any export step.

**Acceptance Scenarios**:

1. **Given** valid dual-channel inputs, **When** the case is opened, **Then** the system shows
   fused views, a quality summary, and a candidate-region summary.
2. **Given** a weak, mismatched, or overexposed input pair, **When** the case is opened, **Then**
   the system flags low confidence or low usability instead of presenting a strong conclusion.

---

### User Story 2 - Refine regions with physician review (Priority: P2)

As a reviewer, I can draw or adjust regions of interest, accept or reject candidate regions, and
see the quantitative summary update with the review state.

**Why this priority**: The platform must preserve a human review boundary and let the reviewer
correct or confirm candidate findings.

**Independent Test**: Create or modify a region on a sample case and verify that the review state
and quantitative summary update consistently.

**Acceptance Scenarios**:

1. **Given** a candidate region, **When** the reviewer accepts it, **Then** the region is saved
with an accepted review state.
2. **Given** a candidate region, **When** the reviewer changes the region or thresholds, **Then**
   the updated state is recorded and the summary reflects the change.

---

### User Story 3 - Export an evidence bundle (Priority: P3)

As a researcher or platform administrator, I can export a case package containing the key
visuals, quantitative summary, review states, and report for sharing or later review.

**Why this priority**: The competition requires evidence, not just on-screen analysis.

**Independent Test**: Complete a reviewed sample case and verify that the exported package contains
the required artifacts and reproduces the reviewed state.

**Acceptance Scenarios**:

1. **Given** a reviewed case, **When** export is requested, **Then** the system produces a
complete evidence bundle with the expected artifacts.
2. **Given** a case with unresolved quality issues, **When** export is requested, **Then** the
system includes the warnings and low-confidence state in the exported output.

---

### User Story 4 - Review patient-conditioned analysis evidence (Priority: P1)

As a physician reviewer, I can record de-identified age, sex at birth, comorbidities,
medications, laboratory values, units, collection time, and review status, then compare the
image-only result with a future patient-conditioned result under explicit safety gates.

**Independent Test**: Save clinical context with missing, stale, invalid-unit, and verified
variants and confirm that the API, UI, persistence, and export preserve provenance and fall back
to the image-only result whenever the context is not eligible.

**Acceptance Scenarios**:

1. **Given** an unauthenticated engineering session, **When** clinical context is saved, **Then**
   it remains `review_required` and cannot be promoted to `verified`.
2. **Given** a trusted reviewer identity and valid context, **When** the reviewer verifies the
   record, **Then** reviewer, institution, authentication source, verification time, units, and
   collection times are persisted.
3. **Given** missing, stale, invalid, or out-of-distribution context, **When** analysis runs,
   **Then** the image-only output remains authoritative and the reason for fallback is visible.

---

### User Story 5 - Review a bone-activity spectrum (Priority: P1)

As a physician reviewer, I can inspect low-activity candidates, a transition review zone,
high-activity references, an ignore region, a continuous activity score, and uncertainty within
a trusted reviewed bone surface.

**Independent Test**: Run the rule-derived engineering path with and without a trusted bone gate
and confirm that spatial classes are withheld until the gate is accepted, while all confidence
values retain their calibrated-candidate meaning.

**Acceptance Scenarios**:

1. **Given** no trusted reviewed bone gate, **When** activity evidence is generated, **Then**
   spatial class masks and area percentages remain unavailable.
2. **Given** an accepted or modified trusted bone gate, **When** activity evidence is generated,
   **Then** class candidates, score map, uncertainty, thresholds, and provenance are traceable.
3. **Given** any displayed value such as `0.80`, **When** it appears in the UI or report, **Then**
   it is described as a defined candidate confidence or coverage metric and never as a resection,
   cure, or recurrence probability.

---

### User Story 6 - Validate magnification-aware 3D registration (Priority: P2)

As an engineering or physician reviewer, I can import CBCT/STL evidence plus offline microscope
metadata, inspect L0/L1/L2 status, and receive fail-closed navigation readiness decisions.

**Independent Test**: Exercise valid and corrupted transforms, out-of-range magnification and
working distance, missing calibration, excessive registration error, timing faults, and lost pose
tracking; every failed gate must remove spatial overlay readiness and return to L0.

**Acceptance Scenarios**:

1. **Given** only CBCT/STL and image candidates, **When** no validated coordinate transform is
   available, **Then** the platform presents an L0 unregistered reference.
2. **Given** a phantom registration package with a valid transform, checksum, coordinate chain,
   calibration range, independent error evidence, and physician review, **When** validation runs,
   **Then** the platform may present L1 static registration validation.
3. **Given** synchronized offline pose logs and all L1 evidence, **When** dynamic validation and
   failure injection pass, **Then** the platform may present L2 dynamic AR engineering validation.

---

### Edge Cases

- What happens when the white-light and fluorescence inputs do not match in size, timing, or
  content?
- How does the platform behave when the fluorescence signal is too weak, too bright, blurred, or
  partly blocked?
- What happens when no candidate region is found but the reviewer still needs a report?
- How are conflicting reviewer actions handled when a region is accepted and later modified?
- What happens when export is interrupted before all artifacts are written?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST allow a user to create or open a case from at least one white-light
  input and one fluorescence input, with optional acquisition metadata.
- **FR-002**: The platform MUST show fused visual evidence and quality flags for valid, low-confidence,
  and unusable inputs.
- **FR-003**: The platform MUST allow a reviewer to define one or more regions of interest and view
  quantitative summaries for each region.
- **FR-004**: The platform MUST present candidate regions or risk regions that can be marked as
  review-required, accepted, modified, or rejected.
- **FR-005**: The platform MUST preserve reviewer decisions and case provenance so the final report
  reflects the reviewed state.
- **FR-006**: The platform MUST export an evidence bundle that includes visual outputs, quantitative
  summaries, and a structured report for each completed case.
- **FR-007**: The platform MUST include platform safety-boundary disclaimers and MUST avoid language that
  presents the output as automatic diagnosis or definitive surgical instruction.
- **FR-008**: The platform MUST preserve the same user-facing case workflow when an approved analysis
  method is replaced with another approved analysis method.
- **FR-009**: The platform MUST persist clinical context with de-identification confirmation,
  value units, collection times, review status, reviewer identity, institution, authentication
  source, verification time, schema version, and checksum.
- **FR-010**: Only an authenticated trusted reviewer identity MAY set clinical context to
  `verified`; all other sessions MUST remain `review_required` or `unreviewed`.
- **FR-011**: Patient-conditioned spatial adjustment MUST remain disabled until target-domain,
  patient-paired image, clinical-variable, and physician pixel-label evidence passes independent
  validation, calibration, subgroup audit, and runtime safety gates.
- **FR-012**: The platform MUST preserve image-only output, conditioned output, difference output,
  versioned clinical feature names, present/missing/out-of-distribution masks, checkpoint-consumed
  and spatially-applied masks, eligibility decision, unconsumed recorded-input reasons, and fallback
  reasons whenever patient conditioning is evaluated.
- **FR-013**: Bone-activity spatial candidates MUST be clipped to a trusted accepted or modified
  physician-reviewed bone gate; unreviewed or engineering-only gates MUST trigger safe degradation.
- **FR-014**: Bone-activity evidence MUST support low, transition, high, and ignore classes plus a
  continuous score, uncertainty, thresholds, calibration status, and provenance.
- **FR-015**: The device overlay channel MAY support display and quality review but MUST NOT be
  treated as independent ground truth or a default training label.
- **FR-016**: 3D evidence MUST expose L0, L1, and L2 states and MUST remove navigation readiness
  whenever required transform, calibration, pose, synchronization, error, drift, scale, or
  physician-review evidence is missing or invalid.
- **FR-017**: Registration transforms MUST be validated for file existence, checksum, supported
  format, finite invertible 4x4 matrix content, units, direction, and coordinate-chain continuity.
- **FR-018**: Magnification and working distance MUST be checked against the calibration range used
  by the selected camera model.
- **FR-019**: Registration error thresholds MUST carry a source and review record; unvalidated
  threshold values cannot enable L1 or L2 readiness.
- **FR-020**: Enterprise SDKs and private device interfaces MUST remain outside the software
  dependency chain; equivalent metadata can enter through files, manifests, or manual entry.
- **FR-021**: A negative comorbidity or medication state MUST only be treated as reviewed input when
  the corresponding list-completeness flag is explicitly confirmed; an empty unreviewed list MUST
  remain missing.

### Key Entities *(include if feature involves data)*

- **Case**: A single de-identified case workspace, including inputs, status, and outputs.
- **Input Pair**: The white-light and fluorescence materials used for a case, plus optional metadata.
- **Region of Interest**: A user-defined area selected for review or quantification.
- **Candidate Region**: A proposed suspicious or risk region awaiting review.
- **Review State**: The current reviewer decision for a region or case.
- **Quality Flag**: A status that describes input usability, signal strength, alignment, or artifact risk.
- **Evidence Bundle**: The exported package of visuals, summaries, and report material for a case.
- **Analysis Run**: A single processing pass that produces the visible outputs and summary results.
- **Clinical Context**: De-identified patient-level structured variables and their review evidence.
- **Clinical Context Assessment**: Eligibility, quality, fallback, checksum, and influence summary.
- **Bone Activity Evidence**: Reviewed bone gate, continuous score, spatial candidate classes,
  uncertainty, and calibration metadata.
- **Navigation Evidence**: CBCT/STL source, coordinate transforms, calibration, microscope metadata,
  pose/synchronization evidence, error thresholds, physician review, and L0/L1/L2 state.

### Evidence Artifacts *(include if feature produces outputs)*

- **Fusion View**: The combined white-light and fluorescence visual evidence for a case.
- **Quantitative Summary**: The measured summary for selected regions and the whole case.
- **Report Package**: The structured case report and export bundle for later review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In representative test cases, users can complete the full import → review → export
  flow with all required artifacts present.
- **SC-002**: In tested weak-signal, mismatched, overexposed, or blurred cases, the platform marks
  the case as low-confidence before final export.
- **SC-003**: Reviewers can accept, modify, or reject candidate regions, and the exported report
  reflects the final review state.
- **SC-004**: Every exported case includes fused visual evidence, a quantitative summary, a review
  record, and a platform safety-boundary disclaimer.
- **SC-005**: No checked output contains unsupported automatic diagnosis language or claims of
  definitive clinical decision-making.
- **SC-006**: An unauthenticated session cannot persist `verified` clinical context, and a trusted
  verification records all required identity and timing fields.
- **SC-007**: Every ineligible clinical-context test case produces an image-only fallback with a
  machine-readable reason code and no patient-conditioned spatial effect.
- **SC-008**: Bone-activity spatial masks remain unavailable without a trusted reviewed bone gate;
  accepted or modified gates produce traceable class and score evidence.
- **SC-009**: All tested malformed, missing, non-invertible, checksum-mismatched, direction-invalid,
  or unit-invalid transforms result in L0 and `navigation_ready=false`.
- **SC-010**: All tested out-of-range magnification/working-distance, excessive registration error,
  synchronization, pose, and drift faults result in fail-closed degradation.
- **SC-011**: Public and proxy datasets used for these capabilities retain source, license,
  checksum, domain boundary, and `training_eligible=false` until explicit admission.

## Assumptions

- The initial target uses offline or uploaded dual-channel inputs rather than live device acquisition.
- A human reviewer remains part of every case workflow.
- Single-frame and short-sequence cases are both valid inputs for the target platform.
- The selected analysis method may change over time without changing the case-level workflow.
- Model retraining follows completion of data contracts, API, persistence, UI comparison,
  reporting, and fail-closed engineering validation.
