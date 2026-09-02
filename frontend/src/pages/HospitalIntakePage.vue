<template>
  <AppPageShell class="intake-page" width="large">
    <AppPageHeader eyebrow="真实数据交接" icon="shield" icon-tone="green" title="医院数据准入与隔离">
      <template #actions>
        <RouterLink class="back-link" to="/cases">
          <AppIcon name="case" />
          病例档案
        </RouterLink>
      </template>
    </AppPageHeader>

    <section class="intake-layout">
      <form class="intake-form" @submit.prevent="submitBatch">
        <header class="section-header">
          <div>
            <span>01</span>
            <h2>交接与授权</h2>
          </div>
          <strong :class="authorizationReady ? 'ready' : 'pending'">
            {{ authorizationReady ? "准入条件已确认" : "等待完整确认" }}
          </strong>
        </header>

        <div v-if="completedBatchId" class="completion-state" role="status">
          <AppIcon name="check" variant="badge" tone="cyan" />
          <div>
            <strong>批次准入已完成</strong>
            <span>批次 {{ completedBatchId }} 已锁定。开始新批次后可继续登记文件。</span>
          </div>
        </div>

        <div class="form-grid">
          <label>
            <span>批次编号</span>
            <input v-model.trim="form.batchId" required maxlength="64" :disabled="formLocked" />
          </label>
          <label>
            <span>交接编号</span>
            <input v-model.trim="form.handoverId" required maxlength="128" :disabled="formLocked" />
          </label>
          <label>
            <span>来源机构</span>
            <input v-model.trim="form.sourceOrganization" required maxlength="160" :disabled="formLocked" />
          </label>
          <label>
            <span>接收人</span>
            <input v-model.trim="form.receivedBy" required maxlength="80" :disabled="formLocked" />
          </label>
          <label>
            <span>接收时间</span>
            <input v-model="form.receivedAt" type="datetime-local" required :disabled="formLocked" />
          </label>
          <label>
            <span>机构授权状态</span>
            <select v-model="form.authorizationStatus" :disabled="formLocked">
              <option value="approved">已批准</option>
              <option value="pending">待批准</option>
              <option value="restricted">限制使用</option>
              <option value="denied">未批准</option>
            </select>
          </label>
          <label class="wide-field">
            <span>允许用途</span>
            <input v-model.trim="form.usageScope" required maxlength="240" :disabled="formLocked" />
          </label>
          <label class="wide-field">
            <span>脱敏方法</span>
            <input
              v-model.trim="form.deidentificationMethod"
              placeholder="例如：医院导出前人工复核与字段清除"
              :disabled="formLocked"
            />
          </label>
        </div>

        <fieldset class="confirmation-grid" :disabled="formLocked">
          <label>
            <input v-model="form.deidentificationConfirmed" type="checkbox" />
            <span>已确认影像与元数据完成脱敏</span>
          </label>
          <label>
            <input v-model="form.mappingHeldByInstitution" type="checkbox" />
            <span>病例编号映射表由医院保管</span>
          </label>
          <label>
            <input v-model="form.targetConditionConfirmed" type="checkbox" />
            <span>已确认属于颌骨骨髓炎目标场景</span>
          </label>
        </fieldset>

        <header class="section-header file-heading">
          <div>
            <span>02</span>
            <h2>官方 JPEG / MP4 文件</h2>
          </div>
          <AppButton
            icon="upload"
            variant="secondary"
            type="button"
            :disabled="formLocked"
            :title="fileActionTitle('选择')"
            @click="openFilePicker"
          >
            选择文件
          </AppButton>
        </header>
        <input
          ref="fileInput"
          class="hidden-file-input"
          type="file"
          accept=".jpg,.jpeg,.mp4,image/jpeg,video/mp4"
          multiple
          :disabled="formLocked"
          @change="handleFiles"
        />

        <div v-if="fileRows.length" class="file-list">
          <article v-for="row in fileRows" :key="row.id" class="file-row">
            <div class="file-row-title">
              <AppIcon :name="row.channel === 'video' ? 'video' : 'file'" variant="tile" tone="cyan" />
              <div>
                <strong>{{ row.file.name }}</strong>
                <small>{{ formatBytes(row.file.size) }} · {{ row.file.type || "待探测格式" }}</small>
              </div>
              <button
                type="button"
                class="icon-button"
                :disabled="formLocked"
                :title="fileActionTitle('移除')"
                @click="removeFile(row.id)"
              >
                <AppIcon name="trash" />
              </button>
            </div>
            <div class="file-fields">
              <label>
                <span>脱敏病例编号</span>
                <input
                  v-model.trim="row.externalCaseId"
                  required
                  minlength="3"
                  maxlength="64"
                  pattern="[A-Za-z0-9][A-Za-z0-9_\-]{2,63}"
                  title="请输入 3-64 位字符，首位为字母或数字，其余可含下划线或短横线"
                  :disabled="formLocked"
                />
              </label>
              <label>
                <span>输入通道</span>
                <select v-model="row.channel" :disabled="formLocked" @change="syncRowDefaults(row)">
                  <option value="video">MP4 视频</option>
                  <option value="white_light">白光 JPEG</option>
                  <option value="fluorescence">ICG 荧光 JPEG</option>
                </select>
              </label>
              <label>
                <span>采集模式</span>
                <select v-model="row.acquisitionMode" :disabled="formLocked">
                  <option value="white_light">白光</option>
                  <option value="fluorescence">荧光</option>
                  <option value="overlay">叠加</option>
                  <option value="mode_switching">模式切换</option>
                  <option value="synchronized_dual_channel">同步双通道</option>
                  <option value="unknown">待确认</option>
                </select>
              </label>
              <label>
                <span>通道关系</span>
                <select v-model="row.channelRelationship" :disabled="formLocked">
                  <option value="single_channel">单通道</option>
                  <option value="synchronized_pair">同步配对</option>
                  <option value="mode_switch">模式切换</option>
                  <option value="overlay_only">仅叠加画面</option>
                  <option value="unknown">待确认</option>
                </select>
              </label>
              <label v-if="row.channelRelationship === 'synchronized_pair'">
                <span>配对编号</span>
                <input v-model.trim="row.pairId" required placeholder="例如 pair-001" :disabled="formLocked" />
              </label>
              <div class="row-state" :class="row.status">
                <span>处理状态</span>
                <strong>{{ rowStatusLabel(row) }}</strong>
              </div>
            </div>
            <p v-if="!isSafeCaseId(row.externalCaseId)" class="row-error">
              脱敏病例编号需为 3-64 位字符，首位为字母或数字，其余可含下划线或短横线。
            </p>
            <p v-if="row.sha256" class="checksum">SHA256：{{ row.sha256 }}</p>
            <p v-if="row.error" class="row-error">{{ row.error }}</p>
          </article>
        </div>
        <p v-else class="empty-files">请选择医院交接的脱敏 JPEG 或 MP4 文件。</p>

        <div class="submit-row">
          <AppButton
            icon="check"
            variant="primary"
            type="submit"
            :disabled="formLocked || !canSubmit"
          >
            {{ submitting ? "正在校验并登记" : completedBatchId ? "本批次已完成" : "执行准入检查" }}
          </AppButton>
          <AppButton
            v-if="completedBatchId"
            icon="plus"
            variant="secondary"
            type="button"
            :disabled="Boolean(loadingBatchId)"
            @click="startNewBatch"
          >
            开始新批次
          </AppButton>
          <p :class="{ error: operationType === 'error' }">{{ operationMessage }}</p>
        </div>
      </form>

      <aside class="intake-results" aria-label="准入结果">
        <header class="section-header">
          <div>
            <span>03</span>
            <h2>准入与隔离结果</h2>
          </div>
          <strong v-if="report">批次 {{ report.batch_id }}</strong>
        </header>

        <template v-if="report">
          <dl class="summary-grid">
            <div>
              <dt>文件总数</dt>
              <dd>{{ report.summary.file_count }}</dd>
            </div>
            <div class="success">
              <dt>已准入</dt>
              <dd>{{ report.summary.admitted_count }}</dd>
            </div>
            <div class="danger">
              <dt>已隔离</dt>
              <dd>{{ report.summary.quarantined_count }}</dd>
            </div>
            <div>
              <dt>目标域来源</dt>
              <dd>{{ report.summary.target_domain_source_count }}</dd>
            </div>
          </dl>

          <div
            v-if="report.artifact_attachment"
            class="artifact-attachment"
            :class="{ error: !artifactAttachmentHealthy(report.artifact_attachment) }"
          >
            <strong v-if="artifactAttachmentHealthy(report.artifact_attachment)">
              病例证据已关联 {{ report.artifact_attachment.attached_case_count }}/{{
                report.artifact_attachment.expected_case_count
              }}
            </strong>
            <template v-else>
              <strong>病例证据关联异常</strong>
              <p>
                已关联 {{ report.artifact_attachment.attached_case_count }}/{{
                  report.artifact_attachment.expected_case_count
                }}，状态记录{{ report.artifact_attachment.status_persisted ? "已保存" : "未保存" }}。
              </p>
              <ul v-if="report.artifact_attachment.failures.length">
                <li
                  v-for="(failure, index) in report.artifact_attachment.failures"
                  :key="failure.code + '-' + index"
                >
                  <code>{{ failure.code }}</code>
                  <span v-if="failure.platform_case_id">病例 {{ failure.platform_case_id }}</span>
                  <span v-if="failure.error_type">{{ failure.error_type }}</span>
                </li>
              </ul>
            </template>
          </div>

          <div class="report-links">
            <a :href="apiClient.fileDownloadUrl(report.report_path)">下载 JSON 报告</a>
            <a :href="apiClient.fileDownloadUrl(report.csv_path)">下载 CSV 清单</a>
          </div>

          <ul class="result-list">
            <li v-for="record in report.records" :key="record.record_id" :class="record.status">
              <div class="result-title">
                <strong>{{ record.original_filename }}</strong>
                <span>{{ record.status === "admitted" ? "已准入" : "已隔离" }}</span>
              </div>
              <dl>
                <div><dt>病例</dt><dd>{{ record.external_case_id }}</dd></div>
                <div><dt>通道</dt><dd>{{ channelLabel(record.channel) }}</dd></div>
                <div><dt>阶段</dt><dd>{{ admissionStageLabel(record.admission_stage) }}</dd></div>
                <div><dt>训练</dt><dd>保持禁入</dd></div>
              </dl>
              <p v-for="finding in record.reasons" :key="finding.code" class="finding error">
                {{ findingMessage(finding) }}
              </p>
              <p v-for="finding in record.warnings" :key="finding.code" class="finding">
                {{ findingMessage(finding) }}
              </p>
              <RouterLink
                v-if="record.platform_case_id"
                class="case-link"
                :to="{ path: '/case', query: { caseId: record.platform_case_id } }"
              >
                打开平台病例
              </RouterLink>
            </li>
          </ul>
          <p class="medical-boundary">{{ report.medical_boundary }}</p>
        </template>
        <div v-else class="empty-result">
          <AppIcon name="clipboard" variant="badge" tone="cyan" />
          <strong>等待准入检查</strong>
          <p>完成交接确认并选择文件后，这里将显示逐文件准入、隔离原因和病例关联结果。</p>
        </div>

        <details v-if="recentBatches.length" class="recent-batches">
          <summary>近期准入批次（{{ recentBatches.length }}）</summary>
          <button
            v-for="batch in recentBatches"
            :key="batch.batch_id"
            type="button"
            :disabled="submitting || loadingBatchId === batch.batch_id"
            :aria-busy="loadingBatchId === batch.batch_id"
            @click="loadBatch(batch.batch_id)"
          >
            <strong>{{ batch.batch_id }}</strong>
            <span v-if="loadingBatchId === batch.batch_id">正在读取批次...</span>
            <span v-else>准入 {{ batch.summary.admitted_count }} / 隔离 {{ batch.summary.quarantined_count }}</span>
          </button>
        </details>
      </aside>
    </section>
  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import AppPageHeader from "@/components/AppPageHeader.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import { apiClient } from "@/services/apiClient";
import type { InputChannel } from "@/types/case";
import type {
  HospitalIntakeArtifactAttachment,
  HospitalAcquisitionMode,
  HospitalAuthorizationStatus,
  HospitalChannelRelationship,
  HospitalIntakeBatchList,
  HospitalIntakeReport,
  IntakeFinding,
} from "@/types/hospitalIntake";
import { errorMessage } from "@/utils/caseDisplay";

type FileStatus = "pending" | "uploading" | "uploaded" | "failed";

interface IntakeFileRow {
  id: string;
  file: File;
  externalCaseId: string;
  channel: Exclude<InputChannel, "sequence">;
  acquisitionMode: HospitalAcquisitionMode;
  channelRelationship: HospitalChannelRelationship;
  pairId: string;
  status: FileStatus;
  uploadedPath: string;
  sha256: string;
  error: string;
}

interface IntakeSubmissionFileSnapshot {
  readonly id: string;
  readonly file: File;
  readonly externalCaseId: string;
  readonly channel: Exclude<InputChannel, "sequence">;
  readonly acquisitionMode: HospitalAcquisitionMode;
  readonly channelRelationship: HospitalChannelRelationship;
  readonly pairId: string;
  readonly status: FileStatus;
  readonly uploadedPath: string;
}

interface IntakeSubmissionSnapshot {
  readonly batchId: string;
  readonly handoverId: string;
  readonly sourceOrganization: string;
  readonly receivedBy: string;
  readonly receivedAt: string;
  readonly authorizationStatus: HospitalAuthorizationStatus;
  readonly usageScope: string;
  readonly deidentificationConfirmed: boolean;
  readonly deidentificationMethod: string;
  readonly mappingHeldByInstitution: boolean;
  readonly targetConditionConfirmed: boolean;
  readonly files: readonly IntakeSubmissionFileSnapshot[];
}

const now = new Date();
const localIsoDateTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString();
const batchDate = localIsoDateTime.slice(0, 10).replaceAll("-", "");
const localDateTime = localIsoDateTime.slice(0, 16);
const defaultBatchId = `HOSP-${batchDate}-01`;
const defaultHandoverId = `HANDOVER-${batchDate}-01`;
const form = reactive({
  batchId: defaultBatchId,
  handoverId: defaultHandoverId,
  sourceOrganization: "",
  receivedBy: "project_receiver",
  receivedAt: localDateTime,
  authorizationStatus: "pending" as HospitalAuthorizationStatus,
  usageScope: "research_validation",
  deidentificationConfirmed: false,
  deidentificationMethod: "",
  mappingHeldByInstitution: false,
  targetConditionConfirmed: false,
});
const fileInput = ref<HTMLInputElement | null>(null);
const fileRows = ref<IntakeFileRow[]>([]);
const submitting = ref(false);
const operationMessage = ref("等待选择文件。所有样本默认保持待复核与训练禁入。");
const operationType = ref<"info" | "error">("info");
const report = ref<HospitalIntakeReport | null>(null);
const recentBatches = ref<HospitalIntakeBatchList["items"]>([]);
const completedBatchId = ref<string | null>(null);
const loadingBatchId = ref<string | null>(null);
let recentBatchesRequestSequence = 0;
let batchLoadRequestSequence = 0;
const SAFE_CASE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/;

const authorizationReady = computed(
  () =>
    form.authorizationStatus === "approved" &&
    form.deidentificationConfirmed &&
    form.mappingHeldByInstitution,
);
const formLocked = computed(() => submitting.value || Boolean(completedBatchId.value));
const canSubmit = computed(
  () =>
    !completedBatchId.value &&
    Boolean(
      form.batchId.trim() &&
      form.handoverId.trim() &&
      form.sourceOrganization.trim() &&
      form.receivedBy.trim() &&
      form.receivedAt &&
      form.usageScope.trim() &&
      fileRows.value.length,
    ) &&
    fileRows.value.every(
      (row) =>
        row.status !== "uploading" &&
        isSafeCaseId(row.externalCaseId) &&
        (row.channelRelationship !== "synchronized_pair" || Boolean(row.pairId.trim())),
    ),
);

onMounted(() => {
  void refreshRecentBatches();
});

function openFilePicker() {
  if (formLocked.value) return;
  fileInput.value?.click();
}

function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const selected = Array.from(input.files ?? []);
  input.value = "";
  if (formLocked.value) return;
  for (const file of selected) {
    const isVideo = file.name.toLowerCase().endsWith(".mp4");
    fileRows.value.push({
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      file,
      externalCaseId: "HOSP_CASE_001",
      channel: isVideo ? "video" : "white_light",
      acquisitionMode: isVideo ? "unknown" : "white_light",
      channelRelationship: isVideo ? "unknown" : "single_channel",
      pairId: "",
      status: "pending",
      uploadedPath: "",
      sha256: "",
      error: "",
    });
  }
}

function removeFile(id: string) {
  if (formLocked.value) return;
  fileRows.value = fileRows.value.filter((row) => row.id !== id);
}

function isSafeCaseId(value: string): boolean {
  return SAFE_CASE_ID_PATTERN.test(value.trim());
}

function syncRowDefaults(row: IntakeFileRow) {
  if (formLocked.value) return;
  if (row.channel === "video") {
    row.acquisitionMode = "unknown";
    row.channelRelationship = "unknown";
    return;
  }
  row.acquisitionMode = row.channel === "white_light" ? "white_light" : "fluorescence";
  row.channelRelationship = "single_channel";
}

function fileActionTitle(action: "选择" | "移除"): string {
  if (submitting.value) return `准入提交进行中，暂不能${action}文件`;
  if (completedBatchId.value) return `批次已完成，请开始新批次后${action}文件`;
  return action === "选择" ? "选择 JPEG 或 MP4 文件" : "移除文件";
}

function createSubmissionSnapshot(): IntakeSubmissionSnapshot {
  const files = fileRows.value.map((row) =>
    Object.freeze({
      id: row.id,
      file: row.file,
      externalCaseId: row.externalCaseId.trim(),
      channel: row.channel,
      acquisitionMode: row.acquisitionMode,
      channelRelationship: row.channelRelationship,
      pairId: row.pairId.trim(),
      status: row.status,
      uploadedPath: row.uploadedPath,
    }),
  );
  return Object.freeze({
    batchId: form.batchId.trim(),
    handoverId: form.handoverId.trim(),
    sourceOrganization: form.sourceOrganization.trim(),
    receivedBy: form.receivedBy.trim(),
    receivedAt: new Date(form.receivedAt).toISOString(),
    authorizationStatus: form.authorizationStatus,
    usageScope: form.usageScope.trim(),
    deidentificationConfirmed: form.deidentificationConfirmed,
    deidentificationMethod: form.deidentificationMethod.trim(),
    mappingHeldByInstitution: form.mappingHeldByInstitution,
    targetConditionConfirmed: form.targetConditionConfirmed,
    files: Object.freeze(files),
  });
}

async function submitBatch() {
  if (!canSubmit.value || submitting.value) return;
  const snapshot = createSubmissionSnapshot();
  submitting.value = true;
  batchLoadRequestSequence += 1;
  loadingBatchId.value = null;
  report.value = null;
  operationType.value = "info";
  operationMessage.value = "正在上传文件并执行完整性校验...";
  try {
    const uploadedPaths = new Map<string, string>();
    let uploadFailed = false;
    for (const fileSnapshot of snapshot.files) {
      if (fileSnapshot.status === "uploaded" && fileSnapshot.uploadedPath) {
        uploadedPaths.set(fileSnapshot.id, fileSnapshot.uploadedPath);
        continue;
      }
      const row = fileRows.value.find((candidate) => candidate.id === fileSnapshot.id);
      if (row) {
        row.status = "uploading";
        row.error = "";
      }
      try {
        const uploaded = await apiClient.uploadRawFile(fileSnapshot.file, "none");
        uploadedPaths.set(fileSnapshot.id, uploaded.path);
        if (row) {
          row.uploadedPath = uploaded.path;
          row.sha256 = uploaded.sha256;
          row.status = "uploaded";
        }
      } catch (error) {
        uploadFailed = true;
        if (row) {
          row.status = "failed";
          row.error = errorMessage(error);
        }
      }
    }
    if (uploadFailed) {
      operationType.value = "error";
      operationMessage.value = "存在上传或格式校验失败的文件，请移除或重新选择后再执行准入。";
      return;
    }

    const submittedReport = await apiClient.submitHospitalIntakeBatch({
      batch_id: snapshot.batchId,
      handover_id: snapshot.handoverId,
      source_organization: snapshot.sourceOrganization,
      received_by: snapshot.receivedBy,
      received_at: snapshot.receivedAt,
      authorization_status: snapshot.authorizationStatus,
      usage_scope: snapshot.usageScope,
      deidentification_confirmed: snapshot.deidentificationConfirmed,
      deidentification_method: snapshot.deidentificationMethod || null,
      mapping_held_by_institution: snapshot.mappingHeldByInstitution,
      target_condition_confirmed: snapshot.targetConditionConfirmed,
      files: snapshot.files.map((fileSnapshot) => ({
        external_case_id: fileSnapshot.externalCaseId,
        path: uploadedPaths.get(fileSnapshot.id) ?? fileSnapshot.uploadedPath,
        channel: fileSnapshot.channel,
        acquisition_mode: fileSnapshot.acquisitionMode,
        channel_relationship: fileSnapshot.channelRelationship,
        pair_id: fileSnapshot.pairId || null,
        original_filename: fileSnapshot.file.name,
        metadata: {},
        missing_fields: [],
      })),
    });
    report.value = submittedReport;
    completedBatchId.value = snapshot.batchId;
    operationMessage.value = `批次检查完成：准入 ${submittedReport.summary.admitted_count}，隔离 ${submittedReport.summary.quarantined_count}。`;
    await refreshRecentBatches();
  } catch (error) {
    operationType.value = "error";
    operationMessage.value = errorMessage(error);
  } finally {
    submitting.value = false;
  }
}

async function refreshRecentBatches() {
  const requestSequence = ++recentBatchesRequestSequence;
  try {
    const batches = (await apiClient.listHospitalIntakeBatches()).items;
    if (requestSequence !== recentBatchesRequestSequence) return;
    recentBatches.value = batches;
    advanceDefaultBatchId(batches);
  } catch {
    if (requestSequence !== recentBatchesRequestSequence) return;
    recentBatches.value = [];
  }
}

function advanceDefaultBatchId(batches: HospitalIntakeBatchList["items"]) {
  if (completedBatchId.value || form.batchId !== defaultBatchId) return;
  const prefix = `HOSP-${batchDate}-`;
  const sequences = batches
    .map((batch) => {
      if (!batch.batch_id.startsWith(prefix)) return null;
      const suffix = batch.batch_id.slice(prefix.length);
      return /^\d+$/.test(suffix) ? Number.parseInt(suffix, 10) : null;
    })
    .filter((sequence): sequence is number => sequence !== null);
  if (!sequences.includes(1)) return;
  const nextSequence = String(Math.max(...sequences) + 1).padStart(2, "0");
  form.batchId = `${prefix}${nextSequence}`;
  if (form.handoverId === defaultHandoverId) {
    form.handoverId = `HANDOVER-${batchDate}-${nextSequence}`;
  }
}

async function loadBatch(batchId: string) {
  if (submitting.value) return;
  const requestSequence = ++batchLoadRequestSequence;
  loadingBatchId.value = batchId;
  try {
    const loadedReport = await apiClient.getHospitalIntakeBatch(batchId);
    if (requestSequence !== batchLoadRequestSequence) return;
    report.value = loadedReport;
    operationType.value = "info";
    operationMessage.value = `已载入准入批次：${batchId}`;
  } catch (error) {
    if (requestSequence !== batchLoadRequestSequence) return;
    operationType.value = "error";
    operationMessage.value = errorMessage(error);
  } finally {
    if (requestSequence === batchLoadRequestSequence) loadingBatchId.value = null;
  }
}

function startNewBatch() {
  if (submitting.value || loadingBatchId.value) return;
  const nextSequence = nextDailyBatchSequence();
  Object.assign(form, {
    batchId: `HOSP-${batchDate}-${nextSequence}`,
    handoverId: `HANDOVER-${batchDate}-${nextSequence}`,
    sourceOrganization: "",
    receivedBy: "project_receiver",
    receivedAt: localDateTime,
    authorizationStatus: "pending" as HospitalAuthorizationStatus,
    usageScope: "research_validation",
    deidentificationConfirmed: false,
    deidentificationMethod: "",
    mappingHeldByInstitution: false,
    targetConditionConfirmed: false,
  });
  fileRows.value = [];
  if (fileInput.value) fileInput.value.value = "";
  report.value = null;
  completedBatchId.value = null;
  operationType.value = "info";
  operationMessage.value = "新批次已建立，请确认交接授权并选择文件。";
}

function nextDailyBatchSequence(): string {
  const prefix = `HOSP-${batchDate}-`;
  const batchIds = recentBatches.value.map((batch) => batch.batch_id);
  if (completedBatchId.value) batchIds.push(completedBatchId.value);
  const sequences = batchIds
    .filter((batchId) => batchId.startsWith(prefix))
    .map((batchId) => batchId.slice(prefix.length))
    .filter((suffix) => /^\d+$/.test(suffix))
    .map((suffix) => Number.parseInt(suffix, 10));
  return String((sequences.length ? Math.max(...sequences) : 0) + 1).padStart(2, "0");
}

function rowStatusLabel(row: IntakeFileRow): string {
  const labels: Record<FileStatus, string> = {
    pending: "待上传",
    uploading: "上传校验中",
    uploaded: "已完成上传校验",
    failed: "上传失败",
  };
  return labels[row.status];
}

function channelLabel(channel: InputChannel): string {
  return { video: "MP4 视频", white_light: "白光 JPEG", fluorescence: "ICG 荧光 JPEG", device_overlay: "设备叠加 JPEG", sequence: "帧序列" }[channel];
}

function admissionStageLabel(stage: string): string {
  return {
    quarantined: "隔离",
    engineering_analysis_ready: "工程分析就绪",
    target_registry_ready: "目标域来源就绪",
  }[stage] ?? stage;
}

function artifactAttachmentHealthy(attachment: HospitalIntakeArtifactAttachment): boolean {
  return (
    attachment.status === "completed" &&
    attachment.status_persisted &&
    attachment.attached_case_count === attachment.expected_case_count &&
    attachment.failures.length === 0
  );
}

function findingMessage(finding: IntakeFinding): string {
  const messages: Record<string, string> = {
    official_image_format_mismatch: "图像可读取，但文件不符合项目输入规范设备要求的 JPEG 规格。",
    official_image_resolution_mismatch: "图像可读取，但分辨率不符合项目输入规范设备的 3840x2160 规格。",
    official_video_resolution_mismatch: "视频可读取，但分辨率不符合项目输入规范设备的 3840x2160 规格。",
    official_video_rotation_present: "视频包含旋转元数据，分析前需要统一画面方向。",
    official_video_codec_unverified: "视频编码超出平台当前完成验证的编码集合。",
    ffprobe_unavailable: "当前环境无法使用 ffprobe，编码、码率和旋转信息检查能力受限。",
  };
  return messages[finding.code] ?? finding.message;
}

function formatBytes(value: number): string {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
</script>

<style scoped>
.intake-page {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.intake-page > :deep(.ov-page-header),
.intake-layout {
  width: min(100%, var(--ov-content-large));
  margin-right: auto;
  margin-left: auto;
}

.back-link,
.report-links a,
.case-link {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  padding: 7px 11px;
  background: var(--ov-bg-elevated);
  color: var(--ov-primary);
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.back-link :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.intake-layout {
  display: grid;
  grid-template-columns: minmax(640px, 1.35fr) minmax(400px, 0.65fr);
  gap: 24px;
  align-items: start;
  margin-top: 24px;
}

@media (max-width: 1100px) {
  .intake-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .intake-results {
    position: static;
    max-height: none;
    overflow-y: visible;
  }
}

.intake-form,
.intake-results {
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  padding: 20px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.intake-results {
  position: sticky;
  top: 72px;
  max-height: calc(100dvh - 92px);
  overflow-y: auto;
}

.section-header {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.section-header > div {
  display: flex;
  gap: 9px;
  align-items: center;
}

.section-header span {
  color: var(--ov-primary-strong);
  font-size: 12px;
  font-weight: 900;
}

.section-header h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
}

.section-header > strong {
  min-width: 0;
  max-width: 100%;
  border-radius: 5px;
  padding: 5px 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.section-header > strong.ready {
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.section-header > strong.pending {
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

.completion-state {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 11px;
  align-items: center;
  margin-top: 16px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  padding: 12px 14px;
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.completion-state :deep(.app-icon) {
  width: 34px;
  height: 34px;
}

.completion-state strong,
.completion-state span {
  display: block;
  overflow-wrap: anywhere;
}

.completion-state span {
  margin-top: 3px;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.form-grid,
.file-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.form-grid label,
.file-fields label {
  display: grid;
  gap: 5px;
}

.form-grid label > span,
.file-fields label > span,
.row-state > span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 800;
}

.form-grid input,
.form-grid select,
.file-fields input,
.file-fields select {
  width: 100%;
  min-height: 36px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 7px 9px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.form-grid input:disabled,
.form-grid select:disabled,
.file-fields input:disabled,
.file-fields select:disabled,
.confirmation-grid:disabled {
  cursor: not-allowed;
  opacity: 0.68;
}

.wide-field {
  grid-column: 1 / -1;
}

.confirmation-grid {
  display: grid;
  gap: 10px;
  margin: 18px 0 24px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 14px;
  background: var(--ov-bg-soft);
}

.confirmation-grid label {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  color: var(--ov-text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.confirmation-grid input {
  width: 16px;
  height: 16px;
  margin: 1px 0 0;
}

.file-heading {
  margin-top: 4px;
}

.hidden-file-input {
  display: none;
}

.file-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.file-row {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 12px;
  background: var(--ov-bg-soft);
}

.file-row-title {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) 34px;
  gap: 10px;
  align-items: center;
}

.file-row-title :deep(.app-icon) {
  width: 32px;
  height: 32px;
}

.file-row-title > div {
  min-width: 0;
}

.file-row-title strong,
.file-row-title small {
  display: block;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.file-row-title small {
  margin-top: 3px;
  color: var(--ov-text-muted);
  font-size: 11px;
}

.icon-button {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  background: var(--ov-bg-elevated);
  color: var(--ov-danger);
  cursor: pointer;
}

.icon-button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.row-state {
  display: grid;
  gap: 4px;
  align-content: center;
  min-height: 36px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-elevated);
}

.row-state strong {
  color: var(--ov-text-secondary);
  font-size: 12px;
}

.row-state.uploaded strong {
  color: var(--ov-success);
}

.row-state.failed strong,
.row-error {
  color: var(--ov-danger);
}

.checksum,
.row-error {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.checksum {
  color: var(--ov-text-muted);
}

.empty-files,
.empty-result {
  margin: 12px 0 0;
  border: 1px dashed var(--ov-border-strong);
  border-radius: 6px;
  padding: 18px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-muted);
  text-align: center;
}

.submit-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  margin-top: 16px;
}

.submit-row p {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.submit-row p.error {
  color: var(--ov-danger);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 14px 0;
}

.summary-grid div {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 9px;
  background: var(--ov-bg-soft);
}

.summary-grid dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.summary-grid dd {
  margin: 4px 0 0;
  color: var(--ov-text);
  font-size: 20px;
  font-weight: 900;
}

.summary-grid .success dd {
  color: var(--ov-success);
}

.summary-grid .danger dd {
  color: var(--ov-danger);
}

.report-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.artifact-attachment {
  display: grid;
  gap: 5px;
  min-width: 0;
  margin-bottom: 12px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 10px;
  background: var(--ov-bg-success);
  color: var(--ov-success);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.artifact-attachment.error {
  border-color: color-mix(in srgb, var(--ov-danger) 35%, var(--ov-border-subtle));
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.artifact-attachment strong,
.artifact-attachment p,
.artifact-attachment li,
.artifact-attachment code,
.artifact-attachment span {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.artifact-attachment p {
  margin: 0;
  color: var(--ov-text-secondary);
  line-height: 1.5;
}

.artifact-attachment ul {
  display: grid;
  gap: 4px;
  margin: 2px 0 0;
  padding-left: 18px;
}

.artifact-attachment li {
  line-height: 1.45;
}

.artifact-attachment code {
  margin-right: 7px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-weight: 800;
}

.artifact-attachment li span + span {
  margin-left: 7px;
}

.report-links a,
.case-link {
  min-height: 32px;
  padding: 5px 9px;
  font-size: 12px;
}

.result-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.result-list li {
  border: 1px solid var(--ov-border);
  border-left: 4px solid var(--ov-success);
  border-radius: 6px;
  padding: 11px;
  background: var(--ov-bg-soft);
}

.result-list li.quarantined {
  border-left-color: var(--ov-danger);
  background: var(--ov-bg-danger);
}

.result-title {
  display: flex;
  gap: 10px;
  align-items: start;
  justify-content: space-between;
}

.result-title strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.result-title span {
  color: var(--ov-success);
  font-size: 11px;
  font-weight: 900;
}

.quarantined .result-title span {
  color: var(--ov-danger);
}

.result-list dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px 12px;
  margin: 8px 0;
}

.result-list dl div {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 6px;
}

.result-list dt,
.result-list dd {
  margin: 0;
  font-size: 11px;
}

.result-list dt {
  color: var(--ov-text-muted);
}

.result-list dd {
  color: var(--ov-text-secondary);
  font-weight: 800;
}

.finding {
  margin: 5px 0 0;
  color: var(--ov-warning);
  font-size: 11px;
  line-height: 1.45;
}

.finding.error {
  color: var(--ov-danger);
}

.medical-boundary {
  margin: 12px 0 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 10px;
  background: var(--ov-bg-warning);
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.55;
}

.empty-result {
  display: grid;
  gap: 6px;
  justify-items: center;
}

.empty-result :deep(.app-icon) {
  width: 34px;
  height: 34px;
}

.empty-result p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
}

.recent-batches {
  margin-top: 12px;
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 10px;
}

.recent-batches summary {
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.recent-batches button {
  display: grid;
  gap: 3px;
  width: 100%;
  margin-top: 7px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.recent-batches button span {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.recent-batches button:disabled {
  cursor: wait;
  opacity: 0.58;
}
</style>
