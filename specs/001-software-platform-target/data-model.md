# Data Model: Osteo Vision Software Platform Target

## Overview

The platform revolves around a de-identified case workspace. Each case contains
inputs, analysis runs, quality flags, regions of interest, review actions, and
an exported evidence bundle.

## Entities

### Case

Represents one reviewable case workspace.

**Fields**
- `case_id`
- `title`
- `status`
- `created_at`
- `updated_at`
- `disclaimer_version`
- `review_summary`

**Relationships**
- Has many `InputAsset`
- Has many `AnalysisRun`
- Has many `ReviewEvent`
- Has many `EvidenceArtifact`

**State**
- `draft`
- `loaded`
- `analyzed`
- `reviewing`
- `reviewed`
- `exported`
- `archived`

### InputAsset

Represents one uploaded or imported source item.

**Fields**
- `input_id`
- `case_id`
- `channel` (`white_light`, `fluorescence`, `sequence`, `video`)
- `path`
- `mime_type`
- `dimensions`
- `timestamps`
- `metadata`
- `quality_flags`

**Relationships**
- Belongs to one `Case`
- May be consumed by many `AnalysisRun`

### AnalysisRun

Represents one processing pass.

**Fields**
- `run_id`
- `case_id`
- `method_id`
- `parameters`
- `status`
- `created_at`
- `duration`
- `notes`

**Relationships**
- Belongs to one `Case`
- Produces many `CandidateRegion`
- Produces many `EvidenceArtifact`

### RegionOfInterest

Represents a user-defined area used for review or quantification.

**Fields**
- `roi_id`
- `case_id`
- `source` (`manual`, `ai`)
- `geometry`
- `label`
- `metrics`
- `review_state`

**Relationships**
- Belongs to one `Case`
- May be linked to one `AnalysisRun`

### CandidateRegion

Represents a suspicious or risk region proposed by the analysis layer.

**Fields**
- `candidate_id`
- `run_id`
- `score`
- `risk_type`
- `confidence`
- `status`
- `explanation`

**Relationships**
- Belongs to one `AnalysisRun`
- May become or map to a `RegionOfInterest`

### ReviewEvent

Represents a reviewer action or correction.

**Fields**
- `event_id`
- `case_id`
- `actor`
- `action`
- `target_id`
- `before_state`
- `after_state`
- `timestamp`

**Relationships**
- Belongs to one `Case`

### EvidenceArtifact

Represents one output file or derived artifact.

**Fields**
- `artifact_id`
- `case_id`
- `run_id`
- `kind`
- `path`
- `checksum`
- `created_at`

**Relationships**
- Belongs to one `Case`
- Usually produced by one `AnalysisRun`

### QualityFlag

Represents an input or case-level usability flag.

**Values**
- `mismatched`
- `weak_signal`
- `overexposed`
- `underexposed`
- `blurred`
- `occluded`
- `low_confidence`

### ClinicalContext

Represents de-identified structured patient variables used for quality assessment and future
bounded patient conditioning.

**Fields**
- `age_years`, `sex_at_birth`
- `comorbidities`, `medications`, plus independent list-completeness review flags
- `labs` with value, unit, reference range, collection time, and abnormal flag
- `deidentification_confirmed`
- `review_status`
- `reviewed_by`, `reviewer_institution`, `review_auth_source`, `reviewed_at`
- `schema_version`, `checksum`

**Rules**
- Only a trusted authenticated reviewer can persist `verified`.
- Missing, stale, invalid-unit, unreviewed, or out-of-distribution values cannot enable a spatial effect.
- An empty comorbidity or medication list is not a verified negative state until its completeness flag is true.

### ClinicalContextAssessment

Represents quality, eligibility, calibration evidence, fallback reasons, and comparison artifacts
for image-only and future patient-conditioned outputs.

### ClinicalFeatureVector

Represents the checksum-bound `clinical-feature-vector-v1` projection of a verified clinical-context
snapshot into the exact feature order declared by a checkpoint.

**Fields**
- feature version, context checksum, feature names, and model input values
- present, missing, and out-of-distribution masks
- recorded input-domain summary and unconsumed recorded-input reason codes
- checkpoint-consumed mask and final spatially-applied mask
- base vector checksum and runtime consumption checksum

**Rules**
- Runtime rebuilds the vector from the verified snapshot and normalized laboratory rows; legacy direct
  `model_features` input cannot override the rebuilt values.
- A checksum, schema, feature-order, rebuild, or context mismatch forces image-only fallback.
- Checkpoint computation and final spatial application remain separately recorded; a proxy checkpoint may
  consume values for engineering evidence while every spatially-applied mask entry remains false.

### BoneActivityEvidence

Represents a trusted bone gate, continuous activity score, low/transition/high/ignore spatial
candidates, uncertainty, thresholds, calibration status, provenance, and physician-review state.

**Rules**
- Spatial candidates require an accepted or modified trusted physician-reviewed bone gate.
- Confidence values cannot be mapped to resection, cure, or recurrence probability without a
  separately defined and validated outcome model.

### NavigationEvidence

Represents L0/L1/L2 registration validation evidence.

**Fields**
- `navigation_level`, `navigation_ready`, `failure_reasons`
- `replay_mode`: `pose_only_engineering` or `dynamic_ar_validation`
- CBCT/STL source and orientation review
- checksum-bound L1 registration-manifest, model, and point-correspondence artifact provenance
- transform path, checksum, matrix, units, direction, and coordinate chain
- camera-calibration artifact path and SHA256, intrinsics, distortion, image size, calibration method,
  calibration date, calibration error, and magnification/working-distance validity range
- camera-calibration schema version, `calibration_table_id`, `nearest_validated_entry_v1`, uniquely identified
  validation entries, and per-frame selected intrinsics evidence
- camera intrinsics identifier, PnP object-to-camera pose, fit reprojection error, independent
  reprojection error, pixel threshold, and composed CBCT-to-camera transform
- L1 threshold-approval protocol, data version, approver, approval time, and FRE/TRE/reprojection snapshot
- admitted MP4 input identifier, SHA256, frame count, dimensions, FPS, FFprobe PTS verification,
  timing mode, median frame interval, and maximum interval deviation
- controlled pose-manifest path and SHA256, per-frame pose, synchronization, magnification, working distance,
  explicit tracking drift and independent source, and independent dynamic target error and source
- independent-measurement artifact and threshold-policy artifact paths, SHA256 values, versions, bindings,
  reviewer identity, approval time, and active-reference state
- 3D projection-point coordinate space, per-frame 2D projection/visibility evidence, positive-depth state,
  visible-point minimum, and projection artifact checksum
- L2 nine-parameter approval snapshot: time offset, drift, TRE proxy, dynamic target error,
  minimum visible projection points, magnification rate, working-distance rate, intrinsics-switch rate,
  and calibration-ambiguity margin
- per-frame and aggregate calibration-transition evidence: selected intrinsics, candidate count, normalized
  selection distance, ambiguity state, magnification/working-distance rates, switch rate, and A/B/A oscillation state
- replay-manifest, frame-state CSV, and optional overlay MP4 paths, frame counts, and SHA256 values
- physician-review identity and time

**Rules**
- Any missing or invalid required evidence forces `navigation_ready=false` and L0 fallback.
- L1 validation requires a checksum-bound registration manifest, parseable model, non-degenerate training points,
  independent validation points, and explicit coordinate/unit/direction binding; manual points remain L0-only.
- `pose_only_engineering` permanently remains L0 and cannot persist a usable AR overlay.
- `dynamic_ar_validation` obtains all safety-critical values from a checksum-bound manifest and persisted
  L1 evidence; client-supplied threshold, calibration, pose, projection, and failure-injection overrides are rejected.
- L2 requires an admitted MP4, verified strictly increasing FFprobe PTS, complete accepted L1 PnP/calibration,
  frame-level 3D-to-2D projection, explicit independent dynamic errors, approved thresholds, trusted physician
  review, and checksum-bound overlay evidence.
- Strict L2 currently accepts verified constant-frame-rate video only; VFR forces L0 and suppresses the overlay.
- Every dynamic frame must select a bounded entry from the checksum-verified v2 calibration table and persist
  the table ID, selection method, and selected intrinsics ID.
- Temporal calibration continuity is derived from FFprobe PTS and fails the complete replay closed on an approved
  rate limit breach, ambiguous calibration selection, or A/B/A intrinsics oscillation.
- A failed dynamic gate removes active L2 references, restores the trusted L1 snapshot, hides the overlay,
  and degrades the complete replay to L0; cancellation preserves existing case evidence.
- L2 identifies offline dynamic AR software engineering validation only; physical phantom accuracy and
  intraoperative navigation performance require separate evidence.

## Validation Rules

- Every exported case MUST have at least one `InputAsset`.
- Every reviewed candidate MUST resolve to a final review state.
- Every `EvidenceArtifact` MUST trace back to a `Case` and, when relevant, an
  `AnalysisRun`.
- A case with unresolved quality issues MUST carry those flags into export.

## State Transitions

- `Case`: `draft` → `loaded` → `analyzed` → `reviewing` → `reviewed` → `exported`
- `ReviewState`: `review_required` → `accepted` | `modified` | `rejected`
- `AnalysisRun`: `queued` → `running` → `completed` | `failed`

## Notes

The model intentionally keeps analysis methods replaceable. The workflow does
not depend on one specific model family, one dataset, or one fusion algorithm.
