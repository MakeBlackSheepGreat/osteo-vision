import { computed, ref, watch } from "vue";

import type { HotspotFrameDetail, VideoPlaybackAnalysis } from "@/components/analysisPreview";

interface UseVideoPlaybackSyncOptions {
  videoPlayback: () => VideoPlaybackAnalysis | null;
  selectedFrameKey: () => string;
  onSelectFrame: (key: string) => void;
}

export function useVideoPlaybackSync(options: UseVideoPlaybackSyncOptions) {
  const currentPlaybackTime = ref(0);
  const playbackDuration = ref(0);
  const lastSyncedFrameKey = ref("");
  const playbackSeekTimeSec = ref<number | null>(null);
  const playbackSeekToken = ref(0);

  const nearestFrameDetail = computed<HotspotFrameDetail | null>(() =>
    nearestFrameDetailForTime(
      options.videoPlayback()?.frameDetails ?? [],
      currentPlaybackTime.value,
      options.selectedFrameKey(),
    ),
  );

  watch(
    () => options.videoPlayback()?.sourcePath ?? "",
    () => {
      // 切换 MP4 输入时重置同步状态，避免沿用上一个视频的时间轴和关键帧。
      currentPlaybackTime.value = 0;
      playbackDuration.value = 0;
      lastSyncedFrameKey.value = "";
      playbackSeekTimeSec.value = null;
      playbackSeekToken.value = 0;
    },
  );

  function syncPlaybackState(timeSec: number, durationSec: number) {
    currentPlaybackTime.value = normalizeSeconds(timeSec);
    playbackDuration.value = normalizeSeconds(durationSec);
    const nearest = nearestFrameDetail.value;
    if (!nearest?.key || nearest.key === lastSyncedFrameKey.value) return;
    lastSyncedFrameKey.value = nearest.key;
    options.onSelectFrame(nearest.key);
  }

  function jumpPlaybackToDetail(detail: HotspotFrameDetail) {
    if (detail.timestampSec === null || !Number.isFinite(detail.timestampSec)) return;
    playbackSeekTimeSec.value = detail.timestampSec;
    playbackSeekToken.value += 1;
    currentPlaybackTime.value = detail.timestampSec;
    lastSyncedFrameKey.value = detail.key;
    options.onSelectFrame(detail.key);
  }

  return {
    currentPlaybackTime,
    playbackDuration,
    playbackSeekTimeSec,
    playbackSeekToken,
    nearestFrameDetail,
    syncPlaybackState,
    jumpPlaybackToDetail,
  };
}

function nearestFrameDetailForTime(
  details: HotspotFrameDetail[],
  timeSec: number,
  selectedFrameKey: string,
): HotspotFrameDetail | null {
  if (!details.length) return null;
  const timedDetails = details.filter(
    (detail) => typeof detail.timestampSec === "number" && Number.isFinite(detail.timestampSec),
  );
  if (!timedDetails.length) return details.find((detail) => detail.key === selectedFrameKey) ?? details[0];

  // 当前平台是 keyframe-based playback analysis：播放时只同步到最近关键帧，不宣称逐帧实时推理。
  return timedDetails.reduce((nearest, detail) =>
    Math.abs((detail.timestampSec ?? 0) - timeSec) < Math.abs((nearest.timestampSec ?? 0) - timeSec)
      ? detail
      : nearest,
  );
}

function normalizeSeconds(value: number): number {
  return Number.isFinite(value) ? value : 0;
}
