<template>
  <AppPageShell class="manual-annotation-page" width="wide">
    <header class="annotation-page-header">
      <div class="ov-title-lead annotation-title-lead">
        <AppIcon name="brush" variant="badge" tone="amber" />
        <div class="annotation-title-copy">
          <span class="page-kicker">医生标注工作台</span>
          <h1>病灶人工标注与医生复核</h1>
          <p>像素级标注、版本审计与训练准入</p>
        </div>
      </div>
      <form class="case-loader" @submit.prevent="loadCaseWorkspace">
        <label>
          <span>病例 ID</span>
          <input
            v-model="caseIdInput"
            type="text"
            placeholder="输入病例 ID"
            :disabled="busy || hasUnsavedChanges"
            :title="hasUnsavedChanges ? '请先保存或放弃当前修改' : '输入需要载入的病例 ID'"
          />
        </label>
        <AppButton
          type="submit"
          variant="secondary"
          size="sm"
          icon="load"
          :disabled="busy || hasUnsavedChanges || !caseIdInput.trim()"
          :title="hasUnsavedChanges ? '请先保存或放弃当前修改' : '载入病例标注工作区'"
        >
          {{ loadingCase ? "正在载入" : "载入病例" }}
        </AppButton>
        <AppButton
          type="button"
          variant="secondary"
          size="sm"
          icon="video"
          :disabled="busy || hasUnsavedChanges"
          :title="hasUnsavedChanges ? '请先保存或放弃当前修改' : '载入 OFDVDnet 公开代理视频的可标注关键帧'"
          @click="loadOfdvdnetDemo"
        >
          OFDVDnet 示例
        </AppButton>
      </form>
    </header>

    <div v-if="message" class="workspace-message" :class="`workspace-message--${messageTone}`" role="status">
      <AppIcon :name="messageTone === 'error' ? 'alert' : 'check'" />
      <span>{{ message }}</span>
    </div>

    <section v-if="!store.currentCase" class="annotation-empty-page">
      <AppIcon name="case" variant="badge" tone="cyan" />
      <h2>尚未载入病例</h2>
      <p>病例档案中的 JPEG、MP4 关键帧和模型候选区会在载入后进入标注来源列表。</p>
      <RouterLink to="/cases">打开病例档案</RouterLink>
    </section>

    <section v-else class="annotation-workspace">
      <aside class="source-panel" aria-label="标注来源">
        <header class="panel-heading">
          <div>
            <span>当前病例</span>
            <strong>{{ store.currentCase.title }}</strong>
            <small>{{ store.currentCase.case_id }}</small>
          </div>
          <button
            type="button"
            title="刷新标注来源"
            :disabled="busy || hasUnsavedChanges"
            @click="refreshWorkspace"
          >
            <AppIcon name="load" />
          </button>
        </header>

        <div class="source-tabs" role="tablist" aria-label="来源类型筛选">
          <button
            v-for="filter in sourceFilters"
            :key="filter.value"
            type="button"
            :class="{ selected: sourceFilter === filter.value }"
            :disabled="hasUnsavedChanges && sourceFilter !== filter.value"
            @click="sourceFilter = filter.value"
          >
            {{ filter.label }}
            <span>{{ sourceCount(filter.value) }}</span>
          </button>
        </div>

        <div class="source-list" aria-live="polite">
          <button
            v-for="source in filteredSources"
            :key="sourceKey(source)"
            type="button"
            class="source-row"
            :class="{ selected: sourceKey(source) === selectedSourceKey }"
            :disabled="hasUnsavedChanges && sourceKey(source) !== selectedSourceKey"
            :title="hasUnsavedChanges && sourceKey(source) !== selectedSourceKey ? '请先保存或放弃当前修改' : sourceTitle(source)"
            @click="selectSource(source)"
          >
            <span class="source-row__icon"><AppIcon :name="sourceIcon(source.source_type)" /></span>
            <span class="source-row__body">
              <strong>{{ sourceTitle(source) }}</strong>
              <small>{{ sourceMeta(source) }}</small>
              <span v-if="annotationForSource(source)" class="source-row__status">
                {{ statusLabel(annotationForSource(source)?.status) }}
              </span>
            </span>
          </button>
          <div v-if="!filteredSources.length" class="source-list__empty">
            <AppIcon name="file" />
            <span>当前筛选下暂无可标注来源</span>
          </div>
        </div>
      </aside>

      <section class="canvas-panel">
        <ManualAnnotationCanvas
          :key="canvasKey"
          :source-url="sourcePreviewUrl"
          :source-title="selectedSource ? sourceTitle(selectedSource) : ''"
          :original-width="selectedSource?.original_width"
          :original-height="selectedSource?.original_height"
          :geometry="geometry"
          :overlay-color="selectedLabelMeta.color"
          :reference-layers="referenceLayers"
          :disabled="annotationLocked || saving"
          :disabled-reason="canvasDisabledReason"
          @geometry-change="handleGeometryChange"
          @source-ready="handleSourceReady"
        />
      </section>

      <aside class="annotation-control-panel" aria-label="标注记录与提交">
        <section class="control-section">
          <header>
            <span>标注标签</span>
            <strong>{{ selectedLabelMeta.label }}</strong>
          </header>
          <div class="label-options" role="radiogroup" aria-label="标注标签">
            <button
              v-for="option in labelOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedLabel === option.value"
              :class="{ selected: selectedLabel === option.value }"
              :disabled="busy"
              :title="option.label"
              @click="selectLabel(option.value)"
            >
              <span class="label-swatch" :style="{ background: option.color }" />
              <span>{{ option.label }}</span>
            </button>
          </div>
        </section>

        <section class="control-section annotation-record">
          <header>
            <span>标注记录</span>
            <strong>{{ activeAnnotation ? statusLabel(activeAnnotation.status) : "新草稿" }}</strong>
          </header>
          <dl>
            <div>
              <dt>记录 ID</dt>
              <dd>{{ activeAnnotation?.annotation_id || "保存后生成" }}</dd>
            </div>
            <div>
              <dt>当前版本</dt>
              <dd>{{ activeAnnotation ? `v${activeAnnotation.current_version}` : "未保存" }}</dd>
            </div>
            <div>
              <dt>训练准入</dt>
              <dd :class="{ eligible: activeAnnotation?.training_eligible }">
                {{ activeAnnotation?.training_eligible ? "已准入" : "尚未准入" }}
              </dd>
            </div>
            <div>
              <dt>样本权重</dt>
              <dd>{{ activeAnnotation ? activeAnnotation.sample_weight.toFixed(2) : "0.00" }}</dd>
            </div>
            <div v-if="activeAnnotation?.training_exclusion_reason">
              <dt>隔离原因</dt>
              <dd>{{ trainingExclusionLabel(activeAnnotation.training_exclusion_reason) }}</dd>
            </div>
          </dl>
          <label class="notes-field">
            <span>标注备注</span>
            <textarea
              v-model="notes"
              rows="4"
              :disabled="annotationLocked || saving"
              placeholder="记录病灶边界判断依据"
              @input="notesDirty = true"
            />
          </label>
        </section>

        <section class="control-section actions-section">
          <header>
            <span>写入操作</span>
            <strong>{{ hasUnsavedChanges ? "存在未保存修改" : "已同步" }}</strong>
          </header>
          <AppButton
            variant="primary"
            icon="save"
            block
            :disabled="saveDisabled"
            :title="saveDisabledReason"
            @click="saveDraft"
          >
            {{ saving ? "正在保存" : activeAnnotation ? "保存新版本" : "保存草稿" }}
          </AppButton>
          <div class="secondary-actions">
            <AppButton
              variant="secondary"
              size="sm"
              icon="undo"
              :disabled="busy || !hasUnsavedChanges"
              title="放弃未保存修改"
              @click="discardUnsavedChanges"
            >
              放弃修改
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="review"
              :disabled="submitDisabled"
              :title="submitDisabledReason"
              @click="submitForReview"
            >
              提交复核
            </AppButton>
          </div>
          <AppButton
            v-if="activeAnnotation?.status === 'draft'"
            variant="ghost"
            size="sm"
            icon="trash"
            block
            :disabled="busy"
            title="删除本人尚未提交的草稿"
            @click="deleteDraft"
          >
            删除草稿
          </AppButton>
        </section>

        <section v-if="activeAnnotation?.status === 'submitted'" class="control-section review-actions">
          <header>
            <span>医生复核</span>
            <strong>待决策</strong>
          </header>
          <div>
            <AppButton
              variant="secondary"
              size="sm"
              icon="check"
              :disabled="busy"
              title="接受医生复核结论并评估训练准入条件"
              @click="review('accepted')"
            >
              接受标注
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              icon="review"
              :disabled="busy"
              title="记录医生修改后确认的标注"
              @click="review('modified')"
            >
              修改后接受
            </AppButton>
            <AppButton variant="secondary" size="sm" icon="undo" :disabled="busy" @click="review('changes_requested')">
              退回修改
            </AppButton>
            <AppButton variant="ghost" size="sm" icon="close" :disabled="busy" @click="review('rejected')">
              拒绝
            </AppButton>
          </div>
        </section>

        <details class="version-history" :open="Boolean(activeAnnotation)">
          <summary>
            <span>版本历史</span>
            <strong>{{ versions.length }}</strong>
          </summary>
          <ol v-if="versions.length">
            <li v-for="version in versions" :key="version.version">
              <span>v{{ version.version }}</span>
              <div>
                <strong>{{ version.author.actor_id }}</strong>
                <small>{{ formatTimestamp(version.created_at) }}</small>
              </div>
            </li>
          </ol>
          <p v-else>暂无已保存版本</p>
        </details>

        <section class="control-section training-section">
          <header>
            <span>训练数据</span>
            <strong>当前病例</strong>
          </header>
          <AppButton
            variant="secondary"
            size="sm"
            icon="download"
            block
            :disabled="busy || hasUnsavedChanges"
            :title="hasUnsavedChanges ? '请先保存或放弃当前修改' : '生成当前病例的标注训练清单'"
            @click="buildTrainingManifest"
          >
            生成训练清单
          </AppButton>
          <p v-if="trainingManifestPath">{{ trainingManifestPath }}</p>
        </section>
      </aside>
    </section>

    <MedicalDisclaimer v-if="store.currentCase" />
  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import ManualAnnotationCanvas from "@/components/ManualAnnotationCanvas.vue";
import MedicalDisclaimer from "@/components/MedicalDisclaimer.vue";
import { ApiError, apiClient } from "@/services/apiClient";
import { useCaseStore } from "@/stores/caseStore";
import type {
  AnnotationGeometry,
  AnnotationLabel,
  AnnotationOverlayLayer,
  AnnotationSource,
  AnnotationSourceReference,
  AnnotationSourceType,
  AnnotationStatus,
  AnnotationVersion,
  ManualAnnotation,
} from "@/types/annotation";
import type { AppIconName } from "@/components/appIcons";

type SourceFilter = "all" | AnnotationSourceType;
type MessageTone = "info" | "success" | "error";

interface AnnotationDraftState {
  annotation: ManualAnnotation | null;
  geometry: AnnotationGeometry;
  notes: string;
  dirty: boolean;
  notesDirty: boolean;
  versions: AnnotationVersion[];
}

const route = useRoute();
const router = useRouter();
const store = useCaseStore();

const caseIdInput = ref("");
const sources = ref<AnnotationSource[]>([]);
const annotations = ref<ManualAnnotation[]>([]);
const versions = ref<AnnotationVersion[]>([]);
const sourceFilter = ref<SourceFilter>("all");
const selectedSourceKey = ref("");
const selectedLabel = ref<AnnotationLabel>("lesion");
const activeAnnotation = ref<ManualAnnotation | null>(null);
const geometry = shallowRef<AnnotationGeometry>({ coordinate_space: "image_pixels", operations: [] });
const notes = ref("");
const dirty = ref(false);
const notesDirty = ref(false);
const labelDrafts = ref(new Map<AnnotationLabel, AnnotationDraftState>());
const loadingCase = ref(false);
const loadingWorkspace = ref(false);
const saving = ref(false);
const submitting = ref(false);
const reviewing = ref(false);
const deleting = ref(false);
const buildingManifest = ref(false);
const message = ref("");
const messageTone = ref<MessageTone>("info");
const canvasDimensions = ref({ width: 0, height: 0 });
const trainingManifestPath = ref("");

const sourceFilters: Array<{ value: SourceFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "case_jpeg", label: "JPEG" },
  { value: "video_keyframe", label: "关键帧" },
  { value: "model_candidate", label: "候选区" },
];

const labelOptions: Array<{ value: AnnotationLabel; label: string; color: string }> = [
  { value: "lesion", label: "疑似病灶", color: "#e5484d" },
  { value: "exposed_bone", label: "暴露骨面", color: "#f0a929" },
  { value: "fluorescence_signal", label: "荧光信号", color: "#1db996" },
  { value: "boundary_risk", label: "边界风险", color: "#df6d2f" },
  { value: "uncertain", label: "不确定区域", color: "#6d77c8" },
  { value: "low_activity", label: "低活性候选", color: "#506a9b" },
  { value: "transition", label: "过渡复核区", color: "#d78a2d" },
  { value: "high_activity", label: "高活性参考", color: "#20a779" },
  { value: "ignore", label: "无法判断区", color: "#68717c" },
];

const busy = computed(
  () => loadingCase.value || loadingWorkspace.value || saving.value || submitting.value || reviewing.value || deleting.value || buildingManifest.value,
);
const currentLabelHasUnsavedChanges = computed(() => dirty.value || notesDirty.value);
const hasUnsavedChanges = computed(
  () => currentLabelHasUnsavedChanges.value || [...labelDrafts.value.values()].some((draft) => draft.dirty || draft.notesDirty),
);
const selectedSource = computed(() => sources.value.find((source) => sourceKey(source) === selectedSourceKey.value) ?? null);
const filteredSources = computed(() =>
  sourceFilter.value === "all" ? sources.value : sources.value.filter((source) => source.source_type === sourceFilter.value),
);
const selectedLabelMeta = computed(() => labelOptions.find((option) => option.value === selectedLabel.value) ?? labelOptions[0]);
const referenceLayers = computed<AnnotationOverlayLayer[]>(() => {
  const source = selectedSource.value;
  if (!source) return [];
  const layers = new Map<AnnotationLabel, AnnotationGeometry>();
  for (const annotation of annotations.value) {
    if (annotation.label === selectedLabel.value || !sameSource(annotation.source, source)) continue;
    if (annotation.geometry?.operations.length) layers.set(annotation.label, cloneGeometry(annotation.geometry));
  }
  for (const [label, draft] of labelDrafts.value) {
    if (label === selectedLabel.value || !draft.geometry.operations.length) continue;
    layers.set(label, cloneGeometry(draft.geometry));
  }
  return labelOptions.flatMap((option) => {
    const geometry = layers.get(option.value);
    return geometry ? [{ id: option.value, label: option.value, color: option.color, geometry }] : [];
  });
});
const sourcePreviewUrl = computed(() => {
  const path = activeAnnotation.value?.source_snapshot_path || selectedSource.value?.preview_path || "";
  return path ? apiClient.filePreviewUrl(path) : "";
});
const annotationLocked = computed(() =>
  activeAnnotation.value ? !["draft", "changes_requested"].includes(activeAnnotation.value.status) : false,
);
const canvasDisabledReason = computed(() => {
  if (!selectedSource.value) return "请先选择标注来源";
  if (saving.value) return "正在保存标注版本";
  if (annotationLocked.value) return `当前记录状态为${statusLabel(activeAnnotation.value?.status)}，编辑已锁定`;
  return "";
});
const canvasKey = computed(() => `${selectedSourceKey.value}:${selectedLabel.value}:${activeAnnotation.value?.current_version ?? 0}`);
const saveDisabled = computed(
  () => busy.value || annotationLocked.value || !selectedSource.value || (!dirty.value && !notesDirty.value) || !geometry.value.operations.length,
);
const saveDisabledReason = computed(() => {
  if (busy.value) return "标注请求处理中";
  if (!selectedSource.value) return "请先选择标注来源";
  if (annotationLocked.value) return canvasDisabledReason.value;
  if (!geometry.value.operations.length) return "当前标签尚无有效标注区域";
  if (!dirty.value && !notesDirty.value) return "当前版本没有未保存修改";
  return "保存草稿或新版本";
});
const submitDisabled = computed(
  () => busy.value || hasUnsavedChanges.value || !activeAnnotation.value || activeAnnotation.value.status !== "draft",
);
const submitDisabledReason = computed(() => {
  if (!activeAnnotation.value) return "请先保存草稿";
  if (activeAnnotation.value.status !== "draft") return `当前状态为${statusLabel(activeAnnotation.value.status)}`;
  if (hasUnsavedChanges.value) return "请先保存或放弃当前修改";
  if (busy.value) return "标注请求处理中";
  return "由可信医生身份提交复核";
});
watch(sourceFilter, () => {
  if (filteredSources.value.some((source) => sourceKey(source) === selectedSourceKey.value)) return;
  const first = filteredSources.value[0];
  if (first && !hasUnsavedChanges.value) void selectSource(first);
});

onMounted(async () => {
  const routeCaseId = typeof route.query.caseId === "string" ? route.query.caseId.trim() : "";
  caseIdInput.value = routeCaseId || store.currentCase?.case_id || "";
  if (routeCaseId && store.currentCase?.case_id !== routeCaseId) {
    await loadCaseWorkspace();
  } else if (store.currentCase) {
    await refreshWorkspace();
  }
});

async function loadCaseWorkspace() {
  const caseId = caseIdInput.value.trim();
  if (!caseId || busy.value || hasUnsavedChanges.value) return;
  loadingCase.value = true;
  clearMessage();
  try {
    const loaded = await store.loadCase(caseId);
    if (!loaded) throw new Error(store.error || "病例载入失败");
    await router.replace({ path: "/annotations", query: { caseId: loaded.case_id } });
    await refreshWorkspace();
    setMessage(`已载入病例 ${loaded.case_id}`, "success");
  } catch (error) {
    setMessage(errorMessage(error, "病例载入失败"), "error");
  } finally {
    loadingCase.value = false;
  }
}

async function loadOfdvdnetDemo() {
  if (busy.value || hasUnsavedChanges.value) return;
  loadingCase.value = true;
  clearMessage();
  try {
    const demo = await apiClient.ensureStandardDemoCase();
    const loaded = await store.loadCase(demo.case_id);
    if (!loaded) throw new Error(store.error || "OFDVDnet 示例病例载入失败");
    caseIdInput.value = loaded.case_id;
    await router.replace({ path: "/annotations", query: { caseId: loaded.case_id } });
    await refreshWorkspace();
    setMessage("已载入 OFDVDnet 公开代理视频的可标注关锥帧。", "success");
  } catch (error) {
    setMessage(errorMessage(error, "OFDVDnet 示例病例载入失败"), "error");
  } finally {
    loadingCase.value = false;
  }
}

async function refreshWorkspace() {
  const caseId = store.currentCase?.case_id;
  if (!caseId || loadingWorkspace.value) return;
  loadingWorkspace.value = true;
  clearMessage();
  try {
    const [sourcePayload, annotationPayload] = await Promise.all([
      apiClient.listAnnotationSources(caseId),
      apiClient.listAnnotations(caseId),
    ]);
    sources.value = sourcePayload.sources ?? [];
    annotations.value = annotationPayload.items ?? [];
    const selectedStillExists = sources.value.some((source) => sourceKey(source) === selectedSourceKey.value);
    if (!selectedStillExists) selectedSourceKey.value = sourceKey(sources.value[0]);
    await syncActiveAnnotation();
  } catch (error) {
    setMessage(errorMessage(error, "标注工作区读取失败"), "error");
  } finally {
    loadingWorkspace.value = false;
  }
}

async function selectSource(source: AnnotationSource) {
  const key = sourceKey(source);
  if (hasUnsavedChanges.value && key !== selectedSourceKey.value) return;
  selectedSourceKey.value = key;
  await syncActiveAnnotation();
}

async function selectLabel(label: AnnotationLabel) {
  if (label === selectedLabel.value || busy.value) return;
  cacheCurrentDraft();
  selectedLabel.value = label;
  if (restoreCachedDraft(label)) {
    setMessage(`已切换至${selectedLabelMeta.value.label}，其他标签的未保存修改会保留在当前页面。`, "info");
    return;
  }
  await syncActiveAnnotation();
}

async function syncActiveAnnotation() {
  const source = selectedSource.value;
  if (!source || !store.currentCase) {
    resetAnnotationState();
    return;
  }
  const summary = annotations.value.find(
    (annotation) => annotation.label === selectedLabel.value && sameSource(annotation.source, source),
  );
  if (!summary) {
    resetAnnotationState();
    return;
  }
  try {
    activeAnnotation.value = await apiClient.getAnnotation(store.currentCase.case_id, summary.annotation_id);
    geometry.value = cloneGeometry(activeAnnotation.value.geometry);
    notes.value = activeAnnotation.value.notes ?? "";
    dirty.value = false;
    notesDirty.value = false;
    const payload = await apiClient.listAnnotationVersions(store.currentCase.case_id, summary.annotation_id);
    versions.value = payload.items ?? [];
  } catch (error) {
    setMessage(errorMessage(error, "标注版本读取失败"), "error");
  }
}

function resetAnnotationState() {
  activeAnnotation.value = null;
  geometry.value = { coordinate_space: "image_pixels", operations: [] };
  notes.value = "";
  dirty.value = false;
  notesDirty.value = false;
  versions.value = [];
}

function cacheCurrentDraft() {
  if (!currentLabelHasUnsavedChanges.value) return;
  labelDrafts.value.set(selectedLabel.value, {
    annotation: activeAnnotation.value,
    geometry: cloneGeometry(geometry.value),
    notes: notes.value,
    dirty: dirty.value,
    notesDirty: notesDirty.value,
    versions: [...versions.value],
  });
}

function restoreCachedDraft(label: AnnotationLabel): boolean {
  const draft = labelDrafts.value.get(label);
  if (!draft) return false;
  activeAnnotation.value = draft.annotation;
  geometry.value = cloneGeometry(draft.geometry);
  notes.value = draft.notes;
  dirty.value = draft.dirty;
  notesDirty.value = draft.notesDirty;
  versions.value = [...draft.versions];
  return true;
}

function handleGeometryChange(nextGeometry: AnnotationGeometry) {
  geometry.value = nextGeometry;
  dirty.value = true;
}

function handleSourceReady(dimensions: { width: number; height: number }) {
  canvasDimensions.value = dimensions;
}

async function saveDraft(): Promise<ManualAnnotation | null> {
  const caseId = store.currentCase?.case_id;
  const source = selectedSource.value;
  if (!caseId || !source || saveDisabled.value) return activeAnnotation.value;
  saving.value = true;
  clearMessage();
  try {
    const saved = activeAnnotation.value
      ? await apiClient.saveAnnotationVersion(caseId, activeAnnotation.value.annotation_id, {
          expected_version: activeAnnotation.value.current_version,
          geometry: cloneGeometry(geometry.value),
          notes: notes.value.trim(),
        })
      : await apiClient.createAnnotation(caseId, {
          source: sourceReference(source),
          label: selectedLabel.value,
          geometry: cloneGeometry(geometry.value),
          notes: notes.value.trim(),
        });
    activeAnnotation.value = saved;
    dirty.value = false;
    notesDirty.value = false;
    labelDrafts.value.delete(selectedLabel.value);
    await refreshAnnotationsAfterWrite(saved);
    setMessage(`标注 ${saved.annotation_id} 已保存为 v${saved.current_version}`, "success");
    return saved;
  } catch (error) {
    setMessage(errorMessage(error, "标注保存失败"), "error");
    return null;
  } finally {
    saving.value = false;
  }
}

async function submitForReview() {
  const caseId = store.currentCase?.case_id;
  const current = activeAnnotation.value;
  if (!caseId || !current || submitDisabled.value) return;
  submitting.value = true;
  clearMessage();
  try {
    const identity = await apiClient.getReviewIdentity();
    if (!identity.authenticated || identity.role !== "physician") {
      throw new Error("提交复核需要服务端已验证的医生身份");
    }
    const submitted = await apiClient.submitAnnotation(caseId, current.annotation_id, current.current_version, notes.value.trim());
    activeAnnotation.value = submitted;
    await refreshAnnotationsAfterWrite(submitted);
    setMessage("标注已提交医生复核，编辑已锁定。", "success");
  } catch (error) {
    setMessage(errorMessage(error, "标注提交失败"), "error");
  } finally {
    submitting.value = false;
  }
}

async function review(decision: "accepted" | "modified" | "rejected" | "changes_requested") {
  const caseId = store.currentCase?.case_id;
  const current = activeAnnotation.value;
  if (!caseId || !current || reviewing.value) return;
  reviewing.value = true;
  clearMessage();
  try {
    const identity = await apiClient.getReviewIdentity();
    if (!identity.authenticated || identity.role !== "physician") {
      throw new Error("复核决策需要服务端已验证的医生身份");
    }
    const reviewed = await apiClient.reviewAnnotation(
      caseId,
      current.annotation_id,
      current.current_version,
      decision,
      notes.value.trim(),
    );
    activeAnnotation.value = reviewed;
    await refreshAnnotationsAfterWrite(reviewed);
    if (["accepted", "modified"].includes(reviewed.status) && reviewed.training_eligible) {
      setMessage(`复核状态已更新为${statusLabel(reviewed.status)}；训练准入已确认，样本权重 ${reviewed.sample_weight.toFixed(2)}。`, "success");
    } else if (["accepted", "modified"].includes(reviewed.status)) {
      setMessage(
        `复核状态已更新为${statusLabel(reviewed.status)}；训练保持隔离：${trainingExclusionLabel(reviewed.training_exclusion_reason)}。`,
        "info",
      );
    } else {
      setMessage(`复核状态已更新为${statusLabel(reviewed.status)}。`, "success");
    }
  } catch (error) {
    setMessage(errorMessage(error, "复核决策写入失败"), "error");
  } finally {
    reviewing.value = false;
  }
}

async function deleteDraft() {
  const caseId = store.currentCase?.case_id;
  const current = activeAnnotation.value;
  if (!caseId || !current || current.status !== "draft" || deleting.value) return;
  deleting.value = true;
  clearMessage();
  try {
    await apiClient.deleteAnnotation(caseId, current.annotation_id);
    annotations.value = annotations.value.filter((item) => item.annotation_id !== current.annotation_id);
    resetAnnotationState();
    setMessage("草稿已删除。", "success");
  } catch (error) {
    setMessage(errorMessage(error, "草稿删除失败"), "error");
  } finally {
    deleting.value = false;
  }
}

function discardUnsavedChanges() {
  labelDrafts.value.clear();
  if (activeAnnotation.value) {
    geometry.value = cloneGeometry(activeAnnotation.value.geometry);
    notes.value = activeAnnotation.value.notes ?? "";
  } else {
    geometry.value = { coordinate_space: "image_pixels", operations: [] };
    notes.value = "";
  }
  dirty.value = false;
  notesDirty.value = false;
  setMessage("未保存修改已放弃。", "info");
}

async function buildTrainingManifest() {
  const caseId = store.currentCase?.case_id;
  if (!caseId || buildingManifest.value || hasUnsavedChanges.value) return;
  buildingManifest.value = true;
  clearMessage();
  try {
    const result = await apiClient.createAnnotationTrainingManifest([caseId], false);
    trainingManifestPath.value = result.manifest_path;
    setMessage(`训练清单已生成：${result.eligible_count} 条准入，${result.excluded_count} 条隔离。`, "success");
  } catch (error) {
    setMessage(errorMessage(error, "训练清单生成失败"), "error");
  } finally {
    buildingManifest.value = false;
  }
}

async function refreshAnnotationsAfterWrite(saved: ManualAnnotation) {
  const index = annotations.value.findIndex((annotation) => annotation.annotation_id === saved.annotation_id);
  if (index >= 0) annotations.value.splice(index, 1, saved);
  else annotations.value.push(saved);
  const caseId = store.currentCase?.case_id;
  if (!caseId) return;
  const payload = await apiClient.listAnnotationVersions(caseId, saved.annotation_id);
  versions.value = payload.items ?? [];
}

function annotationForSource(source: AnnotationSource): ManualAnnotation | null {
  return annotations.value.find(
    (annotation) => annotation.label === selectedLabel.value && sameSource(annotation.source, source),
  ) ?? null;
}

function sameSource(reference: AnnotationSourceReference, source: AnnotationSourceReference): boolean {
  return reference.source_type === source.source_type
    && nullable(reference.input_id) === nullable(source.input_id)
    && nullable(reference.run_id) === nullable(source.run_id)
    && nullable(reference.frame_index) === nullable(source.frame_index)
    && nullable(reference.candidate_id) === nullable(source.candidate_id);
}

function sourceReference(source: AnnotationSource): AnnotationSourceReference {
  return {
    source_type: source.source_type,
    input_id: source.input_id ?? null,
    run_id: source.run_id ?? null,
    frame_index: source.frame_index ?? null,
    timestamp_sec: source.timestamp_sec ?? null,
    candidate_id: source.candidate_id ?? null,
  };
}

function sourceKey(source?: AnnotationSource | null): string {
  if (!source) return "";
  return source.source_id || [
    source.source_type,
    source.input_id,
    source.run_id,
    source.frame_index,
    source.candidate_id,
  ].map(nullable).join(":");
}

function sourceTitle(source: AnnotationSource): string {
  if (source.title) return source.title;
  if (source.source_type === "case_jpeg") return source.label_hint || `病例图像 ${source.input_id ?? ""}`.trim();
  if (source.source_type === "model_candidate") return `模型候选区 ${source.candidate_id ?? ""}`.trim();
  return `视频关键帧 ${source.frame_index ?? ""}`.trim();
}

function sourceMeta(source: AnnotationSource): string {
  const parts: string[] = [sourceTypeLabel(source.source_type)];
  if (source.metadata?.source_record_id === "OFDVDNET_001") parts.push("OFDVDnet 公开代理");
  if (typeof source.frame_index === "number") parts.push(`帧 ${source.frame_index}`);
  if (typeof source.timestamp_sec === "number") parts.push(`${source.timestamp_sec.toFixed(2)} s`);
  if (source.original_width && source.original_height) parts.push(`${source.original_width} × ${source.original_height}`);
  return parts.join(" · ");
}

function sourceIcon(type: AnnotationSourceType): AppIconName {
  if (type === "case_jpeg") return "file";
  if (type === "model_candidate") return "target";
  return "video";
}

function sourceTypeLabel(type: AnnotationSourceType): string {
  return { case_jpeg: "病例 JPEG", video_keyframe: "MP4 关键帧", model_candidate: "模型候选区" }[type];
}

function sourceCount(filter: SourceFilter): number {
  return filter === "all" ? sources.value.length : sources.value.filter((source) => source.source_type === filter).length;
}

function statusLabel(status?: AnnotationStatus | null): string {
  if (!status) return "新草稿";
  return {
    draft: "草稿",
    submitted: "待医生复核",
    accepted: "已接受",
    modified: "修改后接受",
    rejected: "已拒绝",
    changes_requested: "退回修改",
  }[status];
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function cloneGeometry(value?: AnnotationGeometry | null): AnnotationGeometry {
  return {
    coordinate_space: value?.coordinate_space ?? "image_pixels",
    operations: (value?.operations ?? []).map((operation) => ({
      ...operation,
      points: operation.points.map((point) => ({ ...point })),
    })),
  };
}

function nullable(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function trainingExclusionLabel(reason?: string | null): string {
  if (!reason) return "训练准入条件尚未全部满足";
  return {
    trusted_physician_annotation_required: "标注作者身份未达到可信医生要求",
    trusted_physician_submission_required: "提交者身份未达到可信医生要求",
    trusted_physician_review_required: "复核者身份未达到可信医生要求",
    independent_physician_review_required: "需要由另一位可信医生完成独立复核",
    empty_annotation_mask: "标注掩膜为空",
    case_record_missing: "病例记录缺失",
    case_intake_metadata_missing: "病例缺少批次准入记录",
    case_training_authorization_not_approved: "机构训练授权尚未批准",
    case_deidentification_unconfirmed: "病例脱敏状态尚未确认",
    case_mapping_custody_unconfirmed: "病例映射表保管责任尚未确认",
    case_intake_not_admitted: "病例批次尚未通过准入",
    case_training_usage_not_authorized: "用途范围尚未明确允许模型训练",
    source_input_not_bound: "标注未绑定已准入的来源输入",
    source_input_missing: "来源输入记录缺失",
    source_input_institutional_handover_required: "来源输入缺少机构交接证明",
    source_input_not_admitted: "来源输入尚未通过准入",
    source_input_training_authorization_not_approved: "来源输入的机构训练授权尚未批准",
    source_input_deidentification_unconfirmed: "来源输入的脱敏状态尚未确认",
    source_input_training_usage_not_authorized: "来源输入用途尚未明确允许模型训练",
    source_input_batch_id_missing: "来源输入缺少批次编号",
    source_input_batch_not_bound_to_case_intake: "来源输入批次与病例准入记录不一致",
    source_input_intake_record_id_missing: "来源输入缺少准入记录编号",
    source_input_organization_mismatch: "来源机构与病例准入记录不一致",
    source_input_external_case_mismatch: "脱敏病例编号与准入记录不一致",
    source_input_outside_controlled_storage_or_missing: "来源输入缺失或脱离受控存储",
    source_input_checksum_mismatch: "来源输入校验码不一致",
    source_input_checksum_invalid: "来源输入校验码无效",
  }[reason] ?? "训练准入证据未通过安全门";
}

function setMessage(value: string, tone: MessageTone = "info") {
  message.value = value;
  messageTone.value = tone;
}

function clearMessage() {
  message.value = "";
  messageTone.value = "info";
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = error.body as { detail?: string | { message?: string } } | null;
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail && typeof body.detail === "object" && typeof body.detail.message === "string") return body.detail.message;
  }
  return error instanceof Error ? error.message : fallback;
}
</script>

<style scoped>
.manual-annotation-page {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.annotation-page-header,
.annotation-workspace,
.workspace-message,
.annotation-empty-page,
.manual-annotation-page > :deep(.medical-disclaimer) {
  width: min(100%, var(--ov-content-wide));
  margin-right: auto;
  margin-left: auto;
}

.annotation-page-header {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: var(--ov-space-5);
}

.annotation-title-copy {
  display: grid;
  gap: 5px;
}

.page-kicker,
.annotation-page-header p {
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 750;
}

.annotation-page-header h1,
.annotation-page-header p {
  margin: 0;
}

.annotation-page-header h1 {
  font-size: var(--ov-font-page-title);
  line-height: 1.1;
  letter-spacing: 0;
}

.case-loader {
  display: flex;
  gap: 9px;
  align-items: end;
}

.case-loader label {
  display: grid;
  gap: 5px;
}

.case-loader label span {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.case-loader input {
  width: 260px;
  min-height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 6px 9px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font: inherit;
  overflow-wrap: anywhere;
}

.workspace-message {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: 40px;
  margin-bottom: 14px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 9px 12px;
  background: var(--ov-bg-info);
  color: var(--ov-text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.workspace-message--success {
  border-color: color-mix(in srgb, var(--ov-success) 40%, var(--ov-border));
  background: var(--ov-bg-success);
}

.workspace-message--error {
  border-color: color-mix(in srgb, var(--ov-danger) 40%, var(--ov-border));
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.workspace-message :deep(.app-icon) {
  flex: 0 0 auto;
  width: 17px;
  height: 17px;
}

.annotation-empty-page {
  display: grid;
  place-items: center;
  gap: 12px;
  min-height: 440px;
  color: var(--ov-text-muted);
  text-align: center;
}

.annotation-empty-page h2,
.annotation-empty-page p {
  margin: 0;
}

.annotation-empty-page :deep(.app-icon) {
  width: 46px;
  height: 46px;
}

.annotation-empty-page a {
  color: var(--ov-primary);
  font-weight: 800;
}

.annotation-workspace {
  display: grid;
  grid-template-columns: minmax(250px, 0.52fr) minmax(580px, 2fr) minmax(300px, 0.66fr);
  gap: 16px;
  align-items: start;
}

.source-panel,
.canvas-panel,
.annotation-control-panel {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.source-panel,
.annotation-control-panel {
  position: sticky;
  top: 70px;
  max-height: calc(100dvh - 92px);
  overflow: auto;
}

.source-panel {
  display: grid;
  align-content: start;
}

.canvas-panel {
  padding: 15px;
}

.panel-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 15px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.panel-heading > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.panel-heading span,
.panel-heading small {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.panel-heading strong,
.panel-heading small {
  overflow-wrap: anywhere;
}

.panel-heading strong {
  font-size: 13px;
}

.panel-heading button {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  background: var(--ov-bg-control);
  color: var(--ov-text-secondary);
  cursor: pointer;
}

.panel-heading button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.panel-heading button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.source-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.source-tabs button {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 6px 8px;
  background: transparent;
  color: var(--ov-text-muted);
  font: inherit;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
}

.source-tabs button.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  color: var(--ov-primary);
}

.source-tabs button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.source-tabs button span {
  min-width: 20px;
  text-align: right;
}

.source-list {
  display: grid;
  align-content: start;
  gap: 2px;
  padding: 8px;
}

.source-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 9px;
  width: 100%;
  min-height: 68px;
  border: 1px solid transparent;
  border-radius: 5px;
  padding: 9px;
  background: transparent;
  color: var(--ov-text);
  text-align: left;
  cursor: pointer;
}

.source-row.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
}

.source-row:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.source-row:not(:disabled):hover {
  background: var(--ov-bg-hover);
}

.source-row__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 5px;
  background: var(--ov-bg-soft);
  color: var(--ov-primary);
}

.source-row__icon :deep(.app-icon) {
  width: 17px;
  height: 17px;
}

.source-row__body {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.source-row__body strong,
.source-row__body small {
  overflow-wrap: anywhere;
}

.source-row__body strong {
  font-size: 12px;
}

.source-row__body small,
.source-row__status {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.source-row__status {
  color: var(--ov-primary);
  font-weight: 800;
}

.source-list__empty {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 160px;
  padding: 20px;
  color: var(--ov-text-muted);
  font-size: 11px;
  text-align: center;
}

.source-list__empty :deep(.app-icon) {
  width: 28px;
  height: 28px;
}

.annotation-control-panel {
  display: grid;
  align-content: start;
  padding: 13px;
}

.control-section {
  display: grid;
  gap: 10px;
  padding: 12px 2px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.control-section header {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.control-section header span {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.control-section header strong {
  color: var(--ov-text);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.label-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.label-options button {
  display: flex;
  gap: 7px;
  align-items: center;
  min-height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 11px;
  font-weight: 750;
  cursor: pointer;
}

.label-options button.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  color: var(--ov-text);
}

.label-options button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.label-swatch {
  flex: 0 0 auto;
  width: 11px;
  height: 11px;
  border: 1px solid color-mix(in srgb, var(--ov-text) 15%, transparent);
  border-radius: 2px;
}

.annotation-record dl {
  display: grid;
  gap: 7px;
  margin: 0;
}

.annotation-record dl div {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.annotation-record dt,
.annotation-record dd {
  margin: 0;
  font-size: 10px;
  overflow-wrap: anywhere;
}

.annotation-record dt {
  color: var(--ov-text-muted);
}

.annotation-record dd {
  color: var(--ov-text-secondary);
  text-align: right;
}

.annotation-record dd.eligible {
  color: var(--ov-success);
  font-weight: 850;
}

.notes-field {
  display: grid;
  gap: 5px;
}

.notes-field span {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
}

.notes-field textarea {
  width: 100%;
  min-height: 80px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 11px;
  line-height: 1.5;
  resize: vertical;
  overflow-wrap: anywhere;
}

.secondary-actions,
.review-actions > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.review-actions > div > :first-child {
  grid-column: 1 / -1;
}

.version-history {
  padding: 12px 2px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.version-history summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
}

.version-history ol {
  display: grid;
  gap: 7px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.version-history li {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 7px;
  align-items: center;
}

.version-history li > span {
  display: grid;
  place-items: center;
  min-height: 26px;
  border-radius: 4px;
  background: var(--ov-bg-soft);
  color: var(--ov-primary);
  font-size: 10px;
  font-weight: 850;
}

.version-history li div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.version-history li strong,
.version-history li small {
  font-size: 10px;
  overflow-wrap: anywhere;
}

.version-history li small,
.version-history p {
  color: var(--ov-text-muted);
}

.version-history p,
.training-section p {
  margin: 9px 0 0;
  font-size: 10px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.training-section {
  border-bottom: 0;
}

.manual-annotation-page > :deep(.medical-disclaimer) {
  margin-top: 18px;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 1px;
}

@media (max-width: 1360px) {
  .annotation-workspace {
    grid-template-columns: 230px minmax(560px, 1fr) 290px;
  }
}
</style>
