import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";

import DatasetReviewPage from "../src/pages/DatasetReviewPage.vue";
import { apiClient } from "../src/services/apiClient";
import type { DatasetReviewRecord } from "../src/types/datasetReview";

const records: DatasetReviewRecord[] = [
  {
    record_id: "d047-panel-001",
    dataset_id: "d047_pmc_jaw_fluorescence_figures",
    source_record_id: "PMC047_figure_2",
    source_group_id: "PMC047",
    image_path: "C:\\very\\long\\path\\d047\\panel.png",
    image_href: "/dataset-review/d047-panel-001/image",
    review_state: "review_required",
    license: "CC BY",
    source_url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC047/",
  },
  {
    record_id: "d048-panel-001",
    dataset_id: "d048_open_clinical_bone_fluorescence",
    source_record_id: "PMC048_figure_1",
    source_group_id: "PMC048",
    image_path: "C:\\data\\d048\\panel.png",
    image_href: "/dataset-review/d048-panel-001/image",
    review_state: "modified",
    reviewer_role: "project_reviewer",
    license: "CC BY",
    training_eligible: true,
  },
];

const EditorStub = defineComponent({
  props: {
    loading: { type: Boolean, default: false },
    disabledReason: { type: String, default: "" },
  },
  emits: ["save"],
  template: `<button class="stub-save" :disabled="loading" :title="disabledReason" @click="$emit('save', {
    maskPngBase64: 'data:image/png;base64,dGVzdA==',
    reviewState: 'modified',
    reviewerNotes: 'project review',
    reviewerRole: 'project_reviewer'
  })">保存测试</button>`,
});

const CropStub = defineComponent({
  props: {
    loading: { type: Boolean, default: false },
  },
  emits: ["save"],
  template: `<button class="stub-crop" :disabled="loading" @click="$emit('save', {
    x: 4, y: 3, width: 20, height: 16,
    panel_role: 'paired_fluorescence',
    pair_id: 'PMC047_pair_1',
    crop_notes: 'fluorescence panel',
    suggestion_id: 'suggestion_1',
    crop_review_action: 'accepted'
  })">保存裁剪测试</button>`,
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("DatasetReviewPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads D047/D048 records and persists reviewer authority", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({
      items: records,
      medical_boundary: "公开数据工程复核边界",
    });
    const saveSpy = vi.spyOn(apiClient, "saveDatasetReviewMask").mockResolvedValue({
      ...records[0],
      review_state: "modified",
      reviewer_role: "project_reviewer",
      review_authority: "engineering_supervision",
    });
    const wrapper = mount(DatasetReviewPage, {
      global: {
        stubs: {
          AppIcon: true,
          StaticMaskEditor: EditorStub,
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("PMC047_figure_2");
    expect(wrapper.text()).toContain("PMC048_figure_1");
    await wrapper.get("button[aria-expanded='false']").trigger("click");
    expect(wrapper.text()).toContain("C:\\very\\long\\path\\d047\\panel.png");
    await wrapper.find("button.stub-save").trigger("click");
    await flushPromises();

    expect(saveSpy).toHaveBeenCalledWith("d047-panel-001", {
      mask_png_base64: "data:image/png;base64,dGVzdA==",
      review_state: "modified",
      reviewer_notes: "project review",
      reviewer_role: "project_reviewer",
    });
    expect(wrapper.text()).toContain("复核身份：项目复核人员");
  });

  it("shows a clear queue loading error", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockRejectedValue(new Error("backend unavailable"));
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: true } },
    });
    await flushPromises();
    expect(wrapper.find('[role="alert"]').text()).toContain("backend unavailable");
  });

  it("generates a thresholded seed and keeps it behind human review", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: records });
    const seedSpy = vi.spyOn(apiClient, "generateDatasetReviewSeed").mockResolvedValue({
      ...records[0],
      mask_path: "C:\\data\\seed.png",
      mask_href: "/dataset-review/d047-panel-001/mask",
      review_state: "review_required",
      reviewer_role: "automated_seed",
      review_authority: "automated_heuristic",
      mask_source: "heuristic_fluorescence_hotspot_seed",
      record_kind: "automated_seed",
      threshold: 0.6,
      training_eligible: false,
    });
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    const seedButton = wrapper.findAll("button").find((button) => button.text().includes("生成候选掩膜"));
    await seedButton?.trigger("click");
    await flushPromises();

    expect(seedSpy).toHaveBeenCalledWith("d047-panel-001", 0.6);
    expect(wrapper.text()).toContain("自动候选 / 待人工复核 / 不可直接训练");
    expect(wrapper.text()).toContain("当前仍需人工复核且不可直接训练");
  });

  it("keeps uncropped source figures in the queue and persists crop metadata", async () => {
    const uncropped: DatasetReviewRecord = {
      ...records[0],
      crop_required: true,
      panel_role: "unclassified",
      suggested_panel_role: "paired_fluorescence",
      suggested_pair_id: "PMC047_pair_1",
      suggested_pair_alignment: "approximate_view",
      panel_label: "B",
    };
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: [uncropped] });
    const cropSpy = vi.spyOn(apiClient, "saveDatasetReviewCrop").mockResolvedValue({
      ...uncropped,
      crop_required: false,
      crop_bbox: { x: 4, y: 3, width: 20, height: 16 },
      panel_role: "paired_fluorescence",
      pair_id: "PMC047_pair_1",
    });
    const wrapper = mount(DatasetReviewPage, {
      global: {
        stubs: {
          AppIcon: true,
          StaticCropEditor: CropStub,
          StaticMaskEditor: EditorStub,
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("待裁剪");
    await wrapper.get("button[aria-expanded='false']").trigger("click");
    expect(wrapper.text()).toContain("待确认（建议：配对荧光）");
    expect(wrapper.text()).toContain("待确认（建议：PMC047_pair_1）");
    await wrapper.find("button.stub-crop").trigger("click");
    await flushPromises();

    expect(cropSpy).toHaveBeenCalledWith("d047-panel-001", {
      x: 4,
      y: 3,
      width: 20,
      height: 16,
      panel_role: "paired_fluorescence",
      pair_id: "PMC047_pair_1",
      crop_notes: "fluorescence panel",
      suggestion_id: "suggestion_1",
      crop_review_action: "accepted",
    });
    expect(wrapper.text()).toContain("mask仍待复核，当前不可训练");
  });

  it("locks queue navigation while a mask save is pending and unlocks it after failure", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: records });
    const pendingSave = deferred<DatasetReviewRecord>();
    vi.spyOn(apiClient, "saveDatasetReviewMask").mockReturnValue(pendingSave.promise);
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    await wrapper.get("button.stub-save").trigger("click");

    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(true);
    expect(wrapper.findAll<HTMLSelectElement>(".queue-toolbar select").every((select) => select.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-navigation button").slice(0, 2).every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.stub-save").element.disabled).toBe(true);
    expect(wrapper.get("button.stub-save").attributes("title")).toContain("正在保存复核掩膜");

    pendingSave.reject(new Error("mask write failed"));
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("mask write failed");
    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(false);
    expect(wrapper.findAll<HTMLSelectElement>(".queue-toolbar select").every((select) => !select.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => !button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.stub-save").element.disabled).toBe(false);
  });

  it("keeps every record selector locked while candidate generation is pending", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: records });
    const pendingSeed = deferred<DatasetReviewRecord>();
    vi.spyOn(apiClient, "generateDatasetReviewSeed").mockReturnValue(pendingSeed.promise);
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    const seedButton = wrapper.findAll("button").find((button) => button.text().includes("生成候选掩膜"));
    await seedButton?.trigger("click");

    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.stub-save").element.disabled).toBe(true);
    expect(wrapper.get("button.stub-save").attributes("title")).toContain("正在生成候选掩膜");

    pendingSeed.reject(new Error("seed generation failed"));
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("seed generation failed");
    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(false);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => !button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.stub-save").element.disabled).toBe(false);
  });

  it("propagates the shared write lock while a crop save is pending", async () => {
    const uncroppedRecords = records.map((item) => ({
      ...item,
      crop_required: true,
      panel_role: "unclassified",
    } satisfies DatasetReviewRecord));
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: uncroppedRecords });
    const pendingCrop = deferred<DatasetReviewRecord>();
    vi.spyOn(apiClient, "saveDatasetReviewCrop").mockReturnValue(pendingCrop.promise);
    const wrapper = mount(DatasetReviewPage, {
      global: {
        stubs: {
          AppIcon: true,
          StaticCropEditor: CropStub,
          StaticMaskEditor: EditorStub,
        },
      },
    });
    await flushPromises();

    await wrapper.get("button.stub-crop").trigger("click");

    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(true);
    expect(wrapper.findAll<HTMLSelectElement>(".queue-toolbar select").every((select) => select.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-navigation button").slice(0, 2).every((button) => button.element.disabled)).toBe(true);
    expect(wrapper.get<HTMLButtonElement>("button.stub-crop").element.disabled).toBe(true);

    pendingCrop.resolve({ ...uncroppedRecords[0], crop_required: false });
    await flushPromises();

    expect(wrapper.get<HTMLButtonElement>(".queue-toolbar button").element.disabled).toBe(false);
    expect(wrapper.findAll<HTMLSelectElement>(".queue-toolbar select").every((select) => !select.element.disabled)).toBe(true);
    expect(wrapper.findAll<HTMLButtonElement>(".record-item").every((button) => !button.element.disabled)).toBe(true);
  });
});
