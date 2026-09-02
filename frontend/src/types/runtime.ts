export interface RuntimeIssue {
  code: string;
  model_id?: string;
  tool?: string;
}

export interface RuntimeModelEvidence {
  model_id: string;
  family: string;
  checkpoint_path: string;
  checkpoint_sha256: string;
  sidecar_path: string;
  runtime_allowed: boolean;
}

export interface RuntimeToolStatus {
  tool: string;
  available: boolean;
  path?: string | null;
  required: boolean;
}

export interface AcceleratorRuntimeStatus {
  requested_policy: string;
  selected_device: "cpu" | "cuda";
  gpu_acceleration_enabled: boolean;
  fallback_active: boolean;
  fallback_reason?: string | null;
  torch_version?: string | null;
  cuda_runtime_version?: string | null;
  gpu_count: number;
  gpu_name?: string | null;
}

export interface RuntimeReadiness {
  passed: boolean;
  runtime_profile: string;
  strict_startup: boolean;
  config_path: string;
  config_sha256?: string | null;
  error_count: number;
  warning_count: number;
  errors: RuntimeIssue[];
  warnings: RuntimeIssue[];
  required_model_ids: string[];
  verified_models: RuntimeModelEvidence[];
  runtime_tools: RuntimeToolStatus[];
}

export interface ReadyResponse {
  status: "ok" | "degraded";
  inference_config: string;
  runtime_readiness: RuntimeReadiness;
  accelerator?: AcceleratorRuntimeStatus;
}
