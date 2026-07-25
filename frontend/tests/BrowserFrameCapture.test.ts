import { describe, expect, it, vi } from "vitest";

import { captureVideoFrameAsJpeg } from "../src/utils/browserFrameCapture";

describe("browser frame capture", () => {
  it("encodes the current camera video frame as JPEG", async () => {
    const video = document.createElement("video");
    Object.defineProperty(video, "videoWidth", { value: 640 });
    Object.defineProperty(video, "videoHeight", { value: 480 });
    Object.defineProperty(video, "readyState", { value: HTMLMediaElement.HAVE_CURRENT_DATA });
    const drawImage = vi.fn();
    const blob = new Blob(["jpeg"], { type: "image/jpeg" });
    const getContext = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage } as never);
    const toBlob = vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => callback(blob));

    await expect(captureVideoFrameAsJpeg(video)).resolves.toBe(blob);
    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 512, 384);

    getContext.mockRestore();
    toBlob.mockRestore();
  });

  it("fails before a camera frame is ready", async () => {
    const video = document.createElement("video");
    await expect(captureVideoFrameAsJpeg(video)).rejects.toThrow("视频流画面尚未就绪");
  });

  it("downscales a 4K browser frame for the live inference transport", async () => {
    const video = document.createElement("video");
    Object.defineProperty(video, "videoWidth", { value: 3840 });
    Object.defineProperty(video, "videoHeight", { value: 2160 });
    Object.defineProperty(video, "readyState", { value: HTMLMediaElement.HAVE_CURRENT_DATA });
    const drawImage = vi.fn();
    const blob = new Blob(["jpeg"], { type: "image/jpeg" });
    const getContext = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage } as never);
    const toBlob = vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => callback(blob));

    await expect(captureVideoFrameAsJpeg(video)).resolves.toBe(blob);
    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 512, 288);

    getContext.mockRestore();
    toBlob.mockRestore();
  });
});
