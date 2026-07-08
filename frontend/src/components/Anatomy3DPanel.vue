<template>
  <section class="anatomy-3d" aria-label="Slicer 风格 CBCT/STL 三维证据工作台">
    <header class="anatomy-3d__header">
      <div class="anatomy-3d__titleblock">
        <span>Slicer-style planning workspace</span>
        <h2>CBCT/STL 三维证据工作台</h2>
        <p>复刻 3D Slicer 四视图、对象树和截骨规划语义；本项目仅接入脱敏模型、ICG 候选区和医生复核边界。</p>
      </div>
      <div class="anatomy-3d__status" :class="statusClass">
        <strong>{{ riskSummary.label }}</strong>
        <small>{{ registrationLabel }}</small>
      </div>
    </header>

    <nav class="anatomy-3d__slicer-menubar" aria-label="Slicer 顶部菜单复刻">
      <span>File</span>
      <span>Edit</span>
      <span>View</span>
      <span>Help</span>
      <label>
        Modules:
        <strong>BoneReconstructionPlanner</strong>
      </label>
      <div class="anatomy-3d__layout-switcher" aria-label="视图布局切换">
        <button
          v-for="layout in viewLayoutOptions"
          :key="layout.key"
          type="button"
          :class="{ 'is-active': viewLayoutMode === layout.key }"
          @click="viewLayoutMode = layout.key"
        >
          {{ layout.label }}
        </button>
      </div>
      <em>{{ isRegistered ? "Research registration reference" : "Navigation guard: OFF" }}</em>
    </nav>

    <nav class="anatomy-3d__toolbar" aria-label="三维规划工具栏">
      <button
        v-for="item in toolbarItems"
        :key="item.key"
        type="button"
        class="anatomy-3d__tool"
        :class="{ 'is-active': activeWorkspaceTool === item.key }"
        @click="activeWorkspaceTool = item.key"
      >
        <strong>{{ item.label }}</strong>
        <small>{{ item.note }}</small>
      </button>
    </nav>

    <div class="anatomy-3d__body">
      <aside class="anatomy-3d__object-tree" aria-label="对象列表">
        <div class="anatomy-3d__panel-title">
          <span>3D Slicer 5.8.1</span>
          <strong>BoneReconstructionPlanner 模块</strong>
        </div>
        <div class="anatomy-3d__module-card" aria-label="Mandible Reconstruction Planning">
          <header>
            <strong>Mandible Reconstruction Planning</strong>
            <small>非导航锁定：医生复核后才允许进入真实空间解释。</small>
          </header>
          <div class="anatomy-3d__brp-params" aria-label="BRP 规划参数">
            <label>
              <span>Mandibulectomy mode</span>
              <select v-model="mandibulectomyMode">
                <option value="Segmental Mandibulectomy">Segmental Mandibulectomy</option>
                <option value="Hemimandibulectomy">Hemimandibulectomy</option>
              </select>
            </label>
            <label class="anatomy-3d__module-check">
              <input v-model="rightSideLeg" type="checkbox" />
              <span>Right side leg: fibula X axis kept medial</span>
            </label>
            <label>
              <span>Between space (mm)</span>
              <input v-model.number="betweenSpaceMm" type="range" min="0" max="5" step="0.5" />
              <strong>{{ betweenSpaceLabel }}</strong>
            </label>
            <label>
              <span>Security margin of fibula pieces (mm)</span>
              <input v-model.number="securityMarginMm" type="range" min="0" max="8" step="0.5" />
              <strong>{{ securityMarginLabel }}</strong>
            </label>
            <label>
              <span>Bigger miter box distance to fibula (mm)</span>
              <input v-model.number="miterBoxDistanceMm" type="range" min="8" max="36" step="1" />
              <strong>{{ miterBoxDistanceLabel }}</strong>
            </label>
          </div>
          <label v-for="control in moduleControls" :key="control.label" class="anatomy-3d__module-row">
            <span>{{ control.label }}</span>
            <strong>{{ control.value }}</strong>
          </label>
          <div class="anatomy-3d__module-actions">
            <button
              v-for="action in moduleActions"
              :key="action.key"
              type="button"
              :class="{ 'is-active': activeModuleAction === action.key }"
              @click="selectModuleAction(action.key)"
            >
              <strong>{{ action.label }}</strong>
              <small>{{ action.state }}</small>
            </button>
          </div>
          <label class="anatomy-3d__module-check">
            <input v-model="autoPositionPlanes" type="checkbox" />
            <span>Automatic mandibular planes positioning for maximum bones contact area</span>
          </label>
          <label class="anatomy-3d__module-check">
            <input v-model="rotatePlanesTogether" type="checkbox" />
            <span>Make all mandible planes rotate together</span>
          </label>
          <label class="anatomy-3d__module-check">
            <input :checked="objectVisibility.mandible" type="checkbox" @change="toggleObjectVisibility('mandible')" />
            <span>Show original mandible model</span>
          </label>
          <label class="anatomy-3d__module-check">
            <input v-model="showFibulaSegmentLengths" type="checkbox" />
            <span>Show fibula segments lengths</span>
          </label>
          <button class="anatomy-3d__module-update" type="button" @click="selectModuleAction('updateFibulaPlanes')">
            Update fibula planes over fibula line; update fibula bone pieces and transform them to mandible
          </button>
        </div>
        <div class="anatomy-3d__panel-title">
          <span>Data / Models / Node</span>
          <strong>对象列表</strong>
        </div>
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
              @click="activateTreeNode(item)"
            >
              <span
                class="anatomy-3d__visibility"
                :class="{ 'is-visible': !item.muted }"
                aria-hidden="true"
              ></span>
              <span class="anatomy-3d__lock-state" aria-hidden="true">{{ item.locked ? "L" : "U" }}</span>
              <div>
                <strong>{{ item.name }}</strong>
                <small>{{ item.detail }}</small>
              </div>
              <em>{{ item.state }}</em>
            </button>
          </li>
        </ul>
      </aside>

      <main class="anatomy-3d__views" :class="[`is-tool-${activeWorkspaceTool}`, `is-layout-${viewLayoutMode}`]" aria-label="四视图规划区">
        <section
          ref="canvasHost"
          class="anatomy-3d__viewport"
          aria-label="三维规划视图"
          @dblclick="toggleThreeDMaximize"
        >
          <div class="anatomy-3d__view-title">
            <div>
              <span>3D</span>
              <strong>{{ modelSourceLabel }}</strong>
              <small>{{ modelLoadNote }}</small>
              <small>Active tool: {{ activeModuleActionLabel }}</small>
              <small>Layout: {{ viewLayoutLabel }}</small>
            </div>
            <div class="anatomy-3d__view-badge">
              <span>{{ modelFormatLabel }}</span>
              <strong>{{ registrationBadgeLabel }}</strong>
              <small>{{ coordinateSpaceLabel }}</small>
            </div>
          </div>
          <div class="anatomy-3d__legend" aria-label="候选投影图例">
            <span><i class="projection"></i>{{ hotspotProjectionLabel }}</span>
            <span><i class="plane"></i>截骨/复核平面</span>
            <span><i class="reference"></i>医生复核边界</span>
          </div>
          <div class="anatomy-3d__view-controls" aria-label="三维视图控制">
            <button type="button" @click="resetCamera">Reset camera</button>
            <button type="button" @click="toggleObjectVisibility('mandible')">
              {{ objectVisibility.mandible ? "Hide original mandible" : "Show original mandible" }}
            </button>
            <button type="button" @click="focusFirstCandidate">Focus candidate</button>
          </div>
          <div class="anatomy-3d__viewport-label-layer" aria-label="三维标注标签">
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
          <dl class="anatomy-3d__metrics">
            <div>
              <dt>显示模式</dt>
              <dd>{{ modeLabel }}</dd>
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

        <section
          v-for="view in sliceViews"
          :key="view.key"
          class="anatomy-3d__slice-view"
          :class="`is-${view.key}`"
          :aria-label="view.label"
        >
          <header>
            <div>
              <span>{{ view.label }}</span>
              <strong>{{ view.position }}</strong>
            </div>
            <div class="anatomy-3d__slice-controls" :aria-label="`${view.label} 切片滚动`">
              <button type="button" @click="adjustSliceOffset(view.key, -5)">-</button>
              <input
                :value="sliceOffsets[view.key]"
                type="range"
                min="-60"
                max="60"
                step="1"
                :aria-label="`${view.label} 切片位置`"
                @input="setSliceOffset(view.key, $event)"
              />
              <button type="button" @click="adjustSliceOffset(view.key, 5)">+</button>
            </div>
          </header>
          <div class="anatomy-3d__slice-canvas" :style="sliceCanvasStyle(view.key)" aria-hidden="true">
            <i class="anatomy-3d__crosshair anatomy-3d__crosshair--x"></i>
            <i class="anatomy-3d__crosshair anatomy-3d__crosshair--y"></i>
            <b class="anatomy-3d__bone-contour"></b>
            <b class="anatomy-3d__roi-contour"></b>
          </div>
          <p>{{ view.note }}</p>
        </section>

        <section
          class="anatomy-3d__reconstruction-view"
          aria-label="腓骨重建与截骨平面示意"
          @dblclick="toggleReconstructionMaximize"
        >
          <header>
            <div>
              <span>View 2</span>
              <strong>Fibula / Neo-mandible reconstruction reference</strong>
            </div>
            <small>Volume Reslice Driver 概念复刻；本项目默认只作 CBCT/STL 证据参考。</small>
          </header>
          <div class="anatomy-3d__fibula-stage" aria-hidden="true">
            <b class="anatomy-3d__fibula-bone"></b>
            <i class="anatomy-3d__fibula-piece anatomy-3d__fibula-piece--one"></i>
            <i class="anatomy-3d__fibula-piece anatomy-3d__fibula-piece--two"></i>
            <i class="anatomy-3d__fibula-plane anatomy-3d__fibula-plane--red"></i>
            <i class="anatomy-3d__fibula-plane anatomy-3d__fibula-plane--green"></i>
            <i class="anatomy-3d__fibula-plane anatomy-3d__fibula-plane--blue"></i>
            <span v-if="showFibulaSegmentLengths" class="anatomy-3d__measurement anatomy-3d__measurement--one">
              {{ fibulaSegmentLengthLabels[0] }}
            </span>
            <span v-if="showFibulaSegmentLengths" class="anatomy-3d__measurement anatomy-3d__measurement--two">
              {{ fibulaSegmentLengthLabels[1] }}
            </span>
          </div>
          <p>该区域复刻 BoneReconstructionPlanner 的 fibula line、miter boxes、bone pieces 和 transform-to-mandible 语义；在本平台中仅用于说明模型来源与术前证据链，不直接驱动术中导航。</p>
        </section>
      </main>

      <aside class="anatomy-3d__inspector" aria-label="三维证据与复核面板">
        <div class="anatomy-3d__panel-title">
          <span>Evidence inspector</span>
          <strong>证据接入与复核</strong>
        </div>
        <dl class="anatomy-3d__evidence-grid">
          <div v-for="field in evidenceFields" :key="field.label">
            <dt>{{ field.label }}</dt>
            <dd>{{ field.value }}</dd>
          </div>
        </dl>
        <div class="anatomy-3d__registration-guard" aria-label="真实导航前置条件">
          <strong>真实空间映射前置条件</strong>
          <ul>
            <li v-for="item in registrationGuardItems" :key="item.label" :class="{ 'is-ready': item.ready }">
              <span>{{ item.ready ? "Ready" : "Missing" }}</span>
              <p>{{ item.label }}</p>
            </li>
          </ul>
        </div>
        <div class="anatomy-3d__markups" aria-label="Markups 配准点表">
          <header>
            <strong>Markups / Registration Table</strong>
            <small>{{ registrationMarkupsSummary }}</small>
          </header>
          <div class="anatomy-3d__markup-table">
            <button
              v-for="markup in registrationMarkupRows"
              :key="markup.id"
              type="button"
              class="anatomy-3d__markup-row"
              :class="{ 'is-selected': selectedMarkupId === markup.id, 'is-ready': markup.ready }"
              @click="selectMarkup(markup.id)"
            >
              <span>{{ markup.shortLabel }}</span>
              <strong>{{ markup.label }}</strong>
              <small>{{ markup.sourceLabel }} -> {{ markup.targetLabel }}</small>
              <em>{{ markup.residualLabel }}</em>
              <b>{{ markup.statusLabel }}</b>
            </button>
          </div>
        </div>
        <div class="anatomy-3d__transform-chain" aria-label="坐标变换链">
          <header>
            <strong>Transform chain</strong>
            <small>{{ transformChainSummary }}</small>
          </header>
          <ol>
            <li v-for="step in transformChainItems" :key="step.name" :class="{ 'is-ready': step.ready }">
              <span>{{ step.ready ? "Ready" : "Missing" }}</span>
              <div>
                <strong>{{ step.name }}</strong>
                <small>{{ step.fromSpace }} -> {{ step.toSpace }}</small>
                <em>{{ step.detail }}</em>
              </div>
            </li>
          </ol>
        </div>
        <div class="anatomy-3d__workflow" aria-label="三维模型接入流程">
          <div v-for="step in workflowSteps" :key="step.index">
            <span>{{ step.index }}</span>
            <strong>{{ step.title }}</strong>
            <small>{{ step.detail }}</small>
          </div>
        </div>
        <p class="anatomy-3d__boundary">{{ boundaryNote }}</p>
        <div v-if="normalizedHotspots.length" class="anatomy-3d__hotspot-list">
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
        <p v-else class="anatomy-3d__empty">暂无候选区投影；当前仅显示三维参考模型。</p>
      </aside>
    </div>

    <p class="anatomy-3d__disclaimer">
      该视图用于展示脱敏 CBCT/STL/GLB 三维参考和 ICG 候选区的空间关系；未完成配准、误差记录和医生复核时仅为示意参考，不代表自动诊断、真实术中导航定位或精准切除边界。
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
  ThreeDScenePlane,
} from "@/types/case";

interface Props {
  candidates: CandidateRegion[];
  metrics?: Record<string, unknown>;
  modeLabel?: string;
  threeDEvidence?: ThreeDEvidence | null;
}

type RiskLevel = "high" | "medium" | "low";
type WorkspaceTool = "layout" | "curve" | "planes" | "fibula" | "roi";
type ViewLayoutMode = "four" | "threeD" | "reconstruction";
type SliceKey = "axial" | "coronal" | "sagittal";
type ModuleActionKey =
  | "mandibularCurve"
  | "fibulaLine"
  | "cutPlane"
  | "createBoneModels"
  | "centerFibulaLine"
  | "create3dModel"
  | "updateFibulaPlanes";
type ObjectVisibilityKey = "cbct" | "mandible" | "curvePlanes" | "candidates" | "registration" | "fibula";
type ViewportLabelKind = "markup" | "plane" | "hotspot" | "fibula";

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

interface ToolbarItem {
  key: WorkspaceTool;
  label: string;
  note: string;
}

interface ModuleAction {
  key: ModuleActionKey;
  label: string;
  state: string;
}

interface ObjectTreeItem {
  key: ObjectVisibilityKey;
  name: string;
  detail: string;
  state: string;
  muted: boolean;
  locked?: boolean;
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

const props = withDefaults(defineProps<Props>(), {
  metrics: () => ({}),
  modeLabel: "术中融合证据",
});

const emit = defineEmits<{
  selectCandidateFrame: [payload: { candidateId: string; frameKey: string; frameIndex: number | null; timestampSec: number | null }];
}>();

const canvasHost = ref<HTMLDivElement | null>(null);
const selectedHotspotKey = ref("");
const selectedMarkupId = ref("");
const activeTreeNodeName = ref("Mandible surface model");
const modelLoadState = ref<"fallback" | "loaded" | "failed">("fallback");
const loadedModelPath = ref("");
const geometryManifest = ref<ThreeDGeometryManifest | null>(null);
const geometryLoadState = ref<"idle" | "loading" | "loaded" | "failed">("idle");
const activeWorkspaceTool = ref<WorkspaceTool>("layout");
const viewLayoutMode = ref<ViewLayoutMode>("four");
const activeModuleAction = ref<ModuleActionKey>("mandibularCurve");
const mandibulectomyMode = ref<"Segmental Mandibulectomy" | "Hemimandibulectomy">("Segmental Mandibulectomy");
const sliceOffsets = ref<Record<SliceKey, number>>({
  axial: 0,
  coronal: 0,
  sagittal: 0,
});
const autoPositionPlanes = ref(true);
const rotatePlanesTogether = ref(true);
const showFibulaSegmentLengths = ref(true);
const rightSideLeg = ref(true);
const betweenSpaceMm = ref(1.5);
const securityMarginMm = ref(2);
const miterBoxDistanceMm = ref(22);
const objectVisibility = ref<Record<ObjectVisibilityKey, boolean>>({
  cbct: true,
  mandible: true,
  curvePlanes: true,
  candidates: true,
  registration: true,
  fibula: true,
});

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
let fibulaReferenceGroup: THREE.Group | null = null;
let referenceStageGroup: THREE.Group | null = null;
let registrationMarkupGroup: THREE.Group | null = null;
let fallbackBoneGroup: THREE.Group | null = null;
let loadedAnatomyGroup: THREE.Group | null = null;
let frameId = 0;
let resizeObserver: ResizeObserver | null = null;

const evidence = computed(() => props.threeDEvidence ?? null);
const evidenceModelPath = computed(() => stringFromEvidence(evidence.value?.model_path));
const evidenceModelFormat = computed(() => stringFromEvidence(evidence.value?.model_format).toLowerCase());
const sceneManifest = computed<ThreeDSceneManifest | null>(() =>
  isEvidenceRecord(evidence.value?.scene_manifest) ? (evidence.value?.scene_manifest as ThreeDSceneManifest) : null,
);
const geometryManifestPath = computed(() => stringFromEvidence(evidence.value?.geometry_manifest_path));
const hasEvidenceModel = computed(() => Boolean(evidenceModelPath.value));
const isRegistered = computed(() => stringFromEvidence(evidence.value?.registration_status).toLowerCase() === "registered");

const modelSourceLabel = computed(() => {
  if (modelLoadState.value === "failed") return "三维模型加载失败";
  if (modelLoadState.value === "loaded") {
    return stringFromEvidence(evidence.value?.model_source) || "病例三维表面模型";
  }
  return hasEvidenceModel.value ? "待接入病例三维模型" : "示意占位 / 未接入真实模型";
});

const displayModeLabel = computed(() => (modelLoadState.value === "loaded" ? "真实模型参考" : "示意占位参考"));
const registrationLabel = computed(() => {
  if (isRegistered.value) return "已配准";
  if (modelLoadState.value === "loaded") return "未配准";
  return "未配准 / 非导航";
});
const registrationBadgeLabel = computed(() => (isRegistered.value ? "REGISTERED" : "REFERENCE"));
const coordinateSpaceLabel = computed(() => stringFromEvidence(evidence.value?.coordinate_space) || "坐标系未记录");
const modelFileNameLabel = computed(() => stringFromEvidence(evidence.value?.model_file_name) || fileNameFromPath(evidenceModelPath.value) || "文件名未记录");
const exportedFromLabel = computed(() => stringFromEvidence(evidence.value?.exported_from) || "导出工具未记录");
const dicomSeriesLabel = computed(() => stringFromEvidence(evidence.value?.dicom_series_uid) || "DICOM 序列未记录");
const segmentationSourceLabel = computed(() => stringFromEvidence(evidence.value?.segmentation_source) || "分割来源未记录");
const segmentationReviewStatusLabel = computed(() => stringFromEvidence(evidence.value?.segmentation_review_status) || "分割复核状态未记录");
const registrationMethodLabel = computed(() => stringFromEvidence(evidence.value?.registration_method) || "配准方法未记录");
const doctorReviewStatusLabel = computed(() => stringFromEvidence(evidence.value?.doctor_review_status) || "医生复核状态未记录");
const evidenceAnalysisModeLabel = computed(() => stringFromEvidence(evidence.value?.analysis_mode) || "分析模式未记录");
const evidenceDataBoundaryLabel = computed(() => stringFromEvidence(evidence.value?.data_boundary) || "三维数据边界未记录");
const transformPathLabel = computed(() => stringFromEvidence(evidence.value?.transform_path) || "坐标变换文件未记录");
const modelFormatLabel = computed(() => evidenceModelFormat.value.toUpperCase() || (modelLoadState.value === "loaded" ? "3D MODEL" : "DEMO MODEL"));
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
    stringFromEvidence(evidence.value?.boundary_note) ||
    "当前三维视图只提供空间理解和医生复核参考；未记录配准误差时不得作为真实术中导航或切除边界。",
);
const hotspotProjectionLabel = computed(() => (isRegistered.value ? "已配准空间映射" : "2D 候选示意投影"));
const modelLoadNote = computed(() => {
  if (modelLoadState.value === "loaded") return `已加载 ${loadedModelPath.value}`;
  if (modelLoadState.value === "failed") return "真实模型文件无法解析，已回退示意模型";
  return "未检测到真实 STL/GLB，当前为示意占位模型";
});
const sceneCurveLabel = computed(
  () => stringFromEvidence(sceneManifest.value?.mandibular_curve?.label) || "下颌曲线用于解释候选投影与规划切面关系",
);
const sceneManifestSourceLabel = computed(
  () => stringFromEvidence(sceneManifest.value?.source_project) || "前端示意场景",
);
const geometryManifestLabel = computed(() => {
  if (!geometryManifestPath.value) return "BRP 几何计算未生成";
  if (geometryLoadState.value === "loaded") return `${geometryManifestPath.value} · 已读取`;
  if (geometryLoadState.value === "failed") return `${geometryManifestPath.value} · 读取失败`;
  if (geometryLoadState.value === "loading") return `${geometryManifestPath.value} · 读取中`;
  return geometryManifestPath.value;
});
const geometrySchemaLabel = computed(() => stringFromEvidence(geometryManifest.value?.schema_version) || "BRP geometry manifest 未读取");
const geometryStatusLabel = computed(() => {
  const status = geometryManifest.value?.geometry_status;
  if (!isEvidenceRecord(status)) return "几何状态未记录";
  const planeReady = Boolean(status.plane_intersection_ready);
  const candidateReady = Boolean(status.candidate_projection_ready);
  const navigationReady = Boolean(status.navigation_ready);
  return [
    planeReady ? "plane intersections ready" : "plane intersections missing",
    candidateReady ? "candidate surface points ready" : "candidate surface points missing",
    navigationReady ? "navigation ready" : "non-navigation",
  ].join(" / ");
});
const planeIntersectionSummaryLabel = computed(() => {
  const intersections = geometryManifest.value?.plane_intersections;
  if (!Array.isArray(intersections) || !intersections.length) return "未计算";
  const readyCount = intersections.filter((item) => stringFromEvidence(item.status).toLowerCase() === "ready").length;
  const segmentCounts = intersections.map((item) => numberFromEvidenceValue(item.segment_count) ?? 0).join(", ");
  return `${readyCount} / ${intersections.length} ready · segments [${segmentCounts}]`;
});

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
      label: candidate.risk_type || `候选区域 ${index + 1}`,
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

const toolbarItems = computed<ToolbarItem[]>(() => [
  { key: "layout", label: "四视图布局", note: "3D + 轴位 / 冠状 / 矢状" },
  { key: "curve", label: "下颌曲线", note: "参考 Add mandibular curve" },
  { key: "planes", label: "切割平面", note: "参考 Add cut plane" },
  { key: "fibula", label: "腓骨线", note: "参考 Add fibula line" },
  { key: "roi", label: "ROI 复核", note: hotspotProjectionLabel.value },
]);

const viewLayoutOptions: Array<{ key: ViewLayoutMode; label: string }> = [
  { key: "four", label: "四视图" },
  { key: "threeD", label: "3D 最大化" },
  { key: "reconstruction", label: "重建最大化" },
];

const viewLayoutLabel = computed(() => viewLayoutOptions.find((item) => item.key === viewLayoutMode.value)?.label ?? "四视图");
const betweenSpaceLabel = computed(() => `${betweenSpaceMm.value.toFixed(1)} mm`);
const securityMarginLabel = computed(() => `${securityMarginMm.value.toFixed(1)} mm`);
const miterBoxDistanceLabel = computed(() => `${miterBoxDistanceMm.value.toFixed(0)} mm`);
const legSideLabel = computed(() => (rightSideLeg.value ? "Right side leg / medial X axis" : "Left side leg / mirrored reference"));
const fibulaSegmentLengthLabels = computed(() => {
  const measured = geometrySegmentLengthLabels();
  if (measured.length) return [measured[0] ?? "S0: 未计算", measured[1] ?? "S1: 未计算"];
  const lengths = sceneManifest.value?.fibula_reference?.segment_lengths_mm;
  const values = Array.isArray(lengths) ? lengths.map(Number).filter(Number.isFinite) : [];
  return [`S0: ${(values[0] ?? 29.49).toFixed(2)} mm`, `S1: ${(values[1] ?? 28.95).toFixed(2)} mm`];
});

const moduleControls = computed(() => [
  { label: "Mandibulectomy mode", value: mandibulectomyMode.value },
  { label: "Select mandibular segmentation", value: modelLoadState.value === "loaded" ? modelFileNameLabel.value : "Mandible seg / 示意" },
  { label: "Select fibula segmentation", value: "Fibula seg / reference" },
  { label: "Initial space (mm)", value: "0.0" },
  { label: "Intersection distance multiplier", value: "1.0" },
  { label: "Between space (mm)", value: betweenSpaceLabel.value },
  { label: "Fibula side", value: legSideLabel.value },
  { label: "Security margin", value: securityMarginLabel.value },
  { label: "Miter box distance", value: miterBoxDistanceLabel.value },
  { label: "Select mandible curve", value: "mandibularCurve" },
  { label: "Select fibula line", value: "fibulaLine" },
  { label: "Current Scalar Volume", value: dicomSeriesLabel.value },
  { label: "Segmentation source", value: segmentationSourceLabel.value },
  { label: "Segmentation review", value: segmentationReviewStatusLabel.value },
  { label: "Scene manifest", value: sceneManifestSourceLabel.value },
]);

const moduleActions = computed<ModuleAction[]>(() => [
  { key: "mandibularCurve", label: "Add mandibular curve", state: objectVisibility.value.curvePlanes ? "visible" : "hidden" },
  { key: "fibulaLine", label: "Add fibula line", state: objectVisibility.value.fibula ? "visible" : "hidden" },
  { key: "cutPlane", label: "Add cut plane", state: objectVisibility.value.curvePlanes ? "visible" : "hidden" },
  { key: "createBoneModels", label: "Create bone models from segmentations", state: modelLoadState.value === "loaded" ? "case model" : "demo model" },
  { key: "centerFibulaLine", label: "Center fibula line using fibula model", state: "reference" },
  { key: "create3dModel", label: "Create 3D model of the reconstruction for 3D printing", state: "blocked for navigation" },
]);

const activeModuleActionLabel = computed(
  () => moduleActions.value.find((action) => action.key === activeModuleAction.value)?.label || "Update fibula planes",
);

const objectTreeItems = computed<ObjectTreeItem[]>(() => [
  {
    key: "cbct" as ObjectVisibilityKey,
    name: "CBCT volume",
    detail: coordinateSpaceLabel.value,
    state: objectVisibility.value.cbct ? (hasEvidenceModel.value ? "来源记录" : "待接入") : "隐藏",
    muted: !hasEvidenceModel.value || !objectVisibility.value.cbct,
    locked: true,
  },
  {
    key: "mandible" as ObjectVisibilityKey,
    name: "Mandible surface model",
    detail: modelSourceLabel.value,
    state: objectVisibility.value.mandible ? displayModeLabel.value : "隐藏",
    muted: modelLoadState.value !== "loaded" || !objectVisibility.value.mandible,
    locked: !hasEvidenceModel.value,
  },
  {
    key: "curvePlanes" as ObjectVisibilityKey,
    name: "Mandibular curve",
    detail: sceneCurveLabel.value,
    state: objectVisibility.value.curvePlanes ? "示意" : "隐藏",
    muted: !objectVisibility.value.curvePlanes,
    locked: false,
  },
  {
    key: "curvePlanes" as ObjectVisibilityKey,
    name: "Resection / review planes",
    detail: "截骨平面仅作复核语义，不输出真实切除方案",
    state: objectVisibility.value.curvePlanes ? (isRegistered.value ? "待医生复核" : "非导航") : "隐藏",
    muted: !isRegistered.value || !objectVisibility.value.curvePlanes,
    locked: true,
  },
  {
    key: "candidates" as ObjectVisibilityKey,
    name: "ICG candidate overlays",
    detail: normalizedHotspots.value.length ? `${normalizedHotspots.value.length} 个候选区` : "暂无候选区",
    state: objectVisibility.value.candidates ? hotspotProjectionLabel.value : "隐藏",
    muted: !normalizedHotspots.value.length || !objectVisibility.value.candidates,
    locked: !isRegistered.value,
  },
  {
    key: "registration" as ObjectVisibilityKey,
    name: "Registration transform",
    detail: registrationErrorLabel.value,
    state: objectVisibility.value.registration ? registrationLabel.value : "隐藏",
    muted: !isRegistered.value || !objectVisibility.value.registration,
    locked: true,
  },
  {
    key: "fibula" as ObjectVisibilityKey,
    name: "Fibula line / miter boxes",
    detail: `${mandibulectomyMode.value} · ${betweenSpaceLabel.value} between space`,
    state: objectVisibility.value.fibula ? "示意" : "隐藏",
    muted: !objectVisibility.value.fibula,
    locked: false,
  },
]);

const objectTreeGroups = computed<ObjectTreeGroup[]>(() => {
  const items = objectTreeItems.value;
  const byName = (name: string) => items.find((item) => item.name === name);
  return [
    {
      name: "Patient / Volume",
      detail: "Subject hierarchy root",
      items: [byName("CBCT volume")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "Segmentations / Models",
      detail: "Mandible surface and source segmentation",
      items: [byName("Mandible surface model")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "Markups / Planes",
      detail: "Curves, fiducials and review planes",
      items: [byName("Mandibular curve"), byName("Resection / review planes"), byName("Registration transform")].filter(Boolean) as ObjectTreeItem[],
    },
    {
      name: "ICG / Reconstruction Reference",
      detail: "Project evidence overlay, not navigation",
      items: [byName("ICG candidate overlays"), byName("Fibula line / miter boxes")].filter(Boolean) as ObjectTreeItem[],
    },
  ];
});

const viewportLabelItems = computed<ViewportLabelItem[]>(() => {
  const labels: ViewportLabelItem[] = [];
  if (objectVisibility.value.curvePlanes) {
    labels.push(
      {
        key: "plane-left",
        kind: "plane",
        shortLabel: "P0",
        label: mandibulectomyMode.value === "Hemimandibulectomy" ? "Mandible end cut" : "Resection plane left",
        detail: isRegistered.value ? "registered review plane" : "illustrative review plane",
        x: 30,
        y: 42,
        selected: activeModuleAction.value === "cutPlane",
        muted: !isRegistered.value,
        targetKey: "cutPlane",
      },
      {
        key: "plane-right",
        kind: "plane",
        shortLabel: "P1",
        label: mandibulectomyMode.value === "Hemimandibulectomy" ? "Ramus reference plane" : "Resection plane right",
        detail: rotatePlanesTogether.value ? "linked rotation enabled" : "independent rotation",
        x: 67,
        y: 44,
        selected: activeModuleAction.value === "cutPlane",
        muted: !isRegistered.value,
        targetKey: "cutPlane",
      },
    );
  }
  if (objectVisibility.value.fibula) {
    labels.push({
      key: "fibula-reference",
      kind: "fibula",
      shortLabel: "FIB",
      label: "Fibula line / miter boxes",
      detail: `${betweenSpaceLabel.value} between space · ${legSideLabel.value}`,
      x: 54,
      y: 70,
      selected: activeWorkspaceTool.value === "fibula",
      muted: false,
      targetKey: "fibulaLine",
    });
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
    label: "Red 轴位 Axial",
    position: slicePositionLabel("Z", sliceOffsets.value.axial, sliceBaseMm("axial", 12.4)),
    note: sliceNote("axial", "骨窗轮廓、候选投影和十字定位线保持可追溯显示。"),
  },
  {
    key: "coronal" as SliceKey,
    label: "Green 冠状 Coronal",
    position: slicePositionLabel("Y", sliceOffsets.value.coronal, sliceBaseMm("coronal", -18.2)),
    note: sliceNote("coronal", "用于观察下颌体高度、骨皮质连续性和候选区上下边界。"),
  },
  {
    key: "sagittal" as SliceKey,
    label: "Yellow 矢状 Sagittal",
    position: slicePositionLabel("X", sliceOffsets.value.sagittal, sliceBaseMm("sagittal", 6.8)),
    note: sliceNote("sagittal", "用于解释候选区沿牙槽嵴和下颌支方向的空间位置。"),
  },
]);

const evidenceFields = computed(() => [
  { label: "证据 Schema", value: stringFromEvidence(evidence.value?.schema_version) || "three_d_evidence 未接入" },
  { label: "Scene Manifest", value: stringFromEvidence(sceneManifest.value?.schema_version) || "three_d_scene_manifest 未接入" },
  { label: "Geometry Manifest", value: geometryManifestLabel.value },
  { label: "Geometry Schema", value: geometrySchemaLabel.value },
  { label: "几何状态", value: geometryStatusLabel.value },
  { label: "Plane intersections", value: planeIntersectionSummaryLabel.value },
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
  { label: "配准状态", value: registrationLabel.value },
  { label: "配准方法", value: registrationMethodLabel.value },
  { label: "误差记录", value: registrationErrorLabel.value },
  { label: "Fiducial 点数", value: fiducialCount.value == null ? "未记录" : `${fiducialCount.value}` },
  { label: "Surface 点数", value: surfacePointCount.value == null ? "未记录" : `${surfacePointCount.value}` },
  { label: "变换文件", value: transformPathLabel.value },
  { label: "候选映射", value: hotspotProjectionLabel.value },
  { label: "复核状态", value: doctorReviewStatusLabel.value },
  { label: "数据边界", value: evidenceDataBoundaryLabel.value },
  { label: "医生边界", value: boundaryNote.value },
]);

const registrationGuardItems = computed(() => [
  { label: "Point-based fiducials / paired landmarks 已记录", ready: isRegistered.value && (fiducialCount.value ?? 0) >= 3 },
  {
    label: "Surface matching point cloud / ICP 误差已记录",
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
    ready: isRegistered.value && ["accepted", "approved", "reviewed", "复核通过"].includes(doctorReviewStatusLabel.value.toLowerCase()),
  },
  {
    label: "后端明确标记 navigation_ready=true；否则继续保持非导航展示",
    ready: navigationReady.value && isRegistered.value,
  },
]);

const registrationMarkupRows = computed<RegistrationMarkupRow[]>(() => {
  const explicitRows = explicitRegistrationMarkups();
  if (explicitRows.length) return explicitRows;

  const recordedCount = fiducialCount.value ?? 0;
  const rowCount = Math.max(3, Math.min(6, recordedCount || 3));
  return Array.from({ length: rowCount }, (_, index) => {
    const t = rowCount === 1 ? 0.5 : index / (rowCount - 1);
    const archPoint = pointOnMandibleArch(THREE.MathUtils.clamp(0.12 + t * 0.76, 0.12, 0.88));
    const ready = isRegistered.value && index < recordedCount;
    return {
      id: `expected-fiducial-${index + 1}`,
      shortLabel: `F${index + 1}`,
      label: `F${index + 1} paired landmark`,
      sourceLabel: ready ? "CBCT/model point count recorded" : "virtual point missing",
      targetLabel: ready ? "tracked point count recorded" : "tracked point missing",
      residualLabel: ready ? `residual: ${registrationErrorLabel.value}` : "residual: Missing",
      statusLabel: ready ? "Count recorded" : "Missing",
      ready,
      position: archPoint.position,
    };
  });
});

const registrationMarkupsSummary = computed(() => {
  const readyCount = registrationMarkupRows.value.filter((item) => item.ready).length;
  return `${readyCount} / ${registrationMarkupRows.value.length} paired landmarks ready`;
});

const transformChainItems = computed<TransformChainItem[]>(() => {
  const explicitSteps = explicitTransformChain();
  if (explicitSteps.length) return explicitSteps;
  return [
    {
      name: "DICOM voxel to CBCT RAS",
      fromSpace: "DICOM voxel",
      toSpace: coordinateSpaceLabel.value,
      detail: dicomSeriesLabel.value,
      ready: coordinateSpaceLabel.value !== "坐标系未记录" && dicomSeriesLabel.value !== "DICOM 序列未记录",
    },
    {
      name: "Segmentation to surface model",
      fromSpace: segmentationSourceLabel.value,
      toSpace: modelFileNameLabel.value,
      detail: segmentationReviewStatusLabel.value,
      ready: hasEvidenceModel.value && segmentationReviewStatusLabel.value !== "分割复核状态未记录",
    },
    {
      name: "CBCT/STL to video reference",
      fromSpace: coordinateSpaceLabel.value,
      toSpace: "MP4/JPEG keyframe evidence",
      detail: transformPathLabel.value,
      ready: isRegistered.value && transformPathLabel.value !== "坐标变换文件未记录",
    },
    {
      name: "ICG candidate to 3D reference layer",
      fromSpace: "2D keyframe candidate",
      toSpace: isRegistered.value ? "registered reference layer" : "illustrative projection",
      detail: hotspotProjectionLabel.value,
      ready: isRegistered.value && navigationReady.value,
    },
  ];
});

const transformChainSummary = computed(() => {
  const readyCount = transformChainItems.value.filter((item) => item.ready).length;
  return `${readyCount} / ${transformChainItems.value.length} transforms ready`;
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
    detail: "复刻 BoneReconstructionPlanner 的曲线、切面和导板语义。",
  },
  {
    index: "04",
    title: "ICG 候选复核",
    detail: "本项目仅把视频分割候选映射为参考层，默认不做导航承诺。",
  },
]);

function selectModuleAction(action: ModuleActionKey) {
  activeModuleAction.value = action;
  if (action === "mandibularCurve" || action === "cutPlane" || action === "updateFibulaPlanes") {
    objectVisibility.value.curvePlanes = true;
    activeWorkspaceTool.value = action === "mandibularCurve" ? "curve" : "planes";
  }
  if (action === "fibulaLine" || action === "centerFibulaLine" || action === "updateFibulaPlanes") {
    objectVisibility.value.fibula = true;
    activeWorkspaceTool.value = "fibula";
  }
  if (action === "createBoneModels" || action === "create3dModel") {
    objectVisibility.value.mandible = true;
    activeWorkspaceTool.value = "layout";
  }
  applySceneVisibility();
}

function activateTreeNode(item: ObjectTreeItem) {
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
    selectModuleAction("cutPlane");
    return;
  }
  if (label.targetKey === "fibulaLine") {
    selectModuleAction("fibulaLine");
  }
}

function resetCamera() {
  if (!camera || !controls) return;
  camera.position.set(0.8, 1.56, 5.75);
  controls.target.set(0.04, 0.38, 0);
  controls.update();
  viewLayoutMode.value = "four";
  nextTick(resize);
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
  selectedMarkupId.value = id;
  selectedHotspotKey.value = "";
  activeWorkspaceTool.value = "layout";
  objectVisibility.value.registration = true;
  const row = registrationMarkupRows.value.find((item) => item.id === id);
  if (row) {
    updateSliceOffset("axial", Math.round(row.position.z * 42));
    updateSliceOffset("coronal", Math.round(row.position.y * 34));
    updateSliceOffset("sagittal", Math.round(row.position.x * 24));
  }
  renderRegistrationMarkups();
  applySceneVisibility();
}

function toggleObjectVisibility(key: ObjectVisibilityKey) {
  objectVisibility.value[key] = !objectVisibility.value[key];
  applySceneVisibility();
}

function toggleThreeDMaximize() {
  viewLayoutMode.value = viewLayoutMode.value === "threeD" ? "four" : "threeD";
  nextTick(resize);
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
  if (fibulaReferenceGroup) fibulaReferenceGroup.visible = objectVisibility.value.fibula;
  if (referenceStageGroup) referenceStageGroup.visible = objectVisibility.value.registration;
  if (registrationMarkupGroup) registrationMarkupGroup.visible = objectVisibility.value.registration;
}

onMounted(async () => {
  await nextTick();
  initScene();
  void loadGeometryManifest();
  renderHotspots();
  applySceneVisibility();
  startAnimation();
});

onBeforeUnmount(() => {
  stopAnimation();
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
  fibulaReferenceGroup = null;
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
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.18;
  host.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.7;
  controls.enablePan = false;
  controls.minDistance = 3.45;
  controls.maxDistance = 7.4;
  controls.minPolarAngle = 0.62;
  controls.maxPolarAngle = 1.78;
  controls.target.set(0.04, 0.38, 0);
  controls.update();

  rootGroup = new THREE.Group();
  rootGroup.rotation.x = -0.08;
  rootGroup.rotation.y = -0.24;
  scene.add(rootGroup);

  boneGroup = new THREE.Group();
  fallbackBoneGroup = new THREE.Group();
  hotspotGroup = new THREE.Group();
  planningGuideGroup = new THREE.Group();
  anatomyPlaneGroup = new THREE.Group();
  fibulaReferenceGroup = new THREE.Group();
  referenceStageGroup = new THREE.Group();
  registrationMarkupGroup = new THREE.Group();
  rootGroup.add(boneGroup);
  boneGroup.add(fallbackBoneGroup);
  rootGroup.add(planningGuideGroup);
  rootGroup.add(anatomyPlaneGroup);
  rootGroup.add(fibulaReferenceGroup);
  rootGroup.add(referenceStageGroup);
  rootGroup.add(registrationMarkupGroup);
  rootGroup.add(hotspotGroup);

  addLights();
  buildMandible();
  buildPlanningGuides();
  buildFibulaReference();
  buildAnatomyPlanes();
  buildReferenceStage();
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

function buildFibulaReference() {
  if (!fibulaReferenceGroup) return;
  const fibulaCurve = new THREE.CatmullRomCurve3(sceneFibulaCurvePoints());
  const fibulaMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x8fbf7c,
    roughness: 0.62,
    metalness: 0.02,
    clearcoat: 0.12,
    transparent: true,
    opacity: 0.88,
  });
  const fibula = new THREE.Mesh(new THREE.TubeGeometry(fibulaCurve, 84, 0.095, 18, false), fibulaMaterial);
  fibula.castShadow = true;
  fibula.receiveShadow = true;
  fibulaReferenceGroup.add(fibula);

  const pieceMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xc98c9f,
    roughness: 0.52,
    transparent: true,
    opacity: 0.78,
  });
  [0.45, 0.56].forEach((t) => {
    const center = fibulaCurve.getPoint(t);
    const piece = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.38, 10, 18), pieceMaterial);
    piece.position.copy(center);
    piece.rotation.z = Math.PI / 2;
    piece.rotation.y = 0.08;
    piece.castShadow = true;
    fibulaReferenceGroup?.add(piece);
  });

  const planeSpecs = [
    { fallbackX: -0.64, color: 0xd9544f, fallbackTilt: -0.28 },
    { fallbackX: -0.12, color: 0x5aa65a, fallbackTilt: 0.18 },
    { fallbackX: 0.48, color: 0x3f93bf, fallbackTilt: -0.2 },
  ];
  const manifestPlanes = sceneFibulaMiterPlanes();
  planeSpecs.forEach((spec, index) => {
    const manifestPlane = manifestPlanes[index];
    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(0.58, 0.92),
      new THREE.MeshBasicMaterial({
        color: spec.color,
        transparent: true,
        opacity: 0.18,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    plane.position.copy(manifestPlane?.position ?? new THREE.Vector3(spec.fallbackX, -1.27, -0.1));
    const rotation = manifestPlane?.rotation ?? new THREE.Vector3(0, Math.PI / 2 + spec.fallbackTilt, 0.08);
    plane.rotation.x = rotation.x;
    plane.rotation.y = rotation.y;
    plane.rotation.z = rotation.z;
    fibulaReferenceGroup?.add(plane);
  });
}

async function loadRealAnatomyModel() {
  if (!boneGroup) return;
  clearLoadedAnatomyModel();
  ensureFallbackModel();
  const model = await findAvailableModel();
  if (!model) {
    modelLoadState.value = "fallback";
    loadedModelPath.value = "";
    return;
  }

  try {
    const loaded = model.format === "stl"
      ? await loadStlModel(model.path)
      : await loadGltfModel(model.path);
    normalizeLoadedModel(loaded);
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
    clearLoadedAnatomyModel();
    ensureFallbackModel();
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
  const paths = [
    "/models/mandible.glb",
    "/models/mandible.gltf",
    "/models/mandible.stl",
  ];
  for (const path of paths) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      const contentType = response.headers.get("content-type") ?? "";
      if (response.ok && !contentType.includes("text/html")) {
        return { path, sourcePath: path, format: modelFormatFromPath(path) };
      }
    } catch {
      // Missing local model files are expected in the default platform state.
    }
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
      color: 0x72d9ff,
      roughness: 0.18,
      metalness: 0.04,
      clearcoat: 0.72,
      transmission: 0.18,
      thickness: 0.8,
      transparent: true,
      opacity: 0.58,
      depthWrite: false,
      sheen: 0.58,
      sheenColor: new THREE.Color(0xc9f7ff),
      emissive: new THREE.Color(0x0b5d86),
      emissiveIntensity: 0.34,
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
      color: 0xc4f5ff,
      transparent: true,
      opacity: 0.26,
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

function normalizeLoadedModel(model: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const maxAxis = Math.max(size.x, size.y, size.z) || 1;
  const scale = 3.8 / maxAxis;
  model.scale.setScalar(scale);
  model.rotation.x = -Math.PI / 2;

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
  registrationMarkupRows.value.forEach((markup, index) => {
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
    if (rootGroup && !controls?.enabled) {
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
      label: "Resection plane left",
      position: new THREE.Vector3(-0.95, 0.18, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2 - 0.13, -0.16),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
    {
      id: "fallback-plane-mid",
      label: "Resection plane middle",
      position: new THREE.Vector3(0, 0.21, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2, 0),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
    {
      id: "fallback-plane-right",
      label: "Resection plane right",
      position: new THREE.Vector3(0.95, 0.24, 0.12),
      rotation: new THREE.Vector3(0, Math.PI / 2 + 0.13, 0.16),
      scale: new THREE.Vector3(1.0, 1.85, 1),
    },
  ];
}

function sceneFibulaCurvePoints(): THREE.Vector3[] {
  const rawPoints = sceneManifest.value?.fibula_reference?.display_curve;
  const points = Array.isArray(rawPoints)
    ? rawPoints.map((point) => vectorFromScenePoint(point)).filter((point): point is THREE.Vector3 => point !== null)
    : [];
  if (points.length >= 2) return points;
  return [
    new THREE.Vector3(-1.92, -1.34, -0.26),
    new THREE.Vector3(-0.72, -1.24, -0.18),
    new THREE.Vector3(0.62, -1.28, -0.1),
    new THREE.Vector3(1.84, -1.36, -0.2),
  ];
}

function sceneFibulaMiterPlanes(): ScenePlaneDisplay[] {
  const rawPlanes = sceneManifest.value?.fibula_reference?.miter_planes;
  return Array.isArray(rawPlanes)
    ? rawPlanes
        .map((plane, index) => scenePlaneFromEvidence(plane, index))
        .filter((plane): plane is ScenePlaneDisplay => plane !== null)
    : [];
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
    label: stringFromEvidence(markup.label) || `F${index + 1} paired landmark`,
    sourceLabel: stringFromEvidence(markup.source_label) || pointLabelFromEvidence(markup.source_point_mm, "source point"),
    targetLabel: stringFromEvidence(markup.target_label) || pointLabelFromEvidence(markup.target_point_mm, "target point"),
    residualLabel: residual == null ? "residual: Missing" : `residual: ${residual.toFixed(2)} mm`,
    statusLabel: status || (ready ? "Ready" : "Missing"),
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
    name: stringFromEvidence(step.name) || `Transform ${index + 1}`,
    fromSpace: stringFromEvidence(step.from_space) || "未记录输入坐标",
    toSpace: stringFromEvidence(step.to_space) || "未记录输出坐标",
    detail: [path || "变换文件未记录", error == null ? "" : `${error.toFixed(2)} mm`].filter(Boolean).join(" · "),
    ready,
  };
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
.anatomy-3d {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(123, 215, 255, 0.34);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(10, 27, 45, 0.98), rgba(6, 17, 29, 0.98) 52%, rgba(9, 29, 41, 0.98)),
    #07131f;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.1) inset,
    0 14px 34px rgba(7, 19, 31, 0.18);
}

.anatomy-3d::before {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(103, 222, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(103, 222, 255, 0.055) 1px, transparent 1px);
  background-size: 26px 26px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.82), transparent 70%);
  content: "";
}

.anatomy-3d > * {
  position: relative;
  z-index: 1;
}

.anatomy-3d__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px 12px;
  border-bottom: 1px solid rgba(121, 209, 255, 0.24);
  background:
    linear-gradient(90deg, rgba(28, 117, 183, 0.18), transparent 52%),
    rgba(4, 16, 29, 0.54);
}

.anatomy-3d__header span,
.anatomy-3d__rail-title span {
  display: block;
  margin-bottom: 4px;
  color: #74d7ff;
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.anatomy-3d__header h2 {
  margin: 0;
  color: #f2fbff;
  font-size: 23px;
  line-height: 1.2;
  letter-spacing: 0;
}

.anatomy-3d__status {
  display: grid;
  justify-items: end;
  gap: 4px;
  min-width: 126px;
}

.anatomy-3d__status strong {
  border-radius: 7px;
  padding: 8px 11px;
  font-size: 14px;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.08);
}

.anatomy-3d__status.is-high strong {
  border: 1px solid rgba(255, 116, 122, 0.72);
  background: rgba(255, 77, 86, 0.18);
  color: #ffd3d6;
}

.anatomy-3d__status.is-medium strong {
  border: 1px solid rgba(255, 183, 80, 0.74);
  background: rgba(255, 170, 48, 0.16);
  color: #ffe4b7;
}

.anatomy-3d__status.is-low strong {
  border: 1px solid rgba(87, 223, 174, 0.74);
  background: rgba(43, 203, 145, 0.16);
  color: #c5ffed;
}

.anatomy-3d__status.is-reference strong {
  border: 1px solid rgba(142, 181, 196, 0.62);
  background: rgba(142, 181, 196, 0.12);
  color: #d9edf7;
}

.anatomy-3d__status small {
  color: #97b8ca;
  font-size: 12px;
  font-weight: 800;
}

.anatomy-3d__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  min-height: 430px;
}

.anatomy-3d__viewport {
  position: relative;
  min-height: 430px;
  background:
    linear-gradient(rgba(86, 207, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(86, 207, 255, 0.055) 1px, transparent 1px),
    radial-gradient(circle at 49% 42%, rgba(55, 182, 255, 0.18), transparent 36%),
    linear-gradient(180deg, #081623, #06111d);
  background-size: 34px 34px, 34px 34px, auto, auto;
}

.anatomy-3d__viewport::before,
.anatomy-3d__viewport::after {
  position: absolute;
  z-index: 2;
  width: 54px;
  height: 54px;
  pointer-events: none;
  content: "";
}

.anatomy-3d__viewport::before {
  top: 18px;
  left: 18px;
  border-top: 2px solid rgba(116, 215, 255, 0.78);
  border-left: 2px solid rgba(116, 215, 255, 0.78);
}

.anatomy-3d__viewport::after {
  right: 18px;
  bottom: 18px;
  border-right: 2px solid rgba(116, 215, 255, 0.78);
  border-bottom: 2px solid rgba(116, 215, 255, 0.78);
}

.anatomy-3d__viewport :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 430px;
  touch-action: none;
}

.anatomy-3d__hud,
.anatomy-3d__metrics,
.anatomy-3d__legend,
.anatomy-3d__scan-readout {
  position: absolute;
  z-index: 3;
  border: 1px solid rgba(123, 215, 255, 0.34);
  border-radius: 7px;
  background: rgba(7, 20, 34, 0.72);
  box-shadow:
    0 10px 28px rgba(0, 0, 0, 0.24),
    0 0 22px rgba(68, 199, 255, 0.1);
  backdrop-filter: blur(10px);
}

.anatomy-3d__hud {
  top: 14px;
  left: 14px;
  display: grid;
  gap: 3px;
  max-width: min(52%, 380px);
  padding: 10px 12px;
}

.anatomy-3d__hud strong {
  color: #f3fbff;
  font-size: 14px;
}

.anatomy-3d__hud span {
  color: #a3c8d9;
  font-size: 12px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.anatomy-3d__scan-readout {
  right: 14px;
  top: 72px;
  display: grid;
  min-width: 154px;
  gap: 2px;
  padding: 10px 12px;
}

.anatomy-3d__scan-readout span {
  color: #76e4ff;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.anatomy-3d__scan-readout strong {
  color: #f4fbff;
  font-size: 15px;
}

.anatomy-3d__scan-readout small {
  color: #9dbccc;
  font-size: 11px;
  font-weight: 800;
}

.anatomy-3d__metrics {
  right: 14px;
  bottom: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(82px, 1fr));
  gap: 8px;
  padding: 10px 12px;
}

.anatomy-3d__metrics dt,
.anatomy-3d__metrics dd,
.anatomy-3d__rail-grid dt,
.anatomy-3d__rail-grid dd {
  margin: 0;
}

.anatomy-3d__metrics dt,
.anatomy-3d__rail-grid dt {
  color: #82cde9;
  font-size: 11px;
  font-weight: 900;
}

.anatomy-3d__metrics dd,
.anatomy-3d__rail-grid dd {
  margin-top: 4px;
  color: #f1fbff;
  font-size: 14px;
  font-weight: 900;
  overflow-wrap: anywhere;
}

.anatomy-3d__legend {
  top: 14px;
  right: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 9px 11px;
}

.anatomy-3d__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d7ecf7;
  font-size: 12px;
  font-weight: 900;
}

.anatomy-3d__legend i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.anatomy-3d__legend .projection {
  background: #8fb1bd;
}

.anatomy-3d__legend .reference {
  background: #2f8dcc;
}
.anatomy-3d__rail {
  display: grid;
  align-content: start;
  gap: 14px;
  border-left: 1px solid rgba(121, 209, 255, 0.24);
  padding: 16px;
  background:
    linear-gradient(180deg, rgba(9, 25, 40, 0.96), rgba(5, 17, 29, 0.96)),
    #07131f;
}

.anatomy-3d__rail-title strong {
  color: #f2fbff;
  font-size: 16px;
}

.anatomy-3d__rail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.anatomy-3d__rail-grid div {
  min-height: 64px;
  border: 1px solid rgba(111, 205, 255, 0.26);
  border-radius: 7px;
  padding: 9px;
  background: rgba(255, 255, 255, 0.045);
}

.anatomy-3d__interop {
  display: grid;
  gap: 8px;
}

.anatomy-3d__interop div {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 2px 9px;
  align-items: center;
  border: 1px solid rgba(106, 203, 255, 0.24);
  border-radius: 7px;
  padding: 9px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.035));
}

.anatomy-3d__interop span {
  grid-row: span 2;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  border: 1px solid rgba(117, 221, 255, 0.42);
  background: rgba(21, 109, 156, 0.24);
  color: #b8efff;
  font-size: 11px;
  font-weight: 900;
}

.anatomy-3d__interop strong {
  min-width: 0;
  color: #f2fbff;
  font-size: 13px;
  font-weight: 900;
}

.anatomy-3d__interop small {
  min-width: 0;
  color: #a5c4d3;
  font-size: 12px;
  font-weight: 800;
}

.anatomy-3d__boundary,
.anatomy-3d__empty {
  margin: 0;
  border: 1px solid rgba(123, 215, 255, 0.2);
  border-radius: 7px;
  padding: 9px 10px;
  background: rgba(255, 255, 255, 0.04);
  color: #a5c4d3;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__hotspot-list {
  display: grid;
  gap: 9px;
}

.anatomy-3d__hotspot {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 4px 10px;
  width: 100%;
  border: 1px solid rgba(106, 203, 255, 0.22);
  border-radius: 7px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.052);
  color: #f2fbff;
  text-align: left;
}

.anatomy-3d__hotspot span {
  grid-row: span 2;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 7px;
  color: #ffffff;
  font-weight: 900;
}

.anatomy-3d__hotspot strong {
  min-width: 0;
  color: #f4fbff;
  font-size: 13px;
  overflow-wrap: anywhere;
  white-space: normal;
}

.anatomy-3d__hotspot small {
  color: #a7c3d1;
  font-size: 12px;
  font-weight: 800;
}

.anatomy-3d__hotspot.is-high span {
  background: #d83b3e;
}

.anatomy-3d__hotspot.is-medium span {
  background: #d88b18;
}

.anatomy-3d__hotspot.is-low span {
  background: #15966a;
}

.anatomy-3d__hotspot.is-reference-projection span {
  background: #7f9eaa;
}

.anatomy-3d__hotspot.is-reference-projection strong {
  color: #d7ecf7;
}

.anatomy-3d__hotspot.selected {
  border-color: #72dfff;
  background: rgba(66, 177, 229, 0.12);
  box-shadow:
    0 0 0 3px rgba(76, 198, 255, 0.13),
    0 0 22px rgba(76, 198, 255, 0.16);
}

.anatomy-3d__disclaimer {
  margin: 0;
  border-top: 1px solid rgba(121, 209, 255, 0.24);
  padding: 11px 16px;
  background: rgba(4, 16, 29, 0.74);
  color: #a5c0d0;
  font-size: 13px;
  line-height: 1.55;
}

@media (max-width: 1180px) {
  .anatomy-3d__body {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__rail {
    border-top: 1px solid rgba(121, 209, 255, 0.24);
    border-left: 0;
  }
}

@media (max-width: 760px) {
  .anatomy-3d__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .anatomy-3d__status {
    justify-items: start;
  }

  .anatomy-3d__viewport,
  .anatomy-3d__viewport :deep(canvas) {
    min-height: 520px;
  }

  .anatomy-3d__hud {
    top: 10px;
    right: 10px;
    left: 10px;
    max-width: none;
  }

  .anatomy-3d__scan-readout {
    top: 84px;
    right: 10px;
    left: 10px;
  }

  .anatomy-3d__legend {
    top: auto;
    right: 10px;
    bottom: 112px;
    left: 10px;
  }

  .anatomy-3d__metrics {
    right: 10px;
    bottom: 10px;
    left: 10px;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .anatomy-3d__rail-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 520px) {
  .anatomy-3d__viewport,
  .anatomy-3d__viewport :deep(canvas) {
    min-height: 590px;
  }

  .anatomy-3d__legend {
    bottom: 204px;
  }

  .anatomy-3d__metrics {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__rail-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-color-scheme: light) {
  .anatomy-3d {
    border-color: #d6e0eb;
    background: linear-gradient(180deg, #ffffff, #f7fbff);
    box-shadow: 0 2px 12px rgba(39, 74, 106, 0.06);
  }

  .anatomy-3d::before {
    background:
      linear-gradient(rgba(44, 126, 192, 0.06) 1px, transparent 1px),
      linear-gradient(90deg, rgba(44, 126, 192, 0.06) 1px, transparent 1px);
  }

  .anatomy-3d__header {
    border-bottom-color: #e3ebf3;
    background: linear-gradient(90deg, rgba(44, 126, 192, 0.08), transparent 52%), #ffffff;
  }

  .anatomy-3d__header span,
  .anatomy-3d__rail-title span {
    color: #1e6fa6;
  }

  .anatomy-3d__header h2,
  .anatomy-3d__rail-title strong,
  .anatomy-3d__interop strong,
  .anatomy-3d__hotspot,
  .anatomy-3d__hotspot strong {
    color: #102136;
  }

  .anatomy-3d__status small,
  .anatomy-3d__interop small,
  .anatomy-3d__boundary,
  .anatomy-3d__empty,
  .anatomy-3d__hotspot small,
  .anatomy-3d__disclaimer {
    color: #5a6a7a;
  }

  .anatomy-3d__status.is-reference strong {
    border-color: #b8c9d8;
    background: #eef4f8;
    color: #36566a;
  }

  .anatomy-3d__rail {
    border-left-color: #e3ebf3;
    background: #f8fcff;
  }

  .anatomy-3d__rail-grid div,
  .anatomy-3d__interop div,
  .anatomy-3d__boundary,
  .anatomy-3d__empty,
  .anatomy-3d__hotspot {
    border-color: #d6e0eb;
    background: #ffffff;
  }

  .anatomy-3d__metrics dt,
  .anatomy-3d__rail-grid dt {
    color: #4d6780;
  }

  .anatomy-3d__metrics dd,
  .anatomy-3d__rail-grid dd {
    color: #17324a;
  }

  .anatomy-3d__interop span {
    border-color: #b8d9ed;
    background: #eef8ff;
    color: #1e6fa6;
  }

  .anatomy-3d__disclaimer {
    border-top-color: #e3ebf3;
    background: #ffffff;
  }

  .anatomy-3d__hud,
  .anatomy-3d__metrics,
  .anatomy-3d__legend,
  .anatomy-3d__scan-readout {
    border-color: rgba(255, 255, 255, 0.2);
    background: rgba(7, 20, 34, 0.74);
  }
}
/* Slicer-style planning workbench override. Kept at the end to supersede the earlier compact evidence panel rules. */
.anatomy-3d {
  --av-surface: var(--ov-bg-elevated, #ffffff);
  --av-surface-soft: var(--ov-bg-soft, #f4f9ff);
  --av-surface-panel: var(--ov-bg-panel, #eef5fd);
  --av-border: var(--ov-border-subtle, #d8e5f2);
  --av-border-strong: var(--ov-border-strong, #9ebddb);
  --av-text: var(--ov-text, #17324a);
  --av-text-secondary: var(--ov-text-secondary, #4d6780);
  --av-text-muted: var(--ov-text-muted, #6c8299);
  --av-accent: var(--ov-primary-strong, #2c7ec0);
  --av-blue: #2c7ec0;
  --av-green: #2f7b63;
  --av-amber: #aa7128;
  --av-red: #a34933;
  overflow: visible;
  border: 1px solid var(--av-border-strong);
  border-radius: 8px;
  background: var(--av-surface);
  color: var(--av-text);
  box-shadow: var(--ov-shadow, 0 14px 32px rgba(22, 76, 120, 0.08));
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
  align-items: start;
  padding: 14px 16px;
  border-bottom: 1px solid var(--av-border);
  background: linear-gradient(180deg, var(--av-surface), var(--av-surface-soft));
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
  font-size: clamp(19px, 2vw, 24px);
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
  display: block;
  border-radius: 7px;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.35;
  text-align: center;
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
  padding: 6px 12px;
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
  display: grid;
  grid-template-columns: minmax(250px, 300px) minmax(0, 1fr);
  grid-template-areas:
    "tree views"
    "inspector views";
  align-items: start;
  gap: 1px;
  min-height: 0;
  background: var(--av-border);
}

.anatomy-3d__object-tree,
.anatomy-3d__inspector,
.anatomy-3d__views {
  min-width: 0;
  background: var(--av-surface);
}

.anatomy-3d__object-tree {
  grid-area: tree;
}

.anatomy-3d__views {
  grid-area: views;
}

.anatomy-3d__inspector {
  grid-area: inspector;
}

.anatomy-3d__object-tree,
.anatomy-3d__inspector {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 12px;
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

.anatomy-3d__module-card {
  display: grid;
  gap: 7px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__module-card header {
  display: grid;
  gap: 3px;
  border-bottom: 1px solid var(--av-border);
  padding-bottom: 7px;
}

.anatomy-3d__module-card header strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__module-card header small {
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
  background: color-mix(in srgb, var(--av-surface-soft) 82%, #ffffff 18%);
}

.anatomy-3d__tree-item.is-active-node {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 9%, var(--av-surface-soft));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--av-accent) 18%, transparent) inset;
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
  align-content: space-between;
  gap: 12px;
  min-height: 520px;
  padding: 12px;
  overflow: hidden;
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
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
  padding: 10px 12px;
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
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
}

.anatomy-3d__view-badge {
  justify-items: end;
  text-align: right;
}

.anatomy-3d__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-self: end;
  justify-self: start;
  max-width: 100%;
  padding: 8px 10px;
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
  align-self: end;
  justify-self: end;
  max-width: 100%;
  border: 1px solid rgba(216, 229, 242, 0.28);
  border-radius: 7px;
  padding: 7px 8px;
  background: rgba(9, 18, 28, 0.74);
  backdrop-filter: blur(10px);
}

.anatomy-3d__view-controls button {
  min-height: 28px;
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

.anatomy-3d__viewport-label.is-fibula span {
  color: #83bd70;
}

.anatomy-3d__viewport-label.is-selected {
  border-color: #f2c14e;
  box-shadow: 0 0 0 2px rgba(242, 193, 78, 0.16);
}

.anatomy-3d__viewport-label.is-muted {
  opacity: 0.74;
}

.anatomy-3d__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

.anatomy-3d__fibula-stage {
  position: relative;
  min-height: 170px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.26);
  border-radius: 6px;
  background:
    linear-gradient(155deg, transparent 49.5%, rgba(234, 36, 222, 0.46) 49.7%, rgba(234, 36, 222, 0.46) 50.1%, transparent 50.3%),
    linear-gradient(18deg, transparent 48%, rgba(234, 36, 222, 0.42) 48.2%, rgba(234, 36, 222, 0.42) 48.7%, transparent 48.9%),
    radial-gradient(ellipse at 88% 62%, rgba(255, 255, 255, 0.2), transparent 21%),
    rgba(111, 120, 169, 0.96);
}

.anatomy-3d__fibula-bone,
.anatomy-3d__fibula-piece,
.anatomy-3d__fibula-plane,
.anatomy-3d__measurement {
  position: absolute;
  display: block;
}

.anatomy-3d__fibula-bone {
  top: 84px;
  left: 6%;
  width: 88%;
  height: 28px;
  border-radius: 999px;
  background:
    radial-gradient(circle at 10% 50%, #74a565 0 34px, transparent 35px),
    radial-gradient(circle at 90% 50%, #74a565 0 34px, transparent 35px),
    linear-gradient(90deg, #82af6f, #649658 45%, #88b978 100%);
  box-shadow:
    0 10px 22px rgba(24, 40, 56, 0.24),
    0 0 0 1px rgba(42, 81, 44, 0.18) inset;
}

.anatomy-3d__fibula-piece {
  top: 80px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(90deg, #766f64, #c98191);
  box-shadow: 0 0 0 1px rgba(58, 40, 42, 0.2) inset;
}

.anatomy-3d__fibula-piece--one {
  left: 41%;
  width: 9%;
}

.anatomy-3d__fibula-piece--two {
  left: 51%;
  width: 10%;
}

.anatomy-3d__fibula-plane {
  top: 44px;
  width: 70px;
  height: 108px;
  border: 4px solid currentColor;
  background: color-mix(in srgb, currentColor 14%, transparent);
  transform: skewX(-17deg);
}

.anatomy-3d__fibula-plane--red {
  left: 36%;
  color: #d94d45;
}

.anatomy-3d__fibula-plane--green {
  left: 48%;
  color: #53ad61;
}

.anatomy-3d__fibula-plane--blue {
  left: 58%;
  color: #3f8caf;
}

.anatomy-3d__measurement {
  top: 70px;
  border-radius: 999px;
  padding: 3px 7px;
  background: rgba(28, 38, 52, 0.74);
  color: #ffdad7;
  font-size: 11px;
  font-weight: 900;
}

.anatomy-3d__measurement--one {
  left: 44%;
}

.anatomy-3d__measurement--two {
  left: 55%;
}

.anatomy-3d__evidence-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 7px;
  margin: 0;
}

.anatomy-3d__evidence-grid div {
  display: grid;
  gap: 3px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 8px;
  background: var(--av-surface-soft);
}

.anatomy-3d__evidence-grid dt {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 900;
  line-height: 1.35;
}

.anatomy-3d__evidence-grid dd {
  color: var(--av-text);
  font-size: 12px;
  font-weight: 900;
  line-height: 1.4;
}

.anatomy-3d__registration-guard {
  display: grid;
  gap: 8px;
  border: 1px solid var(--av-border);
  border-radius: 7px;
  padding: 9px;
  background: var(--av-surface-soft);
}

.anatomy-3d__registration-guard > strong {
  color: var(--av-text);
  font-size: 12px;
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

.anatomy-3d__markups header,
.anatomy-3d__transform-chain header {
  display: grid;
  gap: 3px;
}

.anatomy-3d__markups header strong,
.anatomy-3d__transform-chain header strong {
  color: var(--av-text);
  font-size: 12px;
  line-height: 1.35;
}

.anatomy-3d__markups header small,
.anatomy-3d__transform-chain header small {
  color: var(--av-text-muted);
  font-size: 11px;
  font-weight: 800;
  line-height: 1.35;
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
  background: #7f9eaa;
  color: #ffffff;
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

.anatomy-3d__hotspot-list {
  display: grid;
  gap: 8px;
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
  color: #ffffff;
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
  background: #7f9eaa;
}

.anatomy-3d__hotspot.selected {
  border-color: var(--av-accent);
  background: color-mix(in srgb, var(--av-accent) 10%, var(--av-surface));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--av-accent) 14%, transparent);
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

@media (prefers-color-scheme: dark) {
  .anatomy-3d {
    --av-surface: #0b1826;
    --av-surface-soft: #0f2233;
    --av-surface-panel: #081624;
    --av-border: rgba(121, 209, 255, 0.18);
    --av-border-strong: rgba(123, 215, 255, 0.34);
    --av-text: #d9edf7;
    --av-text-secondary: #9dbccc;
    --av-text-muted: #7fa0b3;
    --av-accent: #74d7ff;
    --av-blue: #74d7ff;
    --av-green: #79dcb9;
    --av-amber: #ffd58f;
    --av-red: #ffd3d6;
    background: var(--av-surface);
  }

  .anatomy-3d__tree-item.is-muted {
    background: rgba(255, 255, 255, 0.035);
  }
}

@media (max-width: 1320px) {
  .anatomy-3d__body {
    grid-template-columns: minmax(170px, 220px) minmax(360px, 1fr);
    grid-template-areas:
      "tree views"
      "inspector inspector";
  }

  .anatomy-3d__inspector {
    grid-template-columns: minmax(0, 1fr) minmax(260px, 0.8fr);
    align-items: start;
  }

  .anatomy-3d__inspector .anatomy-3d__panel-title,
  .anatomy-3d__inspector .anatomy-3d__boundary,
  .anatomy-3d__inspector .anatomy-3d__hotspot-list,
  .anatomy-3d__inspector .anatomy-3d__empty {
    grid-column: 1 / -1;
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

  .anatomy-3d__body {
    grid-template-columns: 1fr;
    grid-template-areas:
      "tree"
      "views"
      "inspector";
  }

  .anatomy-3d__inspector {
    grid-template-columns: 1fr;
  }

  .anatomy-3d__views {
    grid-template-columns: 1fr;
    grid-template-areas:
      "three"
      "axial"
      "reconstruction"
      "coronal"
      "sagittal";
  }

  .anatomy-3d__viewport {
    min-height: 540px;
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
