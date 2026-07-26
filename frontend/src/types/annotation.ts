export type AnnotationSourceType = "case_jpeg" | "video_keyframe" | "model_candidate";

export type AnnotationLabel =
  | "lesion"
  | "exposed_bone"
  | "fluorescence_signal"
  | "boundary_risk"
  | "uncertain"
  | "low_activity"
  | "transition"
  | "high_activity"
  | "ignore";

export type AnnotationStatus = "draft" | "submitted" | "accepted" | "modified" | "rejected" | "changes_requested";

export type AnnotationTool = "brush" | "eraser" | "polygon";

export interface AnnotationPoint {
  x: number;
  y: number;
}

export interface AnnotationOperation {
  tool: AnnotationTool;
  points: AnnotationPoint[];
  radius?: number | null;
  mode?: "add" | "erase" | null;
}

export interface AnnotationGeometry {
  coordinate_space: "image_pixels" | "normalized";
  operations: AnnotationOperation[];
}

export interface AnnotationOverlayLayer {
  id: string;
  label: AnnotationLabel;
  color: string;
  geometry: AnnotationGeometry;
}

export interface AnnotationSourceReference {
  source_type: AnnotationSourceType;
  input_id?: string | null;
  run_id?: string | null;
  frame_index?: number | null;
  timestamp_sec?: number | null;
  candidate_id?: string | null;
}

export interface AnnotationSource extends AnnotationSourceReference {
  source_id?: string | null;
  title?: string | null;
  label_hint?: string | null;
  original_width?: number | null;
  original_height?: number | null;
  metadata?: Record<string, unknown>;
  preview_path: string;
  source_snapshot_path?: string | null;
}

export interface AnnotationSourceList {
  case_id: string;
  sources: AnnotationSource[];
}

export interface AnnotationActor {
  actor_id: string;
  role: string;
  institution: string;
  auth_source: string;
  authenticated?: boolean | null;
}

export interface ManualAnnotation {
  annotation_id: string;
  case_id: string;
  label: AnnotationLabel;
  status: AnnotationStatus;
  current_version: number;
  source: AnnotationSourceReference;
  source_snapshot_path: string;
  original_width: number;
  original_height: number;
  geometry?: AnnotationGeometry | null;
  mask_path?: string | null;
  mask_checksum?: string | null;
  notes?: string | null;
  created_by: AnnotationActor;
  latest_author: AnnotationActor;
  submitted_by?: AnnotationActor | null;
  reviewed_by?: AnnotationActor | null;
  training_eligible: boolean;
  sample_weight: number;
  training_exclusion_reason?: string | null;
  created_at: string;
  updated_at: string;
  submitted_at?: string | null;
  reviewed_at?: string | null;
}

export interface AnnotationVersion {
  annotation_id: string;
  version: number;
  geometry: AnnotationGeometry;
  mask_path?: string | null;
  mask_checksum?: string | null;
  notes?: string | null;
  author: AnnotationActor;
  created_at: string;
}

export interface AnnotationList {
  case_id: string;
  items: ManualAnnotation[];
}

export interface AnnotationVersionList {
  annotation_id: string;
  items: AnnotationVersion[];
}

export interface CreateAnnotationRequest {
  source: AnnotationSourceReference;
  label: AnnotationLabel;
  geometry: AnnotationGeometry;
  notes?: string;
}

export interface UpdateAnnotationVersionRequest {
  expected_version: number;
  geometry: AnnotationGeometry;
  notes?: string;
}

export interface AnnotationTrainingManifestResponse {
  manifest_id?: string;
  manifest_path: string;
  csv_path?: string | null;
  sample_count: number;
  eligible_count: number;
  excluded_count: number;
  error_analysis_json_path?: string;
  error_analysis_csv_path?: string;
}

export interface AnnotationTrainingManifestSummary {
  manifest_id: string;
  created_at: string;
  created_by: AnnotationActor;
  case_ids: string[];
  json_path: string;
  csv_path: string;
  error_analysis_json_path: string;
  error_analysis_csv_path: string;
  eligible_count: number;
  excluded_count: number;
  rejected_count: number;
  manifest_checksum: string;
  error_analysis_checksum: string;
}
