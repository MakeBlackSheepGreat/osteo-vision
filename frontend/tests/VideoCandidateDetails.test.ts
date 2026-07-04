import { describe, expect, it } from "vitest";

import type { VideoCandidate } from "../src/types/case";
import {
  filterVideoCandidates,
  findVideoCandidate,
  formatBytes,
  videoCandidateDetails,
  videoCandidateFilterSummary,
  videoCandidateFluorescenceLabel,
  videoCandidateGeometryLabel,
  videoCandidatePreviewLabel,
  videoCandidateReadableLabel,
  videoCandidateSourceUrl,
  videoCandidateTrainingBucket,
} from "../src/utils/videoCandidates";

function candidate(overrides: Partial<VideoCandidate> = {}): VideoCandidate {
  return {
    record_id: "v001",
    group: "public",
    title: "FGS proxy video",
    source_page_original_link: "https://example.org/source",
    direct_download_link: "https://example.org/video.mp4",
    local_path: "C:\\data\\video.mp4",
    fluorescence: true,
    medical_scene: "mock fluorescence-guided surgery",
    usable_for_training: "proxy_only",
    notes: "",
    download_status: "downloaded",
    error_or_note: "",
    size_bytes: 1536 * 1024,
    sha256: "abc",
    downloaded_at_utc: "2026-07-04T00:00:00Z",
    exists: true,
    system_readable: true,
    input_type: "video_file",
    domain_boundary: "non_target_domain_proxy",
    preview_path: null,
    preview_status: "not_requested",
    preview_error: "",
    width: 3840,
    height: 2160,
    duration_sec: 12.5,
    ...overrides,
  };
}

describe("video candidate details", () => {
  it("selects and formats candidate metadata for the workspace card", () => {
    const selected = findVideoCandidate([candidate(), candidate({ record_id: "v002", fluorescence: false })], "v002");

    expect(selected?.record_id).toBe("v002");
    expect(selected ? videoCandidateFluorescenceLabel(selected) : "").toBe("非荧光");
    expect(selected ? videoCandidateReadableLabel(selected) : "").toBe("本地可读");
    expect(selected ? videoCandidateSourceUrl(selected) : "").toBe("https://example.org/source");
    expect(formatBytes(1536 * 1024)).toBe("1.5 MB");
  });

  it("keeps domain boundary and training suitability visible", () => {
    const details = videoCandidateDetails(candidate({ source_page_original_link: "", exists: false }));

    expect(videoCandidateSourceUrl(candidate({ source_page_original_link: "" }))).toBe("https://example.org/video.mp4");
    expect(details).toContainEqual({ label: "训练可用性", value: "proxy_only" });
    expect(details).toContainEqual({ label: "视频规格", value: "3840 × 2160 / 12.5 秒" });
    expect(details).toContainEqual({ label: "预览状态", value: "未生成" });
    expect(details).toContainEqual({ label: "读取状态", value: "未落地" });
    expect(details).toContainEqual({ label: "数据边界", value: "non_target_domain_proxy" });
  });

  it("formats generated and failed preview states", () => {
    expect(videoCandidatePreviewLabel(candidate({ preview_status: "cached", preview_path: "preview.jpg" }))).toBe(
      "已生成",
    );
    expect(videoCandidatePreviewLabel(candidate({ preview_status: "failed", preview_error: "decode failed" }))).toBe(
      "decode failed",
    );
    expect(videoCandidateGeometryLabel(candidate({ width: null, height: null, duration_sec: null }))).toBe(
      "分辨率未知 / 时长未知",
    );
  });

  it("filters by fluorescence channel and training suitability", () => {
    const candidates = [
      candidate({ record_id: "fluor", fluorescence: true, usable_for_training: "enhancement_or_self_supervised_only" }),
      candidate({ record_id: "white", fluorescence: false, usable_for_training: "no_labels_demo_or_self_supervised_only" }),
      candidate({ record_id: "doc", fluorescence: null, usable_for_training: "documentation" }),
    ];

    expect(videoCandidateTrainingBucket(candidates[0])).toBe("enhancement_or_self_supervised");
    expect(
      filterVideoCandidates(candidates, {
        fluorescence: "fluorescence",
        training: "enhancement_or_self_supervised",
      }).map((item) => item.record_id),
    ).toEqual(["fluor"]);
    expect(
      filterVideoCandidates(candidates, {
        fluorescence: "non_fluorescence",
        training: "demo_or_self_supervised",
      }).map((item) => item.record_id),
    ).toEqual(["white"]);
    expect(videoCandidateFilterSummary(candidates.length, 1)).toBe("1 / 3 条");
  });
});
