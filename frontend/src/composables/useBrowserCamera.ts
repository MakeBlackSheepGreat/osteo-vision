import { computed, onBeforeUnmount, ref } from "vue";

export interface BrowserCameraOptions {
  onMessage?: (message: string, type?: "info" | "error") => void;
  onStop?: () => void;
}

export function useBrowserCamera(options: BrowserCameraOptions) {
  const cameraStream = ref<MediaStream | null>(null);
  const isOpeningCamera = ref(false);

  const cameraActive = computed(() => Boolean(cameraStream.value));
  const cameraStatusLabel = computed(() => {
    if (isOpeningCamera.value) return "正在请求浏览器摄像头权限";
    if (cameraActive.value) return "摄像头已连接，仅作为实时预览与原型输入";
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
      // 前端只做本地实时预览，不保存患者视频帧；病例登记由页面业务函数完成。
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      cameraStream.value = stream;
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
    options.onStop?.();
  }

  onBeforeUnmount(stopCameraInput);

  return {
    cameraStream,
    cameraActive,
    cameraStatusLabel,
    isOpeningCamera,
    startCameraInput,
    stopCameraInput,
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
