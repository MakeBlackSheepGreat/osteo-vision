import { describe, expect, it } from "vitest";

import {
  candidateOverlaysFromRegions,
  filterHotspotTimelineItems,
  fusionEvidenceSummaryFromRun,
  fusedImageAiPreviewPanelsFromRun,
  hotspotFrameDetailsFromRun,
  hotspotOutputsFromRun,
  selectedHotspotFrameDetailFromRun,
  hotspotTimelineFromRun,
  roiOverlaysFromRegions,
  timelineManifestSummaryFromRun,
  videoPreviewPanelsFromRun,
} from "../src/components/analysisPreview";

describe("analysis preview panels", () => {
  it("shows Task 3 fused-image boundary evidence for JPEG analysis", () => {
    const panels = fusedImageAiPreviewPanelsFromRun(
      {
        fused_outputs: {
          fused_image_ai: {
            execution_state: "completed",
            spatial_interpretation_allowed: false,
            lesion_evidence: {
              overlay_path: "task3-overlay.png",
              risk_mask_path: "task3-risk.png",
              uncertain_mask_path: "task3-uncertain.png",
            },
            boundary_assessment: {
              candidate_count: 7,
              evaluated_candidate_count: 19,
              suppressed_candidate_count: 12,
              boundary_type_counts: {
                high_risk_transition_boundary: 2,
                uncertain_boundary: 3,
              },
            },
          },
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(panels.map((panel) => panel.title)).toEqual(["AI 候选叠加", "边界风险", "边界不确定性"]);
    expect(panels.map((panel) => panel.tag)).toEqual([
      "保留 7 / 评估 19",
      "2 个高风险边界",
      "3 个不确定边界",
    ]);
    expect(panels[0].label).toBe("融合输入空间解释关闭；抑制 12 个低优先级碎片");
    expect(panels[0].previewSrc).toBe("/preview?path=task3-overlay.png");
  });

  it("prioritizes MP4 segmentation overlay and mask outputs over plain keyframes", () => {
    const run = {
      fused_outputs: {
        keyframes: [{ frame_index: 1, timestamp_sec: 0.1, path: "frame.jpg" }],
        hotspot_outputs: [
          {
            frame_index: 8,
            timestamp_sec: 0.8,
            source_path: "evidence_frame.jpg",
            lesion_evidence: {
              overlay_path: "hotspot_overlay.png",
              mask_path: "hotspot_mask.png",
            },
          },
        ],
      },
    };

    const panels = videoPreviewPanelsFromRun(run, (path) => `/preview?path=${path}`);

    expect(hotspotOutputsFromRun(run)).toHaveLength(1);
    expect(panels.map((panel) => panel.title)).toEqual(["关键帧", "分割叠加", "分割掩膜"]);
    expect(panels.map((panel) => panel.path)).toEqual(["evidence_frame.jpg", "hotspot_overlay.png", "hotspot_mask.png"]);
    expect(panels[1].previewSrc).toBe("/preview?path=hotspot_overlay.png");

    const timeline = hotspotTimelineFromRun(
      {
        fused_outputs: {
          hotspot_outputs: [
            {
              frame_index: 8,
              timestamp_sec: 0.8,
              source_path: "evidence_frame.jpg",
              lesion_evidence: { overlay_path: "hotspot_overlay.png" },
              quantification: {
                component_count: 2,
                positive_area_fraction: 0.1234,
                roi_positive_area_fraction: 0.0456,
              },
            },
          ],
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(timeline[0]).toMatchObject({
      frameLabel: "帧 8",
      timestampLabel: "0.80s",
      candidateCountLabel: "2 个候选",
      positiveAreaLabel: "12.34%",
      roiAreaLabel: "4.56%",
      score: 0.1234,
      roiScore: 0.0456,
      candidateCount: 2,
      previewSrc: "/preview?path=hotspot_overlay.png",
    });

    const details = hotspotFrameDetailsFromRun(
      {
        fused_outputs: {
          frame_details: [
            {
              frame_key: "8-0",
              frame_index: 8,
              timestamp_sec: 0.8,
              evidence_path: "evidence_frame.jpg",
              overlay_path: "hotspot_overlay.png",
              mask_path: "hotspot_mask.png",
              positive_area_fraction: 0.1234,
              roi_positive_area_fraction: 0.0456,
              component_count: 2,
              top_component_bbox_xyxy: [10.2, 20.4, 30.8, 44.1],
              review_required: true,
            },
          ],
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(details[0]).toMatchObject({
      key: "8-0",
      frameIndex: 8,
      timestampSec: 0.8,
      frameLabel: "帧 8",
      timestampLabel: "0.80s",
      candidateCountLabel: "2 个候选",
      positiveAreaLabel: "12.34%",
      roiAreaLabel: "4.56%",
      topBBoxLabel: "10, 20, 31, 44",
      evidenceHref: "/preview?path=evidence_frame.jpg",
      overlayHref: "/preview?path=hotspot_overlay.png",
      maskHref: "/preview?path=hotspot_mask.png",
    });
  });

  it("falls back to keyframe panels when hotspot outputs are absent", () => {
    const run = {
      fused_outputs: {
        keyframes: [
          { frame_index: 0, timestamp_sec: 0, preview_path: "keyframe_01.jpg" },
          { frame_index: 4, timestamp_sec: 0.4, preview_path: "keyframe_02.jpg" },
        ],
      },
    };

    const panels = videoPreviewPanelsFromRun(run, (path) => `/preview?path=${path}`);

    expect(panels).toHaveLength(2);
    expect(panels[0].title).toBe("关键帧 1");
    expect(panels[0].path).toBe("keyframe_01.jpg");
  });

  it("suppresses stale live overlays while keeping the source frame inspectable", () => {
    const run = {
      fused_outputs: {
        hotspot_outputs: [
          {
            frame_index: 1,
            timestamp_sec: 0.1,
            source_path: "live_frame.jpg",
            display_allowed: false,
            stale: true,
            lesion_evidence: {
              overlay_path: "stale_overlay.png",
              mask_path: "stale_mask.png",
              risk_mask_path: "stale_risk.png",
            },
          },
        ],
      },
    };
    const panels = videoPreviewPanelsFromRun(run, (path) => `/preview?path=${path}`);
    expect(panels.map((panel) => panel.title)).toEqual(["关键帧"]);

    const details = hotspotFrameDetailsFromRun(
      {
        fused_outputs: {
          frame_details: [
            {
              frame_key: "live-1",
              frame_index: 1,
              timestamp_sec: 0.1,
              evidence_path: "live_frame.jpg",
              overlay_path: "stale_overlay.png",
              mask_path: "stale_mask.png",
              risk_mask_path: "stale_risk.png",
              display_allowed: false,
              stale: true,
              analysis_frame_age_ms: 4321.4,
            },
          ],
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(details[0]).toMatchObject({
      displayAllowed: false,
      stale: true,
      frameAgeLabel: "帧龄 4321 ms",
      evidenceHref: "/preview?path=live_frame.jpg",
      overlayHref: undefined,
      maskHref: undefined,
      riskMaskHref: undefined,
    });
  });

  it("switches MP4 preview panels to the selected hotspot timeline item", () => {
    const run = {
      fused_outputs: {
        hotspot_outputs: [
          {
            frame_index: 0,
            timestamp_sec: 0,
            source_path: "frame_00.jpg",
            lesion_evidence: { overlay_path: "overlay_00.png", mask_path: "mask_00.png" },
          },
          {
            frame_index: 4,
            timestamp_sec: 0.8,
            source_path: "frame_04.jpg",
            lesion_evidence: { overlay_path: "overlay_04.png", mask_path: "mask_04.png" },
          },
        ],
      },
    };

    const timeline = hotspotTimelineFromRun(run, (path) => `/preview?path=${path}`);
    const panels = videoPreviewPanelsFromRun(run, (path) => `/preview?path=${path}`, timeline[1].key);

    expect(timeline.map((item) => item.key)).toEqual(["0-0", "4-1"]);
    expect(panels.map((panel) => panel.path)).toEqual(["frame_04.jpg", "overlay_04.png", "mask_04.png"]);
    expect(panels[0].tag).toBe("帧序号: 4");

    const selectedDetail = selectedHotspotFrameDetailFromRun(run, (path) => `/preview?path=${path}`, timeline[1].key);
    expect(selectedDetail?.frameLabel).toBe("帧 4");
    expect(selectedDetail?.overlayHref).toBe("/preview?path=overlay_04.png");
  });

  it("filters MP4 hotspot timeline by positive area, ROI hit, and candidate count", () => {
    const timeline = hotspotTimelineFromRun(
      {
        fused_outputs: {
          hotspot_outputs: [
            {
              frame_index: 0,
              quantification: {
                component_count: 0,
                positive_area_fraction: 0,
                roi_positive_area_fraction: 0,
              },
            },
            {
              frame_index: 1,
              quantification: {
                component_count: 1,
                positive_area_fraction: 0.08,
                roi_positive_area_fraction: 0,
              },
            },
            {
              frame_index: 2,
              quantification: {
                component_count: 2,
                positive_area_fraction: 0.12,
                roi_positive_area_fraction: 0.03,
              },
            },
          ],
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(filterHotspotTimelineItems(timeline, "positive_area").map((item) => item.frameLabel)).toEqual([
      "帧 1",
      "帧 2",
    ]);
    expect(filterHotspotTimelineItems(timeline, "roi_hit").map((item) => item.frameLabel)).toEqual(["帧 2"]);
    expect(filterHotspotTimelineItems(timeline, "with_candidates").map((item) => item.candidateCount)).toEqual([1, 2]);
  });

  it("derives timeline manifest summary and trace labels", () => {
    const summary = timelineManifestSummaryFromRun(
      {
        fused_outputs: {
          timeline_manifest_path: "timeline_manifest.json",
          timeline_summary: {
            timeline_manifest_path: "timeline_manifest.json",
            timeline_scope: "full_duration_index_with_scored_candidates",
            sampling_strategy: "quality_peak",
            frame_count: 120,
            duration_sec: 12,
            fps: 10,
            timeline_stride: 2,
            selected_frame_count: 5,
            candidate_frame_count: 24,
            duplicate_candidate_count: 3,
            skipped_duplicate_count: 2,
            candidate_trace: [
              { frame_index: 8, selection_rank: 1, selection_score: 0.91, selected: true },
              {
                frame_index: 9,
                selection_rank: 2,
                selection_score: 0.88,
                skipped_as_duplicate: true,
                duplicate_of_frame_index: 8,
                duplicate_similarity: 0.992,
              },
            ],
            duplicate_trace: [
              {
                frame_index: 9,
                selection_rank: 2,
                selection_score: 0.88,
                skipped_as_duplicate: true,
                duplicate_of_frame_index: 8,
                duplicate_similarity: 0.992,
              },
            ],
          },
        },
      },
      (path) => `/download?path=${path}`,
    );

    expect(summary).toMatchObject({
      manifestPath: "timeline_manifest.json",
      manifestHref: "/download?path=timeline_manifest.json",
      scopeLabel: "全时长低频索引",
      samplingLabel: "质量峰值采样",
      frameCountLabel: "120 帧",
      durationLabel: "12.00s",
      fpsLabel: "10.00 fps",
      coverageLabel: "每 2 帧索引",
      selectedFrameCountLabel: "5 帧",
      candidateFrameCountLabel: "24 帧",
      duplicateCountLabel: "3 帧",
      skippedDuplicateCountLabel: "2 帧",
    });
    expect(summary?.traceItems[0]).toMatchObject({
      frameLabel: "帧 8",
      rankLabel: "#1",
      scoreLabel: "0.910",
      statusLabel: "已选中",
    });
    expect(summary?.duplicateItems[0].duplicateLabel).toBe("近似帧 8 · 0.992");
  });

  it("derives fluorescence fusion V2 evidence metadata and colorbar preview", () => {
    const summary = fusionEvidenceSummaryFromRun(
      {
        fused_outputs: {
          outputs: {
            colorbar_path: "case_001_fluorescence_colorbar.png",
          },
          fusion: {
            algorithm_version: "fluorescence_fusion_v2",
            method: "background_corrected_registered_alpha_blend_pseudocolor",
            alpha: 0.45,
            white_light_size: [3840, 2160],
            fluorescence_original_size: [3840, 2160],
            fluorescence_resized_to_white_light: false,
            registration_details: {
              method: "phase_correlation_translation",
              applied: true,
              translation_xy: [2.25, -1.5],
              response: 0.4234,
              reason: "phase_correlation_response_met",
            },
            background_correction: {
              method: "percentile_floor_subtraction",
              percentile: 5,
              baseline: 12.5,
              applied: true,
            },
            colorbar: {
              threshold_marker: 0.6,
              range: [0, 1],
            },
          },
        },
      },
      (path) => `/preview?path=${path}`,
    );

    expect(summary).toMatchObject({
      algorithmVersionLabel: "fluorescence_fusion_v2",
      methodLabel: "背景扣除 + 平移配准 + 伪彩融合",
      thresholdLabel: "0.60",
      alphaLabel: "0.45",
      backgroundLabel: "已扣除 · P5 · baseline 12.5",
      registrationLabel: "已应用 · 相位相关平移 · phase_correlation_response_met",
      translationLabel: "2.25, -1.5 px",
      responseLabel: "0.423",
      resizeLabel: "原始匹配 · 白光 3840, 2160 · 荧光 3840, 2160",
      colorbarPath: "case_001_fluorescence_colorbar.png",
      colorbarPreviewSrc: "/preview?path=case_001_fluorescence_colorbar.png",
    });
  });

  it("derives normalized candidate and ROI overlays for image previews", () => {
    const candidateOverlays = candidateOverlaysFromRegions([
      {
        candidate_id: "cand_1",
        risk_type: "video_keyframe_hotspot",
        metadata: {
          bbox_normalized: { type: "rect", x: 0.2, y: 0.25, width: 0.3, height: 0.35 },
        },
      },
    ]);
    const roiOverlays = roiOverlaysFromRegions([
      {
        roi_id: "roi_1",
        label: "manual_roi",
        source: "manual",
        geometry: { type: "rect", x: 0.1, y: 0.15, width: 0.4, height: 0.45 },
      },
    ]);

    expect(candidateOverlays[0]).toMatchObject({
      key: "candidate-cand_1",
      tone: "candidate",
      x: 0.2,
      y: 0.25,
      width: 0.3,
      height: 0.35,
    });
    expect(roiOverlays[0]).toMatchObject({
      key: "roi-roi_1",
      label: "manual_roi",
      tone: "roi",
      x: 0.1,
      y: 0.15,
      width: 0.4,
      height: 0.45,
    });
  });
});
