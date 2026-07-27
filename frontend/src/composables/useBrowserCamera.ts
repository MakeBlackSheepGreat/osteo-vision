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

export interface BrowserCameraDevice {
  deviceId: string;
  label: string;
}

export function useBrowserCamera(options: BrowserCameraOptions) {
  const cameraStream = ref<MediaStream | null>(null);
  const fluorescenceCameraStream = ref<MediaStream | null>(null);
  const isOpeningCamera = ref(false);
  const isOpeningFluorescenceCamera = ref(false);
  const cameraDevices = ref<BrowserCameraDevice[]>([]);
  const whiteCameraDeviceId = ref("");
  const fluorescenceCameraDeviceId = ref("");
  let captureVideo: HTMLVideoElement | null = null;
  let fluorescenceCaptureVideo: HTMLVideoElement | null = null;
  let cameraStartGeneration = 0;
  let fluorescenceCameraStartGeneration = 0;

  const cameraActive = computed(() => Boolean(cameraStream.value));
  const fluorescenceCameraActive = computed(() => Boolean(fluorescenceCameraStream.value));
  const dualCameraActive = computed(() => cameraActive.value && fluorescenceCameraActive.value);
  const cameraStatusLabel = computed(() => {
    if (isOpeningCamera.value) return "正在请求浏览器摄像头权限";
    if (dualCameraActive.value) return "白光与荧光摄像头已连接，可启动双通道实时分析";
    if (cameraActive.value) return "白光摄像头已连接，可抓取关键帧进入平台分析";
    return "未连接，需浏览器授权后使用";
  });

  async function startCameraInput(): Promise<boolean> {
    return startCamera("white_light");
  }

  async function startFluorescenceCameraInput(): Promise<boolean> {
    return startCamera("fluorescence");
  }

  async function refreshCameraDevices(): Promise<void> {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const devices = await navigator.mediaDevices.enumerateDevices();
    cameraDevices.value = devices
      .filter((device) => device.kind === "videoinput")
      .map((device, index) => ({
        deviceId: device.deviceId,
        label: device.label || `摄像头 ${index + 1}`,
      }));
    if (!whiteCameraDeviceId.value && cameraDevices.value.length) {
      whiteCameraDeviceId.value = cameraDevices.value[0].deviceId;
    }
    if (!fluorescenceCameraDeviceId.value) {
      fluorescenceCameraDeviceId.value = cameraDevices.value.find(
        (device) => device.deviceId !== whiteCameraDeviceId.value,
      )?.deviceId ?? "";
    }
  }

  async function setWhiteCameraDevice(deviceId: string): Promise<void> {
    if (!deviceId || deviceId === whiteCameraDeviceId.value) return;
    if (deviceId === fluorescenceCameraDeviceId.value) {
      options.onMessage?.("白光与荧光通道必须选择不同的摄像头设备。", "error");
      return;
    }
    whiteCameraDeviceId.value = deviceId;
    if (!cameraActive.value) return;
    stopWhiteCameraInput();
    await startCameraInput();
  }

  async function setFluorescenceCameraDevice(deviceId: string): Promise<void> {
    if (!deviceId || deviceId === fluorescenceCameraDeviceId.value) return;
    if (deviceId === whiteCameraDeviceId.value) {
      options.onMessage?.("白光与荧光通道必须选择不同的摄像头设备。", "error");
      return;
    }
    fluorescenceCameraDeviceId.value = deviceId;
    if (!fluorescenceCameraActive.value) return;
    stopFluorescenceCameraInput();
    await startFluorescenceCameraInput();
  }

  async function startCamera(role: "white_light" | "fluorescence"): Promise<boolean> {
    if (role === "white_light" && cameraStream.value) return true;
    if (role === "fluorescence" && fluorescenceCameraStream.value) return true;
    if (!navigator.mediaDevices?.getUserMedia) {
      options.onMessage?.("当前浏览器不支持摄像头访问，请使用支持 MediaDevices API 的浏览器。", "error");
      return false;
    }

    if (role === "fluorescence") {
      await refreshCameraDevices();
      if (!fluorescenceCameraDeviceId.value) {
        options.onMessage?.("未检测到第二路可用摄像头，无法启动双通道实时分析。", "error");
        return false;
      }
      if (fluorescenceCameraDeviceId.value === whiteCameraDeviceId.value) {
        options.onMessage?.("白光与荧光通道必须选择不同的摄像头设备。", "error");
        return false;
      }
    }
    if (
      role === "white_light"
      && fluorescenceCameraActive.value
      && whiteCameraDeviceId.value
      && whiteCameraDeviceId.value === fluorescenceCameraDeviceId.value
    ) {
      options.onMessage?.("白光与荧光通道必须选择不同的摄像头设备。", "error");
      return false;
    }

    const requestGeneration = role === "white_light"
      ? ++cameraStartGeneration
      : ++fluorescenceCameraStartGeneration;
    if (role === "white_light") isOpeningCamera.value = true;
    else isOpeningFluorescenceCamera.value = true;
    options.onMessage?.(role === "white_light" ? "正在请求白光摄像头权限..." : "正在请求荧光摄像头权限...");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: cameraConstraints(role === "white_light" ? whiteCameraDeviceId.value : fluorescenceCameraDeviceId.value),
        audio: false,
      });
      const currentGeneration = role === "white_light" ? cameraStartGeneration : fluorescenceCameraStartGeneration;
      if (requestGeneration !== currentGeneration) {
        stream.getTracks().forEach((track) => track.stop());
        return false;
      }
      const capture = document.createElement("video");
      capture.muted = true;
      capture.playsInline = true;
      capture.srcObject = stream;
      await capture.play().catch(() => undefined);
      if (role === "white_light") {
        cameraStream.value = stream;
        captureVideo = capture;
      } else {
        fluorescenceCameraStream.value = stream;
        fluorescenceCaptureVideo = capture;
      }
      await refreshCameraDevices();
      options.onMessage?.(
        role === "white_light"
          ? "白光摄像头已打开，可抓取关键帧或连接荧光摄像头。"
          : "荧光摄像头已打开，双通道实时配准融合已就绪。",
      );
      return true;
    } catch (error) {
      const currentGeneration = role === "white_light" ? cameraStartGeneration : fluorescenceCameraStartGeneration;
      if (requestGeneration === currentGeneration) {
        options.onMessage?.(cameraAccessErrorMessage(error), "error");
      }
      return false;
    } finally {
      const currentGeneration = role === "white_light" ? cameraStartGeneration : fluorescenceCameraStartGeneration;
      if (requestGeneration === currentGeneration) {
        if (role === "white_light") isOpeningCamera.value = false;
        else isOpeningFluorescenceCamera.value = false;
      }
    }
  }

  function stopCameraInput() {
    cameraStartGeneration += 1;
    fluorescenceCameraStartGeneration += 1;
    isOpeningCamera.value = false;
    isOpeningFluorescenceCamera.value = false;
    stopWhiteCameraInput();
    stopFluorescenceCameraInput();
    options.onStop?.();
  }

  function stopWhiteCameraInput() {
    cameraStartGeneration += 1;
    cameraStream.value?.getTracks().forEach((track) => track.stop());
    cameraStream.value = null;
    releaseCaptureVideo(captureVideo);
    captureVideo = null;
  }

  function stopFluorescenceCameraInput() {
    fluorescenceCameraStartGeneration += 1;
    fluorescenceCameraStream.value?.getTracks().forEach((track) => track.stop());
    fluorescenceCameraStream.value = null;
    releaseCaptureVideo(fluorescenceCaptureVideo);
    fluorescenceCaptureVideo = null;
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

  async function captureDualCameraFrames(): Promise<[Blob, Blob]> {
    if (!captureVideo || !fluorescenceCaptureVideo || !dualCameraActive.value) {
      throw new Error("白光与荧光摄像头均连接后才能抓取双通道画面。");
    }
    return Promise.all([
      captureVideoFrameAsJpeg(captureVideo, LIVE_FRAME_JPEG_QUALITY, LIVE_FRAME_MAX_LONG_SIDE, "白光摄像头"),
      captureVideoFrameAsJpeg(fluorescenceCaptureVideo, LIVE_FRAME_JPEG_QUALITY, LIVE_FRAME_MAX_LONG_SIDE, "荧光摄像头"),
    ]);
  }

  onBeforeUnmount(stopCameraInput);

  return {
    cameraStream,
    fluorescenceCameraStream,
    cameraActive,
    fluorescenceCameraActive,
    dualCameraActive,
    cameraStatusLabel,
    isOpeningCamera,
    isOpeningFluorescenceCamera,
    cameraDevices,
    whiteCameraDeviceId,
    fluorescenceCameraDeviceId,
    startCameraInput,
    startFluorescenceCameraInput,
    stopCameraInput,
    stopFluorescenceCameraInput,
    setWhiteCameraDevice,
    setFluorescenceCameraDevice,
    captureCameraFrame,
    captureDualCameraFrames,
  };
}

function cameraConstraints(deviceId: string): MediaTrackConstraints {
  return {
    ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: "environment" }),
    width: { ideal: 1280 },
    height: { ideal: 720 },
    aspectRatio: { ideal: 16 / 9 },
    frameRate: { ideal: 30, max: 30 },
  };
}

function releaseCaptureVideo(video: HTMLVideoElement | null) {
  if (!video) return;
  video.pause();
  video.srcObject = null;
}

function cameraAccessErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") return "摄像头权限被拒绝，请在浏览器地址栏允许摄像头访问。";
    if (error.name === "NotFoundError") return "未检测到可用摄像头设备。";
    if (error.name === "NotReadableError") return "摄像头当前被其他程序占用，请关闭占用程序后重试。";
  }
  return "摄像头打开失败，请检查浏览器权限和设备状态。";
}
