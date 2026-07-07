<template>
  <section class="anatomy-3d" aria-label="三维颌骨空间证据视图">
    <header class="anatomy-3d__header">
      <div>
        <span>3D holographic evidence</span>
        <h2>颌面三维全息证据视图</h2>
      </div>
      <div class="anatomy-3d__status" :class="`is-${riskSummary.risk}`">
        <strong>{{ riskSummary.label }}</strong>
        <small>{{ candidates.length ? `${candidates.length} 个候选区` : "空间参考" }}</small>
      </div>
    </header>

    <div class="anatomy-3d__body">
      <div ref="canvasHost" class="anatomy-3d__viewport">
        <div class="anatomy-3d__hud anatomy-3d__hud--left">
          <strong>{{ modelSourceLabel }}</strong>
          <span>X-ray 全息模型 + ICG ROI 空间提示 · {{ modelLoadNote }}</span>
        </div>
        <div class="anatomy-3d__scan-readout" aria-label="三维重建状态">
          <span>HOLOGRAM</span>
          <strong>X-RAY 3D</strong>
          <small>STL/GLB · ROI MAP</small>
        </div>
        <dl class="anatomy-3d__metrics">
          <div>
            <dt>空间模式</dt>
            <dd>{{ modeLabel }}</dd>
          </div>
          <div>
            <dt>最高风险</dt>
            <dd>{{ riskSummary.label }}</dd>
          </div>
          <div>
            <dt>平均置信度</dt>
            <dd>{{ confidenceLabel }}</dd>
          </div>
        </dl>
        <div class="anatomy-3d__legend" aria-label="风险图例">
          <span><i class="high"></i>高风险复核</span>
          <span><i class="medium"></i>中等观察</span>
          <span><i class="low"></i>低风险背景</span>
        </div>
      </div>

      <aside class="anatomy-3d__rail" aria-label="三维证据摘要">
        <div class="anatomy-3d__rail-title">
          <span>Holographic evidence pipeline</span>
          <strong>三维证据接入层</strong>
        </div>
        <dl class="anatomy-3d__rail-grid">
          <div>
            <dt>模型来源</dt>
            <dd>{{ modelSourceLabel }}</dd>
          </div>
          <div>
            <dt>显示模式</dt>
            <dd>X-ray 全息</dd>
          </div>
          <div>
            <dt>荧光映射</dt>
            <dd>2D ROI 投影</dd>
          </div>
          <div>
            <dt>接入状态</dt>
            <dd>{{ registrationLabel }}</dd>
          </div>
        </dl>
        <div class="anatomy-3d__interop" aria-label="三维模型接入流程">
          <div>
            <span>01</span>
            <strong>CT / CBCT</strong>
            <small>颌面三维数据来源</small>
          </div>
          <div>
            <span>02</span>
            <strong>3D Slicer / STL</strong>
            <small>颌骨表面模型接入</small>
          </div>
          <div>
            <span>03</span>
            <strong>ICG ROI</strong>
            <small>荧光候选区空间参考</small>
          </div>
        </div>
        <div class="anatomy-3d__hotspot-list">
          <button
            v-for="hotspot in normalizedHotspots"
            :key="hotspot.key"
            type="button"
            :class="['anatomy-3d__hotspot', `is-${hotspot.risk}`, { selected: selectedHotspotKey === hotspot.key }]"
            @click="selectedHotspotKey = hotspot.key"
          >
            <span>{{ hotspot.shortLabel }}</span>
            <strong>{{ hotspot.label }}</strong>
            <small>置信度 {{ Math.round(hotspot.confidence * 100) }}% · {{ riskLabels[hotspot.risk] }}</small>
          </button>
        </div>
      </aside>
    </div>

    <p class="anatomy-3d__disclaimer">
      该视图基于脱敏 STL/GLB 颌面模型进行 X-ray 风格三维展示，并叠加 ICG 候选区域空间提示；显示效果用于比赛演示和空间理解，不代表自动诊断、导航定位或精准切除边界。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import type { CandidateRegion } from "@/types/case";

interface Props {
  candidates: CandidateRegion[];
  metrics?: Record<string, unknown>;
  modeLabel?: string;
}

type RiskLevel = "high" | "medium" | "low";

interface HotspotSpec {
  key: string;
  label: string;
  shortLabel: string;
  risk: RiskLevel;
  confidence: number;
  position: THREE.Vector3;
  normal: THREE.Vector3;
  scale: number;
}

const props = withDefaults(defineProps<Props>(), {
  metrics: () => ({}),
  modeLabel: "术中融合证据",
});

const canvasHost = ref<HTMLDivElement | null>(null);
const selectedHotspotKey = ref("reference-high");
const modelSourceLabel = ref("示意颌骨模型");
const registrationLabel = ref("参考映射");
const modelLoadNote = ref("未检测到真实模型");

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

const referenceHotspots: HotspotSpec[] = [
  {
    key: "reference-high",
    label: "右侧下颌体疑似坏死边界区",
    shortLabel: "A",
    risk: "high",
    confidence: 0.88,
    position: new THREE.Vector3(1.22, -0.2, 0.44),
    normal: new THREE.Vector3(0.3, 0.1, 1).normalize(),
    scale: 0.34,
  },
  {
    key: "reference-medium",
    label: "左侧炎症活跃观察区",
    shortLabel: "B",
    risk: "medium",
    confidence: 0.64,
    position: new THREE.Vector3(-0.98, -0.28, 0.3),
    normal: new THREE.Vector3(-0.15, 0.2, 1).normalize(),
    scale: 0.28,
  },
  {
    key: "reference-low",
    label: "颏部低灌注参照区",
    shortLabel: "C",
    risk: "low",
    confidence: 0.42,
    position: new THREE.Vector3(0.0, -0.44, 0.38),
    normal: new THREE.Vector3(0, 0.15, 1).normalize(),
    scale: 0.22,
  },
];

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;
let rootGroup: THREE.Group | null = null;
let boneGroup: THREE.Group | null = null;
let hotspotGroup: THREE.Group | null = null;
let fallbackBoneGroup: THREE.Group | null = null;
let frameId = 0;
let resizeObserver: ResizeObserver | null = null;

const normalizedHotspots = computed<HotspotSpec[]>(() => {
  if (!props.candidates.length) return referenceHotspots;
  return props.candidates.slice(0, 6).map((candidate, index) => {
    const t = props.candidates.length === 1 ? 0.5 : index / Math.max(1, Math.min(props.candidates.length, 6) - 1);
    const archPoint = pointOnMandibleArch(t);
    const confidence = normalizedConfidence(candidate);
    const risk = riskFromCandidate(candidate);
    return {
      key: candidate.candidate_id,
      label: candidate.risk_type || `候选区域 ${index + 1}`,
      shortLabel: String.fromCharCode(65 + index),
      risk,
      confidence,
      position: archPoint.position,
      normal: archPoint.normal,
      scale: 0.2 + confidence * 0.2,
    };
  });
});

const riskSummary = computed(() => {
  const hotspots = normalizedHotspots.value;
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

const confidenceLabel = computed(() => {
  const hotspots = normalizedHotspots.value;
  const mean = hotspots.reduce((total, item) => total + item.confidence, 0) / Math.max(1, hotspots.length);
  return `${Math.round(mean * 100)}%`;
});

onMounted(async () => {
  await nextTick();
  initScene();
  renderHotspots();
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
  fallbackBoneGroup = null;
});

watch(normalizedHotspots, () => renderHotspots(), { deep: true });
watch(
  () => selectedHotspotKey.value,
  () => renderHotspots(),
);

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
  rootGroup.add(boneGroup);
  boneGroup.add(fallbackBoneGroup);
  rootGroup.add(hotspotGroup);

  addLights();
  buildMandible();
  buildAnatomyPlanes();
  buildReferenceStage();
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

async function loadRealAnatomyModel() {
  if (!boneGroup || !fallbackBoneGroup) return;
  const model = await findAvailableModel();
  if (!model) {
    modelSourceLabel.value = "示意颌骨模型";
    registrationLabel.value = "参考映射";
    modelLoadNote.value = "支持 3D Slicer 导出的 STL/GLB 模型";
    return;
  }

  try {
    const loaded = model.path.endsWith(".stl")
      ? await loadStlModel(model.path)
      : await loadGltfModel(model.path);
    normalizeLoadedModel(loaded);
    boneGroup.remove(fallbackBoneGroup);
    disposeObject(fallbackBoneGroup);
    fallbackBoneGroup = null;
    boneGroup.add(loaded);
    modelSourceLabel.value = model.path.endsWith(".stl") ? "Slicer/CT STL 表面模型" : "Slicer/CT GLB 模型";
    registrationLabel.value = "模型已接入";
    modelLoadNote.value = `已加载 ${model.path}`;
  } catch {
    modelSourceLabel.value = "示意颌骨模型";
    registrationLabel.value = "模型加载失败";
    modelLoadNote.value = "真实模型文件无法解析，已回退示意模型";
  }
}

async function findAvailableModel(): Promise<{ path: string } | null> {
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
        return { path };
      }
    } catch {
      // Missing local model files are expected in the default platform state.
    }
  }
  return null;
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
  if (!rootGroup) return;
  const planeMaterial = new THREE.MeshBasicMaterial({
    color: 0x4dd3ff,
    transparent: true,
    opacity: 0.12,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const sagittal = new THREE.Mesh(new THREE.PlaneGeometry(3.8, 2.2), planeMaterial);
  sagittal.rotation.y = Math.PI / 2;
  sagittal.position.x = 0;
  sagittal.position.y = 0.1;
  rootGroup.add(sagittal);
}

function buildReferenceStage() {
  if (!rootGroup) return;
  const grid = new THREE.GridHelper(5.7, 22, 0x39d7ff, 0x1c4058);
  grid.position.y = -0.93;
  grid.rotation.x = 0.05;
  rootGroup.add(grid);

  const base = new THREE.Mesh(
    new THREE.CircleGeometry(2.9, 128),
    new THREE.MeshBasicMaterial({ color: 0x0d3550, transparent: true, opacity: 0.58, side: THREE.DoubleSide }),
  );
  base.rotation.x = -Math.PI / 2;
  base.position.y = -0.96;
  rootGroup.add(base);

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
  rootGroup.add(contactGlow);

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
  rootGroup.add(outerRing);
}

function renderHotspots() {
  if (!hotspotGroup) return;
  const group = hotspotGroup;
  group.clear();
  normalizedHotspots.value.forEach((hotspot) => {
    const color = riskColors[hotspot.risk];
    const selected = selectedHotspotKey.value === hotspot.key;
    const patch = new THREE.Mesh(
      new THREE.SphereGeometry(hotspot.scale, 48, 24),
      new THREE.MeshPhysicalMaterial({
        color,
        emissive: color,
        emissiveIntensity: selected ? 1.1 : 0.72,
        transparent: true,
        opacity: selected ? 0.86 : 0.68,
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
        opacity: selected ? 0.22 : 0.12,
        depthWrite: false,
      }),
    );
    halo.position.copy(hotspot.position).addScaledVector(hotspot.normal, 0.025);
    halo.scale.set(1.65, 0.2, 0.92);
    orientPatchToNormal(halo, hotspot.normal);
    group.add(halo);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(hotspot.scale * 1.02, 0.012, 10, 72),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: selected ? 0.95 : 0.48 }),
    );
    ring.position.copy(hotspot.position).addScaledVector(hotspot.normal, 0.05);
    orientPatchToNormal(ring, hotspot.normal);
    group.add(ring);
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

function mandibleCurve() {
  return new THREE.CatmullRomCurve3([
    new THREE.Vector3(-1.9, 0.02, -0.08),
    new THREE.Vector3(-1.42, -0.12, 0.16),
    new THREE.Vector3(-0.72, -0.28, 0.34),
    new THREE.Vector3(0, -0.36, 0.42),
    new THREE.Vector3(0.72, -0.28, 0.34),
    new THREE.Vector3(1.42, -0.12, 0.16),
    new THREE.Vector3(1.9, 0.02, -0.08),
  ]);
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

function numberFromMetadata(metadata: Record<string, unknown> | undefined, key: string): number | null {
  const value = metadata?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
</script>

<style scoped>
.anatomy-3d {
  position: relative;
  overflow: hidden;
  border: 1px solid #8bd9ff;
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(10, 27, 45, 0.98), rgba(6, 17, 29, 0.98) 48%, rgba(13, 36, 47, 0.98)),
    #07131f;
  box-shadow:
    0 0 0 1px rgba(71, 208, 255, 0.1) inset,
    0 18px 42px rgba(7, 19, 31, 0.2),
    0 0 34px rgba(62, 189, 255, 0.16);
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
  padding: 18px 20px 14px;
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

.anatomy-3d__status small {
  color: #97b8ca;
  font-size: 12px;
  font-weight: 800;
}

.anatomy-3d__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  min-height: 540px;
}

.anatomy-3d__viewport {
  position: relative;
  min-height: 540px;
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
  min-height: 540px;
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

.anatomy-3d__legend .high {
  background: #d83b3e;
}

.anatomy-3d__legend .medium {
  background: #d88b18;
}

.anatomy-3d__legend .low {
  background: #15966a;
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
  overflow: hidden;
  color: #f4fbff;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
    border-top: 1px solid #e3ebf3;
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
    min-height: 430px;
  }

  .anatomy-3d__legend {
    top: auto;
    right: 10px;
    bottom: 158px;
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
</style>
