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

function makeRecords(
  count: number,
  datasetId = "d047_pmc_jaw_fluorescence_figures",
  prefix = "d047",
): DatasetReviewRecord[] {
  return Array.from({ length: count }, (_, index) => {
    const sequence = String(index + 1).padStart(3, "0");
    return {
      record_id: `${prefix}-panel-${sequence}`,
      dataset_id: datasetId,
      source_record_id: `${prefix.toUpperCase()}_figure_${sequence}`,
      image_path: `C:\\data\\${prefix}\\panel-${sequence}.png`,
      review_state: "review_required",
      license: "CC BY",
      training_eligible: false,
    } satisfies DatasetReviewRecord;
  });
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

  it("renders a bounded page of long review queues and enforces page boundaries", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: makeRecords(45) });
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    const pagination = wrapper.get("nav[aria-label='候选列表分页']");
    let pageButtons = pagination.findAll<HTMLButtonElement>("button");
    expect(wrapper.findAll(".record-item")).toHaveLength(20);
    expect(wrapper.findAll(".record-item")[0].text()).toContain("D047_figure_001");
    expect(wrapper.findAll(".record-item")[19].text()).toContain("D047_figure_020");
    expect(pagination.text()).toContain("第 1 / 3 页");
    expect(pagination.text()).toContain("1-20 / 45 条");
    expect(pageButtons[0].element.disabled).toBe(true);
    expect(pageButtons[1].element.disabled).toBe(false);

    await pageButtons[1].trigger("click");
    expect(wrapper.findAll(".record-item")).toHaveLength(20);
    expect(wrapper.findAll(".record-item")[0].text()).toContain("D047_figure_021");
    expect(wrapper.get(".record-item.selected").text()).toContain("D047_figure_021");
    expect(pagination.text()).toContain("第 2 / 3 页");

    pageButtons = pagination.findAll<HTMLButtonElement>("button");
    await pageButtons[1].trigger("click");
    expect(wrapper.findAll(".record-item")).toHaveLength(5);
    expect(wrapper.findAll(".record-item")[0].text()).toContain("D047_figure_041");
    expect(pagination.text()).toContain("第 3 / 3 页");
    expect(pagination.text()).toContain("41-45 / 45 条");
    expect(pagination.findAll<HTMLButtonElement>("button")[1].element.disabled).toBe(true);
  });

  it("resets pagination and selection when queue filters change", async () => {
    const d047Records = makeRecords(25);
    const d048Records = makeRecords(25, "d048_open_clinical_bone_fluorescence", "d048");
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: [...d047Records, ...d048Records] });
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    const pagination = wrapper.get("nav[aria-label='候选列表分页']");
    await pagination.findAll("button")[1].trigger("click");
    expect(pagination.text()).toContain("第 2 / 3 页");

    await wrapper.findAll<HTMLSelectElement>(".queue-toolbar select")[0].setValue("d048");
    expect(pagination.text()).toContain("第 1 / 2 页");
    expect(pagination.text()).toContain("1-20 / 25 条");
    expect(wrapper.findAll(".record-item")).toHaveLength(20);
    expect(wrapper.get(".record-item.selected").text()).toContain("D048_figure_001");
    expect(wrapper.text()).toContain("当前 1 / 25");
  });

  it("keeps relative record navigation continuous across page boundaries", async () => {
    vi.spyOn(apiClient, "listDatasetReviewQueue").mockResolvedValue({ items: makeRecords(25) });
    const wrapper = mount(DatasetReviewPage, {
      global: { stubs: { AppIcon: true, StaticMaskEditor: EditorStub } },
    });
    await flushPromises();

    await wrapper.findAll(".record-item")[19].trigger("click");
    expect(wrapper.get(".record-item.selected").text()).toContain("D047_figure_020");

    const nextRecordButton = wrapper.findAll(".record-navigation button").find((button) => button.text() === "下一条");
    await nextRecordButton?.trigger("click");

    expect(wrapper.get("nav[aria-label='候选列表分页']").text()).toContain("第 2 / 2 页");
    expect(wrapper.findAll(".record-item")).toHaveLength(5);
    expect(wrapper.get(".record-item.selected").text()).toContain("D047_figure_021");
    expect(wrapper.get(".record-metadata h2").text()).toBe("D047_figure_021");
  });
});
