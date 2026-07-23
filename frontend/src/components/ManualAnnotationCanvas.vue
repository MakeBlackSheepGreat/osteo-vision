<template>
  <section class="annotation-canvas" aria-label="病灶人工标注画布">
    <header class="annotation-canvas__header">
      <div>
        <span>原始像素标注</span>
        <strong>{{ sourceTitle || "待选择标注来源" }}</strong>
      </div>
      <div class="annotation-canvas__meta">
        <span>{{ dimensionLabel }}</span>
        <span>{{ operationCount }} 个标注操作</span>
        <span>{{ zoomLabel }}</span>
      </div>
    </header>

    <div class="annotation-toolbar" aria-label="人工标注工具栏">
      <div class="annotation-toolbar__group" role="group" aria-label="绘制工具">
        <button
          type="button"
          :class="{ selected: tool === 'brush' }"
          :disabled="editingDisabled"
          :title="toolTitle('画笔')"
          aria-label="画笔"
          @click="selectTool('brush')"
        >
          <AppIcon name="brush" />
        </button>
        <button
          type="button"
          :class="{ selected: tool === 'eraser' }"
          :disabled="editingDisabled"
          :title="toolTitle('橡皮擦')"
          aria-label="橡皮擦"
          @click="selectTool('eraser')"
        >
          <AppIcon name="trash" />
        </button>
        <button
          type="button"
          :class="{ selected: tool === 'polygon' }"
          :disabled="editingDisabled"
          :title="toolTitle('多边形')"
          aria-label="多边形"
          @click="selectTool('polygon')"
        >
          <AppIcon name="polygon" />
        </button>
        <button
          type="button"
          :class="{ selected: tool === 'pan' }"
          :disabled="!imageReady"
          :title="imageReady ? '平移画布' : '请先选择标注来源'"
          aria-label="平移画布"
          @click="selectTool('pan')"
        >
          <AppIcon name="move" />
        </button>
      </div>

      <label class="brush-size" :title="toolTitle('调整画笔直径')">
        <span>直径 {{ brushDiameter }} px</span>
        <input
          v-model.number="brushDiameter"
          type="range"
          min="4"
          :max="brushMax"
          step="2"
          :disabled="editingDisabled || (tool !== 'brush' && tool !== 'eraser')"
        />
      </label>

      <div class="annotation-toolbar__group" role="group" aria-label="编辑历史">
        <button type="button" aria-label="撤销" :disabled="editingDisabled || !canUndo" :title="undoTitle" @click="undo">
          <AppIcon name="undo" />
        </button>
        <button type="button" aria-label="重做" :disabled="editingDisabled || !canRedo" :title="redoTitle" @click="redo">
          <AppIcon name="redo" />
        </button>
        <button
          type="button"
          :disabled="editingDisabled || pendingPolygon.length < 3"
          :title="pendingPolygon.length >= 3 ? '闭合当前多边形' : '至少需要三个顶点'"
          @click="completePolygon"
        >
          <AppIcon name="check" />
          <span>闭合</span>
        </button>
      </div>

      <div class="annotation-toolbar__group" role="group" aria-label="画布视图">
        <button type="button" aria-label="缩小" :disabled="!imageReady || zoom <= 0.5" title="缩小" @click="changeZoom(-0.25)">
          <AppIcon name="zoomOut" />
        </button>
        <button type="button" aria-label="放大" :disabled="!imageReady || zoom >= 4" title="放大" @click="changeZoom(0.25)">
          <AppIcon name="zoomIn" />
        </button>
        <button type="button" :disabled="!imageReady" title="重置视图" @click="resetView">
          <AppIcon name="target" />
          <span>复位</span>
        </button>
      </div>

      <button
        class="clear-button"
        type="button"
        :disabled="editingDisabled || (!operations.length && !pendingPolygon.length)"
        :title="toolTitle('清空当前标签掩膜')"
        @click="clearGeometry"
      >
        <AppIcon name="trash" />
        <span>清空</span>
      </button>
    </div>

    <div
      ref="viewportEl"
      class="annotation-viewport"
      :class="{ 'annotation-viewport--pan': tool === 'pan', 'annotation-viewport--disabled': editingDisabled }"
      @wheel.prevent="handleWheel"
    >
      <div v-if="sourceUrl" class="annotation-content" :style="contentStyle">
        <img
          :src="sourceUrl"
          alt="医生人工标注来源图像"
          crossorigin="anonymous"
          draggable="false"
          @load="handleSourceLoad"
          @error="handleSourceError"
        />
        <canvas
          ref="canvasEl"
          :width="imageWidth"
          :height="imageHeight"
          aria-label="病灶人工标注层"
          @pointerdown="handlePointerDown"
          @pointermove="handlePointerMove"
          @pointerup="handlePointerUp"
          @pointercancel="handlePointerUp"
        />
        <canvas
          ref="draftCanvasEl"
          class="annotation-draft-layer"
          :width="imageWidth"
          :height="imageHeight"
          aria-hidden="true"
        />
      </div>

      <div v-if="!sourceUrl" class="annotation-empty">
        <AppIcon name="brush" variant="badge" tone="cyan" />
        <strong>请选择病例图像或视频关键帧</strong>
      </div>
      <div v-else-if="imageError" class="annotation-empty annotation-empty--error" role="alert">
        <AppIcon name="alert" variant="badge" tone="red" />
        <strong>{{ imageError }}</strong>
      </div>
    </div>

    <footer class="annotation-canvas__footer" aria-live="polite">
      <span>{{ statusText }}</span>
      <span v-if="disabledReason">{{ disabledReason }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { AnnotationGeometry, AnnotationOperation, AnnotationPoint } from "@/types/annotation";
import {
  appendAnnotationOperation,
  appendBoundedHistory,
  clearAnnotationOperations,
  redoAnnotationEntry,
  type AnnotationHistoryEntry,
  undoAnnotationEntry,
} from "@/utils/annotationHistory";

type CanvasTool = "brush" | "eraser" | "polygon" | "pan";

const props = withDefaults(
  defineProps<{
    sourceUrl?: string;
    sourceTitle?: string;
    originalWidth?: number | null;
    originalHeight?: number | null;
    geometry?: AnnotationGeometry | null;
    overlayColor?: string;
    disabled?: boolean;
    disabledReason?: string;
  }>(),
  {
    sourceUrl: "",
    sourceTitle: "",
    originalWidth: null,
    originalHeight: null,
    geometry: null,
    overlayColor: "#ffb22e",
    disabled: false,
    disabledReason: "",
  },
);

const emit = defineEmits<{
  "geometry-change": [geometry: AnnotationGeometry];
  "source-ready": [dimensions: { width: number; height: number }];
}>();

const viewportEl = ref<HTMLElement | null>(null);
const canvasEl = ref<HTMLCanvasElement | null>(null);
const draftCanvasEl = ref<HTMLCanvasElement | null>(null);
const viewportWidth = ref(1);
const viewportHeight = ref(1);
const imageWidth = ref(positiveDimension(props.originalWidth) || 1);
const imageHeight = ref(positiveDimension(props.originalHeight) || 1);
const imageReady = ref(false);
const imageError = ref("");
const tool = ref<CanvasTool>("brush");
const brushDiameter = ref(42);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);
const operations = shallowRef<AnnotationOperation[]>([]);
const pendingPolygon = ref<AnnotationPoint[]>([]);
const history = shallowRef<AnnotationHistoryEntry[]>([]);
const redoHistory = shallowRef<AnnotationHistoryEntry[]>([]);
const activeStroke = shallowRef<AnnotationOperation | null>(null);
const pointerId = ref<number | null>(null);
const panOrigin = ref<{ clientX: number; clientY: number; x: number; y: number } | null>(null);
const statusText = ref("选择标注来源后开始描画。请保存草稿，再提交医生复核。");
let resizeObserver: ResizeObserver | null = null;
const emittedGeometries = new WeakSet<AnnotationGeometry>();

const editingDisabled = computed(() => props.disabled || !imageReady.value || Boolean(imageError.value));
const operationCount = computed(() => operations.value.length + (pendingPolygon.value.length ? 1 : 0));
const canUndo = computed(() => history.value.length > 0 || pendingPolygon.value.length > 0);
const canRedo = computed(() => redoHistory.value.length > 0);
const zoomLabel = computed(() => `${Math.round(zoom.value * 100)}%`);
const dimensionLabel = computed(() =>
  imageReady.value ? `${imageWidth.value} × ${imageHeight.value}` : "待读取原始尺寸",
);
const brushMax = computed(() => Math.max(120, Math.round(Math.min(imageWidth.value, imageHeight.value) * 0.08)));
const undoTitle = computed(() => (canUndo.value ? "撤销上一步标注" : "暂无可撤销操作"));
const redoTitle = computed(() => (canRedo.value ? "重做上一步标注" : "暂无可重做操作"));

const fittedSize = computed(() => {
  const ratio = imageWidth.value / Math.max(1, imageHeight.value);
  const widthFromHeight = viewportHeight.value * ratio;
  if (widthFromHeight <= viewportWidth.value) {
    return { width: widthFromHeight, height: viewportHeight.value };
  }
  return { width: viewportWidth.value, height: viewportWidth.value / ratio };
});

const contentStyle = computed(() => ({
  width: `${Math.max(1, fittedSize.value.width)}px`,
  height: `${Math.max(1, fittedSize.value.height)}px`,
  left: `${(viewportWidth.value - fittedSize.value.width) / 2}px`,
  top: `${(viewportHeight.value - fittedSize.value.height) / 2}px`,
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
}));

watch(
  () => props.geometry,
  (geometry) => {
    if (geometry && emittedGeometries.has(geometry)) {
      emittedGeometries.delete(geometry);
      return;
    }
    const sourceOperations = geometry?.operations ?? [];
    if (operationsEqual(operations.value, sourceOperations)) return;
    operations.value = cloneOperations(sourceOperations);
    pendingPolygon.value = [];
    history.value = [];
    redoHistory.value = [];
    activeStroke.value = null;
    nextTick(renderAllCanvases);
  },
  { immediate: true },
);

watch(
  () => props.sourceUrl,
  () => {
    imageReady.value = false;
    imageError.value = "";
    imageWidth.value = positiveDimension(props.originalWidth) || 1;
    imageHeight.value = positiveDimension(props.originalHeight) || 1;
    activeStroke.value = null;
    pendingPolygon.value = [];
    resetView();
    statusText.value = props.sourceUrl ? "正在读取标注来源..." : "请选择标注来源。";
    nextTick(renderAllCanvases);
  },
);

watch(() => props.overlayColor, () => nextTick(renderAllCanvases));

onMounted(() => {
  resizeObserver = new ResizeObserver((entries) => {
    const box = entries[0]?.contentRect;
    if (!box) return;
    viewportWidth.value = Math.max(1, box.width);
    viewportHeight.value = Math.max(1, box.height);
  });
  if (viewportEl.value) resizeObserver.observe(viewportEl.value);
});

onBeforeUnmount(() => resizeObserver?.disconnect());

function handleSourceLoad(event: Event) {
  const image = event.currentTarget as HTMLImageElement;
  imageWidth.value = image.naturalWidth || positiveDimension(props.originalWidth) || 1;
  imageHeight.value = image.naturalHeight || positiveDimension(props.originalHeight) || 1;
  imageReady.value = true;
  imageError.value = "";
  statusText.value = operations.value.length ? "已载入当前版本，可继续修改。" : "标注来源已载入。";
  emit("source-ready", { width: imageWidth.value, height: imageHeight.value });
  nextTick(renderAllCanvases);
}

function handleSourceError() {
  imageReady.value = false;
  imageError.value = "标注来源读取失败，请检查病例文件或关键帧证据。";
  statusText.value = "图像不可用，标注工具已停用。";
}

function selectTool(nextTool: CanvasTool) {
  if (nextTool !== "polygon" && pendingPolygon.value.length) {
    pendingPolygon.value = [];
    renderDraftCanvas();
    statusText.value = "未闭合的多边形已取消。";
  }
  tool.value = nextTool;
}

function handlePointerDown(event: PointerEvent) {
  if (!imageReady.value) return;
  const canvas = canvasEl.value;
  if (!canvas) return;
  canvas.setPointerCapture?.(event.pointerId);
  pointerId.value = event.pointerId;

  if (tool.value === "pan") {
    panOrigin.value = { clientX: event.clientX, clientY: event.clientY, x: panX.value, y: panY.value };
    return;
  }
  if (editingDisabled.value) return;

  const point = pointerPoint(event);
  if (tool.value === "polygon") {
    pendingPolygon.value = [...pendingPolygon.value, point];
    renderDraftCanvas();
    statusText.value = `多边形已记录 ${pendingPolygon.value.length} 个顶点。`;
    return;
  }

  activeStroke.value = {
    tool: tool.value,
    mode: tool.value === "eraser" ? "erase" : "add",
    radius: brushDiameter.value / 2,
    points: [point],
  };
  if (activeStroke.value.tool === "eraser") {
    const context = committedCanvasContext();
    if (context) drawOperation(context, activeStroke.value);
  } else {
    renderDraftCanvas();
  }
}

function handlePointerMove(event: PointerEvent) {
  if (pointerId.value !== event.pointerId) return;
  if (tool.value === "pan" && panOrigin.value) {
    panX.value = panOrigin.value.x + event.clientX - panOrigin.value.clientX;
    panY.value = panOrigin.value.y + event.clientY - panOrigin.value.clientY;
    return;
  }
  if (!activeStroke.value || editingDisabled.value) return;
  const point = pointerPoint(event);
  const previous = activeStroke.value.points.at(-1);
  if (previous && Math.hypot(point.x - previous.x, point.y - previous.y) < 1) return;
  activeStroke.value.points.push(point);
  const context = activeStroke.value.tool === "eraser" ? committedCanvasContext() : draftCanvasContext();
  if (context && previous) drawStrokeSegment(context, activeStroke.value, previous, point);
}

function handlePointerUp(event: PointerEvent) {
  if (pointerId.value !== event.pointerId) return;
  pointerId.value = null;
  panOrigin.value = null;
  const canvas = canvasEl.value;
  if (canvas?.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture?.(event.pointerId);
  if (!activeStroke.value) return;
  const completed = activeStroke.value;
  activeStroke.value = null;
  commitOperation(completed);
  statusText.value = completed.tool === "eraser" ? "擦除操作已记录。" : "画笔操作已记录。";
}

function completePolygon() {
  if (editingDisabled.value || pendingPolygon.value.length < 3) return;
  const polygon: AnnotationOperation = {
    tool: "polygon",
    mode: "add",
    points: pendingPolygon.value.map((point) => ({ ...point })),
  };
  pendingPolygon.value = [];
  commitOperation(polygon);
  statusText.value = "多边形标注已闭合。";
}

function clearGeometry() {
  if (editingDisabled.value) return;
  pendingPolygon.value = [];
  const change = clearAnnotationOperations(operations.value);
  recordHistory(change.entry);
  operations.value = change.operations;
  clearCanvas(canvasEl.value);
  clearDraftCanvas();
  emitGeometry();
  statusText.value = "当前标签掩膜已清空，可撤销恢复。";
}

function undo() {
  if (editingDisabled.value) return;
  if (pendingPolygon.value.length) {
    pendingPolygon.value = pendingPolygon.value.slice(0, -1);
    renderDraftCanvas();
    statusText.value = "已撤销一个多边形顶点。";
    return;
  }
  const entry = history.value.at(-1);
  if (!entry) return;
  history.value = history.value.slice(0, -1);
  redoHistory.value = appendBoundedHistory(redoHistory.value, entry);
  operations.value = undoAnnotationEntry(operations.value, entry);
  renderCommittedCanvas();
  clearDraftCanvas();
  emitGeometry();
  statusText.value = "已撤销上一步标注。";
}

function redo() {
  if (editingDisabled.value) return;
  const entry = redoHistory.value.at(-1);
  if (!entry) return;
  redoHistory.value = redoHistory.value.slice(0, -1);
  history.value = appendBoundedHistory(history.value, entry);
  operations.value = redoAnnotationEntry(operations.value, entry);
  if (entry.kind === "clear") {
    clearCanvas(canvasEl.value);
  } else {
    const context = committedCanvasContext();
    if (context) drawOperation(context, entry.operation);
  }
  clearDraftCanvas();
  emitGeometry();
  statusText.value = "已重做上一步标注。";
}

function commitOperation(operation: AnnotationOperation) {
  const change = appendAnnotationOperation(operations.value, operation);
  recordHistory(change.entry);
  operations.value = change.operations;
  if (operation.tool === "eraser") {
    renderCommittedCanvas();
  } else {
    const context = committedCanvasContext();
    if (context) drawOperation(context, operation);
  }
  clearDraftCanvas();
  emitGeometry();
}

function recordHistory(entry: AnnotationHistoryEntry) {
  history.value = appendBoundedHistory(history.value, entry);
  redoHistory.value = [];
}

function emitGeometry() {
  const geometry: AnnotationGeometry = {
    coordinate_space: "image_pixels",
    operations: cloneOperations(operations.value),
  };
  emittedGeometries.add(geometry);
  emit("geometry-change", geometry);
}

function pointerPoint(event: PointerEvent): AnnotationPoint {
  const canvas = canvasEl.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: clamp(((event.clientX - rect.left) / Math.max(1, rect.width)) * imageWidth.value, 0, imageWidth.value),
    y: clamp(((event.clientY - rect.top) / Math.max(1, rect.height)) * imageHeight.value, 0, imageHeight.value),
  };
}

function renderAllCanvases() {
  renderCommittedCanvas();
  renderDraftCanvas();
}

function renderCommittedCanvas() {
  const context = committedCanvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  for (const operation of operations.value) drawOperation(context, operation);
}

function renderDraftCanvas() {
  const context = draftCanvasContext();
  if (!context) return;
  context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  if (activeStroke.value) drawOperation(context, activeStroke.value);
  if (pendingPolygon.value.length) drawPendingPolygon(context, pendingPolygon.value);
}

function committedCanvasContext(): CanvasRenderingContext2D | null {
  const canvas = canvasEl.value;
  if (!canvas || canvas.width < 1 || canvas.height < 1) return null;
  return canvas.getContext("2d");
}

function draftCanvasContext(): CanvasRenderingContext2D | null {
  const canvas = draftCanvasEl.value;
  if (!canvas || canvas.width < 1 || canvas.height < 1) return null;
  return canvas.getContext("2d");
}

function clearCanvas(canvas: HTMLCanvasElement | null) {
  if (!canvas || canvas.width < 1 || canvas.height < 1) return;
  const context = canvas.getContext("2d");
  context?.clearRect(0, 0, canvas.width, canvas.height);
}

function clearDraftCanvas() {
  clearCanvas(draftCanvasEl.value);
}

function drawOperation(context: CanvasRenderingContext2D, operation: AnnotationOperation) {
  if (!operation.points.length) return;
  context.save();
  context.globalCompositeOperation = operation.mode === "erase" || operation.tool === "eraser"
    ? "destination-out"
    : "source-over";
  context.strokeStyle = colorWithAlpha(props.overlayColor, 0.92);
  context.fillStyle = colorWithAlpha(props.overlayColor, 0.38);
  context.lineCap = "round";
  context.lineJoin = "round";

  if (operation.tool === "polygon") {
    context.beginPath();
    context.moveTo(operation.points[0].x, operation.points[0].y);
    for (let index = 1; index < operation.points.length; index += 1) {
      const point = operation.points[index];
      context.lineTo(point.x, point.y);
    }
    context.closePath();
    context.fill();
    context.lineWidth = Math.max(2, Math.min(imageWidth.value, imageHeight.value) * 0.002);
    context.stroke();
    context.restore();
    return;
  }

  const radius = Math.max(1, operation.radius ?? brushDiameter.value / 2);
  context.lineWidth = radius * 2;
  context.beginPath();
  context.moveTo(operation.points[0].x, operation.points[0].y);
  for (let index = 1; index < operation.points.length; index += 1) {
    const point = operation.points[index];
    context.lineTo(point.x, point.y);
  }
  context.stroke();
  if (operation.points.length === 1) {
    context.beginPath();
    context.arc(operation.points[0].x, operation.points[0].y, radius, 0, Math.PI * 2);
    context.fill();
  }
  context.restore();
}

function drawStrokeSegment(
  context: CanvasRenderingContext2D,
  operation: AnnotationOperation,
  from: AnnotationPoint,
  to: AnnotationPoint,
) {
  context.save();
  context.globalCompositeOperation = operation.mode === "erase" || operation.tool === "eraser"
    ? "destination-out"
    : "source-over";
  context.strokeStyle = colorWithAlpha(props.overlayColor, 0.92);
  context.lineCap = "round";
  context.lineJoin = "round";
  context.lineWidth = Math.max(1, operation.radius ?? brushDiameter.value / 2) * 2;
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
  context.restore();
}

function drawPendingPolygon(context: CanvasRenderingContext2D, points: AnnotationPoint[]) {
  context.save();
  context.strokeStyle = colorWithAlpha(props.overlayColor, 0.95);
  context.fillStyle = colorWithAlpha(props.overlayColor, 0.95);
  context.setLineDash([10, 7]);
  context.lineWidth = Math.max(2, Math.min(imageWidth.value, imageHeight.value) * 0.002);
  context.beginPath();
  context.moveTo(points[0].x, points[0].y);
  for (let index = 1; index < points.length; index += 1) {
    const point = points[index];
    context.lineTo(point.x, point.y);
  }
  context.stroke();
  context.setLineDash([]);
  for (const point of points) {
    context.beginPath();
    context.arc(point.x, point.y, context.lineWidth * 2.2, 0, Math.PI * 2);
    context.fill();
  }
  context.restore();
}

function handleWheel(event: WheelEvent) {
  if (!imageReady.value) return;
  changeZoom(event.deltaY < 0 ? 0.25 : -0.25);
}

function changeZoom(delta: number) {
  zoom.value = clamp(Number((zoom.value + delta).toFixed(2)), 0.5, 4);
  if (zoom.value === 1) {
    panX.value = 0;
    panY.value = 0;
  }
}

function resetView() {
  zoom.value = 1;
  panX.value = 0;
  panY.value = 0;
}

function toolTitle(title: string): string {
  return props.disabledReason || (imageReady.value ? title : "请先选择标注来源");
}

function cloneOperations(value: AnnotationOperation[]): AnnotationOperation[] {
  return value.map(cloneOperation);
}

function cloneOperation(value: AnnotationOperation): AnnotationOperation {
  return { ...value, points: value.points.map((point) => ({ x: point.x, y: point.y })) };
}

function operationsEqual(left: AnnotationOperation[], right: AnnotationOperation[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((operation, index) => {
    const comparison = right[index];
    if (
      !comparison ||
      operation.tool !== comparison.tool ||
      operation.mode !== comparison.mode ||
      operation.radius !== comparison.radius ||
      operation.points.length !== comparison.points.length
    ) {
      return false;
    }
    return operation.points.every(
      (point, pointIndex) => point.x === comparison.points[pointIndex]?.x && point.y === comparison.points[pointIndex]?.y,
    );
  });
}

function positiveDimension(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.round(value) : 0;
}

function colorWithAlpha(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  if (!/^[0-9a-f]{6}$/i.test(value)) return `rgba(255, 178, 46, ${alpha})`;
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
</script>

<style scoped>
.annotation-canvas {
  display: grid;
  gap: 12px;
  min-width: 0;
  color: var(--ov-text);
}

.annotation-canvas__header,
.annotation-toolbar,
.annotation-canvas__footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.annotation-canvas__header {
  justify-content: space-between;
}

.annotation-canvas__header > div:first-child {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.annotation-canvas__header span,
.annotation-canvas__footer {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.annotation-canvas__header strong {
  color: var(--ov-text);
  font-size: 15px;
  overflow-wrap: anywhere;
}

.annotation-canvas__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.annotation-canvas__meta span {
  border: 1px solid var(--ov-border-subtle);
  border-radius: 4px;
  padding: 4px 7px;
  background: var(--ov-bg-soft);
}

.annotation-toolbar {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 9px;
  background: var(--ov-bg-soft);
}

.annotation-toolbar__group {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding-right: 10px;
  border-right: 1px solid var(--ov-border-subtle);
}

.annotation-toolbar button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  min-height: 36px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 7px 9px;
  background: var(--ov-bg-control);
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.annotation-toolbar button.selected {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  color: var(--ov-primary);
}

.annotation-toolbar button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.annotation-toolbar button:not(:disabled):hover {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-hover);
  color: var(--ov-primary);
}

.annotation-toolbar button:focus-visible,
.brush-size input:focus-visible {
  outline: 2px solid var(--ov-focus-ring);
  outline-offset: 1px;
}

.annotation-toolbar :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.brush-size {
  display: grid;
  gap: 4px;
  flex: 1 1 180px;
  max-width: 250px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.brush-size input {
  width: 100%;
}

.clear-button {
  margin-left: auto;
}

.annotation-viewport {
  position: relative;
  min-height: clamp(480px, 64vh, 760px);
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  background-color: var(--ov-bg-media);
  background-image:
    linear-gradient(45deg, color-mix(in srgb, var(--ov-border) 40%, transparent) 25%, transparent 25%),
    linear-gradient(-45deg, color-mix(in srgb, var(--ov-border) 40%, transparent) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, color-mix(in srgb, var(--ov-border) 40%, transparent) 75%),
    linear-gradient(-45deg, transparent 75%, color-mix(in srgb, var(--ov-border) 40%, transparent) 75%);
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  background-size: 16px 16px;
}

.annotation-content {
  position: absolute;
  transform-origin: center;
  will-change: transform;
}

.annotation-content img,
.annotation-content canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.annotation-content img {
  object-fit: fill;
  user-select: none;
}

.annotation-content canvas {
  touch-action: none;
  cursor: crosshair;
}

.annotation-content .annotation-draft-layer {
  pointer-events: none;
}

.annotation-viewport--pan canvas {
  cursor: grab;
}

.annotation-viewport--pan canvas:active {
  cursor: grabbing;
}

.annotation-viewport--disabled canvas {
  cursor: not-allowed;
}

.annotation-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  padding: 32px;
  color: var(--ov-text-muted);
  text-align: center;
}

.annotation-empty :deep(.app-icon) {
  width: 42px;
  height: 42px;
}

.annotation-empty--error {
  color: var(--ov-danger);
}

.annotation-canvas__footer {
  justify-content: space-between;
  min-height: 22px;
  overflow-wrap: anywhere;
}
</style>
