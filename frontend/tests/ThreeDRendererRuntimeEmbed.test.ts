import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import ThreeDRendererRuntimeEmbed from "../src/components/ThreeDRendererRuntimeEmbed.vue";

describe("ThreeDRendererRuntimeEmbed", () => {
  afterEach(() => {
    vi.useRealTimers();
    delete document.documentElement.dataset.theme;
  });

  it("opens the standalone runtime with a case identifier and keeps a visible connection state", () => {
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001" } });

    const frame = wrapper.get("iframe");
    expect(frame.attributes("src")).toContain("http://127.0.0.1:5175");
    expect(frame.attributes("src")).toContain("caseId=case_001");
    expect(wrapper.text()).toContain("正在建立三维渲染会话");
    const status = wrapper.get('[data-testid="three-d-runtime-status"]');
    expect(status.isVisible()).toBe(true);
    expect(getComputedStyle(status.element).opacity).not.toBe("0");
    expect(wrapper.get('a[target="_blank"]').attributes("href")).toContain("caseId=case_001");
  });

  it("degrades visibly when the separate runtime does not confirm within the allowed window", async () => {
    vi.useFakeTimers();
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001" } });

    await vi.advanceTimersByTimeAsync(10000);

    expect(wrapper.attributes("data-state")).toBe("degraded");
    expect(wrapper.text()).toContain("当前页面仍保留病例安全状态");
  });

  it("recreates the isolated scene when the persisted case version changes", async () => {
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001", sceneVersion: 1 } });

    expect(wrapper.get("iframe").attributes("src")).toContain("runtimeInstance=0");
    await wrapper.setProps({ sceneVersion: 2 });

    expect(wrapper.get("iframe").attributes("src")).toContain("runtimeInstance=1");
  });

  it("accepts an allowed runtime handshake, synchronizes the theme, and relays candidate selection", async () => {
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001" } });
    const runtimeWindow = { postMessage: vi.fn() };
    Object.defineProperty(wrapper.get("iframe").element, "contentWindow", { configurable: true, value: runtimeWindow });

    await wrapper.get("iframe").trigger("load");
    expect(runtimeWindow.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ protocol: "osteo-vision-three-d-runtime-bridge-v1", type: "load_case", case_id: "case_001" }),
      "http://127.0.0.1:5175",
    );

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://127.0.0.1:5175",
        source: runtimeWindow as unknown as MessageEventSource,
        data: {
          protocol: "osteo-vision-three-d-runtime-bridge-v1",
          type: "scene_loaded",
          request_id: "case_001-0",
          message: "场景已载入",
        },
      }),
    );
    await nextTick();
    expect(wrapper.attributes("data-state")).toBe("ready");
    expect(wrapper.find('[data-testid="three-d-runtime-status"]').exists()).toBe(false);

    document.documentElement.dataset.theme = "dark";
    await nextTick();
    expect(runtimeWindow.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ protocol: "osteo-vision-three-d-runtime-bridge-v1", type: "set_theme", theme: "dark" }),
      "http://127.0.0.1:5175",
    );

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://127.0.0.1:5175",
        source: runtimeWindow as unknown as MessageEventSource,
        data: {
          protocol: "osteo-vision-three-d-runtime-bridge-v1",
          type: "candidate_selected",
          request_id: "case_001-0",
          candidate: { candidate_id: "candidate_001", frame_key: "frame_10", frame_index: 10, timestamp_sec: 1.25 },
        },
      }),
    );
    await nextTick();
    expect(wrapper.emitted("selectCandidateFrame")?.[0]).toEqual([
      { candidateId: "candidate_001", frameKey: "frame_10", frameIndex: 10, timestampSec: 1.25 },
    ]);
  });

  it("ignores bridge messages from an untrusted origin", async () => {
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001" } });

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://untrusted.example",
        data: { protocol: "osteo-vision-three-d-runtime-bridge-v1", type: "scene_loaded" },
      }),
    );
    await nextTick();

    expect(wrapper.attributes("data-state")).toBe("connecting");
  });

  it("ignores an earlier iframe response after the scene request changes", async () => {
    const wrapper = mount(ThreeDRendererRuntimeEmbed, { props: { caseId: "case_001", sceneVersion: 1 } });
    const firstWindow = { postMessage: vi.fn() };
    Object.defineProperty(wrapper.get("iframe").element, "contentWindow", { configurable: true, value: firstWindow });
    await wrapper.get("iframe").trigger("load");

    await wrapper.setProps({ sceneVersion: 2 });
    const secondWindow = { postMessage: vi.fn() };
    Object.defineProperty(wrapper.get("iframe").element, "contentWindow", { configurable: true, value: secondWindow });
    await wrapper.get("iframe").trigger("load");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://127.0.0.1:5175",
        source: firstWindow as unknown as MessageEventSource,
        data: {
          protocol: "osteo-vision-three-d-runtime-bridge-v1",
          type: "scene_loaded",
          request_id: "case_001-0",
          message: "旧场景已载入",
        },
      }),
    );
    await nextTick();
    expect(wrapper.attributes("data-state")).toBe("connecting");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://127.0.0.1:5175",
        source: secondWindow as unknown as MessageEventSource,
        data: {
          protocol: "osteo-vision-three-d-runtime-bridge-v1",
          type: "scene_loaded",
          request_id: "case_001-1",
          message: "新场景已载入",
        },
      }),
    );
    await nextTick();
    expect(wrapper.attributes("data-state")).toBe("ready");
  });
});
