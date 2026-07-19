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

### Clinical Context

#### Update Clinical Context

`PUT /cases/{case_id}/clinical-context`

**Request**
- de-identified age, sex at birth, comorbidities, medications, and laboratory values
- value units, reference ranges, and collection times
- de-identification confirmation and requested review status
- optional Bearer review credential

**Response**
- stored clinical context
- effective review status
- reviewer identity, institution, authentication source, and verification time when trusted
- checksum and schema version
- clinical-feature-vector version, feature order, present/missing/out-of-distribution masks, recorded-input
  summary, checksum, and current checkpoint/spatial consumption state when an analysis exists

**Rules**
- unauthenticated and engineering-only sessions cannot persist `verified`
- invalid credentials fail explicitly and cannot silently downgrade a verification request
- empty comorbidity and medication lists remain unknown until their list-completeness flags are confirmed
- runtime feature values are rebuilt from the verified snapshot; client-provided legacy model-feature mappings
  cannot override the checksum-bound vector

### Bone Activity Evidence

Bone-activity evidence is returned with analysis details and exports.

**Response fields**
- trusted bone-gate state and source annotation version
- continuous activity score and uncertainty artifacts
- low, transition, high, and ignore candidates
- thresholds, calibration status, evidence provenance, and safety degradation reasons

### 3D Navigation Evidence

3D evidence is returned with the case and navigation workspace state.

#### Start L1 Static Registration

`POST /three-d/registration-jobs`

**Request**
- `case_id`
- `input_mode=offline_manifest`, `registration_manifest_path`, and `registration_manifest_sha256` for L1 validation
- the checksum-bound registration manifest binds case ID, model path/SHA256, point-correspondence artifact
  path/SHA256, training and independent validation points, coordinate spaces, units, transform direction,
  thresholds, and review evidence
- `input_mode=manual_metadata` is accepted only for L0 static-geometry engineering checks
- source/target coordinate spaces, millimetre thresholds, threshold source, and review state
- optional magnification and working-distance calibration evidence
- `registration_method=rigid_points_with_pnp` additionally requires calibrated 3D object points,
  paired 2D image points, independent 3D/2D validation points, a 3x3 camera matrix, distortion
  coefficients, image dimensions, intrinsics identifier, camera space, and pixel reprojection threshold

**Response**
- background job identifier and status
- completed jobs expose the transform, SHA256, FRE, independent TRE, registration manifest, and persisted case evidence
- calibrated PnP jobs additionally expose the reference-to-camera pose, composed CBCT-to-camera
  transform, PnP fit error, independent reprojection error, intrinsics identifier, and pixel threshold

#### Start L2 Offline Pose Replay

`POST /three-d/pose-replay-jobs`

**Request**
- `case_id`
- `replay_mode=pose_only_engineering` accepts manual metadata or a SHA256-bound offline manifest for L0-only engineering checks
- `replay_mode=dynamic_ar_validation` requires `input_mode=offline_manifest`, `pose_manifest_path`,
  `pose_manifest_sha256`, an admitted case `video_input_id`, and requested physician-review state
- dynamic requests cannot carry frame timestamps, poses, calibration tables, failure injections, thresholds,
  threshold approval, or projection settings outside the checksum-bound manifest

**Dynamic manifest**
- case identifier, video input identifier, video SHA256, and video frame count
- L1 intrinsics identifier, `calibration_table_id`, projection-point coordinate space, 3D projection points,
  and per-frame poses
- per-frame magnification, working distance, tracking state, explicit tracking drift plus independent source,
  and explicit dynamic target error plus independent source
- checksum-bound independent-measurement artifact and threshold-policy artifact paths and SHA256 values
- time-offset, drift, TRE-proxy, dynamic-target-error, minimum-visible-projection-point,
  magnification-rate, working-distance-rate, intrinsics-switch-rate, and calibration-ambiguity parameters
- an approved `osteo-vision-l2-threshold-policy-v2` snapshot with protocol version, data version, approver,
  approval time, and all nine values
- requested physician-review state

**Response**
- background job identifier and status
- completed jobs expose replay mode, frame counts, L2/L0 state, failure reasons, video evidence,
  per-frame calibration selection, projection evidence, threshold approval, replay manifest and SHA256,
  frame-state CSV and SHA256, optional overlay MP4 and SHA256, and persisted case evidence

**Rules**
- pose-only replay is permanently L0 and cannot expose an AR overlay
- dynamic replay reads the complete validated L1 PnP transform, calibration artifact, intrinsics, independent
  TRE, independent reprojection evidence, calibration range, and threshold approval from persisted case evidence;
  clients cannot replace them
- the calibration artifact must use `osteo-vision-camera-calibration-v2`, bind the manifest
  `calibration_table_id`, expose `nearest_validated_entry_v1`, and provide one or more uniquely identified
  validated magnification/working-distance entries; the selected entry is recorded for every frame
- the selected MP4 must have passed case admission; input ID, SHA256, frame count, and manifest binding must match
- independent drift/DTE records must come from the checksum-bound measurement artifact with one-to-one frame,
  case, video, reviewer, source, and timestamp binding
- all nine safety parameters must come from the checksum-bound approved policy artifact and may only preserve or
  tighten the platform safety boundary
- the service obtains strictly increasing per-frame PTS from FFprobe and currently requires verified constant
  frame rate; VFR produces `video_variable_frame_rate_unsupported`, L0, and no overlay
- video SHA256 is rechecked around decoding and overlay generation; output FPS is derived from verified PTS,
  then output frame count, PTS, interval stability, FPS, and duration are checked
- each frame must pass 3D-to-2D projection, positive-depth, in-frame visibility, synchronization,
  explicit tracking-drift, and independent dynamic-target-error gates
- magnification and working-distance rates are computed from adjacent FFprobe PTS values; calibration ambiguity,
  excessive intrinsics-switch rate, or an A/B/A intrinsics oscillation fails the complete replay closed
- an accepted review state requires a trusted physician identity
- successful dynamic replay persists checksum-bound manifest, CSV, and `three_d_ar_overlay` artifacts
- any failed gate clears active L2 references, restores the trusted L1 snapshot, deletes or hides the overlay,
  and degrades the whole replay to L0; canceled jobs do not persist case changes

**Response fields**
- L0/L1/L2 level and `navigation_ready`
- transform path, checksum validation, matrix validation, units, direction, and coordinate chain
- magnification, working distance, calibration range, pose, synchronization, registration error,
  TRE, drift, threshold sources, physician review, and failure reason codes
- admitted-video provenance, FFprobe PTS and frame-rate-mode verification, calibration-table ID and per-frame
  selected intrinsics, visible projection counts, independent dynamic-error sources, threshold approval snapshot,
  and overlay artifact checksum

**Rules**
- any invalid required field produces L0 and `navigation_ready=false`
- missing independent PnP validation, out-of-frame correspondences, non-positive camera depth,
  invalid intrinsics, or reprojection error above threshold produces L0 and `navigation_ready=false`
- missing or mismatched MP4 admission, SHA256, frame count, FFprobe PTS, constant-frame-rate status,
  v2 calibration table, per-frame calibration selection, projection, explicit drift, independent dynamic
  target error, threshold approval, trusted physician review, or overlay checksum
  produces L0 and `navigation_ready=false`
- L1 validation requires a checksum-bound registration manifest; manual or file metadata remains L0-only
- strict dynamic AR safety metadata comes from checksum-bound pose, measurement, and threshold-policy artifacts
  plus persisted L1 evidence

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
