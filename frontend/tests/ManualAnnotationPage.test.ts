import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ManualAnnotationPage from "../src/pages/ManualAnnotationPage.vue";
import { apiClient } from "../src/services/apiClient";
import { useCaseStore } from "../src/stores/caseStore";
import type { ManualAnnotation } from "../src/types/annotation";
import type { CaseRecord } from "../src/types/case";

const geometry = {
  coordinate_space: "image_pixels" as const,
  operations: [
    {
      tool: "polygon" as const,
      mode: "add" as const,
      points: [{ x: 10, y: 10 }, { x: 50, y: 10 }, { x: 30, y: 50 }],
    },
  ],
};

describe("ManualAnnotationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a real draft from a case source and submits it with verified physician identity", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    store.currentCase = caseRecord();
    const saved = annotation("draft");
    const savedVersion = { ...saved, current_version: 2, updated_at: "2026-07-15T12:04:00Z" };
    const submitted = { ...savedVersion, status: "submitted" as const, submitted_at: "2026-07-15T12:05:00Z" };

    vi.spyOn(apiClient, "listAnnotationSources").mockResolvedValue({
      case_id: "case_annotation_001",
      sources: [
        {
          source_id: "source_input_001",
          source_type: "case_jpeg",
          input_id: "input_001",
          preview_path: "C:\\cases\\input_001.jpg",
          original_width: 640,
          original_height: 480,
          title: "ICG 图像",
        },
      ],
    });
    vi.spyOn(apiClient, "listAnnotations").mockResolvedValue({ case_id: "case_annotation_001", items: [] });
    vi.spyOn(apiClient, "createAnnotation").mockResolvedValue(saved);
    vi.spyOn(apiClient, "saveAnnotationVersion").mockResolvedValue(savedVersion);
    vi.spyOn(apiClient, "listAnnotationVersions").mockResolvedValue({ annotation_id: saved.annotation_id, items: [] });
    vi.spyOn(apiClient, "getReviewIdentity").mockResolvedValue({
      actor_id: "doctor-001",
      role: "physician",
      institution: "测试医院",
      auth_source: "bearer_token",
      authenticated: true,
    });
    vi.spyOn(apiClient, "submitAnnotation").mockResolvedValue(submitted);

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/annotations", component: ManualAnnotationPage },
        { path: "/cases", component: { template: "<div />" } },
      ],
    });
    await router.push("/annotations?caseId=case_annotation_001");
    await router.isReady();

    const wrapper = mount(ManualAnnotationPage, {
      global: {
        plugins: [pinia, router],
        stubs: {
          AppIcon: true,
          ReviewIdentityPanel: true,
          MedicalDisclaimer: true,
          ManualAnnotationCanvas: {
            props: ["sourceUrl", "sourceTitle", "geometry", "disabled", "disabledReason"],
            emits: ["geometry-change", "source-ready"],
            template: '<button class="canvas-edit" type="button" @click="$emit(\'geometry-change\', fixtureGeometry)">描画病灶</button>',
            setup() {
              return { fixtureGeometry: geometry };
            },
          },
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("ICG 图像");
    expect(wrapper.text()).toContain("无法判断区");
    await wrapper.get(".canvas-edit").trigger("click");
    const saveButton = wrapper.findAll("button").find((button) => button.text().includes("保存草稿"));
    expect(saveButton).toBeDefined();
    expect((saveButton!.element as HTMLButtonElement).disabled).toBe(false);
    await saveButton!.trigger("click");
    await flushPromises();

    expect(apiClient.createAnnotation).toHaveBeenCalledWith(
      "case_annotation_001",
      expect.objectContaining({
        label: "lesion",
        source: expect.objectContaining({ source_type: "case_jpeg", input_id: "input_001" }),
        geometry,
      }),
    );
    expect(wrapper.text()).toContain("annotation_001");

    const submitButton = wrapper.findAll("button").find((button) => button.text().includes("提交复核"));
    expect(submitButton).toBeDefined();
    await wrapper.get(".canvas-edit").trigger("click");
    expect((submitButton!.element as HTMLButtonElement).disabled).toBe(true);
    expect(submitButton!.attributes("title")).toBe("请先保存或放弃当前修改");

    const versionButton = wrapper.findAll("button").find((button) => button.text().includes("保存新版本"));
    expect(versionButton).toBeDefined();
    await versionButton!.trigger("click");
    await flushPromises();

    expect(apiClient.saveAnnotationVersion).toHaveBeenCalledWith(
      "case_annotation_001",
      "annotation_001",
      expect.objectContaining({ expected_version: 1, geometry }),
    );
    expect((submitButton!.element as HTMLButtonElement).disabled).toBe(false);
    await submitButton!.trigger("click");
    await flushPromises();

    expect(apiClient.submitAnnotation).toHaveBeenCalledWith("case_annotation_001", "annotation_001", 2, "");
    expect(wrapper.text()).toContain("待医生复核");
  });

  it("generates the current case training manifest through the backend", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    store.currentCase = caseRecord();
    vi.spyOn(apiClient, "listAnnotationSources").mockResolvedValue({ case_id: "case_annotation_001", sources: [] });
    vi.spyOn(apiClient, "listAnnotations").mockResolvedValue({ case_id: "case_annotation_001", items: [] });
    vi.spyOn(apiClient, "createAnnotationTrainingManifest").mockResolvedValue({
      manifest_path: "artifacts/annotations/training_manifest.json",
      sample_count: 2,
      eligible_count: 1,
      excluded_count: 1,
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/annotations", component: ManualAnnotationPage },
        { path: "/cases", component: { template: "<div />" } },
      ],
    });
    await router.push("/annotations");
    await router.isReady();
    const wrapper = mount(ManualAnnotationPage, {
      global: {
        plugins: [pinia, router],
        stubs: {
          AppIcon: true,
          ReviewIdentityPanel: true,
          MedicalDisclaimer: true,
          ManualAnnotationCanvas: true,
        },
      },
    });
    await flushPromises();

    const manifestButton = wrapper.findAll("button").find((button) => button.text().includes("生成训练清单"));
    expect(manifestButton).toBeDefined();
    await manifestButton!.trigger("click");
    await flushPromises();

    expect(apiClient.createAnnotationTrainingManifest).toHaveBeenCalledWith(["case_annotation_001"], false);
    expect(wrapper.text()).toContain("artifacts/annotations/training_manifest.json");
    expect(wrapper.text()).toContain("1 条准入，1 条隔离");
  });

  it("keeps an engineering-authored annotation isolated with truthful review copy", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useCaseStore();
    store.currentCase = caseRecord();
    const submitted = {
      ...annotation("submitted"),
      latest_author: {
        actor_id: "engineering-local-session",
        role: "engineering_reviewer",
        institution: "Osteo Vision Engineering",
        auth_source: "local_unverified_session",
      },
      submitted_by: physicianActor(),
    };
    const accepted = { ...submitted, status: "accepted" as const, reviewed_by: physicianActor() };

    vi.spyOn(apiClient, "listAnnotationSources").mockResolvedValue({
      case_id: "case_annotation_001",
      sources: [
        {
          source_id: "source_input_001",
          source_type: "case_jpeg",
          input_id: "input_001",
          preview_path: "C:\\cases\\input_001.jpg",
          original_width: 640,
          original_height: 480,
          title: "ICG 图像",
        },
      ],
    });
    vi.spyOn(apiClient, "listAnnotations").mockResolvedValue({
      case_id: "case_annotation_001",
      items: [submitted],
    });
    vi.spyOn(apiClient, "getAnnotation").mockResolvedValue(submitted);
    vi.spyOn(apiClient, "listAnnotationVersions").mockResolvedValue({ annotation_id: submitted.annotation_id, items: [] });
    vi.spyOn(apiClient, "getReviewIdentity").mockResolvedValue({ ...physicianActor(), authenticated: true });
    vi.spyOn(apiClient, "reviewAnnotation").mockResolvedValue(accepted);

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/annotations", component: ManualAnnotationPage },
        { path: "/cases", component: { template: "<div />" } },
      ],
    });
    await router.push("/annotations");
    await router.isReady();
    const wrapper = mount(ManualAnnotationPage, {
      global: {
        plugins: [pinia, router],
        stubs: {
          AppIcon: true,
          ReviewIdentityPanel: true,
          MedicalDisclaimer: true,
          ManualAnnotationCanvas: true,
        },
      },
    });
    await flushPromises();

    const acceptButton = wrapper.findAll("button").find((button) => button.text().includes("接受标注"));
    expect(acceptButton).toBeDefined();
    expect(acceptButton!.attributes("title")).toBe("接受医生复核结论并评估训练准入条件");
    await acceptButton!.trigger("click");
    await flushPromises();

    expect(apiClient.reviewAnnotation).toHaveBeenCalledWith(
      "case_annotation_001",
      "annotation_001",
      1,
      "accepted",
      "",
    );
    expect(wrapper.text()).toContain("训练保持隔离");
    expect(wrapper.text()).toContain("训练准入条件尚未全部满足");
  });
});

function caseRecord(): CaseRecord {
  return {
    case_id: "case_annotation_001",
    title: "人工标注病例",
    status: "analyzed",
    version: 1,
    disclaimer_version: "platform-safety-v1",
    review_summary: {},
    inputs: [],
    analysis_runs: [],
    rois: [],
    quality_flags: [],
    artifacts: [],
    warnings: [],
  };
}

function annotation(status: ManualAnnotation["status"]): ManualAnnotation {
  const actor = physicianActor();
  return {
    annotation_id: "annotation_001",
    case_id: "case_annotation_001",
    label: "lesion",
    status,
    current_version: 1,
    source: { source_type: "case_jpeg", input_id: "input_001" },
    source_snapshot_path: "C:\\cases\\input_001.jpg",
    original_width: 640,
    original_height: 480,
    geometry,
    mask_path: "C:\\cases\\annotation_001.png",
    mask_checksum: "abc123",
    notes: "",
    created_by: actor,
    latest_author: actor,
    submitted_by: null,
    reviewed_by: null,
    training_eligible: false,
    sample_weight: 0,
    created_at: "2026-07-15T12:00:00Z",
    updated_at: "2026-07-15T12:00:00Z",
  };
}

function physicianActor() {
  return {
    actor_id: "doctor-001",
    role: "physician" as const,
    institution: "测试医院",
    auth_source: "verified_identity_token",
    authenticated: true,
  };
}
