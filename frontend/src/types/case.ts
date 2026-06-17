export type CaseStatus = "draft" | "loaded" | "analyzed" | "reviewing" | "reviewed" | "exported" | "archived";

export type InputChannel = "white_light" | "fluorescence" | "sequence" | "video";

export type ReviewState = "review_required" | "accepted" | "modified" | "rejected";

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
  disclaimer_version: string;
  review_summary: Record<string, unknown>;
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
}
