import type { ReadyResponse } from "@/types/runtime";

const API_BASE_URL = import.meta.env.VITE_OSTEO_API_URL ?? "http://127.0.0.1:8001";

export async function getRuntimeReadiness(): Promise<ReadyResponse> {
  const response = await fetch(`${API_BASE_URL}/ready`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`runtime readiness request failed with status ${response.status}`);
  }
  return response.json() as Promise<ReadyResponse>;
}
