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
});
