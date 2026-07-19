import type { ReviewState } from "@/types/case";

export interface DatasetReviewRecord {
  record_id: string;
  dataset_id?: string | null;
  source_record_id?: string | null;
  source_group_id?: string | null;
  title?: string | null;
  image_path: string;
  image_href?: string | null;
  mask_path?: string | null;
  mask_href?: string | null;
  overlay_path?: string | null;
  source_url?: string | null;
  license?: string | null;
  usage_policy?: string | null;
  input_domain?: string | null;
  panel_role?: string | null;
  review_state: ReviewState;
  reviewer_notes?: string | null;
  width?: number | null;
  height?: number | null;
  training_eligible?: boolean | null;
  physician_reviewed?: boolean | null;
  reviewer_role?: "project_reviewer" | "physician" | "automated_seed" | null;
  review_authority?: string | null;
  sampling_weight?: number | null;
  sample_weight?: number | null;
  image_checksum?: string | null;
  label_checksum?: string | null;
  positive_area_fraction?: number | null;
  label_source?: string | null;
  mask_origin?: string | null;
  seed_threshold?: number | null;
  seed_generated?: boolean | null;
  mask_source?: string | null;
  threshold?: number | null;
  colormap?: "green" | "amber" | "magenta" | null;
  quality_status?: string | null;
  quality_warnings?: string[] | null;
  record_kind?: string | null;
  crop_required?: boolean | null;
  crop_bbox?: { x: number; y: number; width: number; height: number } | null;
  parent_record_id?: string | null;
  panel_label?: string | null;
  suggestion_id?: string | null;
  suggested_crop_bbox?: { x: number; y: number; width: number; height: number } | null;
  suggested_panel_role?: string | null;
  suggested_pair_id?: string | null;
  suggested_pair_alignment?: string | null;
  suggestion_method?: string | null;
  suggestion_score?: number | null;
  suggestion_quality_status?: "pass" | "warning" | "blocked" | null;
  suggestion_quality_warnings?: string[] | null;
  crop_review_action?: "pending" | "accepted" | "modified" | "rejected" | null;
  crop_quality_status?: "pass" | "warning" | null;
  crop_quality_warnings?: string[] | null;
  pair_id?: string | null;
  crop_notes?: string | null;
  medical_boundary?: string | null;
  [key: string]: unknown;
}

export interface DatasetReviewCropRequest {
  x: number;
  y: number;
  width: number;
  height: number;
  panel_role: string;
  pair_id: string | null;
  crop_notes: string | null;
  suggestion_id: string | null;
  crop_review_action: "accepted" | "modified";
}

export interface DatasetReviewQueue {
  schema_version?: string | null;
  record_count?: number;
  reviewed_count?: number;
  training_eligible_count?: number;
  items: DatasetReviewRecord[];
  records?: DatasetReviewRecord[];
  summary?: Record<string, unknown>;
  medical_boundary?: string | null;
}

export interface DatasetReviewMaskRequest {
  mask_png_base64: string;
  review_state: ReviewState;
  reviewer_notes: string;
  reviewer_role: "project_reviewer" | "physician";
}
