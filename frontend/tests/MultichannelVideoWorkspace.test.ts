import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import MultichannelVideoWorkspace from "../src/components/MultichannelVideoWorkspace.vue";
import type { MultichannelVideoSession } from "../src/types/case";

function session(): MultichannelVideoSession {
  return {
    schema_version: "osteo-vision-multichannel-video-session-v1",
    session_id: "mcv_0123456789abcdef",
    case_id: "case-test",
    mode: "paired_videos",
    status: "ready",
    analysis_allowed: true,
    channels: [
      {
        role: "white_light",
        input_id: "input-white",
        path: "C:/demo/white.mp4",
        probe: { duration_sec: 4 },
        automatic_offset_ms: 0,
        effective_offset_ms: 0,
        source_boundary: "proxy",
      },
      {
        role: "fluorescence",
        input_id: "input-fluor",
        path: "C:/demo/fluor.mp4",
        probe: { duration_sec: 4 },
        automatic_offset_ms: 20,
        effective_offset_ms: 20,
        source_boundary: "proxy",
      },
      {
        role: "device_overlay",
        input_id: "input-overlay",
        path: "C:/demo/overlay.mp4",
        probe: { duration_sec: 4 },
        automatic_offset_ms: 0,
        effective_offset_ms: 0,
        source_boundary: "proxy",
      },
    ],
    synchronization_tolerance_ms: 33.34,
    synchronization_status: "aligned",
    initial_time_delta_ms: 20,
    common_start_sec: 0,
    common_end_sec: 4,
    common_duration_sec: 4,
    drift_correction_threshold_ms: 80,
    paired_sequence_manifest: null,
    frame_pairs: [],
    warnings: [],
    failure_reasons: [],
    source_boundary: "proxy",
    created_at: "2026-07-25T00:00:00Z",
    updated_at: "2026-07-25T00:00:00Z",
  };
}

describe("MultichannelVideoWorkspace", () => {
  it("renders an immediate paired-video workspace before synchronization is prepared", () => {
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: {
        mode: "paired_videos",
        channelPaths: {
          white_light: "C:/demo/white.mp4",
          fluorescence: "C:/demo/fluor.mp4",
        },
      },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.text()).toContain("双通道同步配准");
    expect(wrapper.text()).toContain("等待同步预览");
    expect(wrapper.text()).toContain("等待准备");
    expect(wrapper.findAll(".channel-card")).toHaveLength(4);
    expect(wrapper.findAll("video")).toHaveLength(2);
  });

  it("labels the composite-layout workspace independently before preparation", () => {
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: { mode: "composite_layout" },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.text()).toContain("合成三视图拆分与配准");
    expect(wrapper.text()).toContain("三视图受控拆分");
    expect(wrapper.text()).toContain("准备三视图拆分后显示白光视图");
  });

  it("renders the stable four-view workflow and registration evidence", () => {
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: {
        session: session(),
        task2Result: {
          frames: [
            {
              frame_index: 0,
              white_timestamp_ms: 1000,
              pair_delta_ms: 0,
              synchronization_verified: true,
              registered_fluorescence_path: "C:/result/registered.jpg",
              pseudocolor_path: "C:/result/pseudo.jpg",
              overlay_path: "C:/result/overlay.jpg",
              device_overlay_difference_path: "C:/result/difference.jpg",
              registration: {
                method: "adaptive_multiscale_registration_v2",
                applied: true,
                translation_xy: [1.5, -2],
                response: 0.84,
              },
            },
          ],
        },
      },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.findAll(".channel-card")).toHaveLength(4);
    expect(wrapper.findAll("video")).toHaveLength(3);
    expect(wrapper.text()).toContain("白光原始视频");
    expect(wrapper.text()).toContain("荧光通道");
    expect(wrapper.text()).toContain("配准融合结果");
    expect(wrapper.text()).toContain("AI 风险与不确定性");
    expect(wrapper.text()).toContain("融合 RGB 关键帧");
    expect(wrapper.text()).toContain("关键帧同步结果 · 第 1 帧");
    expect(wrapper.text()).toContain("差异热图");
    expect(wrapper.text()).toContain("adaptive_multiscale_registration_v2");
  });

  it("corrects follower drift beyond 80 ms using the white-light master clock", async () => {
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: { session: session() },
      global: { stubs: { AppIcon: true } },
    });
    const videos = wrapper.findAll("video");
    const white = videos[0].element as HTMLVideoElement;
    const fluorescence = videos[1].element as HTMLVideoElement;
    const deviceOverlay = videos[2].element as HTMLVideoElement;
    white.currentTime = 1;
    fluorescence.currentTime = 0;
    deviceOverlay.currentTime = 0;

    await videos[0].trigger("timeupdate");

    expect(fluorescence.currentTime).toBeCloseTo(1.02, 2);
    expect(deviceOverlay.currentTime).toBeCloseTo(1, 2);
  });

  it("uses an animation-frame clock to keep continuous follower videos aligned", async () => {
    const animationFrameCallbacks: FrameRequestCallback[] = [];
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);
    const requestAnimationFrame = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((callback) => {
        animationFrameCallbacks.push(callback);
        return 7;
      });
    const cancelAnimationFrame = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: { session: session() },
      global: { stubs: { AppIcon: true } },
    });
    const videos = wrapper.findAll("video");
    const white = videos[0].element as HTMLVideoElement;
    const fluorescence = videos[1].element as HTMLVideoElement;
    white.currentTime = 2;
    fluorescence.currentTime = 0;

    await videos[0].trigger("play");
    expect(requestAnimationFrame).toHaveBeenCalledTimes(1);
    expect(animationFrameCallbacks).toHaveLength(1);
    animationFrameCallbacks[0](16);

    expect(fluorescence.currentTime).toBeCloseTo(2.02, 2);
    expect(wrapper.text()).toContain("连续同步 · 漂移 0ms");

    wrapper.unmount();
    play.mockRestore();
    requestAnimationFrame.mockRestore();
    cancelAnimationFrame.mockRestore();
  });

  it("shows the AI source keyframe, playback delta, and measured inference time", () => {
    const wrapper = mount(MultichannelVideoWorkspace, {
      props: {
        session: session(),
        aiPreviewSrc: "/api/files/preview?path=ai.jpg",
        task2Result: {
          ai_source_frame_index: 3,
          ai_source_timestamp_ms: 2500,
          ai_inference_ms: 118.6,
          frames: [],
        },
      },
      global: { stubs: { AppIcon: true } },
    });

    expect(wrapper.text()).toContain("低延迟离线推理");
    expect(wrapper.text()).toContain("AI 关键帧 第 4 帧");
    expect(wrapper.text()).toContain("模型推理 119ms");
  });
});
