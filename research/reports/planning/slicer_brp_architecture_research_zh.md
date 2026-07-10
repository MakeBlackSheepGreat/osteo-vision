# 3D Slicer 本体与 SlicerBoneReconstructionPlanner 扩展研究记录

日期：2026-07-08
项目：颌骨骨髓炎智能化荧光诊疗平台软件
边界：本记录用于工程迁移研究，不构成临床诊断、手术导航、导板生成或切除方案承诺。

## 1. 研究对象与本地来源

本轮研究对象分为两层：

- **3D Slicer 本体**：通用 3D 医学影像平台，提供 DICOM/Volume/Segmentation/Model/Markups/Transform/MRML Scene/模块系统等基础能力。
- **SlicerBoneReconstructionPlanner（BRP）**：运行在 3D Slicer 内部的外部扩展，用于下颌骨缺损重建的虚拟手术规划、腓骨瓣重建和患者特异性导板设计。

本地源码与归档：

| 对象 | 本地路径 | 来源与状态 |
| --- | --- | --- |
| 3D Slicer | `research/datasets/external_sources/raw/3d_navigation_sources_20260707/Slicer` | `https://github.com/Slicer/Slicer.git`，浅克隆，commit `28ef15df2165a150be97f52e426f22a7dfdbd20d`，外部源码归档，不进入本项目运行时 |
| BRP 扩展 | `research/datasets/external_sources/raw/3d_navigation_sources_20260707/SlicerBoneReconstructionPlanner` | `https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner`，外部扩展源码归档 |
| 相关文章 | `research/datasets/external_sources/raw/3d_navigation_sources_20260707/PMC5549678` | 仅作三维可视化和医学建模背景资料，非本项目目标域数据 |
| BRP 测试数据残留 | `research/datasets/external_sources/raw/3d_navigation_sources_20260707/SlicerBoneReconstructionPlanner_TestingData` | 当前存在未完整校验的 NRRD 残留，暂不能作为可用测试数据 |

外部网页核验来源：

- 3D Slicer GitHub：<https://github.com/Slicer/Slicer>
- 3D Slicer Developer Guide：<https://slicer.readthedocs.io/en/latest/developer_guide/index.html>
- 3D Slicer MRML Overview：<https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html>
- 3D Slicer Segment Editor：<https://slicer.readthedocs.io/en/latest/user_guide/modules/segmenteditor.html>
- 3D Slicer Markups：<https://slicer.readthedocs.io/en/latest/user_guide/modules/markups.html>
- BRP GitHub：<https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner>
- BRP TestingData Release：<https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner/releases/tag/TestingData>
- Slicer 社区 BRP 介绍：<https://discourse.slicer.org/t/new-3d-slicer-extension-for-planning-and-surgical-guide-generation-for-mandibular-bone-reconstruction/17638>

## 2. 3D Slicer 本体定位

3D Slicer 的 README 将其定义为免费、开源的 visualization and image analysis 软件，并说明其原生支持 Windows、Linux、macOS。对本项目最重要的不是它的界面外观，而是它把医学影像软件拆成了一套稳定对象模型：

- **MRML Scene**：所有数据对象、显示对象、变换、交互标注和模块状态的统一场景容器。
- **MRML Nodes**：Volume、Segmentation、Model、Markups、Transform、Table、Sequence 等都以节点形式进入场景。
- **Display Nodes**：数据对象和显示属性分离，模型本体、透明度、颜色、可见性、切片显示等由显示节点控制。
- **SubjectHierarchy**：把病例、检查、序列、分割、模型、标注等组织成可浏览对象树。
- **Module System**：Slicer 本体提供模块加载、UI、逻辑层和测试层；扩展模块在本体上运行。
- **Scene I/O**：MRML/MRB 场景可保存/恢复，支持把复杂多节点工作状态作为一个工程文件管理。

本地源码证据：

- `Slicer/README.md:6-10`：说明 3D Slicer 是开源可视化与影像分析软件，支持多平台。
- `Slicer/Base/Python/slicer/ScriptedLoadableModule.py:17`：`ScriptedLoadableModule` 是 Python 脚本模块入口。
- `Slicer/Base/Python/slicer/ScriptedLoadableModule.py:88`：`ScriptedLoadableModuleWidget` 承担 UI 层。
- `Slicer/Base/Python/slicer/ScriptedLoadableModule.py:296`：`ScriptedLoadableModuleLogic` 承担逻辑层。
- `Slicer/Base/Python/slicer/ScriptedLoadableModule.py:310`：`getParameterNode` 提供模块参数节点模式。
- `Slicer/Base/Python/slicer/util.py:1213`、`:1328`：`loadScene`、`saveScene` 支持场景读写。
- `Slicer/Base/Python/slicer/util.py:1076`：`loadMarkups` 支持标注读取。
- `Slicer/Base/Python/slicer/util.py:1422`：`selectModule` 支持切换模块。

## 3. Slicer 的核心设计模式

### 3.1 场景优先，而不是组件优先

Slicer 的核心不是“一个 3D 面板”，而是一个场景图。Volume、Segmentation、Model、Markups、Transform、Display 都在场景中有独立身份。UI 只是这些节点的视图和编辑器。

对本项目的启发：前端 `Anatomy3DPanel` 不应继续手写“看起来像 3D 医学软件”的假对象，而应改为读取后端输出的三维证据 manifest。manifest 至少应包含模型节点、分割节点、标注节点、变换节点、显示状态、复核状态和来源边界。

### 3.2 参数节点保存模块状态

Slicer scripted module 通常把用户选择、开关、数值参数、当前节点引用保存在 MRML parameter node 中。这样 UI 刷新、场景保存、模块重载后仍能恢复工作状态。

对本项目的启发：病例分析参数不应只散落在 Vue 组件状态中。建议把三维证据状态抽象为 `three_d_evidence` 与 `geometry_review_state`，后端报告和前端 UI 使用同一份结构化状态。

### 3.3 分割、模型、标注相互转换

Slicer 的 Segment Editor 依赖 `Segmentations` 和 `SubjectHierarchy`，使用 `qMRMLSegmentEditorWidget`，在没有 segmentation node 时会创建 `vtkMRMLSegmentationNode`。这说明 Slicer 把分割编辑、三维表面表示、对象树管理作为同一条链路。

本地源码证据：

- `Slicer/Modules/Scripted/SegmentEditor/SegmentEditor.py:11`：Segment Editor 是 scripted module。
- `Slicer/Modules/Scripted/SegmentEditor/SegmentEditor.py:16`：依赖 `Segmentations` 与 `SubjectHierarchy`。
- `Slicer/Modules/Scripted/SegmentEditor/SegmentEditor.py:60`：使用 `qMRMLSegmentEditorWidget`。
- `Slicer/Modules/Scripted/SegmentEditor/SegmentEditor.py:125-129`：自动查找或创建 segmentation node。

对本项目的启发：CBCT 派生 STL 不是终点。更好的结构是保留原始体数据、分割标签、表面模型、坐标系、复核标注和导出文件之间的派生关系。

### 3.4 Markups 是医生交互的核心对象

Slicer 的 Markups 不是装饰线条，而是可保存、可复核、可参与几何计算的医学交互对象。BRP 用曲线、线段和平面表达下颌曲线、腓骨轴线和切割平面。

对本项目的启发：前端三维层应支持最小 markups：

- `curve`：下颌参考曲线或病灶边界复核线。
- `plane`：医生复核平面或观察平面，不应默认叫切除平面。
- `point`：关键解剖点、ROI 锚点、候选区域中心。
- `line`：方向线、距离测量线、配准误差标尺。

当前项目若没有真实配准，就只能显示“证据参考标注”，不能显示“导航定位”。

## 4. BRP 扩展定位

BRP 不是独立软件，而是 3D Slicer 扩展。它的 README 明确写明：它是用于 mandibular reconstruction with vascularized fibula free flap 和 patient-specific surgical guides 的 3D Slicer extension。CMake 也直接 `find_package(Slicer REQUIRED)`，并依赖多个 Slicer 扩展。

本地源码证据：

- `SlicerBoneReconstructionPlanner/README.md:22`：定义为 3D Slicer extension。
- `SlicerBoneReconstructionPlanner/README.md:51`：声明该软件不是 FDA approved。
- `SlicerBoneReconstructionPlanner/CMakeLists.txt:8`：分类为 `Planning`。
- `SlicerBoneReconstructionPlanner/CMakeLists.txt:13`：依赖 `SurfaceWrapSolidify MarkupsToModel Sandbox Telemetry`。
- `SlicerBoneReconstructionPlanner/CMakeLists.txt:22-27`：查找 Slicer 和依赖扩展。

这意味着：

- BRP 插件本身没有独立启动脚本；它由 3D Slicer 主程序加载。
- 仅 clone BRP 不能直接运行完整软件；需要 Slicer 运行环境。
- 当前本地 clone 的 Slicer 是源码，不是可运行安装包。若要体验原版 UI，应下载 Slicer 5.8.1 Stable 或构建 Slicer，后者成本很高。

## 5. BRP 用户工作流

BRP README 给出的用户路径可以概括为：

1. 安装 3D Slicer。
2. 通过 Extension Manager 安装 BoneReconstructionPlanner。
3. 准备最小 VSP 数据：Mandible CT、Fibula CT、Mandible segmentation、Fibula segmentation。
4. 使用 Segment Editor 完成下颌和腓骨分割，并通过 SurfaceWrapSolidify 等步骤清理骨分割。
5. 在 BRP 模块中选择下颌分割和腓骨分割。
6. 从分割创建骨模型。
7. 创建下颌曲线。
8. 添加下颌平面。
9. 添加腓骨线，并把腓骨线居中到解剖轴。
10. 勾选自动平面定位、平面联动等参数。
11. 生成腓骨平面、腓骨骨段，并变换到下颌位置。
12. 重复调整平面和参数，形成虚拟手术规划。
13. 可继续生成腓骨导板、下颌导板、螺钉孔、锯槽盒和 3D 打印模型。
14. 导出 STL 等模型文件。

本地 README 还提示 CT 层厚、分割质量、三角网格密度、平滑、打印分辨率、打印方向、解剖贴合等都会影响误差。因此它的强项不是“看起来 3D”，而是把每一步几何处理、误差来源和人工调整纳入同一工作流。

## 6. BRP 技术工作流

BRP 的核心源码集中在 `BoneReconstructionPlanner/BoneReconstructionPlanner.py` 和 `BRPLib/helperFunctions.py`。

关键实现点：

- 自定义布局：`addBRPLayout()` 建立 Mandible 3D view、Red axial slice、Fibula 3D view 的组合视图。
- 参数默认值：`setDefaultParameters()` 保存规划锁定、自动平面定位、平面联动等开关。
- Markups 创建：`addMandibularCurve()`、`addFibulaLine()`、`addCutPlane()` 创建曲线、线段和平面节点。
- 事件与防抖：平面修改后通过 timer debounce 触发更新，避免每次拖动都重算复杂几何。
- Dynamic Modeler：`createAndUpdateDynamicModelerNodes()` 维护平面切割和模型追加节点。
- 几何生成：`generateFibulaPlanesFibulaBonePiecesAndTransformThemToMandible()` 把腓骨平面、骨段和变换链路串起来。
- 模型生成：`makeModels()`、`create3DModelOfTheReconstruction()` 生成骨模型和重建模型。
- 导板相关：`createMiterBoxesFromFibulaPlanes()`、`createSawBoxesFromFirstAndLastMandiblePlanes()` 等生成导板辅助几何。
- helper functions：使用 VTK cutter、clipper、boolean、surface area、normal 等几何运算。

本地源码证据：

- `BoneReconstructionPlanner.py:153`：`addBRPLayout`
- `BoneReconstructionPlanner.py:1139`：`setDefaultParameters`
- `BoneReconstructionPlanner.py:1240`：`addMandibularCurve`
- `BoneReconstructionPlanner.py:1259`：`addFibulaLine`
- `BoneReconstructionPlanner.py:1300`：`addCutPlane`
- `BoneReconstructionPlanner.py:1995`：`createAndUpdateDynamicModelerNodes`
- `BoneReconstructionPlanner.py:2301`：`generateFibulaPlanesFibulaBonePiecesAndTransformThemToMandible`
- `BoneReconstructionPlanner.py:2591`：`makeModels`
- `BoneReconstructionPlanner.py:4220`：`create3DModelOfTheReconstruction`
- `BRPLib/helperFunctions.py:9`：模型和平面求交
- `BRPLib/helperFunctions.py:260`：创建 box
- `BRPLib/helperFunctions.py:283`：创建 cylinder
- `BRPLib/helperFunctions.py:330`：计算表面积
- `BRPLib/helperFunctions.py:340`：计算法线

## 7. BRP UI 结构

BRP UI 由 Qt `.ui` 文件定义，主结构不是单个炫酷视窗，而是一组临床工程表单：

- `Mandible Reconstruction Planning`
- `Fibula Surgical Guide Generation`
- `Mandible Surgical Guide Generation`
- Dental implant planning
- Custom titanium plate generation
- 节点选择器、按钮、折叠面板和参数输入

本地源码证据：

- `BoneReconstructionPlanner.ui:65-67`：`Mandible Reconstruction Planning`
- `BoneReconstructionPlanner.ui:118`、`:143`：下颌/腓骨 segmentation selector
- `BoneReconstructionPlanner.ui:171`、`:188`、`:202`：添加下颌曲线、腓骨线、切割平面按钮
- `BoneReconstructionPlanner.ui:1060-1062`：`Fibula Surgical Guide Generation`
- `BoneReconstructionPlanner.ui:1380-1382`：`Mandible Surgical Guide Generation`

这说明 BRP 的成熟感来自“节点选择 + 参数 + 状态 + 结果对象”的严谨链路，而不是视觉拟真。

## 8. Slicer 本体与 BRP 的关系

关系可以理解为：

```text
3D Slicer 本体
  ├─ MRML Scene / Nodes / Display / SubjectHierarchy
  ├─ DICOM / Volume / Segmentation / Model / Markups / Transform
  ├─ Segment Editor / Markups / Dynamic Modeler / Scene IO
  └─ Extension Manager / ScriptedLoadableModule API
        └─ SlicerBoneReconstructionPlanner 扩展
             ├─ 下颌/腓骨分割输入
             ├─ 下颌曲线、腓骨线、下颌平面
             ├─ 腓骨平面、骨段、变换到下颌
             ├─ 导板、螺钉孔、锯槽盒
             └─ STL/模型导出
```

因此，前面把 BRP 当成“一个可以直接照搬的 3D 面板”是不准确的。正确拆法是：

- Slicer 是平台。
- BRP 是平台上的专业插件。
- BRP 的价值在 Slicer 对象模型、医生交互标注、几何计算链路和可保存场景中。
- 我们项目目前只是 Web 平台中的三维证据参考层，不能自然拥有 Slicer 的完整手术规划能力。

## 9. 与 osteo-vision 的差距

当前项目的 3D 面板与 Slicer/BRP 的主要差距：

| 维度 | Slicer/BRP | 当前项目应达到的下一步 |
| --- | --- | --- |
| 数据模型 | MRML 场景统一管理 Volume、Segmentation、Model、Markups、Transform | 建立 `three_d_evidence_manifest`，不要只传 STL 路径 |
| 对象树 | SubjectHierarchy 记录病例、检查、节点、派生关系 | 前端显示“证据对象树”，后端保留来源和派生链 |
| 医生交互 | Markups 可保存、可复核、可参与几何计算 | 增加点、线、曲线、平面的复核状态 |
| 几何计算 | DynamicModeler、VTK cutter/boolean/transform | 后端脚本化几何任务，输出 job manifest |
| 场景保存 | MRML/MRB 保存完整工作状态 | 输出平台证据包 JSON + 模型/截图/报告 |
| 导板能力 | 可生成患者特异性导板 | 本项目当前不得声称导板生成或术中导航 |
| 医学边界 | BRP 自身也声明非 FDA approved | 本项目必须继续标注研发验证、非诊断、医生复核 |

## 10. 可迁移设计

建议迁移的是“结构”和“工作流”，不是 BRP 的临床承诺。

### 10.1 三维证据 manifest

建议新增或扩展：

```json
{
  "schema_version": "three-d-evidence-v2",
  "case_id": "demo_case",
  "scene": {
    "coordinate_space": "cbct_voxel_or_exported_model",
    "registration_status": "unregistered",
    "navigation_ready": false,
    "registration_error_mm": null
  },
  "nodes": [
    {
      "id": "mandible_surface",
      "type": "model",
      "role": "cbct_derived_mandible_surface",
      "path": "/models/local/mandible_d024_0001.stl",
      "source": "public CBCT derived label",
      "review_status": "reference_only"
    }
  ],
  "markups": [
    {
      "id": "review_plane_1",
      "type": "plane",
      "role": "doctor_review_plane",
      "status": "not_available"
    }
  ],
  "geometry_jobs": [],
  "data_boundary": "public CBCT derived, non-target-domain, unregistered, not navigation"
}
```

### 10.2 BRP 风格的工作流状态机

前端 3D 区建议按状态机展示：

1. 模型来源已记录
2. 分割来源已记录
3. 坐标系状态已记录
4. 配准状态已记录
5. 医生复核标注已记录
6. 几何任务可追溯
7. 输出证据包可复核

缺失任何关键环节时，界面必须显示“示意/未配准/非导航/待复核”，而不是用红圈、切割边界、导航光标制造确定性。

### 10.3 Markups 复核数据回灌

建议把医生复核动作统一沉淀为 markups：

- 2D 视频帧 ROI：继续保留在 keyframe review manifest。
- 3D CBCT/STL 复核：保存为点、线、曲线、平面。
- 二者若未配准，只能并列展示为多模态证据，不能声称空间映射。

### 10.4 后端几何任务化

前端只做展示和轻交互，几何计算应进入后端或脚本：

- STL/label 读入
- 表面生成
- 模型质量检查
- 平面求交
- 距离/面积/体积计算
- 截图和缩略图生成
- manifest 写出

这样可以把 UI 从“炫酷但不可追溯”改成“朴素但可信”。

## 11. 不应迁移的能力

当前项目不应直接迁移或声称：

- 下颌切除平面规划。
- 腓骨瓣重建方案。
- 患者特异性导板生成。
- 螺钉孔、锯槽盒、钛板生成。
- 术中导航定位。
- 自动生成可临床执行的手术方案。

原因：

- 本项目赛题核心是荧光显微镜下的造影剂、多模态融合处理和 AI 辅助判读，不是颌骨重建导板规划。
- 当前没有真实术中 ICG 颌骨骨髓炎目标域视频、医生标注、CBCT 与视频配准、定位设备误差记录。
- BRP 自身也要求 CT、分割、医生规划、导出和 mock surgery 等严格流程。

## 12. 对本项目的工程建议

优先级从高到低：

1. **建立三维证据 manifest v2**
   把 STL 路径扩展成 Slicer-like scene：nodes、markups、transforms、geometry_jobs、review_state、data_boundary。

2. **前端显示对象树而不是假三维导航**
   参考 SubjectHierarchy，用“模型、分割、标注、配准、复核、输出”对象树组织 3D 区。

3. **保留 BRP 工作流状态，但降级医学语义**
   “切割平面”在本项目应叫“复核平面/观察平面”；“导航”应叫“证据参考”；“导板”暂不进入主流程。

4. **后端增加几何 job manifest**
   例如 `surface_export`、`model_quality_check`、`markup_distance_measurement`、`plane_intersection_preview`。每个 job 记录输入、输出、参数、sha256、时间和失败原因。

5. **重新下载并校验 BRP TestingData 后再使用**
   当前本地 `CTFibula.nrrd` 大小与预期不一致，`CTMandible.nrrd` 还停在 `.part` 文件，不能作为演示数据。

6. **若要看原版 UI，优先安装 Slicer 5.8.1 Stable**
   源码 clone 不是可运行程序。构建 Slicer 成本高，不适合作为当前比赛平台开发前置。

## 13. 结论

3D Slicer 是医学影像平台，BRP 是运行在其上的下颌重建专用扩展。BRP 值得迁移的不是“外观”，而是：

- 场景图对象模型
- 节点化证据管理
- 医生 Markups 交互
- 参数节点/状态保存
- 几何任务可追溯
- 分割到模型再到导出的派生关系
- 明确的误差和非临床边界

本项目下一步应把 3D 面板从“模型展示组件”升级为“CBCT/STL 三维证据参考层”。它可以支持真实公开 CBCT 派生模型、医生复核标注和证据包导出，但在没有真实配准和临床验证前，必须持续标注为非导航、非诊断、医生复核辅助。

## 14. 2026-07-08 深度源码复核补充

本轮额外使用 Tavily Research、3D Slicer 官方文档、GitHub 源码和 BRP 源码做二次复核。为避免污染版本库，临时源码复核路径放在 Git 忽略目录：

| 对象 | 本轮复核路径 | 说明 |
| --- | --- | --- |
| Slicer 本体 | `artifacts/research_search/external_code/Slicer` | sparse shallow clone，仅用于读取文档和源码结构 |
| BRP 扩展 | `artifacts/research_search/external_code/SlicerBoneReconstructionPlanner` | shallow clone，读取 README、UI、Python 逻辑和测试 |
| Tavily 研究结果 | `artifacts/research_search/slicer_brp_deep_research.md` | 外部来源综合，含官方文档与社区链接 |

### 14.1 Slicer 本体不是一个 3D viewer，而是医学场景运行时

官方文档把 Slicer 的核心抽象写得很清楚：所有数据都进入 MRML scene；节点类型覆盖 Volume、Model、Segmentation、Markups、Transform、Display、Storage、View 等。也就是说，Slicer 的 3D 能力不是单纯把 STL 画出来，而是把数据、显示、几何关系、保存/加载和交互事件绑定成一套场景系统。

对本项目的直接结论：

- 前端不应再把三维区设计成单个 `model_path` 的渲染器。
- 后端应输出类似 MRML 的轻量证据场景：`nodes`、`display`、`markups`、`transforms`、`derived_from`、`review_state`、`exported_files`。
- 前端对象树应成为 3D 区核心，而不是“一个模型 + 几个状态标签”。
- 保存证据包时，应能恢复同一个三维证据状态，而不只是重新加载 STL。

### 14.2 Slicer 模块系统对本项目的对应关系

Slicer 模块有 CLI、C++ loadable、Python scripted 三类。BRP 使用 Python scripted module，是典型的 `Widget + Logic + Test` 模式。源码中 `BoneReconstructionPlannerWidget` 负责 UI 连接和参数同步，`BoneReconstructionPlannerLogic` 负责几何计算和场景节点操作，测试类直接加载样例数据并检查节点数量、模型点数、平面和变换结果。

可迁移到本项目的结构：

| Slicer/BRP | 本项目对应 |
| --- | --- |
| `ScriptedLoadableModuleWidget` | Vue 工作台组件 |
| `ScriptedLoadableModuleLogic` | `backend/src/services/*` 几何/建模服务 |
| `vtkMRMLScriptedModuleNode` parameter node | `three_d_evidence_manifest` + case run state |
| `slicer.mrmlScene` | 病例证据包 scene JSON |
| `SubjectHierarchy` | 前端证据对象树 |
| `vtkMRMLMarkups*Node` | 医生复核点/线/曲线/平面 |
| `vtkMRMLDynamicModelerNode` | 后端 geometry job |
| `MRB/MRML save` | 平台 evidence bundle |

### 14.3 BRP 的真实输入前提比我们当前前端强得多

BRP README 给出的最小 VSP 输入不是单独一个漂亮模型，而是：

- Mandible CT。
- Fibula CT。
- Mandible segmentation。
- Fibula segmentation。
- 推荐 CT 层厚 1 mm 或更低，示例中建议 0.65 mm。
- 先在 Segment Editor 中做阈值、Scissors、Islands、Wrap Solidify 等分割清理。

这解释了为什么我们的 3D 面板之前“丑”：我们只有一个从 label 或 fallback 派生的表面模型，缺少 Slicer/BRP 依赖的 CT、分割、对象树、标注、显示节点、相机布局、模型清理和医生调整链路。问题不只是材质或灯光，而是数据链路不完整。

### 14.4 BRP UI 的成熟感来自临床工程表单，不来自炫酷视觉

BRP 的 `.ui` 文件主干是折叠表单：

- `Mandible Reconstruction Planning`
- `Dental Implants Planning`
- `Custom Titanium Plate Generation`
- `Fibula Surgical Guide Generation`
- `Mandible Surgical Guide Generation`
- `Settings`

每一段都由节点选择器、数值输入、复选框、按钮和对象树组成。它几乎没有“科幻 HUD”。它让用户先选择分割，再创建模型，再添加曲线/平面/线，再更新几何结果。我们的前端应学习这个顺序感：输入、检查、建模、标注、复核、导出，而不是把所有结果堆进一个巨大的 3D 卡片。

### 14.5 BRP 的关键源码机制

本轮重点复核了以下机制：

1. **默认参数与状态保存**
   `setDefaultParameters()` 写入 `showOriginalMandible`、`lockVSP`、`mandiblePlanesPositioningForMaximumBoneContact`、`makeAllMandiblePlanesRotateTogether` 等状态。
   本项目应把这些映射为 `display_options`、`workflow_locks`、`review_options`，随 evidence manifest 保存。

2. **SubjectHierarchy 文件夹**
   BRP 为 `BoneReconstructionPlanner`、`Mandible reconstruction`、`Inverse mandible reconstruction`、`Dental Implants planning`、`Mandibular planes` 等建立文件夹。
   本项目应建立对象树分组：`输入体数据`、`分割标签`、`表面模型`、`复核标注`、`几何任务`、`导出文件`。

3. **Markups 创建**
   `addMandibularCurve()` 创建 `vtkMRMLMarkupsCurveNode`，`addFibulaLine()` 创建 `vtkMRMLMarkupsLineNode`，`addCutPlane()` 创建 `vtkMRMLMarkupsPlaneNode` 并设置 `isMandibularPlane=True`。
   本项目不应叫“切割平面”，应叫“复核平面/观察平面”，并记录 `review_status`。

4. **从分割生成模型**
   `makeModels()` 从 `fibulaSegmentation` 和 `mandibularSegmentation` 导出 closed surface，再生成原始模型和 decimated preview 模型。
   本项目当前只有 `export_cbct_mandible_surface.py` 的 marching cubes，下一步应补 `surface_quality`、`decimated_preview`、`source_label`、`mesh_stats`。

5. **动态几何任务**
   `createAndUpdateDynamicModelerNodes()` 维护 Plane Cuts、Cut Bones 等节点，使用 Dynamic Modeler/VTK 更新结果。
   本项目应把它变成后端 job：`surface_export`、`surface_decimation`、`plane_intersection_preview`、`distance_measurement`、`screenshot_render`。

6. **测试方式**
   BRP 测试加载 `CTFibula`、`CTMandible`、`FibulaSegmentation`、`MandibleSegmentation`，再检查模型点数、节点数量、曲线、平面和变换。
   本项目应新增端到端测试：上传 label NIfTI -> 建模 job -> STL/manifest -> 前端加载 -> 对象树展示 -> evidence bundle 包含派生关系。

### 14.6 我们和原版 BRP 的差距清单

| 能力 | BRP 原版 | 本项目当前状态 | 建议 |
| --- | --- | --- | --- |
| 可运行方式 | 由 Slicer 主程序加载扩展 | Web 前后端独立运行 | 不移植 Slicer 运行时，只迁移对象模型 |
| 数据组织 | MRML scene + SubjectHierarchy | 局部 `three_d_evidence` | 做 v2 scene manifest |
| 输入 | CT + segmentation | CBCT/STL 上传、NIfTI label 可导 STL | 增加 DICOM series/NIfTI 元数据检查 |
| 分割编辑 | Segment Editor | 暂无 3D 分割编辑 | 先显示分割来源与质量，不做假编辑 |
| 模型生成 | segmentation -> closed surface -> decimated preview | marching cubes -> STL | 增加 decimation、质量统计、预览模型 |
| 交互标注 | 曲线、线、平面、点 | 少量状态展示 | 增加可保存 markups schema |
| 几何计算 | Dynamic Modeler + VTK | 部分后端 job | 增加 geometry job manifest |
| 场景保存 | MRML/MRB | 平台证据包尚未完整覆盖 3D | evidence bundle 写入 3D scene |
| 导板/切除 | 支持 | 不应支持或声称 | 保持非导航、非导板、非诊断 |

### 14.7 适合立即迁移的最小闭环

下一步最小实现不应继续追求“像 Slicer 的菜单”，而应实现“像 Slicer 的数据链”：

1. 后端新增 `three_d_scene_manifest_v2` 生成器。
2. 建模 job 完成后写入：
   - `volume` node：输入 CBCT/NIfTI 信息。
   - `segmentation` node：label 来源、标签值、是否医生复核。
   - `model` node：STL/GLB 路径、sha256、顶点/面数、是否 decimated。
   - `markups`：初始为空，但 schema 支持点/线/曲线/平面。
   - `transforms`：未配准时显式记录 `identity_or_unknown`。
   - `geometry_jobs`：surface export、quality check。
   - `data_boundary`：公开 CBCT/非目标域/未配准/非导航。
3. 前端 `Anatomy3DPanel` 改成两栏：
   - 左：CBCT 建模与对象树。
   - 右：3D 视图 + 当前节点详情 + 复核状态。
4. 前端所有英文长控件收敛为中文短标签，详情进入状态行/说明区，不挤在按钮里。
5. 证据包导出时包含该 manifest，而不是只包含截图。

### 14.8 必须继续避免的误用

- 不把 BRP 的 mandibulectomy、fibula free flap、guide generation 迁移为本项目默认能力。
- 不把 D024 或任何公开 CBCT 派生模型说成真实颌骨骨髓炎术中 ICG 病例。
- 不把 2D 荧光候选区投射到 3D 模型上说成空间定位，除非未来有明确配准矩阵、误差、坐标系和医生复核记录。
- 不把 Slicer 源码 clone 当作可运行 Slicer 安装包；体验原版 UI 需要安装 Slicer Stable 或下载 release 包。

### 14.9 参考来源

- 3D Slicer MRML Overview：<https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html>
- 3D Slicer Module Overview：<https://slicer.readthedocs.io/en/latest/developer_guide/module_overview.html>
- 3D Slicer Extensions：<https://slicer.readthedocs.io/en/latest/developer_guide/extensions.html>
- 3D Slicer Markups：<https://slicer.readthedocs.io/en/latest/user_guide/modules/markups.html>
- 3D Slicer Dynamic Modeler：<https://slicer.readthedocs.io/en/latest/user_guide/modules/dynamicmodeler.html>
- SlicerBoneReconstructionPlanner GitHub：<https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner>
- BRP TestingData Release：<https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner/releases/tag/TestingData>
- BRP 论文 DOI：<https://doi.org/10.1016/j.stlm.2023.100109>

## 15. 2026-07-08 操作级深度研究结论

本节补充回答两个实操问题：原版 Slicer/BRP 到底怎样使用，以及本项目怎样学习它而不误用它。

### 15.1 原版软件如何启动和使用

3D Slicer 本体的源码 clone 不是直接可运行的安装包。原版体验路线应当是：

1. 下载并安装 Slicer Stable。BRP README 当前说明使用 Slicer 5.8.1 Stable。
2. 打开 Slicer 主程序。
3. 通过 Extensions Manager 搜索并安装 `BoneReconstructionPlanner`，接受依赖扩展安装并重启。
4. 准备或下载测试数据：`CTMandible.nrrd`、`CTFibula.nrrd`、`MandibleSegmentation.seg.nrrd`、`FibulaSegmentation.seg.nrrd`，或直接打开 `.mrb` 场景。
5. 在 Segment Editor 中先完成下颌和腓骨分割清理，再进入 BRP 模块。
6. 在 BRP 中选择分割节点，生成模型，添加下颌曲线、腓骨线、复核/切割平面，再运行几何生成。
7. 需要导板时继续进入 guide generation，但这属于下颌重建手术规划，不属于本项目当前可声称能力。

本地 BRP 源码没有独立 `start.bat`、`run.ps1` 或 Web 服务入口。它是由 Slicer 加载的 Python scripted module。源码证据是 `CMakeLists.txt` 中 `find_package(Slicer REQUIRED)`，以及模块类继承 `ScriptedLoadableModule`。

### 15.2 Slicer/BRP 的“好看”来自对象链，不是材质

本项目 3D 面板过去显得假，根因不是 Three.js 材质不够高级，而是缺少 Slicer 的对象链：

- 原始 CT/CBCT volume node。
- segmentation node。
- closed surface model node。
- display node。
- subject hierarchy 分组。
- markups 曲线、点、线、平面。
- transform / registration state。
- geometry job state。
- scene save / restore。

BRP 的视图只是这些对象链的外显。没有真实体数据、分割、复核标注和配准状态时，单独显示一个下颌 STL 无论材质多好，都只能是证据参考模型。

### 15.3 可迁移到本项目的设计清单

| 原版机制 | 本项目迁移方式 | 当前边界 |
| --- | --- | --- |
| MRML scene | `three_d_scene_manifest_v2` | 轻量 JSON，不运行 Slicer |
| SubjectHierarchy | 前端对象树：输入、分割、模型、标注、几何任务、导出 | 只做证据组织 |
| Parameter node | 病例 run state + evidence manifest | 保存选择、状态和边界 |
| Segment Editor | 后端记录分割来源、标签、质量，不伪造编辑器 | 真实 3D 编辑后续再做 |
| Markups | 复核点、线、曲线、观察平面 schema | 不叫切除平面 |
| Dynamic Modeler | 后端 geometry job manifest | 只做可追溯计算 |
| MRB/MRML save | evidence bundle + scene JSON + STL/截图/报告 | 平台证据包，不是 Slicer 场景 |
| BRP guide generation | 暂不迁移 | 不声称导板和导航 |

### 15.4 对前端工作台的具体要求

三维区应从“大型 3D 展示组件”改为“CBCT/STL 三维证据工作台”：

- 左侧：导入 CBCT/STL、建模任务、对象树。
- 中间：模型视图，仅展示已确认来源的模型。
- 右侧或下方：当前节点详情、来源、派生关系、质量检查、复核状态。
- 所有空间相关文案必须带状态：未配准、非导航、医生复核前参考。
- 荧光视频候选区与 CBCT/STL 只能并列展示；没有配准矩阵和误差记录时，不做 2D 到 3D 空间映射。

### 15.5 对后端的具体要求

后端应把每个三维动作变成可追溯 job：

- `volume_import`：记录上传文件、格式、sha256、spacing、维度、来源。
- `segmentation_import`：记录 label/source/review_status。
- `surface_export`：记录 marching cubes 参数、label value、顶点数、面数、输出 STL、sha256。
- `surface_quality_check`：记录 watertight、连通域、退化面、包围盒、体素间距。
- `markup_save`：记录点/线/曲线/平面、作者、复核状态。
- `scene_export`：写出 scene manifest 并纳入 evidence bundle。

### 15.6 不应继续追的方向

- 不要把 Slicer 本体嵌入 Web 前端。
- 不要把 BRP 的腓骨瓣、导板、螺钉孔、锯槽盒迁移为本项目主功能。
- 不要把公开 CBCT 派生模型包装成真实术中病例。
- 不要把未配准的荧光视频候选区投射成真实 3D 导航。
- 不要只调 Three.js 材质来解决“丑”的问题；优先补数据链、对象树、质量状态和复核链路。

### 15.7 推荐下一步

1. 完成前端浏览器验收：导入 NIfTI label 或 STL，生成建模 job，确认对象树、模型视图、状态文案和证据包均稳定。
2. 给 `three_d_scene_manifest_v2` 增加 `surface_quality_check` 字段，并把它展示到前端节点详情。
3. 新增 markups 保存接口，先支持点、线、曲线、观察平面，不做切割规划。
4. 用 BRP TestingData 中的 `CTMandible` 与 `MandibleSegmentation` 做本地非 Git 演示数据，但必须先校验下载完整性。
5. 若要看原版 UI，单独安装 Slicer 5.8.1 Stable；不要试图从当前源码 clone 直接启动。
