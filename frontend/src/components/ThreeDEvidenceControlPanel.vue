<template>
  <section
    class="three-d-evidence-control"
    :class="`three-d-evidence-control--${presentation}`"
    aria-label="三维证据控制"
  >
    <input
      ref="cbctInput"
      class="three-d-evidence-control__file-input"
      data-testid="cbct-file-input"
      type="file"
      multiple
      accept=".dcm,.dicom,.nii,.nii.gz,.nrrd,.mha,.mhd"
      @change="handleCbctSelection"
    />
    <input
      ref="surfaceInput"
      class="three-d-evidence-control__file-input"
      data-testid="surface-file-input"
      type="file"
      accept=".stl,.glb"
      @change="handleSurfaceSelection"
    />

    <header v-if="presentation !== 'panel'" class="three-d-evidence-control__header">
      <div>
        <span>三维证据控制</span>
        <h2>CBCT 与表面模型建模</h2>
        <p>文件先写入受控后端区域，再以当前病例标识提交建模任务。</p>
      </div>
      <div class="three-d-evidence-control__status" :data-state="modelingStatus">
        <span>任务状态</span>
        <strong>{{ modelingStatusLabel }}</strong>
      </div>
    </header>

    <div class="three-d-evidence-control__layout">
      <section v-if="shows('imports')" class="three-d-evidence-control__section three-d-evidence-control__imports" aria-label="三维文件导入">
        <header>
          <div>
            <span>受控导入</span>
            <strong>病例 CBCT / STL / GLB</strong>
          </div>
          <small>上传完成后可提交建模。</small>
        </header>

        <div class="three-d-evidence-control__actions">
          <AppButton
            size="sm"
            icon="folder"
            :disabled="uploading || modelingActive"
            title="选择 CBCT 体数据文件"
            @click="openCbctPicker"
          >
            选择 CBCT
          </AppButton>
          <AppButton
            size="sm"
            icon="cube"
            :disabled="uploading || modelingActive"
            title="选择 STL 或 GLB 表面模型"
            @click="openSurfacePicker"
          >
            选择 STL / GLB
          </AppButton>
        </div>

        <ul v-if="importedAssets.length" class="three-d-evidence-control__asset-list" aria-label="已选择文件">
          <li v-for="asset in importedAssets" :key="asset.id" :data-upload-status="asset.uploadStatus">
            <div>
              <strong>{{ asset.name }}</strong>
              <small>{{ assetKindLabel(asset.kind) }} · {{ fileSizeLabel(asset.sizeBytes) }}</small>
            </div>
            <span>{{ assetUploadLabel(asset) }}</span>
          </li>
        </ul>
        <p v-else class="three-d-evidence-control__empty">尚未选择文件。CBCT 体数据与表面模型均会保留后端写入状态。</p>

        <label v-if="availableSourceKinds.length > 1" class="three-d-evidence-control__source-select">
          <span>建模来源</span>
          <select v-model="selectedSourceKind" data-testid="modeling-source-kind" :disabled="uploading || modelingActive">
            <option v-for="kind in availableSourceKinds" :key="kind" :value="kind">{{ assetKindLabel(kind) }}</option>
          </select>
        </label>

        <div class="three-d-evidence-control__actions">
          <AppButton
            variant="primary"
            size="sm"
            icon="check"
            data-testid="submit-modeling-job"
            :disabled="!canSubmitModeling"
            title="提交当前已写入后端的三维建模任务"
            @click="submitModelingJob"
          >
            提交建模
          </AppButton>
          <AppButton
            v-if="canCancelModeling"
            size="sm"
            icon="close"
            data-testid="cancel-modeling-job"
            :disabled="canceling"
            title="取消当前三维建模任务"
            @click="cancelModelingJob"
          >
            取消任务
          </AppButton>
          <AppButton
            v-if="jobId && pollingPaused"
            size="sm"
            icon="load"
            data-testid="refresh-modeling-job"
            :disabled="uploading || canceling"
            title="重新读取当前三维建模任务状态"
            @click="refreshModelingJob"
          >
            刷新状态
          </AppButton>
        </div>
        <p class="three-d-evidence-control__job-message" aria-live="polite">{{ jobMessage }}</p>
        <p v-if="errorMessage" class="three-d-evidence-control__error" role="alert">{{ errorMessage }}</p>
      </section>

      <section v-if="shows('tree')" class="three-d-evidence-control__section" aria-label="三维对象树">
        <header>
          <div>
            <span>病例对象树</span>
            <strong>输入、模型与复核对象</strong>
          </div>
          <small>{{ objectTree.length }} 项</small>
        </header>
        <ul class="three-d-evidence-control__tree">
          <li v-for="node in objectTree" :key="node.id">
            <span :class="`is-${node.tone}`" aria-hidden="true"></span>
            <div>
              <strong>{{ node.label }}</strong>
              <small>{{ node.detail }}</small>
            </div>
            <em>{{ node.status }}</em>
          </li>
        </ul>
      </section>

      <section v-if="shows('checks')" class="three-d-evidence-control__section" aria-label="三维建模检查">
        <header>
          <div>
            <span>建模检查</span>
            <strong>可追溯工程门控</strong>
          </div>
          <small>{{ completedCheckCount }} / {{ modelingChecks.length }} 项已记录</small>
        </header>
        <ul class="three-d-evidence-control__checks">
          <li v-for="check in modelingChecks" :key="check.label">
            <div>
              <strong>{{ check.label }}</strong>
              <small>{{ check.detail }}</small>
            </div>
            <b :class="`is-${check.state}`">{{ check.status }}</b>
          </li>
        </ul>
      </section>

      <section
        v-if="presentation !== 'sidebar' && shows('safety')"
        class="three-d-evidence-control__section three-d-evidence-control__safety"
        aria-label="三维安全边界"
      >
        <header>
          <div>
            <span>安全边界</span>
            <strong>{{ navigationStatusLabel }}</strong>
          </div>
          <small>{{ doctorReviewLabel }}</small>
        </header>
        <dl>
          <div><dt>空间状态</dt><dd>{{ registrationStatusLabel }}</dd></div>
          <div><dt>回退模式</dt><dd>{{ fallbackModeLabel }}</dd></div>
          <div><dt>当前级别</dt><dd>{{ navigationLevelLabel }}</dd></div>
        </dl>
        <p>{{ safetyBoundary }}</p>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import { apiClient, type BackendJob } from "@/services/apiClient";
import type { ThreeDEvidence, ThreeDSceneManifestV2 } from "@/types/case";
import { abortableDelay, isAbortError } from "@/utils/abortableDelay";

type AssetKind = "cbct" | "surface";
type UploadStatus = "uploading" | "uploaded" | "failed";
type ModelingStatus = "idle" | BackendJob["status"] | "segmentation_required";
type ControlSection = "imports" | "tree" | "checks" | "safety";

interface ImportedAsset {
  id: string;
  kind: AssetKind;
  name: string;
  sizeBytes: number;
  uploadStatus: UploadStatus;
  serverPath?: string;
  errorMessage?: string;
}

interface TreeNode {
  id: string;
  label: string;
  detail: string;
  status: string;
  tone: "ready" | "pending" | "guarded";
}

interface ModelingCheck {
  label: string;
  detail: string;
  status: string;
  state: "ready" | "pending" | "guarded";
}

interface PollingSession {
  caseId: string;
  generation: number;
  controller: AbortController;
}

const props = withDefaults(defineProps<{
  caseId: string;
  evidence?: ThreeDEvidence | null;
  presentation?: "standard" | "sidebar" | "panel";
  sections?: ControlSection[];
}>(), {
  evidence: null,
  presentation: "standard",
  sections: () => [],
});

const emit = defineEmits<{
  evidencePersisted: [];
}>();

const cbctInput = ref<HTMLInputElement | null>(null);
const surfaceInput = ref<HTMLInputElement | null>(null);
const importedAssets = ref<ImportedAsset[]>([]);
const selectedSourceKind = ref<AssetKind>("cbct");
const localEvidence = ref<ThreeDEvidence | null>(null);
const modelingStatus = ref<ModelingStatus>("idle");
const jobId = ref("");
const jobMessage = ref("请选择病例 CBCT 或 STL / GLB 文件，完成受控上传后提交建模。");
const errorMessage = ref("");
const pollingPaused = ref(false);
const canceling = ref(false);
let pollingGeneration = 0;
let pollingController: AbortController | null = null;
let uploadGeneration = 0;

function shows(section: ControlSection): boolean {
  return props.sections.length === 0 || props.sections.includes(section);
}

const effectiveEvidence = computed(() => localEvidence.value ?? props.evidence ?? null);
const uploading = computed(() => importedAssets.value.some((asset) => asset.uploadStatus === "uploading"));
const modelingActive = computed(() => ["queued", "running"].includes(modelingStatus.value));
const canCancelModeling = computed(() => Boolean(jobId.value) && modelingActive.value);
const availableSourceKinds = computed<AssetKind[]>(() => {
  const kinds: AssetKind[] = [];
  if (uploadedAssets("cbct").length) kinds.push("cbct");
  if (uploadedAssets("surface").length) kinds.push("surface");
  return kinds;
});
const canSubmitModeling = computed(
  () => !uploading.value && !modelingActive.value && !canceling.value && Boolean(selectedSourceAsset()),
);
const modelingStatusLabel = computed(() => {
  const labels: Record<ModelingStatus, string> = {
    idle: "等待建模",
    queued: "已排队",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
    canceled: "已取消",
    segmentation_required: "需要分割标签",
  };
  return labels[modelingStatus.value];
});
const sceneManifest = computed<ThreeDSceneManifestV2 | null>(() => {
  const value = effectiveEvidence.value?.scene_manifest_v2;
  return isRecord(value) ? (value as ThreeDSceneManifestV2) : null;
});
const objectTree = computed<TreeNode[]>(() => {
  const nodes: TreeNode[] = [
    {
      id: "case",
      label: "当前病例",
      detail: props.caseId,
      status: "已关联",
      tone: "ready",
    },
  ];

  for (const asset of importedAssets.value) {
    nodes.push({
      id: asset.id,
      label: asset.name,
      detail: assetKindLabel(asset.kind),
      status: assetUploadLabel(asset),
      tone: asset.uploadStatus === "uploaded" ? "ready" : asset.uploadStatus === "failed" ? "guarded" : "pending",
    });
  }

  for (const node of sceneManifest.value?.nodes ?? []) {
    const id = textValue(node.id) || `scene-${nodes.length}`;
    if (nodes.some((item) => item.id === id)) continue;
    nodes.push({
      id,
      label: textValue(node.name) || sceneNodeRoleLabel(textValue(node.role)),
      detail: sceneNodeTypeLabel(textValue(node.type)),
      status: reviewLabel(textValue(node.review_status)) || "待复核",
      tone: textValue(node.review_status) === "reviewed" ? "ready" : "guarded",
    });
  }

  if (nodes.length === 1) {
    nodes.push({
      id: "awaiting-input",
      label: "三维输入",
      detail: "等待 CBCT 或表面模型上传",
      status: "待输入",
      tone: "pending",
    });
  }
  return nodes;
});
const modelingChecks = computed<ModelingCheck[]>(() => {
  const evidence = effectiveEvidence.value;
  const hasUploadedInput = importedAssets.value.some((asset) => asset.uploadStatus === "uploaded");
  const hasSurface = Boolean(evidence?.model_path || uploadedAssets("surface").length);
  const segmentationStatus = textValue(evidence?.segmentation_review_status);
  const coordinateSpace = textValue(evidence?.coordinate_space);
  return [
    {
      label: "病例关联",
      detail: props.caseId ? "建模任务会以当前病例 ID 写入证据。" : "缺少病例标识。",
      status: props.caseId ? "已关联" : "缺少病例",
      state: props.caseId ? "ready" : "guarded",
    },
    {
      label: "输入写入",
      detail: hasUploadedInput ? "至少一个输入已写入受控后端区域。" : "等待文件上传。",
      status: hasUploadedInput ? "已写入" : "待上传",
      state: hasUploadedInput ? "ready" : "pending",
    },
    {
      label: "表面模型",
      detail: hasSurface ? "已有表面模型或已提交表面输入。" : "CBCT 需完成建模后才能提供表面。",
      status: hasSurface ? "可检查" : "待生成",
      state: hasSurface ? "ready" : "pending",
    },
    {
      label: "分割复核",
      detail: segmentationStatus ? reviewLabel(segmentationStatus) : "尚未记录医生分割复核。",
      status: segmentationStatus ? reviewLabel(segmentationStatus) : "待复核",
      state: segmentationStatus === "reviewed" || segmentationStatus === "accepted" ? "ready" : "guarded",
    },
    {
      label: "坐标与配准",
      detail: coordinateSpace ? `坐标系：${coordinateSpaceLabel(coordinateSpace)}` : "坐标系待记录。",
      status: registrationStatusLabel.value,
      state: navigationReady.value ? "ready" : "guarded",
    },
  ];
});
const completedCheckCount = computed(() => modelingChecks.value.filter((check) => check.state === "ready").length);
const navigationReady = computed(() => asBoolean(effectiveEvidence.value?.navigation_ready));
const navigationLevelLabel = computed(() => textValue(effectiveEvidence.value?.navigation_level) || "L0");
const registrationStatusLabel = computed(() => {
  const value = textValue(effectiveEvidence.value?.registration_status).toLowerCase();
  if (navigationReady.value && value === "registered") return "已记录工程配准";
  if (value === "registered") return "配准已记录，仍待安全检查";
  return "未配准参考";
});
const navigationStatusLabel = computed(() => (navigationReady.value ? `${navigationLevelLabel.value} 工程状态待复核` : "L0 未配准参考"));
const doctorReviewLabel = computed(() => reviewLabel(textValue(effectiveEvidence.value?.doctor_review_status)) || "医生复核待完成");
const fallbackModeLabel = computed(() => textValue(effectiveEvidence.value?.fallback_mode) || "unregistered_3d_reference");
const safetyBoundary = computed(
  () =>
    textValue(effectiveEvidence.value?.boundary_note) ||
    textValue(effectiveEvidence.value?.data_boundary) ||
    "三维内容用于工程检查与医生复核；缺少坐标配准、误差记录和医生复核时保持未配准参考。",
);

watch(
  () => props.caseId,
  () => resetForCase(),
);

watch(
  () => props.evidence,
  (evidence) => {
    localEvidence.value = evidence ?? null;
  },
  { deep: true },
);

watch(availableSourceKinds, (kinds) => {
  if (!kinds.length) return;
  if (!kinds.includes(selectedSourceKind.value)) selectedSourceKind.value = kinds[0];
});

onBeforeUnmount(() => invalidatePolling());

function openCbctPicker() {
  cbctInput.value?.click();
}

function openSurfacePicker() {
  surfaceInput.value?.click();
}

async function handleCbctSelection(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  if (!files.length || uploading.value || modelingActive.value) return;
  await uploadFiles(files, "cbct");
}

async function handleSurfaceSelection(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  const file = files[0];
  if (!file || uploading.value || modelingActive.value) return;
  await uploadFiles([file], "surface");
}

async function uploadFiles(files: File[], kind: AssetKind) {
  const uploadCaseId = props.caseId;
  const generation = ++uploadGeneration;
  errorMessage.value = "";
  jobMessage.value = "正在将文件写入受控后端区域。";
  const records = files.map((file, index) => createAsset(file, kind, index));
  importedAssets.value = [...importedAssets.value.filter((asset) => asset.kind !== kind), ...records];
  const results = await Promise.allSettled(files.map((file) => apiClient.uploadThreeDAsset(file)));
  if (generation !== uploadGeneration || uploadCaseId !== props.caseId) return;
  for (const [index, result] of results.entries()) {
    const assetId = records[index].id;
    if (result.status === "fulfilled") {
      replaceAsset(assetId, {
        uploadStatus: "uploaded",
        serverPath: result.value.path,
      });
    } else {
      replaceAsset(assetId, {
        uploadStatus: "failed",
        errorMessage: errorMessageFromUnknown(result.reason, "文件写入失败。"),
      });
    }
  }
  const failed = records.filter((record) => importedAssets.value.find((asset) => asset.id === record.id)?.uploadStatus === "failed");
  if (failed.length) {
    errorMessage.value = `${failed.length} 个文件未能写入后端。请检查格式、网络和服务状态。`;
    jobMessage.value = "存在上传失败文件，成功写入的文件仍可用于建模。";
  } else {
    selectedSourceKind.value = kind;
    jobMessage.value = "文件已写入后端，可提交三维建模任务。";
  }
}

async function submitModelingJob() {
  const source = selectedSourceAsset();
  if (!source?.serverPath) {
    errorMessage.value = "请先完成至少一个 CBCT 或 STL / GLB 文件的后端上传。";
    return;
  }
  const polling = beginPolling(props.caseId);
  errorMessage.value = "";
  pollingPaused.value = false;
  modelingStatus.value = "queued";
  jobMessage.value = "正在提交三维建模任务。";
  try {
    const started = await apiClient.startThreeDModelingJob({
      source_path: source.serverPath,
      source_paths: source.kind === "cbct" ? uploadedAssets("cbct").flatMap((asset) => (asset.serverPath ? [asset.serverPath] : [])) : [source.serverPath],
      source_role: source.kind === "cbct" ? "volume" : "surface",
      source_original_filename: source.name,
      case_id: props.caseId,
      dataset_id: "frontend_case_import",
      label_value: 1,
      decimation_step: 1,
    });
    if (!isPollingCurrent(polling)) return;
    jobId.value = started.job_id;
    await pollModelingJob(started.job_id, polling);
  } catch (error) {
    if (!isPollingCurrent(polling) || isAbortError(error)) return;
    modelingStatus.value = "failed";
    errorMessage.value = errorMessageFromUnknown(error, "三维建模任务提交失败。")
    jobMessage.value = "建模任务未能提交。";
  } finally {
    if (pollingController === polling.controller) pollingController = null;
  }
}

async function refreshModelingJob() {
  if (!jobId.value || uploading.value || canceling.value) return;
  const polling = beginPolling(props.caseId);
  pollingPaused.value = false;
  errorMessage.value = "";
  jobMessage.value = "正在读取三维建模任务状态。";
  try {
    await pollModelingJob(jobId.value, polling, 1);
  } catch (error) {
    if (!isPollingCurrent(polling) || isAbortError(error)) return;
    errorMessage.value = errorMessageFromUnknown(error, "三维建模任务状态读取失败。")
  } finally {
    if (pollingController === polling.controller) pollingController = null;
  }
}

async function cancelModelingJob() {
  if (!jobId.value || canceling.value) return;
  const polling = beginPolling(props.caseId);
  canceling.value = true;
  pollingPaused.value = false;
  errorMessage.value = "";
  jobMessage.value = "正在取消三维建模任务。";
  try {
    const job = await apiClient.cancelThreeDModelingJob(jobId.value);
    if (!isPollingCurrent(polling)) return;
    if (["queued", "running"].includes(job.status)) {
      modelingStatus.value = job.status;
      jobMessage.value = "取消请求已提交，正在等待后端确认。";
      await pollModelingJob(job.job_id, polling);
    } else {
      applyJobState(job);
    }
  } catch (error) {
    if (!isPollingCurrent(polling) || isAbortError(error)) return;
    errorMessage.value = errorMessageFromUnknown(error, "三维建模任务取消失败。")
  } finally {
    canceling.value = false;
    if (pollingController === polling.controller) pollingController = null;
  }
}

async function pollModelingJob(targetJobId: string, polling: PollingSession, maxAttempts = 60) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (!isPollingCurrent(polling)) return;
    const job = await apiClient.getThreeDModelingJob(targetJobId);
    if (!isPollingCurrent(polling)) return;
    applyJobState(job);
    if (!isActiveJob(job)) return;
    if (attempt + 1 < maxAttempts) await abortableDelay(1000, polling.controller.signal);
  }
  if (!isPollingCurrent(polling)) return;
  pollingPaused.value = true;
  jobMessage.value = "后端任务仍在运行，自动轮询已暂停；请刷新状态或取消任务。";
}

function applyJobState(job: BackendJob) {
  const result = isRecord(job.result) ? job.result : {};
  const modelingOutcome = textValue(result.modeling_status);
  modelingStatus.value = job.status === "completed" && modelingOutcome === "segmentation_required" ? "segmentation_required" : job.status;
  const progressMessage = textValue(job.progress?.message);
  jobMessage.value = textValue(result.message) || progressMessage || textValue(job.error) || statusMessage(modelingStatus.value);
  if (job.status === "failed") errorMessage.value = textValue(job.error) || "三维建模任务失败。";

  const evidence = result.three_d_evidence;
  if (isRecord(evidence)) localEvidence.value = evidence as ThreeDEvidence;

  const persistence = result.case_persistence;
  if (isRecord(persistence) && persistence.status === "persisted") {
    emit("evidencePersisted");
  }
}

function selectedSourceAsset(): ImportedAsset | undefined {
  const primary = uploadedAssets(selectedSourceKind.value)[0];
  if (primary) return primary;
  return uploadedAssets("surface")[0] ?? uploadedAssets("cbct")[0];
}

function uploadedAssets(kind: AssetKind): ImportedAsset[] {
  return importedAssets.value.filter((asset) => asset.kind === kind && asset.uploadStatus === "uploaded" && Boolean(asset.serverPath));
}

function createAsset(file: File, kind: AssetKind, index: number): ImportedAsset {
  return {
    id: `${kind}-${Date.now()}-${index}-${file.name}-${file.size}`,
    kind,
    name: file.name,
    sizeBytes: file.size,
    uploadStatus: "uploading",
  };
}

function replaceAsset(id: string, update: Partial<ImportedAsset>) {
  importedAssets.value = importedAssets.value.map((asset) => (asset.id === id ? { ...asset, ...update } : asset));
}

function resetForCase() {
  uploadGeneration += 1;
  invalidatePolling();
  importedAssets.value = [];
  localEvidence.value = null;
  modelingStatus.value = "idle";
  jobId.value = "";
  jobMessage.value = "病例已切换。请选择该病例的三维输入。";
  errorMessage.value = "";
  pollingPaused.value = false;
  canceling.value = false;
}

function beginPolling(caseId: string): PollingSession {
  invalidatePolling();
  const controller = new AbortController();
  pollingController = controller;
  return { caseId, generation: pollingGeneration, controller };
}

function invalidatePolling() {
  pollingGeneration += 1;
  pollingController?.abort();
  pollingController = null;
}

function isPollingCurrent(polling: PollingSession): boolean {
  return polling.caseId === props.caseId && polling.generation === pollingGeneration && !polling.controller.signal.aborted;
}

function isActiveJob(job: BackendJob): boolean {
  return job.status === "queued" || job.status === "running";
}

function assetKindLabel(kind: AssetKind): string {
  return kind === "cbct" ? "CBCT 体数据" : "表面模型";
}

function assetUploadLabel(asset: ImportedAsset): string {
  if (asset.uploadStatus === "uploaded") return "已写入后端";
  if (asset.uploadStatus === "uploading") return "正在上传";
  return asset.errorMessage || "上传失败";
}

function fileSizeLabel(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return "大小未记录";
  if (sizeBytes >= 1024 * 1024) return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`;
  if (sizeBytes >= 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${sizeBytes} B`;
}

function statusMessage(status: ModelingStatus): string {
  const messages: Record<ModelingStatus, string> = {
    idle: "等待建模。",
    queued: "任务已排队。",
    running: "正在执行三维建模。",
    completed: "三维建模已完成。",
    failed: "三维建模未完成。",
    canceled: "三维建模任务已取消。",
    segmentation_required: "体数据已检查，仍需分割标签或医生复核表面。",
  };
  return messages[status];
}

function reviewLabel(value: string): string {
  const labels: Record<string, string> = {
    accepted: "已接受",
    reviewed: "已复核",
    recorded: "已记录",
    review_required: "待复核",
    not_reviewed: "未复核",
    pending: "待复核",
    public_dataset_annotation_not_case_reviewed: "公开标注待复核",
    public_dataset_annotation_not_case_accepted: "公开标注待接受",
  };
  return labels[value.toLowerCase()] || "状态待确认";
}

function sceneNodeTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    volume: "体数据",
    model: "表面模型",
    segmentation: "分割结果",
    markup: "复核标注",
    transform: "坐标变换",
  };
  return labels[value.toLowerCase()] || "场景对象";
}

function sceneNodeRoleLabel(value: string): string {
  const labels: Record<string, string> = {
    uploaded_surface_reference: "上传表面参考模型",
    cbct_volume: "CBCT 体数据",
    segmentation_surface: "分割表面模型",
    review_markup: "医生复核标注",
  };
  return labels[value.toLowerCase()] || "三维证据对象";
}

function coordinateSpaceLabel(value: string): string {
  const labels: Record<string, string> = {
    uploaded_surface_file_space: "上传表面模型坐标系",
    cbct_lps_mm: "CBCT LPS 毫米坐标系",
    phantom_reference_mm: "仿体参考毫米坐标系",
    three_d_reference_panel: "三维参考面板坐标系",
    video_keyframe_reference: "视频关键帧参考坐标系",
    camera_optical: "相机光学坐标系",
  };
  return labels[value.toLowerCase()] || "已记录坐标系";
}

function asBoolean(value: unknown): boolean {
  return value === true || (typeof value === "string" && ["true", "1", "ready"].includes(value.toLowerCase()));
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function errorMessageFromUnknown(error: unknown, fallback: string): string {
  const body = (error as { body?: unknown } | null)?.body;
  if (isRecord(body)) {
    const detail = body.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (isRecord(detail)) return textValue(detail.message) || textValue(detail.code) || fallback;
  }
  return error instanceof Error && error.message ? error.message : fallback;
}
</script>

<style scoped>
.three-d-evidence-control {
  --three-d-title-size: 18px;
  --three-d-section-size: 15px;
  --three-d-body-size: 13px;
  --three-d-meta-size: 12px;
  width: min(100%, var(--ov-content-wide));
  margin: 0 auto;
  border-top: 1px solid var(--ov-border);
  border-bottom: 1px solid var(--ov-border);
  background: var(--ov-bg-panel);
}

.three-d-evidence-control__file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}

.three-d-evidence-control__header,
.three-d-evidence-control__section > header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.three-d-evidence-control__header {
  padding: 18px 20px;
  border-bottom: 1px solid var(--ov-border);
}

.three-d-evidence-control__header > div:first-child,
.three-d-evidence-control__section > header > div,
.three-d-evidence-control__section > header {
  min-width: 0;
}

.three-d-evidence-control__section > header > div {
  display: grid;
  gap: 2px;
}

.three-d-evidence-control__header span,
.three-d-evidence-control__section header span,
.three-d-evidence-control__section header small,
.three-d-evidence-control__header p {
  margin: 0;
  color: var(--ov-text-muted);
  font-size: var(--three-d-meta-size);
  line-height: 1.45;
}

.three-d-evidence-control__header h2,
.three-d-evidence-control__section header strong {
  margin: 3px 0 4px;
  color: var(--ov-text);
  font-size: var(--three-d-section-size);
  line-height: 1.35;
}

.three-d-evidence-control__header h2 {
  font-size: var(--three-d-title-size);
}

.three-d-evidence-control__status {
  display: grid;
  flex: 0 0 min(210px, 34%);
  gap: 3px;
  padding: 8px 10px;
  border-left: 3px solid var(--ov-border-strong);
  color: var(--ov-text-muted);
}

.three-d-evidence-control__status strong {
  color: var(--ov-text);
  font-size: var(--three-d-section-size);
  line-height: 1.35;
}

.three-d-evidence-control__status[data-state="completed"] { border-left-color: var(--ov-success); }
.three-d-evidence-control__status[data-state="failed"],
.three-d-evidence-control__status[data-state="segmentation_required"] { border-left-color: var(--ov-warning); }
.three-d-evidence-control__status[data-state="canceled"] { border-left-color: var(--ov-text-muted); }

.three-d-evidence-control__layout {
  display: grid;
  grid-template-columns: minmax(260px, 1.08fr) minmax(220px, 0.9fr) minmax(240px, 1fr) minmax(240px, 1fr);
}

.three-d-evidence-control__section {
  display: grid;
  gap: 13px;
  min-width: 0;
  padding: 18px;
  border-right: 1px solid var(--ov-border);
}

.three-d-evidence-control__section:last-child { border-right: 0; }
.three-d-evidence-control__section > header small { text-align: right; }

.three-d-evidence-control__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.three-d-evidence-control__asset-list,
.three-d-evidence-control__tree,
.three-d-evidence-control__checks {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.three-d-evidence-control__asset-list li,
.three-d-evidence-control__tree li,
.three-d-evidence-control__checks li {
  display: grid;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 8px 0;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.three-d-evidence-control__asset-list li,
.three-d-evidence-control__checks li {
  grid-template-columns: minmax(0, 1fr) minmax(84px, 112px);
}

.three-d-evidence-control__tree li {
  grid-template-columns: 10px minmax(0, 1fr) minmax(84px, 112px);
}

.three-d-evidence-control__asset-list li > div,
.three-d-evidence-control__tree li > div,
.three-d-evidence-control__checks li > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.three-d-evidence-control__asset-list strong,
.three-d-evidence-control__tree strong,
.three-d-evidence-control__checks strong {
  color: var(--ov-text);
  font-size: var(--three-d-body-size);
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.three-d-evidence-control__asset-list small,
.three-d-evidence-control__tree small,
.three-d-evidence-control__checks small,
.three-d-evidence-control__empty,
.three-d-evidence-control__job-message {
  color: var(--ov-text-muted);
  font-size: var(--three-d-meta-size);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.three-d-evidence-control__asset-list span,
.three-d-evidence-control__tree em,
.three-d-evidence-control__checks b {
  color: var(--ov-text-secondary);
  font-size: var(--three-d-meta-size);
  font-style: normal;
  font-weight: 700;
  line-height: 1.35;
  text-align: end;
  overflow-wrap: anywhere;
}

.three-d-evidence-control__asset-list li[data-upload-status="uploaded"] span,
.three-d-evidence-control__checks b.is-ready { color: var(--ov-success); }
.three-d-evidence-control__asset-list li[data-upload-status="failed"] span,
.three-d-evidence-control__checks b.is-guarded { color: var(--ov-warning-text); }

.three-d-evidence-control__tree li > span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ov-border-strong);
}

.three-d-evidence-control__tree li > span.is-ready { background: var(--ov-success); }
.three-d-evidence-control__tree li > span.is-guarded { background: var(--ov-warning); }

.three-d-evidence-control__source-select {
  display: grid;
  gap: 5px;
  color: var(--ov-text-secondary);
  font-size: var(--three-d-meta-size);
  font-weight: 700;
}

.three-d-evidence-control__source-select select {
  min-width: 0;
  min-height: var(--ov-control-height-sm);
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 9px;
  color: var(--ov-text);
  background: var(--ov-bg-control);
  font: inherit;
  font-size: var(--three-d-body-size);
}

.three-d-evidence-control__job-message,
.three-d-evidence-control__error,
.three-d-evidence-control__safety p {
  margin: 0;
}

.three-d-evidence-control__error { color: var(--ov-danger); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }

.three-d-evidence-control__safety {
  background: var(--ov-bg-subtle);
}

.three-d-evidence-control__safety dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.three-d-evidence-control__safety dl > div {
  display: grid;
  grid-template-columns: minmax(80px, 0.7fr) minmax(0, 1.3fr);
  gap: 8px;
  align-items: baseline;
}

.three-d-evidence-control__safety dt,
.three-d-evidence-control__safety dd {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.three-d-evidence-control__safety dt { color: var(--ov-text-muted); }
.three-d-evidence-control__safety dd { color: var(--ov-text); font-weight: 700; }
.three-d-evidence-control__safety p { color: var(--ov-warning-text); font-size: 12px; line-height: 1.62; overflow-wrap: anywhere; }

.three-d-evidence-control--sidebar {
  width: 100%;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ov-border);
  border-radius: var(--ov-radius-surface);
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.three-d-evidence-control--sidebar .three-d-evidence-control__header {
  padding: 16px;
  background: var(--ov-bg-elevated);
}

.three-d-evidence-control--sidebar .three-d-evidence-control__header h2 {
  font-size: 17px;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__header p {
  max-width: 38ch;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__status {
  flex-basis: min(132px, 38%);
  padding: 7px 8px;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__layout {
  grid-template-columns: 1fr;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__section {
  gap: 10px;
  padding: 14px 16px;
  border-right: 0;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.three-d-evidence-control--sidebar .three-d-evidence-control__section:last-child {
  border-bottom: 0;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__section > header small {
  text-align: left;
}

.three-d-evidence-control--sidebar .three-d-evidence-control__asset-list li,
.three-d-evidence-control--sidebar .three-d-evidence-control__tree li,
.three-d-evidence-control--sidebar .three-d-evidence-control__checks li {
  padding: 7px 0;
}

.three-d-evidence-control--panel {
  width: 100%;
  height: 100%;
  margin: 0;
  border: 0;
  background: transparent;
}

.three-d-evidence-control--panel .three-d-evidence-control__layout {
  display: block;
  height: 100%;
}

.three-d-evidence-control--panel .three-d-evidence-control__section {
  height: 100%;
  padding: 14px;
  border: 0;
}

.three-d-evidence-control--panel .three-d-evidence-control__section > header small {
  text-align: left;
}

@media (max-width: 1380px) {
  .three-d-evidence-control__layout { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .three-d-evidence-control__section:nth-child(2) { border-right: 0; }
  .three-d-evidence-control__section:nth-child(-n + 2) { border-bottom: 1px solid var(--ov-border); }
}
</style>
