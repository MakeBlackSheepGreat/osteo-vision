<template>
  <section class="l2-panel" aria-label="L2 离线动态 AR 验证">
    <header>
      <div>
        <strong>L2 离线动态 AR 验证</strong>
        <small>锁定病例内已核验的 L1 标定，通过受控 MP4 与 pose manifest 生成逐帧投影证据。</small>
      </div>
      <span :class="['l1-gate', { ready: l1Ready }]">{{ l1GateLabel }}</span>
    </header>

    <section class="locked-evidence" aria-label="锁定的 L1 标定证据">
      <div class="section-heading">
        <strong>锁定的 L1 标定</strong>
        <small>动态验证只读取病例中已持久化并通过 SHA256 核验的 L1 证据。</small>
      </div>
      <dl class="evidence-grid">
        <div><dt>内参标识</dt><dd>{{ valueLabel(evidence?.camera_intrinsics_id) }}</dd></div>
        <div><dt>标定文件</dt><dd>{{ calibrationArtifactLabel }}</dd></div>
        <div><dt>标定 SHA256</dt><dd class="hash">{{ hashLabel(evidence?.camera_calibration_evidence?.artifact_sha256) }}</dd></div>
        <div><dt>L1 变换 SHA256</dt><dd class="hash">{{ hashLabel(evidence?.transform_sha256) }}</dd></div>
        <div><dt>独立重投影误差</dt><dd>{{ metricThresholdLabel(evidence?.reprojection_error_px, evidence?.reprojection_error_threshold_px, "px") }}</dd></div>
        <div><dt>L1 阈值批准</dt><dd>{{ l1ThresholdApprovalLabel }}</dd></div>
      </dl>
    </section>

    <div class="mode-row">
      <label>
        验证模式
        <select v-model="replayMode" :disabled="busy" data-testid="replay-mode" @change="syncReplayMode">
          <option value="pose_only_engineering">位姿链工程检查（固定 L0）</option>
          <option value="dynamic_ar_validation">动态 AR 验证（严格安全门）</option>
        </select>
      </label>
      <label>
        输入方式
        <select v-model="inputMode" :disabled="busy || replayMode === 'dynamic_ar_validation'" data-testid="input-mode">
          <option value="manual_metadata">人工元数据</option>
          <option value="offline_manifest">离线 manifest</option>
        </select>
      </label>
      <label>
        医生复核状态
        <select v-model="doctorReviewStatus" :disabled="busy" data-testid="doctor-review-status">
          <option value="review_required">待医生复核</option>
          <option value="accepted">可信医生已接受</option>
        </select>
      </label>
      <label>
        回放状态
        <input :value="statusText" readonly />
      </label>
    </div>

    <p v-if="replayMode === 'pose_only_engineering'" class="mode-boundary" data-testid="pose-only-boundary">
      位姿链工程检查只验证时间戳、刚体变换和标定范围，结果固定为 L0 未配准三维参考，不能开启动态导航就绪。
    </p>

    <template v-if="replayMode === 'dynamic_ar_validation'">
      <section class="dynamic-inputs" aria-label="受控动态验证输入">
        <div class="section-heading">
          <strong>受控 MP4 与 pose manifest</strong>
          <small>帧时间戳由后端解码所选 MP4 自动生成并逐帧核对。</small>
        </div>
        <div class="field-grid">
          <label>
            病例已准入 MP4
            <select v-model="selectedVideoInputId" :disabled="busy || !admittedVideoInputs.length" data-testid="video-input">
              <option value="">请选择病例视频</option>
              <option v-for="video in admittedVideoInputs" :key="video.input_id" :value="video.input_id">
                {{ videoOptionLabel(video) }}
              </option>
            </select>
          </label>
          <label>
            视频 SHA256
            <input :value="selectedVideoSha256 || '待选择'" readonly class="hash" data-testid="video-sha256" />
          </label>
          <label>
            解码帧数
            <input :value="selectedVideoFrameCount ? `${selectedVideoFrameCount} 帧` : '待选择'" readonly data-testid="video-frame-count" />
          </label>
          <label>
            视频时间基准
            <input :value="selectedVideoTimestampSource" readonly data-testid="video-timestamp-source" />
          </label>
          <label class="wide-field">
            Pose manifest 受控路径
            <input v-model="manifestPath" :disabled="busy" placeholder="artifacts/navigation/pose_replay_input.json" data-testid="pose-manifest-path" />
          </label>
          <label class="wide-field">
            Pose manifest SHA256
            <input v-model.trim="manifestSha256" :disabled="busy" maxlength="64" placeholder="64 位小写 SHA256" class="hash" data-testid="pose-manifest-sha256" />
          </label>
        </div>
        <p v-if="!admittedVideoInputs.length" class="input-warning" role="status">
          当前病例没有可用于 L2 的已准入 MP4。视频需完成授权、脱敏、SHA256、可解码帧数和病例写入核验。
        </p>
      </section>

      <section class="approval-panel" aria-label="L2 阈值批准">
        <div class="section-heading">
          <strong>L2 阈值批准</strong>
          <small>批准记录与时序、漂移、TRE 代理、独立动态误差、倍率/工作距离变化率、内参切换率、标定歧义及可见投影点阈值均由 pose manifest 的 SHA256 锁定。</small>
        </div>
        <dl class="evidence-grid">
          <div><dt>最近核验状态</dt><dd data-testid="l2-approval-display">{{ l2EvidenceApprovalLabel }}</dd></div>
          <div><dt>提交策略</dt><dd>后端读取 SHA 绑定 manifest</dd></div>
          <div><dt>客户端覆盖</dt><dd>禁用</dd></div>
        </dl>
        <p class="manifest-lock-note">浏览器只提交 manifest 路径、SHA256、所选病例视频和医生复核状态，安全关键阈值与批准记录不能由客户端覆盖。</p>
      </section>
    </template>

    <template v-else>
      <div v-if="inputMode === 'offline_manifest'" class="field-grid">
        <label class="wide-field">
          Pose manifest 路径
          <input v-model="manifestPath" :disabled="busy" placeholder="artifacts/navigation/pose_replay_input.json" data-testid="pose-only-manifest-path" />
        </label>
        <label class="wide-field">
          Pose manifest SHA256
          <input v-model.trim="manifestSha256" :disabled="busy" maxlength="64" placeholder="64 位 SHA256" class="hash" data-testid="pose-only-manifest-sha256" />
        </label>
      </div>
      <div v-else class="json-grid">
        <label>
          人工视频帧时间戳 JSON（秒）
          <textarea v-model="frameTimestampsText" :disabled="busy" rows="4" />
        </label>
        <label>
          人工位姿日志 JSON
          <textarea v-model="posesText" :disabled="busy" rows="9" />
        </label>
        <label>
          人工标定表 JSON
          <textarea v-model="calibrationText" :disabled="busy" rows="9" />
        </label>
        <label>
          工程失效注入 JSON
          <textarea v-model="failureInjectionsText" :disabled="busy" rows="4" />
        </label>
      </div>
    </template>

    <div v-if="replayMode === 'pose_only_engineering'" class="threshold-grid">
      <label>
        最大时间偏移（ms）
        <input v-model.number="maxTimeOffsetMs" :disabled="busy" type="number" min="1" step="1" />
      </label>
      <label>
        跟踪漂移阈值（mm）
        <input v-model.number="driftThresholdMm" :disabled="busy" type="number" min="0.01" step="0.1" />
      </label>
      <label>
        TRE 代理阈值（mm）
        <input v-model.number="treProxyThresholdMm" :disabled="busy" type="number" min="0.01" step="0.1" />
      </label>
      <label>
        独立动态误差阈值（mm）
        <input v-model.number="dynamicTargetErrorThresholdMm" :disabled="busy" type="number" min="0.01" step="0.1" />
      </label>
      <label>
        每帧最少可见投影点
        <input v-model.number="minimumVisibleProjectionPoints" :disabled="busy" type="number" min="1" step="1" />
      </label>
    </div>

    <div class="actions">
      <button type="button" :disabled="runDisabled" :title="runDisabledReason" data-testid="run-replay" @click="runReplay">
        {{ runButtonLabel }}
      </button>
      <button v-if="busy && jobId" type="button" class="secondary" @click="cancelReplay">取消任务</button>
    </div>

    <section v-if="hasReplayEvidence" class="replay-evidence" aria-label="L2 回放证据">
      <div class="section-heading">
        <strong>最近一次回放证据</strong>
        <small>{{ replayEvidenceLevelLabel }}</small>
      </div>
      <dl class="evidence-grid">
        <div><dt>视频绑定</dt><dd>{{ valueLabel(evidence?.video_evidence?.input_id || evidence?.video_input_id) }}</dd></div>
        <div><dt>视频 SHA256 / 帧数</dt><dd class="hash">{{ hashLabel(evidence?.video_evidence?.sha256 || evidence?.video_sha256) }} · {{ countLabel(evidence?.video_evidence?.frame_count ?? evidence?.video_frame_count, "帧") }}</dd></div>
        <div><dt>自动时序检查</dt><dd>{{ timeSyncEvidenceLabel }}</dd></div>
        <div><dt>时序连续性门控</dt><dd data-testid="temporal-safety-gate">{{ temporalSafetyGateLabel }}</dd></div>
        <div><dt>内参切换</dt><dd data-testid="intrinsics-switch-summary">{{ intrinsicsSwitchLabel }}</dd></div>
        <div><dt>最大倍率变化率</dt><dd data-testid="magnification-rate-summary">{{ magnificationRateLabel }}</dd></div>
        <div><dt>最大工作距离变化率</dt><dd data-testid="working-distance-rate-summary">{{ workingDistanceRateLabel }}</dd></div>
        <div><dt>标定选择歧义</dt><dd data-testid="calibration-ambiguity-summary">{{ calibrationAmbiguityLabel }}</dd></div>
        <div><dt>A/B/A 内参振荡</dt><dd data-testid="calibration-oscillation-summary">{{ calibrationOscillationLabel }}</dd></div>
        <div><dt>Tracking drift</dt><dd>{{ metricThresholdLabel(evidence?.microscope_pose_evidence?.drift_mm, evidence?.microscope_pose_evidence?.drift_threshold_mm, "mm") }}</dd></div>
        <div><dt>独立动态误差</dt><dd>{{ metricThresholdLabel(evidence?.microscope_pose_evidence?.tre_mm, evidence?.microscope_pose_evidence?.tre_threshold_mm, "mm") }}</dd></div>
        <div><dt>逐帧投影</dt><dd>{{ projectionEvidenceLabel }}</dd></div>
        <div><dt>叠加视频</dt><dd>{{ artifactLabel(evidence?.overlay_evidence?.path || evidence?.overlay_video_path, evidence?.overlay_evidence?.sha256 || evidence?.overlay_video_sha256) }}</dd></div>
        <div><dt>回放 manifest</dt><dd>{{ artifactLabel(evidence?.pose_replay_manifest_path, evidence?.pose_replay_manifest_sha256) }}</dd></div>
        <div><dt>L2 阈值批准</dt><dd>{{ l2EvidenceApprovalLabel }}</dd></div>
      </dl>
      <p v-if="temporalFailureLabels.length" class="input-warning" data-testid="temporal-failure-closure" role="status">
        时序连续性失败原因：{{ temporalFailureLabels.join("、") }}。本次 L2 已撤销并回退 L0 未配准三维参考。
      </p>
    </section>

    <p class="boundary">
      动态验证任一安全证据缺失、篡改、越界或超限时，整次回放保持 <code>navigation_ready=false</code>
      并回退 L0 未配准三维参考。L2 仅表示离线动态 AR 工程验证。
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { apiClient } from "@/services/apiClient";
import type { CaseInputAsset, L2PoseReplayRequest, L2ReplayMode, ThreeDEvidence } from "@/types/case";

const props = withDefaults(defineProps<{
  caseId: string;
  evidence?: ThreeDEvidence | null;
  videoInputs?: CaseInputAsset[];
  caseAdmissionStatus?: string | null;
  caseAuthorizationStatus?: string | null;
  caseDeidentificationConfirmed?: boolean;
}>(), {
  evidence: null,
  videoInputs: () => [],
  caseAdmissionStatus: null,
  caseAuthorizationStatus: null,
  caseDeidentificationConfirmed: false,
});
const emit = defineEmits<{ completed: [] }>();

const replayMode = ref<L2ReplayMode>("pose_only_engineering");
const inputMode = ref<L2PoseReplayRequest["input_mode"]>("manual_metadata");
const doctorReviewStatus = ref<L2PoseReplayRequest["doctor_review_status"]>("review_required");
const selectedVideoInputId = ref("");
const manifestPath = ref("");
const manifestSha256 = ref("");
const maxTimeOffsetMs = ref(50);
const driftThresholdMm = ref(1);
const treProxyThresholdMm = ref(2);
const dynamicTargetErrorThresholdMm = ref(1.5);
const minimumVisibleProjectionPoints = ref(3);
const frameTimestampsText = ref("[0.0, 0.033, 0.066]");
const posesText = ref(JSON.stringify([
  { timestamp_s: 0.0, matrix: identity(), magnification: 4, working_distance_mm: 300, tracking_status: "tracking" },
  { timestamp_s: 0.033, matrix: translated(0.1), magnification: 4, working_distance_mm: 300, tracking_status: "tracking" },
  { timestamp_s: 0.066, matrix: translated(0.2), magnification: 4, working_distance_mm: 300, tracking_status: "tracking" },
], null, 2));
const calibrationText = ref(JSON.stringify([
  { intrinsics_id: "offline_calibration_4x_300mm", magnification_min: 3.5, magnification_max: 4.5, working_distance_min_mm: 280, working_distance_max_mm: 320 },
], null, 2));
const failureInjectionsText = ref("{}");
const busy = ref(false);
const jobId = ref("");
const statusText = ref("待运行");
const error = ref("");

const evidence = computed(() => props.evidence ?? undefined);
const l1Ready = computed(() => {
  const current = evidence.value;
  const level = String(current?.navigation_level || "").toUpperCase();
  const ready = current?.navigation_ready === true || String(current?.navigation_ready).toLowerCase() === "true";
  return ready
    && level === "L1"
    && String(current?.registration_status || "").toLowerCase() === "registered"
    && current?.camera_calibration_evidence?.artifact_validation?.valid === true
    && isSha256(current.camera_calibration_evidence.artifact_sha256)
    && isSha256(current.transform_sha256)
    && Boolean(String(current.camera_intrinsics_id || "").trim())
    && current.threshold_approval?.status === "approved";
});
const l1GateLabel = computed(() => l1Ready.value ? "L1 标定证据已锁定" : "等待完整 L1 安全证据");
const calibrationArtifactLabel = computed(() => evidence.value?.camera_calibration_evidence?.artifact_validation?.valid === true
  ? valueLabel(evidence.value.camera_calibration_evidence.artifact_path)
  : "待核验");
const l1ThresholdApprovalLabel = computed(() => evidence.value?.threshold_approval?.status === "approved"
  ? `${valueLabel(evidence.value.threshold_approval.protocol_version)} · 已批准`
  : "待批准");

const admittedVideoInputs = computed(() => props.videoInputs.filter(isAdmittedMp4));
const selectedVideo = computed(() => admittedVideoInputs.value.find((item) => item.input_id === selectedVideoInputId.value));
const selectedVideoSha256 = computed(() => stringMetadata(selectedVideo.value, "sha256").toLowerCase());
const selectedVideoFrameCount = computed(() => positiveIntegerMetadata(selectedVideo.value, "frame_count"));
const selectedVideoTimestampSource = computed(() => {
  if (!selectedVideo.value) return "待选择";
  return stringMetadata(selectedVideo.value, "video_timestamp_source")
    || stringMetadata(selectedVideo.value, "timestamp_source")
    || "MP4 解码帧率与帧序号";
});
const dynamicFormReady = computed(() => Boolean(
  selectedVideo.value
  && manifestPath.value.trim()
  && isSha256(manifestSha256.value)
  && doctorReviewStatus.value === "accepted",
));
const runDisabled = computed(() => busy.value || !l1Ready.value || (
  replayMode.value === "dynamic_ar_validation" && !dynamicFormReady.value
  ) || (
  replayMode.value === "pose_only_engineering"
  && inputMode.value === "offline_manifest"
  && (!manifestPath.value.trim() || !isSha256(manifestSha256.value))
));
const runDisabledReason = computed(() => {
  if (busy.value) return "回放任务正在运行";
  if (!l1Ready.value) return "请先完成包含标定文件、变换文件及阈值批准的 L1 安全门控";
  if (replayMode.value === "pose_only_engineering" && inputMode.value === "offline_manifest"
    && (!manifestPath.value.trim() || !isSha256(manifestSha256.value))) {
    return "请填写 pose-only manifest 路径和 64 位 SHA256";
  }
  if (replayMode.value === "pose_only_engineering") return "运行固定 L0 的位姿链工程检查";
  if (!selectedVideo.value) return "请选择病例已准入且含 SHA256 和可解码帧数的 MP4";
  if (!manifestPath.value.trim() || !isSha256(manifestSha256.value)) return "请填写受控 pose manifest 路径和 64 位 SHA256";
  if (doctorReviewStatus.value !== "accepted") return "动态 AR 验证需可信医生接受复核";
  return "运行严格门控的离线动态 AR 验证";
});
const runButtonLabel = computed(() => busy.value
  ? "正在回放"
  : replayMode.value === "dynamic_ar_validation"
    ? "运行 L2 动态 AR 验证"
    : "运行位姿链工程检查（L0）");

const hasReplayEvidence = computed(() => Boolean(evidence.value?.replay_mode || evidence.value?.pose_replay_manifest_path));
const replayEvidenceLevelLabel = computed(() => evidence.value?.navigation_ready === true && evidence.value.navigation_level === "L2"
  ? "L2 动态 AR 工程验证证据已满足"
  : "安全门未通过，当前保持 L0");
const calibrationTransition = computed(() => (
  evidence.value?.calibration_transition_summary
  ?? evidence.value?.calibration_selection
));
const continuityThresholds = computed(() => calibrationTransition.value?.approved_thresholds);
const timeSyncEvidenceLabel = computed(() => {
  const source = valueLabel(evidence.value?.video_evidence?.timestamp_source || evidence.value?.video_timestamp_source);
  const offset = evidence.value?.microscope_pose_evidence?.time_offset_ms;
  const threshold = evidence.value?.l2_threshold_approval?.max_time_offset_ms;
  return `${source} · ${metricThresholdLabel(offset, threshold, "ms")}`;
});
const temporalFailureLabels = computed(() => {
  const recorded = calibrationTransition.value?.failure_reasons?.length
    ? calibrationTransition.value.failure_reasons
    : evidence.value?.failure_reasons ?? [];
  return [...new Set(recorded)]
    .filter((code) => temporalFailureReasonLabels[code])
    .map((code) => temporalFailureReasonLabels[code]);
});
const temporalSafetyGateLabel = computed(() => {
  if (evidence.value?.replay_mode === "pose_only_engineering") return "位姿链工程检查固定 L0";
  const status = String(calibrationTransition.value?.status || "").toLowerCase();
  if (status === "passed") return "已通过连续性检查";
  if (status === "failed_closed" || temporalFailureLabels.value.length) {
    return "已失败闭合 · L2 已撤销并回退 L0";
  }
  return "连续性证据待记录 · 保持 L0";
});
const intrinsicsSwitchLabel = computed(() => {
  const count = calibrationTransition.value?.switch_count
    ?? evidence.value?.microscope_pose_evidence?.intrinsics_switch_count;
  const parsedCount = numberOrNull(count);
  if (parsedCount === null) return "待记录";
  const rate = calibrationTransition.value?.max_intrinsics_switch_rate_hz_observed
    ?? evidence.value?.microscope_pose_evidence?.intrinsics_switch_rate_hz;
  const threshold = continuityThresholds.value?.max_intrinsics_switch_rate_hz
    ?? evidence.value?.l2_threshold_approval?.max_intrinsics_switch_rate_hz
    ?? evidence.value?.microscope_pose_evidence?.intrinsics_switch_rate_threshold_hz;
  const rateLabel = numberOrNull(rate) === null ? "" : ` · 峰值 ${metricThresholdLabel(rate, threshold, "Hz")}`;
  return `${parsedCount} 次${rateLabel}`;
});
const magnificationRateLabel = computed(() => metricThresholdLabel(
  calibrationTransition.value?.max_magnification_rate_per_s
    ?? evidence.value?.microscope_pose_evidence?.magnification_rate_per_s,
  continuityThresholds.value?.max_magnification_rate_per_s
    ?? evidence.value?.l2_threshold_approval?.max_magnification_rate_per_s
    ?? evidence.value?.microscope_pose_evidence?.magnification_rate_threshold_per_s,
  "×/s",
));
const workingDistanceRateLabel = computed(() => metricThresholdLabel(
  calibrationTransition.value?.max_working_distance_rate_mm_per_s
    ?? evidence.value?.microscope_pose_evidence?.working_distance_rate_mm_per_s,
  continuityThresholds.value?.max_working_distance_rate_mm_per_s
    ?? evidence.value?.l2_threshold_approval?.max_working_distance_rate_mm_per_s
    ?? evidence.value?.microscope_pose_evidence?.working_distance_rate_threshold_mm_per_s,
  "mm/s",
));
const calibrationAmbiguityLabel = computed(() => continuityFailureCountLabel(
  calibrationTransition.value?.ambiguous_frame_count,
  "帧",
  "标定选择歧义",
));
const calibrationOscillationLabel = computed(() => continuityFailureCountLabel(
  calibrationTransition.value?.oscillation_count,
  "次",
  "A/B/A 内参振荡",
));
const projectionEvidenceLabel = computed(() => {
  const projection = evidence.value?.projection_evidence;
  if (!projection) return "待记录";
  const frames = numberOrNull(projection.projected_frame_count ?? projection.frame_count);
  const visible = numberOrNull(
    projection.minimum_visible_count_observed
      ?? projection.visible_point_count
      ?? projection.visible_projection_count,
  );
  const total = numberOrNull(projection.point_count ?? projection.total_projection_count);
  if (frames === null && visible === null && total === null) return valueLabel(projection.status);
  return frames === null
    ? `每帧最少可见 ${visible ?? 0}/${total ?? 0} 点`
    : `${frames} 帧 · 可见 ${visible ?? 0}/${total ?? 0} 点`;
});
const l2EvidenceApprovalLabel = computed(() => evidence.value?.l2_threshold_approval?.status === "approved"
  ? `${valueLabel(evidence.value.l2_threshold_approval.protocol_version)} · ${valueLabel(evidence.value.l2_threshold_approval.data_version)}`
  : "待批准");

const temporalFailureReasonLabels: Record<string, string> = {
  magnification_rate_exceeded: "倍率变化率超限",
  working_distance_rate_exceeded: "工作距离变化率超限",
  calibration_switch_rate_exceeded: "内参切换率超限",
  calibration_selection_ambiguous: "标定选择存在歧义",
  calibration_selection_oscillation: "出现 A/B/A 内参振荡",
};

function syncReplayMode() {
  error.value = "";
  if (replayMode.value === "dynamic_ar_validation") inputMode.value = "offline_manifest";
}

async function runReplay() {
  error.value = "";
  if (runDisabled.value) {
    error.value = runDisabledReason.value;
    return;
  }
  try {
    busy.value = true;
    statusText.value = "正在提交";
    const payload = buildPayload();
    const started = await apiClient.startL2PoseReplayJob(payload);
    jobId.value = started.job_id;
    await pollReplay();
  } catch (cause) {
    busy.value = false;
    statusText.value = "失败";
    error.value = cause instanceof Error ? cause.message : "L2 离线回放任务失败";
  }
}

function buildPayload(): L2PoseReplayRequest {
  const base = {
    case_id: props.caseId,
    doctor_review_status: doctorReviewStatus.value,
  };
  if (replayMode.value === "dynamic_ar_validation") {
    const video = selectedVideo.value;
    if (!video) throw new Error("请选择病例已准入 MP4。");
    const path = manifestPath.value.trim();
    const sha256 = manifestSha256.value.trim().toLowerCase();
    if (!path) throw new Error("Pose manifest 受控路径不能为空。");
    if (!isSha256(sha256)) throw new Error("Pose manifest SHA256 必须为 64 位十六进制字符串。");
    return {
      ...base,
      replay_mode: "dynamic_ar_validation",
      input_mode: "offline_manifest",
      video_input_id: video.input_id,
      pose_manifest_path: path,
      pose_manifest_sha256: sha256,
    };
  }
  const common = {
    ...base,
    replay_mode: "pose_only_engineering",
    input_mode: inputMode.value,
    max_time_offset_ms: positive(maxTimeOffsetMs.value, "最大时间偏移"),
    drift_threshold_mm: positive(driftThresholdMm.value, "跟踪漂移阈值"),
    tre_proxy_threshold_mm: positive(treProxyThresholdMm.value, "TRE 代理阈值"),
    dynamic_target_error_threshold_mm: positive(dynamicTargetErrorThresholdMm.value, "独立动态误差阈值"),
    minimum_visible_projection_points: positiveInteger(
      minimumVisibleProjectionPoints.value,
      "每帧最少可见投影点",
    ),
  } satisfies L2PoseReplayRequest;
  if (inputMode.value === "offline_manifest") {
    const path = manifestPath.value.trim();
    const sha256 = manifestSha256.value.trim().toLowerCase();
    if (!path) throw new Error("离线 manifest 路径不能为空。");
    if (!isSha256(sha256)) throw new Error("离线 manifest SHA256 必须为 64 位十六进制字符串。");
    return { ...common, pose_manifest_path: path, pose_manifest_sha256: sha256 };
  }
  const frame_timestamps_s = jsonValue<number[]>(frameTimestampsText.value, "帧时间戳");
  const poses = jsonValue<NonNullable<L2PoseReplayRequest["poses"]>>(posesText.value, "位姿日志");
  const calibration_table = jsonValue<NonNullable<L2PoseReplayRequest["calibration_table"]>>(calibrationText.value, "标定表");
  const failure_injections = jsonValue<Record<string, string[]>>(failureInjectionsText.value, "失效注入");
  if (!Array.isArray(frame_timestamps_s) || !frame_timestamps_s.length) throw new Error("帧时间戳 JSON 至少需要一项。");
  if (!Array.isArray(poses) || !poses.length) throw new Error("位姿日志 JSON 至少需要一项。");
  if (!Array.isArray(calibration_table) || !calibration_table.length) throw new Error("标定表 JSON 至少需要一项。");
  return { ...common, frame_timestamps_s, poses, calibration_table, failure_injections };
}

async function pollReplay() {
  for (let index = 0; index < 60; index += 1) {
    const job = await apiClient.getL2PoseReplayJob(jobId.value);
    statusText.value = job.progress?.message || job.status;
    if (["completed", "failed", "canceled"].includes(job.status)) {
      busy.value = false;
      if (job.status === "completed") emit("completed");
      else error.value = job.error || "L2 离线回放未完成";
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  busy.value = false;
  error.value = "任务仍在运行，可稍后同步病例。";
}

async function cancelReplay() {
  try {
    await apiClient.cancelL2PoseReplayJob(jobId.value);
    statusText.value = "已取消";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "取消 L2 回放任务失败";
  } finally {
    busy.value = false;
  }
}

function isAdmittedMp4(input: CaseInputAsset): boolean {
  const isMp4 = input.channel === "video"
    && (input.mime_type?.toLowerCase() === "video/mp4" || input.path.toLowerCase().endsWith(".mp4"))
    && stringMetadata(input, "input_type") === "video_file";
  const metadataAdmission = stringMetadata(input, "admission_status");
  const caseAdmission = String(props.caseAdmissionStatus || "").toLowerCase();
  const admitted = metadataAdmission === "admitted"
    && ["engineering_analysis_ready", "target_registry_ready", "admitted"].includes(caseAdmission)
    && String(props.caseAuthorizationStatus || "").toLowerCase() === "approved"
    && props.caseDeidentificationConfirmed === true
    && stringMetadata(input, "source_type") === "institutional_handover"
    && stringMetadata(input, "authorization_status") === "approved"
    && input.metadata.deidentification_confirmed === true
    && Boolean(stringMetadata(input, "intake_record_id"));
  return isMp4
    && admitted
    && isSha256(stringMetadata(input, "sha256"))
    && positiveIntegerMetadata(input, "frame_count") > 0
    && !input.quality_flags.some((flag) => flag.blocking);
}

function videoOptionLabel(video: CaseInputAsset): string {
  const fileName = video.path.replace(/\\/g, "/").split("/").at(-1) || video.path;
  return `${fileName} · ${positiveIntegerMetadata(video, "frame_count")} 帧`;
}

function stringMetadata(input: CaseInputAsset | undefined, key: string): string {
  const value = input?.metadata?.[key];
  return typeof value === "string" ? value.trim() : "";
}

function positiveIntegerMetadata(input: CaseInputAsset | undefined, key: string): number {
  const value = Number(input?.metadata?.[key]);
  return Number.isInteger(value) && value > 0 ? value : 0;
}

function isSha256(value: unknown): boolean {
  return /^[0-9a-f]{64}$/i.test(String(value || "").trim());
}

function jsonValue<T>(raw: string, label: string): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(`${label} JSON 格式无效。`);
  }
}

function positive(value: number, label: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) throw new Error(`${label}必须为正数。`);
  return parsed;
}

function positiveInteger(value: number, label: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${label}必须为正整数。`);
  return parsed;
}

function valueLabel(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "待记录";
}

function hashLabel(value: unknown): string {
  const normalized = typeof value === "string" ? value.trim() : "";
  return normalized || "待记录";
}

function countLabel(value: unknown, suffix: string): string {
  const parsed = numberOrNull(value);
  return parsed === null ? "待记录" : `${parsed} ${suffix}`;
}

function metricThresholdLabel(value: unknown, threshold: unknown, unit: string): string {
  const metric = numberOrNull(value);
  const limit = numberOrNull(threshold);
  if (metric === null) return "待记录";
  return `${metric.toFixed(2)} ${unit}${limit === null ? "" : ` / 阈值 ${limit.toFixed(2)} ${unit}`}`;
}

function continuityFailureCountLabel(value: unknown, suffix: string, label: string): string {
  const count = numberOrNull(value);
  if (count === null) return "待记录";
  return count > 0 ? `${count} ${suffix} · 已触发失败闭合` : `0 ${suffix} · 未检出${label}`;
}

function artifactLabel(path: unknown, sha256: unknown): string {
  const pathLabel = valueLabel(path);
  const hash = typeof sha256 === "string" && sha256.trim() ? sha256.trim() : "SHA256 待记录";
  return `${pathLabel} · ${hash}`;
}

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function identity(): number[][] {
  return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
}

function translated(x: number): number[][] {
  return [[1, 0, 0, x], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
}
</script>

<style scoped>
.l2-panel{width:min(100%,var(--ov-content-wide));margin:0 auto 16px;display:grid;gap:12px;border:1px solid var(--ov-border);border-radius:7px;padding:14px;background:var(--ov-bg-elevated)}
header,.actions,.section-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}header>div,.section-heading{display:grid;gap:3px}.section-heading small,header small,.boundary{color:var(--ov-text-muted);font-size:11px}.l1-gate{border:1px solid var(--ov-warning);border-radius:999px;padding:5px 9px;color:var(--ov-warning);font-size:11px;font-weight:900}.l1-gate.ready{border-color:var(--ov-success);color:var(--ov-success)}
.locked-evidence,.dynamic-inputs,.approval-panel,.replay-evidence{display:grid;gap:10px;border-top:1px solid var(--ov-border-subtle);padding-top:12px}
.mode-row,.threshold-grid,.json-grid,.field-grid,.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.mode-row{grid-template-columns:repeat(4,minmax(0,1fr))}.json-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.wide-field{grid-column:span 2}.evidence-grid{margin:0}.evidence-grid>div{min-width:0;border-left:2px solid var(--ov-border);padding-left:8px}.evidence-grid dt{color:var(--ov-text-muted);font-size:10px}.evidence-grid dd{margin:3px 0 0;color:var(--ov-text);font-size:11px;font-weight:800;overflow-wrap:anywhere}
label{display:grid;gap:4px;color:var(--ov-text-secondary);font-size:11px;font-weight:800}input,select,textarea,button{min-width:0;border:1px solid var(--ov-border-strong);border-radius:5px;padding:7px;background:var(--ov-bg-elevated);color:var(--ov-text);font:inherit;overflow-wrap:anywhere}textarea{resize:vertical;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px}.hash{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}button{cursor:pointer;font-weight:800}button:disabled{cursor:not-allowed;opacity:.55}button.secondary{background:transparent}.boundary,.mode-boundary,.input-warning,.manifest-lock-note,.error{margin:0;line-height:1.5;overflow-wrap:anywhere}.mode-boundary,.input-warning{border-left:3px solid var(--ov-warning);padding:7px 9px;background:var(--ov-bg-warning);color:var(--ov-text-secondary);font-size:11px}.manifest-lock-note{color:var(--ov-text-muted);font-size:11px}.error{color:var(--ov-danger);font-size:12px}code{overflow-wrap:anywhere}
@media(max-width:1180px){.mode-row,.threshold-grid,.json-grid,.field-grid,.evidence-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
