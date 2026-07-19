<template>
  <section class="navigation-safety" aria-label="导航安全门控">
    <header>
      <div><span>导航安全门控</span><strong>{{ level }} · {{ statusLabel }}</strong></div>
      <b :class="{ ready: gatePassed }">{{ gateStatusText }}</b>
    </header>
    <div class="navigation-safety__grid">
      <p><span>显微镜倍率</span><strong>{{ numberLabel(microscope.magnification, "×") }}</strong></p>
      <p><span>工作距离</span><strong>{{ numberLabel(microscope.working_distance_mm, " mm") }}</strong></p>
      <p><span>位姿跟踪</span><strong>{{ textLabel(microscope.pose_tracking_status) }}</strong></p>
      <p><span>TRE</span><strong>{{ thresholdLabel(microscope.tre_mm, microscope.tre_threshold_mm) }}</strong></p>
      <p><span>漂移</span><strong>{{ thresholdLabel(microscope.drift_mm, microscope.drift_threshold_mm) }}</strong></p>
      <p><span>相机标定</span><strong>{{ textLabel(microscope.calibration_status) }}</strong></p>
      <p><span>内参标识</span><strong>{{ textLabel(evidence?.camera_intrinsics_id || microscope.intrinsics_id) }}</strong></p>
      <p><span>独立重投影误差</span><strong>{{ pixelThresholdLabel(evidence?.reprojection_error_px, evidence?.reprojection_error_threshold_px) }}</strong></p>
      <p><span>标定文件</span><strong>{{ calibrationArtifactLabel }}</strong></p>
      <p><span>阈值批准</span><strong>{{ thresholdApprovalLabel }}</strong></p>
    </div>
    <p v-if="reasons.length" class="navigation-safety__warning">降级原因：{{ reasons.join("、") }}</p>
    <p class="navigation-safety__boundary">L0 为未配准三维参考，L1 为静态/仿体配准验证，L2 为动态 AR 验证。任何安全证据缺失均禁止显示导航就绪。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ThreeDEvidence } from "@/types/case";
const props = defineProps<{ evidence?: ThreeDEvidence | null }>();
const microscope = computed(() => props.evidence?.microscope_pose_evidence ?? {});
const gatePassed = computed(() => props.evidence?.navigation_ready === true && ["L1", "L2"].includes(level.value));
const level = computed(() => props.evidence?.navigation_level || "L0");
const statusLabel = computed(() => level.value === "L2" && gatePassed.value
  ? "动态 AR 验证"
  : level.value === "L1" && gatePassed.value
    ? "静态配准验证"
    : "未配准三维参考");
const gateStatusText = computed(() => level.value === "L2" && gatePassed.value
  ? "动态 AR 证据已满足"
  : level.value === "L1" && gatePassed.value
    ? "静态配准证据已满足"
    : "已降级为三维参考");
const reasonLabels: Record<string, string> = {
  registration_not_verified: "配准未验证", transform_missing: "坐标变换缺失",
  transform_file_not_found: "变换文件不存在", transform_format_mismatch: "变换文件格式与声明不一致",
  transform_format_unsupported: "变换文件格式不受支持", transform_sha256_missing: "变换文件校验码缺失",
  transform_sha256_invalid: "变换文件校验码格式无效", transform_sha256_mismatch: "变换文件校验码不一致",
  transform_matrix_unreadable: "变换矩阵无法读取", transform_matrix_shape_invalid: "变换矩阵尺寸无效",
  transform_matrix_non_finite: "变换矩阵含无效数值", transform_matrix_not_homogeneous: "变换矩阵不满足齐次形式",
  transform_matrix_not_invertible: "变换矩阵不可逆", coordinate_chain_missing: "坐标链缺失",
  coordinate_chain_space_missing: "坐标链空间名称缺失", coordinate_chain_direction_missing: "坐标链方向缺失",
  coordinate_chain_direction_invalid: "坐标链方向无效", coordinate_chain_unit_missing: "坐标链单位缺失",
  coordinate_chain_unit_conversion_missing: "坐标链单位换算证据缺失", coordinate_chain_step_not_ready: "坐标链步骤未就绪",
  coordinate_chain_discontinuous: "坐标链不连续", coordinate_chain_unit_discontinuous: "坐标链单位不连续",
  registration_error_invalid_or_missing: "配准误差缺失或无效",
  registration_error_threshold_invalid_or_missing: "配准误差阈值缺失或无效",
  registration_error_source_missing: "配准误差来源缺失", registration_error_threshold_exceeded: "配准误差超限",
  magnification_not_recorded: "倍率未记录", magnification_calibration_range_missing: "倍率标定范围缺失",
  magnification_calibration_range_invalid: "倍率标定范围无效", magnification_out_of_calibration_range: "倍率超出标定范围",
  working_distance_not_recorded: "工作距离未记录", working_distance_calibration_range_missing: "工作距离标定范围缺失",
  working_distance_calibration_range_invalid: "工作距离标定范围无效",
  working_distance_out_of_calibration_range: "工作距离超出标定范围",
  camera_calibration_invalid_or_missing: "相机标定无效或缺失", pose_tracking_invalid_or_missing: "位姿跟踪无效或缺失",
  frame_pose_time_sync_out_of_bounds: "影像与位姿时间不同步", tre_not_recorded: "TRE 未记录", tre_threshold_exceeded: "TRE 超限",
  drift_not_recorded: "漂移未记录", drift_threshold_exceeded: "漂移超限", doctor_review_not_accepted: "医生复核未通过",
  depth_or_scale_source_invalid: "深度或尺度来源无效",
  camera_reprojection_validation_missing: "独立重投影验证缺失",
  reprojection_error_threshold_exceeded: "独立重投影误差超限",
  reprojection_fit_error_threshold_exceeded: "PnP 拟合重投影误差超限",
  camera_calibration_evidence_missing: "相机标定证据缺失",
  camera_calibration_artifact_not_verified: "相机标定文件未通过核验",
  camera_calibration_artifact_path_missing: "相机标定文件路径缺失",
  camera_calibration_artifact_sha256_invalid_or_missing: "相机标定文件校验码缺失或无效",
  camera_calibration_artifact_sha256_mismatch: "相机标定文件校验码不一致",
  camera_calibration_matrix_mismatch: "相机内参与标定文件不一致",
  camera_calibration_distortion_mismatch: "畸变参数与标定文件不一致",
  camera_calibration_image_size_mismatch: "图像尺寸与标定文件不一致",
  threshold_approval_missing: "阈值批准证据缺失",
  threshold_policy_not_approved: "阈值策略尚未批准",
  threshold_protocol_version_missing: "阈值协议版本缺失",
  threshold_data_version_missing: "阈值数据版本缺失",
  threshold_approver_missing: "阈值批准人缺失",
  threshold_approval_time_missing: "阈值批准时间缺失",
  magnification_rate_exceeded: "倍率变化率超限",
  working_distance_rate_exceeded: "工作距离变化率超限",
  calibration_switch_rate_exceeded: "内参切换率超限",
  calibration_selection_ambiguous: "标定选择存在歧义",
  calibration_selection_oscillation: "出现 A/B/A 内参振荡",
  video_variable_frame_rate_unsupported: "视频帧间隔不满足已验证恒定帧率门",
};
const evidence = computed(() => props.evidence ?? {});
const calibrationArtifactLabel = computed(() => evidence.value.camera_calibration_evidence?.artifact_validation?.valid === true ? "SHA256 与参数已核验" : "待核验");
const thresholdApprovalLabel = computed(() => evidence.value.threshold_approval?.status === "approved" ? `${evidence.value.threshold_approval.protocol_version || "版本待记录"} · 已批准` : "待批准");
const reasons = computed(() => (props.evidence?.failure_reasons ?? []).map((item) => reasonLabels[item] ?? item));
function textLabel(value: unknown) { return typeof value === "string" && value.trim() ? value : "待记录"; }
function numberLabel(value: unknown, suffix: string) { const parsed = Number(value); return Number.isFinite(parsed) ? `${parsed}${suffix}` : "待记录"; }
function thresholdLabel(value: unknown, threshold: unknown) { const a = Number(value); const b = Number(threshold); return Number.isFinite(a) ? `${a.toFixed(2)} mm${Number.isFinite(b) ? ` / 阈值 ${b.toFixed(2)} mm` : ""}` : "待记录"; }
function pixelThresholdLabel(value: unknown, threshold: unknown) { const a = Number(value); const b = Number(threshold); return Number.isFinite(a) ? `${a.toFixed(2)} px${Number.isFinite(b) ? ` / 阈值 ${b.toFixed(2)} px` : ""}` : "待记录"; }
</script>

<style scoped>
.navigation-safety{width:min(100%,var(--ov-content-wide));margin:0 auto 16px;border:1px solid var(--ov-border);border-radius:7px;padding:14px;background:var(--ov-bg-elevated)}
.navigation-safety header{display:flex;justify-content:space-between;gap:16px;align-items:center}.navigation-safety header div{display:grid;gap:3px}.navigation-safety span{color:var(--ov-text-muted);font-size:11px}.navigation-safety strong{overflow-wrap:anywhere}.navigation-safety b{color:var(--ov-warning);font-size:12px}.navigation-safety b.ready{color:var(--ov-success)}
.navigation-safety__grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.navigation-safety__grid p{display:grid;gap:3px;margin:0;border-left:2px solid var(--ov-border);padding-left:9px}.navigation-safety__grid strong{font-size:12px}.navigation-safety__warning,.navigation-safety__boundary{margin:10px 0 0;line-height:1.45;overflow-wrap:anywhere}.navigation-safety__warning{color:var(--ov-warning);font-size:12px}.navigation-safety__boundary{color:var(--ov-text-muted);font-size:11px}@media(max-width:1180px){.navigation-safety__grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
