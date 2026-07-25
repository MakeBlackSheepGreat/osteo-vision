import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnalysisExportPanel from "../src/components/AnalysisExportPanel.vue";

describe("AnalysisExportPanel", () => {
  it("renders export links, summary, and a compact artifact handoff", () => {
    const wrapper = mount(AnalysisExportPanel, {
      props: {
        exportPath: "artifacts/platform/case/export.zip",
        exportLinks: [
          {
            label: "证据包 ZIP",
            path: "artifacts/platform/case/export.zip",
            href: "/files/download?path=export.zip",
          },
        ],
        exportSummary: {
          analysis_run_count: 2,
          candidate_region_count: 3,
          total_artifact_count: 5,
          quantification_row_count: 8,
          bundle_size_bytes: 1536,
          dicom_included: true,
        },
        artifactEntries: [
          { kind: "video_segmentation_manifest", path: "manifest.json", size_bytes: 2048 },
          { kind: "unknown_kind", path: "raw.bin", size_bytes: null },
        ],
      },
      global: {
        stubs: {
          AppIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("证据包已导出");
    expect(wrapper.find("a.export-link").attributes("href")).toBe("/files/download?path=export.zip");
    expect(wrapper.text()).toContain("分析次数");
    expect(wrapper.text()).toContain("2");
    expect(wrapper.text()).toContain("1.5 KB");
    expect(wrapper.text()).toContain("MP4 分割清单");
    expect(wrapper.text()).toContain("unknown_kind");
    expect(wrapper.text()).toContain("证据文件共 2 项");
    expect(wrapper.find("a.export-report-link").attributes("href")).toBe("/report");
    expect(wrapper.text()).toContain("artifacts/platform/case/export.zip");
  });
});
