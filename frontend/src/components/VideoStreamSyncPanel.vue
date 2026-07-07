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
            <dt>Top BBox</dt>
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
          <button type="button" @click="emit('generateBoneGate', nearestFrameDetail)">
            生成骨面门控
          </button>
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
            <figcaption>mask</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.riskMaskHref">
            <img :src="nearestFrameDetail.riskMaskHref" alt="当前关键帧风险图" />
            <figcaption>risk</figcaption>
          </figure>
          <figure v-if="nearestFrameDetail.uncertainMaskHref">
            <img :src="nearestFrameDetail.uncertainMaskHref" alt="当前关键帧不确定性掩膜" />
            <figcaption>uncertain</figcaption>
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
            mask 复核视频
          </a>
        </div>
        <p>{{ videoPlayback.boundaryLabel }}</p>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import AppIcon from "@/components/AppIcon.vue";
import type { HotspotFrameDetail, VideoPlaybackAnalysis } from "@/components/analysisPreview";

defineProps<{
  videoPlayback: VideoPlaybackAnalysis;
  nearestFrameDetail: HotspotFrameDetail | null;
}>();

const emit = defineEmits<{
  jumpToFrame: [detail: HotspotFrameDetail];
  generateBoneGate: [detail: HotspotFrameDetail];
}>();
</script>

<style scoped>
.video-playback-panel {
  display: grid;
  gap: 9px;
  margin: 10px 0 0;
  border: 1px solid #d4e2f0;
  border-radius: 6px;
  padding: 9px 10px;
  background: #fbfdff;
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
  color: #102136;
  font-size: 13px;
  font-weight: 900;
}

.video-playback-panel header :deep(.app-icon) {
  width: 15px;
  height: 15px;
  color: #2c7ec0;
}

.video-playback-panel header > span {
  flex: 0 0 auto;
  border: 1px solid #d3e2f1;
  border-radius: 999px;
  padding: 3px 8px;
  background: #f2f7fc;
  color: #4d6780;
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
  border: 1px solid #dbe8f4;
  border-radius: 6px;
  padding: 8px;
  background: #ffffff;
}

.video-sync-status {
  display: grid;
  gap: 2px;
}

.video-sync-status strong,
.video-sync-status span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-sync-status strong {
  color: #102136;
  font-size: 13px;
}

.video-sync-status span {
  color: #5a6a7a;
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
  border: 1px solid #e0e8f1;
  border-radius: 5px;
  padding: 5px 7px;
  background: #f8fbfe;
}

.video-sync-grid dt,
.video-sync-grid dd {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-sync-grid dt {
  color: #748494;
  font-size: 10px;
  font-weight: 900;
}

.video-sync-grid dd {
  color: #102136;
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
  border: 1px solid #c9dae8;
  border-radius: 5px;
  padding: 4px 8px;
  background: #f8fbfe;
  color: #145d91;
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.video-sync-previews button:disabled {
  color: #8a99a8;
  cursor: not-allowed;
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
  background: #0f1720;
}

.video-sync-previews figcaption {
  color: #5a6a7a;
  font-size: 10px;
  font-weight: 900;
}

.video-review-link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.video-review-link-row a {
  border: 1px solid #c9dae8;
  border-radius: 999px;
  padding: 3px 8px;
  background: #f8fbfe;
  color: #145d91;
  font-size: 11px;
  font-weight: 900;
  text-decoration: none;
}

.video-sync-panel p {
  margin: 0;
  color: #5a6a7a;
  font-size: 11px;
  line-height: 1.45;
}
</style>
