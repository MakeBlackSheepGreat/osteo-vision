import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

function readyPayload(profile: "development" | "competition_strict") {
  const strict = profile === "competition_strict";
  return {
    status: "ok",
    inference_config: `configs/inference/${profile}.yml`,
    accelerator: {
      requested_policy: "auto",
      selected_device: "cuda",
      gpu_acceleration_enabled: true,
      fallback_active: false,
      fallback_reason: null,
      torch_version: "2.11.0",
      cuda_runtime_version: "12.8",
      gpu_count: 1,
      gpu_name: "NVIDIA Test GPU",
    },
    runtime_readiness: {
      passed: true,
      runtime_profile: profile,
      strict_startup: strict,
      config_path: `configs/inference/${profile}.yml`,
      config_sha256: "1234567890abcdef",
      error_count: 0,
      warning_count: strict ? 0 : 1,
      errors: [],
      warnings: strict ? [] : [{ code: "development_fixture_model_enabled" }],
      required_model_ids: strict ? ["segmenter"] : [],
      verified_models: strict
        ? [
            {
              model_id: "segmenter",
              family: "convnext2d_keyframe_segmenter",
              checkpoint_path: "model.pt",
              checkpoint_sha256: "abcdef1234567890",
              sidecar_path: "model.json",
              runtime_allowed: true,
            },
          ]
        : [],
      runtime_tools: [],
    },
  };
}

async function mountBanner(profile: "development" | "competition_strict", expectStrict: boolean) {
  vi.stubEnv("VITE_OSTEO_EXPECT_STRICT_RUNTIME", String(expectStrict));
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => readyPayload(profile),
    }),
  );
  vi.resetModules();
  const { default: RuntimeStatusBanner } = await import("../src/components/RuntimeStatusBanner.vue");
  const wrapper = mount(RuntimeStatusBanner);
  await flushPromises();
  return wrapper;
}

describe("RuntimeStatusBanner", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("shows the development fixture warning with runtime evidence", async () => {
    const wrapper = await mountBanner("development", false);

    expect(wrapper.text()).toContain("当前为研发运行档位");
    expect(wrapper.text()).toContain("development");
    expect(wrapper.text()).toContain("未锁定");
    expect(wrapper.emitted("blockingChange")?.at(-1)).toEqual([false]);
  });

  it("shows model and configuration evidence for a verified strict runtime", async () => {
    const wrapper = await mountBanner("competition_strict", true);

    expect(wrapper.text()).toContain("比赛严格运行已核验");
    expect(wrapper.text()).toContain("segmenter");
    expect(wrapper.text()).toContain("abcdef123456");
    expect(wrapper.text()).toContain("GPU：NVIDIA Test GPU");
    expect(wrapper.find(".runtime-status--success").exists()).toBe(true);
    expect(wrapper.emitted("blockingChange")?.at(-1)).toEqual([false]);
  });

  it("blocks a competition frontend connected to a development backend", async () => {
    const wrapper = await mountBanner("development", true);

    expect(wrapper.text()).toContain("比赛运行已阻断");
    expect(wrapper.attributes("role")).toBe("alert");
    expect(wrapper.emitted("blockingChange")?.at(-1)).toEqual([true]);
  });
});
