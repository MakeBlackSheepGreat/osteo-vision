<template>
  <section class="anatomy-3d" aria-label="CBCT/STL 三维证据工作台">
    <input
      ref="cbctInput"
      class="anatomy-3d__file-input"
      type="file"
      multiple
      accept=".dcm,.dicom,.nii,.nii.gz,.nrrd,.mha,.mhd"
      @change="handleCbctFiles"
    />
    <input
      ref="surfaceInput"
      class="anatomy-3d__file-input"
      type="file"
      accept=".stl,.glb,.gltf"
      @change="handleSurfaceModelFile"
    />
    <header class="anatomy-3d__header">
      <div class="anatomy-3d__titleblock">
        <span>三维证据参考层</span>
        <h2>CBCT/STL 术前证据参考</h2>
        <p>只展示已导入或已生成的三维证据；未配准前不做导航定位。</p>
      </div>
      <div class="anatomy-3d__status" :class="statusClass">
        <strong>{{ riskSummary.label }}</strong>
        <small>{{ isRegistered ? registrationLabel : `${registrationLabel} / 非导航锁定` }}</small>
      </div>
    </header>

    <ol
      class="anatomy-3d__workflow-strip"
      :class="{ 'is-focus-view': viewLayoutMode === 'threeD' }"
      aria-label="三维证据工作流状态"
    >
      <li
        v-for="step in migratedWorkflowSteps"
        :key="step.key"
        class="anatomy-3d__workflow-step"
        :class="[`is-${step.state}`]"
        :title="step.detail"
      >
        <span>{{ step.index }}</span>
        <strong>{{ step.title }}</strong>
        <small>{{ step.detail }}</small>
        <em>{{ step.stateLabel }}</em>
      </li>
    </ol>

    <div
      class="anatomy-3d__body"
      :class="{
        'is-focus-view': viewLayoutMode === 'threeD',
        'is-model-empty': modelLoadState !== 'loaded',
        'is-model-loaded': modelLoadState === 'loaded',
      }"
    >
      <aside class="anatomy-3d__object-tree" aria-label="对象列表">
        <section class="anatomy-3d__import-card" aria-label="CBCT 导入与建模检查">
          <header>
            <div>
              <span>CBCT 建模入口</span>
              <strong>{{ cbctImportSummary.title }}</strong>
            </div>
            <small>{{ cbctImportSummary.detail }}</small>
          </header>
          <div class="anatomy-3d__import-actions">
            <button
              type="button"
              :disabled="modelingOperationBusy"
              :title="modelingOperationBusy ? '三维建模任务处理中，请稍候' : '选择 CBCT 体数据或 DICOM 序列'"
              @click="openCbctPicker"
            >
              导入 CBCT
            </button>
            <button
              type="button"
              :disabled="modelingOperationBusy"
              :title="modelingOperationBusy ? '三维建模任务处理中，请稍候' : '选择 Slicer 导出的 STL/GLB 表面模型'"
              @click="openSurfacePicker"
            >
              导入 STL/GLB
            </button>
            <button
              v-if="localImportedFiles.length"
              type="button"
              :disabled="!canStartModelingJob"
              :title="canStartModelingJob ? '提交三维建模检查任务' : '等待所选文件写入后端证据区'"
              @click="() => startCbctModelingJob()"
            >
              检查/生成表面
            </button>
            <button
              v-if="canCancelModelingJob"
              type="button"
              :disabled="modelingJobCanceling"
              :title="modelingJobCanceling ? '正在取消三维建模任务' : '取消当前三维建模任务'"
              @click="cancelCbctModelingJob"
            >
              {{ modelingJobCanceling ? "正在取消" : "取消任务" }}
            </button>
            <button
              v-if="modelingPollingPaused"
              type="button"
              :disabled="modelingOperationBusy"
              title="重新读取后端三维建模任务状态"
              @click="refreshCbctModelingJob"
            >
              刷新任务状态
            </button>
            <button v-if="localImportedFiles.length && !modelingOperationBusy" type="button" @click="clearLocalEvidence">
              清空本地选择
            </button>
          </div>
          <p v-if="modelingJobStatus !== 'idle' || localImportedFiles.length" class="anatomy-3d__job-status">
            {{ modelingJobStatusLabel }}
          </p>
          <details class="anatomy-3d__modeling-check-details">
            <summary>
              <strong>导入与建模检查</strong>
              <small>{{ cbctModelingChecks.filter((check) => check.ready).length }} / {{ cbctModelingChecks.length }} 项通过</small>
            </summary>
            <ol class="anatomy-3d__modeling-checks">
              <li v-for="check in cbctModelingChecks" :key="check.label" :class="{ 'is-ready': check.ready }">
                <span>{{ check.ready ? "通过" : "待办" }}</span>
                <p>{{ check.label }}</p>
              </li>
            </ol>
          </details>
        </section>
        <details class="anatomy-3d__sidebar-section anatomy-3d__object-browser">
          <summary>
            <span>证据节点</span>
            <strong>病例对象</strong>
            <small>{{ objectTreeGroups.reduce((count, group) => count + group.items.length, 0) }} 个对象，可展开管理显示状态</small>
          </summary>
          <ul class="anatomy-3d__subject-hierarchy">
            <li v-for="group in objectTreeGroups" :key="group.name" class="anatomy-3d__tree-group">
              <header>
                <span class="anatomy-3d__folder-icon" aria-hidden="true"></span>
                <strong>{{ group.name }}</strong>
                <small>{{ group.detail }}</small>
              </header>
              <button
                v-for="item in group.items"
                :key="item.name"
                type="button"
                :class="[
                  'anatomy-3d__tree-item',
                  { 'is-muted': item.muted, 'is-active-node': activeTreeNodeName === item.name },
                ]"
                :disabled="!item.interactive"
                :title="item.interactive ? `切换${item.name}显示状态` : `${item.name}当前只读或无可渲染对象`"
                @click="activateTreeNode(item)"
              >
                <span
                  class="anatomy-3d__visibility"
                  :class="{ 'is-visible': !item.muted }"
                  aria-hidden="true"
                ></span>
                <span class="anatomy-3d__lock-state" aria-hidden="true">{{ item.locked ? "锁" : "开" }}</span>
                <div>
                  <strong>{{ item.name }}</strong>
                  <small>{{ item.detail }}</small>
                </div>
                <em>{{ item.state }}</em>
              </button>
            </li>
          </ul>
        </details>
      </aside>

      <main class="anatomy-3d__views" :class="[`is-tool-${activeWorkspaceTool}`, `is-layout-${viewLayoutMode}`]" aria-label="三维参考视图区">
        <section
          ref="canvasHost"
          class="anatomy-3d__viewport"
          :class="{
            'is-model-empty': modelLoadState !== 'loaded',
            'is-model-loaded': modelLoadState === 'loaded',
          }"
          :data-model-state="modelLoadState"
          aria-label="三维规划视图"
          @dblclick="toggleThreeDMaximize"
        >
          <div class="anatomy-3d__view-title">
            <div>
              <span>下颌三维模型</span>
              <strong>{{ modelSourceLabel }}</strong>
              <small>{{ modelLoadNote }}</small>
            </div>
            <div class="anatomy-3d__view-badge">
              <span>{{ modelFormatLabel }}</span>
              <strong>{{ registrationBadgeLabel }}</strong>
              <small>{{ coordinateSpaceLabel }}</small>
            </div>
          </div>
          <div
            v-if="modelLoadState === 'loaded'"
            class="anatomy-3d__viewport-toolbar"
          >
            <div class="anatomy-3d__legend" aria-label="模型状态图例">
              <span><i class="reference"></i>真实模型优先</span>
              <span><i class="plane"></i>未配准不映射</span>
              <span><i class="projection"></i>{{ hotspotProjectionLabel }}</span>
            </div>
            <div class="anatomy-3d__view-controls" aria-label="三维视图控制">
              <button v-if="modelLoadState === 'loaded'" type="button" @click="resetCamera">重置视角</button>
              <button
                v-if="modelLoadState === 'loaded'"
                type="button"
                :class="{ 'is-active': autoRotateModel }"
                :aria-pressed="autoRotateModel"
                @click="toggleAutoRotate"
              >
                自动旋转：{{ autoRotateModel ? "开" : "关" }}
              </button>
              <button v-if="modelLoadState === 'loaded'" type="button" @click="toggleObjectVisibility('mandible')">
                {{ objectVisibility.mandible ? "隐藏模型" : "显示模型" }}
              </button>
              <button v-if="normalizedHotspots.length" type="button" @click="focusFirstCandidate">
                {{ isRegistered ? "查看候选定位" : "查看候选示意" }}
              </button>
              <button
                v-if="modelLoadState === 'loaded'"
                type="button"
                :aria-pressed="viewLayoutMode === 'threeD'"
                :title="viewLayoutMode === 'threeD' ? '恢复三维工作台布局' : '展开主三维视图'"
                @click.stop="toggleThreeDMaximize"
              >
                {{ viewLayoutMode === "threeD" ? "退出专注" : "专注视图" }}
              </button>
            </div>
          </div>
          <div v-if="modelLoadState !== 'loaded'" class="anatomy-3d__empty-viewport">
            <strong>未加载三维模型</strong>
            <p>导入 Slicer 导出的 STL/GLB，或由 CBCT 标签生成表面后显示；未配准时只作参考。</p>
            <small>{{ modelLoadNote }}</small>
            <small v-if="normalizedHotspots.length" class="anatomy-3d__empty-hotspot-summary">
              已联动 {{ normalizedHotspots.length }} 个视频候选区，模型载入后可继续检查空间关系。
            </small>
            <div class="anatomy-3d__empty-actions">
              <button
                type="button"
                :disabled="modelingOperationBusy"
                :title="modelingOperationBusy ? '三维建模任务处理中，请稍候' : '选择 Slicer 导出的 STL/GLB 表面模型'"
                @click="openSurfacePicker"
              >
                导入 STL/GLB
              </button>
              <button
                type="button"
                :disabled="modelingOperationBusy"
                :title="modelingOperationBusy ? '三维建模任务处理中，请稍候' : '选择 CBCT 体数据或 DICOM 序列'"
                @click="openCbctPicker"
              >
                导入 CBCT
              </button>
            </div>
          </div>
          <div v-if="selectedHotspot" class="anatomy-3d__selection-feedback" role="status" aria-live="polite">
            <strong>候选区已联动</strong>
            <span>{{ selectedHotspotFeedback }}</span>
          </div>
          <div v-if="showViewportLabels" class="anatomy-3d__viewport-label-layer" aria-label="三维标注标签">
            <button
              v-for="label in viewportLabelItems"
              :key="label.key"
              type="button"
              class="anatomy-3d__viewport-label"
              :class="[`is-${label.kind}`, { 'is-selected': label.selected, 'is-muted': label.muted }]"
              :style="{ left: `${label.x}%`, top: `${label.y}%` }"
              @click="selectViewportLabel(label)"
            >
              <span>{{ label.shortLabel }}</span>
              <strong>{{ label.label }}</strong>
              <small>{{ label.detail }}</small>
            </button>
          </div>
          <dl v-if="modelLoadState === 'loaded'" class="anatomy-3d__metrics">
            <div>
              <dt>显示模式</dt>
              <dd>{{ modeLabel }}</dd>
            </div>
            <div>
              <dt>方向复核</dt>
              <dd>{{ displayUpAxisLabel }}</dd>
            </div>
            <div>
              <dt>配准误差</dt>
              <dd>{{ registrationErrorLabel }}</dd>
            </div>
            <div>
              <dt>候选置信度</dt>
              <dd>{{ confidenceLabel }}</dd>
            </div>
          </dl>
        </section>

        <section class="anatomy-3d__model-check-panel" aria-label="模型检查结果">
          <details class="anatomy-3d__model-check-details">
            <summary>
              <div>
                <span>建模检查</span>
                <strong>数据链完整性</strong>
              </div>
              <small>{{ navigationGuardSummary }}</small>
            </summary>
            <div class="anatomy-3d__model-check-content">
              <ol class="anatomy-3d__model-check-list">
                <li v-for="check in cbctModelingChecks" :key="check.label" :class="{ 'is-ready': check.ready }">
                  <span>{{ check.ready ? "通过" : "待办" }}</span>
                  <div>
                    <strong>{{ check.label }}</strong>
                    <small>{{ check.detail }}</small>
                  </div>
                </li>
              </ol>
              <p>没有配准矩阵、误差记录和医生复核前，荧光候选区与 CBCT/STL 只并列展示，不做空间定位。</p>
            </div>
          </details>
        </section>
      </main>

      <aside class="anatomy-3d__inspector" aria-label="三维证据与复核面板">
        <div class="anatomy-3d__inspector-heading">
          <div class="anatomy-3d__panel-title">
            <span>证据检查</span>
            <strong>状态与复核</strong>
          </div>
          <small>{{ evidenceFields.length }} 项证据字段</small>
        </div>
        <dl class="anatomy-3d__evidence-summary">
          <div v-for="field in summaryEvidenceFields" :key="field.label">
            <dt>{{ field.label }}</dt>
            <dd>{{ field.value }}</dd>
          </div>
        </dl>
        <details class="anatomy-3d__technical-evidence" aria-label="技术证据详情">
          <summary>
            <strong>技术证据详情</strong>
            <small>证据字段、配准条件与医生复核边界</small>
          </summary>
          <div class="anatomy-3d__technical-evidence-content">
            <details class="anatomy-3d__evidence-drawer" aria-label="完整三维证据字段">
              <summary>
                <strong>完整证据字段</strong>
                <small>{{ evidenceFields.length }} 项，可展开核对路径、来源和边界。</small>
              </summary>
              <dl class="anatomy-3d__evidence-grid">
                <div v-for="field in evidenceFields" :key="field.label">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ field.value }}</dd>
                </div>
              </dl>
            </details>
            <details class="anatomy-3d__registration-guard" aria-label="真实导航前置条件">
              <summary>
                <strong>真实空间映射前置条件</strong>
                <small>{{ navigationGuardSummary }}</small>
              </summary>
              <ul>
                <li v-for="item in registrationGuardItems" :key="item.label" :class="{ 'is-ready': item.ready }">
                  <span>{{ item.ready ? "已就绪" : "缺失" }}</span>
                  <p>{{ item.label }}</p>
                </li>
              </ul>
            </details>
            <details class="anatomy-3d__markups" aria-label="配准点表">
              <summary>
                <strong>配准点表</strong>
                <small>{{ registrationMarkupsSummary }}</small>
              </summary>
              <div class="anatomy-3d__markup-table">
                <button
                  v-for="markup in registrationMarkupRows"
                  :key="markup.id"
                  type="button"
                  class="anatomy-3d__markup-row"
                  :class="{ 'is-selected': selectedMarkupId === markup.id, 'is-ready': markup.ready }"
                  :disabled="!markup.ready"
                  :title="markup.ready ? `查看${markup.label}` : `${markup.label}缺少可核验坐标，当前不可定位`"
                  @click="selectMarkup(markup.id)"
                >
                  <span>{{ markup.shortLabel }}</span>
                  <strong>{{ markup.label }}</strong>
                  <small>{{ markup.sourceLabel }} 至 {{ markup.targetLabel }}</small>
                  <em>{{ markup.residualLabel }}</em>
                  <b>{{ markup.statusLabel }}</b>
                </button>
                <p v-if="!registrationMarkupRows.length" class="anatomy-3d__markup-empty">
                  当前证据中没有可核验的配准点，需导入真实标志点及坐标后才能交互定位。
                </p>
              </div>
            </details>
            <details class="anatomy-3d__transform-chain" aria-label="坐标变换链">
              <summary>
                <strong>坐标变换链</strong>
                <small>{{ transformChainSummary }}</small>
              </summary>
              <ol>
                <li v-for="step in transformChainItems" :key="step.name" :class="{ 'is-ready': step.ready }">
                  <span>{{ step.ready ? "已就绪" : "缺失" }}</span>
                  <div>
                    <strong>{{ step.name }}</strong>
                    <small>{{ step.fromSpace }} 至 {{ step.toSpace }}</small>
                    <em>{{ step.detail }}</em>
                  </div>
                </li>
              </ol>
            </details>
            <details class="anatomy-3d__workflow" aria-label="三维模型接入流程">
              <summary>
                <strong>三维接入工作流</strong>
                <small>展开查看输入、曲线、平面、几何计算与医生复核链路。</small>
              </summary>
              <div v-for="step in workflowSteps" :key="step.index">
                <span>{{ step.index }}</span>
                <strong>{{ step.title }}</strong>
                <small>{{ step.detail }}</small>
              </div>
            </details>
            <details class="anatomy-3d__boundary" aria-label="医生复核边界">
              <summary>医生复核边界</summary>
              <p>{{ boundaryNote }}</p>
            </details>
          </div>
        </details>
        <div v-if="normalizedHotspots.length" class="anatomy-3d__hotspot-list">
          <header class="anatomy-3d__hotspot-list-heading">
            <span>视频联动</span>
            <strong>候选区域</strong>
          </header>
          <button
            v-for="hotspot in normalizedHotspots"
            :key="hotspot.key"
            type="button"
            :class="[
              'anatomy-3d__hotspot',
              `is-${hotspot.risk}`,
              { selected: selectedHotspotKey === hotspot.key, 'is-reference-projection': !isRegistered },
            ]"
            @click="selectHotspot(hotspot.key)"
          >
            <span>{{ hotspot.shortLabel }}</span>
            <strong>{{ hotspot.label }}</strong>
            <small>置信度 {{ Math.round(hotspot.confidence * 100) }}% · {{ hotspotProjectionLabel }}</small>
          </button>
        </div>
      </aside>
    </div>

    <p class="anatomy-3d__disclaimer">
      该视图用于展示脱敏 CBCT/STL/GLB 三维参考和 ICG 候选区的空间关系；未完成配准、误差记录和医生复核时仅为示意参考，不代表自动诊断、真实术中导航定位或手术边界。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import { apiClient } from "@/services/apiClient";
import type {
  CandidateRegion,
  ThreeDEvidence,
  ThreeDEvidenceMarkup,
  ThreeDEvidenceTransformStep,
  ThreeDGeometryManifest,
  ThreeDSceneManifest,
  ThreeDSceneManifestV2,
  ThreeDScenePlane,
} from "@/types/case";

interface Props {
  candidates: CandidateRegion[];
  caseId?: string;
  metrics?: Record<string, unknown>;
  modeLabel?: string;
  threeDEvidence?: ThreeDEvidence | null;
}

type RiskLevel = "high" | "medium" | "low";
type WorkspaceTool = "layout" | "planes" | "roi";
type ViewLayoutMode = "four" | "threeD" | "reconstruction";
type SliceKey = "axial" | "coronal" | "sagittal";
type ObjectVisibilityKey = "cbct" | "mandible" | "curvePlanes" | "candidates" | "registration";
type ViewportLabelKind = "markup" | "plane" | "hotspot";

interface RegistrationMarkupRow {
  id: string;
  shortLabel: string;
  label: string;
  sourceLabel: string;
  targetLabel: string;
  residualLabel: string;
  statusLabel: string;
  ready: boolean;
  position: THREE.Vector3;
}

interface TransformChainItem {
  name: string;
  fromSpace: string;
  toSpace: string;
  detail: string;
  ready: boolean;
}

interface MigratedWorkflowStep {
  key: string;
  index: string;
  title: string;
  detail: string;
  state: "ready" | "partial" | "blocked";
  stateLabel: string;
}

interface ObjectTreeItem {
  key: ObjectVisibilityKey;
  name: string;
  detail: string;
  state: string;
  muted: boolean;
  locked?: boolean;
  interactive: boolean;
}

interface ObjectTreeGroup {
  name: string;
  detail: string;
  items: ObjectTreeItem[];
}

interface ViewportLabelItem {
  key: string;
  kind: ViewportLabelKind;
  shortLabel: string;
  label: string;
  detail: string;
  x: number;
  y: number;
  selected: boolean;
  muted: boolean;
  targetKey?: string;
}

interface HotspotSpec {
  key: string;
  label: string;
  shortLabel: string;
  risk: RiskLevel;
  confidence: number;
  frameKey: string;
  frameIndex: number | null;
  timestampSec: number | null;
  position: THREE.Vector3;
  normal: THREE.Vector3;
  scale: number;
}

interface ScenePlaneDisplay {
  id: string;
  label: string;
  position: THREE.Vector3;
  rotation: THREE.Vector3;
  scale: THREE.Vector3;
}

interface LocalImportedFile {
  name: string;
  size: number;
  type: string;
  kind: "cbct" | "surface";
  backendPath?: string;
  uploadError?: string;
  uploadStatus?: "local" | "uploading" | "uploaded" | "failed";
}

const props = withDefaults(defineProps<Props>(), {
  metrics: () => ({}),
  modeLabel: "术中融合证据",
});

const emit = defineEmits<{
  selectCandidateFrame: [payload: { candidateId: string; frameKey: string; frameIndex: number | null; timestampSec: number | null }];
  threeDEvidencePersisted: [];
}>();

const canvasHost = ref<HTMLDivElement | null>(null);
const cbctInput = ref<HTMLInputElement | null>(null);
const surfaceInput = ref<HTMLInputElement | null>(null);
const selectedHotspotKey = ref("");
const selectedMarkupId = ref("");
const activeTreeNodeName = ref("下颌表面模型");
const modelLoadState = ref<"fallback" | "loaded" | "failed">("fallback");
const loadedModelPath = ref("");
const localThreeDEvidence = ref<ThreeDEvidence | null>(null);
const localImportedFiles = ref<LocalImportedFile[]>([]);
const localSurfaceObjectUrl = ref("");
const modelingJobId = ref("");
const modelingJobStatus = ref<"idle" | "queued" | "running" | "completed" | "failed" | "canceled" | "segmentation_required">("idle");
const modelingJobMessage = ref("");
const modelingJobCanceling = ref(false);
const modelingPollingPaused = ref(false);
let modelingPollGeneration = 0;
const geometryManifest = ref<ThreeDGeometryManifest | null>(null);
const geometryLoadState = ref<"idle" | "loading" | "loaded" | "failed">("idle");
const activeWorkspaceTool = ref<WorkspaceTool>("layout");
const viewLayoutMode = ref<ViewLayoutMode>("four");
const sliceOffsets = ref<Record<SliceKey, number>>({
  axial: 0,
  coronal: 0,
  sagittal: 0,
});
const objectVisibility = ref<Record<ObjectVisibilityKey, boolean>>({
  cbct: true,
  mandible: true,
  curvePlanes: true,
  candidates: true,
  registration: true,
});
const autoRotateModel = ref(false);

const riskColors: Record<RiskLevel, number> = {
  high: 0xd83b3e,
  medium: 0xd88b18,
  low: 0x15966a,
};

const riskLabels: Record<RiskLevel, string> = {
  high: "高风险复核",
  medium: "中等观察",
  low: "低风险背景",
};

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;
let rootGroup: THREE.Group | null = null;
let boneGroup: THREE.Group | null = null;
let hotspotGroup: THREE.Group | null = null;
let planningGuideGroup: THREE.Group | null = null;
let anatomyPlaneGroup: THREE.Group | null = null;
let referenceStageGroup: THREE.Group | null = null;
let registrationMarkupGroup: THREE.Group | null = null;
let fallbackBoneGroup: THREE.Group | null = null;
let loadedAnatomyGroup: THREE.Group | null = null;
let modelLoadSequence = 0;
let frameId = 0;
let resizeObserver: ResizeObserver | null = null;

const evidence = computed(() => localThreeDEvidence.value ?? props.threeDEvidence ?? null);
const evidenceModelPath = computed(() => stringFromEvidence(evidence.value?.model_path));
const evidenceModelFormat = computed(() => stringFromEvidence(evidence.value?.model_format).toLowerCase());
const sceneManifest = computed<ThreeDSceneManifest | null>(() =>
  isEvidenceRecord(evidence.value?.scene_manifest) ? (evidence.value?.scene_manifest as ThreeDSceneManifest) : null,
);
const sceneManifestV2 = computed<ThreeDSceneManifestV2 | null>(() =>
  isEvidenceRecord(evidence.value?.scene_manifest_v2) ? (evidence.value?.scene_manifest_v2 as ThreeDSceneManifestV2) : null,
);
const geometryManifestPath = computed(() => stringFromEvidence(evidence.value?.geometry_manifest_path));
const hasEvidenceModel = computed(() => Boolean(evidenceModelPath.value));
const isRegistered = computed(() => stringFromEvidence(evidence.value?.registration_status).toLowerCase() === "registered");

const modelSourceLabel = computed(() => {
  if (modelLoadState.value === "failed") return "三维模型加载失败";
  if (modelLoadState.value === "loaded") {
    return humanizeEvidenceText(stringFromEvidence(evidence.value?.model_source)) || "病例三维表面模型";
  }
  return hasEvidenceModel.value ? "待接入病例三维模型" : "未接入真实三维模型";
});

const displayModeLabel = computed(() => (modelLoadState.value === "loaded" ? "真实模型参考" : "空白待接入"));
const registrationLabel = computed(() => {
  if (isRegistered.value) return "已配准";
  return "未配准 / 非导航";
});
const registrationBadgeLabel = computed(() => (isRegistered.value ? "已配准" : "参考"));
const coordinateSpaceLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.coordinate_space)) || "坐标系未记录");
const modelFileNameLabel = computed(() => stringFromEvidence(evidence.value?.model_file_name) || fileNameFromPath(evidenceModelPath.value) || "文件名未记录");
const exportedFromLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.exported_from)) || "导出工具未记录");
const dicomSeriesLabel = computed(() => stringFromEvidence(evidence.value?.dicom_series_uid) || "DICOM 序列未记录");
const segmentationSourceLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.segmentation_source)) || "分割来源未记录");
const segmentationReviewStatusLabel = computed(
  () => statusLabel(humanizeEvidenceText(stringFromEvidence(evidence.value?.segmentation_review_status)), false) || "分割复核状态未记录",
);
const registrationMethodLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.registration_method)) || "配准方法未记录");
const doctorReviewStatusLabel = computed(
  () => statusLabel(humanizeEvidenceText(stringFromEvidence(evidence.value?.doctor_review_status)), false) || "医生复核状态未记录",
);
const evidenceAnalysisModeLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.analysis_mode)) || "分析模式未记录");
const evidenceDataBoundaryLabel = computed(() => humanizeEvidenceText(stringFromEvidence(evidence.value?.data_boundary)) || "三维数据边界未记录");
const transformPathLabel = computed(() => stringFromEvidence(evidence.value?.transform_path) || "坐标变换文件未记录");
const modelFormatLabel = computed(() => evidenceModelFormat.value.toUpperCase() || (modelLoadState.value === "loaded" ? "三维模型" : "待接入"));
const registrationErrorLabel = computed(() => {
  const value = evidence.value?.registration_error_mm;
  if (typeof value === "number" && Number.isFinite(value)) return `${value.toFixed(2)} mm`;
  if (typeof value === "string" && value.trim()) return value;
  return "未记录";
});
const fiducialCount = computed(() => numberFromEvidenceValue(evidence.value?.fiducial_count));
const surfacePointCount = computed(() => numberFromEvidenceValue(evidence.value?.surface_point_count));
const navigationReady = computed(() => {
  const raw = evidence.value?.navigation_ready;
  if (typeof raw === "boolean") return raw;
  if (typeof raw === "string") return ["true", "yes", "ready", "1"].includes(raw.trim().toLowerCase());
  return false;
});
const boundaryNote = computed(
  () =>
    humanizeEvidenceText(stringFromEvidence(evidence.value?.boundary_note)) ||
    "当前三维视图只提供空间理解和医生复核参考；未记录配准误差时不得作为真实术中导航或手术边界。",
);
const viewSpaceMapping = computed(() => evidence.value?.view_space_mapping ?? sceneManifestV2.value?.scene?.view_space_mapping ?? null);
const orientationReviewStatus = computed(
  () =>
    stringFromEvidence(evidence.value?.orientation_review_status) ||
    stringFromEvidence(sceneManifestV2.value?.scene?.orientation_review_status),
);
const displayOrientationStatus = computed(
  () =>
    stringFromEvidence(evidence.value?.display_orientation_status) ||
    stringFromEvidence(sceneManifestV2.value?.scene?.display_orientation_status),
);
const inferIdentityMhaJawDisplayFlip = computed(() => {
  const coordinateSpace = stringFromEvidence(evidence.value?.coordinate_space).toLowerCase();
  if (!coordinateSpace.startsWith("cbct_physical_lps_mm")) return false;
  const sceneRecord = (sceneManifestV2.value?.scene ?? null) as Record<string, unknown> | null;
  const volumeGeometry = isEvidenceRecord(sceneRecord?.volume_geometry) ? sceneRecord?.volume_geometry : null;
  const direction = Array.isArray(volumeGeometry?.direction) ? volumeGeometry.direction.map(Number) : [];
  const identityDirection =
    direction.length === 9 &&
    direction.every((value, index) => Number.isFinite(value) && Math.abs(value - (index % 4 === 0 ? 1 : 0)) < 1e-6);
  const sourceText = [
    evidenceModelPath.value,
    evidence.value?.model_source,
    evidence.value?.segmentation_source,
    ...(sceneManifestV2.value?.nodes ?? []).flatMap((node) => [node.name, node.path, node.source]),
  ]
    .map((value) => stringFromEvidence(value).toLowerCase())
    .join(" ");
  return identityDirection && (/\.mha\b|\.mhd\b/.test(sourceText) || sourceText.includes("toothfairy2") || sourceText.includes("d036"));
});
const orientationReviewLabel = computed(() => {
  const status = orientationReviewStatus.value || displayOrientationStatus.value;
  if (!status) return inferIdentityMhaJawDisplayFlip.value ? "MHA 轴向推断 / 待复核" : "方向复核未记录";
  return statusLabel(humanizeEvidenceText(status), false);
});
const displayUpAxisLabel = computed(() => {
  const axis = stringFromEvidence(viewSpaceMapping.value?.display_up_axis);
  if (axis === "-physical_z") return "显示上方 = -Z 轴";
  if (axis === "physical_z") return "显示上方 = Z 轴";
  return inferIdentityMhaJawDisplayFlip.value ? "显示上方 = -Z 轴" : "显示上方 = Z 轴";
});
const modelRotationXDegrees = computed(() => {
  const explicitRotation = numberFromEvidenceValue(viewSpaceMapping.value?.frontend_rotation_x_degrees);
  if (explicitRotation != null) return explicitRotation;
  return inferIdentityMhaJawDisplayFlip.value ? 90 : -90;
});
const hotspotProjectionLabel = computed(() => (isRegistered.value ? "已配准空间映射" : "2D 候选示意投影"));
const modelLoadNote = computed(() => {
  if (modelLoadState.value === "loaded") return `已加载 ${fileNameFromPath(loadedModelPath.value) || "三维模型"}；完整路径见证据字段`;
  if (modelLoadState.value === "failed") return "真实模型文件无法解析，未显示任何替代示意模型";
  return "未检测到真实 STL/GLB，当前保持空白检查状态";
});
const localCbctFiles = computed(() => localImportedFiles.value.filter((file) => file.kind === "cbct"));
const localSurfaceFiles = computed(() => localImportedFiles.value.filter((file) => file.kind === "surface"));
const cbctImportSummary = computed(() => {
  if (localSurfaceFiles.value.length) {
    const file = localSurfaceFiles.value[0];
    return {
      title: "表面模型已接入",
      detail: `${file.name} · ${fileSizeLabel(file.size)}；${uploadStateLabel(file)}；正在用于三维预览和检查。`,
    };
  }
  if (localCbctFiles.value.length) {
    const failed = localCbctFiles.value.find((file) => file.uploadStatus === "failed");
    if (failed) {
      return {
        title: "CBCT 写入失败",
        detail: `${failed.name}：${failed.uploadError || "后端未返回可用错误信息"}。`,
      };
    }
    const uploadedCount = localCbctFiles.value.filter((file) => file.uploadStatus === "uploaded").length;
    return {
      title: uploadedCount ? "CBCT 体数据已写入" : "CBCT 体数据写入中",
      detail: `${localCbctFiles.value.length} 个文件，${uploadedCount} 个已写入后端；写入后自动提交检查/建模任务。`,
    };
  }
  return {
    title: "等待 CBCT 或 STL/GLB",
    detail: "优先导入 Slicer 导出的 STL/GLB；原始 CBCT 体数据会先进入检查清单。",
  };
});
const cbctModelingChecks = computed(() => [
  {
    label: "体数据来源",
    detail: "CBCT/DICOM 或 NIfTI/NRRD 已记录来源。",
    ready: localCbctFiles.value.length > 0 || hasEvidenceModel.value,
  },
  {
    label: "证据包写入",
    detail: "CBCT/STL/GLB 写入后端 artifact 或病例证据字段。",
    ready:
      localImportedFiles.value.some((file) => file.uploadStatus === "uploaded") ||
      Boolean(evidence.value?.model_path && !localThreeDEvidence.value),
  },
  {
    label: "表面模型",
    detail: "下颌分割或表面模型已接入三维预览。",
    ready: modelLoadState.value === "loaded" || localSurfaceFiles.value.length > 0,
  },
  {
    label: "复核字段",
    detail: "坐标系、分割复核和医生边界进入证据字段。",
    ready: Boolean(localThreeDEvidence.value) || Boolean(props.threeDEvidence),
  },
  {
    label: "候选边界",
    detail: "荧光视频候选区只作参考叠加，未配准时保持非导航。",
    ready: true,
  },
]);
const evidenceUploadBusy = computed(() => localImportedFiles.value.some((file) => file.uploadStatus === "uploading"));
const modelingJobBusy = computed(() => ["queued", "running"].includes(modelingJobStatus.value) && !evidenceUploadBusy.value);
const modelingOperationBusy = computed(
  () => evidenceUploadBusy.value || modelingJobBusy.value || modelingJobCanceling.value,
);
const canStartModelingJob = computed(
  () =>
    localImportedFiles.value.some((file) => file.uploadStatus === "uploaded" && Boolean(file.backendPath)) &&
    !["completed", "segmentation_required"].includes(modelingJobStatus.value) &&
    !modelingOperationBusy.value,
);
const canCancelModelingJob = computed(() =>
  Boolean(modelingJobId.value) && ["queued", "running"].includes(modelingJobStatus.value),
);
const modelingJobStatusLabel = computed(() => {
  if (modelingJobStatus.value === "queued") return `建模任务已排队：${modelingJobId.value}`;
  if (modelingJobStatus.value === "running") return modelingJobMessage.value || "正在生成表面模型...";
  if (modelingJobStatus.value === "completed") return modelingJobMessage.value || "表面模型已生成并接入三维证据。";
  if (modelingJobStatus.value === "canceled") return modelingJobMessage.value || "三维建模任务已取消。";
  if (modelingJobStatus.value === "segmentation_required") return modelingJobMessage.value || "体数据已检查，仍需分割标签后才能生成表面。";
  if (modelingJobStatus.value === "failed") return modelingJobMessage.value || "表面模型生成失败。";
  return "可先导入 CBCT 或 Slicer 导出的 STL/GLB；体数据生成表面需要后端建模任务。";
});
const sceneCurveLabel = computed(
  () => humanizeEvidenceText(stringFromEvidence(sceneManifest.value?.mandibular_curve?.label)) || "下颌曲线用于解释候选投影与规划切面关系",
);
const sceneManifestSourceLabel = computed(
  () => humanizeEvidenceText(stringFromEvidence(sceneManifest.value?.source_project)) || "前端示意场景",
);
const geometryManifestLabel = computed(() => {
  if (!geometryManifestPath.value) return "几何计算未生成";
  if (geometryLoadState.value === "loaded") return `${geometryManifestPath.value} · 已读取`;
  if (geometryLoadState.value === "failed") return `${geometryManifestPath.value} · 读取失败`;
  if (geometryLoadState.value === "loading") return `${geometryManifestPath.value} · 读取中`;
  return geometryManifestPath.value;
});
const geometrySchemaLabel = computed(() => stringFromEvidence(geometryManifest.value?.schema_version) || "几何清单未读取");
const geometryStatusLabel = computed(() => {
  const status = geometryManifest.value?.geometry_status;
  if (!isEvidenceRecord(status)) return "几何状态未记录";
  const planeReady = Boolean(status.plane_intersection_ready);
  const candidateReady = Boolean(status.candidate_projection_ready);
  const navigationReady = Boolean(status.navigation_ready);
  return [
    planeReady ? "平面交线已计算" : "平面交线缺失",
    candidateReady ? "候选表面点已计算" : "候选表面点缺失",
    navigationReady ? "导航就绪" : "非导航",
  ].join(" / ");
});
const planeIntersectionSummaryLabel = computed(() => {
  const intersections = geometryManifest.value?.plane_intersections;
  if (!Array.isArray(intersections) || !intersections.length) return "未计算";
  const readyCount = intersections.filter((item) => stringFromEvidence(item.status).toLowerCase() === "ready").length;
  const segmentCounts = intersections.map((item) => numberFromEvidenceValue(item.segment_count) ?? 0).join(", ");
  return `${readyCount} / ${intersections.length} 已就绪 · 交线段：${segmentCounts}`;
});
const surfaceQualityLabel = computed(() => {
  const quality = evidence.value?.surface_quality;
  if (!isEvidenceRecord(quality)) return "未记录";
  const method = humanizeEvidenceText(stringFromEvidence(quality.method)) || "代理表面";
  const threshold = numberFromEvidenceValue(quality.threshold_value);
  const fillRatio = numberFromEvidenceValue(quality.fill_ratio_after_components);
  const components = numberFromEvidenceValue(quality.kept_component_count);
  const parts = [method];
  if (threshold != null) parts.push(`阈值 ${threshold.toFixed(1)}`);
  if (fillRatio != null) parts.push(`保留 ${(fillRatio * 100).toFixed(2)}%`);
  if (components != null) parts.push(`${components} 个主要连通域`);
  const upperJawStatus = upperJawCoverageStatus(quality);
  if (upperJawStatus === "partial_or_crop_limited") parts.push("上颌标签偏少或被裁切");
  if (upperJawStatus === "crop_boundary_touching") parts.push("上颌触及裁切边界");
  if (upperJawStatus === "missing") parts.push("上颌标签缺失");
  return parts.join(" / ");
});

function upperJawCoverageStatus(quality: Record<string, unknown>): string {
  const perLabel = quality.per_label;
  if (!Array.isArray(perLabel)) return "";
  const upper = perLabel.find((item) => {
    if (!isEvidenceRecord(item)) return false;
    const name = stringFromEvidence(item.label_name).toLowerCase();
    return name.includes("upper") || name.includes("maxilla") || name.includes("上颌");
  });
  return isEvidenceRecord(upper) ? stringFromEvidence(upper.coverage_status) : "";
}

const normalizedHotspots = computed<HotspotSpec[]>(() => {
  if (!props.candidates.length) return [];
  return props.candidates.slice(0, 6).map((candidate, index) => {
    const t = props.candidates.length === 1 ? 0.5 : index / Math.max(1, Math.min(props.candidates.length, 6) - 1);
    const archPoint = pointOnMandibleArch(t);
    const confidence = normalizedConfidence(candidate);
    const risk = riskFromCandidate(candidate);
    const frameKey = stringFromMetadata(candidate.metadata, "frame_key");
    const frameIndex = numberFromMetadata(candidate.metadata, "frame_index");
    const timestampSec = numberFromMetadata(candidate.metadata, "timestamp_sec");
    return {
      key: candidate.candidate_id,
      label: humanizeEvidenceText(candidate.risk_type || "") || `候选区域 ${index + 1}`,
      shortLabel: String.fromCharCode(65 + index),
      risk,
      confidence,
      frameKey,
      frameIndex,
      timestampSec,
      position: archPoint.position,
      normal: archPoint.normal,
      scale: 0.2 + confidence * 0.2,
    };
  });
});

const selectedHotspot = computed(() =>
  normalizedHotspots.value.find((hotspot) => hotspot.key === selectedHotspotKey.value) ?? null,
);
const selectedHotspotFeedback = computed(() => {
  const hotspot = selectedHotspot.value;
  if (!hotspot) return "";
  const timing = hotspot.timestampSec == null ? "时间点未记录" : `${hotspot.timestampSec.toFixed(2)} s`;
  return `${hotspot.shortLabel} · ${hotspot.label} · ${timing} · 置信度 ${Math.round(hotspot.confidence * 100)}%`;
});

const riskSummary = computed(() => {
  const hotspots = normalizedHotspots.value;
  if (!hotspots.length) {
    return {
      risk: "low" as RiskLevel,
      label: "三维参考",
    };
  }
  const risk: RiskLevel = hotspots.some((item) => item.risk === "high")
    ? "high"
    : hotspots.some((item) => item.risk === "medium")
      ? "medium"
      : "low";
  return {
    risk,
    label: riskLabels[risk],
  };
});

const statusClass = computed(() => {
  if (!isRegistered.value) return "is-reference";
  return `is-${riskSummary.value.risk}`;
});

const confidenceLabel = computed(() => {
  const hotspots = normalizedHotspots.value;
  if (!hotspots.length) return "暂无";
  const mean = hotspots.reduce((total, item) => total + item.confidence, 0) / Math.max(1, hotspots.length);
  return `${Math.round(mean * 100)}%`;
});

const migratedWorkflowSteps = computed<MigratedWorkflowStep[]>(() => {
  const hasGeometry = geometryLoadState.value === "loaded" || Boolean(sceneManifest.value);
  const hasCandidates = normalizedHotspots.value.length > 0;
  return [
    {
      key: "model",
      index: "01",
      title: "模型/分割",
      detail: hasEvidenceModel.value ? modelFileNameLabel.value : "等待 STL/GLB 或 CBCT 派生模型",
      state: modelLoadState.value === "loaded" ? "ready" : hasEvidenceModel.value ? "partial" : "blocked",
      stateLabel: modelLoadState.value === "loaded" ? "已接入" : hasEvidenceModel.value ? "待加载" : "缺失",
    },
    {
      key: "source",
      index: "02",
      title: "来源记录",
      detail: segmentationSourceLabel.value,
      state: hasEvidenceModel.value || localImportedFiles.value.length ? "ready" : "blocked",
      stateLabel: hasEvidenceModel.value || localImportedFiles.value.length ? "已记录" : "缺失",
    },
    {
      key: "geometry",
      index: "03",
      title: "建模检查",
      detail: hasGeometry ? geometryStatusLabel.value : modelingJobStatusLabel.value,
      state: hasGeometry ? "partial" : "blocked",
      stateLabel: hasGeometry ? "有清单" : "待生成",
    },
    {
      key: "mapping",
      index: "04",
      title: "荧光对应",
      detail: hotspotProjectionLabel.value,
      state: isRegistered.value && hasCandidates ? "ready" : hasCandidates ? "partial" : "blocked",
      stateLabel: isRegistered.value && hasCandidates ? "已映射" : hasCandidates ? "示意" : "无候选",
    },
  ];
});

const objectTreeItems = computed<ObjectTreeItem[]>(() => [
  {
    key: "cbct" as ObjectVisibilityKey,
    name: "CBCT 体数据",
    detail: coordinateSpaceLabel.value,
    state: objectVisibility.value.cbct ? (hasEvidenceModel.value ? "来源记录" : "待接入") : "隐藏",
    muted: !hasEvidenceModel.value || !objectVisibility.value.cbct,
    locked: true,
    interactive: false,
  },
  {
    key: "mandible" as ObjectVisibilityKey,
    name: "下颌表面模型",
    detail: modelSourceLabel.value,
    state: objectVisibility.value.mandible ? displayModeLabel.value : "隐藏",
    muted: modelLoadState.value !== "loaded" || !objectVisibility.value.mandible,
    locked: !hasEvidenceModel.value,
    interactive: modelLoadState.value === "loaded",
  },
  {
    key: "curvePlanes" as ObjectVisibilityKey,
    name: "下颌曲线",
    detail: sceneCurveLabel.value,
    state: objectVisibility.value.curvePlanes ? "示意" : "隐藏",
    muted: !objectVisibility.value.curvePlanes,
    locked: false,
    interactive: modelLoadState.value === "loaded",
  },
  {
    key: "curvePlanes" as ObjectVisibilityKey,
    name: "观察 / 复核平面",
    detail: "仅记录观察平面，不输出手术方案",
    state: objectVisibility.value.curvePlanes ? (isRegistered.value ? "待医生复核" : "非导航") : "隐藏",
    muted: !isRegistered.value || !objectVisibility.value.curvePlanes,
    locked: true,
    interactive: modelLoadState.value === "loaded" && isRegistered.value,
  },
  {
    key: "candidates" as ObjectVisibilityKey,
    name: "ICG 候选叠加",
    detail: normalizedHotspots.value.length ? `${normalizedHotspots.value.length} 个候选区` : "暂无候选区",
    state: objectVisibility.value.candidates ? hotspotProjectionLabel.value : "隐藏",
    muted: !normalizedHotspots.value.length || !objectVisibility.value.candidates,
    locked: !isRegistered.value,
    interactive: normalizedHotspots.value.length > 0,
  },
  {
    key: "registration" as ObjectVisibilityKey,
    name: "配准变换",
    detail: registrationErrorLabel.value,
    state: objectVisibility.value.registration ? registrationLabel.value : "隐藏",
    muted: !isRegistered.value || !objectVisibility.value.registration,
    locked: true,
    interactive: isRegistered.value && registrationMarkupRows.value.some((markup) => markup.ready),
  },
]);

const objectTreeGroups = computed<ObjectTreeGroup[]>(() => {
  const v2Groups = objectTreeGroupsFromSceneV2();
  if (v2Groups.length) return v2Groups;
  const items = objectTreeItems.value;
  const byName = (name: string) => items.find((item) => item.name === name);
  return [
    {
      name: "病例 / 体数据",
      detail: "对象树根节点",
      items: [byName("CBCT 体数据")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "分割 / 模型",
      detail: "下颌表面模型与来源分割",
      items: [byName("下颌表面模型")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "标注 / 平面",
      detail: "曲线、配准点与复核平面",
      items: [byName("下颌曲线"), byName("观察 / 复核平面"), byName("配准变换")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "ICG / 视频对应",
      detail: "证据并列，未配准时仅作参考",
      items: [byName("ICG 候选叠加")].filter(Boolean) as ObjectTreeItem[],
    },
  ];
});

const showViewportLabels = computed(
  () =>
    modelLoadState.value === "loaded" &&
    (isRegistered.value || normalizedHotspots.value.length > 0 || registrationMarkupRows.value.some((markup) => markup.ready)),
);

const viewportLabelItems = computed<ViewportLabelItem[]>(() => {
  const labels: ViewportLabelItem[] = [];
  if (objectVisibility.value.curvePlanes) {
    labels.push(
      {
        key: "plane-left",
        kind: "plane",
        shortLabel: "P0",
        label: "左侧复核平面",
        detail: isRegistered.value ? "已配准复核平面" : "未配准示意平面",
        x: 30,
        y: 42,
        selected: activeWorkspaceTool.value === "planes",
        muted: !isRegistered.value,
        targetKey: "cutPlane",
      },
      {
        key: "plane-right",
        kind: "plane",
        shortLabel: "P1",
        label: "右侧复核平面",
        detail: isRegistered.value ? "已配准复核平面" : "未配准示意平面",
        x: 67,
        y: 44,
        selected: activeWorkspaceTool.value === "planes",
        muted: !isRegistered.value,
        targetKey: "cutPlane",
      },
    );
  }
  if (objectVisibility.value.registration) {
    registrationMarkupRows.value.slice(0, 4).forEach((markup, index) => {
      labels.push({
        key: `markup-${markup.id}`,
        kind: "markup",
        shortLabel: markup.shortLabel,
        label: markup.label,
        detail: markup.residualLabel,
        x: 20 + index * 18,
        y: index % 2 === 0 ? 27 : 57,
        selected: selectedMarkupId.value === markup.id,
        muted: !markup.ready,
        targetKey: markup.id,
      });
    });
  }
  if (objectVisibility.value.candidates) {
    normalizedHotspots.value.slice(0, 4).forEach((hotspot, index) => {
      labels.push({
        key: `hotspot-${hotspot.key}`,
        kind: "hotspot",
        shortLabel: hotspot.shortLabel,
        label: hotspot.label,
        detail: hotspotProjectionLabel.value,
        x: 34 + index * 10,
        y: 63 - index * 8,
        selected: selectedHotspotKey.value === hotspot.key,
        muted: !isRegistered.value,
        targetKey: hotspot.key,
      });
    });
  }
  return labels;
});

const sliceViews = computed(() => [
  {
    key: "axial" as SliceKey,
    label: "红色轴位",
    position: slicePositionLabel("Z", sliceOffsets.value.axial, sliceBaseMm("axial", 12.4)),
    note: sliceNote("axial", "骨窗轮廓、候选投影和十字定位线保持可追溯显示。"),
  },
  {
    key: "coronal" as SliceKey,
    label: "绿色冠状位",
    position: slicePositionLabel("Y", sliceOffsets.value.coronal, sliceBaseMm("coronal", -18.2)),
    note: sliceNote("coronal", "用于观察下颌体高度、骨皮质连续性和候选区上下边界。"),
  },
  {
    key: "sagittal" as SliceKey,
    label: "黄色矢状位",
    position: slicePositionLabel("X", sliceOffsets.value.sagittal, sliceBaseMm("sagittal", 6.8)),
    note: sliceNote("sagittal", "用于解释候选区沿牙槽嵴和下颌支方向的空间位置。"),
  },
]);

const evidenceFields = computed(() => [
  { label: "证据结构", value: stringFromEvidence(evidence.value?.schema_version) || "three_d_evidence 未接入" },
  { label: "场景清单", value: stringFromEvidence(sceneManifest.value?.schema_version) || "three_d_scene_manifest 未接入" },
  { label: "场景图 V2", value: stringFromEvidence(sceneManifestV2.value?.schema_version) || "场景图 V2 未接入" },
  { label: "场景对象", value: sceneManifestV2.value?.nodes?.length ? `${sceneManifestV2.value.nodes.length} 个节点` : "未记录节点" },
  { label: "标注对象", value: sceneManifestV2.value?.markups?.length ? `${sceneManifestV2.value.markups.length} 个标注` : "未记录标注" },
  { label: "几何任务", value: sceneManifestV2.value?.geometry_jobs?.length ? `${sceneManifestV2.value.geometry_jobs.length} 个任务` : "未记录任务" },
  { label: "几何清单", value: geometryManifestLabel.value },
  { label: "几何结构", value: geometrySchemaLabel.value },
  { label: "几何状态", value: geometryStatusLabel.value },
  { label: "平面交线", value: planeIntersectionSummaryLabel.value },
  { label: "表面质量", value: surfaceQualityLabel.value },
  { label: "分析模式", value: evidenceAnalysisModeLabel.value },
  { label: "模型来源", value: modelSourceLabel.value },
  { label: "模型路径", value: evidenceModelPath.value || "未记录真实 STL/GLB/GLTF" },
  { label: "模型文件名", value: modelFileNameLabel.value },
  { label: "模型格式", value: modelFormatLabel.value },
  { label: "导出工具", value: exportedFromLabel.value },
  { label: "DICOM 序列", value: dicomSeriesLabel.value },
  { label: "分割来源", value: segmentationSourceLabel.value },
  { label: "分割复核", value: segmentationReviewStatusLabel.value },
  { label: "空间坐标", value: coordinateSpaceLabel.value },
  { label: "方向复核", value: `${orientationReviewLabel.value} / ${displayUpAxisLabel.value}` },
  { label: "配准状态", value: registrationLabel.value },
  { label: "配准方法", value: registrationMethodLabel.value },
  { label: "误差记录", value: registrationErrorLabel.value },
  { label: "标志点数", value: fiducialCount.value == null ? "未记录" : `${fiducialCount.value}` },
  { label: "表面点数", value: surfacePointCount.value == null ? "未记录" : `${surfacePointCount.value}` },
  { label: "变换文件", value: transformPathLabel.value },
  { label: "候选映射", value: hotspotProjectionLabel.value },
  { label: "复核状态", value: doctorReviewStatusLabel.value },
  { label: "数据边界", value: evidenceDataBoundaryLabel.value },
  { label: "医生边界", value: boundaryNote.value },
]);

const summaryEvidenceFields = computed(() => [
  { label: "模型", value: modelFileNameLabel.value },
  { label: "来源", value: modelSourceLabel.value },
  { label: "坐标", value: coordinateSpaceLabel.value },
  { label: "质量", value: surfaceQualityLabel.value },
  { label: "配准", value: registrationLabel.value },
  { label: "误差", value: registrationErrorLabel.value },
  { label: "候选映射", value: hotspotProjectionLabel.value },
]);

const registrationGuardItems = computed(() => [
  { label: "点配准标志点已记录", ready: isRegistered.value && (fiducialCount.value ?? 0) >= 3 },
  {
    label: "表面匹配点云与 ICP 误差已记录",
    ready: isRegistered.value && (surfacePointCount.value ?? 0) > 0 && registrationErrorLabel.value !== "未记录",
  },
  {
    label: "CBCT 坐标系、模型来源、DICOM 序列和导出文件名已进入证据包",
    ready:
      hasEvidenceModel.value &&
      coordinateSpaceLabel.value !== "坐标系未记录" &&
      dicomSeriesLabel.value !== "DICOM 序列未记录" &&
      modelFileNameLabel.value !== "文件名未记录",
  },
  {
    label: "医生复核边界已确认，ICG 候选区可进入空间参考层",
    ready:
      isRegistered.value &&
      ["accepted", "approved", "reviewed", "复核通过", "已接受", "已批准", "已复核"].includes(
        doctorReviewStatusLabel.value.toLowerCase(),
      ),
  },
  {
    label: "后端明确标记导航就绪；否则继续保持非导航展示",
    ready: navigationReady.value && isRegistered.value,
  },
]);

const navigationGuardSummary = computed(() => {
  const readyCount = registrationGuardItems.value.filter((item) => item.ready).length;
  return `${readyCount} / ${registrationGuardItems.value.length} 项满足；未全部满足时保持非导航展示。`;
});

const registrationMarkupRows = computed<RegistrationMarkupRow[]>(() => {
  const explicitRows = explicitRegistrationMarkups();
  if (explicitRows.length) return explicitRows;
  return [];
});

const registrationMarkupsSummary = computed(() => {
  const readyCount = registrationMarkupRows.value.filter((item) => item.ready).length;
  return `${readyCount} / ${registrationMarkupRows.value.length} 个配准点已就绪`;
});

const transformChainItems = computed<TransformChainItem[]>(() => {
  const explicitSteps = explicitTransformChain();
  if (explicitSteps.length) return explicitSteps;
  return [
    {
      name: "DICOM 体素到 CBCT 坐标",
      fromSpace: "DICOM 体素",
      toSpace: coordinateSpaceLabel.value,
      detail: dicomSeriesLabel.value,
      ready: coordinateSpaceLabel.value !== "坐标系未记录" && dicomSeriesLabel.value !== "DICOM 序列未记录",
    },
    {
      name: "分割结果到表面模型",
      fromSpace: segmentationSourceLabel.value,
      toSpace: modelFileNameLabel.value,
      detail: segmentationReviewStatusLabel.value,
      ready: hasEvidenceModel.value && segmentationReviewStatusLabel.value !== "分割复核状态未记录",
    },
    {
      name: "CBCT/STL 到视频参考",
      fromSpace: coordinateSpaceLabel.value,
      toSpace: "MP4/JPEG 关键帧证据",
      detail: transformPathLabel.value,
      ready: isRegistered.value && transformPathLabel.value !== "坐标变换文件未记录",
    },
    {
      name: "ICG 候选区到三维参考层",
      fromSpace: "二维关键帧候选区",
      toSpace: isRegistered.value ? "已配准参考层" : "示意投影",
      detail: hotspotProjectionLabel.value,
      ready: isRegistered.value && navigationReady.value,
    },
  ];
});

const transformChainSummary = computed(() => {
  const readyCount = transformChainItems.value.filter((item) => item.ready).length;
  return `${readyCount} / ${transformChainItems.value.length} 项变换就绪`;
});

const workflowSteps = computed(() => [
  {
    index: "01",
    title: "CT / CBCT 导入",
    detail: "体数据、层厚、脱敏状态和坐标系需要进入病例证据包。",
  },
  {
    index: "02",
    title: "Slicer 分割与 STL",
    detail: "表面模型建议记录阈值、手工修正和医生复核状态。",
  },
  {
    index: "03",
    title: "曲线 / 切面规划",
    detail: "记录下颌曲线、复核平面与几何检查清单。",
  },
  {
    index: "04",
    title: "ICG 候选复核",
    detail: "本项目仅把视频分割候选映射为参考层，默认不做导航承诺。",
  },
]);

function openCbctPicker() {
  if (modelingOperationBusy.value) return;
  cbctInput.value?.click();
}

function openSurfacePicker() {
  if (modelingOperationBusy.value) return;
  surfaceInput.value?.click();
}

async function handleCbctFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  if (modelingOperationBusy.value) {
    input.value = "";
    return;
  }
  const files = Array.from(input.files ?? []);
  if (!files.length) return;
  modelingJobId.value = "";
  modelingJobStatus.value = "running";
  modelingJobMessage.value = "正在写入 CBCT 体数据，写入完成后会自动检查能否生成表面。";
  const records = files.map((file) => ({
    name: file.name,
    size: file.size,
    type: file.type || "medical-volume",
    kind: "cbct" as const,
    uploadStatus: "uploading" as const,
  }));
  localImportedFiles.value = [
    ...localImportedFiles.value.filter((file) => file.kind !== "cbct"),
    ...records,
  ];
  localThreeDEvidence.value = buildLocalEvidence({
    modelPath: localSurfaceObjectUrl.value,
    modelFile: localSurfaceFiles.value[0],
    cbctFiles: localCbctFiles.value,
  });
  activeWorkspaceTool.value = "layout";
  input.value = "";
  const uploaded = await uploadLocalThreeDFiles(files, "cbct");
  if (uploaded) {
    modelingJobStatus.value = "idle";
    await startCbctModelingJob("cbct");
  } else {
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = "CBCT 体数据未能写入后端，请检查文件格式、后端服务和上传接口。";
  }
}

async function handleSurfaceModelFile(event: Event) {
  const input = event.target as HTMLInputElement;
  if (modelingOperationBusy.value) {
    input.value = "";
    return;
  }
  const file = input.files?.[0];
  if (!file) return;
  revokeLocalSurfaceObjectUrl();
  localSurfaceObjectUrl.value = URL.createObjectURL(file);
  const surfaceFile: LocalImportedFile = {
    name: file.name,
    size: file.size,
    type: file.type || "surface-model",
    kind: "surface",
    uploadStatus: "uploading",
  };
  localImportedFiles.value = [
    ...localImportedFiles.value.filter((item) => item.kind !== "surface"),
    surfaceFile,
  ];
  localThreeDEvidence.value = buildLocalEvidence({
    modelPath: localSurfaceObjectUrl.value,
    modelFile: surfaceFile,
    cbctFiles: localCbctFiles.value,
  });
  objectVisibility.value.mandible = true;
  activeWorkspaceTool.value = "layout";
  if (boneGroup) void loadRealAnatomyModel();
  input.value = "";
  const uploaded = await uploadLocalThreeDFiles([file], "surface");
  if (uploaded) {
    modelingJobStatus.value = "idle";
    await startCbctModelingJob("surface");
  } else {
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = "表面模型未能写入后端，请检查文件格式、后端服务和上传接口。";
  }
}

function clearLocalEvidence() {
  if (modelingOperationBusy.value) return;
  ++modelingPollGeneration;
  revokeLocalSurfaceObjectUrl();
  localImportedFiles.value = [];
  localThreeDEvidence.value = null;
  modelingJobId.value = "";
  modelingJobStatus.value = "idle";
  modelingJobMessage.value = "";
  modelingPollingPaused.value = false;
  if (cbctInput.value) cbctInput.value.value = "";
  if (surfaceInput.value) surfaceInput.value.value = "";
  if (boneGroup) void loadRealAnatomyModel();
}

async function startCbctModelingJob(preferredKind: "cbct" | "surface" = "surface") {
  if (modelingOperationBusy.value) return;
  modelingPollingPaused.value = false;
  const pollGeneration = ++modelingPollGeneration;
  const cbctSource = localCbctFiles.value.find((file) => file.backendPath);
  const surfaceSource = localSurfaceFiles.value.find((file) => file.backendPath);
  const source = preferredKind === "cbct"
    ? cbctSource ?? surfaceSource
    : surfaceSource ?? cbctSource;
  if (!source?.backendPath) {
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = "请先完成 CBCT 或 STL/GLB 后端写入。";
    return;
  }
  modelingJobStatus.value = "queued";
  modelingJobMessage.value = "正在提交三维建模任务。";
  try {
    const selectedKind = source.kind;
    const modelingParameters: Record<string, unknown> = {
      source_path: source.backendPath,
      source_paths: selectedKind === "cbct"
        ? localCbctFiles.value.map((file) => file.backendPath).filter(Boolean)
        : [source.backendPath],
      source_role: selectedKind === "cbct" ? "volume" : "surface",
      source_original_filename: source.name,
      case_id: props.caseId || "frontend_local_cbct",
      dataset_id: "frontend_local_import",
      decimation_step: 1,
    };
    if (selectedKind !== "cbct") modelingParameters.label_value = 1;
    const started = await apiClient.startThreeDModelingJob(modelingParameters);
    if (pollGeneration !== modelingPollGeneration) return;
    modelingJobId.value = started.job_id;
    await pollCbctModelingJob(started.job_id, pollGeneration);
  } catch (error) {
    if (pollGeneration !== modelingPollGeneration) return;
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = errorMessageFromUnknown(error, "三维建模任务提交失败。");
  }
}

async function cancelCbctModelingJob() {
  if (!modelingJobId.value || modelingJobCanceling.value) return;
  const jobId = modelingJobId.value;
  ++modelingPollGeneration;
  modelingJobCanceling.value = true;
  modelingPollingPaused.value = false;
  modelingJobMessage.value = "正在取消三维建模任务。";
  try {
    const canceled = await apiClient.cancelThreeDModelingJob(jobId);
    if (["queued", "running"].includes(canceled.status)) {
      modelingJobStatus.value = "failed";
      modelingPollingPaused.value = true;
      modelingJobMessage.value = "取消请求尚未确认终态，可刷新任务状态继续核对。";
    } else {
      modelingJobStatus.value = canceled.status === "canceled" ? "canceled" : canceled.status;
      modelingJobMessage.value = canceled.error || canceled.progress?.message || "三维建模任务已取消。";
    }
  } catch (error) {
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = errorMessageFromUnknown(error, "三维建模任务取消失败。");
  } finally {
    modelingJobCanceling.value = false;
  }
}

async function refreshCbctModelingJob() {
  if (!modelingJobId.value || modelingOperationBusy.value) return;
  const pollGeneration = ++modelingPollGeneration;
  modelingPollingPaused.value = false;
  modelingJobStatus.value = "running";
  modelingJobMessage.value = "正在刷新三维建模任务状态。";
  try {
    await pollCbctModelingJob(modelingJobId.value, pollGeneration, 1);
  } catch (error) {
    if (pollGeneration !== modelingPollGeneration) return;
    modelingJobStatus.value = "failed";
    modelingJobMessage.value = errorMessageFromUnknown(error, "三维建模任务状态刷新失败。");
  }
}

async function pollCbctModelingJob(jobId: string, pollGeneration: number, maxAttempts = 60) {
  let lastJob = await apiClient.getThreeDModelingJob(jobId);
  if (pollGeneration !== modelingPollGeneration) return;
  for (let attempt = 0; attempt < maxAttempts && ["queued", "running"].includes(lastJob.status); attempt += 1) {
    if (pollGeneration !== modelingPollGeneration) return;
    modelingJobStatus.value = lastJob.status;
    modelingJobMessage.value = lastJob.progress?.message || "正在生成表面模型...";
    await sleep(1000);
    if (pollGeneration !== modelingPollGeneration) return;
    lastJob = await apiClient.getThreeDModelingJob(jobId);
    if (pollGeneration !== modelingPollGeneration) return;
  }
  if (pollGeneration !== modelingPollGeneration) return;
  if (["queued", "running"].includes(lastJob.status)) {
    modelingJobStatus.value = "failed";
    modelingPollingPaused.value = true;
    modelingJobMessage.value = "后端任务仍在运行，前端轮询已暂停；可刷新任务状态继续核对。";
    return;
  }
  modelingPollingPaused.value = false;
  modelingJobStatus.value =
    lastJob.status === "completed" && lastJob.result?.modeling_status === "segmentation_required"
      ? "segmentation_required"
      : lastJob.status === "completed"
        ? "completed"
        : lastJob.status === "canceled"
          ? "canceled"
          : "failed";
  const result = isEvidenceRecord(lastJob.result) ? lastJob.result : {};
  modelingJobMessage.value = stringFromEvidence(result.message) || lastJob.progress?.message || lastJob.error || "";
  if (modelingJobStatus.value === "completed" && !stringFromEvidence(result.message)) {
    modelingJobMessage.value = "表面模型已生成并接入三维证据。";
  }
  const evidencePayload = result.three_d_evidence;
  if (isEvidenceRecord(evidencePayload)) {
    localThreeDEvidence.value = evidencePayload as ThreeDEvidence;
    if (boneGroup) void loadRealAnatomyModel();
  }
  const casePersistence = isEvidenceRecord(result.case_persistence) ? result.case_persistence : {};
  if (casePersistence.status === "persisted") {
    emit("threeDEvidencePersisted");
  }
}

function buildLocalEvidence({
  modelPath,
  modelFile,
  cbctFiles,
}: {
  modelPath: string;
  modelFile?: LocalImportedFile;
  cbctFiles: LocalImportedFile[];
}): ThreeDEvidence {
  const firstCbct = cbctFiles[0];
  const sourceNames = cbctFiles.map((file) => file.name).join(", ");
  const modelFormat = modelFile ? modelFormatFromFileName(modelFile.name) : "";
  return {
    schema_version: "osteo-vision-three-d-evidence-local-v1",
    analysis_mode: "cbct_import_modeling_review",
    model_path: modelPath || null,
    model_format: modelFormat || null,
    model_file_name: modelFile?.name ?? null,
    model_source: modelFile ? "本地导入表面模型" : "本地导入 CBCT 体数据",
    exported_from: modelFile ? "浏览器本地 STL/GLB 预览" : "等待 Slicer/后端分割导出表面",
    dicom_series_uid: firstCbct ? `本地文件：${firstCbct.name}` : null,
    segmentation_source: modelFile ? "用户导入的下颌表面模型" : "待分割：需要 Slicer Segment Editor 或后端分割脚本",
    segmentation_review_status: "not_reviewed",
    registration_status: "unregistered",
    registration_method: "not_recorded",
    registration_error_mm: null,
    coordinate_space: "local_cbct_or_surface_file_space",
    doctor_review_status: "not_reviewed",
    navigation_ready: false,
    input_domain: "local_cbct_surface_import",
    source_inputs: [
      ...cbctFiles.map((file) => ({
        channel: "cbct",
        path: file.backendPath || file.name,
        mime_type: file.type,
        size_bytes: file.size,
        upload_status: file.uploadStatus || "local",
      })),
      ...(modelFile
        ? [{
            channel: "surface_model",
            path: modelFile.backendPath || modelFile.name,
            mime_type: modelFile.type,
            size_bytes: modelFile.size,
            upload_status: modelFile.uploadStatus || "local",
          }]
        : []),
    ],
    scene_manifest: {
      schema_version: "osteo-vision-three-d-scene-local-v1",
      source_project: "3D Slicer local import workflow",
      scene_id: "local_cbct_review_scene",
      coordinate_space: "local_cbct_or_surface_file_space",
      mandibular_curve: {
        id: "local_mandibular_curve_pending_review",
        label: "本地下颌参考曲线",
        source: "front-end generated review scaffold; not physician markups",
        display_points: [
          [-1.9, 0.02, -0.08],
          [-1.2, -0.18, 0.22],
          [0, -0.34, 0.42],
          [1.2, -0.18, 0.22],
          [1.9, 0.02, -0.08],
        ],
      },
      review_planes: [
        {
          id: "local_review_plane_left",
          label: "本地左侧复核平面",
          display_position: [-0.92, 0.18, 0.12],
          display_rotation: [0, 1.44, -0.16],
          display_scale: [1, 1.85, 1],
          status: "illustrative_unregistered",
        },
        {
          id: "local_review_plane_right",
          label: "本地右侧复核平面",
          display_position: [0.92, 0.22, 0.12],
          display_rotation: [0, 1.7, 0.16],
          display_scale: [1, 1.85, 1],
          status: "illustrative_unregistered",
        },
      ],
      migration_notes: [
        sourceNames ? `CBCT 文件：${sourceNames}` : "未导入 CBCT 体数据",
        modelFile ? `表面模型：${modelFile.name}` : "未导入 STL/GLB 表面模型",
        "该场景只用于前端建模检查，不代表术中定位。",
      ],
    },
    scene_manifest_v2: {
      schema_version: "osteo-vision-three-d-scene-v2",
      source_project: "3D Slicer MRML local evidence scene",
      case_id: "frontend_local_cbct",
      dataset_id: "frontend_local_import",
      scene_id: "frontend_local_cbct_review_scene",
      scene: {
        coordinate_space: "local_cbct_or_surface_file_space",
        registration_status: "unregistered",
        registration_error_mm: null,
        navigation_ready: false,
        doctor_review_status: "not_reviewed",
      },
      subject_hierarchy: [
        { id: "case_root", name: "病例 / 体数据", children: cbctFiles.map((file, index) => `local_cbct_${index + 1}`) },
        { id: "segmentation_models", name: "分割 / 模型", children: modelFile ? ["local_surface_model"] : [] },
        { id: "markups_review", name: "标注 / 平面", children: ["local_mandibular_curve", "local_review_plane_left", "local_review_plane_right"] },
        { id: "geometry_jobs", name: "几何任务", children: ["local_import_check"] },
      ],
      nodes: [
        ...cbctFiles.map((file, index) => ({
          id: `local_cbct_${index + 1}`,
          type: "volume",
          role: "source_cbct_volume",
          name: file.name,
          path: file.backendPath || file.name,
          source: "browser imported CBCT asset",
          review_status: file.uploadStatus === "uploaded" ? "recorded" : "local_only",
        })),
        ...(modelFile
          ? [
              {
                id: "local_surface_model",
                type: "model",
                role: "uploaded_surface_reference",
                name: modelFile.name,
                path: modelFile.backendPath || modelFile.name,
                format: modelFormat,
                source: "browser imported STL/GLB surface",
                review_status: "not_reviewed",
              },
            ]
          : []),
      ],
      markups: [
        { id: "local_mandibular_curve", type: "curve", role: "mandibular_reference_curve", name: "本地下颌参考曲线", review_status: "illustrative_unregistered" },
        { id: "local_review_plane_left", type: "plane", role: "review_plane", name: "本地左侧复核平面", review_status: "illustrative_unregistered" },
        { id: "local_review_plane_right", type: "plane", role: "review_plane", name: "本地右侧复核平面", review_status: "illustrative_unregistered" },
      ],
      transforms: [
        {
          id: "surface_to_video",
          type: "cross_modal_registration",
          from_node: modelFile ? "local_surface_model" : "local_cbct_1",
          to_node: "video_keyframe_reference",
          status: "missing",
        },
      ],
      geometry_jobs: [{ id: "local_import_check", type: "local_import_check", status: "completed" }],
      review_state: {
        segmentation: modelFile ? "surface_supplied_directly" : "segmentation_required",
        model: modelFile ? "not_reviewed" : "not_available",
        markups: "illustrative_not_physician_reviewed",
        fluorescence_video_mapping: "missing_registration",
      },
      data_boundary: "Local CBCT/surface import for platform validation; unregistered and not navigation-ready.",
    },
    boundary_note:
      "本地导入的 CBCT/STL/GLB 只进入三维证据检查工作流；未完成配准误差记录和医生复核前，不显示真实术中定位结论或手术方案。",
    data_boundary:
      "Local CBCT/surface import for platform validation; unregistered and not navigation-ready.",
  };
}

async function uploadLocalThreeDFiles(files: File[], kind: "cbct" | "surface"): Promise<boolean> {
  const uploads = await Promise.allSettled(files.map((file) => apiClient.uploadThreeDAsset(file)));
  let surfacePathChanged = false;
  let uploadedCount = 0;
  uploads.forEach((result, index) => {
    const source = files[index];
    const targetIndex = localImportedFiles.value.findIndex(
      (item) => item.kind === kind && item.name === source.name && item.size === source.size,
    );
    if (targetIndex < 0) return;
    const current = localImportedFiles.value[targetIndex];
    const updated: LocalImportedFile =
      result.status === "fulfilled"
        ? {
            ...current,
            backendPath: result.value.path,
            type: result.value.content_type || current.type,
            uploadError: undefined,
            uploadStatus: "uploaded",
          }
        : {
            ...current,
            uploadError: errorMessageFromUnknown(result.reason, "后端写入失败"),
            uploadStatus: "failed",
          };
    if (result.status === "fulfilled") uploadedCount += 1;
    localImportedFiles.value.splice(targetIndex, 1, updated);
    surfacePathChanged = surfacePathChanged || (kind === "surface" && result.status === "fulfilled");
  });
  localThreeDEvidence.value = buildLocalEvidence({
    modelPath: localSurfaceFiles.value[0]?.backendPath || localSurfaceObjectUrl.value,
    modelFile: localSurfaceFiles.value[0],
    cbctFiles: localCbctFiles.value,
  });
  if (surfacePathChanged && boneGroup) void loadRealAnatomyModel();
  return uploadedCount === files.length;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function revokeLocalSurfaceObjectUrl() {
  if (!localSurfaceObjectUrl.value) return;
  URL.revokeObjectURL(localSurfaceObjectUrl.value);
  localSurfaceObjectUrl.value = "";
}

function fileSizeLabel(size: number): string {
  if (!Number.isFinite(size) || size <= 0) return "大小未记录";
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

function uploadStateLabel(file: LocalImportedFile): string {
  if (file.uploadStatus === "uploaded") return "已写入后端证据区";
  if (file.uploadStatus === "uploading") return "正在写入后端证据区";
  if (file.uploadStatus === "failed") return `后端写入失败：${file.uploadError || "保留本地预览"}`;
  return "本地预览";
}

function errorMessageFromUnknown(error: unknown, fallback: string): string {
  const body = (error as { body?: unknown } | null)?.body;
  if (isEvidenceRecord(body)) {
    const detail = body.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (isEvidenceRecord(detail)) {
      return stringFromEvidence(detail.message) || stringFromEvidence(detail.code) || fallback;
    }
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function modelFormatFromFileName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".stl")) return "stl";
  if (lower.endsWith(".glb")) return "glb";
  if (lower.endsWith(".gltf")) return "gltf";
  return "";
}

function activateTreeNode(item: ObjectTreeItem) {
  if (!item.interactive) return;
  activeTreeNodeName.value = item.name;
  toggleObjectVisibility(item.key);
}

function selectViewportLabel(label: ViewportLabelItem) {
  if (label.kind === "markup" && label.targetKey) {
    selectMarkup(label.targetKey);
    return;
  }
  if (label.kind === "hotspot" && label.targetKey) {
    selectHotspot(label.targetKey);
    return;
  }
  if (label.targetKey === "cutPlane") {
    objectVisibility.value.curvePlanes = true;
    activeWorkspaceTool.value = "planes";
    applySceneVisibility();
  }
}

function resetCamera() {
  if (modelLoadState.value !== "loaded" || !camera || !controls) return;
  camera.position.set(0.8, 1.56, 5.75);
  controls.target.set(0.04, 0.38, 0);
  controls.update();
  viewLayoutMode.value = "four";
  nextTick(resize);
}

function toggleAutoRotate() {
  autoRotateModel.value = !autoRotateModel.value;
  if (controls) {
    controls.autoRotate = autoRotateModel.value;
    controls.update();
  }
}

function focusFirstCandidate() {
  const first = normalizedHotspots.value[0];
  if (first) {
    selectHotspot(first.key);
    return;
  }
  activeWorkspaceTool.value = "roi";
}

function selectHotspot(key: string) {
  selectedHotspotKey.value = key;
  selectedMarkupId.value = "";
  activeWorkspaceTool.value = "roi";
  objectVisibility.value.candidates = true;
  const selected = normalizedHotspots.value.find((hotspot) => hotspot.key === key);
  if (selected) {
    emit("selectCandidateFrame", {
      candidateId: selected.key,
      frameKey: selected.frameKey,
      frameIndex: selected.frameIndex,
      timestampSec: selected.timestampSec,
    });
  }
  const index = normalizedHotspots.value.findIndex((hotspot) => hotspot.key === key);
  if (index >= 0) {
    const offset = Math.round((index - (normalizedHotspots.value.length - 1) / 2) * 10);
    updateSliceOffset("axial", offset);
    updateSliceOffset("coronal", Math.round(offset * 0.55));
    updateSliceOffset("sagittal", Math.round(offset * -0.42));
  }
  applySceneVisibility();
}

function selectMarkup(id: string) {
  const row = registrationMarkupRows.value.find((item) => item.id === id);
  if (!row?.ready) return;
  selectedMarkupId.value = id;
  selectedHotspotKey.value = "";
  activeWorkspaceTool.value = "layout";
  objectVisibility.value.registration = true;
  updateSliceOffset("axial", Math.round(row.position.z * 42));
  updateSliceOffset("coronal", Math.round(row.position.y * 34));
  updateSliceOffset("sagittal", Math.round(row.position.x * 24));
  renderRegistrationMarkups();
  applySceneVisibility();
}

function toggleObjectVisibility(key: ObjectVisibilityKey) {
  objectVisibility.value[key] = !objectVisibility.value[key];
  applySceneVisibility();
}

function toggleThreeDMaximize() {
  if (modelLoadState.value !== "loaded") return;
  viewLayoutMode.value = viewLayoutMode.value === "threeD" ? "four" : "threeD";
  void nextTick(() => {
    resize();
    if (viewLayoutMode.value === "threeD") {
      canvasHost.value?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
  });
}

function toggleReconstructionMaximize() {
  viewLayoutMode.value = viewLayoutMode.value === "reconstruction" ? "four" : "reconstruction";
  nextTick(resize);
}

function setSliceOffset(key: SliceKey, event: Event) {
  const input = event.target as HTMLInputElement;
  updateSliceOffset(key, Number(input.value));
}

function adjustSliceOffset(key: SliceKey, delta: number) {
  updateSliceOffset(key, sliceOffsets.value[key] + delta);
}

function updateSliceOffset(key: SliceKey, value: number) {
  sliceOffsets.value[key] = Math.round(THREE.MathUtils.clamp(value, -60, 60));
}

function slicePositionLabel(axis: string, offset: number, base: number): string {
  const value = base + offset;
  const prefix = isRegistered.value ? `CBCT ${axis}` : `示意 ${axis}`;
  return `${prefix} ${value >= 0 ? "+" : ""}${value.toFixed(1)} mm`;
}

function sliceBaseMm(key: SliceKey, fallback: number): number {
  const raw = sceneManifest.value?.slice_views?.[key]?.base_mm;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim()) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function sliceNote(key: SliceKey, fallback: string): string {
  return stringFromEvidence(sceneManifest.value?.slice_views?.[key]?.note) || fallback;
}

function sliceCanvasStyle(key: SliceKey) {
  const offset = sliceOffsets.value[key];
  const normalized = 50 + (offset / 60) * 28;
  const roiShift = (offset / 60) * 18;
  return {
    "--slice-crosshair": `${normalized}%`,
    "--slice-roi-shift": `${roiShift}%`,
  };
}

function applySceneVisibility() {
  if (boneGroup) boneGroup.visible = objectVisibility.value.mandible;
  if (hotspotGroup) hotspotGroup.visible = objectVisibility.value.candidates;
  if (planningGuideGroup) planningGuideGroup.visible = objectVisibility.value.curvePlanes || objectVisibility.value.registration;
  if (anatomyPlaneGroup) anatomyPlaneGroup.visible = objectVisibility.value.cbct || objectVisibility.value.registration;
  if (referenceStageGroup) referenceStageGroup.visible = objectVisibility.value.registration;
  if (registrationMarkupGroup) registrationMarkupGroup.visible = objectVisibility.value.registration;
}

onMounted(() => {
  void ensureSceneReady();
});

async function ensureSceneReady() {
  await nextTick();
  if (!canvasHost.value) return;
  if (scene && renderer) {
    if (!canvasHost.value.contains(renderer.domElement)) {
      canvasHost.value.appendChild(renderer.domElement);
      resizeObserver?.disconnect();
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(canvasHost.value);
    }
    resize();
    return;
  }
  initScene();
  void loadGeometryManifest();
  renderHotspots();
  applySceneVisibility();
  startAnimation();
}

onBeforeUnmount(() => {
  stopAnimation();
  revokeLocalSurfaceObjectUrl();
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (renderer?.domElement && canvasHost.value?.contains(renderer.domElement)) {
    canvasHost.value.removeChild(renderer.domElement);
  }
  renderer?.dispose();
  controls?.dispose();
  renderer = null;
  scene = null;
  camera = null;
  controls = null;
  rootGroup = null;
  boneGroup = null;
  hotspotGroup = null;
  planningGuideGroup = null;
  anatomyPlaneGroup = null;
  referenceStageGroup = null;
  registrationMarkupGroup = null;
  fallbackBoneGroup = null;
  loadedAnatomyGroup = null;
});

watch(normalizedHotspots, () => renderHotspots(), { deep: true });
watch(
  () => selectedHotspotKey.value,
  () => renderHotspots(),
);
watch(
  () => selectedMarkupId.value,
  () => renderRegistrationMarkups(),
);
watch(
  evidence,
  () => {
    void loadGeometryManifest();
    if (boneGroup) void loadRealAnatomyModel();
    renderRegistrationMarkups();
  },
  { deep: true },
);
watch(registrationMarkupRows, () => renderRegistrationMarkups(), { deep: true });

function initScene() {
  const host = canvasHost.value;
  if (!host) return;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x081522);
  scene.fog = new THREE.Fog(0x081522, 5.6, 10.2);

  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0.8, 1.56, 5.75);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.18;
  host.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = autoRotateModel.value;
  controls.autoRotateSpeed = 0.7;
  controls.enablePan = false;
  controls.minDistance = 3.45;
  controls.maxDistance = 7.4;
  controls.minPolarAngle = 0.62;
  controls.maxPolarAngle = 1.78;
  controls.target.set(0.04, 0.38, 0);
  controls.update();

  rootGroup = new THREE.Group();
  rootGroup.rotation.x = -0.02;
  rootGroup.rotation.y = -0.18;
  scene.add(rootGroup);

  boneGroup = new THREE.Group();
  hotspotGroup = new THREE.Group();
  planningGuideGroup = new THREE.Group();
  anatomyPlaneGroup = new THREE.Group();
  referenceStageGroup = new THREE.Group();
  registrationMarkupGroup = new THREE.Group();
  rootGroup.add(boneGroup);
  rootGroup.add(planningGuideGroup);
  rootGroup.add(anatomyPlaneGroup);
  rootGroup.add(referenceStageGroup);
  rootGroup.add(registrationMarkupGroup);
  rootGroup.add(hotspotGroup);

  addLights();
  renderRegistrationMarkups();
  void loadRealAnatomyModel();
  resize();

  resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(host);
}

function addLights() {
  if (!scene) return;
  scene.add(new THREE.HemisphereLight(0xf4fbff, 0x263b4c, 2.6));

  const key = new THREE.DirectionalLight(0xffffff, 5.8);
  key.position.set(3.4, 4.9, 3.8);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.near = 0.5;
  key.shadow.camera.far = 12;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xa7f0ff, 1.4);
  fill.position.set(-2.6, 1.2, 3.2);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0x55d6ff, 3.0);
  rim.position.set(-3.8, 2.6, -2.9);
  scene.add(rim);

  const fluorescence = new THREE.PointLight(0x61dfff, 2.8, 7);
  fluorescence.position.set(0.8, 0.5, 2.4);
  scene.add(fluorescence);

  const underGlow = new THREE.PointLight(0x2ea7ff, 2.2, 5.8);
  underGlow.position.set(0, -1.0, 1.2);
  scene.add(underGlow);
}

function buildMandible() {
  if (!fallbackBoneGroup) return;

  const corticalMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xe8d8c4,
    roughness: 0.48,
    metalness: 0.02,
    clearcoat: 0.18,
    transparent: true,
    opacity: 0.95,
  });
  const cancellousMaterial = new THREE.MeshStandardMaterial({
    color: 0xb88f78,
    roughness: 0.78,
    transparent: true,
    opacity: 0.34,
  });
  const enamelMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xf6efe5,
    roughness: 0.32,
    clearcoat: 0.22,
  });
  const cutSurfaceMaterial = new THREE.MeshStandardMaterial({
    color: 0xd9b69d,
    roughness: 0.62,
  });

  const archCurve = mandibleCurve();
  const body = new THREE.Mesh(new THREE.TubeGeometry(archCurve, 120, 0.22, 28, false), corticalMaterial);
  body.castShadow = true;
  body.receiveShadow = true;
  fallbackBoneGroup.add(body);

  const marrow = new THREE.Mesh(new THREE.TubeGeometry(archCurve, 110, 0.145, 18, false), cancellousMaterial);
  marrow.position.y -= 0.015;
  fallbackBoneGroup.add(marrow);

  const alveolarCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-1.58, 0.12, 0.02),
    new THREE.Vector3(-1.02, -0.02, 0.23),
    new THREE.Vector3(-0.45, -0.08, 0.35),
    new THREE.Vector3(0, -0.1, 0.39),
    new THREE.Vector3(0.45, -0.08, 0.35),
    new THREE.Vector3(1.02, -0.02, 0.23),
    new THREE.Vector3(1.58, 0.12, 0.02),
  ]);
  const alveolar = new THREE.Mesh(new THREE.TubeGeometry(alveolarCurve, 96, 0.075, 18, false), cutSurfaceMaterial);
  alveolar.position.y += 0.22;
  alveolar.castShadow = true;
  fallbackBoneGroup.add(alveolar);

  buildRamus(-1, corticalMaterial, cutSurfaceMaterial);
  buildRamus(1, corticalMaterial, cutSurfaceMaterial);
  buildTeeth(archCurve, enamelMaterial);
  buildMentalForamina();
}

function buildRamus(side: -1 | 1, corticalMaterial: THREE.Material, cutSurfaceMaterial: THREE.Material) {
  if (!fallbackBoneGroup) return;
  const ramus = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.86, 12, 24), corticalMaterial);
  ramus.position.set(side * 1.88, 0.44, -0.03);
  ramus.rotation.z = side * 0.24;
  ramus.scale.set(0.85, 1.18, 0.95);
  ramus.castShadow = true;
  ramus.receiveShadow = true;
  fallbackBoneGroup.add(ramus);

  const condyle = new THREE.Mesh(new THREE.SphereGeometry(0.18, 32, 18), cutSurfaceMaterial);
  condyle.position.set(side * 1.97, 1.1, -0.1);
  condyle.scale.set(1.32, 0.72, 0.92);
  condyle.castShadow = true;
  fallbackBoneGroup.add(condyle);

  const coronoid = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.48, 28), corticalMaterial);
  coronoid.position.set(side * 1.64, 0.98, 0.2);
  coronoid.rotation.z = side * -0.28;
  coronoid.castShadow = true;
  fallbackBoneGroup.add(coronoid);
}

function buildTeeth(archCurve: THREE.CatmullRomCurve3, enamelMaterial: THREE.Material) {
  if (!fallbackBoneGroup) return;
  const toothCount = 14;
  for (let index = 0; index < toothCount; index += 1) {
    const t = 0.06 + (index / (toothCount - 1)) * 0.88;
    const point = archCurve.getPoint(t);
    const tangent = archCurve.getTangent(t);
    const crownHeight = index < 3 || index > 10 ? 0.18 : 0.23;
    const radius = index < 2 || index > 11 ? 0.065 : 0.078;
    const tooth = new THREE.Mesh(new THREE.CapsuleGeometry(radius, crownHeight, 8, 18), enamelMaterial);
    tooth.position.set(point.x, point.y + 0.34, point.z + 0.12);
    tooth.rotation.z = -Math.atan2(tangent.x, tangent.y) * 0.22;
    tooth.rotation.x = -0.14;
    tooth.castShadow = true;
    fallbackBoneGroup.add(tooth);

    const root = new THREE.Mesh(
      new THREE.ConeGeometry(radius * 0.72, 0.18, 18),
      new THREE.MeshStandardMaterial({ color: 0xd9c7b4, roughness: 0.58 }),
    );
    root.position.set(point.x, point.y + 0.2, point.z + 0.08);
    root.rotation.x = Math.PI;
    fallbackBoneGroup.add(root);
  }
}

function buildMentalForamina() {
  if (!fallbackBoneGroup) return;
  const material = new THREE.MeshBasicMaterial({ color: 0x6a4f3f, transparent: true, opacity: 0.68 });
  [-0.72, 0.72].forEach((x) => {
    const foramen = new THREE.Mesh(new THREE.CircleGeometry(0.055, 24), material);
    foramen.position.set(x, -0.2, 0.53);
    foramen.rotation.x = -0.18;
    fallbackBoneGroup?.add(foramen);
  });
}

function buildPlanningGuides() {
  if (!planningGuideGroup) return;

  const curveMaterial = new THREE.MeshBasicMaterial({
    color: 0x50a7d8,
    transparent: true,
    opacity: 0.86,
  });
  const planningCurve = new THREE.Mesh(new THREE.TubeGeometry(mandibleCurve(), 128, 0.018, 10, false), curveMaterial);
  planningCurve.position.y += 0.55;
  planningCurve.position.z += 0.08;
  planningGuideGroup.add(planningCurve);

  const reviewPlaneMaterial = new THREE.MeshBasicMaterial({
    color: 0xf2c14e,
    transparent: true,
    opacity: 0.22,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const planeEdgeMaterial = new THREE.MeshBasicMaterial({
    color: 0xf6d36c,
    transparent: true,
    opacity: 0.58,
    side: THREE.DoubleSide,
    depthWrite: false,
  });

  sceneReviewPlanes().forEach((spec) => {
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(0.82, 1.58), reviewPlaneMaterial);
    plane.position.copy(spec.position);
    plane.rotation.x = spec.rotation.x;
    plane.rotation.y = spec.rotation.y;
    plane.rotation.z = spec.rotation.z;
    planningGuideGroup?.add(plane);

    const edge = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.006, 8, 72), planeEdgeMaterial);
    edge.position.copy(plane.position);
    edge.rotation.x = plane.rotation.x;
    edge.rotation.y = plane.rotation.y;
    edge.rotation.z = plane.rotation.z;
    edge.scale.copy(spec.scale);
    planningGuideGroup?.add(edge);
  });

  const fiducialMaterial = new THREE.MeshBasicMaterial({
    color: 0x3fc39a,
    transparent: true,
    opacity: 0.88,
  });
  [0.12, 0.32, 0.5, 0.68, 0.88].forEach((t) => {
    const point = mandibleCurve().getPoint(t);
    const marker = new THREE.Mesh(new THREE.SphereGeometry(0.05, 18, 12), fiducialMaterial);
    marker.position.set(point.x, point.y + 0.58, point.z + 0.14);
    planningGuideGroup?.add(marker);
  });

  const trajectory = new THREE.Mesh(
    new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3([
        new THREE.Vector3(1.65, 0.76, 0.86),
        new THREE.Vector3(0.82, 0.44, 0.55),
        new THREE.Vector3(0.12, 0.18, 0.32),
      ]),
      32,
      0.014,
      10,
      false,
    ),
    new THREE.MeshBasicMaterial({ color: 0x7fb4c8, transparent: true, opacity: 0.52 }),
  );
  planningGuideGroup.add(trajectory);
}

async function loadRealAnatomyModel() {
  const sequence = ++modelLoadSequence;
  if (!boneGroup) return;
  clearLoadedAnatomyModel();
  const model = await findAvailableModel();
  if (!model) {
    if (sequence === modelLoadSequence) {
      modelLoadState.value = "fallback";
      loadedModelPath.value = "";
    }
    return;
  }

  try {
    const loaded = model.format === "stl"
      ? await loadStlModel(model.path)
      : await loadGltfModel(model.path);
    if (sequence !== modelLoadSequence) {
      disposeObject(loaded);
      return;
    }
    normalizeLoadedModel(loaded, modelRotationXDegrees.value);
    if (fallbackBoneGroup) {
      boneGroup.remove(fallbackBoneGroup);
      disposeObject(fallbackBoneGroup);
      fallbackBoneGroup = null;
    }
    loadedAnatomyGroup = loaded;
    boneGroup.add(loaded);
    modelLoadState.value = "loaded";
    loadedModelPath.value = model.sourcePath;
  } catch {
    if (sequence !== modelLoadSequence) return;
    clearLoadedAnatomyModel();
    modelLoadState.value = "failed";
    loadedModelPath.value = model.sourcePath;
  }
}

async function findAvailableModel(): Promise<{ path: string; sourcePath: string; format: "stl" | "gltf" } | null> {
  if (evidenceModelPath.value) {
    return {
      path: modelUrlFromPath(evidenceModelPath.value),
      sourcePath: evidenceModelPath.value,
      format: modelFormatFromPath(evidenceModelPath.value),
    };
  }
  return null;
}

function clearLoadedAnatomyModel() {
  if (!boneGroup || !loadedAnatomyGroup) return;
  boneGroup.remove(loadedAnatomyGroup);
  disposeObject(loadedAnatomyGroup);
  loadedAnatomyGroup = null;
}

function ensureFallbackModel() {
  if (!boneGroup || fallbackBoneGroup) return;
  fallbackBoneGroup = new THREE.Group();
  boneGroup.add(fallbackBoneGroup);
  buildMandible();
}

function modelUrlFromPath(path: string): string {
  if (/^(https?:|data:|blob:|\/)/i.test(path)) return path;
  const normalized = path.replace(/\\/g, "/");
  const publicPrefix = "frontend/public/";
  if (normalized.startsWith(publicPrefix)) return `/${normalized.slice(publicPrefix.length)}`;
  return apiClient.fileDownloadUrl(path);
}

async function loadGeometryManifest() {
  const path = geometryManifestPath.value;
  geometryManifest.value = null;
  if (!path) {
    geometryLoadState.value = "idle";
    return;
  }
  geometryLoadState.value = "loading";
  const requestPath = path;
  try {
    const response = await fetch(modelUrlFromPath(path), { cache: "no-store" });
    if (!response.ok) throw new Error(`Geometry manifest request failed: ${response.status}`);
    const payload = (await response.json()) as unknown;
    if (requestPath !== geometryManifestPath.value) return;
    if (!isEvidenceRecord(payload)) throw new Error("Geometry manifest payload is not an object");
    geometryManifest.value = payload as ThreeDGeometryManifest;
    geometryLoadState.value = "loaded";
  } catch {
    if (requestPath !== geometryManifestPath.value) return;
    geometryManifest.value = null;
    geometryLoadState.value = "failed";
  }
}

function modelFormatFromPath(path: string): "stl" | "gltf" {
  const format = evidenceModelFormat.value;
  if (format.includes("stl")) return "stl";
  if (format.includes("glb") || format.includes("gltf")) return "gltf";
  const pathname = path.split("?")[0].toLowerCase();
  return pathname.endsWith(".stl") ? "stl" : "gltf";
}

async function loadGltfModel(path: string): Promise<THREE.Group> {
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(path);
  const group = new THREE.Group();
  group.add(gltf.scene);
  applyMedicalModelMaterial(group);
  return group;
}

async function loadStlModel(path: string): Promise<THREE.Group> {
  const loader = new STLLoader();
  const geometry = await loader.loadAsync(path);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshPhysicalMaterial({
      color: 0xd8c7b0,
      roughness: 0.62,
      metalness: 0.02,
      clearcoat: 0.08,
      transparent: false,
      opacity: 1,
      depthWrite: true,
      side: THREE.DoubleSide,
    }),
  );
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  const group = new THREE.Group();
  group.add(mesh);

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry, 34),
    new THREE.LineBasicMaterial({
      color: 0x806f5e,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
    }),
  );
  edges.scale.setScalar(1.001);
  group.add(edges);
  return group;
}

function applyMedicalModelMaterial(model: THREE.Object3D) {
  model.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    child.castShadow = true;
    child.receiveShadow = true;
    if (!child.material) {
      child.material = new THREE.MeshPhysicalMaterial({ color: 0xe8d8c4, roughness: 0.5 });
    }
  });
}

function normalizeLoadedModel(model: THREE.Object3D, rotationXDegrees: number) {
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const maxAxis = Math.max(size.x, size.y, size.z) || 1;
  const scale = 2.25 / maxAxis;
  model.scale.setScalar(scale);
  model.rotation.x = (rotationXDegrees * Math.PI) / 180;

  const fittedCenter = center.clone().multiplyScalar(scale).applyEuler(model.rotation);
  model.position.copy(fittedCenter.multiplyScalar(-1));
  model.position.y += 0.5;
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

function buildAnatomyPlanes() {
  if (!anatomyPlaneGroup) return;
  const planes = [
    { color: 0x4d99c8, opacity: 0.1, rotation: [Math.PI / 2, 0, 0], position: [0, 0.18, 0.12], scale: [1.18, 0.72, 1] },
    { color: 0x69b58a, opacity: 0.08, rotation: [0, Math.PI / 2, 0], position: [0, 0.16, 0.05], scale: [1, 0.72, 1] },
    { color: 0xb79a58, opacity: 0.08, rotation: [0, 0, 0], position: [0, 0.16, -0.02], scale: [1.18, 0.72, 1] },
  ];
  planes.forEach((spec) => {
    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(3.8, 2.18),
      new THREE.MeshBasicMaterial({
        color: spec.color,
        transparent: true,
        opacity: spec.opacity,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    plane.rotation.x = spec.rotation[0];
    plane.rotation.y = spec.rotation[1];
    plane.rotation.z = spec.rotation[2];
    plane.position.set(spec.position[0], spec.position[1], spec.position[2]);
    plane.scale.set(spec.scale[0], spec.scale[1], spec.scale[2]);
    anatomyPlaneGroup?.add(plane);
  });
}

function buildReferenceStage() {
  if (!referenceStageGroup) return;
  const grid = new THREE.GridHelper(5.7, 22, 0x39d7ff, 0x1c4058);
  grid.position.y = -0.93;
  grid.rotation.x = 0.05;
  referenceStageGroup.add(grid);

  const base = new THREE.Mesh(
    new THREE.CircleGeometry(2.9, 128),
    new THREE.MeshBasicMaterial({ color: 0x0d3550, transparent: true, opacity: 0.58, side: THREE.DoubleSide }),
  );
  base.rotation.x = -Math.PI / 2;
  base.position.y = -0.96;
  referenceStageGroup.add(base);

  const contactGlow = new THREE.Mesh(
    new THREE.CircleGeometry(1.68, 96),
    new THREE.MeshBasicMaterial({
      color: 0x59cfff,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  );
  contactGlow.rotation.x = -Math.PI / 2;
  contactGlow.position.set(0, -0.925, 0.12);
  contactGlow.scale.set(1.35, 0.48, 1);
  referenceStageGroup.add(contactGlow);

  const outerRing = new THREE.Mesh(
    new THREE.TorusGeometry(2.15, 0.012, 12, 160),
    new THREE.MeshBasicMaterial({
      color: 0x6fe7ff,
      transparent: true,
      opacity: 0.54,
      depthWrite: false,
    }),
  );
  outerRing.rotation.x = -Math.PI / 2;
  outerRing.position.y = -0.9;
  referenceStageGroup.add(outerRing);

  buildAxisTriad();
}

function buildAxisTriad() {
  if (!referenceStageGroup) return;
  const origin = new THREE.Vector3(-2.32, -0.78, 1.42);
  const axes = [
    { color: 0xd65c5c, end: new THREE.Vector3(-1.82, -0.78, 1.42), cone: new THREE.Vector3(-1.76, -0.78, 1.42), rotation: [0, 0, -Math.PI / 2] },
    { color: 0x57a66d, end: new THREE.Vector3(-2.32, -0.28, 1.42), cone: new THREE.Vector3(-2.32, -0.22, 1.42), rotation: [0, 0, 0] },
    { color: 0x4d87d6, end: new THREE.Vector3(-2.32, -0.78, 0.92), cone: new THREE.Vector3(-2.32, -0.78, 0.86), rotation: [Math.PI / 2, 0, 0] },
  ];
  axes.forEach((axis) => {
    const material = new THREE.MeshBasicMaterial({ color: axis.color, transparent: true, opacity: 0.92 });
    const shaft = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([origin, axis.end]), 4, 0.012, 8, false), material);
    referenceStageGroup?.add(shaft);

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.04, 0.13, 14), material);
    cone.position.copy(axis.cone);
    cone.rotation.x = axis.rotation[0];
    cone.rotation.y = axis.rotation[1];
    cone.rotation.z = axis.rotation[2];
    referenceStageGroup?.add(cone);
  });
}

function renderHotspots() {
  if (!hotspotGroup) return;
  const group = hotspotGroup;
  group.clear();
  normalizedHotspots.value.forEach((hotspot) => {
    const color = isRegistered.value ? riskColors[hotspot.risk] : 0x8fb1bd;
    const selected = selectedHotspotKey.value === hotspot.key;
    const patch = new THREE.Mesh(
      new THREE.SphereGeometry(hotspot.scale, 48, 24),
      new THREE.MeshPhysicalMaterial({
        color,
        emissive: color,
        emissiveIntensity: isRegistered.value ? (selected ? 0.72 : 0.42) : 0.12,
        transparent: true,
        opacity: isRegistered.value ? (selected ? 0.62 : 0.42) : 0.24,
        roughness: 0.34,
        depthWrite: false,
      }),
    );
    patch.position.copy(hotspot.position);
    patch.scale.set(1.45, 0.28, 0.82);
    orientPatchToNormal(patch, hotspot.normal);
    group.add(patch);

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(hotspot.scale * 1.7, 48, 24),
      new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: isRegistered.value ? (selected ? 0.16 : 0.08) : 0.05,
        depthWrite: false,
      }),
    );
    halo.position.copy(hotspot.position).addScaledVector(hotspot.normal, 0.025);
    halo.scale.set(1.65, 0.2, 0.92);
    orientPatchToNormal(halo, hotspot.normal);
    group.add(halo);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(hotspot.scale * 1.02, 0.012, 10, 72),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: isRegistered.value ? (selected ? 0.72 : 0.34) : 0.22 }),
    );
    ring.position.copy(hotspot.position).addScaledVector(hotspot.normal, 0.05);
    orientPatchToNormal(ring, hotspot.normal);
    group.add(ring);
  });
}

function renderRegistrationMarkups() {
  if (!registrationMarkupGroup) return;
  const group = registrationMarkupGroup;
  group.clear();
  registrationMarkupRows.value.filter((markup) => markup.ready).forEach((markup, index) => {
    const selected = selectedMarkupId.value === markup.id;
    const color = markup.ready ? 0x49b988 : 0x8798a8;
    const pointMaterial = new THREE.MeshBasicMaterial({
      color: selected ? 0xf2c14e : color,
      transparent: true,
      opacity: selected ? 0.96 : 0.74,
    });
    const point = new THREE.Mesh(new THREE.SphereGeometry(selected ? 0.066 : 0.046, 18, 12), pointMaterial);
    point.position.copy(markup.position).addScaledVector(new THREE.Vector3(0, 1, 0), 0.58);
    group.add(point);

    const target = markup.position.clone().addScaledVector(new THREE.Vector3(index % 2 ? -0.18 : 0.18, 0.11, 0.16), 1);
    const connector = new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.CatmullRomCurve3([point.position.clone(), target]), 6, selected ? 0.01 : 0.006, 8, false),
      new THREE.MeshBasicMaterial({
        color: selected ? 0xf2c14e : color,
        transparent: true,
        opacity: selected ? 0.68 : 0.34,
      }),
    );
    group.add(connector);

    const targetPoint = new THREE.Mesh(new THREE.SphereGeometry(0.032, 14, 10), pointMaterial);
    targetPoint.position.copy(target);
    group.add(targetPoint);
  });
}

function startAnimation() {
  const tick = () => {
    frameId = window.requestAnimationFrame(tick);
    controls?.update();
    if (rootGroup && autoRotateModel.value && !controls?.enabled) {
      rootGroup.rotation.y += 0.002;
    }
    renderer?.render(scene as THREE.Scene, camera as THREE.PerspectiveCamera);
  };
  tick();
}

function stopAnimation() {
  if (frameId) {
    window.cancelAnimationFrame(frameId);
    frameId = 0;
  }
}

function resize() {
  const host = canvasHost.value;
  if (!host || !renderer || !camera) return;
  const width = Math.max(320, host.clientWidth);
  const height = Math.max(420, host.clientHeight);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function sceneCurvePoints(): THREE.Vector3[] {
  const rawPoints = sceneManifest.value?.mandibular_curve?.display_points;
  const points = Array.isArray(rawPoints)
    ? rawPoints.map((point) => vectorFromScenePoint(point)).filter((point): point is THREE.Vector3 => point !== null)
    : [];
  if (points.length >= 2) return points;
  return [
    new THREE.Vector3(-1.9, 0.02, -0.08),
    new THREE.Vector3(-1.42, -0.12, 0.16),
    new THREE.Vector3(-0.72, -0.28, 0.34),
    new THREE.Vector3(0, -0.36, 0.42),
    new THREE.Vector3(0.72, -0.28, 0.34),
    new THREE.Vector3(1.42, -0.12, 0.16),
    new THREE.Vector3(1.9, 0.02, -0.08),
  ];
}

function sceneReviewPlanes(): ScenePlaneDisplay[] {
  const rawPlanes = sceneManifest.value?.review_planes;
  const planes = Array.isArray(rawPlanes)
    ? rawPlanes
        .map((plane, index) => scenePlaneFromEvidence(plane, index))
        .filter((plane): plane is ScenePlaneDisplay => plane !== null)
    : [];
  if (planes.length) return planes;
  return [
    {
      id: "fallback-plane-left",
      label: "左侧复核平面",
      position: new THREE.Vector3(-0.95, 0.18, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2 - 0.13, -0.16),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
    {
      id: "fallback-plane-mid",
      label: "中间复核平面",
      position: new THREE.Vector3(0, 0.21, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2, 0),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
    {
      id: "fallback-plane-right",
      label: "右侧复核平面",
      position: new THREE.Vector3(0.95, 0.24, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2 + 0.13, 0.16),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
  ];
}

function scenePlaneFromEvidence(plane: ThreeDScenePlane, index: number): ScenePlaneDisplay | null {
  const position = vectorFromScenePoint(plane.display_position);
  if (!position) return null;
  return {
    id: stringFromEvidence(plane.id) || `scene-plane-${index + 1}`,
    label: stringFromEvidence(plane.label) || `Scene plane ${index + 1}`,
    position,
    rotation: vectorFromScenePoint(plane.display_rotation) ?? new THREE.Vector3(0, Math.PI / 2, 0),
    scale: vectorFromScenePoint(plane.display_scale) ?? new THREE.Vector3(1.0, 1.85, 1),
  };
}

function mandibleCurve() {
  return new THREE.CatmullRomCurve3(sceneCurvePoints());
}

function pointOnMandibleArch(t: number) {
  const curve = mandibleCurve();
  const position = curve.getPoint(THREE.MathUtils.clamp(t, 0.08, 0.92));
  position.y += 0.05;
  position.z += 0.18;
  const tangent = curve.getTangent(t);
  const normal = new THREE.Vector3(-tangent.z, 0.18, tangent.x).normalize();
  if (normal.z < 0) normal.multiplyScalar(-1);
  return { position, normal };
}

function geometrySegmentLengthLabels(): string[] {
  const measurements = geometryManifest.value?.segment_measurements;
  if (!Array.isArray(measurements)) return [];
  return measurements
    .map((item, index) => {
      const length = numberFromEvidenceValue(item.length_mm);
      if (length == null) return null;
      return `${stringFromEvidence(item.id) || `S${index}`}: ${length.toFixed(2)} mm`;
    })
    .filter((item): item is string => item !== null);
}

function orientPatchToNormal(mesh: THREE.Object3D, normal: THREE.Vector3) {
  const source = new THREE.Vector3(0, 0, 1);
  mesh.quaternion.setFromUnitVectors(source, normal.clone().normalize());
}

function riskFromCandidate(candidate: CandidateRegion): RiskLevel {
  const source = `${candidate.risk_type} ${candidate.explanation ?? ""}`.toLowerCase();
  if (source.includes("high") || source.includes("高") || source.includes("necrotic") || source.includes("坏死")) {
    return "high";
  }
  if (source.includes("medium") || source.includes("中") || source.includes("inflamm") || source.includes("炎")) {
    return "medium";
  }
  return "low";
}

function normalizedConfidence(candidate: CandidateRegion): number {
  const value = candidate.confidence ?? candidate.score ?? numberFromMetadata(candidate.metadata, "confidence") ?? 0.55;
  return THREE.MathUtils.clamp(Number(value), 0.18, 0.96);
}

function explicitRegistrationMarkups(): RegistrationMarkupRow[] {
  const raw = evidence.value?.registration_markups;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(isEvidenceRecord)
    .slice(0, 10)
    .map((markup, index) => registrationMarkupRowFromEvidence(markup as ThreeDEvidenceMarkup, index));
}

function registrationMarkupRowFromEvidence(markup: ThreeDEvidenceMarkup, index: number): RegistrationMarkupRow {
  const fallback = pointOnMandibleArch(THREE.MathUtils.clamp(0.12 + index * 0.16, 0.12, 0.88)).position;
  const position = pointFromEvidenceValue(markup.source_point_mm, fallback);
  const residual = numberFromEvidenceValue(markup.residual_mm);
  const status = stringFromEvidence(markup.status);
  const ready = isRegistered.value && Boolean(status) && !["missing", "rejected", "unavailable"].includes(status.toLowerCase());
  return {
    id: stringFromEvidence(markup.id) || `registration-markup-${index + 1}`,
    shortLabel: `F${index + 1}`,
    label: humanizeEvidenceText(stringFromEvidence(markup.label)) || `F${index + 1} 配准标志点`,
    sourceLabel: humanizeEvidenceText(stringFromEvidence(markup.source_label)) || pointLabelFromEvidence(markup.source_point_mm, "源点"),
    targetLabel: humanizeEvidenceText(stringFromEvidence(markup.target_label)) || pointLabelFromEvidence(markup.target_point_mm, "目标点"),
    residualLabel: residual == null ? "残差：缺失" : `残差：${residual.toFixed(2)} mm`,
    statusLabel: statusLabel(status, ready),
    ready,
    position,
  };
}

function explicitTransformChain(): TransformChainItem[] {
  const raw = evidence.value?.transform_chain;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(isEvidenceRecord)
    .slice(0, 8)
    .map((step, index) => transformStepFromEvidence(step as ThreeDEvidenceTransformStep, index));
}

function transformStepFromEvidence(step: ThreeDEvidenceTransformStep, index: number): TransformChainItem {
  const status = stringFromEvidence(step.status);
  const error = numberFromEvidenceValue(step.error_mm);
  const path = stringFromEvidence(step.path);
  const ready = ["ready", "registered", "accepted", "ok", "true"].includes(status.toLowerCase());
  return {
    name: humanizeEvidenceText(stringFromEvidence(step.name)) || `变换 ${index + 1}`,
    fromSpace: humanizeEvidenceText(stringFromEvidence(step.from_space)) || "未记录输入坐标",
    toSpace: humanizeEvidenceText(stringFromEvidence(step.to_space)) || "未记录输出坐标",
    detail: [path || "变换文件未记录", error == null ? "" : `${error.toFixed(2)} mm`].filter(Boolean).join(" · "),
    ready,
  };
}

function objectTreeGroupsFromSceneV2(): ObjectTreeGroup[] {
  const manifest = sceneManifestV2.value;
  const hierarchy = Array.isArray(manifest?.subject_hierarchy) ? manifest.subject_hierarchy : [];
  if (!manifest || !hierarchy.length) return [];
  const allNodes = [
    ...(Array.isArray(manifest.nodes) ? manifest.nodes : []),
    ...(Array.isArray(manifest.markups) ? manifest.markups : []),
    ...(Array.isArray(manifest.geometry_jobs)
      ? manifest.geometry_jobs.map((job, index) => ({
          id: stringFromEvidence(job.id) || `geometry_job_${index + 1}`,
          type: "geometry_job",
          role: stringFromEvidence(job.type) || "geometry_job",
          name: stringFromEvidence(job.type) || `几何任务 ${index + 1}`,
          review_status: stringFromEvidence(job.status),
        }))
      : []),
  ].filter(isEvidenceRecord);
  const byId = new Map(allNodes.map((node) => [stringFromEvidence(node.id), node]));
  return hierarchy
    .map((group) => {
      const children = Array.isArray(group.children) ? group.children : [];
      return {
        name: humanizeEvidenceText(stringFromEvidence(group.name)) || stringFromEvidence(group.id) || "未命名分组",
        detail: `${children.length} 个场景对象`,
        items: children
          .map((childId) => byId.get(childId))
          .filter(isEvidenceRecord)
          .map(sceneV2NodeToObjectTreeItem),
      };
    })
    .filter((group) => group.items.length > 0);
}

function sceneV2NodeToObjectTreeItem(node: Record<string, unknown>): ObjectTreeItem {
  const type = stringFromEvidence(node.type);
  const status = stringFromEvidence(node.review_status || node.status);
  const path = stringFromEvidence(node.path);
  const source = stringFromEvidence(node.source);
  const role = stringFromEvidence(node.role);
  const key: ObjectVisibilityKey =
    type === "volume"
      ? "cbct"
      : type === "model" || type === "segmentation"
        ? "mandible"
        : type === "curve" || type === "plane"
          ? "curvePlanes"
          : "registration";
  const interactive =
    type === "model"
      ? modelLoadState.value === "loaded"
      : type === "curve" || type === "plane"
        ? modelLoadState.value === "loaded"
        : false;
  return {
    key,
    name: humanizeEvidenceText(stringFromEvidence(node.name)) || humanizeEvidenceText(role) || humanizeEvidenceText(type) || "未命名对象",
    detail: humanizeEvidenceText(source || path || role || type) || "对象来源未记录",
    state: statusLabel(status, ["ready", "completed", "accepted", "recorded"].includes(status.toLowerCase())),
    muted: !objectVisibility.value[key],
    locked: type === "volume" || type === "segmentation" || type === "model",
    interactive,
  };
}

function humanizeEvidenceText(value: string): string {
  if (!value.trim()) return "";
  const exact: Record<string, string> = {
    "3D Slicer Segmentations": "3D Slicer 分割模块导出",
    "doctor reviewed mandibular segmentation": "医生复核下颌分割",
    accepted: "已接受",
    approved: "已批准",
    reviewed: "已复核",
    registered: "已配准",
    unregistered: "未配准",
    ready: "已就绪",
    "point-based + surface matching": "点配准 + 表面匹配",
    "CBCT RAS to STL surface": "CBCT 坐标到 STL 表面",
    "STL surface to keyframe reference": "STL 表面到关键帧参考",
    cbct_ras: "CBCT RAS 坐标",
    mandible_stl: "下颌 STL 表面",
    video_keyframe_reference: "视频关键帧参考",
    "Left mental foramen": "左侧颏孔",
    "Right condyle": "右侧髁突",
    "CBCT L mental foramen": "CBCT 左侧颏孔",
    "tracked L mental foramen": "跟踪左侧颏孔",
    "CBCT R condyle": "CBCT 右侧髁突",
    "tracked R condyle": "跟踪右侧髁突",
    "D024 DentVoxel public CBCT derived mandible label": "D024 DentVoxel 公开 CBCT 派生下颌标签",
    "D024 DentVoxel label value 2 mandible": "D024 DentVoxel 标签 2：下颌骨",
    public_dataset_annotation_not_case_reviewed: "公开数据集标注，非本病例医生复核",
    cbct_label_voxel_spacing_mm: "CBCT 标签体素间距坐标",
    cbct_voxel_spacing_mm_proxy: "CBCT 体素间距代理坐标",
    cbct_physical_lps_mm_proxy: "CBCT 物理坐标代理表面",
    "uploaded CBCT hard tissue threshold proxy": "上传 CBCT 硬组织代理表面",
    "uploaded CBCT high-threshold hard tissue proxy": "上传 CBCT 高阈值硬组织代理表面",
    "uploaded CBCT balanced hard tissue proxy": "上传 CBCT 自适应硬组织代理表面",
    "automatic hard tissue proxy from raw CBCT; not mandible-specific": "原始 CBCT 自动硬组织代理，非下颌专用分割",
    "automatic high-threshold hard tissue proxy from raw CBCT; not mandible-specific":
      "原始 CBCT 高阈值硬组织代理，非下颌专用分割",
    "automatic balanced hard tissue proxy from raw CBCT; not mandible-specific":
      "原始 CBCT 自适应硬组织代理，非下颌专用分割",
    "automatic balanced hard tissue proxy from raw CBCT; not jawbone-specific":
      "原始 CBCT 自适应硬组织代理，非上下颌骨专用分割",
    "automatic hard tissue proxy threshold from raw CBCT": "原始 CBCT 自动阈值硬组织代理",
    "automatic high-threshold hard tissue proxy from raw CBCT": "原始 CBCT 高阈值硬组织代理",
    "automatic balanced hard tissue proxy from raw CBCT": "原始 CBCT 自适应硬组织代理",
    "CBCT DICOM voxels to hard tissue proxy STL": "CBCT DICOM 体素到硬组织代理 STL",
    "CBCT DICOM voxels to physical hard tissue proxy STL": "CBCT DICOM 体素到物理坐标硬组织代理 STL",
    "Proxy STL to video keyframe reference": "代理 STL 到视频关键帧参考",
    dicom_voxel_space: "DICOM 体素空间",
    cbct_hard_tissue_proxy_stl: "CBCT 硬组织代理 STL",
    cbct_physical_hard_tissue_proxy_stl: "CBCT 物理坐标硬组织代理 STL",
    uploaded_cbct_proxy_surface: "上传 CBCT 代理表面",
    high_percentile_hard_tissue_proxy: "高阈值硬组织代理",
    balanced_adaptive_hard_tissue_proxy: "自适应骨窗硬组织代理",
    pending_slicer_or_physician_review: "待 Slicer 或医生复核",
    axis_mapping_inferred_not_physician_reviewed: "轴向映射为系统推断，未医生复核",
    not_reviewed: "未复核",
    "SlicerBoneReconstructionPlanner-inspired scene semantics": "参考开源重建插件的场景语义",
    "D024 mandibular reference curve": "D024 下颌参考曲线",
    "high fluorescence prompt": "高荧光信号提示",
  };
  if (exact[value]) return exact[value];
  return value
    .replace(/public CBCT-derived mandible surface/gi, "公开 CBCT 派生下颌表面")
    .replace(/non-target-domain anatomy reference/gi, "非目标域解剖参考")
    .replace(/It is not surgical navigation\./gi, "不可作为手术导航。")
    .replace(/derived from STL manifest for display; not physician markups/gi, "由 STL 清单派生用于显示，非医生标志点")
    .replace(/Reference review plane left/gi, "左侧参考复核平面")
    .replace(/public CBCT derived mandible label/gi, "公开 CBCT 派生下颌标签")
    .replace(/CBCT-derived/gi, "CBCT 派生")
    .replace(/mandible/gi, "下颌骨")
    .replace(/surface/gi, "表面")
    .replace(/reference/gi, "参考")
    .replace(/ready/gi, "已就绪")
    .replace(/missing/gi, "缺失")
    .replace(/residual/gi, "残差")
    .replace(/transforms/gi, "变换")
    .replace(/segments/gi, "交线段");
}

function statusLabel(status: string, ready: boolean): string {
  const normalized = status.toLowerCase();
  if (["ready", "accepted", "recorded", "ok", "true"].includes(normalized)) return "已就绪";
  if (["missing", "rejected", "unavailable"].includes(normalized)) return "缺失";
  return status || (ready ? "已就绪" : "缺失");
}

function pointFromEvidenceValue(value: unknown, fallback: THREE.Vector3): THREE.Vector3 {
  const numbers = pointNumbersFromEvidence(value);
  if (!numbers) return fallback;
  return new THREE.Vector3(numbers[0] / 32, numbers[1] / 32 + 0.18, numbers[2] / 32);
}

function vectorFromScenePoint(value: unknown): THREE.Vector3 | null {
  const numbers = pointNumbersFromEvidence(value);
  if (!numbers) return null;
  return new THREE.Vector3(numbers[0], numbers[1], numbers[2]);
}

function pointNumbersFromEvidence(value: unknown): [number, number, number] | null {
  if (Array.isArray(value) && value.length >= 3) {
    const numbers = value.slice(0, 3).map(Number);
    return numbers.every(Number.isFinite) ? [numbers[0], numbers[1], numbers[2]] : null;
  }
  if (isEvidenceRecord(value)) {
    const numbers = [value.x, value.y, value.z].map(Number);
    return numbers.every(Number.isFinite) ? [numbers[0], numbers[1], numbers[2]] : null;
  }
  return null;
}

function pointLabelFromEvidence(value: unknown, fallback: string): string {
  const numbers = pointNumbersFromEvidence(value);
  if (!numbers) return fallback;
  return `[${numbers.map((item) => item.toFixed(1)).join(", ")}] mm`;
}

function numberFromMetadata(metadata: Record<string, unknown> | undefined, key: string): number | null {
  const value = metadata?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringFromMetadata(metadata: Record<string, unknown> | undefined, key: string): string {
  const value = metadata?.[key];
  return typeof value === "string" ? value.trim() : "";
}

function numberFromEvidenceValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function stringFromEvidence(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isEvidenceRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function fileNameFromPath(path: string): string {
  if (!path) return "";
  const cleanPath = path.split(/[?#]/)[0] ?? "";
  const parts = cleanPath.split(/[\\/]/).filter(Boolean);
  return parts.at(-1) ?? "";
}
</script>

<style scoped>
/* Slicer-style planning workbench. */
.anatomy-3d {
  --av-surface: var(--ov-bg-elevated);
  --av-surface-soft: var(--ov-bg-soft);
  --av-surface-panel: var(--ov-bg-panel);
  --av-border: var(--ov-border-subtle);
  --av-border-strong: var(--ov-border-strong);
  --av-text: var(--ov-text);
  --av-text-secondary: var(--ov-text-secondary);
  --av-text-muted: var(--ov-text-muted);
  --av-accent: var(--ov-primary-strong);
  --av-blue: var(--ov-primary-strong);
  --av-green: var(--ov-success);
  --av-amber: var(--ov-warning);
  --av-red: var(--ov-danger);
  --av-workbench-height: clamp(660px, 70vh, 820px);
  --av-empty-workbench-height: clamp(520px, 56vh, 620px);
  overflow: visible;
  border: 1px solid var(--av-border-strong);
  border-radius: 8px;
  background: var(--av-surface);
  color: var(--av-text);
  box-shadow: var(--ov-shadow);
}

.anatomy-3d::before {
  display: none;
}

.anatomy-3d,
.anatomy-3d * {
  box-sizing: border-box;
}

.anatomy-3d :where(span, strong, small, p, dt, dd, li, button, em, h2) {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.anatomy-3d__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(150px, auto);
  gap: 16px;
  align-items: stretch;
  padding: 20px 22px;
  border-bottom: 1px solid var(--av-border);
  background: var(--av-surface);
}

.anatomy-3d__titleblock {
  display: grid;
  gap: 5px;
}

.anatomy-3d__titleblock span,
.anatomy-3d__panel-title span {
  margin: 0;
  color: var(--av-accent);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: none;
}

.anatomy-3d__titleblock h2 {
  margin: 0;
  color: var(--av-text);
  font-size: 22px;
  line-height: 1.22;
  letter-spacing: 0;
}

.anatomy-3d__titleblock p {
  max-width: 92ch;
  margin: 0;
  color: var(--av-text-secondary);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.55;
}

.anatomy-3d__status {
  display: grid;
  justify-items: stretch;
  min-width: 0;
  gap: 5px;
}

.anatomy-3d__status strong {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  justify-self: end;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.35;
  text-align: right;
}

.anatomy-3d__status strong::before {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  content: "";
}

.anatomy-3d__status.is-high strong {
  color: var(--av-red);
}

.anatomy-3d__status.is-medium strong {
  color: var(--av-amber);
}

.anatomy-3d__status.is-low strong {
  color: var(--av-green);
}

.anatomy-3d__status.is-reference strong {
  color: var(--av-text-secondary);
}

.anatomy-3d__status small {
  color: var(--av-text-muted);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.35;
  text-align: center;
}

.anatomy-3d__slicer-menubar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  align-items: center;
  min-height: 40px;
  border-bottom: 1px solid var(--av-border);
  padding: 8px 16px;
  background: color-mix(in srgb, var(--av-surface) 78%, var(--av-surface-soft));
}

.anatomy-3d__slicer-menubar span,
.anatomy-3d__slicer-menubar label,
.anatomy-3d__slicer-menubar em {
  color: var(--av-text-secondary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
  font-style: normal;
}

.anatomy-3d__slicer-menubar label {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
}

.anatomy-3d__layout-switcher {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
}

.anatomy-3d__layout-switcher button {
  min-height: 26px;
  border: 1px solid var(--av-border);
  border-radius: 5px;
  padding: 4px 8px;
  background: var(--av-surface);
  color: var(--av-text-secondary);
  font: inherit;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
  cursor: pointer;
}

.anatomy-3d__layout-switcher button.is-active {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 11%, var(--av-surface));
  color: var(--av-accent);
}

.anatomy-3d__slicer-menubar strong {
  border: 1px solid var(--av-border);
  border-radius: 5px;
  padding: 3px 8px;
  background: var(--av-surface);
  color: var(--av-text);
}

.anatomy-3d__slicer-menubar em {
  margin-left: auto;
  border: 1px solid var(--av-border);
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__workflow-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  border-bottom: 1px solid var(--av-border);
  padding: 8px 12px;
  background: var(--av-surface-soft);
  list-style: none;
}

.anatomy-3d__workflow-step {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 48px;
  border: 0;
  padding: 8px 16px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: default;
}

.anatomy-3d__workflow-step:not(:last-child) {
  border-right: 1px solid var(--av-border);
}

.anatomy-3d__workflow-step span {
  grid-row: 1;
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--av-border-strong);
  border-radius: 50%;
  color: var(--av-accent);
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
}

.anatomy-3d__workflow-step strong,
.anatomy-3d__workflow-step small,
.anatomy-3d__workflow-step em {
  min-width: 0;
}

.anatomy-3d__workflow-step strong {
  color: var(--av-text);
  font-size: 13px;
  line-height: 1.25;
}

.anatomy-3d__workflow-step small {
  display: none;
}

.anatomy-3d__workflow-step em {
  grid-column: 3;
  grid-row: 1;
  justify-self: start;
  border-radius: 999px;
  padding: 2px 7px;
  background: var(--av-surface-soft);
  color: var(--av-text-muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  line-height: 1.25;
}

.anatomy-3d__workflow-step.is-ready span,
.anatomy-3d__workflow-step.is-ready em {
  border-color: color-mix(in srgb, var(--av-green) 45%, var(--av-border));
  background: color-mix(in srgb, var(--av-green) 12%, var(--av-surface));
  color: var(--av-green);
}

.anatomy-3d__workflow-step.is-partial span,
.anatomy-3d__workflow-step.is-partial em {
  border-color: color-mix(in srgb, var(--av-amber) 45%, var(--av-border));
  background: color-mix(in srgb, var(--av-amber) 12%, var(--av-surface));
  color: var(--av-amber);
}

.anatomy-3d__workflow-step.is-blocked span,
.anatomy-3d__workflow-step.is-blocked em {
  border-color: color-mix(in srgb, var(--av-red) 38%, var(--av-border));
  background: color-mix(in srgb, var(--av-red) 9%, var(--av-surface));
  color: var(--av-red);
}

.anatomy-3d__workflow-strip.is-focus-view .anatomy-3d__workflow-step {
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  min-height: 46px;
  padding: 7px 11px;
}

.anatomy-3d__workflow-strip.is-focus-view .anatomy-3d__workflow-step span {
  grid-row: 1;
}

.anatomy-3d__workflow-strip.is-focus-view .anatomy-3d__workflow-step small {
  display: none;
}

.anatomy-3d__workflow-strip.is-focus-view .anatomy-3d__workflow-step em {
  grid-column: 3;
  grid-row: 1;
  justify-self: end;
}

.anatomy-3d__workflow-strip .anatomy-3d__layout-switcher {
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 8px;
  background: var(--av-surface);
}

.anatomy-3d__toolbar {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1px;
  border-bottom: 1px solid var(--av-border);
  background: var(--av-border);
}

.anatomy-3d__tool {
  display: grid;
  gap: 2px;
  min-height: 58px;
  border: 0;
  align-content: center;
  padding: 9px 12px;
  background: var(--av-surface-soft);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.anatomy-3d__tool.is-active {
  background: color-mix(in srgb, var(--av-accent) 12%, var(--av-surface));
  box-shadow: inset 0 -3px 0 var(--av-accent);
}

.anatomy-3d__tool strong {
  color: var(--av-text);
  font-size: 13px;
  line-height: 1.35;
}

.anatomy-3d__tool small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.4;
}

.anatomy-3d__body {
  --av-side-row-height: clamp(318px, 34vh, 398px);
  display: grid;
  grid-template-columns: minmax(680px, 1fr) minmax(310px, 350px);
  grid-template-areas:
    "viewport tree"
    "viewport inspector"
    "check check";
  grid-template-rows: var(--av-side-row-height) var(--av-side-row-height) auto;
  align-items: stretch;
  gap: 24px;
  min-height: 0;
  padding: 24px;
  background: var(--av-surface-panel);
}

.anatomy-3d__object-tree,
.anatomy-3d__inspector,
.anatomy-3d__views {
  min-width: 0;
  background: var(--av-surface);
}

.anatomy-3d__object-tree,
.anatomy-3d__inspector {
  border: 1px solid var(--av-border);
  border-radius: 7px;
}

.anatomy-3d__object-tree {
  grid-area: tree;
  align-self: stretch;
  height: auto;
  max-height: none;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.anatomy-3d__views {
  grid-area: auto;
  min-height: 0;
}

.anatomy-3d__inspector {
  grid-area: inspector;
  align-self: stretch;
  grid-template-columns: 1fr;
  height: auto;
  max-height: none;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.anatomy-3d__object-tree,
.anatomy-3d__inspector {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 14px;
}

.anatomy-3d__inspector .anatomy-3d__panel-title,
.anatomy-3d__evidence-summary,
.anatomy-3d__evidence-drawer,
.anatomy-3d__boundary,
.anatomy-3d__hotspot-list,
.anatomy-3d__empty {
  grid-column: 1 / -1;
}

.anatomy-3d__panel-title {
  display: grid;
  gap: 3px;
}

.anatomy-3d__panel-title strong {
  color: var(--av-text);
  font-size: 15px;
  line-height: 1.35;
}

.anatomy-3d__inspector-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: end;
  justify-content: space-between;
}

.anatomy-3d__inspector-heading > small {
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__object-tree ul,
.anatomy-3d__tree-group {
  display: grid;
  gap: 6px;
}

.anatomy-3d__object-tree ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.anatomy-3d__tree-group {
  min-width: 0;
}

.anatomy-3d__tree-group header {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 2px 7px;
  align-items: center;
  border: 1px solid var(--av-border);
  border-radius: 6px;
  padding: 6px 7px;
  background: color-mix(in srgb, var(--av-surface) 70%, var(--av-surface-soft));
}

.anatomy-3d__folder-icon {
  position: relative;
  width: 14px;
  height: 11px;
  border: 1px solid color-mix(in srgb, var(--av-accent) 52%, var(--av-border));
  border-radius: 2px;
  background: color-mix(in srgb, var(--av-accent) 18%, var(--av-surface));
}

.anatomy-3d__folder-icon::before {
  position: absolute;
  top: -4px;
  left: 1px;
  width: 7px;
  height: 4px;
  border: inherit;
  border-bottom: 0;
  border-radius: 2px 2px 0 0;
  background: inherit;
  content: "";
}

.anatomy-3d__tree-group header strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__tree-group header small {
  grid-column: 2;
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 800;
  line-height: 1.35;
}

.anatomy-3d__import-card {
  display: grid;
  gap: 9px;
  border: 0;
  padding: 0;
  background: transparent;
}

.anatomy-3d__file-input {
  display: none;
}

.anatomy-3d__import-card header {
  display: grid;
  gap: 4px;
}

.anatomy-3d__import-card header span {
  color: var(--av-accent);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__import-card header strong {
  color: var(--av-text);
  font-size: 13px;
  line-height: 1.35;
}

.anatomy-3d__import-card header small {
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__import-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.anatomy-3d__import-actions button {
  flex: 1 1 108px;
  min-height: 36px;
  border: 1px solid var(--av-border);
  border-radius: 6px;
  padding: 7px 10px;
  background: var(--av-surface);
  color: var(--av-text);
  font: inherit;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.3;
  cursor: pointer;
}

.anatomy-3d__import-actions button:hover,
.anatomy-3d__import-actions button:focus-visible {
  border-color: var(--av-accent);
  color: var(--av-accent);
}

.anatomy-3d__import-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.anatomy-3d__job-status {
  margin: 0;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__modeling-checks {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.anatomy-3d__modeling-check-details,
.anatomy-3d__sidebar-section {
  border: 1px solid var(--av-border);
  border-radius: 7px;
  background: var(--av-surface-soft);
}

.anatomy-3d__modeling-check-details {
  padding: 7px;
}

.anatomy-3d__modeling-check-details summary,
.anatomy-3d__sidebar-section > summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  align-items: center;
  cursor: pointer;
  list-style: none;
}

.anatomy-3d__modeling-check-details summary::-webkit-details-marker,
.anatomy-3d__sidebar-section > summary::-webkit-details-marker {
  display: none;
}

.anatomy-3d__modeling-check-details summary::after,
.anatomy-3d__sidebar-section > summary::after {
  grid-row: 1 / span 2;
  grid-column: 2;
  content: "+";
  color: var(--av-accent);
  font-size: 16px;
  font-weight: 900;
  line-height: 1;
}

.anatomy-3d__modeling-check-details[open] summary::after,
.anatomy-3d__sidebar-section[open] > summary::after {
  content: "-";
}

.anatomy-3d__modeling-check-details summary strong,
.anatomy-3d__sidebar-section > summary strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__modeling-check-details summary small,
.anatomy-3d__sidebar-section > summary small {
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 800;
  line-height: 1.35;
}

.anatomy-3d__modeling-check-details[open] .anatomy-3d__modeling-checks,
.anatomy-3d__sidebar-section[open] .anatomy-3d__subject-hierarchy {
  margin-top: 8px;
}

.anatomy-3d__sidebar-section {
  padding: 9px;
}

.anatomy-3d__sidebar-section > summary span {
  grid-column: 1;
  color: var(--av-accent);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.25;
}

.anatomy-3d__sidebar-section > summary strong,
.anatomy-3d__sidebar-section > summary small {
  grid-column: 1;
}

.anatomy-3d__modeling-checks li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}

.anatomy-3d__modeling-checks span {
  border: 1px solid var(--av-border);
  border-radius: 999px;
  padding: 2px 6px;
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.25;
}

.anatomy-3d__modeling-checks p {
  margin: 0;
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__modeling-checks li.is-ready span {
  border-color: color-mix(in srgb, var(--av-green) 45%, var(--av-border));
  background: color-mix(in srgb, var(--av-green) 12%, var(--av-surface));
  color: var(--av-green);
}

.anatomy-3d__module-card {
  display: grid;
  gap: 7px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__module-card summary {
  display: grid;
  gap: 3px;
  cursor: pointer;
  list-style: none;
}

.anatomy-3d__module-card summary::-webkit-details-marker {
  display: none;
}

.anatomy-3d__module-card summary::after {
  content: "展开参数";
  justify-self: start;
  border: 1px solid var(--av-border);
  border-radius: 999px;
  padding: 2px 7px;
  color: var(--av-accent);
  font-size: 10px;
  font-weight: 900;
}

.anatomy-3d__module-card[open] summary {
  border-bottom: 1px solid var(--av-border);
  padding-bottom: 7px;
}

.anatomy-3d__module-card[open] summary::after {
  content: "收起参数";
}

.anatomy-3d__module-card summary strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__module-card summary small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.4;
}

.anatomy-3d__brp-params {
  display: grid;
  gap: 6px;
  border: 1px solid var(--av-border);
  border-radius: 6px;
  padding: 7px;
  background: color-mix(in srgb, var(--av-surface) 72%, var(--av-surface-soft));
}

.anatomy-3d__brp-params label {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 4px;
  min-width: 0;
}

.anatomy-3d__brp-params span {
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__brp-params select,
.anatomy-3d__brp-params input[type="range"] {
  width: 100%;
  min-width: 0;
}

.anatomy-3d__brp-params select {
  min-height: 30px;
  border: 1px solid var(--av-border-strong);
  border-radius: 5px;
  padding: 5px 7px;
  background: var(--av-surface);
  color: var(--av-text);
  font: inherit;
  font-size: 11px;
  font-weight: 850;
  line-height: 1.35;
}

.anatomy-3d__brp-params strong {
  justify-self: start;
  border: 1px solid var(--av-border);
  border-radius: 999px;
  padding: 2px 7px;
  background: var(--av-surface);
  color: var(--av-accent);
  font-size: 10px;
  line-height: 1.35;
}

.anatomy-3d__module-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 3px;
}

.anatomy-3d__module-row span,
.anatomy-3d__module-check span {
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
}

.anatomy-3d__module-row strong {
  min-height: 25px;
  border: 1px solid var(--av-border);
  border-radius: 5px;
  padding: 4px 7px;
  background: var(--av-surface);
  color: var(--av-text);
  font-size: 11px;
  line-height: 1.35;
}

.anatomy-3d__module-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 5px;
}

.anatomy-3d__module-actions button,
.anatomy-3d__module-update {
  display: grid;
  gap: 2px;
  width: 100%;
  min-height: 28px;
  border: 1px solid var(--av-border-strong);
  border-radius: 5px;
  padding: 5px 8px;
  background: var(--av-surface);
  color: var(--av-text);
  font: inherit;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
  text-align: center;
}

.anatomy-3d__module-actions button small {
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 800;
  line-height: 1.3;
}

.anatomy-3d__module-actions button.is-active {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 12%, var(--av-surface));
  color: var(--av-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--av-accent) 11%, transparent);
}

.anatomy-3d__module-check {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}

.anatomy-3d__module-check input {
  margin: 2px 0 0;
}

.anatomy-3d__module-update {
  border-color: color-mix(in srgb, var(--av-accent) 44%, var(--av-border));
  background: color-mix(in srgb, var(--av-accent) 9%, var(--av-surface));
  color: var(--av-accent);
  text-align: left;
}

.anatomy-3d__tree-item {
  display: grid;
  grid-template-columns: 16px 16px minmax(0, 1fr);
  gap: 6px 8px;
  align-items: start;
  width: 100%;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.anatomy-3d__tree-item.is-muted {
  background: color-mix(in srgb, var(--av-surface-soft) 82%, var(--av-surface) 18%);
}

.anatomy-3d__tree-item.is-active-node {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 9%, var(--av-surface-soft));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--av-accent) 18%, transparent) inset;
}

.anatomy-3d__tree-item:disabled {
  cursor: not-allowed;
  opacity: 0.64;
}

.anatomy-3d__visibility {
  width: 13px;
  height: 13px;
  margin-top: 2px;
  border: 2px solid var(--av-accent);
  border-radius: 50%;
  background: color-mix(in srgb, var(--av-accent) 18%, transparent);
}

.anatomy-3d__visibility::before {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: currentColor;
  opacity: 0.24;
  content: "";
}

.anatomy-3d__tree-item.is-muted .anatomy-3d__visibility {
  border-color: var(--av-text-muted);
  background: transparent;
}

.anatomy-3d__lock-state {
  display: inline-grid;
  place-items: center;
  width: 14px;
  min-height: 14px;
  border: 1px solid var(--av-border);
  border-radius: 3px;
  background: var(--av-surface);
  color: var(--av-text-muted);
  font-size: 9px;
  font-weight: 950;
  line-height: 1;
}

.anatomy-3d__tree-item:focus-visible,
.anatomy-3d__tool:focus-visible,
.anatomy-3d__view-controls button:focus-visible,
.anatomy-3d__viewport-label:focus-visible,
.anatomy-3d__markup-row:focus-visible,
.anatomy-3d__hotspot:focus-visible,
.anatomy-3d__layout-switcher button:focus-visible,
.anatomy-3d__brp-params select:focus-visible,
.anatomy-3d__module-actions button:focus-visible,
.anatomy-3d__module-update:focus-visible {
  outline: 2px solid var(--av-accent);
  outline-offset: 2px;
}

.anatomy-3d__tree-item strong {
  display: block;
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__tree-item small,
.anatomy-3d__tree-item em {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  font-style: normal;
  line-height: 1.4;
}

.anatomy-3d__tree-item em {
  grid-column: 3;
  justify-self: start;
  border: 1px solid var(--av-border);
  border-radius: 999px;
  padding: 2px 7px;
  background: var(--av-surface);
  color: var(--av-text-secondary);
}

.anatomy-3d__views {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.95fr);
  grid-template-areas:
    "three axial"
    "reconstruction reconstruction"
    "coronal sagittal";
  gap: 1px;
  background: var(--av-border);
}

.anatomy-3d__views.is-layout-threeD {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "three";
}

.anatomy-3d__views.is-layout-threeD .anatomy-3d__viewport {
  min-height: 760px;
}

.anatomy-3d__views.is-layout-threeD .anatomy-3d__slice-view,
.anatomy-3d__views.is-layout-threeD .anatomy-3d__reconstruction-view {
  display: none;
}

.anatomy-3d__views.is-layout-reconstruction {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "reconstruction";
}

.anatomy-3d__views.is-layout-reconstruction .anatomy-3d__viewport,
.anatomy-3d__views.is-layout-reconstruction .anatomy-3d__slice-view {
  display: none;
}

.anatomy-3d__views.is-layout-reconstruction .anatomy-3d__reconstruction-view {
  min-height: 540px;
}

.anatomy-3d__viewport {
  grid-area: three;
  position: relative;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  align-content: stretch;
  gap: 8px;
  min-height: 520px;
  padding: 10px;
  overflow: hidden;
  scroll-margin-top: 84px;
  background:
    linear-gradient(rgba(109, 145, 171, 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(109, 145, 171, 0.16) 1px, transparent 1px),
    radial-gradient(circle at 50% 45%, rgba(44, 126, 192, 0.24), transparent 36%),
    #101923;
  background-size: 32px 32px, 32px 32px, auto, auto;
}

.anatomy-3d__viewport::before,
.anatomy-3d__viewport::after {
  display: none;
}

.anatomy-3d__viewport :deep(canvas) {
  position: absolute;
  z-index: 1;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  min-height: 100%;
  touch-action: none;
}

.anatomy-3d__view-title,
.anatomy-3d__legend,
.anatomy-3d__metrics {
  position: relative;
  z-index: 2;
  border: 1px solid rgba(216, 229, 242, 0.28);
  border-radius: 7px;
  background: rgba(9, 18, 28, 0.74);
  color: #f2fbff;
  backdrop-filter: blur(10px);
}

.anatomy-3d__view-title {
  grid-row: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
  padding: 8px 10px;
}

.anatomy-3d__view-title > div {
  display: grid;
  gap: 3px;
  min-width: min(100%, 180px);
}

.anatomy-3d__view-title span,
.anatomy-3d__view-badge span {
  color: #9edcff;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.3;
}

.anatomy-3d__view-title strong,
.anatomy-3d__view-badge strong {
  color: #ffffff;
  font-size: 14px;
  line-height: 1.35;
}

.anatomy-3d__view-title small,
.anatomy-3d__view-badge small {
  color: #c5d9e6;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__view-badge {
  justify-items: end;
  text-align: right;
}

.anatomy-3d__viewport-toolbar {
  position: relative;
  z-index: 2;
  grid-row: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
  pointer-events: none;
}

.anatomy-3d__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  flex: 0 1 auto;
  max-width: min(100%, 520px);
  padding: 7px 9px;
  pointer-events: auto;
}

.anatomy-3d__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #e8f5fb;
  font-size: 12px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__legend i {
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.anatomy-3d__legend .projection {
  background: #8fb1bd;
}

.anatomy-3d__legend .plane {
  background: #f2c14e;
}

.anatomy-3d__legend .reference {
  background: #2c7ec0;
}

.anatomy-3d__view-controls {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 0 1 auto;
  justify-content: flex-end;
  max-width: min(100%, 420px);
  border: 1px solid rgba(216, 229, 242, 0.28);
  border-radius: 7px;
  padding: 6px 7px;
  background: rgba(9, 18, 28, 0.74);
  backdrop-filter: blur(10px);
  pointer-events: auto;
}

.anatomy-3d__view-controls button {
  min-height: 26px;
  border: 1px solid rgba(158, 220, 255, 0.35);
  border-radius: 5px;
  padding: 4px 8px;
  background: rgba(158, 220, 255, 0.08);
  color: #e8f5fb;
  font: inherit;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
  cursor: pointer;
}

.anatomy-3d__view-controls button.is-active {
  border-color: rgba(242, 193, 78, 0.62);
  background: rgba(242, 193, 78, 0.18);
  color: #ffe7ad;
}

.anatomy-3d__view-controls button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.anatomy-3d__viewport-label-layer {
  position: absolute;
  z-index: 3;
  inset: 76px 18px 104px;
  pointer-events: none;
}

.anatomy-3d__viewport-label {
  position: absolute;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 1px 6px;
  min-width: 118px;
  max-width: min(240px, 48%);
  border: 1px solid rgba(216, 229, 242, 0.34);
  border-radius: 6px;
  padding: 5px 7px;
  background: rgba(9, 18, 28, 0.78);
  color: #f2fbff;
  font: inherit;
  text-align: left;
  pointer-events: auto;
  backdrop-filter: blur(8px);
  transform: translate(-50%, -50%);
}

.anatomy-3d__viewport-label span {
  grid-row: span 2;
  display: inline-grid;
  place-items: center;
  width: 22px;
  min-height: 22px;
  border: 1px solid currentColor;
  border-radius: 50%;
  color: #9edcff;
  font-size: 10px;
  font-weight: 950;
  line-height: 1;
}

.anatomy-3d__viewport-label strong,
.anatomy-3d__viewport-label small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.anatomy-3d__viewport-label strong {
  color: #ffffff;
  font-size: 11px;
  line-height: 1.25;
}

.anatomy-3d__viewport-label small {
  grid-column: 2;
  color: #c5d9e6;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.25;
}

.anatomy-3d__viewport-label.is-plane span {
  color: #f2c14e;
}

.anatomy-3d__viewport-label.is-hotspot span {
  color: #e0985a;
}

.anatomy-3d__viewport-label.is-markup span {
  color: #49b988;
}

.anatomy-3d__viewport-label.is-selected {
  border-color: #f2c14e;
  box-shadow: 0 0 0 2px rgba(242, 193, 78, 0.16);
}

.anatomy-3d__viewport-label.is-muted {
  opacity: 0.74;
}

.anatomy-3d__metrics {
  grid-row: 4;
  align-self: end;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  width: min(100%, 620px);
  padding: 9px 10px;
}

.anatomy-3d__metrics dt,
.anatomy-3d__metrics dd,
.anatomy-3d__evidence-grid dt,
.anatomy-3d__evidence-grid dd {
  margin: 0;
}

.anatomy-3d__metrics dt {
  color: #9edcff;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__metrics dd {
  color: #ffffff;
  font-size: 13px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__slice-view {
  display: grid;
  gap: 8px;
  min-height: 178px;
  padding: 10px;
  background: #111b25;
  color: #edf7ff;
}

.anatomy-3d__slice-view.is-axial {
  grid-area: axial;
}

.anatomy-3d__slice-view.is-coronal {
  grid-area: coronal;
}

.anatomy-3d__slice-view.is-sagittal {
  grid-area: sagittal;
}

.anatomy-3d__slice-view.is-axial {
  border-top: 3px solid #e1493f;
}

.anatomy-3d__slice-view.is-coronal {
  border-top: 3px solid #46a85e;
}

.anatomy-3d__slice-view.is-sagittal {
  border-top: 3px solid #e0b43d;
}

.anatomy-3d__slice-view header {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 7px;
}

.anatomy-3d__slice-view header span,
.anatomy-3d__slice-view header strong {
  display: block;
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__slice-view header span {
  color: #9edcff;
  font-weight: 900;
}

.anatomy-3d__slice-view header strong {
  color: #edf7ff;
  font-weight: 900;
}

.anatomy-3d__slice-controls {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) 26px;
  gap: 6px;
  align-items: center;
}

.anatomy-3d__slice-controls button {
  display: grid;
  place-items: center;
  min-width: 0;
  min-height: 24px;
  border: 1px solid rgba(158, 220, 255, 0.35);
  border-radius: 5px;
  background: rgba(158, 220, 255, 0.08);
  color: #dff5ff;
  font: inherit;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}

.anatomy-3d__slice-controls input {
  width: 100%;
  min-width: 0;
  accent-color: #9edcff;
}

.anatomy-3d__slice-canvas {
  position: relative;
  --slice-crosshair: 50%;
  --slice-roi-shift: 0%;
  min-height: 94px;
  overflow: hidden;
  border: 1px solid rgba(216, 229, 242, 0.22);
  border-radius: 6px;
  background:
    linear-gradient(rgba(181, 207, 224, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(181, 207, 224, 0.12) 1px, transparent 1px),
    radial-gradient(ellipse at 48% 52%, rgba(213, 225, 232, 0.18), transparent 42%),
    #0b121a;
  background-size: 18px 18px, 18px 18px, auto, auto;
}

.anatomy-3d__crosshair {
  position: absolute;
  display: block;
  background: rgba(126, 188, 228, 0.72);
}

.anatomy-3d__crosshair--x {
  top: var(--slice-crosshair);
  right: 0;
  left: 0;
  height: 1px;
}

.anatomy-3d__crosshair--y {
  top: 0;
  bottom: 0;
  left: var(--slice-crosshair);
  width: 1px;
}

.anatomy-3d__bone-contour,
.anatomy-3d__roi-contour {
  position: absolute;
  display: block;
  border-radius: 50%;
}

.anatomy-3d__bone-contour {
  inset: 22% 21%;
  border: 2px solid rgba(218, 201, 176, 0.78);
  transform: rotate(-12deg);
}

.anatomy-3d__roi-contour {
  right: 29%;
  bottom: 26%;
  width: 28%;
  height: 25%;
  border: 2px solid rgba(242, 193, 78, 0.82);
  background: rgba(242, 193, 78, 0.12);
  transform: translateX(var(--slice-roi-shift));
}

.anatomy-3d__slice-view p {
  margin: 0;
  color: #c5d9e6;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__reconstruction-view {
  grid-area: reconstruction;
  display: grid;
  gap: 10px;
  min-height: 286px;
  padding: 10px;
  background: #68709d;
  color: #f5fbff;
}

.anatomy-3d__reconstruction-view header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
  align-items: start;
}

.anatomy-3d__reconstruction-view header div {
  display: grid;
  gap: 3px;
}

.anatomy-3d__reconstruction-view header span,
.anatomy-3d__reconstruction-view header small {
  color: #edf2ff;
  font-size: 12px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__reconstruction-view header strong {
  color: #ffffff;
  font-size: 14px;
  line-height: 1.35;
}

.anatomy-3d__reconstruction-view p {
  margin: 0;
  color: #eef4ff;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__evidence-summary,
.anatomy-3d__evidence-grid {
  display: grid;
  gap: 7px;
  margin: 0;
}

.anatomy-3d__evidence-summary {
  grid-template-columns: minmax(0, 1fr);
  gap: 0;
  border-top: 1px solid var(--av-border);
}

.anatomy-3d__evidence-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 8px;
}

.anatomy-3d__evidence-summary div,
.anatomy-3d__evidence-grid div {
  display: grid;
  gap: 3px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__evidence-summary div {
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: start;
  align-content: start;
  min-height: 0;
  border: 0;
  border-bottom: 1px solid var(--av-border);
  border-radius: 0;
  padding: 9px 0;
  background: transparent;
}

.anatomy-3d__evidence-summary dt,
.anatomy-3d__evidence-grid dt {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__evidence-summary dd,
.anatomy-3d__evidence-grid dd {
  color: var(--av-text);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.4;
}

.anatomy-3d__body.is-model-empty .anatomy-3d__evidence-summary div:nth-child(n + 4) {
  display: none;
}

.anatomy-3d__evidence-drawer,
.anatomy-3d__registration-guard {
  display: grid;
  gap: 8px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 9px;
  background: var(--av-surface-soft);
}

.anatomy-3d__technical-evidence {
  order: 4;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  background: var(--av-surface-soft);
}

.anatomy-3d__technical-evidence > summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 3px 10px;
  align-items: center;
  padding: 11px 12px;
  cursor: pointer;
  list-style: none;
}

.anatomy-3d__technical-evidence > summary::-webkit-details-marker {
  display: none;
}

.anatomy-3d__technical-evidence > summary::after {
  grid-row: 1 / span 2;
  grid-column: 2;
  color: var(--av-accent);
  font-size: 16px;
  font-weight: 900;
  content: "+";
}

.anatomy-3d__technical-evidence[open] > summary {
  border-bottom: 1px solid var(--av-border);
}

.anatomy-3d__technical-evidence[open] > summary::after {
  content: "-";
}

.anatomy-3d__technical-evidence > summary strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__technical-evidence > summary small {
  grid-column: 1;
  color: var(--av-text-muted);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
}

.anatomy-3d__technical-evidence-content {
  display: grid;
  gap: 0;
  padding: 0 12px 10px;
}

.anatomy-3d__technical-evidence-content > details {
  border: 0;
  border-bottom: 1px solid var(--av-border);
  border-radius: 0;
  padding: 10px 0;
  background: transparent;
}

.anatomy-3d__technical-evidence-content > details:last-child {
  border-bottom: 0;
}

.anatomy-3d__evidence-drawer summary,
.anatomy-3d__registration-guard summary,
.anatomy-3d__markups summary,
.anatomy-3d__transform-chain summary {
  display: grid;
  gap: 3px;
  cursor: pointer;
  list-style: none;
}

.anatomy-3d__evidence-drawer summary::-webkit-details-marker,
.anatomy-3d__registration-guard summary::-webkit-details-marker,
.anatomy-3d__markups summary::-webkit-details-marker,
.anatomy-3d__transform-chain summary::-webkit-details-marker {
  display: none;
}

.anatomy-3d__evidence-drawer summary strong,
.anatomy-3d__registration-guard summary strong,
.anatomy-3d__markups summary strong,
.anatomy-3d__transform-chain summary strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__evidence-drawer summary small,
.anatomy-3d__registration-guard summary small,
.anatomy-3d__markups summary small,
.anatomy-3d__transform-chain summary small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
}

.anatomy-3d__registration-guard ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.anatomy-3d__registration-guard li {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 7px;
  align-items: start;
  min-width: 0;
}

.anatomy-3d__registration-guard span {
  border: 1px solid color-mix(in srgb, var(--av-red) 38%, var(--av-border));
  border-radius: 999px;
  padding: 2px 5px;
  background: color-mix(in srgb, var(--av-red) 8%, var(--av-surface));
  color: var(--av-red);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.35;
  text-align: center;
}

.anatomy-3d__registration-guard li.is-ready span {
  border-color: color-mix(in srgb, var(--av-green) 44%, var(--av-border));
  background: color-mix(in srgb, var(--av-green) 10%, var(--av-surface));
  color: var(--av-green);
}

.anatomy-3d__registration-guard p {
  margin: 0;
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__markups,
.anatomy-3d__transform-chain {
  display: grid;
  gap: 8px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 9px;
  background: var(--av-surface-soft);
}

.anatomy-3d__markup-table,
.anatomy-3d__transform-chain ol {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.anatomy-3d__markup-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) minmax(54px, auto);
  gap: 3px 8px;
  align-items: start;
  width: 100%;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 7px;
  background: var(--av-surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.anatomy-3d__markup-row span {
  grid-row: span 3;
  display: grid;
  place-items: center;
  min-height: 28px;
  border-radius: 6px;
  background: var(--av-text-muted);
  color: var(--ov-bg-elevated);
  font-size: 11px;
  font-weight: 900;
}

.anatomy-3d__markup-row.is-ready span {
  background: var(--av-green);
}

.anatomy-3d__markup-row strong,
.anatomy-3d__markup-row small,
.anatomy-3d__markup-row em,
.anatomy-3d__markup-row b {
  min-width: 0;
  line-height: 1.35;
}

.anatomy-3d__markup-row strong {
  color: var(--av-text);
  font-size: 12px;
}

.anatomy-3d__markup-row small {
  grid-column: 2;
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
}

.anatomy-3d__markup-row em {
  grid-column: 2;
  color: var(--av-text-secondary);
  font-size: 11px;
  font-style: normal;
  font-weight: 850;
}

.anatomy-3d__markup-row b {
  grid-row: 1 / span 3;
  grid-column: 3;
  justify-self: end;
  border: 1px solid color-mix(in srgb, var(--av-red) 38%, var(--av-border));
  border-radius: 999px;
  padding: 2px 6px;
  background: color-mix(in srgb, var(--av-red) 8%, var(--av-surface));
  color: var(--av-red);
  font-size: 10px;
  font-weight: 900;
  text-align: center;
}

.anatomy-3d__markup-row.is-ready b {
  border-color: color-mix(in srgb, var(--av-green) 44%, var(--av-border));
  background: color-mix(in srgb, var(--av-green) 10%, var(--av-surface));
  color: var(--av-green);
}

.anatomy-3d__markup-row.is-selected {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 10%, var(--av-surface));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--av-accent) 14%, transparent);
}

.anatomy-3d__markup-row:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.anatomy-3d__markup-empty {
  margin: 0;
  border: 1px dashed var(--av-border-strong);
  border-radius: 6px;
  padding: 10px;
  background: var(--av-surface);
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.5;
}

.anatomy-3d__transform-chain ol {
  margin: 0;
  padding: 0;
  list-style: none;
}

.anatomy-3d__transform-chain li {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 7px;
  align-items: start;
  min-width: 0;
}

.anatomy-3d__transform-chain li > span {
  border: 1px solid color-mix(in srgb, var(--av-red) 38%, var(--av-border));
  border-radius: 999px;
  padding: 2px 5px;
  background: color-mix(in srgb, var(--av-red) 8%, var(--av-surface));
  color: var(--av-red);
  font-size: 10px;
  font-weight: 900;
  line-height: 1.35;
  text-align: center;
}

.anatomy-3d__transform-chain li.is-ready > span {
  border-color: color-mix(in srgb, var(--av-green) 44%, var(--av-border));
  background: color-mix(in srgb, var(--av-green) 10%, var(--av-surface));
  color: var(--av-green);
}

.anatomy-3d__transform-chain li div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.anatomy-3d__transform-chain strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__transform-chain small,
.anatomy-3d__transform-chain em {
  color: var(--av-text-muted);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 1.35;
}

.anatomy-3d__workflow {
  display: grid;
  gap: 7px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__workflow summary,
.anatomy-3d__boundary summary {
  display: grid;
  gap: 2px;
  cursor: pointer;
  color: var(--av-text);
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__workflow summary small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
}

.anatomy-3d__workflow div {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 3px 8px;
  align-items: start;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__workflow span {
  grid-row: span 2;
  display: grid;
  place-items: center;
  min-width: 30px;
  min-height: 30px;
  border: 1px solid color-mix(in srgb, var(--av-accent) 42%, var(--av-border));
  border-radius: 6px;
  background: color-mix(in srgb, var(--av-accent) 10%, var(--av-surface));
  color: var(--av-accent);
  font-size: 11px;
  font-weight: 900;
}

.anatomy-3d__workflow strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__workflow small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__boundary,
.anatomy-3d__empty {
  margin: 0;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 9px 10px;
  background: var(--av-surface-soft);
  color: var(--av-text-secondary);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.5;
}

.anatomy-3d__boundary p {
  margin: 8px 0 0;
  color: var(--av-text-secondary);
  overflow-wrap: anywhere;
}

.anatomy-3d__hotspot-list {
  display: grid;
  order: 3;
  gap: 8px;
}

.anatomy-3d__hotspot-list-heading {
  display: flex;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--av-border);
}

.anatomy-3d__hotspot-list-heading span {
  color: var(--av-accent);
  font-size: 10px;
  font-weight: 800;
}

.anatomy-3d__hotspot-list-heading strong {
  color: var(--av-text);
  font-size: 12px;
}

.anatomy-3d__hotspot {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 4px 9px;
  width: 100%;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 9px;
  background: var(--av-surface-soft);
  color: var(--av-text);
  text-align: left;
  cursor: pointer;
}

.anatomy-3d__hotspot span {
  grid-row: span 2;
  display: grid;
  place-items: center;
  width: 30px;
  min-height: 30px;
  border-radius: 6px;
  color: var(--ov-text-on-primary);
  font-size: 12px;
  font-weight: 900;
}

.anatomy-3d__hotspot strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__hotspot small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__hotspot.is-high span {
  background: var(--av-red);
}

.anatomy-3d__hotspot.is-medium span {
  background: var(--av-amber);
}

.anatomy-3d__hotspot.is-low span {
  background: var(--av-green);
}

.anatomy-3d__hotspot.is-reference-projection span {
  background: var(--ov-text-muted);
}

.anatomy-3d__hotspot.selected {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 10%, var(--av-surface));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--av-accent) 14%, transparent);
}

.anatomy-3d__inspector > .anatomy-3d__empty {
  order: 3;
}

.anatomy-3d__disclaimer {
  margin: 0;
  border-top: 1px solid var(--av-border);
  padding: 11px 16px;
  background: var(--av-surface-soft);
  color: var(--av-text-secondary);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.55;
}

.anatomy-3d__views {
  display: contents;
}

.anatomy-3d__views .anatomy-3d__viewport {
  grid-area: viewport;
  height: var(--av-workbench-height);
  min-height: 660px;
}

.anatomy-3d__model-check-panel {
  grid-area: check;
  display: block;
  min-height: 0;
  min-width: 0;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 0;
  background: var(--av-surface-panel);
  color: var(--av-text);
}

.anatomy-3d__model-check-details > summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  list-style: none;
}

.anatomy-3d__model-check-details > summary::-webkit-details-marker {
  display: none;
}

.anatomy-3d__model-check-details > summary::after {
  color: var(--av-accent);
  font-size: 12px;
  font-weight: 900;
  content: "展开检查";
}

.anatomy-3d__model-check-details[open] > summary {
  border-bottom: 1px solid var(--av-border);
}

.anatomy-3d__model-check-details[open] > summary::after {
  content: "收起检查";
}

.anatomy-3d__model-check-details > summary div {
  display: grid;
  gap: 2px;
}

.anatomy-3d__model-check-details > summary span,
.anatomy-3d__model-check-details > summary small {
  color: var(--av-accent);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
}

.anatomy-3d__model-check-details > summary strong {
  color: var(--av-text);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}

.anatomy-3d__model-check-content {
  display: grid;
  gap: 10px;
  padding: 12px 14px 14px;
}

.anatomy-3d__model-check-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.anatomy-3d__model-check-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 4px 7px;
  align-items: start;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 7px;
  background: var(--av-surface);
}

.anatomy-3d__model-check-list span {
  grid-row: span 2;
  border-radius: 999px;
  padding: 2px 6px;
  background: var(--ov-bg-warning);
  color: var(--av-amber);
  font-size: 10px;
  font-weight: 950;
  line-height: 1.25;
}

.anatomy-3d__model-check-list li.is-ready span {
  background: var(--ov-bg-success);
  color: var(--av-green);
}

.anatomy-3d__model-check-list strong,
.anatomy-3d__model-check-list small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.anatomy-3d__model-check-list strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__model-check-list small {
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.4;
}

.anatomy-3d__model-check-panel dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.anatomy-3d__model-check-panel dl div {
  display: grid;
  gap: 3px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface);
}

.anatomy-3d__model-check-panel dt,
.anatomy-3d__model-check-panel dd,
.anatomy-3d__model-check-panel p {
  margin: 0;
  overflow-wrap: anywhere;
}

.anatomy-3d__model-check-panel dt {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__model-check-panel dd {
  color: var(--av-text);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.4;
}

.anatomy-3d__model-check-panel p {
  border: 1px solid color-mix(in srgb, var(--av-amber) 34%, var(--av-border));
  border-radius: 7px;
  padding: 9px;
  background: var(--ov-bg-warning);
  color: var(--av-amber);
  font-size: 12px;
  font-weight: 850;
  line-height: 1.5;
}

.anatomy-3d__viewport.is-model-empty {
  background: var(--av-surface-panel);
}

.anatomy-3d__body.is-model-empty {
  --av-side-row-height: clamp(248px, 27vh, 298px);
}

.anatomy-3d__viewport.is-model-empty :deep(canvas) {
  pointer-events: none;
  opacity: 0;
}

.anatomy-3d__viewport.is-model-empty .anatomy-3d__view-title,
.anatomy-3d__viewport.is-model-empty .anatomy-3d__legend,
.anatomy-3d__viewport.is-model-empty .anatomy-3d__metrics,
.anatomy-3d__viewport.is-model-empty .anatomy-3d__view-controls {
  border-color: var(--av-border);
  background: var(--av-surface);
  color: var(--av-text);
  box-shadow: none;
  backdrop-filter: none;
}

.anatomy-3d__viewport.is-model-empty :is(
    .anatomy-3d__view-title span,
    .anatomy-3d__view-badge span,
    .anatomy-3d__metrics dt
  ) {
  color: var(--av-accent);
}

.anatomy-3d__viewport.is-model-empty :is(
    .anatomy-3d__view-title strong,
    .anatomy-3d__view-badge strong,
    .anatomy-3d__metrics dd
  ) {
  color: var(--av-text);
}

.anatomy-3d__viewport.is-model-empty :is(
    .anatomy-3d__view-title small,
    .anatomy-3d__view-badge small,
    .anatomy-3d__legend span
  ) {
  color: var(--av-text-secondary);
}

.anatomy-3d__viewport.is-model-empty .anatomy-3d__view-controls button {
  border-color: var(--av-border-strong);
  background: var(--av-surface-soft);
  color: var(--av-text-secondary);
}

.anatomy-3d__viewport.is-model-empty .anatomy-3d__view-controls button.is-active {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 10%, var(--av-surface));
  color: var(--av-accent);
}

.anatomy-3d__empty-viewport {
  position: relative;
  z-index: 3;
  grid-row: 3;
  align-self: center;
  justify-self: center;
  display: grid;
  gap: 8px;
  width: min(460px, calc(100% - 40px));
  border: 1px dashed var(--av-border-strong);
  border-radius: 8px;
  padding: 24px;
  background: var(--av-surface);
  color: var(--av-text);
  box-shadow: var(--ov-shadow);
  text-align: center;
}

.anatomy-3d__selection-feedback {
  position: absolute;
  z-index: 5;
  top: 122px;
  left: 50%;
  display: grid;
  gap: 2px;
  width: min(460px, calc(100% - 40px));
  border: 1px solid color-mix(in srgb, var(--av-accent) 42%, var(--av-border));
  border-radius: 7px;
  padding: 9px 12px;
  background: color-mix(in srgb, var(--av-surface) 92%, var(--av-accent) 8%);
  color: var(--av-text);
  text-align: center;
  box-shadow: var(--ov-shadow);
  transform: translateX(-50%);
  pointer-events: none;
}

.anatomy-3d__selection-feedback strong {
  color: var(--av-accent);
  font-size: 12px;
}

.anatomy-3d__selection-feedback span {
  color: var(--av-text-secondary);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.4;
}

.anatomy-3d__empty-viewport strong,
.anatomy-3d__empty-viewport p,
.anatomy-3d__empty-viewport small {
  margin: 0;
  overflow-wrap: anywhere;
}

.anatomy-3d__empty-viewport strong {
  font-size: 16px;
  line-height: 1.35;
}

.anatomy-3d__empty-viewport p {
  color: var(--av-text-secondary);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.55;
}

.anatomy-3d__empty-viewport small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.45;
}

.anatomy-3d__empty-viewport .anatomy-3d__empty-hotspot-summary {
  border-top: 1px solid var(--av-border);
  padding-top: 8px;
  color: var(--av-accent);
}

.anatomy-3d__empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.anatomy-3d__empty-actions button {
  min-height: 30px;
  border: 1px solid var(--av-border-strong);
  border-radius: 5px;
  padding: 5px 10px;
  background: var(--av-surface-soft);
  color: var(--av-text);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  line-height: 1.35;
  cursor: pointer;
}

.anatomy-3d__empty-actions button:hover,
.anatomy-3d__empty-actions button:focus-visible {
  border-color: var(--av-accent);
  color: var(--av-accent);
}

.anatomy-3d__empty-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.anatomy-3d__subject-hierarchy {
  max-height: 430px;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-gutter: stable;
}

.anatomy-3d__views.is-layout-reconstruction,
.anatomy-3d__views.is-layout-threeD {
  display: contents;
}

.anatomy-3d__views.is-layout-threeD .anatomy-3d__viewport {
  height: var(--av-workbench-height);
  min-height: 660px;
}

.anatomy-3d__body.is-focus-view {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas:
    "viewport"
    "check";
  grid-template-rows: auto auto;
}

.anatomy-3d__body.is-focus-view .anatomy-3d__object-tree,
.anatomy-3d__body.is-focus-view .anatomy-3d__inspector {
  display: none;
}

.anatomy-3d__body.is-focus-view .anatomy-3d__views .anatomy-3d__viewport {
  height: min(82vh, 940px);
  min-height: 720px;
}

.anatomy-3d__body.is-model-empty .anatomy-3d__object-tree,
.anatomy-3d__body.is-model-empty .anatomy-3d__inspector,
.anatomy-3d__body.is-model-empty .anatomy-3d__views .anatomy-3d__viewport,
.anatomy-3d__body.is-focus-view.is-model-empty .anatomy-3d__views .anatomy-3d__viewport {
  min-height: 0;
}

.anatomy-3d__body.is-model-empty .anatomy-3d__views .anatomy-3d__viewport,
.anatomy-3d__body.is-focus-view.is-model-empty .anatomy-3d__views .anatomy-3d__viewport {
  height: var(--av-empty-workbench-height);
  min-height: 520px;
  max-height: var(--av-empty-workbench-height);
}

@media (max-width: 1320px) {
  .anatomy-3d {
    --av-workbench-height: clamp(620px, 68vh, 760px);
  }

  .anatomy-3d__body {
    grid-template-columns: minmax(560px, 1fr) minmax(280px, 320px);
    grid-template-areas:
      "viewport tree"
      "viewport inspector"
      "check check";
  }

  .anatomy-3d__inspector {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 980px) {
  .anatomy-3d__header {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__status {
    justify-items: start;
  }

  .anatomy-3d__status strong,
  .anatomy-3d__status small {
    text-align: left;
  }

  .anatomy-3d__toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .anatomy-3d__workflow-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .anatomy-3d__body {
    grid-template-columns: 1fr;
    grid-template-areas:
      "tree"
      "viewport"
      "inspector"
      "check";
    grid-template-rows: auto;
  }

  .anatomy-3d__object-tree,
  .anatomy-3d__inspector {
    height: auto;
    max-height: none;
    align-self: stretch;
    overflow: visible;
  }

  .anatomy-3d__object-tree {
    grid-area: tree;
  }

  .anatomy-3d__inspector {
    grid-area: inspector;
  }

  .anatomy-3d__inspector {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__views {
    grid-template-columns: 1fr;
    grid-template-areas:
      "three"
      "check";
  }

  .anatomy-3d__viewport {
    min-height: 620px;
  }
}

@media (max-width: 560px) {
  .anatomy-3d__header,
  .anatomy-3d__object-tree,
  .anatomy-3d__inspector,
  .anatomy-3d__viewport,
  .anatomy-3d__slice-view {
    padding: 10px;
  }

  .anatomy-3d__toolbar {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__workflow-strip,
  .anatomy-3d__workflow-strip .anatomy-3d__layout-switcher {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__viewport {
    min-height: 620px;
  }

  .anatomy-3d__view-title {
    display: grid;
  }

  .anatomy-3d__view-badge {
    justify-items: start;
    text-align: left;
  }

  .anatomy-3d__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
