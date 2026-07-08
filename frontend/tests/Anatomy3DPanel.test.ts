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
    PCFSoftShadowMap: "PCFSoftShadowMap",
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
    globalThis.fetch = vi.fn(async () => ({ ok: false, headers: new Headers({ "content-type": "text/html" }) })) as unknown as typeof fetch;
    globalThis.ResizeObserver = class {
      observe = vi.fn();
      disconnect = vi.fn();
    } as unknown as typeof ResizeObserver;
  });

  it("falls back to unregistered reference wording without 3D evidence", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
        modeLabel: "双通道融合证据",
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("CBCT/STL 三维证据工作台");
    expect(wrapper.text()).toContain("对象列表");
    expect(wrapper.text()).toContain("Red 轴位 Axial");
    expect(wrapper.text()).toContain("切割平面");
    expect(wrapper.text()).toContain("Mandible Reconstruction Planning");
    expect(wrapper.text()).toContain("Patient / Volume");
    expect(wrapper.text()).toContain("Markups / Planes");
    expect(wrapper.text()).toContain("ICG / Reconstruction Reference");
    expect(wrapper.text()).toContain("Mandibulectomy mode");
    expect(wrapper.text()).toContain("Segmental Mandibulectomy");
    expect(wrapper.text()).toContain("Right side leg: fibula X axis kept medial");
    expect(wrapper.text()).toContain("Bigger miter box distance to fibula");
    expect(wrapper.text()).toContain("Add fibula line");
    expect(wrapper.text()).toContain("Update fibula planes over fibula line");
    expect(wrapper.text()).toContain("S0: 29.49 mm");
    expect(wrapper.text()).toContain("非导航锁定");
    expect(wrapper.text()).toContain("示意占位 / 未接入真实模型");
    expect(wrapper.text()).toContain("未配准 / 非导航");
    expect(wrapper.text()).toContain("Markups / Registration Table");
    expect(wrapper.text()).toContain("Transform chain");
    expect(wrapper.text()).toContain("F1 paired landmark");
    expect(wrapper.text()).toContain("DICOM voxel to CBCT RAS");
    expect(wrapper.text()).toContain("暂无候选区投影");
    expect(wrapper.text()).not.toContain("全息");
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
    expect(wrapper.text()).toContain("point-based + surface matching");
    expect(wrapper.text()).toContain("176");
    expect(wrapper.text()).toContain("Left mental foramen");
    expect(wrapper.text()).toContain("residual: 0.62 mm");
    expect(wrapper.text()).toContain("CBCT RAS to STL surface");
    expect(wrapper.text()).toContain("2 / 2 transforms ready");
    expect(wrapper.findAll(".anatomy-3d__registration-guard .is-ready")).toHaveLength(5);
  });

  it("loads generated local D024 STL evidence as an unregistered public CBCT reference", async () => {
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
            fibula_reference: {
              segment_lengths_mm: [31.25, 27.5],
              display_curve: [
                [-1.92, -1.34, -0.26],
                [-0.72, -1.24, -0.18],
                [0.62, -1.28, -0.1],
                [1.84, -1.36, -0.2],
              ],
            },
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

    expect(threeLoadState.stlPaths[0]).toContain(
      "frontend%2Fpublic%2Fmodels%2Flocal%2Fmandible_d024_0001.stl",
    );
    expect(threeLoadState.gltfPaths).toEqual([]);
    expect(fetch).not.toHaveBeenCalledWith("/models/mandible.stl", expect.anything());
    expect(wrapper.text()).toContain("D024 DentVoxel public CBCT derived mandible label");
    expect(wrapper.text()).toContain("未配准");
    expect(wrapper.text()).toContain("非导航锁定");
    expect(wrapper.text()).toContain("mandible_d024_0001.stl");
    expect(wrapper.text()).toContain("public_dataset_annotation_not_case_reviewed");
    expect(wrapper.text()).toContain("non-target-domain anatomy reference");
    expect(wrapper.text()).toContain("osteo-vision-three-d-scene-v1");
    expect(wrapper.text()).toContain("osteo-vision-brp-geometry-manifest-v1");
    expect(wrapper.text()).toContain("D024 mandibular reference curve");
    expect(wrapper.text()).toContain("2D 候选示意投影");
    expect(wrapper.text()).toContain("3 / 3 ready");
    expect(wrapper.text()).toContain("segments [1267, 708, 1241]");
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
  });

  it("keeps BRP planning controls interactive without claiming navigation", async () => {
    const wrapper = mount(Anatomy3DPanel, {
      props: {
        candidates: [],
        metrics: {},
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain("Point-based fiducials / paired landmarks 已记录");
    expect(wrapper.text()).toContain("Missing");
    expect(wrapper.text()).toContain("示意 Z +12.4 mm");
    expect(wrapper.text()).toContain("Reset camera");

    const axialSlider = wrapper.find('input[aria-label="Red 轴位 Axial 切片位置"]');
    expect(axialSlider.exists()).toBe(true);
    await axialSlider.setValue("20");
    await nextTick();
    expect(wrapper.text()).toContain("示意 Z +32.4 mm");

    const firstMarkup = wrapper.find(".anatomy-3d__markup-row");
    expect(firstMarkup.exists()).toBe(true);
    await firstMarkup.trigger("click");
    await nextTick();
    expect(firstMarkup.classes()).toContain("is-selected");
    expect(wrapper.find(".anatomy-3d__viewport-label.is-markup.is-selected").exists()).toBe(true);

    const modeSelect = wrapper.find(".anatomy-3d__brp-params select");
    expect(modeSelect.exists()).toBe(true);
    await modeSelect.setValue("Hemimandibulectomy");
    await nextTick();
    expect(wrapper.text()).toContain("Hemimandibulectomy");
    expect(wrapper.text()).toContain("Mandible end cut");

    const fibulaTool = wrapper
      .findAll(".anatomy-3d__tool")
      .find((button) => button.text().includes("腓骨线"));
    expect(fibulaTool).toBeTruthy();
    await fibulaTool?.trigger("click");
    await nextTick();
    expect(fibulaTool?.classes()).toContain("is-active");

    const fibulaNode = wrapper
      .findAll(".anatomy-3d__tree-item")
      .find((button) => button.text().includes("Fibula line / miter boxes"));
    expect(fibulaNode).toBeTruthy();
    await fibulaNode?.trigger("click");
    await nextTick();
    expect(wrapper.text()).toContain("Fibula line / miter boxes");
    expect(fibulaNode?.text()).toContain("隐藏");

    const threeDLayoutButton = wrapper
      .findAll(".anatomy-3d__layout-switcher button")
      .find((button) => button.text().includes("3D 最大化"));
    expect(threeDLayoutButton).toBeTruthy();
    await threeDLayoutButton?.trigger("click");
    await nextTick();
    expect(wrapper.find(".anatomy-3d__views").classes()).toContain("is-layout-threeD");
    expect(wrapper.text()).toContain("Layout: 3D 最大化");

    await wrapper.find(".anatomy-3d__viewport").trigger("dblclick");
    await nextTick();
    expect(wrapper.find(".anatomy-3d__views").classes()).toContain("is-layout-four");
  });
});
