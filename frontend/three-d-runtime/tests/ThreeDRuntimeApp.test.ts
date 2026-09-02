import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runtimeClientMocks = vi.hoisted(() => ({
  fetchCaseSnapshot: vi.fn(),
  fetchReferenceSnapshot: vi.fn(),
}));

vi.mock("../src/services/threeDRuntimeClient", () => ({
  fetchCaseSnapshot: runtimeClientMocks.fetchCaseSnapshot,
  fetchReferenceSnapshot: runtimeClientMocks.fetchReferenceSnapshot,
  resolveAssetUrl: (url: string) => url,
}));

import ThreeDRuntimeApp from "../src/ThreeDRuntimeApp.vue";

function deferred<T>() {
  let resolve: (value: T) => void;
  let reject: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve: resolve!, reject: reject! };
}

function caseSnapshot(caseId: string) {
  return {
    schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
    case_id: caseId,
    case_version: 4,
    model_asset: {
      asset_id: "model" as const,
      url: `/three-d-runtime/v1/cases/${caseId}/assets/model`,
      format: "stl" as const,
      file_name: "mandible.stl",
      sha256: "a".repeat(64),
      size_bytes: 128,
    },
    candidate_regions: [],
    safety: { navigation_level: "L0", navigation_ready: false, doctor_review_status: "review_required" },
  };
}

function bridgeMessage(source: WindowProxy, caseId: string, requestId = `request-${caseId}`) {
  return new MessageEvent("message", {
    origin: "http://localhost:5174",
    source,
    data: {
      protocol: "osteo-vision-three-d-runtime-bridge-v1",
      type: "load_case",
      request_id: requestId,
      case_id: caseId,
    },
  });
}

describe("ThreeDRuntimeApp", () => {
  beforeEach(() => {
    runtimeClientMocks.fetchCaseSnapshot.mockReset();
    runtimeClientMocks.fetchReferenceSnapshot.mockReset();
    window.localStorage.clear();
    document.documentElement.dataset.theme = "light";
    document.documentElement.style.colorScheme = "light";
    window.history.replaceState({}, "", "/?caseId=case_001");
    runtimeClientMocks.fetchCaseSnapshot.mockResolvedValue({
      schema_version: "osteo-vision-three-d-runtime-snapshot-v2",
      case_id: "case_001",
      case_version: 4,
      model_asset: {
        asset_id: "model",
        url: "/three-d-runtime/v1/cases/case_001/assets/model",
        format: "stl",
        file_name: "mandible.stl",
        sha256: "a".repeat(64),
        size_bytes: 128,
      },
      candidate_regions: [
        {
          candidate_id: "candidate_001",
          risk_type: "boundary_risk",
          confidence: 0.82,
          frame_index: 8,
          timestamp_sec: 0.8,
        },
      ],
      safety: { navigation_level: "L0", navigation_ready: false, doctor_review_status: "review_required" },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads only the controlled scene snapshot and exposes a selectable candidate", async () => {
    const wrapper = mount(ThreeDRuntimeApp, {
      global: {
        stubs: {
          ThreeDViewport: {
            props: ["snapshot", "autoRotate"],
            emits: ["candidateSelected", "state"],
            template: '<button class="viewport-stub" @click="$emit(\'candidateSelected\', { candidate_id: \'candidate_001\', frame_key: \'frame_8\', frame_index: 8, timestamp_sec: 0.8 })">viewport</button>',
          },
        },
      },
    });
    await flushPromises();

    expect(runtimeClientMocks.fetchCaseSnapshot).toHaveBeenCalledWith("case_001");
    expect(wrapper.get("h1").text()).toBe("独立三维渲染运行时");
    expect(wrapper.text()).toContain("L0 参考状态");
    expect(wrapper.text()).toContain("边界风险");
    expect(wrapper.text()).not.toContain("clinical_context");

    await wrapper.get(".viewport-stub").trigger("click");
    expect(wrapper.get(".runtime-inspector__candidates button").classes()).toContain("is-selected");
    wrapper.unmount();
  });

  it("replies to the verified localhost parent after receiving a bridge request", async () => {
    window.history.replaceState({}, "", "/");
    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    runtimeClientMocks.fetchCaseSnapshot.mockResolvedValueOnce(caseSnapshot("case_localhost"));

    const wrapper = mount(ThreeDRuntimeApp, {
      global: {
        stubs: {
          ThreeDViewport: {
            props: ["snapshot", "autoRotate"],
            template: '<div class="viewport-stub">{{ snapshot?.case_id || "empty" }}</div>',
          },
        },
      },
    });
    expect(parentWindow.postMessage).not.toHaveBeenCalled();
    window.dispatchEvent(bridgeMessage(parentWindow, "case_localhost"));
    await flushPromises();

    expect(parentWindow.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "scene_loaded" }),
      "http://localhost:5174",
    );
    expect(wrapper.get(".runtime-shell__actions a").attributes("href")).toBe(
      "http://localhost:5174/navigation?caseId=case_localhost",
    );
    expect(wrapper.get(".runtime-shell__actions a").attributes("target")).toBe("_top");

    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });

  it("echoes the current bridge request identifier with scene results", async () => {
    window.history.replaceState({}, "", "/");
    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    runtimeClientMocks.fetchCaseSnapshot.mockResolvedValueOnce(caseSnapshot("case_request"));

    const wrapper = mount(ThreeDRuntimeApp, {
      global: { stubs: { ThreeDViewport: { template: '<div class="viewport-stub" />' } } },
    });
    window.dispatchEvent(bridgeMessage(parentWindow, "case_request", "request-latest"));
    await flushPromises();

    expect(parentWindow.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "scene_loaded", request_id: "request-latest" }),
      "http://localhost:5174",
    );

    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });

  it("does not restart a pending snapshot when the parent retries the same scene request", async () => {
    window.history.replaceState({}, "", "/");
    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    const pending = deferred<ReturnType<typeof caseSnapshot>>();
    runtimeClientMocks.fetchCaseSnapshot.mockReturnValue(pending.promise);

    const wrapper = mount(ThreeDRuntimeApp, {
      global: { stubs: { ThreeDViewport: { template: '<div class="viewport-stub" />' } } },
    });
    const message = bridgeMessage(parentWindow, "case_retry", "request-retry");
    window.dispatchEvent(message);
    window.dispatchEvent(message);
    await flushPromises();

    expect(runtimeClientMocks.fetchCaseSnapshot).toHaveBeenCalledTimes(1);

    pending.resolve(caseSnapshot("case_retry"));
    await flushPromises();
    expect(parentWindow.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "scene_loaded", request_id: "request-retry" }),
      "http://localhost:5174",
    );

    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });

  it("waits for the verified bridge request when an iframe URL already contains a case ID", async () => {
    window.history.replaceState({}, "", "/?caseId=case_embedded&embedded=1");
    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    runtimeClientMocks.fetchCaseSnapshot.mockResolvedValueOnce(caseSnapshot("case_embedded"));

    const wrapper = mount(ThreeDRuntimeApp, {
      global: {
        stubs: {
          ThreeDViewport: {
            props: ["snapshot", "autoRotate"],
            template: '<div class="viewport-stub">{{ snapshot?.case_id || "empty" }}</div>',
          },
        },
      },
    });
    await flushPromises();
    expect(wrapper.get(".runtime-shell").classes()).toContain("is-embedded");
    expect(wrapper.find(".runtime-shell__header").exists()).toBe(true);
    expect(runtimeClientMocks.fetchCaseSnapshot).toHaveBeenCalledTimes(1);
    expect(runtimeClientMocks.fetchCaseSnapshot).toHaveBeenCalledWith("case_embedded");

    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });

  it("persists a user-selected runtime theme and accepts a parent theme", async () => {
    window.history.replaceState({}, "");
    const wrapper = mount(ThreeDRuntimeApp, {
      global: { stubs: { ThreeDViewport: { template: '<div class="viewport-stub" />' } } },
    });

    const toggle = wrapper.get(".runtime-theme-toggle input");
    await toggle.setValue(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem("osteo-vision-theme")).toBe("dark");

    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://localhost:5174",
        source: parentWindow,
        data: { protocol: "osteo-vision-three-d-runtime-bridge-v1", type: "set_theme", theme: "light" },
      }),
    );
    await flushPromises();

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("osteo-vision-theme")).toBe("light");
    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });

  it("returns a public reference window to the showcase", async () => {
    window.history.replaceState({}, "", "/?referenceId=d024");
    runtimeClientMocks.fetchReferenceSnapshot.mockResolvedValueOnce({
      ...caseSnapshot("reference_d024"),
      case_id: "reference_d024",
    });
    const wrapper = mount(ThreeDRuntimeApp, {
      global: { stubs: { ThreeDViewport: { template: '<div class="viewport-stub" />' } } },
    });
    await flushPromises();

    expect(wrapper.get(".runtime-shell__actions a").attributes("href")).toBe("http://127.0.0.1:5174/showcase");
    expect(wrapper.get(".runtime-shell__actions a").attributes("target")).toBe("_top");
    wrapper.unmount();
  });

  it("keeps the newest bridge snapshot when an earlier request resolves later", async () => {
    window.history.replaceState({}, "", "/");
    const originalParent = window.parent;
    const parentWindow = { postMessage: vi.fn() } as unknown as WindowProxy;
    Object.defineProperty(window, "parent", { configurable: true, value: parentWindow });
    const first = deferred<ReturnType<typeof caseSnapshot>>();
    const second = deferred<ReturnType<typeof caseSnapshot>>();
    runtimeClientMocks.fetchCaseSnapshot.mockImplementation((caseId: string) => {
      if (caseId === "case_first") return first.promise;
      if (caseId === "case_latest") return second.promise;
      return Promise.resolve(caseSnapshot(caseId));
    });

    const wrapper = mount(ThreeDRuntimeApp, {
      global: {
        stubs: {
          ThreeDViewport: {
            props: ["snapshot", "autoRotate"],
            template: '<div class="viewport-stub">{{ snapshot?.case_id || "empty" }}</div>',
          },
        },
      },
    });
    window.dispatchEvent(bridgeMessage(parentWindow, "case_first"));
    window.dispatchEvent(bridgeMessage(parentWindow, "case_latest"));

    second.resolve(caseSnapshot("case_latest"));
    await flushPromises();
    expect(wrapper.get(".viewport-stub").text()).toBe("case_latest");

    first.resolve(caseSnapshot("case_first"));
    await flushPromises();
    expect(wrapper.get(".viewport-stub").text()).toBe("case_latest");

    wrapper.unmount();
    Object.defineProperty(window, "parent", { configurable: true, value: originalParent });
  });
});
