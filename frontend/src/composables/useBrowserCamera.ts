import { computed, onBeforeUnmount, ref } from "vue";

import {
  captureVideoFrameAsJpeg,
  LIVE_FRAME_JPEG_QUALITY,
  LIVE_FRAME_MAX_LONG_SIDE,
} from "@/utils/browserFrameCapture";

export interface BrowserCameraOptions {
  onMessage?: (message: string, type?: "info" | "error") => void;
  onStop?: () => void;
}

export function useBrowserCamera(options: BrowserCameraOptions) {
  const cameraStream = ref<MediaStream | null>(null);
  const isOpeningCamera = ref(false);
  let captureVideo: HTMLVideoElement | null = null;

  const cameraActive = computed(() => Boolean(cameraStream.value));
  const cameraStatusLabel = computed(() => {
    if (isOpeningCamera.value) return "正在请求浏览器摄像头权限";
    if (cameraActive.value) return "摄像头已连接，可抓取关键帧进入平台分析";
    return "未连接，需浏览器授权后使用";
  });

  async function startCameraInput(): Promise<boolean> {
    if (cameraStream.value) return true;
    if (!navigator.mediaDevices?.getUserMedia) {
      options.onMessage?.("当前浏览器不支持摄像头访问，请使用支持 MediaDevices API 的浏览器。", "error");
      return false;
    }

    isOpeningCamera.value = true;
    options.onMessage?.("正在请求摄像头权限...");
    try {
      // 默认保持本地预览；仅在用户触发关键帧分析时上传当前 JPEG 帧。
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1280 },
          height: { ideal: 720 },
          aspectRatio: { ideal: 16 / 9 },
          frameRate: { ideal: 30, max: 30 },
        },
        audio: false,
      });
      cameraStream.value = stream;
      captureVideo = document.createElement("video");
      captureVideo.muted = true;
      captureVideo.playsInline = true;
      captureVideo.srcObject = stream;
      await captureVideo.play().catch(() => undefined);
      options.onMessage?.("摄像头已打开，可写入病例或启动实时视频分析。");
      return true;
    } catch (error) {
      options.onMessage?.(cameraAccessErrorMessage(error), "error");
      return false;
    } finally {
      isOpeningCamera.value = false;
    }
  }

  function stopCameraInput() {
    // 主动释放媒体轨道，避免离开页面后摄像头仍被浏览器占用。
    cameraStream.value?.getTracks().forEach((track) => track.stop());
    cameraStream.value = null;
    if (captureVideo) {
      captureVideo.pause();
      captureVideo.srcObject = null;
      captureVideo = null;
    }
    options.onStop?.();
  }

  async function captureCameraFrame(): Promise<Blob> {
    if (!captureVideo || !cameraStream.value) {
      throw new Error("摄像头尚未连接。");
    }
    return captureVideoFrameAsJpeg(
      captureVideo,
      LIVE_FRAME_JPEG_QUALITY,
      LIVE_FRAME_MAX_LONG_SIDE,
      "摄像头",
    );
  }

  onBeforeUnmount(stopCameraInput);

  return {
    cameraStream,
    cameraActive,
    cameraStatusLabel,
    isOpeningCamera,
    startCameraInput,
    stopCameraInput,
    captureCameraFrame,
  };
}

function cameraAccessErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") return "摄像头权限被拒绝，请在浏览器地址栏允许摄像头访问。";
    if (error.name === "NotFoundError") return "未检测到可用摄像头设备。";
    if (error.name === "NotReadableError") return "摄像头当前被其他程序占用，请关闭占用程序后重试。";
  }
  return "摄像头打开失败，请检查浏览器权限和设备状态。";
}
