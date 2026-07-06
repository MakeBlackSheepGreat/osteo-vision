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
  cameraStream: null,
  cameraActive: false,
  cameraStatusLabel: "未连接",
  isOpeningCamera: false,
  operationMessage: "",
  operationMessageType: "info" as const,
  realtimeVideoActive: false,
};

describe("CaseWorkspaceControls video stream area", () => {
  it("shows selected MP4 examples in the camera/video stream area", () => {
    const wrapper = mount(CaseWorkspaceControls, {
      props: {
        ...baseProps,
        videoStreamPreviewSrc: "/files/video?path=demo.mp4",
        videoStreamPreviewLabel: "demo.mp4",
      },
      global: {
        stubs: {
          AppButton: true,
          AppIcon: true,
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.find(".stream-panel-copy strong").text()).toBe("视频流输入");
    expect(wrapper.find(".stream-preview-viewport.has-file-video").exists()).toBe(true);
    expect(wrapper.find("video.stream-file-preview").attributes("src")).toBe("/files/video?path=demo.mp4");
    expect(wrapper.text()).toContain("MP4 示例正在视频流区预览");
  });
});
