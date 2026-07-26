<template>
  <section class="mask-editor" aria-label="骨面门控掩膜编辑器">
    <header>
      <div>
        <AppIcon name="target" />
        <strong>骨面掩膜编辑</strong>
      </div>
      <button type="button" @click="emit('cancel')">关闭</button>
    </header>
    <div class="editor-toolbar" aria-label="掩膜编辑工具">
      <button type="button" :class="{ selected: tool === 'add' }" :disabled="editorLocked" @click="tool = 'add'">添加</button>
      <button type="button" :class="{ selected: tool === 'erase' }" :disabled="editorLocked" @click="tool = 'erase'">擦除</button>
      <label>
        <span>画刷</span>
        <input v-model.number="brushSize" type="range" min="4" max="48" step="2" :disabled="editorLocked" />
      </label>
      <button type="button" :disabled="editorLocked || !canUndo" @click="undo">撤销</button>
      <button type="button" :disabled="editorLocked || !canRedo" @click="redo">重做</button>
      <button type="button" :disabled="editorLocked" @click="clearMask">清空</button>
      <select v-model="reviewState" aria-label="复核状态" :disabled="editorLocked">
        <option value="modified">已修改</option>
        <option value="accepted">接受</option>
        <option value="review_required">待复核</option>
        <option value="rejected">拒绝</option>
      </select>
      <button class="save-mask-button" type="button" :disabled="editorLocked" @click="save">
        {{ loading ? "正在保存..." : maskLoading ? "正在载入..." : "保存掩膜" }}
      </button>
    </div>
    <div class="editor-canvas-frame" :aria-busy="maskLoading">
      <img v-if="detail?.overlayHref" :src="detail.overlayHref" alt="当前关键帧叠加参考" />
      <canvas
        ref="canvasEl"
        width="256"
        height="192"
        aria-label="二值掩膜编辑画布"
        :aria-disabled="editorLocked"
        :class="{ 'is-locked': editorLocked }"
        @pointerdown="startStroke"
        @pointermove="moveStroke"
        @pointerup="endStroke"
        @pointerleave="endStroke"
      />
    </div>
    <p v-if="maskLoadError" class="editor-status error" role="alert">{{ maskLoadError }}</p>
    <p v-else class="editor-status" role="status">{{ editorStatus }}</p>
    <p>{{ detail?.boneGateStatusLabel ?? "待生成骨面门控" }}；保存后进入复核回灌清单。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { HotspotFrameDetail } from "@/components/analysisPreview";
import type { ReviewState } from "@/types/case";

const props = defineProps<{
  detail: HotspotFrameDetail | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  save: [payload: { maskPngBase64: string; reviewState: ReviewState; reviewerNotes: string }];
  cancel: [];
}>();

const canvasEl = ref<HTMLCanvasElement | null>(null);
const tool = ref<"add" | "erase">("add");
const brushSize = ref(18);
const reviewState = ref<ReviewState>("modified");
const drawing = ref(false);
const undoStack = ref<string[]>([]);
const redoStack = ref<string[]>([]);
const maskLoading = ref(false);
const maskReady = ref(false);
const maskLoadError = ref("");
const editorStatus = ref("正在准备骨面掩膜...");
let maskLoadRequestId = 0;
const canUndo = computed(() => undoStack.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);
const editorLocked = computed(() => props.loading || maskLoading.value || !maskReady.value);

watch(
  () => [props.detail?.key, props.detail?.boneGateMaskHref] as const,
  async () => {
    const requestId = ++maskLoadRequestId;
    drawing.value = false;
    maskLoading.value = false;
    maskReady.value = false;
    maskLoadError.value = "";
    editorStatus.value = "正在准备骨面掩膜...";
    await nextTick();
    resetCanvas();
    const maskHref = props.detail?.boneGateMaskHref;
    if (!maskHref) {
      maskLoadError.value = "当前关键帧没有可载入的骨面掩膜，请先生成骨面门控。";
      editorStatus.value = "掩膜未载入，编辑与保存已停用。";
      return;
    }
    maskLoading.value = true;
    editorStatus.value = "正在载入当前帧已有骨面掩膜...";
    try {
      const image = await loadImage(maskHref);
      if (requestId !== maskLoadRequestId) return;
      renderExistingMask(image);
      maskReady.value = true;
      editorStatus.value = "当前帧已有骨面掩膜已载入，可继续复核修改。";
    } catch {
      if (requestId !== maskLoadRequestId) return;
      resetCanvas();
      maskReady.value = false;
      maskLoadError.value = "已有骨面掩膜读取失败，画布保持锁定；请检查文件接口后重新打开编辑器。";
      editorStatus.value = "掩膜载入失败，保存已停用。";
    } finally {
      if (requestId === maskLoadRequestId) maskLoading.value = false;
    }
  },
  { immediate: true },
);

watch(
  () => props.loading,
  (loading) => {
    if (loading) drawing.value = false;
  },
);

function resetCanvas() {
  const context = canvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  undoStack.value = [];
  redoStack.value = [];
}

function startStroke(event: PointerEvent) {
  if (editorLocked.value) return;
  pushUndo();
  drawing.value = true;
  drawAt(event);
}

function moveStroke(event: PointerEvent) {
  if (!drawing.value || editorLocked.value) return;
  drawAt(event);
}

function endStroke() {
  drawing.value = false;
}

function drawAt(event: PointerEvent) {
  const context = canvasContext();
  const canvas = canvasEl.value;
  if (!context || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / Math.max(1, rect.width)) * canvas.width;
  const y = ((event.clientY - rect.top) / Math.max(1, rect.height)) * canvas.height;
  context.globalCompositeOperation = tool.value === "erase" ? "destination-out" : "source-over";
  context.fillStyle = "rgba(255, 182, 38, 0.88)";
  context.beginPath();
  context.arc(x, y, brushSize.value / 2, 0, Math.PI * 2);
  context.fill();
  context.globalCompositeOperation = "source-over";
}

function clearMask() {
  if (editorLocked.value) return;
  const context = canvasContext();
  if (!context) return;
  pushUndo();
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
}

function undo() {
  if (editorLocked.value) return;
  const canvas = canvasEl.value;
  if (!canvas || !undoStack.value.length) return;
  redoStack.value.push(canvas.toDataURL("image/png"));
  restore(undoStack.value.pop() ?? "");
}

function redo() {
  if (editorLocked.value) return;
  const canvas = canvasEl.value;
  if (!canvas || !redoStack.value.length) return;
  undoStack.value.push(canvas.toDataURL("image/png"));
  restore(redoStack.value.pop() ?? "");
}

function save() {
  if (editorLocked.value) return;
  const canvas = canvasEl.value;
  if (!canvas) return;
  try {
    emit("save", {
      maskPngBase64: canvas.toDataURL("image/png"),
      reviewState: reviewState.value,
      reviewerNotes: "frontend binary mask editor",
    });
  } catch {
    maskReady.value = false;
    maskLoadError.value = "骨面掩膜导出失败，保存已停用；请重新打开编辑器后再试。";
  }
}

function pushUndo() {
  const canvas = canvasEl.value;
  if (!canvas) return;
  undoStack.value.push(canvas.toDataURL("image/png"));
  redoStack.value = [];
}

function restore(dataUrl: string) {
  const context = canvasContext();
  if (!context || !dataUrl) return;
  const image = new Image();
  image.onload = () => {
    context.clearRect(0, 0, context.canvas.width, context.canvas.height);
    context.drawImage(image, 0, 0, context.canvas.width, context.canvas.height);
  };
  image.src = dataUrl;
}

function renderExistingMask(image: HTMLImageElement) {
  const context = canvasContext();
  if (!context) throw new Error("mask_canvas_unavailable");
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  context.drawImage(image, 0, 0, context.canvas.width, context.canvas.height);
  const source = context.getImageData(0, 0, context.canvas.width, context.canvas.height);
  const overlay = context.createImageData(context.canvas.width, context.canvas.height);
  for (let index = 0; index < source.data.length; index += 4) {
    const luminance = (source.data[index] + source.data[index + 1] + source.data[index + 2]) / 3;
    if (luminance <= 127) continue;
    overlay.data[index] = 255;
    overlay.data[index + 1] = 182;
    overlay.data[index + 2] = 38;
    overlay.data[index + 3] = 224;
  }
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  context.putImageData(overlay, 0, 0);
  undoStack.value = [];
  redoStack.value = [];
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("bone_gate_mask_load_failed"));
    image.src = url;
  });
}

function canvasContext(): CanvasRenderingContext2D | null {
  return canvasEl.value?.getContext("2d") ?? null;
}
</script>

<style scoped>
.mask-editor {
  display: grid;
  gap: 9px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 10px;
  background: var(--ov-bg-soft);
}

.mask-editor header,
.mask-editor header div,
.editor-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.mask-editor header {
  justify-content: space-between;
}

.mask-editor header strong {
  color: var(--ov-text);
  font-size: 13px;
}

.mask-editor button,
.mask-editor select {
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 5px 8px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 850;
}

.mask-editor button.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.editor-toolbar label {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.editor-canvas-frame {
  position: relative;
  overflow: hidden;
  width: min(100%, 420px);
  aspect-ratio: 4 / 3;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  background: var(--ov-bg-media);
}

.editor-canvas-frame img,
.editor-canvas-frame canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.editor-canvas-frame img {
  object-fit: contain;
  opacity: 0.78;
}

.editor-canvas-frame canvas {
  touch-action: none;
  cursor: crosshair;
}

.editor-canvas-frame canvas.is-locked {
  cursor: wait;
  pointer-events: none;
}

.mask-editor p {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.mask-editor .editor-status.error {
  color: var(--ov-danger);
  font-weight: 800;
}
</style>
