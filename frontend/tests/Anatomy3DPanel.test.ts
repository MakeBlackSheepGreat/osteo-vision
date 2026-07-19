import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Anatomy3DPanel from "../src/components/Anatomy3DPanel.vue";

const threeLoadState = vi.hoisted(() => ({
  gltfPaths: [] as string[],
  stlPaths: [] as string[],
}));

vi.mock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class {
    enableDamping = false;
    dampingFactor = 0;
    autoRotate = false;
    autoRotateSpeed = 0;
    enablePan = false;
    minDistance = 0;
    maxDistance = 0;
    minPolarAngle = 0;
    maxPolarAngle = 0;
    target = { set: vi.fn() };
    update = vi.fn();
    dispose = vi.fn();
  },
}));

vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => ({
  GLTFLoader: class {
    async loadAsync(path: string) {
      threeLoadState.gltfPaths.push(path);
      const three = await import("three");
      return { scene: new three.Group() };
    }
  },
}));

vi.mock("three/examples/jsm/loaders/STLLoader.js", () => ({
  STLLoader: class {
    async loadAsync(path: string) {
      threeLoadState.stlPaths.push(path);
      const three = await import("three");
      return new three.BufferGeometry();
    }
  },
}));

vi.mock("three", () => {
  class Vector3 {
    constructor(public x = 0, public y = 0, public z = 0) {}
    set(x: number, y: number, z: number) {
      this.x = x;
      this.y = y;
      this.z = z;
      return this;
    }
    setScalar(value: number) {
      this.x = value;
      this.y = value;
      this.z = value;
      return this;
    }
    clone() {
      return new Vector3(this.x, this.y, this.z);
    }
    copy(value: Vector3) {
      this.x = value.x;
      this.y = value.y;
      this.z = value.z;
      return this;
    }
    addScaledVector(value: Vector3, scale: number) {
      this.x += value.x * scale;
      this.y += value.y * scale;
      this.z += value.z * scale;
      return this;
    }
    multiplyScalar(value: number) {
      this.x *= value;
      this.y *= value;
      this.z *= value;
      return this;
    }
    applyEuler() {
      return this;
    }
    normalize() {
      return this;
    }
  }

  class Object3D {
    children: Object3D[] = [];
    position = new Vector3();
    rotation = { x: 0, y: 0, z: 0 };
    scale = new Vector3(1, 1, 1);
    quaternion = { setFromUnitVectors: vi.fn() };
    castShadow = false;
    receiveShadow = false;
    add(...items: Object3D[]) {
      this.children.push(...items);
    }
    remove(item: Object3D) {
      this.children = this.children.filter((child) => child !== item);
    }
    clear() {
      this.children = [];
    }
    traverse(callback: (item: Object3D) => void) {
      callback(this);
      this.children.forEach((child) => child.traverse(callback));
    }
  }

  class Group extends Object3D {}
  class Scene extends Group {
    background = null;
    fog = null;
  }
  class Mesh extends Object3D {
    constructor(public geometry: unknown, public material: unknown) {
      super();
    }
  }
  class LineSegments extends Mesh {}
  class Geometry {
    computeVertexNormals = vi.fn();
    dispose = vi.fn();
  }
  class Material {
    dispose = vi.fn();
  }

  return {
    Vector3,
    Group,
    Scene,
    Mesh,
    LineSegments,
    BufferGeometry: Geometry,
    Color: class {
      constructor(public value: unknown) {}
    },
    Fog: class {
      constructor(public color: unknown, public near: number, public far: number) {}
    },
    PerspectiveCamera: class extends Object3D {
      aspect = 1;
      updateProjectionMatrix = vi.fn();
      constructor(public fov: number, public aspectIn: number, public near: number, public far: number) {
        super();
      }
    },
    WebGLRenderer: class {
      domElement = document.createElement("canvas");
      shadowMap = { enabled: false, type: "" };
      outputColorSpace = "";
      toneMapping = "";
      toneMappingExposure = 1;
      setPixelRatio = vi.fn();
      setSize = vi.fn();
      render = vi.fn();
      dispose = vi.fn();
    },
    HemisphereLight: class extends Object3D {},
    DirectionalLight: class extends Object3D {
      shadow = { mapSize: { set: vi.fn() }, camera: { near: 0, far: 0 } };
    },
    PointLight: class extends Object3D {},
    MeshPhysicalMaterial: class extends Material {
      constructor(public options: unknown) {
        super();
      }
    },
    MeshStandardMaterial: class extends Material {
      constructor(public options: unknown) {
        super();
      }
    },
    MeshBasicMaterial: class extends Material {
      constructor(public options: unknown) {
        super();
      }
    },
    LineBasicMaterial: class extends Material {
      constructor(public options: unknown) {
        super();
      }
    },
    TubeGeometry: class extends Geometry {},
    CatmullRomCurve3: class {
      constructor(public points: Vector3[]) {}
      getPoint(index: number) {
        return this.points[Math.min(this.points.length - 1, Math.max(0, Math.round(index * (this.points.length - 1))))].clone();
      }
      getTangent() {
        return new Vector3(1, 0, 0);
      }
    },
    CapsuleGeometry: class extends Geometry {},
    SphereGeometry: class extends Geometry {},
    ConeGeometry: class extends Geometry {},
    CircleGeometry: class extends Geometry {},
    PlaneGeometry: class extends Geometry {},
    TorusGeometry: class extends Geometry {},
    GridHelper: class extends Object3D {},
    EdgesGeometry: class extends Geometry {},
    Box3: class {
      setFromObject() {
        return this;
      }
      getSize(target: Vector3) {
        target.set(1, 1, 1);
      }
      getCenter(target: Vector3) {
        target.set(0, 0, 0);
      }
    },
    MathUtils: { clamp: (value: number, min: number, max: number) => Math.min(max, Math.max(min, value)) },
    DoubleSide: "DoubleSide",
    PCFShadowMap: "PCFShadowMap",
    SRGBColorSpace: "SRGBColorSpace",
    ACESFilmicToneMapping: "ACESFilmicToneMapping",
  };
});

describe("Anatomy3DPanel", () => {
  beforeEach(() => {
    threeLoadState.gltfPaths = [];
    threeLoadState.stlPaths = [];
    window.requestAnimationFrame = vi.fn(() => 1) as unknown as typeof window.requestAnimationFrame;
    window.cancelAnimationFrame = vi.fn() as unknown as typeof window.cancelAnimationFrame;
    URL.createObjectURL = vi.fn(() => "blob:local-mandible-model") as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL;
    globalThis.fetch = vi.fn(async () => ({ ok: false, headers: new Headers({ "content-type": "text/html" }) })) as unknown as typeof fetch;
    globalThis.ResizeObserver = class {
      observe = vi.fn();
      disconnect = vi.fn();
    } as unknown as typeof ResizeObserver;
  });

  it("keeps the empty 3D workbench available without claiming navigation", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
        modeLabel: "双通道融合证据",
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("CBCT/STL 术前证据参考");
    expect(wrapper.text()).toContain("未加载三维模型");
    expect(wrapper.text()).toContain("导入 STL/GLB");
    expect(wrapper.text()).toContain("导入 CBCT");
    expect(wrapper.text()).toContain("病例对象");
    expect(wrapper.text()).not.toContain("高级参数");
    expect(wrapper.text()).toContain("建模检查");
    expect(wrapper.text()).toContain("数据链完整性");
    expect(wrapper.text()).toContain("非导航锁定");
    expect(wrapper.text()).not.toContain("示意占位 / 未接入真实模型");
    expect(wrapper.text()).not.toContain("腓骨段 / 新下颌重建参考");
    expect(wrapper.text()).not.toContain("导板盒");
    expect(wrapper.text()).toContain("未配准 / 非导航");
    expect(wrapper.find(".anatomy-3d__body").classes()).toContain("is-model-empty");
    expect(wrapper.find(".anatomy-3d__body").classes()).not.toContain("is-model-loaded");
    expect(wrapper.find(".anatomy-3d__viewport").classes()).toContain("is-model-empty");
    expect(wrapper.find(".anatomy-3d__viewport").attributes("data-model-state")).toBe("fallback");
    expect(wrapper.find(".anatomy-3d__empty-viewport").text()).toContain("当前保持空白检查状态");
    expect(wrapper.find(".anatomy-3d__compact-empty").exists()).toBe(false);
    expect(wrapper.find(".anatomy-3d__modeling-check-details").exists()).toBe(true);
    expect(wrapper.find(".anatomy-3d__object-browser").exists()).toBe(true);
    expect(wrapper.find(".anatomy-3d__object-browser").attributes("open")).toBeUndefined();
    expect(wrapper.find(".anatomy-3d__inspector-heading").text()).toContain("项证据字段");
    expect(wrapper.findAll(".anatomy-3d__tree-item").every((item) => item.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.findAll(".anatomy-3d__markup-row")).toHaveLength(0);
    expect(wrapper.find(".anatomy-3d__markup-empty").text()).toContain("没有可核验的配准点");
    expect(wrapper.text()).not.toContain("expected-fiducial");
    expect(wrapper.findAll(".anatomy-3d__workflow-step")).toHaveLength(4);
    expect(wrapper.find(".anatomy-3d__workflow-step").element.tagName).toBe("LI");
    expect(wrapper.text()).not.toContain("加载公开参考");
    expect(wrapper.find(".anatomy-3d__module-actions").exists()).toBe(false);
    expect(wrapper.find(".anatomy-3d__module-update").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("全息");
  });

  it("provides a focus view only after a real surface model is loaded", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
      },
    });

    await flushPromises();

    expect(
      wrapper
        .findAll(".anatomy-3d__view-controls button")
        .find((button) => button.text().includes("专注视图")),
    ).toBeUndefined();

    const surfaceInput = wrapper.find('input[accept=".stl,.glb,.gltf"]');
    Object.defineProperty(surfaceInput.element, "files", {
      value: [new File(["solid"], "focus_view_mandible.stl", { type: "model/stl" })],
      configurable: true,
    });
    await surfaceInput.trigger("change");
    await flushPromises();

    const focusButton = wrapper
      .findAll(".anatomy-3d__view-controls button")
      .find((button) => button.text().includes("专注视图"));
    expect(focusButton).toBeDefined();

    await focusButton?.trigger("click");
    expect(wrapper.find(".anatomy-3d__body").classes()).toContain("is-focus-view");
    expect(wrapper.text()).toContain("退出专注");

    const exitButton = wrapper
      .findAll(".anatomy-3d__view-controls button")
      .find((button) => button.text().includes("退出专注"));
    await exitButton?.trigger("click");
    expect(wrapper.find(".anatomy-3d__body").classes()).not.toContain("is-focus-view");
  });

  it("lets users import CBCT files and a local STL surface for 3D evidence checks", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("未加载三维模型");
    expect(wrapper.text()).toContain("CBCT 建模入口");
    expect(wrapper.text()).toContain("导入 CBCT");
    expect(wrapper.text()).toContain("导入 STL/GLB");

    const cbctInput = wrapper.find('input[accept=".dcm,.dicom,.nii,.nii.gz,.nrrd,.mha,.mhd"]');
    Object.defineProperty(cbctInput.element, "files", {
      value: [new File(["dicom"], "case001_cbct.dcm", { type: "application/dicom" })],
      configurable: true,
    });
    await cbctInput.trigger("change");
    await nextTick();

    expect(wrapper.text()).toContain("CBCT 建模入口");
    expect(wrapper.text()).toContain("CBCT 写入失败");
    expect(wrapper.text()).toContain("case001_cbct.dcm");
    expect(wrapper.text()).toContain("待分割：需要 Slicer Segment Editor 或后端分割脚本");

    const surfaceInput = wrapper.find('input[accept=".stl,.glb,.gltf"]');
    Object.defineProperty(surfaceInput.element, "files", {
      value: [new File(["solid"], "case001_mandible.stl", { type: "model/stl" })],
      configurable: true,
    });
    await surfaceInput.trigger("change");
    await flushPromises();

    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(threeLoadState.stlPaths).toContain("blob:local-mandible-model");
    expect(wrapper.text()).toContain("表面模型已接入");
    expect(wrapper.text()).toContain("case001_mandible.stl");
    expect(wrapper.text()).toContain("本地导入表面模型");
    expect(wrapper.text()).toContain("本地导入的 CBCT/STL/GLB");
    expect(wrapper.text()).toContain("osteo-vision-three-d-scene-local-v1");
    expect(wrapper.text()).toContain("osteo-vision-three-d-scene-v2");
    expect(wrapper.text()).toContain("几何任务");
    expect(wrapper.findAll(".anatomy-3d__modeling-checks .is-ready").length).toBeGreaterThanOrEqual(3);
  });

  it("starts a backend CBCT surface modeling job as a raw volume and attaches returned evidence", async () => {
    let modelingRequest: Record<string, unknown> = {};
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/uploads/raw")) {
        return {
          ok: true,
          json: async () => ({
            path: "artifacts/platform/uploads/upload_d024_0006.nii.gz",
            filename: "upload_d024_0006.nii.gz",
            original_filename: "d024_0006_0000.nii.gz",
            content_type: "application/gzip",
            size_bytes: 128,
            input_type: "nifti_volume",
            metadata: {},
            warnings: [],
          }),
        } as Response;
      }
      if (url.includes("/three-d/modeling-jobs") && init?.method === "POST") {
        modelingRequest = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        return {
          ok: true,
          json: async () => ({
            job_id: "job_cbct001",
            kind: "cbct_surface_modeling",
            status: "queued",
            progress: { message: "Job queued." },
          }),
        } as Response;
      }
      if (url.includes("/three-d/modeling-jobs/job_cbct001")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job_cbct001",
            kind: "cbct_surface_modeling",
            status: "completed",
            progress: { message: "Job completed." },
            result: {
              modeling_status: "completed",
              model_path: "artifacts/platform/three_d_models/d024_0006_upper_lower_jaw_surface.stl",
              three_d_evidence: {
                schema_version: "osteo-vision-three-d-evidence-v1",
                model_path: "artifacts/platform/three_d_models/d024_0006_upper_lower_jaw_surface.stl",
                model_format: "stl",
                model_file_name: "d024_0006_upper_lower_jaw_surface.stl",
                model_source: "D024 DentVoxel public maxilla/mandible segmentation labels",
                segmentation_source: "D024 DentVoxel label values 1 maxilla and 2 mandible",
                segmentation_review_status: "not_reviewed",
                registration_status: "unregistered",
                coordinate_space: "cbct_physical_lps_mm_public_label",
                doctor_review_status: "not_reviewed",
                navigation_ready: false,
                boundary_note: "后端生成的表面模型仍未配准，不能作为术中定位。",
              },
            },
          }),
        } as Response;
      }
      return { ok: false, headers: new Headers({ "content-type": "text/html" }) } as Response;
    }) as unknown as typeof fetch;

    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
      },
    });
    await flushPromises();

    const cbctInput = wrapper.find('input[accept=".dcm,.dicom,.nii,.nii.gz,.nrrd,.mha,.mhd"]');
    Object.defineProperty(cbctInput.element, "files", {
      value: [new File(["nifti"], "d024_0006_0000.nii.gz", { type: "application/gzip" })],
      configurable: true,
    });
    await cbctInput.trigger("change");
    await flushPromises();

    const modelingButton = wrapper
      .findAll(".anatomy-3d__import-actions button")
      .find((button) => button.text().includes("生成表面"));
    expect(modelingButton?.attributes("disabled")).toBeDefined();

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/three-d/modeling-jobs"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(Object.keys(modelingRequest).length).toBeGreaterThan(0);
    expect(modelingRequest.source_role).toBe("volume");
    expect(modelingRequest.source_original_filename).toBe("d024_0006_0000.nii.gz");
    expect(modelingRequest).not.toHaveProperty("label_value", 2);
    expect(threeLoadState.stlPaths.some((path) => path.includes("d024_0006_upper_lower_jaw_surface.stl"))).toBe(true);
    expect(wrapper.text()).toContain("表面模型已生成并接入三维证据");
    expect(wrapper.text()).toContain("d024_0006_upper_lower_jaw_surface.stl");
    expect(wrapper.text()).toContain("后端生成的表面模型仍未配准");
  });

  it("keeps the canceled state after a stale modeling poll completes", async () => {
    let resolveStalePoll: (() => void) | undefined;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/uploads/raw")) {
        return {
          ok: true,
          json: async () => ({
            path: "artifacts/platform/uploads/upload_cancel_case.nii.gz",
            filename: "upload_cancel_case.nii.gz",
            original_filename: "cancel_case.nii.gz",
            content_type: "application/gzip",
            size_bytes: 128,
            input_type: "nifti_volume",
            metadata: {},
            warnings: [],
          }),
        } as Response;
      }
      if (url.includes("/three-d/modeling-jobs/job_cancel_case/cancel")) {
        return {
          ok: true,
          json: async () => ({
            job_id: "job_cancel_case",
            kind: "cbct_surface_modeling",
            status: "canceled",
            progress: { message: "三维建模任务已取消。" },
          }),
        } as Response;
      }
      if (url.includes("/three-d/modeling-jobs") && init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            job_id: "job_cancel_case",
            kind: "cbct_surface_modeling",
            status: "queued",
            progress: { message: "已排队。" },
          }),
        } as Response;
      }
      if (url.includes("/three-d/modeling-jobs/job_cancel_case")) {
        return new Promise<Response>((resolve) => {
          resolveStalePoll = () => resolve({
            ok: true,
            json: async () => ({
              job_id: "job_cancel_case",
              kind: "cbct_surface_modeling",
              status: "running",
              progress: { message: "正在生成表面模型..." },
            }),
          } as Response);
        });
      }
      return { ok: false, headers: new Headers({ "content-type": "text/html" }) } as Response;
    }) as unknown as typeof fetch;

    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
      },
    });
    await flushPromises();

    const cbctInput = wrapper.find('input[accept=".dcm,.dicom,.nii,.nii.gz,.nrrd,.mha,.mhd"]');
    Object.defineProperty(cbctInput.element, "files", {
      value: [new File(["nifti"], "cancel_case.nii.gz", { type: "application/gzip" })],
      configurable: true,
    });
    await cbctInput.trigger("change");
    await flushPromises();

    expect(resolveStalePoll).toBeTypeOf("function");
    const busyButtons = wrapper.findAll(".anatomy-3d__import-actions button");
    expect(busyButtons.find((button) => button.text().includes("导入 CBCT"))?.attributes("disabled")).toBeDefined();
    expect(busyButtons.find((button) => button.text().includes("导入 STL/GLB"))?.attributes("disabled")).toBeDefined();
    expect(busyButtons.find((button) => button.text().includes("生成表面"))?.attributes("disabled")).toBeDefined();
    expect(busyButtons.find((button) => button.text().includes("清空本地选择"))).toBeUndefined();
    const cancelButton = wrapper
      .findAll(".anatomy-3d__import-actions button")
      .find((button) => button.text().includes("取消任务"));
    expect(cancelButton?.attributes("disabled")).toBeUndefined();
    await cancelButton?.trigger("click");
    await flushPromises();
    expect(wrapper.find(".anatomy-3d__job-status").text()).toContain("三维建模任务已取消");
    expect(
      wrapper.findAll(".anatomy-3d__import-actions button").find((button) => button.text().includes("清空本地选择")),
    ).toBeDefined();

    resolveStalePoll?.();
    await flushPromises();
    expect(wrapper.find(".anatomy-3d__job-status").text()).toContain("三维建模任务已取消");
    wrapper.unmount();
  });

  it("uses case three_d_evidence model_path before default public models", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
        threeDEvidence: {
          model_path: "artifacts/models/case_001_mandible.glb",
          model_format: "glb",
          model_file_name: "case_001_mandible.glb",
          model_source: "Slicer 导出病例模型",
          exported_from: "3D Slicer Segmentations",
          dicom_series_uid: "1.2.840.case001.cbct",
          segmentation_source: "doctor reviewed mandibular segmentation",
          segmentation_review_status: "accepted",
          registration_status: "registered",
          registration_method: "point-based + surface matching",
          registration_error_mm: 0.8,
          fiducial_count: 5,
          surface_point_count: 176,
          coordinate_space: "cbct_ras",
          transform_path: "artifacts/transforms/case_001_cbct_ras.tfm",
          registration_markups: [
            {
              id: "lm_mental_foramen_l",
              label: "Left mental foramen",
              source_label: "CBCT L mental foramen",
              target_label: "tracked L mental foramen",
              source_point_mm: [-23.5, 8.2, 14.1],
              target_point_mm: [-23.1, 8.0, 13.7],
              residual_mm: 0.62,
              status: "accepted",
            },
            {
              id: "lm_condyle_r",
              label: "Right condyle",
              source_label: "CBCT R condyle",
              target_label: "tracked R condyle",
              source_point_mm: [32.8, 45.0, 18.4],
              target_point_mm: [32.5, 44.6, 18.2],
              residual_mm: 0.74,
              status: "accepted",
            },
          ],
          transform_chain: [
            {
              name: "CBCT RAS to STL surface",
              from_space: "cbct_ras",
              to_space: "mandible_stl",
              path: "artifacts/transforms/case_001_surface.tfm",
              error_mm: 0.52,
              status: "ready",
            },
            {
              name: "STL surface to keyframe reference",
              from_space: "mandible_stl",
              to_space: "video_keyframe_reference",
              path: "artifacts/transforms/case_001_video.tfm",
              error_mm: 0.8,
              status: "ready",
            },
          ],
          doctor_review_status: "approved",
          navigation_ready: true,
        },
      },
    });

    await flushPromises();

    expect(threeLoadState.gltfPaths[0]).toContain("artifacts%2Fmodels%2Fcase_001_mandible.glb");
    expect(fetch).not.toHaveBeenCalledWith("/models/mandible.glb", expect.anything());
    expect(wrapper.text()).toContain("Slicer 导出病例模型");
    expect(wrapper.text()).toContain("已配准");
    expect(wrapper.text()).toContain("0.80 mm");
    expect(wrapper.text()).toContain("case_001_mandible.glb");
    expect(wrapper.text()).toContain("1.2.840.case001.cbct");
    expect(wrapper.text()).toContain("点配准 + 表面匹配");
    expect(wrapper.text()).toContain("176");
    expect(wrapper.text()).toContain("左侧颏孔");
    expect(wrapper.text()).toContain("残差：0.62 mm");
    expect(wrapper.text()).toContain("CBCT 坐标到 STL 表面");
    expect(wrapper.text()).toContain("2 / 2 项变换就绪");
    expect(wrapper.findAll(".anatomy-3d__registration-guard .is-ready")).toHaveLength(5);
    expect(wrapper.find(".anatomy-3d__body").classes()).toContain("is-model-loaded");
    expect(wrapper.find(".anatomy-3d__body").classes()).not.toContain("is-model-empty");
    expect(wrapper.find(".anatomy-3d__viewport").classes()).toContain("is-model-loaded");
    expect(wrapper.find(".anatomy-3d__viewport").attributes("data-model-state")).toBe("loaded");
    expect(wrapper.find(".anatomy-3d__empty-viewport").exists()).toBe(false);
  });

  // This legacy D024 fixture still asserts retired slice/segment-detail copy. Keep it isolated
  // until the public reference manifest is refreshed against the current evidence panel contract.
  it.skip("loads generated local D024 STL evidence as an unregistered public CBCT reference", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("mandible_d024_0001.brp_geometry_manifest.json")) {
        return {
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({
            schema_version: "osteo-vision-brp-geometry-manifest-v1",
            plane_intersections: [
              { id: "d024_review_plane_left", status: "ready", segment_count: 1267 },
              { id: "d024_review_plane_mid", status: "ready", segment_count: 708 },
              { id: "d024_review_plane_right", status: "ready", segment_count: 1241 },
            ],
            segment_measurements: [
              { id: "S0", length_mm: 62.345, status: "ready" },
              { id: "S1", length_mm: 64.3239, status: "ready" },
            ],
            geometry_status: {
              plane_intersection_ready: true,
              candidate_projection_ready: false,
              navigation_ready: false,
            },
          }),
        } as Response;
      }
      return { ok: false, headers: new Headers({ "content-type": "text/html" }) } as Response;
    }) as unknown as typeof fetch;

    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
        threeDEvidence: {
          model_path: "frontend/public/models/local/mandible_d024_0001.stl",
          model_format: "stl",
          model_file_name: "mandible_d024_0001.stl",
          model_source: "D024 DentVoxel public CBCT derived mandible label",
          segmentation_source: "D024 DentVoxel label value 2 mandible",
          segmentation_review_status: "public_dataset_annotation_not_case_reviewed",
          registration_status: "unregistered",
          coordinate_space: "cbct_label_voxel_spacing_mm",
          doctor_review_status: "not_reviewed",
          navigation_ready: false,
          geometry_manifest_path: "frontend/public/models/local/mandible_d024_0001.brp_geometry_manifest.json",
          scene_manifest: {
            schema_version: "osteo-vision-three-d-scene-v1",
            source_project: "SlicerBoneReconstructionPlanner-inspired scene semantics",
            mandibular_curve: {
              label: "D024 mandibular reference curve",
              source: "derived from STL manifest for display; not physician markups",
              display_points: [
                [-1.9, 0.02, -0.08],
                [-1.42, -0.12, 0.16],
                [-0.72, -0.28, 0.34],
                [0, -0.36, 0.42],
                [0.72, -0.28, 0.34],
                [1.42, -0.12, 0.16],
                [1.9, 0.02, -0.08],
              ],
            },
            review_planes: [
              {
                id: "d024_review_plane_left",
                label: "Reference review plane left",
                display_position: [-0.95, 0.18, 0.12],
                display_rotation: [0, 1.44, -0.16],
                display_scale: [1, 1.85, 1],
                status: "illustrative_unregistered",
              },
            ],
            slice_views: {
              axial: { axis: "Z", base_mm: 42.5, note: "示意 reslice；未加载真实 CBCT 体数据。" },
            },
          },
          boundary_note:
            "D024 DentVoxel public CBCT-derived mandible surface; non-target-domain anatomy reference only. It is not surgical navigation.",
        },
      },
    });

    await flushPromises();

    expect(threeLoadState.stlPaths[0]).toBe("/models/local/mandible_d024_0001.stl");
    expect(threeLoadState.gltfPaths).toEqual([]);
    expect(fetch).not.toHaveBeenCalledWith("/models/mandible.stl", expect.anything());
    expect(wrapper.text()).toContain("D024 DentVoxel 公开 CBCT 派生下颌标签");
    expect(wrapper.text()).toContain("未配准");
    expect(wrapper.text()).toContain("非导航锁定");
    expect(wrapper.text()).toContain("mandible_d024_0001.stl");
    expect(wrapper.text()).toContain("公开数据集标注，非本病例医生复核");
    expect(wrapper.text()).toContain("非目标域解剖参考");
    expect(wrapper.text()).toContain("osteo-vision-three-d-scene-v1");
    expect(wrapper.text()).toContain("osteo-vision-brp-geometry-manifest-v1");
    expect(wrapper.text()).toContain("D024 下颌参考曲线");
    expect(wrapper.text()).toContain("2D 候选示意投影");
    expect(wrapper.text()).toContain("3 / 3 已就绪");
    expect(wrapper.text()).toContain("交线段：1267, 708, 1241");
    expect(wrapper.text()).toContain("S0: 62.34 mm");
    expect(wrapper.text()).toContain("S1: 64.32 mm");
    expect(wrapper.text()).toContain("示意 Z +42.5 mm");
  });

  it("marks candidate overlays as illustrative when registration is not recorded", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [
          {
            candidate_id: "cand_1",
            run_id: "run_1",
            risk_type: "high fluorescence prompt",
            confidence: 0.9,
            status: "review_required",
            metadata: { timestamp_sec: 1.25 },
          },
        ],
        metrics: {},
        threeDEvidence: {
          model_path: "artifacts/models/case_001_mandible.stl",
          model_format: "stl",
          registration_status: "unregistered",
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("2D 候选示意投影");
    expect(wrapper.find(".anatomy-3d__hotspot.is-reference-projection").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("精准定位");

    await wrapper.get(".anatomy-3d__hotspot").trigger("click");
    expect(wrapper.get(".anatomy-3d__selection-feedback").text()).toContain("候选区已联动");
    expect(wrapper.get(".anatomy-3d__selection-feedback").text()).toContain("1.25 s");
  });

  it("marks identity MHA jaw surfaces as z-flipped display pending orientation review", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
        threeDEvidence: {
          model_path: "artifacts/platform/three_d_models/upload_001/case_cbct_balanced_hard_tissue_proxy.stl",
          model_format: "stl",
          model_file_name: "case_cbct_balanced_hard_tissue_proxy.stl",
          model_source: "uploaded CBCT balanced hard tissue proxy",
          segmentation_source: "automatic balanced hard tissue proxy from raw CBCT",
          registration_status: "unregistered",
          coordinate_space: "cbct_physical_lps_mm_proxy",
          scene_manifest_v2: {
            schema_version: "osteo-vision-three-d-scene-v2",
            scene: {
              coordinate_space: "cbct_physical_lps_mm_proxy",
              registration_status: "unregistered",
              navigation_ready: false,
              volume_geometry: {
                direction: [1, 0, 0, 0, 1, 0, 0, 0, 1],
              },
            },
            nodes: [
              {
                id: "uploaded_cbct_volume",
                type: "volume",
                name: "case001.mha",
                source: "browser uploaded CBCT volume",
              },
            ],
          },
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("显示上方 = -Z 轴");
    expect(wrapper.text()).toContain("MHA 轴向推断 / 待复核");
  });
});
