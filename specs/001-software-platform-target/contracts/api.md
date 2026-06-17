# Contract: Osteo Vision Case Workflow API

## Purpose

Define the case-review and export contract for the browser-based platform.

## Resources

### Case

Represents a de-identified review workspace.

#### Create Case

`POST /cases`

**Request**
- `title`
- `disclaimer_version`
- optional case metadata

**Response**
- `case_id`
- `status`
- `created_at`

#### Get Case

`GET /cases/{case_id}`

**Response**
- case metadata
- input inventory
- current quality flags
- review summary
- artifact list

### Inputs

#### Add Inputs

`POST /cases/{case_id}/inputs`

**Request**
- one or more white-light or fluorescence assets
- optional acquisition metadata

**Response**
- `input_ids`
- detected quality flags
- usability summary

### Analysis Run

#### Start Analysis

`POST /cases/{case_id}/analysis-runs`

**Request**
- selected inputs
- analysis parameters
- optional ROI hints

**Response**
- `run_id`
- `status`
- initial artifacts or job reference

#### Get Analysis Run

`GET /analysis-runs/{run_id}`

**Response**
- run status
- candidate regions
- fused outputs
- quantitative summary
- warnings

### Review

#### Update Region

`PATCH /cases/{case_id}/regions/{region_id}`

**Request**
- `review_state`
- optional geometry or labels
- reviewer notes

**Response**
- updated review state
- updated summary

#### Add Review Event

`POST /cases/{case_id}/review-events`

**Request**
- action
- target identifier
- before/after state

**Response**
- stored event reference

### Export

#### Export Evidence Bundle

`POST /cases/{case_id}/exports`

**Request**
- export format
- selected artifacts

**Response**
- bundle path or bundle identifier
- report path
- artifact manifest

## Contract Rules

- Every response that surfaces an analysis result MUST carry the review boundary
  and disclaimer context.
- Every export MUST include traceable artifacts, quantitative output, and review
  state.
- Low-confidence or unusable input states MUST be explicit in the contract.

## Artifact Types

- `overlay`
- `heatmap`
- `normalized_fluorescence`
- `roi_mask`
- `quantification_csv`
- `report_json`
- `report_md`
- `evidence_bundle`

## Notes

This contract is shaped for the target platform and may be refined when the
frontend/backend split is implemented.
