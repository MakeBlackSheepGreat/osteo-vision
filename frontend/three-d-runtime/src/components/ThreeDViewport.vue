<template>
  <section class="three-d-viewport" :data-state="renderState" aria-label="三维模型渲染视口">
    <div v-if="hasModel" ref="canvasHost" class="three-d-viewport__canvas" @pointerup="selectMarkerFromPointer"></div>
    <div v-else class="three-d-viewport__empty" role="status">
      <strong>没有可渲染的三维模型</strong>
      <span>场景快照保留 L0/L1/L2 状态和医生复核边界。</span>
    </div>
    <div v-if="renderState === 'loading'" class="three-d-viewport__overlay" role="status">
      <strong>正在校验并加载模型</strong>
      <span>{{ renderMessage }}</span>
    </div>
    <div v-if="renderState === 'failed'" class="three-d-viewport__failure" role="status">
      <strong>三维渲染已安全降级</strong>
      <span>{{ renderMessage }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import { resolveAssetUrl } from "../services/threeDRuntimeClient";
import { canRenderSpatialCandidateMarker, canRenderSpatialCandidateMarkers, spatialCandidatePoint } from "../sceneSafety";
import type { RuntimeCandidate, SelectedCandidate, ThreeDRuntimeSnapshot } from "../types";

type RenderState = "loading" | "ready" | "failed" | "reference";

const MAX_MODEL_BYTES = 256 * 1024 * 1024;
const RENDERING_FAILURE_MESSAGES: Record<string, string> = {
  gltf_not_supported_by_isolated_renderer:
    "当前 GLTF 模型可能依赖外部二进制或纹理资源，独立三维运行时已安全降级；场景快照和医生复核路径仍可用。",
};

const props = withDefaults(
  defineProps<{
    snapshot: ThreeDRuntimeSnapshot | null;
    autoRotate?: boolean;
  }>(),
  { autoRotate: false },
);

const emit = defineEmits<{
  candidateSelected: [candidate: SelectedCandidate];
  state: [payload: { state: RenderState; message: string }];
}>();

const canvasHost = ref<HTMLDivElement | null>(null);
const renderState = ref<RenderState>("reference");
const renderMessage = ref("等待受控场景快照。");
const hasModel = computed(() => Boolean(props.snapshot?.model_asset));

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let modelRoot: THREE.Object3D | null = null;
let markerRoot: THREE.Group | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationFrame: number | null = null;
let raycaster: THREE.Raycaster | null = null;
let loadGeneration = 0;
let contextLostHandler: ((event: Event) => void) | null = null;
let assetDownloadController: AbortController | null = null;

watch(
  () => props.snapshot,
  () => void loadSnapshot(),
  { immediate: true },
);

watch(
  () => props.autoRotate,
  (value) => {
    if (controls) controls.autoRotate = value;
  },
);

onBeforeUnmount(() => disposeRenderer());

async function loadSnapshot() {
  const generation = ++loadGeneration;
  assetDownloadController?.abort();
  assetDownloadController = null;
  await nextTick();
  if (generation !== loadGeneration) return;
  clearSceneObjects();
  if (!props.snapshot?.model_asset) {
    disposeRenderer();
    setRenderState("reference", "场景未提供受控模型资产，保持证据参考状态。");
    return;
  }

  try {
    setRenderState("loading", "正在检查 WebGL、模型格式和校验和。");
    const asset = props.snapshot.model_asset;
    const format = normalizedFormat(asset.format, asset.file_name);
    if (asset.rendering_status === "unsupported_format" || format === "gltf") {
      disposeRenderer();
      setRenderState("failed", unsupportedModelMessage(asset));
      return;
    }
    if (!format) {
      throw new Error("场景模型格式无效；独立运行时仅可加载受控 STL 或内嵌 GLB。");
    }
    if (!asset.sha256 || !/^[a-f0-9]{64}$/i.test(asset.sha256)) {
      throw new Error("场景快照缺少有效模型 SHA256，已拒绝渲染。");
    }
    if (typeof asset.size_bytes === "number" && asset.size_bytes > MAX_MODEL_BYTES) {
      throw new Error("模型超过独立运行时的安全加载上限。");
    }

    initializeRenderer();
    const controller = new AbortController();
    assetDownloadController = controller;
    const data = await downloadAndVerifyAsset(assetUrl(asset), asset.sha256, asset.size_bytes, controller.signal);
    if (generation !== loadGeneration) return;
    const object = await parseModel(data, format);
    if (generation !== loadGeneration) {
      disposeObject(object);
      return;
    }
    modelRoot = object;
    scene?.add(modelRoot);
    frameModel(modelRoot);
    addCandidateMarkers(props.snapshot.candidate_regions ?? []);
    setRenderState("ready", "模型校验完成；候选区按当前配准安全状态显示。");
  } catch (error) {
    if (generation !== loadGeneration) return;
    disposeRenderer();
    setRenderState("failed", error instanceof Error ? error.message : "模型加载失败。");
  } finally {
    if (generation === loadGeneration) assetDownloadController = null;
  }
}

function initializeRenderer() {
  if (renderer && scene && camera && controls) return;
  if (!canvasHost.value) throw new Error("三维视口尚未准备完成。");
  if (!supportsWebGl()) throw new Error("当前浏览器或工作站未提供 WebGL，无法启动独立三维运行时。");

  const host = canvasHost.value;
  const width = Math.max(host.clientWidth, 480);
  const height = Math.max(host.clientHeight, 420);
  const canvas = document.createElement("canvas");
  contextLostHandler = (event) => {
    event.preventDefault();
    setRenderState("failed", "WebGL 上下文已丢失，渲染已停止并保留场景快照证据。");
    disposeRenderer({ releaseContext: false });
  };
  canvas.addEventListener("webglcontextlost", contextLostHandler);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  renderer.setClearColor(0x111a1e, 1);
  host.replaceChildren(canvas);

  scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xd7f2ef, 0x1d2830, 2.1));
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
  keyLight.position.set(60, 80, 90);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0x63d6c8, 1.3);
  fillLight.position.set(-55, 30, -40);
  scene.add(fillLight);

  camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 5000);
  camera.position.set(130, 105, 170);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.autoRotate = props.autoRotate;
  controls.autoRotateSpeed = 0.8;
  controls.target.set(0, 0, 0);
  raycaster = new THREE.Raycaster();

  resizeObserver = new ResizeObserver(() => resizeRenderer());
  resizeObserver.observe(host);
  animate();
}

function supportsWebGl(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

async function downloadAndVerifyAsset(
  url: string,
  expectedSha256: string,
  expectedSize: number | null | undefined,
  signal: AbortSignal,
): Promise<ArrayBuffer> {
  const response = await fetch(url, { headers: { Accept: "application/octet-stream" }, signal });
  if (!response.ok) throw new Error(`受控模型下载失败，状态码 ${response.status}。`);
  const body = await response.arrayBuffer();
  if (body.byteLength === 0) throw new Error("受控模型文件为空。");
  if (body.byteLength > MAX_MODEL_BYTES) throw new Error("下载后的模型超过独立运行时安全上限。");
  if (typeof expectedSize === "number" && expectedSize !== body.byteLength) {
    throw new Error("模型大小与场景快照不一致，已拒绝渲染。");
  }
  const actualSha256 = await sha256(body);
  if (actualSha256.toLowerCase() !== expectedSha256.toLowerCase()) {
    throw new Error("模型 SHA256 与场景快照不一致，已拒绝渲染。");
  }
  return body;
}

async function sha256(data: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error("浏览器未提供 SubtleCrypto，无法验证模型 SHA256。");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function parseModel(data: ArrayBuffer, format: "stl" | "glb"): Promise<THREE.Object3D> {
  if (format === "stl") {
    const geometry = new STLLoader().parse(data);
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color: 0x8acbc4,
      roughness: 0.64,
      metalness: 0.05,
      transparent: true,
      opacity: 0.96,
    });
    return new THREE.Mesh(geometry, material);
  }

  return new Promise<THREE.Object3D>((resolve, reject) => {
    const loader = new GLTFLoader();
    loader.parse(
      data,
      "",
      (result) => resolve(result.scene),
      (error) => reject(error instanceof Error ? error : new Error("GLB 模型解析失败。")),
    );
  });
}

function addCandidateMarkers(candidates: RuntimeCandidate[]) {
  if (!scene || !modelRoot || !candidates.length || !canRenderSpatialCandidateMarkers(props.snapshot)) return;
  markerRoot = new THREE.Group();
  const bounds = new THREE.Box3().setFromObject(modelRoot);
  const size = bounds.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() * 0.14, 5);
  candidates.forEach((candidate) => {
    if (!canRenderSpatialCandidateMarker(props.snapshot, candidate)) return;
    const position = candidatePosition(candidate);
    if (!position) return;
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 22, 16),
      new THREE.MeshStandardMaterial({ color: candidateColor(candidate), emissive: candidateColor(candidate), emissiveIntensity: 0.24 }),
    );
    marker.position.copy(position);
    marker.userData.candidate = candidate;
    markerRoot?.add(marker);
  });
  scene.add(markerRoot);
}

function candidatePosition(candidate: RuntimeCandidate): THREE.Vector3 | null {
  const point = spatialCandidatePoint(candidate);
  return point ? new THREE.Vector3(point[0], point[1], point[2]) : null;
}

function candidateColor(candidate: RuntimeCandidate): number {
  const type = String(candidate.risk_type || "").toLowerCase();
  if (type.includes("high") || type.includes("risk")) return 0xe86c67;
  if (type.includes("uncertain") || type.includes("boundary")) return 0xe0af50;
  return 0x3ec7b5;
}

function frameModel(object: THREE.Object3D) {
  if (!camera || !controls) return;
  const bounds = new THREE.Box3().setFromObject(object);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const distance = Math.max(size.length() * 1.35, 90);
  camera.position.copy(center.clone().add(new THREE.Vector3(distance * 0.7, distance * 0.48, distance * 0.72)));
  camera.near = Math.max(distance / 1000, 0.01);
  camera.far = Math.max(distance * 15, 1000);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function selectMarkerFromPointer(event: PointerEvent) {
  if (!renderer || !camera || !raycaster || !markerRoot) return;
  const rect = renderer.domElement.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const pointer = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(markerRoot.children, false)[0];
  const candidate = hit?.object.userData.candidate as RuntimeCandidate | undefined;
  if (!candidate) return;
  emit("candidateSelected", {
    candidate_id: candidate.candidate_id,
    frame_key: String(candidate.frame_key ?? ""),
    frame_index: finiteNumber(candidate.frame_index),
    timestamp_sec: finiteNumber(candidate.timestamp_sec),
  });
}

function resizeRenderer() {
  if (!renderer || !camera || !canvasHost.value) return;
  const width = Math.max(canvasHost.value.clientWidth, 480);
  const height = Math.max(canvasHost.value.clientHeight, 420);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  if (!renderer || !scene || !camera) return;
  animationFrame = window.requestAnimationFrame(animate);
  controls?.update();
  renderer.render(scene, camera);
}

function clearSceneObjects() {
  if (modelRoot) {
    modelRoot.removeFromParent();
    disposeObject(modelRoot);
    modelRoot = null;
  }
  if (markerRoot) {
    markerRoot.removeFromParent();
    disposeObject(markerRoot);
    markerRoot = null;
  }
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((node) => {
    const mesh = node as THREE.Mesh;
    mesh.geometry?.dispose?.();
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    materials.filter(Boolean).forEach((material) => material.dispose());
  });
}

function disposeRenderer({ releaseContext = true }: { releaseContext?: boolean } = {}) {
  loadGeneration += 1;
  assetDownloadController?.abort();
  assetDownloadController = null;
  if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
  animationFrame = null;
  resizeObserver?.disconnect();
  resizeObserver = null;
  clearSceneObjects();
  if (renderer) {
    renderer.domElement.removeEventListener("webglcontextlost", contextLostHandler ?? (() => undefined));
    renderer.renderLists.dispose();
    renderer.dispose();
    if (releaseContext) renderer.forceContextLoss();
  }
  controls?.dispose();
  scene = null;
  camera = null;
  controls = null;
  renderer = null;
  raycaster = null;
  contextLostHandler = null;
}

function assetUrl(asset: NonNullable<ThreeDRuntimeSnapshot["model_asset"]>): string {
  return resolveAssetUrl(asset.url);
}

function normalizedFormat(format: string | null | undefined, fileName: string | null | undefined): "stl" | "glb" | "gltf" | "" {
  const value = String(format || fileName?.split(".").at(-1) || "").toLowerCase().replace(".", "");
  return value === "stl" || value === "glb" || value === "gltf" ? value : "";
}

function unsupportedModelMessage(asset: NonNullable<ThreeDRuntimeSnapshot["model_asset"]>): string {
  const failureCode = asset.rendering_failure_reason?.trim().toLowerCase();
  if (failureCode) {
    return (
      RENDERING_FAILURE_MESSAGES[failureCode] ||
      "模型已由后端标记为当前独立运行时不可渲染，已安全降级；场景快照和医生复核路径仍可用。"
    );
  }
  if (asset.format === "gltf") {
    return RENDERING_FAILURE_MESSAGES.gltf_not_supported_by_isolated_renderer;
  }
  return "模型已由后端标记为当前独立运行时不可渲染，已安全降级；场景快照和医生复核路径仍可用。";
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function setRenderState(state: RenderState, message: string) {
  renderState.value = state;
  renderMessage.value = message;
  emit("state", { state, message });
}
</script>

<style scoped>
.three-d-viewport {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid var(--runtime-border);
  background-color: var(--runtime-surface-muted);
  background-image:
    linear-gradient(var(--runtime-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--runtime-grid) 1px, transparent 1px);
  background-size: 28px 28px;
}

.three-d-viewport__canvas {
  min-height: 560px;
  touch-action: none;
}

.three-d-viewport__canvas :deep(canvas) {
  display: block;
  width: 100%;
  height: 560px;
  cursor: grab;
}

.three-d-viewport__canvas :deep(canvas):active {
  cursor: grabbing;
}

.three-d-viewport__empty,
.three-d-viewport__overlay,
.three-d-viewport__failure {
  display: grid;
  gap: 8px;
  place-content: center;
  min-height: 560px;
  padding: 28px;
  text-align: center;
}

.three-d-viewport__empty {
  color: var(--runtime-text-muted);
}

.three-d-viewport__empty strong,
.three-d-viewport__overlay strong,
.three-d-viewport__failure strong {
  color: var(--runtime-text);
  font-size: 17px;
}

.three-d-viewport__overlay {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--runtime-surface-muted) 88%, transparent);
  color: var(--runtime-text-muted);
  pointer-events: none;
}

.three-d-viewport__failure {
  position: absolute;
  inset: 0;
  color: var(--runtime-warning-text);
  background: var(--runtime-warning-bg);
}
</style>
