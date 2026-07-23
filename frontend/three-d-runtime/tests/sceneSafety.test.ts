import { describe, expect, it } from "vitest";

import { canRenderSpatialCandidateMarker, canRenderSpatialCandidateMarkers, spatialCandidatePoint } from "../src/sceneSafety";

describe("sceneSafety", () => {
  const candidate = {
    candidate_id: "candidate_001",
    surface_point_mm: [10, 20, 30],
    coordinate_space: "cbct_ras",
    spatial_mapping_status: "verified",
    coordinate_transform_sha256: "a".repeat(64),
  };

  const verifiedSpatialMapping = {
    schema_version: "osteo-vision-three-d-runtime-spatial-mapping-v1" as const,
    model_coordinate_space: "cbct_ras",
    transform_sha256: "a".repeat(64),
    status: "verified" as const,
  };

  it("never turns an L0 reference candidate into a spatial marker", () => {
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [candidate],
        spatial_mapping: verifiedSpatialMapping,
        safety: { navigation_ready: false, navigation_level: "L0" },
      }),
    ).toBe(false);
  });

  it("requires the same L1/L2 registered gate as the primary navigation workspace", () => {
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [candidate],
        spatial_mapping: verifiedSpatialMapping,
        safety: { navigation_ready: true, navigation_level: "L1", registration_status: "registered" },
      }),
    ).toBe(true);
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [candidate],
        spatial_mapping: verifiedSpatialMapping,
        safety: { navigation_ready: true, navigation_level: "L0", registration_status: "registered" },
      }),
    ).toBe(false);
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [candidate],
        spatial_mapping: verifiedSpatialMapping,
        safety: { navigation_ready: true, navigation_level: "L2", registration_status: "unregistered" },
      }),
    ).toBe(false);
    expect(spatialCandidatePoint({ candidate_id: "bad", surface_point_mm: [1, Number.NaN, 3] })).toBeNull();
  });

  it("requires a checksum-bound coordinate mapping for each spatial marker", () => {
    const mismatchedCandidate = { ...candidate, coordinate_space: "camera_optical" };
    expect(
      canRenderSpatialCandidateMarker(
        {
          schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
          spatial_mapping: verifiedSpatialMapping,
        },
        mismatchedCandidate,
      ),
    ).toBe(false);
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [{ ...candidate, coordinate_transform_sha256: "b".repeat(64) }],
        spatial_mapping: verifiedSpatialMapping,
        safety: { navigation_ready: true, navigation_level: "L1", registration_status: "registered" },
      }),
    ).toBe(false);
  });

  it("does not recover spatial coordinates from legacy metadata outside the v2 contract", () => {
    const legacyCandidate = {
      candidate_id: "legacy_candidate",
      metadata: { surface_point_mm: [10, 20, 30] },
    };

    expect(spatialCandidatePoint(legacyCandidate)).toBeNull();
    expect(
      canRenderSpatialCandidateMarkers({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
        candidate_regions: [legacyCandidate],
        safety: { navigation_ready: true, navigation_level: "L1", registration_status: "registered" },
      }),
    ).toBe(false);
  });
});
