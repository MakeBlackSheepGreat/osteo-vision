export const LIVE_FRAME_JPEG_QUALITY = 0.85;
export const LIVE_FRAME_MAX_LONG_SIDE = 960;

export async function captureVideoFrameAsJpeg(
  video: HTMLVideoElement,
  quality = LIVE_FRAME_JPEG_QUALITY,
  maxLongSide = LIVE_FRAME_MAX_LONG_SIDE,
  sourceLabel = "视频流",
): Promise<Blob> {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    throw new Error(`${sourceLabel}画面尚未就绪，请稍候重试。`);
  }

  const canvas = document.createElement("canvas");
  const scale = Math.min(1, maxLongSide / Math.max(width, height));
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器无法创建关键帧画布。");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("浏览器关键帧 JPEG 编码失败。"))),
      "image/jpeg",
      quality,
    );
  });
}
