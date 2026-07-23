export interface RuntimeCandidate {
  candidate_id: string;
  risk_type?: string | null;
  confidence?: number | null;
  score?: number | null;
  status?: string | null;
  frame_key?: string | null;
  frame_index?: number | null;
  timestamp_sec?: number | null;
  surface_point_mm?: number[] | null;
  position_mm?: number[] | null;
  position_3d?: number[] | null;
  projection_point_3d?: number[] | null;
  coordinate_space?: string | null;
  spatial_mapping_status?: string | null;
  coordinate_transform_sha256?: string | null;
}

export interface RuntimeModelAsset {
  asset_id: "model";
  url: string;
  format: "stl" | "glb" | "gltf";
  file_name: string;
  sha256: string;
  size_bytes: number;
  rendering_status?: "ready" | "unsupported_format";
  rendering_failure_reason?: string | null;
}

export interface RuntimeSafetyState {
  navigation_level?: string | null;
  navigation_ready?: boolean | null;
  registration_status?: string | null;
  doctor_review_status?: string | null;
  fallback_mode?: string | null;
  failure_reasons?: string[];
  boundary?: string | null;
}

export interface RuntimeSpatialMapping {
  schema_version: "osteo-vision-three-d-runtime-spatial-mapping-v1";
  model_coordinate_space?: string | null;
  transform_sha256?: string | null;
  status: "verified" | "unavailable";
  failure_reasons?: string[];
}

export interface ThreeDRuntimeSnapshot {
  schema_version: string;
  case_id?: string | null;
  case_version?: number | null;
  generated_at?: string | null;
  snapshot_sha256?: string | null;
  mode_label?: string | null;
  candidate_regions?: RuntimeCandidate[];
  metrics?: Record<string, unknown>;
  three_d_evidence?: Record<string, unknown>;
  model_asset?: RuntimeModelAsset | null;
  spatial_mapping?: RuntimeSpatialMapping;
  safety?: RuntimeSafetyState;
}

export interface RuntimeBridgeMessage {
  protocol?: string;
  type?: string;
  request_id?: string;
  case_id?: string;
  reference_id?: string;
  theme?: "light" | "dark";
}

export interface SelectedCandidate {
  candidate_id: string;
  frame_key: string;
  frame_index: number | null;
  timestamp_sec: number | null;
}
