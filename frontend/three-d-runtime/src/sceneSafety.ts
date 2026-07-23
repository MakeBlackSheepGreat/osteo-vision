import type { RuntimeCandidate, ThreeDRuntimeSnapshot } from "./types";

export function canRenderSpatialCandidateMarkers(snapshot: ThreeDRuntimeSnapshot | null): boolean {
  const safety = snapshot?.safety;
  const navigationLevel = String(safety?.navigation_level ?? "").toUpperCase();
  const registrationStatus = String(safety?.registration_status ?? "").trim().toLowerCase();
  if (!safety?.navigation_ready || !["L1", "L2"].includes(navigationLevel) || registrationStatus !== "registered") {
    return false;
  }
  return (snapshot?.candidate_regions ?? []).some((candidate) => canRenderSpatialCandidateMarker(snapshot, candidate));
}

export function canRenderSpatialCandidateMarker(
  snapshot: ThreeDRuntimeSnapshot | null,
  candidate: RuntimeCandidate,
): boolean {
  const mapping = snapshot?.spatial_mapping;
  const coordinateSpace = candidate.coordinate_space?.trim();
  const candidateSha256 = candidate.coordinate_transform_sha256?.trim().toLowerCase();
  const expectedSha256 = mapping?.transform_sha256?.trim().toLowerCase();
  return Boolean(
    spatialCandidatePoint(candidate) &&
      mapping?.status === "verified" &&
      mapping.model_coordinate_space &&
      coordinateSpace === mapping.model_coordinate_space &&
      candidate.spatial_mapping_status?.trim().toLowerCase() === "verified" &&
      expectedSha256 &&
      candidateSha256 === expectedSha256,
  );
}

export function spatialCandidatePoint(candidate: RuntimeCandidate): [number, number, number] | null {
  const raw =
    candidate.surface_point_mm ??
    candidate.position_mm ??
    candidate.position_3d ??
    candidate.projection_point_3d;
  if (!Array.isArray(raw) || raw.length < 3) return null;
  const values = raw.slice(0, 3);
  if (!values.every((value) => typeof value === "number" && Number.isFinite(value))) return null;
  return values as [number, number, number];
}
