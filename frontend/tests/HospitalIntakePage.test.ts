import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";

import HospitalIntakePage from "../src/pages/HospitalIntakePage.vue";
import { apiClient } from "../src/services/apiClient";
import type {
  HospitalIntakeBatchList,
  HospitalIntakeReport,
} from "../src/types/hospitalIntake";

const RouterLinkStub = defineComponent({
  props: {
    to: { type: [String, Object], required: true },
  },
  template: '<a href="#"><slot /></a>',
});

function reportFixture(overrides: Partial<HospitalIntakeReport> = {}): HospitalIntakeReport {
  return {
    schema_version: "hospital-intake-v1",
    batch_id: "HOSP-20260713-01",
    handover_id: "HANDOVER-20260713-01",
    source_organization: "测试医院",
    received_by: "project_receiver",
    received_at: "2026-07-13T08:00:00.000Z",
    authorization_status: "approved",
    deidentification_confirmed: true,
    target_condition_confirmed: true,
    case_map: { HOSP_CASE_001: "case_hosp_001" },
    summary: {
      status: "completed",
      file_count: 1,
      admitted_count: 1,
      quarantined_count: 0,
      target_domain_source_count: 1,
      training_eligible_count: 0,
      case_count: 1,
    },
    records: [
      {
        record_id: "intake_record_001",
        external_case_id: "HOSP_CASE_001",
        platform_case_id: "case_hosp_001",
        path: "artifacts/platform/uploads/case-001.mp4",
        original_filename: "case-001.mp4",
        suffix: ".mp4",
        size_bytes: 2048,
        sha256: "abc123",
        channel: "video",
        acquisition_mode: "unknown",
        channel_relationship: "unknown",
        status: "admitted",
        admission_stage: "target_registry_ready",
        reasons: [],
        warnings: [
          {
            code: "review_required",
            message: "样本仍需医生复核。",
            details: {},
          },
          {
            code: "official_image_resolution_mismatch",
            message: "Image is readable, but it does not match the official 3840x2160 device resolution.",
            details: {},
          },
        ],
        target_domain_flag: true,
        review_state: "review_required",
        training_eligible: false,
        fusion_eligible: false,
      },
    ],
    artifact_attachment: {
      status: "completed",
      status_path: "artifacts/intake/HOSP-20260713-01/artifact_attachment_status.json",
      expected_case_count: 1,
      attached_case_count: 1,
      attached_case_ids: ["case_hosp_001"],
      failures: [],
      status_persisted: true,
    },
    report_path: "artifacts/intake/HOSP-20260713-01/report.json",
    csv_path: "artifacts/intake/HOSP-20260713-01/report.csv",
    medical_boundary: "准入结果仅用于研发验证，样本需医生复核后再进入后续流程。",
    ...overrides,
  };
}

function emptyBatchList(): HospitalIntakeBatchList {
  return { count: 0, items: [] };
}

function localBatchDate(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10)
    .replaceAll("-", "");
}

function mountPage(): VueWrapper {
  return mount(HospitalIntakePage, {
    global: {
      stubs: {
        AppIcon: true,
        RouterLink: RouterLinkStub,
      },
    },
  });
}

async function selectFiles(wrapper: VueWrapper, files: File[]) {
  const input = wrapper.get<HTMLInputElement>('input[type="file"]');
  Object.defineProperty(input.element, "files", {
    configurable: true,
    value: files,
  });
  await input.trigger("change");
}

async function setSourceOrganization(wrapper: VueWrapper, value: string) {
  const label = wrapper
    .findAll(".form-grid label")
    .find((candidate) => candidate.text().includes("来源机构"));
  if (!label) throw new Error("未找到来源机构输入框");
  await label.get("input").setValue(value);
}

function formInput(wrapper: VueWrapper, labelText: string) {
  const label = wrapper
    .findAll(".form-grid label")
    .find((candidate) => candidate.text().includes(labelText));
  if (!label) throw new Error(`未找到${labelText}输入框`);
  return label.get<HTMLInputElement>("input");
}

function fileRowField(wrapper: VueWrapper, labelText: string, field: "input" | "select") {
  const label = wrapper
    .findAll(".file-fields label")
    .find((candidate) => candidate.text().includes(labelText));
  if (!label) throw new Error(`未找到${labelText}字段`);
  return label.get<HTMLInputElement | HTMLSelectElement>(field);
}

describe("HospitalIntakePage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("adds selected JPEG and MP4 files and removes an unwanted file", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    const wrapper = mountPage();
    await flushPromises();

    await selectFiles(wrapper, [
      new File(["video"], "surgery.mp4", { type: "video/mp4" }),
      new File(["image"], "fluorescence.jpg", { type: "image/jpeg" }),
    ]);

    expect(wrapper.text()).toContain("surgery.mp4");
    expect(wrapper.text()).toContain("fluorescence.jpg");
    expect(wrapper.findAll(".file-row")).toHaveLength(2);

    await wrapper.findAll('button[title="移除文件"]')[0].trigger("click");

    expect(wrapper.text()).not.toContain("surgery.mp4");
    expect(wrapper.text()).toContain("fluorescence.jpg");
    expect(wrapper.findAll(".file-row")).toHaveLength(1);
  });

  it("uploads the selected file, submits the batch, and renders admission evidence", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    const uploadSpy = vi.spyOn(apiClient, "uploadRawFile").mockResolvedValue({
      path: "artifacts/platform/uploads/case-001.mp4",
      filename: "upload-case-001.mp4",
      original_filename: "case-001.mp4",
      content_type: "video/mp4",
      size_bytes: 2048,
      sha256: "abc123",
    });
    const intakeReport = reportFixture();
    const submitSpy = vi
      .spyOn(apiClient, "submitHospitalIntakeBatch")
      .mockResolvedValue(intakeReport);
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "测试医院");
    await selectFiles(wrapper, [
      new File(["video"], "case-001.mp4", { type: "video/mp4" }),
    ]);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(uploadSpy).toHaveBeenCalledWith(expect.any(File), "none");
    expect(submitSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        source_organization: "测试医院",
        files: [
          expect.objectContaining({
            external_case_id: "HOSP_CASE_001",
            path: "artifacts/platform/uploads/case-001.mp4",
            channel: "video",
            original_filename: "case-001.mp4",
          }),
        ],
      }),
    );
    expect(wrapper.text()).toContain("批次检查完成：准入 1，隔离 0");
    expect(wrapper.text()).toContain("case-001.mp4");
    expect(wrapper.text()).toContain("已准入");
    expect(wrapper.text()).toContain("目标域来源就绪");
    expect(wrapper.text()).toContain("样本仍需医生复核");
    expect(wrapper.text()).toContain("图像可读取，但分辨率不符合赛题设备的 3840x2160 规格");
    expect(wrapper.text()).not.toContain("Image is readable");
    expect(wrapper.text()).toContain("保持禁入");
    expect(wrapper.text()).toContain("病例证据已关联 1/1");
    expect(wrapper.text()).toContain("准入结果仅用于研发验证");
    expect(wrapper.findAll(".report-links a")).toHaveLength(2);
  });

  it("locks file selection and removal while a batch upload is in progress", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue({
      count: 1,
      items: [
        {
          batch_id: "HOSP-HISTORY-LOCK",
          handover_id: "HANDOVER-HISTORY-LOCK",
          received_at: "2026-07-12T08:00:00.000Z",
          source_organization: "历史医院",
          summary: reportFixture().summary,
          report_path: "report-lock.json",
        },
      ],
    });
    let resolveUpload: ((value: Awaited<ReturnType<typeof apiClient.uploadRawFile>>) => void) | undefined;
    vi.spyOn(apiClient, "uploadRawFile").mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve;
      }),
    );
    vi.spyOn(apiClient, "submitHospitalIntakeBatch").mockResolvedValue(reportFixture());
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "测试医院");
    await selectFiles(wrapper, [new File(["video"], "case-001.mp4", { type: "video/mp4" })]);
    void wrapper.get("form").trigger("submit");
    await flushPromises();

    const fileInput = wrapper.get<HTMLInputElement>('input[type="file"]');
    const selectButton = wrapper
      .findAll<HTMLButtonElement>("button")
      .find((button) => button.text().includes("选择文件"));
    const removeButton = wrapper.get<HTMLButtonElement>('button[title="准入提交进行中，暂不能移除文件"]');
    expect(fileInput.element.disabled).toBe(true);
    expect(selectButton?.element.disabled).toBe(true);
    expect(selectButton?.attributes("title")).toBe("准入提交进行中，暂不能选择文件");
    expect(removeButton.element.disabled).toBe(true);
    expect(wrapper.get<HTMLButtonElement>(".recent-batches button").element.disabled).toBe(true);
    for (const field of wrapper.findAll<HTMLInputElement | HTMLSelectElement>(
      ".form-grid input, .form-grid select, .confirmation-grid input, .file-fields input, .file-fields select",
    )) {
      expect(field.element.matches(":disabled")).toBe(true);
    }

    Object.defineProperty(fileInput.element, "files", {
      configurable: true,
      value: [new File(["image"], "late.jpg", { type: "image/jpeg" })],
    });
    await fileInput.trigger("change");
    await removeButton.trigger("click");
    expect(wrapper.findAll(".file-row")).toHaveLength(1);
    expect(wrapper.text()).not.toContain("late.jpg");

    resolveUpload?.({
      path: "artifacts/platform/uploads/case-001.mp4",
      filename: "upload-case-001.mp4",
      original_filename: "case-001.mp4",
      content_type: "video/mp4",
      size_bytes: 2048,
      sha256: "abc123",
    });
    await flushPromises();
  });

  it("submits the immutable payload captured before asynchronous upload", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    let resolveUpload: ((value: Awaited<ReturnType<typeof apiClient.uploadRawFile>>) => void) | undefined;
    vi.spyOn(apiClient, "uploadRawFile").mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve;
      }),
    );
    const submitSpy = vi
      .spyOn(apiClient, "submitHospitalIntakeBatch")
      .mockResolvedValue(reportFixture());
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "原始医院");
    await selectFiles(wrapper, [new File(["video"], "snapshot.mp4", { type: "video/mp4" })]);
    await fileRowField(wrapper, "脱敏病例编号", "input").setValue("CASE_ORIGINAL");
    void wrapper.get("form").trigger("submit");
    await flushPromises();

    await setSourceOrganization(wrapper, "异步突变医院");
    await fileRowField(wrapper, "脱敏病例编号", "input").setValue("CASE_MUTATED");
    await fileRowField(wrapper, "输入通道", "select").setValue("fluorescence");

    resolveUpload?.({
      path: "artifacts/platform/uploads/snapshot.mp4",
      filename: "upload-snapshot.mp4",
      original_filename: "snapshot.mp4",
      content_type: "video/mp4",
      size_bytes: 2048,
      sha256: "snapshot-sha",
    });
    await flushPromises();

    expect(submitSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        source_organization: "原始医院",
        files: [
          expect.objectContaining({
            external_case_id: "CASE_ORIGINAL",
            channel: "video",
            acquisition_mode: "unknown",
            path: "artifacts/platform/uploads/snapshot.mp4",
          }),
        ],
      }),
    );
  });

  it("locks a completed batch against duplicate submission and opens a clean new batch", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    const uploadSpy = vi.spyOn(apiClient, "uploadRawFile").mockResolvedValue({
      path: "artifacts/platform/uploads/completed.mp4",
      filename: "upload-completed.mp4",
      original_filename: "completed.mp4",
      content_type: "video/mp4",
      size_bytes: 2048,
      sha256: "completed-sha",
    });
    const submitSpy = vi
      .spyOn(apiClient, "submitHospitalIntakeBatch")
      .mockResolvedValue(reportFixture());
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "测试医院");
    await selectFiles(wrapper, [new File(["video"], "completed.mp4", { type: "video/mp4" })]);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("批次准入已完成");
    const submitButton = wrapper.get<HTMLButtonElement>('button[type="submit"]');
    expect(submitButton.text()).toContain("本批次已完成");
    expect(submitButton.element.disabled).toBe(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(uploadSpy).toHaveBeenCalledTimes(1);
    expect(submitSpy).toHaveBeenCalledTimes(1);

    const newBatchButton = wrapper
      .findAll<HTMLButtonElement>("button")
      .find((button) => button.text().includes("开始新批次"));
    expect(newBatchButton).toBeDefined();
    await newBatchButton?.trigger("click");

    expect(wrapper.text()).not.toContain("批次准入已完成");
    expect(wrapper.findAll(".file-row")).toHaveLength(0);
    expect(formInput(wrapper, "来源机构").element.value).toBe("");
    expect(formInput(wrapper, "批次编号").element.value).toBe(`HOSP-${localBatchDate()}-02`);
    expect(wrapper.get<HTMLInputElement>('.confirmation-grid input[type="checkbox"]').element.checked).toBe(false);
    expect(wrapper.get<HTMLInputElement>('input[type="file"]').element.disabled).toBe(false);
    expect(wrapper.text()).toContain("新批次已建立");
  });

  it("keeps a failed upload visible and does not submit its batch", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    vi.spyOn(apiClient, "uploadRawFile").mockRejectedValue(new Error("上传连接中断"));
    const submitSpy = vi.spyOn(apiClient, "submitHospitalIntakeBatch");
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "测试医院");
    await selectFiles(wrapper, [
      new File(["video"], "broken.mp4", { type: "video/mp4" }),
    ]);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(submitSpy).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("上传失败");
    expect(wrapper.text()).toContain("上传连接中断");
    expect(wrapper.text()).toContain("存在上传或格式校验失败的文件");
    expect(wrapper.get(".submit-row p").classes()).toContain("error");
  });

  it("requires a safe case identifier and a pair identifier for synchronized inputs", async () => {
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue(emptyBatchList());
    const wrapper = mountPage();
    await flushPromises();

    await setSourceOrganization(wrapper, "测试医院");
    await selectFiles(wrapper, [
      new File(["image"], "white-light.jpg", { type: "image/jpeg" }),
    ]);
    const submitButton = wrapper.get<HTMLButtonElement>('button[type="submit"]');
    const caseIdInput = fileRowField(wrapper, "脱敏病例编号", "input");
    expect(caseIdInput.attributes("pattern")).toBe("[A-Za-z0-9][A-Za-z0-9_\\-]{2,63}");

    await caseIdInput.setValue("病例 01");
    expect(submitButton.element.disabled).toBe(true);
    expect(wrapper.text()).toContain("脱敏病例编号需为 3-64 位字符，首位为字母或数字");

    await caseIdInput.setValue("_HOSP_CASE-01");
    expect(submitButton.element.disabled).toBe(true);

    await caseIdInput.setValue("HOSP_CASE-01");
    await fileRowField(wrapper, "通道关系", "select").setValue("synchronized_pair");
    expect(submitButton.element.disabled).toBe(true);

    await fileRowField(wrapper, "配对编号", "input").setValue("pair-001");
    expect(submitButton.element.disabled).toBe(false);
  });

  it("loads a historical batch and displays its quarantine and attachment failure", async () => {
    const historicalSummary: HospitalIntakeReport["summary"] = {
      status: "completed_with_quarantine",
      file_count: 1,
      admitted_count: 0,
      quarantined_count: 1,
      target_domain_source_count: 0,
      training_eligible_count: 0,
      case_count: 0,
    };
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue({
      count: 1,
      items: [
        {
          batch_id: "HOSP-HISTORY-01",
          handover_id: "HANDOVER-HISTORY-01",
          received_at: "2026-07-12T08:00:00.000Z",
          source_organization: "历史医院",
          summary: historicalSummary,
          report_path: "artifacts/intake/HOSP-HISTORY-01/report.json",
        },
      ],
    });
    const historicalReport = reportFixture({
      batch_id: "HOSP-HISTORY-01",
      handover_id: "HANDOVER-HISTORY-01",
      source_organization: "历史医院",
      summary: historicalSummary,
      case_map: {},
      records: [
        {
          ...reportFixture().records[0],
          record_id: "intake_record_history",
          platform_case_id: null,
          original_filename: "missing-authorization.jpg",
          suffix: ".jpg",
          channel: "fluorescence",
          acquisition_mode: "fluorescence",
          channel_relationship: "single_channel",
          status: "quarantined",
          admission_stage: "quarantined",
          reasons: [
            {
              code: "authorization_missing",
              message: "机构授权尚未确认。",
              details: {},
            },
          ],
          warnings: [],
          target_domain_flag: false,
        },
      ],
      artifact_attachment: {
        status: "completed_with_errors",
        status_path: "artifacts/intake/HOSP-HISTORY-01/artifact_attachment_status.json",
        expected_case_count: 1,
        attached_case_count: 0,
        attached_case_ids: [],
        failures: [
          {
            code: "case_artifact_attachment_failed",
            platform_case_id: "case_with_a_very_long_identifier_that_must_wrap_without_overflow",
            error_type: "OSError",
          },
        ],
        status_persisted: true,
      },
    });
    const loadSpy = vi
      .spyOn(apiClient, "getHospitalIntakeBatch")
      .mockResolvedValue(historicalReport);
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("近期准入批次（1）");
    const batchButton = wrapper
      .findAll(".recent-batches button")
      .find((button) => button.text().includes("HOSP-HISTORY-01"));
    expect(batchButton).toBeDefined();
    await batchButton?.trigger("click");
    await flushPromises();

    expect(loadSpy).toHaveBeenCalledWith("HOSP-HISTORY-01");
    expect(wrapper.text()).toContain("已载入准入批次：HOSP-HISTORY-01");
    expect(wrapper.text()).toContain("missing-authorization.jpg");
    expect(wrapper.text()).toContain("已隔离");
    expect(wrapper.text()).toContain("机构授权尚未确认");
    expect(wrapper.text()).toContain("病例证据关联异常");
    expect(wrapper.text()).toContain("case_artifact_attachment_failed");
    expect(wrapper.text()).toContain("case_with_a_very_long_identifier_that_must_wrap_without_overflow");
  });

  it("keeps the newest historical batch when read requests resolve out of order", async () => {
    const summary = reportFixture().summary;
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue({
      count: 2,
      items: [
        {
          batch_id: "HOSP-RACE-A",
          handover_id: "HANDOVER-RACE-A",
          received_at: "2026-07-12T08:00:00.000Z",
          source_organization: "医院 A",
          summary,
          report_path: "report-a.json",
        },
        {
          batch_id: "HOSP-RACE-B",
          handover_id: "HANDOVER-RACE-B",
          received_at: "2026-07-12T09:00:00.000Z",
          source_organization: "医院 B",
          summary,
          report_path: "report-b.json",
        },
      ],
    });
    let resolveA: ((value: HospitalIntakeReport) => void) | undefined;
    let resolveB: ((value: HospitalIntakeReport) => void) | undefined;
    vi.spyOn(apiClient, "getHospitalIntakeBatch").mockImplementation(
      (batchId) =>
        new Promise((resolve) => {
          if (batchId === "HOSP-RACE-A") resolveA = resolve;
          if (batchId === "HOSP-RACE-B") resolveB = resolve;
        }),
    );
    const wrapper = mountPage();
    await flushPromises();

    const batchButtons = wrapper.findAll<HTMLButtonElement>(".recent-batches button");
    await batchButtons[0].trigger("click");
    expect(batchButtons[0].element.disabled).toBe(true);
    await batchButtons[1].trigger("click");
    expect(batchButtons[1].element.disabled).toBe(true);

    resolveB?.(
      reportFixture({
        batch_id: "HOSP-RACE-B",
        source_organization: "医院 B",
        records: [{ ...reportFixture().records[0], original_filename: "newest-batch.mp4" }],
      }),
    );
    await flushPromises();
    expect(wrapper.text()).toContain("已载入准入批次：HOSP-RACE-B");
    expect(wrapper.text()).toContain("newest-batch.mp4");

    resolveA?.(
      reportFixture({
        batch_id: "HOSP-RACE-A",
        source_organization: "医院 A",
        records: [{ ...reportFixture().records[0], original_filename: "stale-batch.mp4" }],
      }),
    );
    await flushPromises();
    expect(wrapper.text()).toContain("已载入准入批次：HOSP-RACE-B");
    expect(wrapper.text()).toContain("newest-batch.mp4");
    expect(wrapper.text()).not.toContain("stale-batch.mp4");
  });

  it("advances an unused daily default batch number after loading recent batches", async () => {
    const today = localBatchDate();
    const summary = reportFixture().summary;
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockResolvedValue({
      count: 3,
      items: [
        {
          batch_id: `HOSP-${today}-01`,
          handover_id: "HANDOVER-01",
          received_at: "2026-07-13T08:00:00.000Z",
          source_organization: "测试医院",
          summary,
          report_path: "report-01.json",
        },
        {
          batch_id: `HOSP-${today}-03`,
          handover_id: "HANDOVER-03",
          received_at: "2026-07-13T09:00:00.000Z",
          source_organization: "测试医院",
          summary,
          report_path: "report-03.json",
        },
        {
          batch_id: "HOSP-19990101-99",
          handover_id: "HANDOVER-OLD",
          received_at: "1999-01-01T00:00:00.000Z",
          source_organization: "历史医院",
          summary,
          report_path: "report-old.json",
        },
      ],
    });

    const wrapper = mountPage();
    await flushPromises();

    expect(formInput(wrapper, "批次编号").element.value).toBe(`HOSP-${today}-04`);
    expect(formInput(wrapper, "交接编号").element.value).toBe(`HANDOVER-${today}-04`);
  });

  it("preserves a manually entered batch number while recent batches are loading", async () => {
    const today = localBatchDate();
    let resolveBatches: ((value: HospitalIntakeBatchList) => void) | undefined;
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockReturnValue(
      new Promise((resolve) => {
        resolveBatches = resolve;
      }),
    );
    const wrapper = mountPage();
    await formInput(wrapper, "批次编号").setValue("MANUAL-BATCH-07");

    resolveBatches?.({
      count: 1,
      items: [
        {
          batch_id: `HOSP-${today}-01`,
          handover_id: "HANDOVER-01",
          received_at: "2026-07-13T08:00:00.000Z",
          source_organization: "测试医院",
          summary: reportFixture().summary,
          report_path: "report-01.json",
        },
      ],
    });
    await flushPromises();

    expect(formInput(wrapper, "批次编号").element.value).toBe("MANUAL-BATCH-07");
  });

  it("preserves a manual handover number when the daily batch number advances", async () => {
    const today = localBatchDate();
    let resolveBatches: ((value: HospitalIntakeBatchList) => void) | undefined;
    vi.spyOn(apiClient, "listHospitalIntakeBatches").mockReturnValue(
      new Promise((resolve) => {
        resolveBatches = resolve;
      }),
    );
    const wrapper = mountPage();
    await formInput(wrapper, "交接编号").setValue("MANUAL-HANDOVER-09");

    resolveBatches?.({
      count: 1,
      items: [
        {
          batch_id: `HOSP-${today}-01`,
          handover_id: `HANDOVER-${today}-01`,
          received_at: "2026-07-13T08:00:00.000Z",
          source_organization: "测试医院",
          summary: reportFixture().summary,
          report_path: "report-01.json",
        },
      ],
    });
    await flushPromises();

    expect(formInput(wrapper, "批次编号").element.value).toBe(`HOSP-${today}-02`);
    expect(formInput(wrapper, "交接编号").element.value).toBe("MANUAL-HANDOVER-09");
  });
});
