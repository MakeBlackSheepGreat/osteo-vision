import { computed, ref, watch } from "vue";

import type { HotspotFrameDetail, VideoPlaybackAnalysis } from "@/components/analysisPreview";

interface UseVideoPlaybackSyncOptions {
  videoPlayback: () => VideoPlaybackAnalysis | null;
  selectedFrameKey: () => string;
  onSelectFrame: (key: string) => void;
}

interface TimedFrameDetail {
  detail: HotspotFrameDetail;
  timestampSec: number;
  sourceIndex: number;
}

interface FrameDetailIndex {
  displayable: HotspotFrameDetail[];
  timed: TimedFrameDetail[];
}

// 关键帧清单随一次分析结果整体替换；按数组引用缓存索引，避免播放 timeupdate 重复线性过滤与扫描。
const frameDetailIndexes = new WeakMap<HotspotFrameDetail[], FrameDetailIndex>();

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
    seekPlaybackToTime(detail.timestampSec);
    lastSyncedFrameKey.value = detail.key;
    options.onSelectFrame(detail.key);
  }

  function seekPlaybackToTime(timeSec: number) {
    const normalized = normalizeSeconds(timeSec);
    playbackSeekTimeSec.value = normalized;
    playbackSeekToken.value += 1;
    currentPlaybackTime.value = normalized;
  }

  return {
    currentPlaybackTime,
    playbackDuration,
    playbackSeekTimeSec,
    playbackSeekToken,
    nearestFrameDetail,
    syncPlaybackState,
    jumpPlaybackToDetail,
    seekPlaybackToTime,
  };
}

export function nearestFrameDetailForTime(
  details: HotspotFrameDetail[],
  timeSec: number,
  selectedFrameKey: string,
): HotspotFrameDetail | null {
  if (!details.length) return null;
  const index = frameDetailIndexFor(details);
  if (!index.displayable.length) return details.find((detail) => detail.key === selectedFrameKey) ?? details[0];
  if (!index.timed.length) {
    return index.displayable.find((detail) => detail.key === selectedFrameKey) ?? index.displayable[0];
  }

  // 当前平台是 keyframe-based playback analysis：播放时只同步到最近关键帧，不宣称逐帧实时推理。
  const nextIndex = lowerBoundTimestamp(index.timed, timeSec);
  const next = index.timed[nextIndex];
  const previous = nextIndex > 0
    ? index.timed[firstIndexForTimestamp(index.timed, index.timed[nextIndex - 1].timestampSec)]
    : undefined;
  if (!previous) return next.detail;
  if (!next) return previous.detail;
  const previousDistance = Math.abs(previous.timestampSec - timeSec);
  const nextDistance = Math.abs(next.timestampSec - timeSec);
  if (previousDistance !== nextDistance) return previousDistance < nextDistance ? previous.detail : next.detail;
  return previous.sourceIndex <= next.sourceIndex ? previous.detail : next.detail;
}

function frameDetailIndexFor(details: HotspotFrameDetail[]): FrameDetailIndex {
  const cached = frameDetailIndexes.get(details);
  if (cached) return cached;

  const displayable: HotspotFrameDetail[] = [];
  const timed: TimedFrameDetail[] = [];
  details.forEach((detail, sourceIndex) => {
    if (detail.displayAllowed === false) return;
    displayable.push(detail);
    if (typeof detail.timestampSec === "number" && Number.isFinite(detail.timestampSec)) {
      timed.push({ detail, timestampSec: detail.timestampSec, sourceIndex });
    }
  });
  timed.sort((left, right) => left.timestampSec - right.timestampSec || left.sourceIndex - right.sourceIndex);

  const index = { displayable, timed };
  frameDetailIndexes.set(details, index);
  return index;
}

function lowerBoundTimestamp(details: TimedFrameDetail[], timeSec: number): number {
  let low = 0;
  let high = details.length;
  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if (details[middle].timestampSec < timeSec) low = middle + 1;
    else high = middle;
  }
  return low;
}

function firstIndexForTimestamp(details: TimedFrameDetail[], timestampSec: number): number {
  return lowerBoundTimestamp(details, timestampSec);
}

function normalizeSeconds(value: number): number {
  return Number.isFinite(value) ? value : 0;
}
