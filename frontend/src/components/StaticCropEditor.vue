<template>
  <section class="crop-editor" aria-label="论文原图裁剪">
    <header>
      <div>
        <span>原图面板处理</span>
        <h3>裁剪范围与双通道配对</h3>
      </div>
      <strong>{{ selection.width }} × {{ selection.height }} px</strong>
    </header>

    <div class="canvas-shell">
      <canvas
        ref="canvasRef"
        :aria-disabled="loading"
        :class="{ 'is-locked': loading }"
        @pointerdown="startSelection"
        @pointermove="updateSelection"
        @pointerup="finishSelection"
        @pointercancel="finishSelection"
      />
    </div>

    <section v-if="hasSuggestion" class="suggestion-summary" :class="`state-${suggestionStatus}`">
      <div>
        <strong>自动面板建议 {{ Math.round((record.suggestion_score || 0) * 100) }}%</strong>
        <span>{{ record.suggestion_method || "未记录检测方法" }}</span>
      </div>
      <p>橙色虚线为原始建议，绿色实线为当前裁剪。自动建议仍需人工接受或修改。</p>
      <ul v-if="suggestionWarnings.length">
        <li v-for="warning in suggestionWarnings" :key="warning">{{ warningLabel(warning) }}</li>
      </ul>
    </section>

    <div class="crop-fields">
      <label><span>X</span><input v-model.number="selection.x" type="number" min="0" :disabled="loading" @change="normalizeSelection" /></label>
      <label><span>Y</span><input v-model.number="selection.y" type="number" min="0" :disabled="loading" @change="normalizeSelection" /></label>
      <label><span>宽度</span><input v-model.number="selection.width" type="number" min="16" :disabled="loading" @change="normalizeSelection" /></label>
      <label><span>高度</span><input v-model.number="selection.height" type="number" min="16" :disabled="loading" @change="normalizeSelection" /></label>
      <label>
        <span>面板类型</span>
        <select v-model="panelRole" :disabled="loading">
          <option value="fluorescence_signal">荧光信号</option>
          <option value="white_light">白光</option>
          <option value="paired_fluorescence">配对荧光</option>
          <option value="paired_white_light">配对白光</option>
          <option value="histopathology">病理</option>
          <option value="unclassified">待分类</option>
        </select>
      </label>
      <label>
        <span>配对 ID</span>
        <input v-model.trim="pairId" type="text" :disabled="loading" placeholder="同一白光/荧光视野使用相同 ID" />
      </label>
    </div>

    <label class="notes-field">
      <span>裁剪备注</span>
      <textarea v-model.trim="cropNotes" rows="2" :disabled="loading" />
    </label>

    <footer>
      <button type="button" :disabled="loading || !imageReady" @click="selectFullImage">
        <AppIcon name="expand" />
        全图
      </button>
      <button
        v-if="hasSuggestion"
        type="button"
        :disabled="loading || !canSave || suggestionStatus === 'blocked'"
        @click="acceptSuggestion"
      >
        <AppIcon name="check" />
        接受建议
      </button>
      <button class="primary" type="button" :disabled="loading || !canSave" @click="saveModifiedCrop">
        <AppIcon name="check" />
        {{ loading ? "正在保存..." : "保存修改" }}
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { DatasetReviewCropRequest, DatasetReviewRecord } from "@/types/datasetReview";

const props = defineProps<{
  record: DatasetReviewRecord;
  sourceUrl: string;
  loading?: boolean;
}>();
const emit = defineEmits<{
  save: [payload: DatasetReviewCropRequest];
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const imageReady = ref(false);
const sourceWidth = ref(0);
const sourceHeight = ref(0);
const panelRole = ref(props.record.panel_role || props.record.suggested_panel_role || "unclassified");
const pairId = ref(props.record.pair_id || props.record.suggested_pair_id || "");
const cropNotes = ref(props.record.crop_notes || "");
const selection = reactive({ x: 0, y: 0, width: 16, height: 16 });
let sourceImage: HTMLImageElement | null = null;
let dragStart: { x: number; y: number } | null = null;
let imageLoadRequestId = 0;

const canSave = computed(
  () => imageReady.value && selection.width >= 16 && selection.height >= 16,
);
const hasSuggestion = computed(() => Boolean(props.record.suggestion_id && props.record.suggested_crop_bbox));
const suggestionStatus = computed(() => props.record.suggestion_quality_status || "warning");
const suggestionWarnings = computed(() => props.record.suggestion_quality_warnings || []);

watch(
  () => props.sourceUrl,
  () => void loadImage(),
);

watch(
  () => props.loading,
  (loading) => {
    if (loading) dragStart = null;
  },
);

onMounted(() => void loadImage());

async function loadImage() {
  const requestId = ++imageLoadRequestId;
  imageReady.value = false;
  sourceImage = null;
  const image = new Image();
  image.decoding = "async";
  image.onload = async () => {
    if (requestId !== imageLoadRequestId) return;
    sourceImage = image;
    sourceWidth.value = image.naturalWidth;
    sourceHeight.value = image.naturalHeight;
    const existing = props.record.crop_bbox || props.record.suggested_crop_bbox;
    if (existing) {
      Object.assign(selection, existing);
    } else {
      Object.assign(selection, {
        x: 0,
        y: 0,
        width: image.naturalWidth,
        height: image.naturalHeight,
      });
    }
    imageReady.value = true;
    await nextTick();
    if (requestId !== imageLoadRequestId) return;
    drawCanvas();
  };
  image.onerror = () => {
    if (requestId !== imageLoadRequestId) return;
    imageReady.value = false;
  };
  image.src = props.sourceUrl;
}

function pointerPosition(event: PointerEvent) {
  const canvas = canvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: Math.round(((event.clientX - rect.left) / rect.width) * canvas.width),
    y: Math.round(((event.clientY - rect.top) / rect.height) * canvas.height),
  };
}

function startSelection(event: PointerEvent) {
  if (props.loading || !imageReady.value) return;
  const canvas = canvasRef.value;
  canvas?.setPointerCapture(event.pointerId);
  dragStart = pointerPosition(event);
  Object.assign(selection, { x: dragStart.x, y: dragStart.y, width: 16, height: 16 });
  normalizeSelection();
}

function updateSelection(event: PointerEvent) {
  if (props.loading || !dragStart) return;
  const point = pointerPosition(event);
  Object.assign(selection, {
    x: Math.min(dragStart.x, point.x),
    y: Math.min(dragStart.y, point.y),
    width: Math.max(16, Math.abs(point.x - dragStart.x)),
    height: Math.max(16, Math.abs(point.y - dragStart.y)),
  });
  normalizeSelection();
}

function finishSelection(event: PointerEvent) {
  canvasRef.value?.releasePointerCapture(event.pointerId);
  dragStart = null;
  if (props.loading) return;
  normalizeSelection();
}

function normalizeSelection() {
  if (props.loading) return;
  selection.x = Math.max(0, Math.min(Math.round(selection.x || 0), Math.max(0, sourceWidth.value - 16)));
  selection.y = Math.max(0, Math.min(Math.round(selection.y || 0), Math.max(0, sourceHeight.value - 16)));
  selection.width = Math.max(16, Math.min(Math.round(selection.width || 16), sourceWidth.value - selection.x));
  selection.height = Math.max(16, Math.min(Math.round(selection.height || 16), sourceHeight.value - selection.y));
  drawCanvas();
}

function selectFullImage() {
  if (props.loading) return;
  Object.assign(selection, { x: 0, y: 0, width: sourceWidth.value, height: sourceHeight.value });
  drawCanvas();
}

function drawCanvas() {
  const canvas = canvasRef.value;
  const image = sourceImage;
  if (!canvas || !image) return;
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.drawImage(image, 0, 0);
  context.fillStyle = "rgba(2, 11, 18, 0.58)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  const suggested = props.record.suggested_crop_bbox;
  if (suggested) {
    context.save();
    context.strokeStyle = "#ffbd66";
    context.setLineDash([12, 8]);
    context.lineWidth = Math.max(2, Math.round(Math.max(canvas.width, canvas.height) / 550));
    context.strokeRect(suggested.x, suggested.y, suggested.width, suggested.height);
    context.restore();
  }
  context.drawImage(
    image,
    selection.x,
    selection.y,
    selection.width,
    selection.height,
    selection.x,
    selection.y,
    selection.width,
    selection.height,
  );
  context.strokeStyle = "#62e6b4";
  context.lineWidth = Math.max(2, Math.round(Math.max(canvas.width, canvas.height) / 500));
  context.strokeRect(selection.x, selection.y, selection.width, selection.height);
}

function emitCrop(cropReviewAction: "accepted" | "modified") {
  if (props.loading) return;
  normalizeSelection();
  emit("save", {
    ...selection,
    panel_role: panelRole.value,
    pair_id: pairId.value || null,
    crop_notes: cropNotes.value || null,
    suggestion_id: props.record.suggestion_id || null,
    crop_review_action: cropReviewAction,
  });
}

function acceptSuggestion() {
  if (props.loading) return;
  const suggested = props.record.suggested_crop_bbox;
  if (!suggested) return;
  Object.assign(selection, suggested);
  panelRole.value = props.record.suggested_panel_role || panelRole.value;
  pairId.value = props.record.suggested_pair_id || pairId.value;
  drawCanvas();
  emitCrop("accepted");
}

function saveModifiedCrop() {
  if (props.loading) return;
  emitCrop("modified");
}

function warningLabel(value: string) {
  const labels: Record<string, string> = {
    crop_dimension_below_96px: "面板短边小于 96 px，细节有限。",
    crop_area_below_2_percent: "面板面积低于原图 2%。",
    crop_near_full_source_image: "裁剪接近整张原图，请确认相邻面板已排除。",
    crop_extreme_aspect_ratio: "面板长宽比异常。",
    crop_high_white_background_fraction: "面板白色背景占比较高。",
    crop_white_border_residue: "面板边缘可能残留白色分隔带。",
    crop_black_border_residue: "面板边缘可能残留黑色边框。",
    crop_out_of_bounds: "建议范围越界，必须人工修改。",
  };
  return labels[value] || value;
}
</script>

<style scoped>
.crop-editor {
  display: grid;
  gap: 12px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 12px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  box-shadow: var(--ov-shadow);
}

header,
footer {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

header span,
label span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

h3 {
  margin: 3px 0 0;
  color: var(--ov-text);
  font-size: 16px;
  letter-spacing: 0;
}

header strong {
  color: var(--ov-success);
  font-size: 13px;
}

.canvas-shell {
  overflow: auto;
  max-height: 620px;
  border: 1px solid var(--ov-border-strong);
  background: var(--ov-bg-media);
}

.suggestion-summary {
  display: grid;
  gap: 6px;
  border-left: 3px solid var(--ov-warning);
  padding: 9px 11px;
  background: var(--ov-bg-warning);
  color: var(--ov-text);
}

.suggestion-summary div {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.suggestion-summary strong,
.suggestion-summary span,
.suggestion-summary p,
.suggestion-summary ul {
  margin: 0;
  overflow-wrap: anywhere;
}

.suggestion-summary span,
.suggestion-summary p,
.suggestion-summary li {
  color: var(--ov-text-secondary);
  font-size: 12px;
}

.suggestion-summary.state-blocked {
  border-left-color: var(--ov-danger);
  background: var(--ov-bg-danger);
}

canvas {
  display: block;
  width: 100%;
  height: auto;
  cursor: crosshair;
  touch-action: none;
}

canvas.is-locked {
  cursor: wait;
  pointer-events: none;
}

.crop-fields {
  display: grid;
  grid-template-columns: repeat(4, minmax(90px, 0.55fr)) minmax(180px, 1fr) minmax(220px, 1.3fr);
  gap: 8px;
}

label {
  display: grid;
  gap: 4px;
  min-width: 0;
}

input,
select,
textarea {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
  overflow-wrap: anywhere;
}

textarea {
  resize: vertical;
}

button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 11px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

button.primary {
  border-color: var(--ov-button-primary-bg);
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
}

button:not(:disabled):hover {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-hover);
}

button.primary:not(:disabled):hover {
  border-color: var(--ov-button-primary-hover);
  background: var(--ov-button-primary-hover);
}

input:focus-visible,
select:focus-visible,
textarea:focus-visible,
button:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 1px;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

@media (max-width: 1180px) {
  .crop-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
