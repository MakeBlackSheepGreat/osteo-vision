<template>
  <div class="video-stream-input-panel">
    <div class="stream-panel-header">
      <AppIcon name="camera" variant="tile" tone="cyan" />
      <div class="stream-panel-copy">
        <strong>视频流输入</strong>
        <span>{{ streamStatusLabel }}</span>
      </div>
    </div>
    <div
      class="stream-preview-viewport"
      :class="{ active: streamPreviewActive, 'has-file-video': fileVideoPreviewActive }"
      aria-label="摄像头与 MP4 共用视频流预览"
    >
      <video
        v-if="fileVideoPreviewActive"
        class="stream-file-preview"
        :src="videoStreamPreviewSrc"
        controls
        muted
        preload="metadata"
        playsinline
      ></video>
      <video
        v-show="!fileVideoPreviewActive"
        ref="cameraPreviewVideoRef"
        class="stream-live-preview"
        muted
        autoplay
        playsinline
      ></video>
      <div v-if="!streamPreviewActive" class="stream-preview-empty">
        <strong>视频流预览区</strong>
        <span>可打开摄像头或选择 MP4 示例</span>
      </div>
      <div v-if="fileVideoPreviewActive" class="stream-source-chip">
        MP4 示例 · {{ videoStreamPreviewLabel || "已选择视频" }}
      </div>
    </div>
    <div class="stream-action-row">
      <AppButton
        variant="secondary"
        size="sm"
        icon="camera"
        :disabled="isOpeningCamera"
        @click="emit('startCamera')"
      >
        打开摄像头
      </AppButton>
      <AppButton variant="ghost" size="sm" :disabled="!cameraActive" @click="emit('stopCamera')">停止</AppButton>
      <AppButton variant="ghost" size="sm" :disabled="loading || !hasCase || !cameraActive" @click="emit('importCamera')">
        写入
      </AppButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";

const props = withDefaults(
  defineProps<{
    cameraStream: MediaStream | null;
    cameraActive: boolean;
    cameraStatusLabel: string;
    isOpeningCamera: boolean;
    loading: boolean;
    hasCase: boolean;
    videoStreamPreviewSrc?: string;
    videoStreamPreviewLabel?: string;
  }>(),
  {
    videoStreamPreviewSrc: "",
    videoStreamPreviewLabel: "",
  },
);

const emit = defineEmits<{
  startCamera: [];
  stopCamera: [];
  importCamera: [];
}>();

const cameraPreviewVideoRef = ref<HTMLVideoElement | null>(null);
const fileVideoPreviewActive = computed(() => Boolean(props.videoStreamPreviewSrc));
const streamPreviewActive = computed(() => props.cameraActive || fileVideoPreviewActive.value);
const streamStatusLabel = computed(() => {
  if (fileVideoPreviewActive.value) {
    return `MP4 示例正在视频流区预览：${props.videoStreamPreviewLabel || "已选择视频"}`;
  }
  return props.cameraStatusLabel;
});

watch(
  () => props.cameraStream,
  async (stream) => {
    await nextTick();
    if (!cameraPreviewVideoRef.value) return;
    cameraPreviewVideoRef.value.srcObject = stream;
    if (stream && !fileVideoPreviewActive.value) {
      await cameraPreviewVideoRef.value.play().catch(() => undefined);
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.video-stream-input-panel {
  display: grid;
  gap: 6px;
  margin: 8px 0 7px;
  border: 1px solid #c7dceb;
  border-radius: 6px;
  padding: 7px 8px;
  background:
    linear-gradient(180deg, rgba(247, 252, 255, 0.98), rgba(236, 247, 255, 0.98)),
    #eef8ff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 8px 18px rgba(20, 86, 138, 0.08);
}

.stream-panel-header {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.stream-panel-header :deep(.app-icon--tile) {
  width: 28px;
  height: 28px;
}

.stream-panel-copy strong,
.stream-panel-copy span {
  display: block;
  min-width: 0;
}

.stream-panel-copy strong {
  color: #102136;
  font-size: 12px;
  line-height: 1.3;
}

.stream-panel-copy span {
  margin-top: 2px;
  color: #5a6a7a;
  font-size: 11px;
  line-height: 1.35;
}

.stream-preview-viewport {
  position: relative;
  display: grid;
  place-items: center;
  aspect-ratio: 16 / 9;
  min-height: 124px;
  overflow: hidden;
  border: 1px solid #b9d2e5;
  border-radius: 5px;
  background:
    linear-gradient(90deg, rgba(30, 111, 166, 0.11) 1px, transparent 1px),
    linear-gradient(180deg, rgba(30, 111, 166, 0.11) 1px, transparent 1px),
    linear-gradient(145deg, #dff1fd, #c1e0f5);
  background-size: 20px 20px, 20px 20px, auto;
  isolation: isolate;
}

.stream-preview-viewport.has-file-video {
  background: #0f1720;
}

.stream-preview-viewport::after {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(255, 255, 255, 0.55);
  content: "";
  pointer-events: none;
}

.stream-live-preview,
.stream-file-preview {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  min-height: inherit;
  background: #0f1720;
}

.stream-live-preview {
  object-fit: cover;
  opacity: 0;
}

.stream-preview-viewport.active .stream-live-preview {
  opacity: 1;
}

.stream-file-preview {
  object-fit: contain;
}

.stream-preview-empty {
  position: relative;
  z-index: 3;
  display: grid;
  gap: 4px;
  justify-items: center;
  max-width: 82%;
  border: 1px solid rgba(30, 111, 166, 0.28);
  border-radius: 6px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.86);
  color: #4d6780;
  text-align: center;
}

.stream-preview-empty strong,
.stream-preview-empty span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.stream-preview-empty strong {
  color: #155f96;
  font-size: 12px;
  line-height: 1.2;
}

.stream-preview-empty span {
  color: #6c8299;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
}

.stream-source-chip {
  position: absolute;
  z-index: 4;
  right: 7px;
  bottom: 7px;
  max-width: calc(100% - 14px);
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 999px;
  padding: 3px 7px;
  background: rgba(15, 23, 32, 0.76);
  color: #e8f3ff;
  font-size: 10px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stream-action-row {
  display: grid;
  grid-template-columns: 1fr 0.72fr 0.72fr;
  gap: 6px;
}

.stream-action-row :deep(.app-button) {
  min-width: 0;
  padding-right: 7px;
  padding-left: 7px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.88) inset;
}
</style>
