import { describe, expect, it } from "vitest";

import { errorMessage, normalizeWarning } from "../src/utils/caseDisplay";

describe("case display error messages", () => {
  it("turns upload signature errors into actionable Chinese copy", () => {
    const message = errorMessage({
      status: 415,
      body: { detail: "uploaded image content does not match the filename extension" },
    });

    expect(message).toContain("上传文件内容与图片后缀不匹配");
  });

  it("uses backend detail objects for queue and conflict errors", () => {
    const conflict = errorMessage({
      status: 409,
      body: {
        detail: {
          code: "case_analysis_job_already_active",
          message: "An analysis job is already queued or running for this case.",
        },
      },
    });
    const capacity = errorMessage({
      status: 429,
      body: {
        detail: {
          code: "upload_keyframe_job_capacity_exceeded",
          message: "Too many keyframe extraction jobs are queued or running. Try again later.",
        },
      },
    });

    expect(conflict).toBe("该病例或视频已有后台任务正在运行，请等待完成后再重试。");
    expect(capacity).toBe("后台任务队列已满，请等待当前任务完成后再重试。");
  });

  it("turns unreadable upload errors into actionable Chinese copy", () => {
    const message = errorMessage({
      status: 422,
      body: {
        detail: {
          code: "upload_content_unreadable",
          message: "Uploaded file could not be decoded or validated.",
          reason: "video capture could not be opened",
        },
      },
    });

    expect(message).toContain("上传文件无法解码");
  });

  it("translates missing dual-channel warnings used by failed analysis runs", () => {
    const warning = normalizeWarning(
      {
        code: "missing_dual_channel_pair",
        message: "Dual-channel white-light and fluorescence inputs are required for fusion.",
        blocking: true,
      },
      0,
    );

    expect(warning.message).toBe("需要同时提供白光和 ICG 荧光输入后才能进行融合分析。");
  });
});
