<template>
  <section class="roi-panel ov-card">
    <SectionHeading icon="target" eyebrow="ROI 复核" :title="regionLabel ?? '术中 ROI'" />
    <div class="roi-toolbar" aria-label="ROI 标注控制">
      <label class="roi-label-field">
        <span>ROI 标签</span>
        <input v-model="labelDraft" type="text" placeholder="manual_roi" />
      </label>
      <label class="roi-label-field">
        <span>复核状态</span>
        <select v-model="reviewStateDraft">
          <option value="review_required">待复核</option>
          <option value="accepted">接受</option>
          <option value="modified">已修改</option>
          <option value="rejected">拒绝</option>
        </select>
      </label>
      <AppButton variant="ghost" size="sm" :disabled="!canUndo" @click="undoDraft">撤销</AppButton>
      <AppButton variant="ghost" size="sm" :disabled="!canRedo" @click="redoDraft">重做</AppButton>
      <AppButton variant="secondary" size="sm" :disabled="!rectDraft" @click="clearDraft">清除</AppButton>
      <AppButton variant="primary" size="sm" icon="check" :disabled="!canSave" @click="saveDraft">{{ saveLabel }}</AppButton>
    </div>
    <div
      class="canvas-frame"
      :class="{ empty: !hasOutput && !rectDraft }"
      tabindex="0"
      role="application"
      aria-label="ROI 矩形编辑画布，方向键微调当前 ROI"
      @keydown="nudgeDraft"
    >
      <svg
        ref="svgEl"
        class="roi-svg"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-label="ROI 手动矩形标注画布"
        @pointerdown="startDraw"
        @pointermove="updateDraw"
        @pointerup="finishDraw"
        @pointerleave="finishDraw"
      >
        <defs>
          <pattern id="roi-grid" width="6" height="6" patternUnits="userSpaceOnUse">
            <path d="M 6 0 L 0 0 0 6" fill="none" stroke="rgba(50,60,75,0.12)" stroke-width="0.18" />
          </pattern>
          <radialGradient id="roi-tissue" cx="55%" cy="48%" r="48%">
            <stop offset="0%" stop-color="#f1e5d6" stop-opacity="0.78" />
            <stop offset="48%" stop-color="#b97363" stop-opacity="0.34" />
            <stop offset="100%" stop-color="#6d8799" stop-opacity="0.16" />
          </radialGradient>
          <radialGradient id="roi-fluor" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#79ff9a" stop-opacity="0.82" />
            <stop offset="58%" stop-color="#2eb76f" stop-opacity="0.38" />
            <stop offset="100%" stop-color="#2eb76f" stop-opacity="0" />
          </radialGradient>
        </defs>
        <rect x="0" y="0" width="100" height="100" fill="#eef3f8" />
        <rect x="0" y="0" width="100" height="100" fill="url(#roi-grid)" />
        <ellipse cx="51" cy="50" rx="34" ry="28" fill="url(#roi-tissue)" />
        <ellipse cx="56" cy="45" rx="13" ry="11" fill="url(#roi-fluor)" />
        <ellipse cx="44" cy="57" rx="9" ry="8" fill="url(#roi-fluor)" opacity="0.62" />
        <line x1="8" y1="50" x2="92" y2="50" stroke="rgba(45,120,173,0.22)" stroke-width="0.28" />
        <line x1="50" y1="8" x2="50" y2="92" stroke="rgba(45,120,173,0.22)" stroke-width="0.28" />
        <rect
          v-for="roi in persistedRects"
          :key="roi.roi_id"
          :x="roi.rect.x * 100"
          :y="roi.rect.y * 100"
          :width="roi.rect.width * 100"
          :height="roi.rect.height * 100"
          class="roi-box persisted"
          vector-effect="non-scaling-stroke"
        />
        <rect
          v-if="originalRect && hasDraftChanged"
          :x="originalRect.x * 100"
          :y="originalRect.y * 100"
          :width="originalRect.width * 100"
          :height="originalRect.height * 100"
          class="roi-box original"
          vector-effect="non-scaling-stroke"
        />
        <rect
          v-if="rectDraft"
          :x="rectDraft.x * 100"
          :y="rectDraft.y * 100"
          :width="rectDraft.width * 100"
          :height="rectDraft.height * 100"
          class="roi-box draft"
          vector-effect="non-scaling-stroke"
          @pointerdown.stop="startEdit('move', $event)"
        />
        <g v-if="rectDraft" class="roi-handles" aria-label="ROI 编辑控制点">
          <rect
            v-for="handle in edgeHandles"
            :key="handle.key"
            :x="handle.x"
            :y="handle.y"
            :width="handle.width"
            :height="handle.height"
            :class="['roi-handle', `roi-handle-${handle.key}`]"
            vector-effect="non-scaling-stroke"
            @pointerdown.stop="startEdit(handle.key, $event)"
          />
          <circle
            v-for="handle in cornerHandles"
            :key="handle.key"
            :cx="handle.cx"
            :cy="handle.cy"
            r="1.6"
            :class="['roi-handle', `roi-handle-${handle.key}`]"
            vector-effect="non-scaling-stroke"
            @pointerdown.stop="startEdit(handle.key, $event)"
          />
        </g>
      </svg>
      <div class="canvas-meta top-left">WL + ICG / normalized ROI</div>
      <div class="canvas-meta bottom-right">{{ geometrySummary }}</div>
      <div v-if="originalRect && hasDraftChanged" class="canvas-meta bottom-left">{{ comparisonSummary }}</div>
      <div v-if="!hasOutput && !rectDraft" class="empty-canvas-copy">
        <strong>空白 ROI 画布</strong>
        <span>{{ emptyCanvasText }}</span>
      </div>
    </div>
    <p class="roi-status">{{ statusText }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import SectionHeading from "@/components/SectionHeading.vue";
import type { RegionOfInterest, ReviewState } from "@/types/case";
import {
  roiAreaFraction,
  roiGeometryPayload,
  roiRectFromGeometry,
  rectFromPoints,
  resizeRectFromHandle,
  type RoiPoint,
  type RoiRect,
  type RoiResizeHandle,
  translateRect,
} from "@/utils/roiGeometry";

const props = withDefaults(
  defineProps<{
    regionLabel?: string;
    hasOutput?: boolean;
    rois?: RegionOfInterest[];
    disabled?: boolean;
    draftId?: string;
    draftGeometry?: Record<string, unknown> | null;
    draftLabel?: string;
    draftReviewState?: ReviewState;
    saveLabel?: string;
    emptyText?: string;
  }>(),
  {
    hasOutput: false,
    rois: () => [],
    disabled: false,
    draftId: "",
    draftGeometry: null,
    draftLabel: "",
    draftReviewState: "modified",
    saveLabel: "保存 ROI",
    emptyText: "拖拽画出矩形 ROI，保存后进入医生复核记录。",
  },
);

const emit = defineEmits<{
  save: [payload: { roiId: string; geometry: Record<string, unknown>; label: string; reviewState: ReviewState }];
}>();

const svgEl = ref<SVGSVGElement | null>(null);
const editMode = ref<"draw" | "move" | RoiResizeHandle | null>(null);
const startPoint = ref<RoiPoint | null>(null);
const startRect = ref<RoiRect | null>(null);
const rectDraft = ref<RoiRect | null>(null);
const originalRect = ref<RoiRect | null>(null);
const undoStack = ref<Array<RoiRect | null>>([]);
const redoStack = ref<Array<RoiRect | null>>([]);
const labelDraft = ref("manual_roi");
const reviewStateDraft = ref<ReviewState>("modified");

const persistedRects = computed(() =>
  props.rois
    .map((roi) => ({ roi_id: roi.roi_id, rect: roiRectFromGeometry(roi.geometry) }))
    .filter((item): item is { roi_id: string; rect: RoiRect } => item.rect !== null),
);

const canSave = computed(() => Boolean(rectDraft.value && !props.disabled));
const canUndo = computed(() => undoStack.value.length > 0 && !props.disabled);
const canRedo = computed(() => redoStack.value.length > 0 && !props.disabled);
const saveLabel = computed(() => props.saveLabel || "保存 ROI");
const emptyCanvasText = computed(() => props.emptyText || "拖拽画出矩形 ROI，保存后进入医生复核记录。");
const geometrySummary = computed(() => {
  if (!rectDraft.value) return persistedRects.value.length ? `${persistedRects.value.length} 个已保存 ROI` : "拖拽创建 ROI";
  return `面积 ${(roiAreaFraction(rectDraft.value) * 100).toFixed(1)}%`;
});
const hasDraftChanged = computed(() => Boolean(originalRect.value && rectDraft.value && !rectEquals(originalRect.value, rectDraft.value)));
const comparisonSummary = computed(() => {
  if (!originalRect.value || !rectDraft.value) return "";
  const originalArea = roiAreaFraction(originalRect.value) * 100;
  const currentArea = roiAreaFraction(rectDraft.value) * 100;
  const delta = currentArea - originalArea;
  const sign = delta > 0 ? "+" : "";
  return `原始 ${originalArea.toFixed(1)}% → 当前 ${currentArea.toFixed(1)}% (${sign}${delta.toFixed(1)}%)`;
});
const statusText = computed(() => {
  if (props.disabled) return "请先载入病例后再保存 ROI。";
  if (rectDraft.value) return "当前 ROI 可移动、缩放、方向键微调，并支持撤销/重做；保存后写入复核记录。";
  if (persistedRects.value.length) return "已保存 ROI 可随证据包导出。";
  return "在画布上按住并拖拽即可创建矩形 ROI。";
});
const cornerHandles = computed(() => {
  if (!rectDraft.value) return [];
  const left = rectDraft.value.x * 100;
  const top = rectDraft.value.y * 100;
  const right = (rectDraft.value.x + rectDraft.value.width) * 100;
  const bottom = (rectDraft.value.y + rectDraft.value.height) * 100;
  return [
    { key: "nw" as const, cx: left, cy: top },
    { key: "ne" as const, cx: right, cy: top },
    { key: "sw" as const, cx: left, cy: bottom },
    { key: "se" as const, cx: right, cy: bottom },
  ];
});
const edgeHandles = computed(() => {
  if (!rectDraft.value) return [];
  const left = rectDraft.value.x * 100;
  const top = rectDraft.value.y * 100;
  const width = rectDraft.value.width * 100;
  const height = rectDraft.value.height * 100;
  const right = left + width;
  const bottom = top + height;
  const centerX = left + width / 2;
  const centerY = top + height / 2;
  return [
    { key: "n" as const, x: centerX - 3, y: top - 1, width: 6, height: 2 },
    { key: "s" as const, x: centerX - 3, y: bottom - 1, width: 6, height: 2 },
    { key: "w" as const, x: left - 1, y: centerY - 3, width: 2, height: 6 },
    { key: "e" as const, x: right - 1, y: centerY - 3, width: 2, height: 6 },
  ];
});

watch(
  () => props.rois.length,
  (current, previous) => {
    if (current > previous) {
      rectDraft.value = null;
      originalRect.value = null;
      resetHistory();
    }
  },
);

watch(
  () => [props.draftId, props.draftGeometry, props.draftLabel, props.draftReviewState] as const,
  () => {
    if (!props.draftId || !props.draftGeometry) return;
    const draftRect = roiRectFromGeometry(props.draftGeometry);
    if (!draftRect) return;
    rectDraft.value = draftRect;
    originalRect.value = { ...draftRect };
    resetHistory();
    labelDraft.value = props.draftLabel || props.draftId;
    reviewStateDraft.value = props.draftReviewState || "modified";
  },
  { immediate: true },
);

function startDraw(event: PointerEvent) {
  if (props.disabled) return;
  const point = eventPoint(event);
  if (!point) return;
  pushHistory();
  editMode.value = "draw";
  startPoint.value = point;
  startRect.value = null;
  rectDraft.value = { x: point.x, y: point.y, width: 0, height: 0 };
  svgEl.value?.setPointerCapture(event.pointerId);
}

function startEdit(mode: "move" | RoiResizeHandle, event: PointerEvent) {
  if (props.disabled || !rectDraft.value) return;
  const point = eventPoint(event);
  if (!point) return;
  pushHistory();
  editMode.value = mode;
  startPoint.value = point;
  startRect.value = { ...rectDraft.value };
  svgEl.value?.setPointerCapture(event.pointerId);
}

function updateDraw(event: PointerEvent) {
  if (!editMode.value || !startPoint.value) return;
  const point = eventPoint(event);
  if (!point) return;
  if (editMode.value === "draw") {
    rectDraft.value = rectFromPoints(startPoint.value, point);
    return;
  }
  if (!startRect.value) return;
  if (editMode.value === "move") {
    rectDraft.value = translateRect(startRect.value, {
      x: point.x - startPoint.value.x,
      y: point.y - startPoint.value.y,
    });
    return;
  }
  rectDraft.value = resizeRectFromHandle(startRect.value, editMode.value, point);
}

function finishDraw(event: PointerEvent) {
  if (!editMode.value) return;
  updateDraw(event);
  editMode.value = null;
  startPoint.value = null;
  startRect.value = null;
  if (rectDraft.value && (rectDraft.value.width < 0.01 || rectDraft.value.height < 0.01)) {
    rectDraft.value = null;
  }
}

function clearDraft() {
  pushHistory();
  rectDraft.value = null;
}

function saveDraft() {
  if (!rectDraft.value || props.disabled) return;
  emit("save", {
    roiId: props.draftId || `manual_roi_${Date.now()}`,
    geometry: { ...roiGeometryPayload(rectDraft.value) },
    label: labelDraft.value.trim() || "manual_roi",
    reviewState: reviewStateDraft.value,
  });
}

function nudgeDraft(event: KeyboardEvent) {
  if (!rectDraft.value || props.disabled) return;
  const step = event.shiftKey ? 0.02 : 0.005;
  const deltaByKey: Record<string, RoiPoint> = {
    ArrowLeft: { x: -step, y: 0 },
    ArrowRight: { x: step, y: 0 },
    ArrowUp: { x: 0, y: -step },
    ArrowDown: { x: 0, y: step },
  };
  const delta = deltaByKey[event.key];
  if (!delta) return;
  event.preventDefault();
  pushHistory();
  rectDraft.value = translateRect(rectDraft.value, delta);
}

function undoDraft() {
  const previous = undoStack.value.pop();
  if (previous === undefined) return;
  redoStack.value.push(cloneRect(rectDraft.value));
  rectDraft.value = cloneRect(previous);
}

function redoDraft() {
  const next = redoStack.value.pop();
  if (next === undefined) return;
  undoStack.value.push(cloneRect(rectDraft.value));
  rectDraft.value = cloneRect(next);
}

function pushHistory() {
  const current = cloneRect(rectDraft.value);
  const last = undoStack.value.at(-1);
  if (rectEquals(last, current)) return;
  undoStack.value.push(current);
  redoStack.value = [];
}

function resetHistory() {
  undoStack.value = [];
  redoStack.value = [];
}

function cloneRect(rect: RoiRect | null): RoiRect | null {
  return rect ? { ...rect } : null;
}

function rectEquals(first: RoiRect | null | undefined, second: RoiRect | null | undefined): boolean {
  if (!first && !second) return true;
  if (!first || !second) return false;
  return first.x === second.x && first.y === second.y && first.width === second.width && first.height === second.height;
}

function eventPoint(event: PointerEvent): RoiPoint | null {
  const box = svgEl.value?.getBoundingClientRect();
  if (!box || box.width <= 0 || box.height <= 0) return null;
  return {
    x: (event.clientX - box.left) / box.width,
    y: (event.clientY - box.top) / box.height,
  };
}
</script>

<style scoped>
.roi-panel {
  padding: 14px;
}

.roi-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto auto auto auto;
  gap: 8px;
  align-items: end;
  margin-bottom: 10px;
}

.roi-label-field {
  display: grid;
  gap: 4px;
}

.roi-label-field span {
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.roi-label-field input,
.roi-label-field select {
  min-height: 32px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 5px 8px;
  background: #fbfdff;
  color: var(--ov-text);
  font: inherit;
  font-size: 13px;
}

.canvas-frame {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid var(--ov-border-strong);
  border-radius: var(--ov-radius);
  background: #eef3f8;
}

.canvas-frame.empty {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 249, 255, 0.96)),
    #f8fbfe;
}

.roi-svg {
  display: block;
  width: 100%;
  min-height: 560px;
  touch-action: none;
  cursor: crosshair;
}

.roi-box {
  fill: rgba(228, 155, 63, 0.14);
  stroke-width: 0.8;
}

.roi-box.persisted {
  stroke: rgba(45, 120, 173, 0.92);
  stroke-dasharray: 3 2;
}

.roi-box.original {
  fill: transparent;
  stroke: #2c7ec0;
  stroke-dasharray: 2.5 1.8;
}

.roi-box.draft {
  stroke: #e49b3f;
  cursor: move;
}

.roi-handles {
  pointer-events: all;
}

.roi-handle {
  fill: #ffffff;
  stroke: #d47c1d;
  stroke-width: 0.45;
}

.roi-handle-n,
.roi-handle-s {
  cursor: ns-resize;
}

.roi-handle-e,
.roi-handle-w {
  cursor: ew-resize;
}

.roi-handle-nw,
.roi-handle-se {
  cursor: nwse-resize;
}

.roi-handle-ne,
.roi-handle-sw {
  cursor: nesw-resize;
}

.empty-canvas-copy {
  position: absolute;
  z-index: 2;
  left: 50%;
  top: 50%;
  display: grid;
  gap: 6px;
  justify-items: center;
  max-width: min(360px, calc(100% - 32px));
  border: 1px solid rgba(44, 126, 192, 0.22);
  border-radius: 8px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 8px 20px rgba(22, 76, 120, 0.08);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.empty-canvas-copy strong {
  color: var(--ov-primary);
  font-size: 14px;
}

.empty-canvas-copy span {
  color: var(--ov-text-muted);
  font-size: 12px;
  text-align: center;
}

.canvas-meta {
  position: absolute;
  border-radius: 6px;
  padding: 5px 7px;
  background: rgba(255, 255, 255, 0.84);
  color: #415362;
  font-size: 12px;
  font-weight: 800;
  pointer-events: none;
}

.top-left {
  left: 12px;
  top: 12px;
}

.bottom-right {
  right: 12px;
  bottom: 12px;
}

.bottom-left {
  left: 12px;
  bottom: 12px;
}

.roi-status {
  margin: 9px 0 0;
  color: var(--ov-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 860px) {
  .roi-toolbar {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
