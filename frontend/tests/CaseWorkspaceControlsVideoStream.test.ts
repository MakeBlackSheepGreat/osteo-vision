import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import CaseWorkspaceControls from "../src/components/CaseWorkspaceControls.vue";

const baseProps = {
  whiteLightPath: "",
  fluorescencePath: "",
  videoPath: "",
  videoTimepoints: "",
  alpha: 0.45,
  threshold: 0.6,
  colormap: "green" as const,
  loading: false,
  hasCase: true,
  isUploadingWhite: false,
  isUploadingFluorescence: false,
  isUploadingVideo: false,
  isLoadingVideoCandidates: false,
  isLoadingVideoPreview: false,
  selectedVideoCandidateId: "",
  selectedVideoCandidatePreviewSrc: "",
  videoCandidates: [],
  operationMessage: "",
  operationMessageType: "info" as const,
  videoInputSource: "file" as const,
  inputMode: "video" as const,
  videoMode: "single_video" as const,
  imagePairReady: false,
  imagePairOptions: [],
  selectedImagePairKey: "",
  analysisJobPolling: false,
  videoReady: false,
  cameraActive: false,
  cameraOpening: false,
  cameraManualAnalysisBusy: false,
  cameraAnalysisRunning: false,
  cameraContinuousAnalysisStarting: false,
  cameraContinuousAnalysisActive: false,
  cameraAnalysisIntervalSec: 5,
  cameraContinuousAnalysisStatus: "连续关键帧分析未启动",
  cameraStatusLabel: "未连接，需浏览器授权后使用",
  liveSessionReady: false,
};

describe("CaseWorkspaceControls video stream area", () => {
  it("offers mutually exclusive file and camera input controls", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: baseProps,
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.text()).toContain("选择 MP4 视频");
    expect(wrapper.find(".live-stream-control-card").exists()).toBe(false);

    const cameraSourceButton = wrapper
      .findAll('[role="tab"]')
      .find((button) => button.text().includes("浏览器摄像头"));
    await cameraSourceButton?.trigger("click");
    expect(wrapper.emitted("update:videoInputSource")?.[0]).toEqual(["camera"]);

    await wrapper.setProps({ videoInputSource: "camera" });
    expect(wrapper.text()).toContain("开启摄像头");
    expect(wrapper.text()).not.toContain("选择 MP4 视频");
  });

  it("uses MP4 video as the default official input without rendering a duplicate left preview", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: baseProps,
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.find(".video-stream-input-panel").exists()).toBe(false);
    expect(wrapper.find(".stream-preview-viewport").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("实时预览");
    expect(wrapper.text()).toContain("MP4 视频");
    expect(wrapper.text()).toContain("选择 MP4 视频");
    expect(wrapper.text()).toContain("启动离线关键帧分析");
    expect(wrapper.text()).not.toContain("开启摄像头");
    expect(wrapper.text()).not.toContain("官方 MP4 视频路径");
    expect(wrapper.find('input[accept="video/mp4,.mp4"]').exists()).toBe(true);
  });

  it("keeps JPEG fusion disabled until both images are attached to the case", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        inputMode: "images",
        whiteLightPath: "artifacts/platform/uploads/white.jpg",
        fluorescencePath: "artifacts/platform/uploads/icg.jpg",
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const buttons = wrapper.findAll("button");
    const analyzeButton = buttons.find((button) => button.text().includes("开始图像融合分析"));
    expect(analyzeButton?.attributes("disabled")).toBeDefined();
    expect(wrapper.findAll('input[accept=".jpg,.jpeg,image/jpeg"]')).toHaveLength(3);

    await wrapper.setProps({ imagePairReady: true });
    expect(analyzeButton?.attributes("disabled")).toBeUndefined();
  });

  it("exposes admitted pair_id choices and emits the selected pair key", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        inputMode: "images",
        imagePairOptions: [
          { key: '["batch-01","pair-001"]', label: "pair-001 · 批次 batch-01" },
          { key: '["batch-01","pair-002"]', label: "pair-002 · 批次 batch-01" },
        ],
        selectedImagePairKey: '["batch-01","pair-001"]',
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const selector = wrapper.get('select[aria-label="已准入同步 JPEG 图像对"]');
    expect(selector.text()).toContain("pair-001");
    expect(selector.text()).toContain("pair-002");
    await selector.setValue('["batch-01","pair-002"]');
    expect(wrapper.emitted("selectImagePair")?.[0]).toEqual(['["batch-01","pair-002"]']);
  });

  it("keeps camera controls in the left control sidebar", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoInputSource: "camera",
        cameraActive: true,
        cameraStatusLabel: "摄像头已连接，可抓取关键帧进入平台分析",
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.find(".live-stream-control-card").exists()).toBe(true);
    expect(wrapper.text()).toContain("关闭摄像头");
    expect(wrapper.text()).toContain("抓取关键帧分析");
    expect(wrapper.text()).toContain("开始实时分割");

    const buttons = wrapper.findAll("button");
    const continuousStart = buttons.find((button) => button.text().includes("开始实时分割"));
    expect(continuousStart).toBeDefined();
    await continuousStart?.trigger("click");
    expect(wrapper.emitted("startContinuousCameraAnalysis")).toHaveLength(1);

    await wrapper.get('select[aria-label="连续关键帧采样间隔"]').setValue("10");
    expect(wrapper.emitted("updateCameraAnalysisInterval")?.[0]).toEqual([10]);
    expect(wrapper.text()).toContain("推理完成后立即继续");
  });

  it("supports paired MP4 inputs and exposes synchronization commands", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoMode: "paired_videos",
        multichannelWhitePath: "C:/demo/white.mp4",
        multichannelFluorescencePath: "C:/demo/icg.mp4",
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.text()).toContain("更换白光 MP4");
    expect(wrapper.text()).toContain("更换荧光 MP4");
    expect(wrapper.text()).toContain("可选设备叠加 MP4");
    expect(wrapper.text()).toContain("准备同步预览");
    expect(wrapper.text()).toContain("运行双通道融合分析");
    const prepare = wrapper.findAll("button").find((button) => button.text().includes("准备同步预览"));
    expect(prepare?.attributes("disabled")).toBeUndefined();
    await prepare?.trigger("click");
    expect(wrapper.emitted("prepareMultichannelSession")).toHaveLength(1);
  });

  it("emits each video workspace mode from the visible tabs", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: baseProps,
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const modeTabs = wrapper.findAll(".video-mode-tabs button");
    const paired = modeTabs.find((button) => button.text() === "双通道视频");
    await paired?.trigger("click");
    expect(wrapper.emitted("update:videoMode")?.[0]).toEqual(["paired_videos"]);

    const composite = modeTabs.find((button) => button.text() === "合成三视图");
    await composite?.trigger("click");
    expect(wrapper.emitted("update:videoMode")?.[1]).toEqual(["composite_layout"]);
  });

  it("labels the browser camera as a single-channel extension", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: { ...baseProps, videoInputSource: "camera" },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.find(".live-stream-control-card").html()).toContain('title="单路浏览器摄像头"');
  });

  it("places live stream controls before analysis parameters", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: { ...baseProps, videoInputSource: "camera" },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const cards = wrapper.findAll(".control-card");
    const liveStreamIndex = cards.findIndex((card) => card.classes().includes("live-stream-control-card"));
    const analysisParameterIndex = cards.findIndex((card) => card.classes().includes("analysis-parameter-card"));

    expect(liveStreamIndex).toBeGreaterThanOrEqual(0);
    expect(analysisParameterIndex).toBeGreaterThanOrEqual(0);
    expect(liveStreamIndex).toBeLessThan(analysisParameterIndex);
  });

  it("keeps live camera actions available while an unrelated workspace task is loading", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoInputSource: "camera",
        loading: true,
        cameraActive: true,
        cameraStatusLabel: "摄像头已连接，可抓取关键帧进入平台分析",
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const buttons = wrapper.findAll("button");
    const capture = buttons.find((button) => button.text().includes("抓取关键帧分析"));
    const continuousStart = buttons.find((button) => button.text().includes("开始实时分割"));
    expect(capture?.attributes("disabled")).toBeUndefined();
    expect(continuousStart?.attributes("disabled")).toBeUndefined();
  });

  it("locks manual and continuous actions while a manual keyframe request is pending", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoInputSource: "camera",
        cameraActive: true,
        cameraManualAnalysisBusy: true,
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    const buttons = wrapper.findAll("button");
    const capture = buttons.find((button) => button.text().includes("关键帧分析中"));
    const continuousStart = buttons.find((button) => button.text().includes("开始实时分割"));
    expect(capture?.attributes("disabled")).toBeDefined();
    expect(capture?.attributes("aria-busy")).toBe("true");
    expect(capture?.attributes("title")).toContain("仍在处理");
    expect(continuousStart?.attributes("disabled")).toBeDefined();

    await capture?.trigger("click");
    await continuousStart?.trigger("click");
    expect(wrapper.emitted("captureCameraFrame")).toBeUndefined();
    expect(wrapper.emitted("startContinuousCameraAnalysis")).toBeUndefined();
  });

  it("locks manual capture while continuous analysis is starting or active", async () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoInputSource: "camera",
        cameraActive: true,
        cameraContinuousAnalysisStarting: true,
      },
      global: {
        stubs: {
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    let capture = wrapper.findAll("button").find((button) => button.text().includes("实时分割启动中"));
    expect(capture?.attributes("disabled")).toBeDefined();

    await wrapper.setProps({
      cameraContinuousAnalysisStarting: false,
      cameraContinuousAnalysisActive: true,
    });
    capture = wrapper.findAll("button").find((button) => button.text().includes("连续分析运行中"));
    expect(capture?.attributes("disabled")).toBeDefined();
    expect(capture?.attributes("title")).toContain("先停止连续实时分割");
  });
});
