<template>
  <section class="video-playback-panel" aria-label="视频流同步分析">
    <header>
      <div>
        <AppIcon name="video" />
        <strong>视频流同步分析</strong>
      </div>
      <span>{{ videoPlayback.analysisScopeLabel }}</span>
    </header>
    <div class="video-sync-body">
      <aside class="video-sync-panel" aria-live="polite">
        <div class="video-sync-status">
          <strong>{{ nearestFrameDetail?.frameLabel ?? "暂无关键帧" }}</strong>
          <span>{{ nearestFrameDetail?.timestampLabel ?? "等待 MP4 关键帧分析" }}</span>
        </div>
        <dl v-if="nearestFrameDetail" class="video-sync-grid">
          <div>
            <dt>候选数量</dt>
            <dd>{{ nearestFrameDetail.candidateCountLabel }}</dd>
          </div>
          <div>
            <dt>阳性面积</dt>
            <dd>{{ nearestFrameDetail.positiveAreaLabel }}</dd>
          </div>
          <div>
            <dt>ROI 命中</dt>
            <dd>{{ nearestFrameDetail.roiAreaLabel }}</dd>
          </div>
          <div>
            <dt>最大候选框</dt>
            <dd>{{ nearestFrameDetail.topBBoxLabel }}</dd>
          </div>
        </dl>
        <div v-if="nearestFrameDetail" class="video-sync-previews">
          <button
            type="button"
            :disabled="nearestFrameDetail.timestampSec === null"
            @click="emit('jumpToFrame', nearestFrameDetail)"
          >
            跳转关键帧
          </button>
          <button
            type="button"
            class="bone-gate-generate-button"
            :title="generateUnavailableReason"
            :aria-busy="activeAction === 'generate' || loading"
            :disabled="boneGateActionBusy || !generateAvailable"
            @click="requestGenerateBoneGate(nearestFrameDetail)"
          >
            {{ activeAction === "generate" ? "正在生成..." : "生成骨面门控" }}
          </button>
          <button
            type="button"
            class="bone-gate-edit-button"
            :title="editUnavailableReason"
            :aria-busy="activeAction === 'edit'"
            :disabled="boneGateActionBusy || !editAvailable"
            @click="requestEditBoneGate(nearestFrameDetail)"
          >
            {{ editorOpen ? "编辑器已打开" : "编辑骨面掩膜" }}
          </button>
          <p v-if="boneGateActionMessage" class="bone-gate-action-message" role="status">
            {{ boneGateActionMessage }}
          </p>
          <figure v-if="nearestFrameDetail.boneGateOverlayHref || nearestFrameDetail.boneGateMaskHref">
            <img
              :src="nearestFrameDetail.boneGateOverlayHref || nearestFrameDetail.boneGateMaskHref"
              alt="当前关键帧骨面门控"
            />
            <figcaption>{{ nearestFrameDetail.boneGateStatusLabel }}</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.overlayHref">
            <img :src="nearestFrameDetail.overlayHref" alt="当前关键帧分割叠加" />
            <figcaption>叠加图</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.maskHref">
            <img :src="nearestFrameDetail.maskHref" alt="当前关键帧分割掩膜" />
            <figcaption>分割掩膜</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.riskMaskHref">
            <img :src="nearestFrameDetail.riskMaskHref" alt="当前关键帧风险图" />
            <figcaption>风险图</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.uncertainMaskHref">
            <img :src="nearestFrameDetail.uncertainMaskHref" alt="当前关键帧不确定性掩膜" />
            <figcaption>不确定性</figcaption>
          </figure>
        </div>
        <div
          v-if="videoPlayback.overlayReviewVideoSrc || videoPlayback.maskReviewVideoSrc"
          class="video-review-link-row"
        >
          <a
            v-if="videoPlayback.overlayReviewVideoSrc"
            :href="videoPlayback.overlayReviewVideoSrc"
            target="_blank"
            rel="noreferrer"
          >
            叠加复核视频
          </a>
          <a
            v-if="videoPlayback.maskReviewVideoSrc"
            :href="videoPlayback.maskReviewVideoSrc"
            target="_blank"
            rel="noreferrer"
          >
            掩膜复核视频
          </a>
        </div>
        <p>{{ videoPlayback.boundaryLabel }}</p>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import type { HotspotFrameDetail, VideoPlaybackAnalysis } from "@/components/analysisPreview";

const props = withDefaults(
  defineProps<{
    videoPlayback: VideoPlaybackAnalysis;
    nearestFrameDetail: HotspotFrameDetail | null;
    loading?: boolean;
    editorOpen?: boolean;
    generateAvailable?: boolean;
    editAvailable?: boolean;
    generateUnavailableReason?: string;
    editUnavailableReason?: string;
  }>(),
  {
    loading: false,
    editorOpen: false,
    generateAvailable: false,
    editAvailable: false,
    generateUnavailableReason: "当前关键帧无法生成骨面门控。",
    editUnavailableReason: "当前关键帧没有可编辑的骨面掩膜。",
  },
);

const emit = defineEmits<{
  jumpToFrame: [detail: HotspotFrameDetail];
  generateBoneGate: [detail: HotspotFrameDetail];
  editBoneGate: [detail: HotspotFrameDetail];
}>();

const activeAction = ref<"generate" | "edit" | null>(null);
const boneGateActionBusy = computed(() => props.loading || props.editorOpen || activeAction.value !== null);
const boneGateActionMessage = computed(() => {
  if (props.loading || activeAction.value === "generate") return "骨面门控任务处理中，生成与编辑操作暂时停用。";
  if (props.editorOpen || activeAction.value === "edit") return "骨面掩膜编辑器已打开，关闭编辑器后可继续操作。";
  if (!props.generateAvailable && !props.editAvailable) return props.generateUnavailableReason;
  if (!props.editAvailable) return props.editUnavailableReason;
  if (!props.generateAvailable) return props.generateUnavailableReason;
  return "";
});

watch(
  () => [props.loading, props.editorOpen] as const,
  ([loading, editorOpen]) => {
    if (!loading && !editorOpen) activeAction.value = null;
  },
);

watch(
  () => props.nearestFrameDetail?.key,
  () => {
    if (!props.loading && !props.editorOpen) activeAction.value = null;
  },
);

async function requestGenerateBoneGate(detail: HotspotFrameDetail) {
  if (boneGateActionBusy.value || !props.generateAvailable) return;
  activeAction.value = "generate";
  emit("generateBoneGate", detail);
  await nextTick();
  if (!props.loading) activeAction.value = null;
}

async function requestEditBoneGate(detail: HotspotFrameDetail) {
  if (boneGateActionBusy.value || !props.editAvailable) return;
  activeAction.value = "edit";
  emit("editBoneGate", detail);
  await nextTick();
  if (!props.editorOpen) activeAction.value = null;
}
</script>

<style scoped>
.video-playback-panel {
  display: grid;
  gap: 9px;
  margin: 10px 0 0;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 9px 10px;
  background: var(--ov-bg-soft);
}

.video-playback-panel header,
.video-playback-panel header div {
  display: flex;
  gap: 7px;
  align-items: center;
  min-width: 0;
}

.video-playback-panel header {
  justify-content: space-between;
}

.video-playback-panel header div {
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 900;
}

.video-playback-panel header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: var(--ov-primary-strong);
}

.video-playback-panel header > span {
  flex: 0 0 auto;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--ov-bg-panel);
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 900;
}

.video-sync-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  align-items: stretch;
}

.video-sync-panel {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 6px;
  padding: 8px;
  background: var(--ov-bg-elevated);
}

.video-sync-status {
  display: grid;
  gap: 2px;
}

.video-sync-status strong,
.video-sync-status span {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.video-sync-status strong {
  color: var(--ov-text);
  font-size: 13px;
}

.video-sync-status span {
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 850;
}

.video-sync-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
}

.video-sync-grid div {
  min-width: 0;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 5px 7px;
  background: var(--ov-bg-soft);
}

.video-sync-grid dt,
.video-sync-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.video-sync-grid dt {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 900;
}

.video-sync-grid dd {
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 900;
}

.video-sync-previews {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.video-sync-previews button {
  grid-column: 1 / -1;
  min-height: 28px;
  border: 1px solid var(--ov-border-strong);
  border-radius: 5px;
  padding: 4px 8px;
  background: var(--ov-bg-elevated);
  color: var(--ov-primary);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.video-sync-previews button:disabled {
  color: var(--ov-text-muted);
  cursor: not-allowed;
}

.bone-gate-action-message {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.video-sync-previews figure {
  display: grid;
  gap: 4px;
  min-width: 0;
  margin: 0;
}

.video-sync-previews img {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 4px;
  object-fit: cover;
  background: var(--ov-bg-media);
}

.video-sync-previews figcaption {
  color: var(--ov-text-secondary);
  font-size: 10px;
  font-weight: 900;
}

.video-review-link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.video-review-link-row a {
  border: 1px solid var(--ov-border-strong);
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--ov-bg-elevated);
  color: var(--ov-primary);
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.video-sync-panel p {
  margin: 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.45;
}
</style>
