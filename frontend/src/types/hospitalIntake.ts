import type { InputChannel } from "@/types/case";

export type HospitalAuthorizationStatus = "approved" | "pending" | "restricted" | "denied";
export type HospitalAcquisitionMode =
  | "white_light"
  | "fluorescence"
  | "overlay"
  | "mode_switching"
  | "synchronized_dual_channel"
  | "unknown";
export type HospitalChannelRelationship =
  | "single_channel"
  | "synchronized_pair"
  | "mode_switch"
  | "overlay_only"
  | "unknown";

export interface HospitalIntakeFileRequest {
  external_case_id: string;
  path: string;
  channel: InputChannel;
  acquisition_mode: HospitalAcquisitionMode;
  channel_relationship: HospitalChannelRelationship;
  pair_id?: string | null;
  original_filename?: string | null;
  metadata: Record<string, unknown>;
  missing_fields: string[];
}

export interface HospitalIntakeBatchRequest {
  batch_id: string;
  handover_id: string;
  source_organization: string;
  received_by: string;
  received_at: string;
  authorization_status: HospitalAuthorizationStatus;
  usage_scope: string;
  deidentification_confirmed: boolean;
  deidentification_method?: string | null;
  mapping_held_by_institution: boolean;
  target_condition_confirmed: boolean;
  files: HospitalIntakeFileRequest[];
}

export interface IntakeFinding {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface HospitalIntakeRecord {
  record_id: string;
  external_case_id: string;
  platform_case_id?: string | null;
  path: string;
  original_filename: string;
  suffix: string;
  size_bytes: number;
  sha256: string;
  channel: InputChannel;
  acquisition_mode: HospitalAcquisitionMode;
  channel_relationship: HospitalChannelRelationship;
  pair_id?: string | null;
  status: "admitted" | "quarantined";
  admission_stage: "quarantined" | "engineering_analysis_ready" | "target_registry_ready";
  reasons: IntakeFinding[];
  warnings: IntakeFinding[];
  target_domain_flag: boolean;
  review_state: "review_required";
  training_eligible: false;
  fusion_eligible: boolean;
}

export interface HospitalIntakeArtifactAttachmentFailure {
  code: string;
  platform_case_id?: string;
  error_type?: string;
  [key: string]: unknown;
}

export interface HospitalIntakeArtifactAttachment {
  status: "pending" | "completed" | "completed_with_errors" | string;
  status_path: string;
  expected_case_count: number;
  attached_case_count: number;
  attached_case_ids: string[];
  failures: HospitalIntakeArtifactAttachmentFailure[];
  status_persisted: boolean;
}

export interface HospitalIntakeReport {
  schema_version: string;
  batch_id: string;
  handover_id: string;
  source_organization: string;
  received_by: string;
  received_at: string;
  authorization_status: HospitalAuthorizationStatus;
  deidentification_confirmed: boolean;
  target_condition_confirmed: boolean;
  case_map: Record<string, string>;
  summary: {
    status: string;
    file_count: number;
    admitted_count: number;
    quarantined_count: number;
    target_domain_source_count: number;
    training_eligible_count: number;
    case_count: number;
  };
  records: HospitalIntakeRecord[];
  artifact_attachment?: HospitalIntakeArtifactAttachment;
  report_path: string;
  csv_path: string;
  medical_boundary: string;
}

export interface HospitalIntakeBatchList {
  count: number;
  items: Array<{
    batch_id: string;
    handover_id: string;
    received_at: string;
    source_organization: string;
    summary: HospitalIntakeReport["summary"];
    report_path: string;
  }>;
}
