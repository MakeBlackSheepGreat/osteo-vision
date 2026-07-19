<template>
  <section class="static-mask-editor" aria-label="静态图像二值掩膜编辑器">
    <header class="editor-header">
      <div>
        <span class="editor-kicker">像素级复核</span>
        <strong>{{ record.title || record.source_record_id || record.record_id }}</strong>
      </div>
      <span class="dimension-label">{{ dimensionLabel }}</span>
    </header>

    <div class="editor-toolbar" aria-label="掩膜编辑工具">
      <button
        type="button"
        :class="{ selected: tool === 'add' }"
        :disabled="editingDisabled"
        :title="toolTitle('添加掩膜')"
        @click="tool = 'add'"
      >
        <AppIcon name="brush" />
        添加
      </button>
      <button
        type="button"
        :class="{ selected: tool === 'erase' }"
        :disabled="editingDisabled"
        :title="toolTitle('擦除掩膜')"
        @click="tool = 'erase'"
      >
        <AppIcon name="trash" />
        擦除
      </button>
      <label class="brush-control" :title="toolTitle('调整画刷大小')">
        <span>画刷 {{ brushSize }} px</span>
        <input v-model.number="brushSize" type="range" min="4" max="120" step="2" :disabled="editingDisabled" />
      </label>
      <button type="button" :title="undoTitle" aria-label="撤销" :disabled="!canUndo || editingDisabled" @click="undo">
        <AppIcon name="undo" />
      </button>
      <button type="button" :title="redoTitle" aria-label="重做" :disabled="!canRedo || editingDisabled" @click="redo">
        <AppIcon name="redo" />
      </button>
      <button type="button" :title="toolTitle('清空掩膜')" :disabled="editingDisabled" @click="clearMask">
        <AppIcon name="trash" />
        清空
      </button>
    </div>

    <div class="canvas-stage" :style="stageStyle">
      <img
        ref="sourceImageEl"
        :src="sourceUrl"
        alt="待复核荧光论文裁剪图"
        crossorigin="anonymous"
        @load="handleSourceLoad"
        @error="handleSourceError"
      />
      <canvas
        ref="canvasEl"
        :width="canvasWidth"
        :height="canvasHeight"
        aria-label="按原始图像像素坐标编辑的二值掩膜"
        @pointerdown="startStroke"
        @pointermove="moveStroke"
        @pointerup="endStroke"
        @pointercancel="endStroke"
        @pointerleave="endStroke"
      />
      <div v-if="imageError" class="canvas-error" role="alert">{{ imageError }}</div>
    </div>

    <div class="review-form">
      <label>
        <span>复核身份</span>
        <select v-model="reviewerRole" :disabled="editingDisabled">
          <option value="project_reviewer">项目复核人员</option>
          <option value="physician">医生</option>
        </select>
      </label>
      <label>
        <span>复核结论</span>
        <select v-model="reviewState" :disabled="editingDisabled">
          <option value="accepted">接受</option>
          <option value="modified">已修改</option>
          <option value="rejected">拒绝</option>
        </select>
      </label>
      <label class="notes-field">
        <span>复核备注</span>
        <textarea
          v-model="reviewerNotes"
          rows="3"
          :disabled="editingDisabled"
          placeholder="记录修改依据、可疑区域或拒绝原因"
        />
      </label>
      <button
        class="save-button"
        type="button"
        :disabled="editingDisabled"
        :title="editingDisabledReason || '保存复核结果'"
        @click="save"
      >
        <AppIcon name="check" />
        {{ loading ? "正在处理..." : "保存复核结果" }}
      </button>
    </div>

    <p class="editor-status" :class="{ error: Boolean(maskLoadError) }">
      {{ maskLoadError || editorStatus }}
    </p>
    <p class="identity-boundary">
      项目复核人员提交的数据保留人工工程复核标识；选择“医生”仅适用于实际由医生完成的复核记录。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { ReviewState } from "@/types/case";
import type { DatasetReviewRecord } from "@/types/datasetReview";

const props = defineProps<{
  record: DatasetReviewRecord;
  sourceUrl: string;
  maskUrl?: string;
  loading?: boolean;
  disabledReason?: string;
}>();

const emit = defineEmits<{
  save: [payload: {
    maskPngBase64: string;
    reviewState: ReviewState;
    reviewerNotes: string;
    reviewerRole: "project_reviewer" | "physician";
  }];
}>();

const sourceImageEl = ref<HTMLImageElement | null>(null);
const canvasEl = ref<HTMLCanvasElement | null>(null);
const canvasWidth = ref(1);
const canvasHeight = ref(1);
const tool = ref<"add" | "erase">("add");
const brushSize = ref(36);
const reviewState = ref<ReviewState>("modified");
const reviewerNotes = ref("");
const reviewerRole = ref<"project_reviewer" | "physician">("project_reviewer");
const drawing = ref(false);
const lastPoint = ref<{ x: number; y: number } | null>(null);
const imageReady = ref(false);
const imageError = ref("");
const maskLoadError = ref("");
const maskLoadState = ref<"idle" | "loading" | "ready" | "error">("idle");
const editorStatus = ref("正在读取原始裁剪图...");
const undoStack = ref<ImageData[]>([]);
const redoStack = ref<ImageData[]>([]);
let maskLoadRequest = 0;

const canUndo = computed(() => undoStack.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);
const editingDisabledReason = computed(() => {
  if (props.loading) return props.disabledReason || "正在处理复核写入，编辑工具暂不可用。";
  if (imageError.value) return "原始裁剪图读取失败，编辑工具暂不可用。";
  if (!imageReady.value) return "原始裁剪图尚未载入，编辑工具暂不可用。";
  if (maskLoadState.value === "loading") return "正在载入已有复核掩膜，编辑和保存暂不可用。";
  if (maskLoadState.value === "error") return maskLoadError.value || "已有复核掩膜读取失败，编辑和保存已停用。";
  return "";
});
const editingDisabled = computed(() => Boolean(editingDisabledReason.value));
const undoTitle = computed(() => editingDisabledReason.value || (canUndo.value ? "撤销" : "暂无可撤销操作"));
const redoTitle = computed(() => editingDisabledReason.value || (canRedo.value ? "重做" : "暂无可重做操作"));
const stageStyle = computed(() => ({ aspectRatio: `${canvasWidth.value} / ${canvasHeight.value}` }));
const dimensionLabel = computed(() =>
  imageReady.value ? `${canvasWidth.value} × ${canvasHeight.value} 原始像素` : "待读取原始尺寸",
);

watch(
  () => props.record.record_id,
  async () => {
    reviewState.value = props.record.review_state === "review_required" ? "modified" : props.record.review_state;
    reviewerNotes.value = props.record.reviewer_notes || "";
    reviewerRole.value = props.record.reviewer_role === "physician" || props.record.physician_reviewed
      ? "physician"
      : "project_reviewer";
    canvasWidth.value = positiveDimension(props.record.width) || 1;
    canvasHeight.value = positiveDimension(props.record.height) || 1;
    imageReady.value = false;
    imageError.value = "";
    maskLoadError.value = "";
    maskLoadState.value = "idle";
    maskLoadRequest += 1;
    editorStatus.value = "正在读取原始裁剪图...";
    undoStack.value = [];
    redoStack.value = [];
    await nextTick();
    clearCanvasWithoutHistory();
  },
  { immediate: true },
);

async function handleSourceLoad(event: Event) {
  const requestId = ++maskLoadRequest;
  const image = event.currentTarget as HTMLImageElement;
  canvasWidth.value = image.naturalWidth || positiveDimension(props.record.width) || 1;
  canvasHeight.value = image.naturalHeight || positiveDimension(props.record.height) || 1;
  imageReady.value = true;
  imageError.value = "";
  maskLoadState.value = props.maskUrl ? "loading" : "ready";
  await nextTick();
  clearCanvasWithoutHistory();
  if (props.maskUrl) {
    editorStatus.value = "正在载入已有复核掩膜...";
    await loadExistingMask(props.maskUrl, requestId);
  } else {
    maskLoadState.value = "ready";
    editorStatus.value = "原始裁剪图已载入，可开始描画。";
  }
}

function handleSourceError() {
  maskLoadRequest += 1;
  imageReady.value = false;
  imageError.value = "原始裁剪图读取失败，请检查后端文件接口和源文件路径。";
  maskLoadState.value = "error";
  editorStatus.value = "图像未载入，保存已停用。";
}

function startStroke(event: PointerEvent) {
  if (editingDisabled.value) return;
  pushUndo();
  drawing.value = true;
  const point = pointerPoint(event);
  lastPoint.value = point;
  drawSegment(point, point);
}

function moveStroke(event: PointerEvent) {
  if (!drawing.value || editingDisabled.value || !lastPoint.value) return;
  const point = pointerPoint(event);
  drawSegment(lastPoint.value, point);
  lastPoint.value = point;
}

function endStroke() {
  drawing.value = false;
  lastPoint.value = null;
}

function drawSegment(from: { x: number; y: number }, to: { x: number; y: number }) {
  const context = canvasContext();
  if (!context) return;
  context.save();
  context.globalCompositeOperation = tool.value === "erase" ? "destination-out" : "source-over";
  context.strokeStyle = "rgba(255, 178, 38, 0.82)";
  context.fillStyle = "rgba(255, 178, 38, 0.82)";
  context.lineWidth = brushSize.value;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
  context.beginPath();
  context.arc(to.x, to.y, brushSize.value / 2, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function pointerPoint(event: PointerEvent): { x: number; y: number } {
  const canvas = canvasEl.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / Math.max(1, rect.width)) * canvas.width,
    y: ((event.clientY - rect.top) / Math.max(1, rect.height)) * canvas.height,
  };
}

function clearMask() {
  if (editingDisabled.value) return;
  pushUndo();
  clearCanvasWithoutHistory();
  editorStatus.value = "掩膜已清空，保存前仍可撤销。";
}

function clearCanvasWithoutHistory() {
  const context = canvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
}

function pushUndo() {
  const snapshot = canvasSnapshot();
  if (!snapshot) return;
  undoStack.value.push(snapshot);
  const bytesPerSnapshot = Math.max(1, canvasWidth.value * canvasHeight.value * 4);
  const historyLimit = Math.max(3, Math.min(30, Math.floor((96 * 1024 * 1024) / bytesPerSnapshot)));
  while (undoStack.value.length > historyLimit) undoStack.value.shift();
  redoStack.value = [];
}

function undo() {
  if (editingDisabled.value) return;
  const snapshot = canvasSnapshot();
  const previous = undoStack.value.pop();
  if (!snapshot || !previous) return;
  redoStack.value.push(snapshot);
  restoreSnapshot(previous);
}

function redo() {
  if (editingDisabled.value) return;
  const snapshot = canvasSnapshot();
  const next = redoStack.value.pop();
  if (!snapshot || !next) return;
  undoStack.value.push(snapshot);
  restoreSnapshot(next);
}

function canvasSnapshot(): ImageData | null {
  const context = canvasContext();
  if (!context) return null;
  return context.getImageData(0, 0, context.canvas.width, context.canvas.height);
}

function restoreSnapshot(snapshot: ImageData) {
  const context = canvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  context.putImageData(snapshot, 0, 0);
}

async function loadExistingMask(url: string, requestId: number): Promise<void> {
  maskLoadError.value = "";
  try {
    const maskImage = await loadImage(url);
    if (requestId !== maskLoadRequest) return;
    const context = canvasContext();
    if (!context) throw new Error("mask_canvas_unavailable");
    context.clearRect(0, 0, context.canvas.width, context.canvas.height);
    context.drawImage(maskImage, 0, 0, context.canvas.width, context.canvas.height);
    const source = context.getImageData(0, 0, context.canvas.width, context.canvas.height);
    const overlay = context.createImageData(context.canvas.width, context.canvas.height);
    for (let index = 0; index < source.data.length; index += 4) {
      const luminance = (source.data[index] + source.data[index + 1] + source.data[index + 2]) / 3;
      if (luminance <= 127) continue;
      overlay.data[index] = 255;
      overlay.data[index + 1] = 178;
      overlay.data[index + 2] = 38;
      overlay.data[index + 3] = 210;
    }
    context.clearRect(0, 0, context.canvas.width, context.canvas.height);
    context.putImageData(overlay, 0, 0);
    undoStack.value = [];
    redoStack.value = [];
    maskLoadState.value = "ready";
    editorStatus.value = "已有复核掩膜已载入，可继续修改。";
  } catch {
    if (requestId !== maskLoadRequest) return;
    clearCanvasWithoutHistory();
    maskLoadState.value = "error";
    maskLoadError.value = "已有复核掩膜读取失败，编辑和保存已停用；请重新载入当前记录。";
  }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("mask_load_failed"));
    image.src = url;
  });
}

function save() {
  if (editingDisabled.value) return;
  const maskPngBase64 = exportBinaryPng();
  if (!maskPngBase64) {
    maskLoadError.value = "二值掩膜导出失败，请重新载入当前记录后再试。";
    return;
  }
  emit("save", {
    maskPngBase64,
    reviewState: reviewState.value,
    reviewerNotes: reviewerNotes.value.trim(),
    reviewerRole: reviewerRole.value,
  });
}

function exportBinaryPng(): string {
  const sourceContext = canvasContext();
  if (!sourceContext) return "";
  const source = sourceContext.getImageData(0, 0, sourceContext.canvas.width, sourceContext.canvas.height);
  const binaryCanvas = document.createElement("canvas");
  binaryCanvas.width = sourceContext.canvas.width;
  binaryCanvas.height = sourceContext.canvas.height;
  const binaryContext = binaryCanvas.getContext("2d");
  if (!binaryContext) return "";
  const binary = binaryContext.createImageData(binaryCanvas.width, binaryCanvas.height);
  for (let index = 0; index < source.data.length; index += 4) {
    const active = source.data[index + 3] > 0;
    const value = active ? 255 : 0;
    binary.data[index] = value;
    binary.data[index + 1] = value;
    binary.data[index + 2] = value;
    binary.data[index + 3] = 255;
  }
  binaryContext.putImageData(binary, 0, 0);
  return binaryCanvas.toDataURL("image/png");
}

function canvasContext(): CanvasRenderingContext2D | null {
  return canvasEl.value?.getContext("2d", { willReadFrequently: true }) ?? null;
}

function positiveDimension(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.round(value) : 0;
}

function toolTitle(enabledTitle: string): string {
  return editingDisabledReason.value || enabledTitle;
}
</script>

<style scoped>
.static-mask-editor {
  display: grid;
  gap: 12px;
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 14px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  box-shadow: var(--ov-shadow-strong);
}

.editor-header,
.editor-toolbar,
.review-form {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
}

.editor-header {
  justify-content: space-between;
}

.editor-header > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.editor-header strong,
.dimension-label {
  overflow-wrap: anywhere;
}

.editor-header strong {
  color: var(--ov-text);
  font-size: 16px;
}

.editor-kicker,
.dimension-label,
.review-form label > span {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 900;
}

.editor-toolbar {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 8px;
  background: var(--ov-bg-soft);
}

.editor-toolbar button,
.save-button {
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

.editor-toolbar button.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  color: var(--ov-primary);
}

.editor-toolbar button:disabled,
.save-button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.editor-toolbar :deep(.app-icon),
.save-button :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.brush-control {
  display: grid;
  gap: 3px;
  min-width: 190px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.brush-control input {
  width: 100%;
}

.canvas-stage {
  position: relative;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  background: var(--ov-bg-media);
}

.canvas-stage img,
.canvas-stage canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.canvas-stage img {
  object-fit: contain;
}

.canvas-stage canvas {
  touch-action: none;
  cursor: crosshair;
}

.canvas-error {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(48, 8, 14, 0.88);
  color: #ffd3d6;
  font-weight: 900;
  text-align: center;
}

.review-form {
  align-items: end;
}

.review-form label {
  display: grid;
  gap: 5px;
}

.review-form select,
.review-form textarea {
  min-height: 38px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 7px 9px;
  background: var(--ov-bg-control);
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.notes-field {
  flex: 1 1 420px;
}

.review-form textarea {
  width: 100%;
  resize: vertical;
  overflow-wrap: anywhere;
}

.save-button {
  min-height: 58px;
  border-color: var(--ov-button-primary-bg);
  padding: 10px 16px;
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
}

.editor-status {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.editor-status.error {
  color: var(--ov-danger);
}

.identity-boundary {
  margin: -4px 0 0;
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.editor-toolbar button:not(:disabled):hover {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-hover);
}

.save-button:not(:disabled):hover {
  border-color: var(--ov-button-primary-hover);
  background: var(--ov-button-primary-hover);
}

.editor-toolbar button:focus-visible,
.review-form select:focus-visible,
.review-form textarea:focus-visible,
.save-button:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 1px;
}
</style>
