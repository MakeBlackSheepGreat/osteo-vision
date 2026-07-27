import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useBrowserCamera } from "../src/composables/useBrowserCamera";

let originalMediaDevicesDescriptor: PropertyDescriptor | undefined;

afterEach(() => {
  if (originalMediaDevicesDescriptor) {
    Object.defineProperty(navigator, "mediaDevices", originalMediaDevicesDescriptor);
  } else {
    Reflect.deleteProperty(navigator, "mediaDevices");
  }
  originalMediaDevicesDescriptor = undefined;
  vi.restoreAllMocks();
});

describe("useBrowserCamera", () => {
  it("releases a camera stream that resolves after the user switches back to file input", async () => {
    let resolveStream: ((stream: MediaStream) => void) | undefined;
    const pendingStream = new Promise<MediaStream>((resolve) => {
      resolveStream = resolve;
    });
    const stopTrack = vi.fn();
    const getUserMedia = vi.fn(() => pendingStream);
    originalMediaDevicesDescriptor = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });

    let camera: ReturnType<typeof useBrowserCamera> | undefined;
    const wrapper = mount(defineComponent({
      setup() {
        camera = useBrowserCamera({});
        return () => h("div");
      },
    }));

    const opening = camera!.startCameraInput();
    expect(camera!.isOpeningCamera.value).toBe(true);
    camera!.stopCameraInput();
    expect(camera!.isOpeningCamera.value).toBe(false);

    resolveStream!({
      getTracks: () => [{ stop: stopTrack }],
    } as unknown as MediaStream);

    await expect(opening).resolves.toBe(false);
    expect(stopTrack).toHaveBeenCalledOnce();
    expect(camera!.cameraActive.value).toBe(false);
    wrapper.unmount();
  });

  it("opens two distinct camera devices and rejects duplicate channel selection", async () => {
    const whiteStop = vi.fn();
    const fluorescenceStop = vi.fn();
    const whiteStream = { getTracks: () => [{ stop: whiteStop }] } as unknown as MediaStream;
    const fluorescenceStream = { getTracks: () => [{ stop: fluorescenceStop }] } as unknown as MediaStream;
    const getUserMedia = vi
      .fn()
      .mockResolvedValueOnce(whiteStream)
      .mockResolvedValueOnce(fluorescenceStream);
    const enumerateDevices = vi.fn().mockResolvedValue([
      { kind: "videoinput", deviceId: "camera-white", label: "白光摄像头" },
      { kind: "videoinput", deviceId: "camera-fluorescence", label: "荧光摄像头" },
    ] as MediaDeviceInfo[]);
    originalMediaDevicesDescriptor = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia, enumerateDevices },
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const onMessage = vi.fn();

    let camera: ReturnType<typeof useBrowserCamera> | undefined;
    const wrapper = mount(defineComponent({
      setup() {
        camera = useBrowserCamera({ onMessage });
        return () => h("div");
      },
    }));

    await expect(camera!.startCameraInput()).resolves.toBe(true);
    await expect(camera!.startFluorescenceCameraInput()).resolves.toBe(true);

    expect(camera!.dualCameraActive.value).toBe(true);
    expect(camera!.whiteCameraDeviceId.value).toBe("camera-white");
    expect(camera!.fluorescenceCameraDeviceId.value).toBe("camera-fluorescence");
    expect(getUserMedia).toHaveBeenCalledTimes(2);

    await camera!.setWhiteCameraDevice("camera-fluorescence");
    expect(camera!.whiteCameraDeviceId.value).toBe("camera-white");
    expect(onMessage).toHaveBeenCalledWith("白光与荧光通道必须选择不同的摄像头设备。", "error");
    expect(getUserMedia).toHaveBeenCalledTimes(2);

    wrapper.unmount();
    expect(whiteStop).toHaveBeenCalledOnce();
    expect(fluorescenceStop).toHaveBeenCalledOnce();
  });
});
