<template>
  <section class="l1-panel" :aria-label="panelTitle">
    <header><div><strong>{{ panelTitle }}</strong><small>{{ panelSubtitle }}</small></div><span>{{ statusText }}</span></header>
    <div class="mode-row">
      <label>输入方式<select v-model="mode" data-testid="registration-input-mode"><option value="manual_metadata">人工点对（L0 工程检查）</option><option value="offline_manifest">离线 manifest（L1 证据校验）</option></select></label>
      <label v-if="mode === 'manual_metadata'">配准方法<select v-model="registrationMethod" data-testid="registration-method"><option value="rigid_points">三维刚性点配准</option><option value="rigid_points_with_pnp">三维点配准 + 标定 PnP</option></select></label>
      <label v-if="mode === 'manual_metadata'">模型路径<input v-model="modelPath" placeholder="CBCT/STL 已写入路径" /></label>
      <label v-if="mode === 'offline_manifest'">Manifest 路径<input v-model="manifestPath" data-testid="registration-manifest-path" placeholder="registration_manifest.json" /></label>
      <label v-if="mode === 'offline_manifest'">Manifest SHA256<input v-model="manifestSha256" data-testid="registration-manifest-sha256" maxlength="64" autocomplete="off" placeholder="64 位十六进制摘要" /></label>
    </div>
    <template v-if="mode === 'manual_metadata'">
      <div class="actions"><button type="button" @click="loadExample">载入固定仿体示例</button></div>
      <div class="point-grid">
        <label>CBCT/STL 配准点 JSON<textarea v-model="sourceText" rows="5" /></label>
        <label>仿体/相机参考点 JSON<textarea v-model="targetText" rows="5" /></label>
        <label>独立 TRE 源点 JSON<textarea v-model="validationSourceText" rows="3" /></label>
        <label>独立 TRE 目标点 JSON<textarea v-model="validationTargetText" rows="3" /></label>
      </div>
      <div class="field-grid">
        <label>源坐标系<input v-model="sourceSpace" /></label><label>目标坐标系<input v-model="targetSpace" /></label>
        <label>FRE 阈值 mm<input v-model.number="freThreshold" type="number" min="0.01" step="0.01" /></label>
        <label>TRE 阈值 mm<input v-model.number="treThreshold" type="number" min="0.01" step="0.01" /></label>
        <label>阈值来源<input v-model="thresholdSource" /></label>
        <label>复核状态<input value="待可信医生复核（固定 L0）" disabled /></label>
      </div>
      <div class="field-grid">
        <label>当前倍率 ×<input v-model.number="magnification" type="number" min="0.1" step="0.1" /></label>
        <label>倍率标定下限<input v-model.number="magnificationMin" type="number" min="0.1" step="0.1" /></label>
        <label>倍率标定上限<input v-model.number="magnificationMax" type="number" min="0.1" step="0.1" /></label>
        <label>工作距离 mm<input v-model.number="workingDistance" type="number" min="1" step="1" /></label>
        <label>距离标定下限 mm<input v-model.number="workingDistanceMin" type="number" min="1" step="1" /></label>
        <label>距离标定上限 mm<input v-model.number="workingDistanceMax" type="number" min="1" step="1" /></label>
      </div>
      <details v-if="registrationMethod === 'rigid_points_with_pnp'" class="pnp-panel" open>
        <summary>显微相机 PnP 与独立重投影验证</summary>
        <div class="point-grid">
          <label>相机配准三维点 JSON<textarea v-model="cameraObjectText" rows="5" /></label>
          <label>相机配准像素点 JSON<textarea v-model="cameraImageText" rows="5" /></label>
          <label>独立验证三维点 JSON<textarea v-model="validationCameraObjectText" rows="3" /></label>
          <label>独立验证像素点 JSON<textarea v-model="validationCameraImageText" rows="3" /></label>
          <label>相机内参 3×3 JSON<textarea v-model="cameraMatrixText" rows="3" /></label>
          <label>畸变参数 JSON<textarea v-model="distortionText" rows="3" /></label>
        </div>
        <div class="field-grid">
          <label>内参标识<input v-model="intrinsicsId" /></label>
          <label>相机坐标系<input v-model="cameraSpace" /></label>
          <label>画面宽度 px<input v-model.number="imageWidth" type="number" min="1" step="1" /></label>
          <label>画面高度 px<input v-model.number="imageHeight" type="number" min="1" step="1" /></label>
          <label>重投影阈值 px<input v-model.number="reprojectionThreshold" type="number" min="0.01" step="0.01" /></label>
        </div>
        <div class="field-grid">
          <label>标定文件路径<input v-model="calibrationArtifactPath" placeholder="artifacts/calibration/scope.json" /></label>
          <label>标定文件 SHA256<input v-model="calibrationArtifactSha256" maxlength="64" /></label>
          <label>阈值状态<select v-model="thresholdApprovalStatus"><option value="pending">待批准</option><option value="approved">已批准</option></select></label>
          <label>协议版本<input v-model="thresholdProtocolVersion" /></label>
          <label>数据版本<input v-model="thresholdDataVersion" /></label>
          <label>批准人<input v-model="thresholdApprovedBy" /></label>
          <label>批准时间<input v-model="thresholdApprovedAt" type="datetime-local" /></label>
        </div>
      </details>
    </template>
    <label v-if="mode === 'offline_manifest'" class="review-field">医生复核状态<select v-model="reviewStatus"><option value="review_required">待可信医生复核</option><option value="accepted">可信医生接受</option></select></label>
    <p class="boundary">{{ boundaryText }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions"><button type="button" :disabled="busy" @click="submit">{{ busy ? "任务处理中" : actionText }}</button><button v-if="jobId && busy" type="button" @click="cancel">取消任务</button></div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { apiClient } from "@/services/apiClient";
import type { L1StaticRegistrationRequest, ThreeDEvidence } from "@/types/case";
const props = defineProps<{ caseId: string; evidence?: ThreeDEvidence | null }>();
const emit = defineEmits<{ completed: [] }>();
const mode = ref<"manual_metadata" | "offline_manifest">("manual_metadata"); const modelPath = ref(""); const manifestPath = ref(""); const manifestSha256 = ref("");
const registrationMethod = ref<"rigid_points" | "rigid_points_with_pnp">("rigid_points");
const sourceText = ref(""); const targetText = ref(""); const validationSourceText = ref(""); const validationTargetText = ref("");
const cameraObjectText = ref(""); const cameraImageText = ref(""); const validationCameraObjectText = ref(""); const validationCameraImageText = ref("");
const cameraMatrixText = ref(""); const distortionText = ref("[0,0,0,0,0]"); const intrinsicsId = ref("scope_4x_250mm"); const cameraSpace = ref("camera_optical");
const imageWidth = ref(1280); const imageHeight = ref(720); const reprojectionThreshold = ref(2);
const calibrationArtifactPath = ref(""); const calibrationArtifactSha256 = ref("");
const thresholdApprovalStatus = ref<"pending" | "approved">("pending"); const thresholdProtocolVersion = ref(""); const thresholdDataVersion = ref(""); const thresholdApprovedBy = ref(""); const thresholdApprovedAt = ref("");
const sourceSpace = ref("cbct_lps_mm"); const targetSpace = ref("phantom_reference_mm"); const freThreshold = ref(1); const treThreshold = ref(1); const thresholdSource = ref("phantom_protocol_pending_review"); const reviewStatus = ref<"review_required" | "accepted">("review_required");
const magnification = ref(4); const magnificationMin = ref(2); const magnificationMax = ref(8); const workingDistance = ref(250); const workingDistanceMin = ref(200); const workingDistanceMax = ref(300);
const busy = ref(false); const error = ref(""); const statusText = ref("待运行"); const jobId = ref("");
const panelTitle = computed(() => mode.value === "manual_metadata" ? "L0 静态几何工程检查" : "L1 离线配准证据校验");
const panelSubtitle = computed(() => mode.value === "manual_metadata" ? "人工点对、独立 TRE、倍率和工作距离记录" : "校验和绑定的配准输入、坐标契约与安全门控");
const actionText = computed(() => mode.value === "manual_metadata" ? "运行 L0 工程检查" : "运行 L1 证据校验");
const boundaryText = computed(() => mode.value === "manual_metadata" ? "人工点对模式固定用于 L0 静态几何工程检查，输出保持未配准参考，不能显示 L1 就绪状态。" : "离线 manifest 需同时提交路径和 SHA256。可信医生复核、输入来源、变换、坐标契约和误差门控全部通过后，平台才可显示 L1 静态工程验证状态。");
watch(() => props.evidence?.model_path, (value) => { if (value && !modelPath.value) modelPath.value = value; }, { immediate: true });
function loadExample() { sourceText.value = JSON.stringify([[0,0,0],[20,0,0],[0,20,0],[0,0,20]]); targetText.value = JSON.stringify([[5,-3,2],[25,-3,2],[5,17,2],[5,-3,22]]); validationSourceText.value = JSON.stringify([[10,10,10]]); validationTargetText.value = JSON.stringify([[15,7,12]]); const objects = [[-30,-20,0],[30,-20,0],[30,20,0],[-30,20,0],[-20,-10,25],[20,10,30],[0,-25,15],[0,25,20]]; const pixels = [[596.717355,316.40251],[703.015907,319.589071],[700.412639,389.202713],[594.749572,386.365798],[613.535459,332.291048],[679.197857,366.792024],[648.989669,308.578333],[645.833905,392.408567]]; cameraObjectText.value = JSON.stringify(objects.slice(0,6)); cameraImageText.value = JSON.stringify(pixels.slice(0,6)); validationCameraObjectText.value = JSON.stringify(objects.slice(6)); validationCameraImageText.value = JSON.stringify(pixels.slice(6)); cameraMatrixText.value = JSON.stringify([[920,0,640],[0,910,360],[0,0,1]]); statusText.value = "已载入工程仿体示例"; }
function matrix(value: string, label: string, columns: number, minimumRows = 1): number[][] { const parsed = JSON.parse(value); if (!Array.isArray(parsed) || parsed.length < minimumRows || parsed.some((row) => !Array.isArray(row) || row.length !== columns || row.some((item) => !Number.isFinite(Number(item))))) throw new Error(`${label}必须是数值 Nx${columns} JSON 数组`); return parsed.map((row) => row.map(Number)); }
function points(value: string, label: string): number[][] { return matrix(value, label, 3, 1); }
function numbers(value: string, label: string): number[] { const parsed = JSON.parse(value); if (!Array.isArray(parsed) || parsed.some((item) => !Number.isFinite(Number(item)))) throw new Error(`${label}必须是数值 JSON 数组`); return parsed.map(Number); }
function sha256(value: string, label: string): string { const normalized = value.trim().toLowerCase(); if (!/^[0-9a-f]{64}$/.test(normalized)) throw new Error(`${label}必须是 64 位十六进制摘要`); return normalized; }
async function submit() { error.value = ""; busy.value = true; statusText.value = "正在提交"; try { const payload: L1StaticRegistrationRequest = mode.value === "offline_manifest" ? { case_id: props.caseId, input_mode: "offline_manifest", registration_method: registrationMethod.value, unit: "mm", doctor_review_status: reviewStatus.value, registration_manifest_path: manifestPath.value.trim(), registration_manifest_sha256: sha256(manifestSha256.value,"Manifest SHA256") } : { case_id: props.caseId, input_mode: "manual_metadata", registration_method: registrationMethod.value, unit: "mm", doctor_review_status: "review_required", model_path: modelPath.value, source_points: points(sourceText.value,"源点"), target_points: points(targetText.value,"目标点"), validation_source_points: points(validationSourceText.value,"TRE 源点"), validation_target_points: points(validationTargetText.value,"TRE 目标点"), source_space: sourceSpace.value, target_space: targetSpace.value, fre_threshold_mm: freThreshold.value, tre_threshold_mm: treThreshold.value, threshold_source: thresholdSource.value, ...(registrationMethod.value === "rigid_points_with_pnp" ? { camera_object_points: matrix(cameraObjectText.value,"相机三维点",3,4), camera_image_points: matrix(cameraImageText.value,"相机像素点",2,4), validation_camera_object_points: matrix(validationCameraObjectText.value,"独立验证三维点",3), validation_camera_image_points: matrix(validationCameraImageText.value,"独立验证像素点",2), camera_matrix: matrix(cameraMatrixText.value,"相机内参",3,3), distortion_coefficients: numbers(distortionText.value,"畸变参数"), image_size_px: [imageWidth.value,imageHeight.value] as [number,number], intrinsics_id: intrinsicsId.value, camera_space: cameraSpace.value, reprojection_threshold_px: reprojectionThreshold.value, camera_calibration_evidence: { artifact_path: calibrationArtifactPath.value.trim(), artifact_sha256: calibrationArtifactSha256.value.trim().toLowerCase() }, threshold_approval: { status: thresholdApprovalStatus.value, protocol_version: thresholdProtocolVersion.value.trim(), data_version: thresholdDataVersion.value.trim(), approved_by: thresholdApprovedBy.value.trim(), approved_at: timestampValue(thresholdApprovedAt.value), fre_threshold_mm: freThreshold.value, tre_threshold_mm: treThreshold.value, reprojection_threshold_px: reprojectionThreshold.value } } : {}), microscope_pose_evidence: { intrinsics_id: intrinsicsId.value, magnification: magnification.value, calibration_magnification_min: magnificationMin.value, calibration_magnification_max: magnificationMax.value, working_distance_mm: workingDistance.value, calibration_working_distance_min_mm: workingDistanceMin.value, calibration_working_distance_max_mm: workingDistanceMax.value, depth_source: "offline_phantom_scale", depth_status: "valid" } }; if (payload.input_mode === "offline_manifest" && !payload.registration_manifest_path) throw new Error("Manifest 路径不能为空"); const started = await apiClient.startL1RegistrationJob(payload); jobId.value = started.job_id; await poll(); } catch (cause) { error.value = cause instanceof Error ? cause.message : "静态配准任务失败"; statusText.value = "失败"; busy.value = false; } }
function timestampValue(value: string) { if (!value.trim()) return ""; const parsed = new Date(value); if (Number.isNaN(parsed.getTime())) throw new Error("批准时间格式无效"); return parsed.toISOString(); }
async function poll() { for (let index=0; index<60; index+=1) { const job = await apiClient.getL1RegistrationJob(jobId.value); statusText.value = job.progress?.message || job.status; if (["completed","failed","canceled"].includes(job.status)) { busy.value = false; if (job.status === "completed") emit("completed"); else error.value = job.error || "L1 配准未完成"; return; } await new Promise((resolve) => setTimeout(resolve, 300)); } busy.value = false; error.value = "任务仍在运行，可稍后同步病例"; }
async function cancel() { await apiClient.cancelL1RegistrationJob(jobId.value); busy.value = false; statusText.value = "已取消"; }
</script>

<style scoped>
.l1-panel{width:min(100%,var(--ov-content-wide));margin:0 auto 16px;display:grid;gap:12px;border:1px solid var(--ov-border);border-radius:7px;padding:14px;background:var(--ov-bg-elevated)} header,.actions{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap} header>div{display:grid;gap:3px} header small,.boundary{color:var(--ov-text-muted);font-size:11px}.mode-row,.field-grid,.point-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.point-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.review-field{max-width:360px}.pnp-panel{display:grid;gap:10px;border:1px solid var(--ov-border-subtle);border-radius:6px;padding:10px}.pnp-panel summary{cursor:pointer;color:var(--ov-text);font-weight:800}.pnp-panel>.point-grid,.pnp-panel>.field-grid{margin-top:10px} label{display:grid;gap:4px;color:var(--ov-text-secondary);font-size:11px;font-weight:800} input,select,textarea,button{min-width:0;border:1px solid var(--ov-border-strong);border-radius:5px;padding:7px;background:var(--ov-bg-elevated);color:var(--ov-text);font:inherit;overflow-wrap:anywhere} input:disabled{background:var(--ov-bg-subtle);color:var(--ov-text-muted)} textarea{resize:vertical} button{cursor:pointer;font-weight:800}.boundary,.error{margin:0;line-height:1.5}.error{color:var(--ov-danger);font-size:12px}@media(max-width:1180px){.mode-row,.field-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.point-grid{grid-template-columns:1fr}}
</style>
