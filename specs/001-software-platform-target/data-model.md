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
