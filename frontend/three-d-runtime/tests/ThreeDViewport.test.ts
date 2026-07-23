import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ThreeDRuntimeSnapshot } from "../src/types";

const threeMocks = vi.hoisted(() => ({
  renderers: [] as Array<{
    dispose: ReturnType<typeof vi.fn>;
    forceContextLoss: ReturnType<typeof vi.fn>;
  }>,
}));

vi.mock("three", () => {
  class FakeWebGLRenderer {
    domElement = document.createElement("canvas");
    renderLists = { dispose: vi.fn() };
    dispose = vi.fn();
    forceContextLoss = vi.fn();

    constructor() {
      threeMocks.renderers.push(this);
    }

    setPixelRatio() {}
    setSize() {}
    setClearColor() {}
    render() {}
  }

  class FakeScene {
    add() {}
  }

  class FakeLight {
    position = { set() {} };
  }

  class FakeCamera {
    position = { set() {} };
    aspect = 1;
    near = 0;
    far = 0;

    updateProjectionMatrix() {}
  }

  class FakeRaycaster {}

  return {
    WebGLRenderer: FakeWebGLRenderer,
    Scene: FakeScene,
    HemisphereLight: FakeLight,
    DirectionalLight: FakeLight,
    PerspectiveCamera: FakeCamera,
    Raycaster: FakeRaycaster,
  };
});

vi.mock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class {
    enableDamping = false;
    dampingFactor = 0;
    autoRotate = false;
    autoRotateSpeed = 0;
    target = { set() {} };

    update() {}
    dispose() {}
  },
}));

vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => ({
  GLTFLoader: class {
    parse() {}
  },
}));

vi.mock("three/examples/jsm/loaders/STLLoader.js", () => ({
  STLLoader: class {
    parse() {}
  },
}));

import ThreeDViewport from "../src/components/ThreeDViewport.vue";

function modelSnapshot(format: "stl" | "gltf" = "stl"): ThreeDRuntimeSnapshot {
  return {
    schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
    model_asset: {
      asset_id: "model" as const,
      url: "/three-d-runtime/v1/cases/case_001/assets/model",
      format,
      file_name: `mandible.${format}`,
      sha256: "a".repeat(64),
      size_bytes: 128,
      ...(format === "gltf"
        ? {
            rendering_status: "unsupported_format" as const,
            rendering_failure_reason: "gltf_not_supported_by_isolated_renderer",
          }
        : {}),
    },
    safety: { navigation_ready: false, navigation_level: "L0", registration_status: "unregistered" },
  };
}

describe("ThreeDViewport", () => {
  afterEach(() => {
    threeMocks.renderers.length = 0;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps an empty scene in a neutral evidence state without allocating a WebGL canvas", async () => {
    const wrapper = mount(ThreeDViewport, { props: { snapshot: null } });
    await flushPromises();

    expect(wrapper.text()).toContain("没有可渲染的三维模型");
    expect(wrapper.find("canvas").exists()).toBe(false);
    expect(wrapper.attributes("data-state")).toBe("reference");
  });

  it("keeps a GLTF asset in an explicit safe degradation state before WebGL initialization", async () => {
    const wrapper = mount(ThreeDViewport, { props: { snapshot: modelSnapshot("gltf") } });
    await flushPromises();

    expect(wrapper.attributes("data-state")).toBe("failed");
    expect(wrapper.text()).toContain("当前 GLTF 模型可能依赖外部二进制或纹理资源");
    expect(wrapper.text()).not.toContain("gltf_not_supported_by_isolated_renderer");
    expect(wrapper.find("canvas").exists()).toBe(false);
    expect(threeMocks.renderers).toHaveLength(0);
  });

  it("honors the backend rendering status before WebGL initialization", async () => {
    const snapshot = modelSnapshot();
    snapshot.model_asset!.rendering_status = "unsupported_format";
    snapshot.model_asset!.rendering_failure_reason = "future_renderer_failure_code";
    const wrapper = mount(ThreeDViewport, { props: { snapshot } });
    await flushPromises();

    expect(wrapper.attributes("data-state")).toBe("failed");
    expect(wrapper.text()).toContain("模型已由后端标记为当前独立运行时不可渲染");
    expect(wrapper.text()).not.toContain("future_renderer_failure_code");
    expect(threeMocks.renderers).toHaveLength(0);
  });

  it("releases the detached renderer and creates a new one after model to empty to model", async () => {
    const pendingDownload = new Promise<Response>(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingDownload));
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);

    const wrapper = mount(ThreeDViewport, { props: { snapshot: modelSnapshot() } });
    await flushPromises();
    expect(threeMocks.renderers).toHaveLength(1);
    const firstRenderer = threeMocks.renderers[0];

    await wrapper.setProps({ snapshot: null });
    await flushPromises();
    expect(firstRenderer.forceContextLoss).toHaveBeenCalledTimes(1);
    expect(wrapper.attributes("data-state")).toBe("reference");

    await wrapper.setProps({ snapshot: modelSnapshot() });
    await flushPromises();
    expect(threeMocks.renderers).toHaveLength(2);
    expect(wrapper.find("canvas").exists()).toBe(true);

    wrapper.unmount();
  });

  it("releases a lost WebGL context so a later scene reload can allocate a renderer", async () => {
    const pendingDownload = new Promise<Response>(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingDownload));
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);

    const wrapper = mount(ThreeDViewport, { props: { snapshot: modelSnapshot() } });
    await flushPromises();
    const firstRenderer = threeMocks.renderers[0];
    wrapper.find("canvas").element.dispatchEvent(new Event("webglcontextlost", { cancelable: true }));
    await flushPromises();

    expect(wrapper.attributes("data-state")).toBe("failed");
    expect(firstRenderer.dispose).toHaveBeenCalledTimes(1);
    expect(firstRenderer.forceContextLoss).not.toHaveBeenCalled();

    await wrapper.setProps({ snapshot: { ...modelSnapshot(), case_version: 2 } });
    await flushPromises();
    expect(threeMocks.renderers).toHaveLength(2);

    wrapper.unmount();
  });
});
