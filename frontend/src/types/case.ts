import type { ReviewActorIdentity } from "@/types/reviewIdentity";

export type CaseStatus = "draft" | "loaded" | "analyzed" | "reviewing" | "reviewed" | "exported" | "archived";

export type InputChannel = "white_light" | "fluorescence" | "device_overlay" | "sequence" | "video";

export interface ClinicalLabResult {
  name: string;
  value: number | string;
  unit?: string | null;
  reference_range?: string | null;
  measured_at?: string | null;
  abnormal_flag: "low" | "normal" | "high" | "unknown";
}

export interface ClinicalContext {
  age_years?: number | null;
  age_group: "pediatric" | "young_adult" | "middle_aged" | "older_adult" | "unknown";
  sex_at_birth: "female" | "male" | "intersex" | "unknown" | "not_recorded";
  comorbidities: string[];
  comorbidities_reviewed?: boolean;
  medications: string[];
  medications_reviewed?: boolean;
  labs: ClinicalLabResult[];
  source_organization?: string | null;
  recorded_by?: string | null;
  recorded_at?: string | null;
  review_status: "unreviewed" | "review_required" | "verified";
  verified_by?: ReviewActorIdentity | null;
  verified_at?: string | null;
  deidentified: boolean;
  clinical_use_boundary:
    | "risk_prior_and_calibration_only_no_spatial_boundary_effect"
    | "restricted_spatial_conditioning_with_physician_review";
}

export interface ClinicalContextAssessment {
  schema_version?: string;
  assessed_at?: string;
  clinical_context_revision?: number | null;
  clinical_context_checksum?: string | null;
  clinical_context_assessment_checksum?: string | null;
  clinical_context_snapshot?: Partial<ClinicalContext>;
  clinical_context_quality?: {
    status?: string;
    review_status?: string;
    deidentified?: boolean;
    missing_critical_fields?: string[];
    issues?: string[];
    usable_lab_count?: number;
    recorded_lab_count?: number;
  };
  normalized_labs?: Array<{
    source_name?: string;
    canonical_name?: string | null;
    canonical_value?: number | null;
    canonical_unit?: string | null;
    freshness_status?: string;
    unit_status?: string;
    issues?: string[];
  }>;
  rule_based_risk_summary?: {
    available?: boolean;
    contributing_factors?: Array<Record<string, unknown>>;
    factor_count?: number;
    review_required?: boolean;
  };
  calibration_evidence?: { applied?: boolean; status?: string; reasons?: string[] };
  clinical_feature_vector?: {
    schema_version?: string;
    feature_version?: string;
    feature_names?: string[];
    present_mask?: boolean[];
    missing_mask?: boolean[];
    ood_mask?: boolean[];
    eligible_feature_names?: string[];
    missing_feature_names?: string[];
    ood_feature_names?: string[];
    vector_checksum?: string;
    [key: string]: unknown;
  };
  spatial_effect_applied?: boolean;
}

export type ReviewState = "review_required" | "accepted" | "modified" | "rejected";

export interface CaseInputDraft {
  channel: InputChannel;
  path: string;
  mime_type?: string | null;
  metadata?: Record<string, unknown>;
}

export interface QualityFlag {
  code: string;
  message: string;
  blocking: boolean;
  details: Record<string, unknown>;
}

export interface CaseInputAsset {
  input_id: string;
  channel: InputChannel;
  path: string;
  mime_type?: string | null;
  dimensions: number[];
  timestamps?: string[];
  metadata: Record<string, unknown>;
  quality_flags: QualityFlag[];
}

export interface CandidateRegion {
  candidate_id: string;
  run_id: string;
  score?: number | null;
  risk_type: string;
  confidence?: number | null;
  status: ReviewState;
  explanation?: string | null;
  metadata?: Record<string, unknown>;
}

export interface NavigationFrameSelection {
  caseId: string;
  candidateId: string;
  frameKey: string;
  frameIndex: number | null;
  timestampSec: number | null;
}

export interface ThreeDEvidenceMarkup {
  id?: string | null;
  label?: string | null;
  type?: string | null;
  source_label?: string | null;
  target_label?: string | null;
  source_point_mm?: number[] | Record<string, unknown> | null;
  target_point_mm?: number[] | Record<string, unknown> | null;
  residual_mm?: number | string | null;
  status?: string | null;
}

export interface ThreeDEvidenceTransformStep {
  name?: string | null;
  from_space?: string | null;
  to_space?: string | null;
  path?: string | null;
  error_mm?: number | string | null;
  status?: string | null;
}

export interface ThreeDScenePoint {
  x?: number | string | null;
  y?: number | string | null;
  z?: number | string | null;
}

export interface ThreeDSceneCurve {
  id?: string | null;
  label?: string | null;
  source?: string | null;
  coordinate_space?: string | null;
  points_mm?: Array<ThreeDScenePoint | number[]> | null;
  display_points?: Array<ThreeDScenePoint | number[]> | null;
}

export interface ThreeDScenePlane {
  id?: string | null;
  label?: string | null;
  source?: string | null;
  origin_mm?: ThreeDScenePoint | number[] | null;
  normal?: ThreeDScenePoint | number[] | null;
  display_position?: ThreeDScenePoint | number[] | null;
  display_rotation?: ThreeDScenePoint | number[] | null;
  display_scale?: ThreeDScenePoint | number[] | null;
  status?: string | null;
}

export interface ThreeDSceneManifest {
  schema_version?: string | null;
  source_project?: string | null;
  scene_id?: string | null;
  coordinate_space?: string | null;
  model_bounds_mm?: {
    min?: number[] | null;
    max?: number[] | null;
    center?: number[] | null;
    size?: number[] | null;
  } | null;
  mandibular_curve?: ThreeDSceneCurve | null;
  review_planes?: ThreeDScenePlane[] | null;
  fibula_reference?: {
    label?: string | null;
    display_curve?: Array<ThreeDScenePoint | number[]> | null;
    segment_lengths_mm?: number[] | null;
    miter_planes?: ThreeDScenePlane[] | null;
  } | null;
  slice_views?: Partial<Record<"axial" | "coronal" | "sagittal", { axis?: string | null; base_mm?: number | string | null; note?: string | null }>> | null;
  migration_notes?: string[] | null;
}

export interface ThreeDSceneV2Node {
  id?: string | null;
  type?: string | null;
  role?: string | null;
  name?: string | null;
  path?: string | null;
  format?: string | null;
  source?: string | null;
  derived_from?: string[] | null;
  review_status?: string | null;
  display?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface ThreeDSceneV2Markup {
  id?: string | null;
  type?: string | null;
  role?: string | null;
  name?: string | null;
  review_status?: string | null;
  source?: string | null;
  [key: string]: unknown;
}

export interface ThreeDSceneV2HierarchyGroup {
  id?: string | null;
  name?: string | null;
  children?: string[] | null;
}

export interface ThreeDSceneManifestV2 {
  schema_version?: string | null;
  source_project?: string | null;
  case_id?: string | null;
  dataset_id?: string | null;
  scene_id?: string | null;
  scene?: {
    coordinate_space?: string | null;
    registration_status?: string | null;
    registration_error_mm?: number | string | null;
    navigation_ready?: boolean | string | null;
    doctor_review_status?: string | null;
    orientation_review_status?: string | null;
    display_orientation_status?: string | null;
    view_space_mapping?: ThreeDViewSpaceMapping | null;
    volume_geometry?: {
      spacing_xyz_mm?: number[] | null;
      origin_xyz_mm?: number[] | null;
      direction?: number[] | null;
      array_axis_order?: string | null;
      stl_vertex_order?: string | null;
    } | null;
  } | null;
  subject_hierarchy?: ThreeDSceneV2HierarchyGroup[] | null;
  nodes?: ThreeDSceneV2Node[] | null;
  markups?: ThreeDSceneV2Markup[] | null;
  transforms?: Array<Record<string, unknown>> | null;
  geometry_jobs?: Array<Record<string, unknown>> | null;
  review_state?: Record<string, unknown> | null;
  data_boundary?: string | null;
}

export interface ThreeDGeometryPlaneIntersection {
  id?: string | null;
  label?: string | null;
  status?: string | null;
  segment_count?: number | string | null;
  centroid_mm?: number[] | null;
  polyline_length_mm?: number | string | null;
  sample_points_mm?: number[][] | null;
}

export interface ThreeDGeometrySegmentMeasurement {
  id?: string | null;
  from_plane_id?: string | null;
  to_plane_id?: string | null;
  length_mm?: number | string | null;
  measurement_mode?: string | null;
  status?: string | null;
}

export interface ThreeDGeometryManifest {
  schema_version?: string | null;
  source?: Record<string, unknown> | null;
  mesh_summary?: Record<string, unknown> | null;
  plane_intersections?: ThreeDGeometryPlaneIntersection[] | null;
  segment_measurements?: ThreeDGeometrySegmentMeasurement[] | null;
  candidate_surface_points?: Array<Record<string, unknown>> | null;
  geometry_status?: Record<string, unknown> | null;
  data_boundary?: string | null;
}

export interface ThreeDViewSpaceMapping {
  source_vertex_order?: string | null;
  display_up_axis?: string | null;
  frontend_rotation_x_degrees?: number | string | null;
  identity_direction?: boolean | string | null;
  requires_review?: boolean | string | null;
  reason?: string | null;
}

export interface ThreeDEvidence {
  schema_version?: string | null;
  run_id?: string | null;
  analysis_mode?: string | null;
  model_path?: string | null;
  model_format?: string | null;
  model_file_name?: string | null;
  model_source?: string | null;
  exported_from?: string | null;
  dicom_series_uid?: string | null;
  segmentation_source?: string | null;
  segmentation_review_status?: string | null;
  registration_status?: string | null;
  registration_method?: string | null;
  registration_error_mm?: number | string | null;
  camera_registration_status?: string | null;
  camera_intrinsics_id?: string | null;
  reprojection_error_px?: number | string | null;
  reprojection_fit_error_px?: number | string | null;
  reprojection_error_threshold_px?: number | string | null;
  reprojection_error_source?: string | null;
  camera_calibration_evidence?: {
    artifact_path?: string | null;
    artifact_sha256?: string | null;
    artifact_validation?: { valid?: boolean; failure_reasons?: string[] } | null;
    calibration_method?: string | null;
    calibrated_at?: string | null;
  } | null;
  threshold_approval?: {
    status?: string | null;
    protocol_version?: string | null;
    data_version?: string | null;
    approved_by?: string | null;
    approved_at?: string | null;
  } | null;
  transform_sha256?: string | null;
  fiducial_count?: number | string | null;
  surface_point_count?: number | string | null;
  coordinate_space?: string | null;
  model_coordinate_space?: string | null;
  transform_path?: string | null;
  registration_markups?: ThreeDEvidenceMarkup[] | null;
  transform_chain?: ThreeDEvidenceTransformStep[] | null;
  doctor_review_status?: string | null;
  navigation_ready?: boolean | string | null;
  navigation_level?: "L0" | "L1" | "L2" | string | null;
  degradation_state?: string | null;
  fallback_mode?: string | null;
  failure_reasons?: string[] | null;
  replay_mode?: L2ReplayMode | string | null;
  video_evidence?: L2VideoEvidence | null;
  video_input_id?: string | null;
  video_sha256?: string | null;
  video_frame_count?: number | string | null;
  video_timestamp_source?: string | null;
  pose_manifest_path?: string | null;
  pose_manifest_sha256?: string | null;
  pose_replay_manifest_path?: string | null;
  pose_replay_manifest_sha256?: string | null;
  pose_replay_frames_csv_path?: string | null;
  overlay_video_path?: string | null;
  overlay_video_sha256?: string | null;
  overlay_frame_count?: number | string | null;
  overlay_evidence?: L2OverlayEvidence | null;
  projection_evidence?: L2ProjectionEvidence | null;
  l2_threshold_approval?: L2ThresholdApproval | null;
  calibration_selection?: L2CalibrationSelection | null;
  calibration_transition_summary?: L2CalibrationTransitionSummary | null;
  microscope_pose_evidence?: {
    device_source?: string | null;
    device_model?: string | null;
    firmware?: string | null;
    magnification?: number | string | null;
    working_distance_mm?: number | string | null;
    calibration_status?: string | null;
    intrinsics_id?: string | null;
    pose_tracking_status?: string | null;
    time_offset_ms?: number | string | null;
    depth_status?: string | null;
    tre_mm?: number | string | null;
    tre_threshold_mm?: number | string | null;
    drift_mm?: number | string | null;
    drift_threshold_mm?: number | string | null;
    magnification_rate_per_s?: number | string | null;
    magnification_rate_threshold_per_s?: number | string | null;
    working_distance_rate_mm_per_s?: number | string | null;
    working_distance_rate_threshold_mm_per_s?: number | string | null;
    intrinsics_switch_count?: number | string | null;
    intrinsics_switch_rate_hz?: number | string | null;
    intrinsics_switch_rate_threshold_hz?: number | string | null;
  } | null;
  input_domain?: string | null;
  orientation_review_status?: string | null;
  display_orientation_status?: string | null;
  view_space_mapping?: ThreeDViewSpaceMapping | null;
  data_boundary?: string | null;
  surface_quality?: Record<string, unknown> | null;
  source_inputs?: Array<Record<string, unknown>> | null;
  scene_manifest?: ThreeDSceneManifest | null;
  scene_manifest_v2?: ThreeDSceneManifestV2 | null;
  geometry_manifest_path?: string | null;
  boundary_note?: string | null;
}

interface L1StaticRegistrationRequestBase {
  case_id: string;
  registration_method: "rigid_points" | "rigid_points_with_pnp";
  unit: "mm";
}

export interface L1ManualStaticRegistrationRequest extends L1StaticRegistrationRequestBase {
  input_mode: "manual_metadata";
  doctor_review_status: "review_required";
  registration_manifest_path?: never;
  registration_manifest_sha256?: never;
  model_path?: string | null;
  source_points?: number[][];
  target_points?: number[][];
  validation_source_points?: number[][];
  validation_target_points?: number[][];
  source_space?: string | null;
  target_space?: string | null;
  fre_threshold_mm?: number | null;
  tre_threshold_mm?: number | null;
  threshold_source?: string | null;
  camera_object_points?: number[][];
  camera_image_points?: number[][];
  validation_camera_object_points?: number[][];
  validation_camera_image_points?: number[][];
  camera_matrix?: number[][];
  distortion_coefficients?: number[];
  image_size_px?: [number, number];
  intrinsics_id?: string | null;
  camera_space?: string | null;
  reprojection_threshold_px?: number | null;
  camera_calibration_evidence?: Record<string, unknown>;
  threshold_approval?: Record<string, unknown>;
  microscope_pose_evidence?: Record<string, unknown>;
}

export interface L1OfflineManifestRegistrationRequest extends L1StaticRegistrationRequestBase {
  input_mode: "offline_manifest";
  doctor_review_status: "review_required" | "accepted";
  registration_manifest_path: string;
  registration_manifest_sha256: string;
}

export type L1StaticRegistrationRequest =
  | L1ManualStaticRegistrationRequest
  | L1OfflineManifestRegistrationRequest;

export type L2ReplayMode = "pose_only_engineering" | "dynamic_ar_validation";

export interface L2ThresholdApproval {
  status: "pending" | "approved" | string;
  protocol_version?: string | null;
  data_version?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  max_time_offset_ms?: number | null;
  drift_threshold_mm?: number | null;
  tre_proxy_threshold_mm?: number | null;
  dynamic_target_error_threshold_mm?: number | null;
  minimum_visible_projection_points?: number | null;
  max_magnification_rate_per_s?: number | null;
  max_working_distance_rate_mm_per_s?: number | null;
  max_intrinsics_switch_rate_hz?: number | null;
  calibration_ambiguity_margin?: number | null;
}

export interface L2CalibrationTransitionThresholds {
  max_magnification_rate_per_s?: number | string | null;
  max_working_distance_rate_mm_per_s?: number | string | null;
  max_intrinsics_switch_rate_hz?: number | string | null;
  calibration_ambiguity_margin?: number | string | null;
}

export interface L2CalibrationTransition {
  from_frame_index?: number | string | null;
  to_frame_index?: number | string | null;
  from_intrinsics_id?: string | null;
  to_intrinsics_id?: string | null;
  delta_time_s?: number | string | null;
  magnification_rate_per_s?: number | string | null;
  working_distance_rate_mm_per_s?: number | string | null;
  intrinsics_switch_rate_hz?: number | string | null;
  oscillation?: boolean | string | null;
}

export interface L2CalibrationTransitionSummary {
  status?: "passed" | "failed_closed" | string | null;
  switch_count?: number | string | null;
  ambiguous_frame_count?: number | string | null;
  oscillation_count?: number | string | null;
  max_magnification_rate_per_s?: number | string | null;
  max_working_distance_rate_mm_per_s?: number | string | null;
  max_intrinsics_switch_rate_hz_observed?: number | string | null;
  approved_thresholds?: L2CalibrationTransitionThresholds | null;
  intrinsics_transitions?: L2CalibrationTransition[] | null;
  failure_reasons?: string[] | null;
}

export interface L2CalibrationSelectionFrame {
  frame_index?: number | string | null;
  pose_index?: number | string | null;
  intrinsics_id?: string | null;
  magnification?: number | string | null;
  working_distance_mm?: number | string | null;
  magnification_rate_per_s?: number | string | null;
  working_distance_rate_mm_per_s?: number | string | null;
  intrinsics_switched?: boolean | string | null;
  intrinsics_switch_rate_hz?: number | string | null;
  candidate_count?: number | string | null;
  selection_distance?: number | string | null;
  ambiguous?: boolean | string | null;
  failure_reasons?: string[] | null;
}

export interface L2CalibrationSelection extends L2CalibrationTransitionSummary {
  calibration_table_id?: string | null;
  selection_method?: string | null;
  artifact_sha256?: string | null;
  selected_intrinsics_ids?: string[] | null;
  per_frame?: L2CalibrationSelectionFrame[] | null;
}

export interface L2VideoEvidence {
  input_id?: string | null;
  path?: string | null;
  sha256?: string | null;
  frame_count?: number | string | null;
  fps?: number | string | null;
  width?: number | string | null;
  height?: number | string | null;
  timestamp_source?: string | null;
}

export interface L2OverlayEvidence {
  path?: string | null;
  sha256?: string | null;
  frame_count?: number | string | null;
  fps?: number | string | null;
  width?: number | string | null;
  height?: number | string | null;
  render_method?: string | null;
}

export interface L2ProjectionEvidence {
  status?: string | null;
  point_count?: number | string | null;
  projected_frame_count?: number | string | null;
  frame_count?: number | string | null;
  visible_point_count?: number | string | null;
  visible_projection_count?: number | string | null;
  total_projection_count?: number | string | null;
  minimum_visible_points?: number | string | null;
  minimum_visible_count_observed?: number | string | null;
  out_of_frame_point_count?: number | string | null;
  projection_artifact_path?: string | null;
  projection_artifact_sha256?: string | null;
}

export interface L2PoseRecord {
  timestamp_s: number;
  matrix: number[][];
  magnification: number;
  working_distance_mm: number;
  tracking_status: string;
}

export interface L2CalibrationRange {
  intrinsics_id: string;
  magnification_min: number;
  magnification_max: number;
  working_distance_min_mm: number;
  working_distance_max_mm: number;
}

interface L2ReplayRequestBase {
  case_id: string;
  doctor_review_status: "review_required" | "accepted";
}

export interface L2PoseOnlyReplayRequest extends L2ReplayRequestBase {
  replay_mode: "pose_only_engineering";
  input_mode: "manual_metadata" | "offline_manifest";
  pose_manifest_path?: string | null;
  pose_manifest_sha256?: string | null;
  frame_timestamps_s?: number[];
  poses?: L2PoseRecord[];
  calibration_table?: L2CalibrationRange[];
  failure_injections?: Record<string, string[]>;
  max_time_offset_ms: number;
  drift_threshold_mm: number;
  tre_proxy_threshold_mm: number;
  dynamic_target_error_threshold_mm: number;
  minimum_visible_projection_points: number;
  max_magnification_rate_per_s?: number;
  max_working_distance_rate_mm_per_s?: number;
  max_intrinsics_switch_rate_hz?: number;
  calibration_ambiguity_margin?: number;
}

export interface L2DynamicArReplayRequest extends L2ReplayRequestBase {
  replay_mode: "dynamic_ar_validation";
  input_mode: "offline_manifest";
  video_input_id: string;
  pose_manifest_path: string;
  pose_manifest_sha256: string;
  frame_timestamps_s?: never;
  poses?: never;
  calibration_table?: never;
  failure_injections?: never;
  max_time_offset_ms?: never;
  drift_threshold_mm?: never;
  tre_proxy_threshold_mm?: never;
  dynamic_target_error_threshold_mm?: never;
  minimum_visible_projection_points?: never;
  max_magnification_rate_per_s?: never;
  max_working_distance_rate_mm_per_s?: never;
  max_intrinsics_switch_rate_hz?: never;
  calibration_ambiguity_margin?: never;
  l2_threshold_approval?: never;
}

export type L2PoseReplayRequest = L2PoseOnlyReplayRequest | L2DynamicArReplayRequest;

export interface AnalysisRun {
  run_id: string;
  case_id: string;
  method_id?: string | null;
  parameters: Record<string, unknown>;
  status: string;
  candidate_regions: CandidateRegion[];
  fused_outputs: Record<string, unknown>;
  quantitative_summary: Record<string, unknown>;
  warnings: Array<Record<string, unknown>>;
}

export interface RegionOfInterest {
  roi_id: string;
  case_id: string;
  source: "manual" | "ai";
  geometry: Record<string, unknown>;
  label?: string | null;
  metrics: Record<string, unknown>;
  review_state: ReviewState;
  candidate_id?: string | null;
}

export interface EvidenceArtifact {
  artifact_id: string;
  case_id: string;
  run_id?: string | null;
  kind: string;
  path: string;
  checksum?: string | null;
}

export interface CaseRecord {
  case_id: string;
  title: string;
  status: CaseStatus;
  version: number;
  disclaimer_version: string;
  intake_metadata?: {
    source_type: string;
    source_organization: string;
    external_case_id: string;
    batch_ids: string[];
    handover_ids: string[];
    authorization_status: string;
    usage_scope: string;
    deidentification_confirmed: boolean;
    deidentification_method?: string | null;
    mapping_held_by_institution: boolean;
    target_condition_confirmed: boolean;
    admission_status: string;
    report_paths: string[];
  } | null;
  review_summary: Record<string, unknown>;
  clinical_context?: ClinicalContext;
  three_d_evidence?: ThreeDEvidence;
  three_d_modeling?: Record<string, unknown>;
  inputs: CaseInputAsset[];
  analysis_runs: AnalysisRun[];
  rois: RegionOfInterest[];
  quality_flags: QualityFlag[];
  artifacts: EvidenceArtifact[];
  warnings: Array<Record<string, unknown>>;
  disclaimer?: string | null;
}

export interface ExportResponse {
  bundle_path: string;
  report_path: string;
  manifest_path: string;
  case_id: string;
  dicom_path?: string | null;
  summary?: ExportSummary;
  artifact_entries?: ExportArtifactEntry[];
}

export interface ExportSummary {
  schema_version?: string;
  case_id?: string;
  analysis_run_count?: number;
  candidate_region_count?: number;
  core_artifact_count?: number;
  included_artifact_count?: number;
  total_artifact_count?: number;
  quantification_row_count?: number;
  bundle_size_bytes?: number | null;
  formats?: string[];
  dicom_included?: boolean;
}

export interface ExportArtifactEntry {
  artifact_id?: string;
  kind: string;
  path: string;
  checksum?: string | null;
  exists?: boolean;
  size_bytes?: number | null;
  extra?: Record<string, unknown>;
}

export interface VideoCandidate {
  record_id: string;
  group: string;
  title: string;
  source_page_original_link: string;
  direct_download_link: string;
  local_path: string;
  fluorescence: boolean | null;
  medical_scene: string;
  usable_for_training: string;
  notes: string;
  download_status: string;
  error_or_note: string;
  size_bytes?: number | null;
  sha256: string;
  downloaded_at_utc: string;
  exists: boolean;
  system_readable: boolean;
  input_type: string;
  domain_boundary: string;
  preview_path?: string | null;
  preview_status?: string;
  preview_error?: string;
  preview_frame_index?: number | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  duration_sec?: number | null;
}

export interface VideoCandidateList {
  manifest_path: string;
  exists: boolean;
  count: number;
  items: VideoCandidate[];
}
