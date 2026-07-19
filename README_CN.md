# osteo-vision 开发框架

本仓库是颌骨骨髓炎智能化荧光诊疗项目的正式开发工程，基于通用医学影像比赛框架模板整理而来，用于分类、分割、检测、量化、可解释性、报告、Demo 和 Benchmark 开发。

完整赛题原文和赛题方设备技术文档均为本地忽略 PDF，不进入 Git。后续方案优先围绕完整赛题的三项核心答题要求展开：新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助显微成像判读。DICOM/远程协作只能作为扩展亮点，不能替代造影剂设计要求。

本仓库只用于科研、教学、比赛和受控演示。所有输出都不是临床诊断，不能替代医生复核。

## 当前可运行闭环

当前 V1 平台已经能跑通一个研发验证版平台闭环：

1. 创建病例。
2. 上传或登记 JPEG 图片、MP4 视频，优先贴合赛题官方设备边界：4K `3840x2160`、JPEG、MP4。
3. 对白光/ICG 图片执行伪彩增强、背景扣除、轻量配准、融合、色标生成和 ROI 定量。
4. 对 MP4 抽取关键帧，并运行当前比赛主线 Residual Attention U-Net keyframe 代理分割模型，生成 mask、probability map、伪彩和叠加结果。
5. 在 Vue 工作台展示候选区域、荧光融合证据、时间线摘要、医生复核状态和导出证据。
6. 在医生标注页对关键帧病灶/风险区域进行像素级人工标注，保留版本、身份、复核状态和训练准入记录。
7. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP evidence bundle。

当前仍是研发验证版平台。ICG 信号主要反映灌注和组织活性差异，不是颌骨骨髓炎特异性探针；平台输出只能作为术中参考信号、风险提示和医生复核辅助。

## 软件三项固定优先目标

1. 患者年龄、性别、基础病、用药和血液指标参与的受限患者条件分割，同时保留影像基础结果、条件结果、差异图和失败回退。
2. 在医生复核骨面内输出低活性候选、过渡复核区、高活性参考、无法判断区和连续骨活性评分，最终形成目标域多任务模型。
3. 通过离线 manifest 或人工元数据接入倍率、工作距离、相机标定、坐标变换和位姿，完成 CBCT/STL 的 L1 静态仿体配准与严格 L2 离线动态 AR 软件工程验证。

三项软件目标主要映射官方赛题第二项多模态图像融合处理和第三项 AI 辅助判读；第一项新型荧光造影剂设计及必要验证独立维护。固定母稿见 `research/reports/planning/three_priority_capabilities_target_20260717_zh.md`，验收与安全门控见 `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`。项目侧负责主动检索、下载和校验所需公开/代理数据。当前 15 份源数据 manifest 已覆盖 47 条记录、138 个本地文件、5,514,559,510 字节；所有源记录保持非目标域和未训练准入状态。D069 MMDental 已从 68,087,010,723 字节 ZIP64 远程包中选择性物化 660 个患者的 2,124 条就诊记录及 1 例配对牙科 CBCT，并完成未配准硬组织代理表面建模；其聚合质控记录了 390 个多次就诊患者、2 个年龄冲突患者、0 个性别冲突患者和逐字段缺失量。D087 C3VD 官方样例已完成 1,515,094,074 字节下载、ZIP CRC 和 SHA256 校验，包含 766 对 RGB/depth 帧及 2,558 条位姿记录；平台另行安全物化 53 个必要资产共 106,975,431 字节，将 766 帧全部绑定到去重后的 2,556 条位姿，并完成 OCamCalib 投影、24 帧回放及三类失效注入。D090 已新增 3 段 1080p 人体乳腺前哨淋巴结 ICG 视频；D091 已新增 2 段肝切除 ICG 三面板视频，并经抽帧确认画面同时包含白光、伪彩叠加和灰度荧光显示。D094/D095 新增 53 例 ORNJ 临床影像判读表和 1,129 例头颈放疗 ORNJ 结局/下颌剂量学表，用于患者条件字段映射、患者级分组和亚组审计。上述资源均缺少可直接支撑目标域空间分割的联合影像与像素标注。

患者条件和骨活性模型已有非目标域代理训练闭环。KiTS23 患者条件代理复跑 288 个训练批次，测试 Dice/IoU/召回率/精确率为 `0.243974/0.151192/0.195572/0.553163`，ECE 为 `0.005700`，相对影像基础 Dice 的差值为 `-0.000214`，最大物理边界位移为 `183.478 mm`；no-harm 与 provisional `2 mm` 边界门均失败。D074 人脑 PpIX 显微荧光代理采用 3 个患者组、5 个真实图像样本完成骨活性多任务训练，冻结测试 macro Dice 为 `0.733064`，骨面 Dice 为 `0.102190`，非拒答覆盖率为 `0.056417`，选择性错误率为 `0.301527`；测试安全约束失败，`engineering_utility_ready=false`。两项模型均保持 `target_domain_promotion_ready=false` 和 `runtime_replacement_allowed=false`。L1/L2 证据现强制绑定坐标 frame、手性、轴方向、单位和矩阵约定；任一 provenance、标定、同步、误差或医生复核门失败均回退 L0。真实设备全倍率/全工作距离 4K 标定和真实下颌仿体物理证据尚未完成，真实病例导航默认保持 `navigation_ready=false`。

目标域晋级器现从 SHA256 绑定的逐病例预测与医生复核真值独立重算全部指标，并要求医生与项目复核员使用不同 Ed25519 密钥双签。后端提供认证审批、追加式哈希链、防重放、撤销、状态和 bundle API；离线 CLI 负责仓库外密钥、公钥信任表合并、精确目标载荷和签名；最终晋级器再次重放证据、哈希链、签名和密钥状态。生产策略哈希与公钥信任表继续保持为空，T101/T102/T107 在真实目标域数据和正式审批到位前持续关闭。操作流程见 `docs/promotion_approval_offline.md`。

2026-07-19 最终全量工程自测通过：后端 253 项，核心 unit/smoke 584 项，前端 48 个测试文件共 186 项通过、1 项跳过，Playwright E2E 5 项通过，`vue-tsc` 与 Vite build 通过。`NavigationWorkspacePage` 路由块约 61.97 kB，三维视口作为约 709.67 kB 的异步块按需加载；Vite 仅对该独立三维块保留大块提示。该结果属于项目工程自测。

## 当前模型状态

可运行：

- `convnext3d_d025_proxy_segmenter`：D025 CBCT ROI 代理分割模型，用于工程闭环验证。
- `d025_lesion_smoke_segmenter`：同一 D025 代理 checkpoint 的 smoke/兼容入口。
- `keyframe_residual_attention_unet_s20260715_20260715`：当前 MP4/JPEG keyframe 比赛主线；代理测试集 Dice `0.9177`、IoU `0.8483`，三种子 Dice `0.9149 +/- 0.0041`，运行阈值 `0.4`。
- `convnext2d_keyframe_proxy_segmenter`：保留为上一代 2D ConvNeXt-style 代理对照模型。
- 当前 keyframe 主线支持 4K patch/tiling 推理和 960 长边实时 fast-output。比赛严格配置关闭启发式回退；研发配置保留 hotspot 对照能力。
- `fluorescence_hotspot_2d_segmenter`：MP4/JPEG keyframe 的阈值和连通域 hotspot baseline，作为回退和可解释对照。
- `medsam2_osteo_promptable`：MedSAM/SAM2 风格 prompt contract fallback，可用医生 ROI/bbox/point 生成可复核 mask；缺真实 MedSAM2 checkpoint，不能写成真实 MedSAM2 推理。
- `fixture_default`：测试和兜底 fixture。

尚不可用：

- `nnunet_v2_osteo_baseline`：缺 checkpoint 和 adapter inference。
- `biomedclip_osteo_screening`：缺 `open_clip`、checkpoint 和 adapter inference。

最新 D025 代理模型评估见 `research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`。该评估不能代表真实术中 ICG 颌骨骨髓炎目标域性能。
2D keyframe 模型选型见 `research/reports/modeling/keyframe_model_selection_summary_20260715_zh.md`；4K 门控见 `research/reports/modeling/keyframe_residual_attention_4k_runtime_gate_20260715_zh.md`；实时 fast-output 门控见 `research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md`。
MedSAM-like prompt fallback 说明见 `research/reports/modeling/medsam_prompt_contract_20260704_zh.md`。

2D MP4/JPEG keyframe 分割模型当前已有可运行训练链路：

```powershell
conda run -n osteo-vision python tools\build_keyframe_segmentation_proxy_manifest.py --input research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705 --dataset-id d046_mp4_proxy --input-domain public_fluorescence_or_osteomyelitis_proxy_mp4 --fluorescence-attribute mixed_fluorescence_and_non_fluorescence --max-frames-per-video 4 --max-samples 200 --threshold 0.62 --min-component-area 32 --min-positive-area-fraction 0.0005 --max-positive-area-fraction 0.6 --preview-sample-count 40 --review-seed-sample-count 50
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 160x256 --max-train-batches 160 --batch-size 4 --base-channels 12 --learning-rate 0.0007 --threshold 0.15 --device auto --report-stamp 20260705_threshold_calibrated
conda run -n osteo-vision python scripts\evaluate_keyframe_segmentation_proxy.py --checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-dir research\reports\modeling\keyframe_threshold_eval_20260705 --image-shape 160x256 --split val --device auto
```

这组命令保留上一代 ConvNeXt 基线的训练复现。当前比赛主线由三种子模型选型、锁定测试集、4K tiled、完整比赛流和 960 长边实时 fast-output 门控共同晋级。医生标注可通过 `/annotations` 页面保存，再由 `tools\build_keyframe_training_manifest_from_manual_annotations.py` 生成训练准入 manifest；可信 `accepted` / `modified` 标注进入高权重训练数据，工程身份或未复核标注继续隔离。生成的原始帧、mask、标注版本和 checkpoint 均为本地运行产物，不进入 Git。

单帧 4K/tiling 分割推理可单独验证：

```powershell
conda run -n osteo-vision python tools\run_keyframe_tiling_smoke.py --width 3840 --height 2160
```

该命令直接调用主线 `keyframe_residual_attention_unet_s20260715_20260715` adapter，验证 keyframe mask、probability map、伪彩叠加图和 tiled inference 元数据是否完整；输出写入 `artifacts/platform_smoke/keyframe_tiling_*`，不进入 Git。

## 已包含能力

- `configs/inference/osteo_vision.yml` 作为颌骨骨髓炎 Demo 和 Benchmark 的共同运行配置。
- `configs/tasks/` 下的 TaskPackage 用于快速生成新比赛任务。
- `MedicalImagingInferenceService` 作为唯一推理入口。
- ModelSpec 和 adapter 契约覆盖 fixture、timm、MONAI Bundle、nnU-Net v2、MedSAM-like、VISTA3D-like、VLM encoder 等模型族。
- V3 实验契约覆盖 fixture 训练闭环、评估、阈值选择、模型卡、checkpoint manifest 和 promotion 草案。
- 分类、分割、检测、量化、多任务 fixture pipeline。
- 识别 2D 图像、NPZ ROI、DICOM 序列、NIfTI 体数据。
- 单病例报告、Benchmark 报告、指标、warning、发布资产模板。
- Vue 3 + TypeScript 前端、FastAPI 后端和 legacy Gradio Demo 骨架。
- unit、smoke、integration 测试。

## 快速命令

一键启动比赛严格模式前后端平台：

```cmd
start_platform.cmd
```

根目录只保留这一个用户启动入口。实际启动逻辑位于 `scripts/start_platform.ps1`。脚本默认复用或启动后端 `http://127.0.0.1:8001` 与前端 `http://127.0.0.1:5174/`，并在前端启动前完成比赛主线分割模型预热。如只想启动服务不自动打开浏览器：

```cmd
start_platform.cmd -NoBrowser
```

手动启动前后端：

```powershell
conda activate osteo-vision
python -m backend.src.main
```

后端默认地址：`http://127.0.0.1:8001/health`

另开一个终端启动前端：

```powershell
npm --prefix frontend run dev
```

前端默认地址：`http://127.0.0.1:5174/`

基础检查：

```powershell
conda run -n osteo-vision python check_env.py
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
conda run -n osteo-vision python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs
conda run -n osteo-vision python scripts/new_task.py --task-id my_competition --template classification --output-dir configs/tasks
conda run -n osteo-vision python scripts/new_experiment.py --experiment-id my_competition_fixture --manifest tests/fixtures/benchmark_manifest_v2.csv
conda run -n osteo-vision python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
conda run -n osteo-vision python scripts/promote_model.py --run-dir artifacts/runs/<run_id>
```

赛题对齐演示自查：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

该命令会生成 4K JPEG/MP4 代理输入，通过后端真实接口完成上传、双通道融合、MP4 关键帧分析、医生复核和 evidence bundle 导出。它只用于按赛题官方技术文档做工程自查，不是赛题方验收。输出默认写入 `artifacts/platform_smoke/competition_demo_check_*`，不进入 Git。

legacy Gradio Demo：

```powershell
python app/main.py --config configs/inference/osteo_vision.yml
```

## 复现当前闭环验证

推荐使用固定 Conda 环境 `osteo-vision`：

```powershell
conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise
conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary
conda run -n osteo-vision python -m pytest -q
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
conda run -n osteo-vision python tools\run_platform_smoke.py
conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 6 --keyframes 3
conda run -n osteo-vision python tools\run_mp4_edge_case_smoke.py --frames 48 --keyframes 5 --fps 6
conda run -n osteo-vision python tools\run_keyframe_tiling_smoke.py --width 3840 --height 2160
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml
conda run -n osteo-vision python tools\check_project_readiness.py
```

这些命令覆盖代码质量、前端构建、浏览器 E2E、JPEG/MP4 上传、4K 代理输入、关键帧分析、4K keyframe tiling 分割、荧光融合、复核导出和 evidence bundle。`run_competition_flow_demo_check.py` 是当前比赛故事线的赛题对齐演示自查入口，不是赛题方验收。所有 MP4 smoke 都是合成代理视频，不代表真实术中 ICG 颌骨骨髓炎视频。

## 二次开发方式

1. 在 `configs/tasks/` 新增 TaskPackage 比赛任务配置。
2. 选择或扩展 `src/pipelines/` 中的任务 pipeline。
3. 在 `src/models/` 中替换 fixture 模型适配器。
4. 保持 legacy Demo 和 Benchmark 都调用 `MedicalImagingInferenceService`；V1 平台后端通过服务层复用共享分析能力。
5. 正式实验输出写入 `artifacts/runs/<run_id>/`，并记录配置、任务包、模型规格、命令、指标、阈值和失败样本。

## V2 模型适配边界

V2 面向 VISTA3D、MedSAM2、nnU-Net v2、TotalSegmentator 类工作流、MONAI Bundles、BiomedCLIP、Rad-DINO、MedImageInsight 等医学影像推理模型族设计接口。本仓库不下载、不内置真实权重；缺依赖和缺权重会在 adapter status 中明确提示，fixture fallback 继续用于测试和演示。

## V3 训练闭环契约

V3 新增实验层。`ExperimentSpec` 记录任务包、manifest、模型候选、划分策略、训练配置、评估配置、阈值策略和 promotion gate。`scripts/run_experiment.py` 运行确定性 fixture 流程，并在 `artifacts/runs/<run_id>/` 写出 `training_report.json`、`evaluation_report.json`、`oof_predictions.csv`、`model_card.json`、`checkpoint_manifest.json` 和 `promotion_record.json`。

Promotion 只生成可审查草案。`scripts/promote_model.py` 读取 run 目录并输出 runtime patch draft，不会自动覆盖 `configs/inference/osteo_vision.yml`。默认 gate 会检查 patient-level 信息、泄漏风险、最低指标和安全声明。

## 安全边界

- 用户上传数据默认只用于当次推理。
- 原始医学数据、个人路径、大文件、checkpoint 不进入 Git。
- 报告必须包含平台安全边界免责声明。
- 不输出临床诊断承诺。

## 关键文档

- 项目规则：`AGENTS.md`
- 快速开始：`docs/quickstart.md`
- 导出证据包 schema：`docs/export_schema_v1.md`
- 比赛演示闭环说明：`research/reports/planning/competition_demo_closed_loop_20260704_zh.md`
- 当前缺口审计：`research/reports/planning/project_gap_followup_audit_20260704_zh.md`
