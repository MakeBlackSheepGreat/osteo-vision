import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";

import VideoCandidateSelectorPanel from "../src/components/VideoCandidateSelectorPanel.vue";
import type { VideoCandidate } from "../src/types/case";

function candidate(overrides: Partial<VideoCandidate> = {}): VideoCandidate {
  return {
    record_id: "fluor",
    group: "public",
    title: "Fluorescence proxy video",
    source_page_original_link: "https://example.org/source",
    direct_download_link: "https://example.org/video.mp4",
    local_path: "C:\\data\\video.mp4",
    fluorescence: true,
    medical_scene: "fluorescence-guided surgery",
    usable_for_training: "enhancement_or_self_supervised_only",
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
    preview_path: "preview.jpg",
    preview_status: "cached",
    preview_error: "",
    width: 3840,
    height: 2160,
    duration_sec: 12.5,
    ...overrides,
  };
}

describe("VideoCandidateSelectorPanel", () => {
  it("hides catalog metadata and keeps import actions delegated to the parent", async () => {
    const wrapper = mount(VideoCandidateSelectorPanel, {
      props: {
        loading: false,
        hasCase: true,
        isLoadingVideoCandidates: false,
        isLoadingVideoPreview: false,
        selectedVideoCandidateId: "fluor",
        selectedVideoCandidatePreviewSrc: "/preview?path=preview.jpg",
        videoCandidates: [candidate()],
      },
      global: {
        stubs: {
          AppButton: true,
        },
      },
    });

    expect(wrapper.text()).toContain("公开视频候选（1 条）");
    expect(wrapper.text()).toContain("公开视频候选 fluor");
    expect(wrapper.text()).not.toContain("Fluorescence proxy video");
    expect(wrapper.text()).not.toContain("fluorescence-guided surgery");
    expect(wrapper.find("img").attributes("src")).toBe("/preview?path=preview.jpg");

    await wrapper.find('[icon="upload"]').trigger("click");
    expect(wrapper.emitted("importVideoCandidate")).toHaveLength(1);
  });

  it("emits a replacement candidate when filters exclude the selected item", async () => {
    const wrapper = mount(VideoCandidateSelectorPanel, {
      props: {
        loading: false,
        hasCase: true,
        isLoadingVideoCandidates: false,
        isLoadingVideoPreview: false,
        selectedVideoCandidateId: "white",
        selectedVideoCandidatePreviewSrc: "",
        videoCandidates: [
          candidate({ record_id: "fluor", fluorescence: true }),
          candidate({
            record_id: "white",
            title: "Non fluorescence video",
            fluorescence: false,
            usable_for_training: "no_labels_demo_or_self_supervised_only",
          }),
        ],
      },
      global: {
        stubs: {
          AppButton: true,
        },
      },
    });

    const channelFilter = wrapper.find(".video-library-filters select");
    await channelFilter.setValue("fluorescence");
    await nextTick();

    expect(wrapper.emitted("selectVideoCandidate")?.at(-1)).toEqual(["fluor"]);
  });
});
