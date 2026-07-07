<template>
  <section class="mask-editor" aria-label="骨面门控 mask 编辑器">
    <header>
      <div>
        <AppIcon name="target" />
        <strong>骨面 mask 编辑</strong>
      </div>
      <button type="button" @click="emit('cancel')">关闭</button>
    </header>
    <div class="editor-toolbar" aria-label="mask 编辑工具">
      <button type="button" :class="{ selected: tool === 'add' }" @click="tool = 'add'">添加</button>
      <button type="button" :class="{ selected: tool === 'erase' }" @click="tool = 'erase'">擦除</button>
      <label>
        <span>画刷</span>
        <input v-model.number="brushSize" type="range" min="4" max="48" step="2" />
      </label>
      <button type="button" :disabled="!canUndo" @click="undo">撤销</button>
      <button type="button" :disabled="!canRedo" @click="redo">重做</button>
      <button type="button" @click="clearMask">清空</button>
      <select v-model="reviewState" aria-label="复核状态">
        <option value="modified">已修改</option>
        <option value="accepted">接受</option>
        <option value="review_required">待复核</option>
        <option value="rejected">拒绝</option>
      </select>
      <button type="button" :disabled="loading" @click="save">保存 mask</button>
    </div>
    <div class="editor-canvas-frame">
      <img v-if="detail?.overlayHref" :src="detail.overlayHref" alt="当前关键帧叠加参考" />
      <canvas
        ref="canvasEl"
        width="256"
        height="192"
        aria-label="二值 mask 编辑画布"
        @pointerdown="startStroke"
        @pointermove="moveStroke"
        @pointerup="endStroke"
        @pointerleave="endStroke"
      />
    </div>
    <p>{{ detail?.boneGateStatusLabel ?? "待生成骨面门控" }}；保存后进入复核回灌 manifest。</p>
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
const canUndo = computed(() => undoStack.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);

watch(
  () => props.detail?.key,
  async () => {
    await nextTick();
    resetCanvas();
  },
  { immediate: true },
);

function resetCanvas() {
  const context = canvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  undoStack.value = [];
  redoStack.value = [];
}

function startStroke(event: PointerEvent) {
  if (props.loading) return;
  pushUndo();
  drawing.value = true;
  drawAt(event);
}

function moveStroke(event: PointerEvent) {
  if (!drawing.value || props.loading) return;
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
  const context = canvasContext();
  if (!context) return;
  pushUndo();
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
}

function undo() {
  const canvas = canvasEl.value;
  if (!canvas || !undoStack.value.length) return;
  redoStack.value.push(canvas.toDataURL("image/png"));
  restore(undoStack.value.pop() ?? "");
}

function redo() {
  const canvas = canvasEl.value;
  if (!canvas || !redoStack.value.length) return;
  undoStack.value.push(canvas.toDataURL("image/png"));
  restore(redoStack.value.pop() ?? "");
}

function save() {
  const canvas = canvasEl.value;
  if (!canvas) return;
  emit("save", {
    maskPngBase64: canvas.toDataURL("image/png"),
    reviewState: reviewState.value,
    reviewerNotes: "frontend binary mask editor",
  });
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

function canvasContext(): CanvasRenderingContext2D | null {
  return canvasEl.value?.getContext("2d") ?? null;
}
</script>

<style scoped>
.mask-editor {
  display: grid;
  gap: 9px;
  border: 1px solid #d7e3ef;
  border-radius: 6px;
  padding: 10px;
  background: #fbfdff;
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
  color: #102136;
  font-size: 13px;
}

.mask-editor button,
.mask-editor select {
  border: 1px solid #cdd9e6;
  border-radius: 5px;
  padding: 5px 8px;
  background: #ffffff;
  color: #1b2d40;
  font-size: 12px;
  font-weight: 850;
}

.mask-editor button.selected {
  border-color: #2c7ec0;
  background: #eaf4ff;
  color: #155b94;
}

.editor-toolbar label {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: #4d6073;
  font-size: 12px;
  font-weight: 850;
}

.editor-canvas-frame {
  position: relative;
  overflow: hidden;
  width: min(100%, 420px);
  aspect-ratio: 4 / 3;
  border: 1px solid #ccd9e6;
  border-radius: 6px;
  background: #0f1b25;
}

.editor-canvas-frame img,
.editor-canvas-frame canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.editor-canvas-frame img {
  object-fit: cover;
  opacity: 0.78;
}

.editor-canvas-frame canvas {
  touch-action: none;
  cursor: crosshair;
}

.mask-editor p {
  margin: 0;
  color: #5d6e7f;
  font-size: 12px;
  line-height: 1.5;
}
</style>
