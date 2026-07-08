import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import CaseWorkspaceControls from "../src/components/CaseWorkspaceControls.vue";

const baseProps = {
  whiteLightPath: "",
  fluorescencePath: "",
  videoPath: "artifacts/platform/uploads/demo.mp4",
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
};

describe("CaseWorkspaceControls video stream area", () => {
  it("keeps MP4 input controls without rendering a duplicate left video preview", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: baseProps,
      global: {
        stubs: {
          AppButton: true,
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.find(".video-stream-input-panel").exists()).toBe(false);
    expect(wrapper.find(".stream-preview-viewport").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("实时预览");
    expect(wrapper.text()).toContain("官方 MP4 视频路径");
    expect(wrapper.find(".analysis-action-row").exists()).toBe(true);
  });
});
