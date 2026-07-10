export type CaseStatus = "draft" | "loaded" | "analyzed" | "reviewing" | "reviewed" | "exported" | "archived";

export type InputChannel = "white_light" | "fluorescence" | "sequence" | "video";

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
  fiducial_count?: number | string | null;
  surface_point_count?: number | string | null;
  coordinate_space?: string | null;
  transform_path?: string | null;
  registration_markups?: ThreeDEvidenceMarkup[] | null;
  transform_chain?: ThreeDEvidenceTransformStep[] | null;
  doctor_review_status?: string | null;
  navigation_ready?: boolean | string | null;
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
  review_summary: Record<string, unknown>;
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
