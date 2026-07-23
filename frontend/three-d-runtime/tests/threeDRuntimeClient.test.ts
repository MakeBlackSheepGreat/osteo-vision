import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCaseSnapshot,
  fetchReferenceSnapshot,
  resolveAssetUrl,
  snapshotSha256,
} from "../src/services/threeDRuntimeClient";

describe("threeDRuntimeClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads a versioned case snapshot without requesting the full case record", async () => {
    const unsigned = { schema_version: "osteo-vision-three-d-runtime-snapshot-v2", case_id: "case_001" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ ...unsigned, snapshot_sha256: await snapshotSha256(unsigned) }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await fetchCaseSnapshot("case_001");

    expect(snapshot.case_id).toBe("case_001");
    expect(fetchMock.mock.calls[0][0]).toContain("/three-d-runtime/v1/cases/case_001/snapshot");
    expect(fetchMock.mock.calls[0][0]).not.toContain("http://127.0.0.1:8001/cases/case_001");
  });

  it("reads the controlled public reference scene and resolves relative asset URLs through the API", async () => {
    const unsigned = { schema_version: "osteo-vision-three-d-runtime-snapshot-v2", case_id: "reference_d024" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ ...unsigned, snapshot_sha256: await snapshotSha256(unsigned) }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await fetchReferenceSnapshot("d024");

    expect(snapshot.case_id).toBe("reference_d024");
    expect(fetchMock.mock.calls[0][0]).toContain("/three-d-runtime/v1/references/d024/snapshot");
    expect(resolveAssetUrl("/three-d-runtime/v1/cases/case_001/assets/asset_001")).toBe(
      "http://127.0.0.1:8001/three-d-runtime/v1/cases/case_001/assets/asset_001",
    );
  });

  it("rejects an unknown schema version or a modified snapshot", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({
        schema_version: "osteo-vision-three-d-runtime-snapshot-v999",
        case_id: "case_001",
        snapshot_sha256: "a".repeat(64),
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchCaseSnapshot("case_001")).rejects.toThrow("版本不受支持");

    const unsigned = { schema_version: "osteo-vision-three-d-runtime-snapshot-v2", case_id: "case_001" };
    fetchMock.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ ...unsigned, snapshot_sha256: "b".repeat(64) }),
    });
    await expect(fetchCaseSnapshot("case_001")).rejects.toThrow("SHA256 不一致");
  });

  it("uses the v2 byte-framed integrity protocol across edge-case numbers and UTF-8 keys", async () => {
    const vector = {
      schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
      numbers: [-0, 0, 1e-7, 1e-6, 1e20, 1e21],
      integer_keys: { "10": 1, "2": 2 },
      unicode_keys: { "\ue000": "BMP", "😀": "emoji", 边界: "医生复核" },
      nested: [{ active: true, value: null }],
    };

    await expect(snapshotSha256(vector)).resolves.toBe("680bb7c661eff18fe2b3512b46ad6d15831aa54df59d578d5df59ffd04325a1e");
  });
});
