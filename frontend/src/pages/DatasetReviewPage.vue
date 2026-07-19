<template>
  <main class="dataset-review-page">
    <header class="page-header">
      <div>
        <h1>静态荧光数据复核</h1>
        <p>对 D047/D048 论文原图完成面板裁剪、双通道配对和像素级复核，保留来源、许可、身份和训练准入边界。</p>
      </div>
      <div class="summary-strip" aria-label="复核队列概览">
        <div><span>总记录</span><strong>{{ records.length }}</strong></div>
        <div><span>待裁剪</span><strong>{{ cropRequiredCount }}</strong></div>
        <div><span>已复核</span><strong>{{ reviewedCount }}</strong></div>
        <div><span>训练准入</span><strong>{{ trainingEligibleCount }}</strong></div>
      </div>
    </header>

    <section class="queue-toolbar" aria-label="复核队列筛选">
      <button
        type="button"
        :disabled="loading || writeBusy"
        :title="writeBusy ? writeBusyReason : '刷新复核队列'"
        @click="loadQueue"
      >
        <AppIcon name="load" />
        {{ loading ? "正在读取..." : "刷新队列" }}
      </button>
      <label>
        <span>数据集</span>
        <select v-model="datasetFilter" :disabled="writeBusy" :title="writeBusy ? writeBusyReason : '筛选数据集'">
          <option value="all">全部</option>
          <option value="d047">D047</option>
          <option value="d048">D048</option>
        </select>
      </label>
      <label>
        <span>复核状态</span>
        <select v-model="stateFilter" :disabled="writeBusy" :title="writeBusy ? writeBusyReason : '筛选复核状态'">
          <option value="all">全部</option>
          <option value="crop_required">待裁剪</option>
          <option value="review_required">待复核</option>
          <option value="accepted">已接受</option>
          <option value="modified">已修改</option>
          <option value="rejected">已拒绝</option>
        </select>
      </label>
      <div class="queue-position">
        当前 {{ selectedPositionLabel }}；筛选结果 {{ filteredRecords.length }} 条；列表第 {{ currentPage }} / {{ pageCount }} 页
      </div>
    </section>

    <section v-if="error" class="page-alert" role="alert">{{ error }}</section>
    <section v-if="successMessage" class="page-success" role="status">{{ successMessage }}</section>

    <section class="review-workspace" aria-label="静态数据复核工作区">
      <aside class="record-sidebar">
        <div class="sidebar-heading">
          <strong>候选列表</strong>
          <span>长路径和来源字段完整换行显示</span>
        </div>
        <div class="record-list">
          <button
            v-for="item in paginatedRecords"
            :key="item.record_id"
            type="button"
            class="record-item"
            :class="{ selected: item.record_id === selectedRecordId }"
            :disabled="writeBusy"
            :title="writeBusy ? writeBusyReason : `选择记录 ${item.source_record_id || item.record_id}`"
            @click="selectRecord(item.record_id)"
          >
            <span class="record-item__topline">
              <b>{{ datasetLabel(item) }}</b>
              <i :class="`state-${item.review_state}`">{{ item.crop_required ? "待裁剪" : reviewStateLabel(item.review_state) }}</i>
            </span>
            <strong>{{ item.source_record_id || item.record_id }}</strong>
            <span>{{ item.record_id }}</span>
            <small>{{ item.license || "许可待核验" }}</small>
          </button>
        </div>
        <nav v-if="filteredRecords.length" class="record-pagination" aria-label="候选列表分页">
          <button
            type="button"
            :disabled="currentPage <= 1 || writeBusy"
            :title="writeBusy ? writeBusyReason : currentPage <= 1 ? '当前已是第一页' : '查看上一页候选'"
            @click="selectPage(currentPage - 1)"
          >
            上一页
          </button>
          <span aria-live="polite">
            第 {{ currentPage }} / {{ pageCount }} 页
            <small>{{ pageRangeLabel }}</small>
          </span>
          <button
            type="button"
            :disabled="currentPage >= pageCount || writeBusy"
            :title="writeBusy ? writeBusyReason : currentPage >= pageCount ? '当前已是最后一页' : '查看下一页候选'"
            @click="selectPage(currentPage + 1)"
          >
            下一页
          </button>
        </nav>
        <p v-if="!loading && !filteredRecords.length" class="empty-state">当前筛选条件下没有复核记录。</p>
      </aside>

      <div class="review-main">
        <template v-if="selectedRecord">
          <section class="record-metadata">
            <div class="metadata-header">
              <div>
                <span>{{ datasetLabel(selectedRecord) }}</span>
                <h2>{{ selectedRecord.source_record_id || selectedRecord.record_id }}</h2>
              </div>
              <div class="record-navigation">
                <button type="button" :disabled="!hasPrevious || writeBusy" :title="writeBusy ? writeBusyReason : '上一条'" @click="selectRelative(-1)">上一条</button>
                <button type="button" :disabled="!hasNext || writeBusy" :title="writeBusy ? writeBusyReason : '下一条'" @click="selectRelative(1)">下一条</button>
                <button type="button" :aria-expanded="metadataExpanded" @click="metadataExpanded = !metadataExpanded">
                  {{ metadataExpanded ? "收起元数据" : "展开元数据" }}
                </button>
              </div>
            </div>
            <dl v-if="metadataExpanded">
              <dt>记录 ID</dt><dd>{{ selectedRecord.record_id }}</dd>
              <dt>来源分组</dt><dd>{{ selectedRecord.source_group_id || "暂无" }}</dd>
              <dt>图像路径</dt><dd>{{ selectedRecord.image_path }}</dd>
              <dt>许可</dt><dd>{{ selectedRecord.license || "待核验" }}</dd>
              <dt>用途策略</dt><dd>{{ selectedRecord.usage_policy || "待核验" }}</dd>
              <dt>裁剪状态</dt><dd>{{ selectedRecord.crop_required ? "原图待裁剪" : "原子面板已就绪" }}</dd>
              <dt>面板类型</dt><dd>{{ panelRoleDisplay(selectedRecord) }}</dd>
              <dt>配对 ID</dt><dd>{{ pairIdDisplay(selectedRecord) }}</dd>
              <dt v-if="selectedRecord.panel_label">建议面板</dt><dd v-if="selectedRecord.panel_label">{{ selectedRecord.panel_label }}</dd>
              <dt v-if="selectedRecord.suggested_pair_alignment">配对可信度</dt><dd v-if="selectedRecord.suggested_pair_alignment">{{ pairAlignmentLabel(selectedRecord.suggested_pair_alignment) }}</dd>
              <dt>复核身份</dt><dd>{{ reviewerRoleLabel(selectedRecord) }}</dd>
              <dt>复核权限</dt><dd>{{ selectedRecord.review_authority || "待复核" }}</dd>
              <dt>训练状态</dt><dd>{{ selectedRecord.training_eligible ? "已通过当前训练准入" : "当前未进入训练" }}</dd>
              <dt>来源页面</dt>
              <dd>
                <a v-if="selectedRecord.source_url" :href="selectedRecord.source_url" target="_blank" rel="noreferrer">
                  {{ selectedRecord.source_url }}
                </a>
                <span v-else>暂无</span>
              </dd>
            </dl>
          </section>

          <StaticCropEditor
            v-if="selectedRecord.crop_required"
            :key="`crop-${selectedRecord.record_id}`"
            :record="selectedRecord"
            :source-url="recordImageUrl(selectedRecord)"
            :loading="writeBusy"
            @save="saveCrop"
          />

          <section v-else class="seed-controls" aria-label="自动候选掩膜">
            <div>
              <span>自动候选阈值 {{ seedThreshold.toFixed(1) }}</span>
              <input v-model.number="seedThreshold" type="range" min="0.1" max="0.9" step="0.1" :disabled="writeBusy" />
            </div>
            <button type="button" :disabled="writeBusy" :title="writeBusy ? writeBusyReason : '生成候选掩膜'" @click="generateSeed">
              <AppIcon name="target" />
              {{ seedLoading ? "正在生成..." : "生成候选掩膜" }}
            </button>
            <strong v-if="selectedIsAutoSeed" class="seed-warning">
              自动候选 / 待人工复核 / 不可直接训练
            </strong>
            <p>候选掩膜仅用于加速描画；必须由项目复核人员或医生检查并通过现有保存流程提交。</p>
          </section>

          <StaticMaskEditor
            v-if="!selectedRecord.crop_required"
            :key="`${selectedRecord.record_id}-${maskRevision}`"
            :record="selectedRecord"
            :source-url="recordImageUrl(selectedRecord)"
            :mask-url="recordMaskUrl(selectedRecord)"
            :loading="writeBusy"
            :disabled-reason="writeBusyReason"
            @save="saveReview"
          />

          <p class="medical-boundary">
            {{ selectedRecord.medical_boundary || queueBoundary || defaultBoundary }}
          </p>
        </template>
        <div v-else class="workspace-empty">
          {{ loading ? "正在载入复核队列..." : "请选择一条 D047/D048 记录开始复核。" }}
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import StaticCropEditor from "@/components/StaticCropEditor.vue";
import StaticMaskEditor from "@/components/StaticMaskEditor.vue";
import { apiClient } from "@/services/apiClient";
import type { ReviewState } from "@/types/case";
import type { DatasetReviewCropRequest, DatasetReviewRecord } from "@/types/datasetReview";
import { errorMessage, reviewStateLabel } from "@/utils/caseDisplay";

type DatasetFilter = "all" | "d047" | "d048";
type StateFilter = "all" | "crop_required" | ReviewState;

const defaultBoundary = "公开论文裁剪图属于非目标域工程复核数据；结果需保留来源与复核身份，不代表临床金标准。";
const loading = ref(false);
const saving = ref(false);
const seedLoading = ref(false);
const cropSaving = ref(false);
const error = ref("");
const successMessage = ref("");
const records = ref<DatasetReviewRecord[]>([]);
const selectedRecordId = ref("");
const datasetFilter = ref<DatasetFilter>("all");
const stateFilter = ref<StateFilter>("all");
const queueBoundary = ref("");
const seedThreshold = ref(0.6);
const maskRevision = ref(0);
const seededRecordIds = ref(new Set<string>());
const metadataExpanded = ref(false);
const pageSize = 20;
const currentPage = ref(1);
const writeBusy = computed(() => saving.value || seedLoading.value || cropSaving.value);
const writeBusyReason = computed(() => {
  if (saving.value) return "正在保存复核掩膜，请等待当前写入完成。";
  if (cropSaving.value) return "正在保存裁剪结果，请等待当前写入完成。";
  if (seedLoading.value) return "正在生成候选掩膜，请等待当前写入完成。";
  return "";
});

const filteredRecords = computed(() =>
  records.value.filter((item) => {
    const dataset = datasetKey(item);
    return (datasetFilter.value === "all" || dataset === datasetFilter.value)
      && (
        stateFilter.value === "all"
        || (stateFilter.value === "crop_required" ? item.crop_required === true : item.review_state === stateFilter.value)
      );
  }),
);
const pageCount = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize)));
const pageStartIndex = computed(() => (currentPage.value - 1) * pageSize);
const paginatedRecords = computed(() => filteredRecords.value.slice(pageStartIndex.value, pageStartIndex.value + pageSize));
const pageRangeLabel = computed(() => {
  if (!filteredRecords.value.length) return "0 条";
  const start = pageStartIndex.value + 1;
  const end = Math.min(pageStartIndex.value + pageSize, filteredRecords.value.length);
  return `${start}-${end} / ${filteredRecords.value.length} 条`;
});
const selectedRecord = computed(() => records.value.find((item) => item.record_id === selectedRecordId.value) ?? null);
const selectedFilteredIndex = computed(() => filteredRecords.value.findIndex((item) => item.record_id === selectedRecordId.value));
const hasPrevious = computed(() => selectedFilteredIndex.value > 0);
const hasNext = computed(() => selectedFilteredIndex.value >= 0 && selectedFilteredIndex.value < filteredRecords.value.length - 1);
const selectedPositionLabel = computed(() => {
  if (selectedFilteredIndex.value < 0) return "未选择";
  return `${selectedFilteredIndex.value + 1} / ${filteredRecords.value.length}`;
});
const reviewedCount = computed(() => records.value.filter((item) => item.review_state !== "review_required").length);
const cropRequiredCount = computed(() => records.value.filter((item) => item.crop_required === true).length);
const trainingEligibleCount = computed(() => records.value.filter((item) => item.training_eligible === true).length);
const selectedIsAutoSeed = computed(() => {
  const item = selectedRecord.value;
  if (!item) return false;
  const labelSource = `${item.label_source || ""} ${item.mask_origin || ""} ${item.mask_source || ""} ${item.record_kind || ""}`.toLowerCase();
  return seededRecordIds.value.has(item.record_id)
    || item.seed_generated === true
    || item.reviewer_role === "automated_seed"
    || labelSource.includes("seed")
    || labelSource.includes("auto_candidate");
});

watch([datasetFilter, stateFilter], () => {
  currentPage.value = 1;
  selectedRecordId.value = filteredRecords.value[0]?.record_id || "";
  successMessage.value = "";
});
watch(pageCount, (count) => {
  if (currentPage.value > count) currentPage.value = count;
});
watch(filteredRecords, (nextRecords) => {
  if (nextRecords.some((item) => item.record_id === selectedRecordId.value)) return;
  const firstVisible = nextRecords[(currentPage.value - 1) * pageSize] || nextRecords[0];
  selectedRecordId.value = firstVisible?.record_id || "";
});
watch(selectedRecordId, () => {
  metadataExpanded.value = false;
});

async function loadQueue() {
  if (loading.value || writeBusy.value) return;
  loading.value = true;
  error.value = "";
  successMessage.value = "";
  try {
    const payload = await apiClient.listDatasetReviewQueue();
    records.value = payload.items?.length ? payload.items : payload.records || [];
    queueBoundary.value = payload.medical_boundary || "";
    const currentExists = records.value.some((item) => item.record_id === selectedRecordId.value);
    if (!currentExists) selectedRecordId.value = filteredRecords.value[0]?.record_id || records.value[0]?.record_id || "";
  } catch (loadError) {
    error.value = errorMessage(loadError, "静态复核队列读取失败，请检查后端服务和数据 manifest。 ");
    records.value = [];
    selectedRecordId.value = "";
  } finally {
    loading.value = false;
  }
}

function selectRecord(recordId: string) {
  if (writeBusy.value) return;
  const filteredIndex = filteredRecords.value.findIndex((item) => item.record_id === recordId);
  if (filteredIndex >= 0) currentPage.value = Math.floor(filteredIndex / pageSize) + 1;
  selectedRecordId.value = recordId;
  error.value = "";
  successMessage.value = "";
}

function selectPage(page: number) {
  if (writeBusy.value) return;
  const nextPage = Math.min(Math.max(page, 1), pageCount.value);
  if (nextPage === currentPage.value) return;
  currentPage.value = nextPage;
  const firstRecord = filteredRecords.value[(nextPage - 1) * pageSize];
  if (firstRecord) selectRecord(firstRecord.record_id);
}

async function generateSeed() {
  if (!selectedRecord.value || writeBusy.value) return;
  const recordId = selectedRecord.value.record_id;
  seedLoading.value = true;
  error.value = "";
  successMessage.value = "";
  try {
    const updated = await apiClient.generateDatasetReviewSeed(recordId, seedThreshold.value);
    records.value = records.value.map((item) => item.record_id === recordId ? { ...item, ...updated } : item);
    seededRecordIds.value = new Set([...seededRecordIds.value, recordId]);
    maskRevision.value += 1;
    successMessage.value = `${recordId} 已生成自动候选掩膜，当前仍需人工复核且不可直接训练。`;
  } catch (seedError) {
    error.value = errorMessage(seedError, "自动候选掩膜生成失败，请检查图像内容、阈值和后端服务。 ");
  } finally {
    seedLoading.value = false;
  }
}

async function saveCrop(payload: DatasetReviewCropRequest) {
  if (!selectedRecord.value || writeBusy.value) return;
  const recordId = selectedRecord.value.record_id;
  cropSaving.value = true;
  error.value = "";
  successMessage.value = "";
  try {
    const updated = await apiClient.saveDatasetReviewCrop(recordId, payload);
    records.value = records.value.map((item) => item.record_id === recordId ? { ...item, ...updated } : item);
    maskRevision.value += 1;
    successMessage.value = `${recordId} 已保存原子面板裁剪；mask仍待复核，当前不可训练。`;
  } catch (cropError) {
    error.value = errorMessage(cropError, "原图裁剪保存失败，请检查范围、面板类型和后端写入状态。 ");
  } finally {
    cropSaving.value = false;
  }
}

function selectRelative(offset: number) {
  if (writeBusy.value) return;
  const target = filteredRecords.value[selectedFilteredIndex.value + offset];
  if (target) selectRecord(target.record_id);
}

function pairAlignmentLabel(value: string) {
  const labels: Record<string, string> = {
    approximate_view: "近似同视野，需人工确认",
    weak_sequential: "弱时序配对，不用于像素配准监督",
    sequential: "前后时序，非同步双通道",
  };
  return labels[value] || value;
}

function panelRoleDisplay(record: DatasetReviewRecord) {
  if (record.panel_role && record.panel_role !== "unclassified") return panelRoleLabel(record.panel_role);
  if (record.suggested_panel_role) return `待确认（建议：${panelRoleLabel(record.suggested_panel_role)}）`;
  return "待分类";
}

function panelRoleLabel(value: string) {
  const labels: Record<string, string> = {
    fluorescence_signal: "荧光信号",
    white_light: "白光",
    paired_fluorescence: "配对荧光",
    paired_white_light: "配对白光",
    histopathology: "病理",
    unclassified: "待分类",
  };
  return labels[value] || value;
}

function pairIdDisplay(record: DatasetReviewRecord) {
  if (record.pair_id) return record.pair_id;
  if (record.suggested_pair_id) return `待确认（建议：${record.suggested_pair_id}）`;
  return "暂无";
}

async function saveReview(payload: {
  maskPngBase64: string;
  reviewState: ReviewState;
  reviewerNotes: string;
  reviewerRole: "project_reviewer" | "physician";
}) {
  if (!selectedRecord.value || writeBusy.value) return;
  const recordId = selectedRecord.value.record_id;
  saving.value = true;
  error.value = "";
  successMessage.value = "";
  try {
    const updated = await apiClient.saveDatasetReviewMask(recordId, {
      mask_png_base64: payload.maskPngBase64,
      review_state: payload.reviewState,
      reviewer_notes: payload.reviewerNotes,
      reviewer_role: payload.reviewerRole,
    });
    records.value = records.value.map((item) => item.record_id === recordId ? { ...item, ...updated } : item);
    seededRecordIds.value.delete(recordId);
    seededRecordIds.value = new Set(seededRecordIds.value);
    maskRevision.value += 1;
    successMessage.value = `${recordId} 已保存；复核身份：${payload.reviewerRole === "physician" ? "医生" : "项目复核人员"}。`;
  } catch (saveError) {
    error.value = errorMessage(saveError, "复核掩膜保存失败，请检查 PNG 尺寸、复核状态和后端写入权限。 ");
  } finally {
    saving.value = false;
  }
}

function recordImageUrl(item: DatasetReviewRecord): string {
  return item.image_href ? apiClient.apiAssetUrl(item.image_href) : apiClient.filePreviewUrl(item.image_path);
}

function recordMaskUrl(item: DatasetReviewRecord): string | undefined {
  if (item.mask_href) return apiClient.apiAssetUrl(item.mask_href);
  return item.mask_path ? apiClient.filePreviewUrl(item.mask_path) : undefined;
}

function datasetKey(item: DatasetReviewRecord): "d047" | "d048" | "other" {
  const value = `${item.dataset_id || ""} ${item.record_id}`.toLowerCase();
  if (value.includes("d047")) return "d047";
  if (value.includes("d048")) return "d048";
  return "other";
}

function datasetLabel(item: DatasetReviewRecord): string {
  const key = datasetKey(item);
  return key === "other" ? item.dataset_id || "来源待确认" : key.toUpperCase();
}

function reviewerRoleLabel(item: DatasetReviewRecord): string {
  if (item.reviewer_role === "physician" || item.physician_reviewed) return "医生";
  if (item.reviewer_role === "project_reviewer") return "项目复核人员";
  if (item.reviewer_role === "automated_seed") return "自动候选，待人工复核";
  return "待复核";
}

onMounted(() => {
  void loadQueue();
});
</script>

<style scoped>
.dataset-review-page {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.page-header,
.queue-toolbar,
.page-alert,
.page-success,
.review-workspace {
  width: min(100%, var(--ov-content-large));
  margin-right: auto;
  margin-left: auto;
}

.page-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 0.7fr);
  gap: 24px;
  align-items: end;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  color: var(--ov-text);
  font-size: var(--ov-font-page-title);
  letter-spacing: 0;
}

.page-header p {
  margin: 7px 0 0;
  color: var(--ov-text-secondary);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.55;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-strip > div {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 11px 12px;
  background: var(--ov-bg-elevated);
}

.summary-strip span,
.summary-strip strong {
  display: block;
}

.summary-strip span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

.summary-strip strong {
  margin-top: 3px;
  color: var(--ov-text);
  font-size: 20px;
}

.queue-toolbar {
  display: grid;
  grid-template-columns: 150px 170px 180px minmax(240px, 1fr);
  gap: 14px;
  align-items: end;
  margin-bottom: 20px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 14px;
  background: var(--ov-bg-elevated);
}

.queue-toolbar button,
.record-navigation button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 10px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.queue-toolbar button:disabled,
.record-navigation button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.queue-toolbar button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.queue-toolbar label {
  display: grid;
  gap: 4px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.queue-toolbar select {
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
}

.queue-position {
  min-width: 0;
  min-height: 36px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 900;
  overflow-wrap: anywhere;
}

.page-alert,
.page-success {
  margin-bottom: 10px;
  border: 1px solid var(--ov-danger-border);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
  font-size: 13px;
  font-weight: 900;
  overflow-wrap: anywhere;
}

.page-success {
  border-color: var(--ov-success);
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.review-workspace {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.record-sidebar,
.record-metadata,
.seed-controls,
.workspace-empty,
.medical-boundary {
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  background: var(--ov-bg-elevated);
}

.record-sidebar {
  position: sticky;
  top: 72px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  max-height: calc(100vh - 94px);
  overflow: hidden;
}

.sidebar-heading {
  display: grid;
  gap: 3px;
  padding: 11px;
  border-bottom: 1px solid var(--ov-border-subtle);
}

.sidebar-heading strong {
  color: var(--ov-text);
  font-size: 14px;
}

.sidebar-heading span {
  color: var(--ov-text-muted);
  font-size: 10px;
  line-height: 1.4;
}

.record-list {
  display: grid;
  gap: 6px;
  min-height: 0;
  padding: 8px;
  overflow-y: auto;
}

.record-pagination {
  display: grid;
  grid-template-columns: minmax(72px, 1fr) auto minmax(72px, 1fr);
  gap: 8px;
  align-items: center;
  border-top: 1px solid var(--ov-border-subtle);
  padding: 9px;
  background: var(--ov-bg-elevated);
}

.record-pagination button {
  min-height: 34px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 11px;
  font-weight: 900;
  cursor: pointer;
}

.record-pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.record-pagination span,
.record-pagination small {
  display: block;
  color: var(--ov-text-secondary);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.35;
  text-align: center;
  white-space: normal;
}

.record-pagination small {
  margin-top: 2px;
  color: var(--ov-text-muted);
  font-size: 9px;
}

.record-item {
  display: grid;
  gap: 4px;
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 9px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.record-item.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  box-shadow: 0 0 0 1px var(--ov-focus-ring) inset;
}

.record-item__topline {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  justify-content: space-between;
}

.record-item__topline b,
.record-item__topline i {
  border-radius: 4px;
  padding: 2px 5px;
  font-size: 10px;
  font-style: normal;
  font-weight: 900;
}

.record-item__topline b {
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.record-item__topline i {
  background: var(--ov-bg-panel);
  color: var(--ov-text-secondary);
}

.record-item__topline .state-accepted,
.record-item__topline .state-modified {
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.record-item__topline .state-rejected {
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.record-item strong,
.record-item span,
.record-item small {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.record-item strong {
  color: var(--ov-text);
  font-size: 12px;
}

.record-item > span,
.record-item small {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.review-main {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.record-metadata {
  padding: 16px;
}

.seed-controls {
  display: grid;
  grid-template-columns: minmax(230px, 360px) 180px minmax(260px, auto);
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
}

.seed-controls > div {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.seed-controls > div span {
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.seed-controls input {
  width: 100%;
}

.seed-controls button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  border: 1px solid var(--ov-border-accent);
  border-radius: 5px;
  padding: 8px 11px;
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.seed-controls button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.seed-controls button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.seed-warning {
  border: 1px solid var(--ov-warning);
  border-radius: 5px;
  padding: 8px 10px;
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.seed-controls p {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--ov-text-muted);
  font-size: 10px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.metadata-header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.metadata-header span {
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 900;
}

.metadata-header h2 {
  margin: 3px 0 0;
  color: var(--ov-text);
  font-size: 17px;
  overflow-wrap: anywhere;
}

.record-navigation {
  display: flex;
  gap: 7px;
}

.record-metadata dl {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 5px 10px;
  margin: 0;
}

.record-metadata dt,
.record-metadata dd {
  min-width: 0;
  font-size: 11px;
  line-height: 1.5;
}

.record-metadata dt {
  color: var(--ov-text-muted);
  font-weight: 900;
}

.record-metadata dd {
  margin: 0;
  color: var(--ov-text-secondary);
  overflow-wrap: anywhere;
  white-space: normal;
}

.record-metadata a {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 4px 0;
  color: var(--ov-primary-strong);
  overflow-wrap: anywhere;
}

.medical-boundary,
.workspace-empty,
.empty-state {
  margin: 0;
  padding: 11px 12px;
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.workspace-empty {
  min-height: 380px;
  display: grid;
  place-items: center;
  color: var(--ov-text-secondary);
  font-size: 13px;
  font-weight: 900;
}
</style>
