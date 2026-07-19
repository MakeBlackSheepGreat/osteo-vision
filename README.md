# osteo-vision

颌骨骨髓炎智能化荧光诊疗正式开发工作区。

本项目以医学影像比赛框架模板为工程底座，面向完整赛题原文中的三项核心答题要求开展开发：新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助显微成像判读。根目录就是正式开发工程；既有文献、数据清单、报告和外部模型快照统一归档到 `research/`。

当前项目原则和固定边界见 `AGENTS.md` 与 `.specify/memory/constitution.md`。完整赛题原文和赛题方设备技术文档均为本地忽略 PDF，不进入 Git；当前软件平台优先覆盖白光/ICG 融合、AI + 医生复核和结果导出三层；DICOM/远程协作只作为扩展亮点，不能替代造影剂设计要求。

## 当前可运行闭环

当前 V1 平台已经能跑通一个中规中矩的研发验证版平台闭环：

1. 创建病例。
2. 上传或登记官方边界内的 JPEG 图片、MP4 视频，优先按 4K `3840x2160`、JPEG、MP4 处理。
3. 对白光/ICG 图片执行伪彩增强、背景扣除、轻量配准、融合、色标生成和 ROI 定量。
4. 对 MP4 抽取关键帧，并运行当前比赛主线 Residual Attention U-Net keyframe 代理分割模型，生成 mask、probability map、伪彩和叠加结果。
5. 展示候选区域、荧光融合证据、时间线摘要、医生复核状态和导出证据。
6. 在医生标注页完成像素级人工标注、版本审计、身份记录和训练准入。
7. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP evidence bundle。

医学边界保持不变：当前输出是研发验证版平台结果，不能作为临床诊断结论；ICG 信号主要反映灌注和组织活性差异，不是颌骨骨髓炎特异性探针。

## 软件三项固定优先目标

1. 患者年龄、性别、基础病、用药和血液指标参与的受限患者条件分割，同时保留影像基础结果、条件结果、差异图和失败回退。
2. 在医生复核骨面内输出低活性候选、过渡复核区、高活性参考、无法判断区和连续骨活性评分，最终形成目标域多任务模型。
3. 通过离线 manifest 或人工元数据接入倍率、工作距离、相机标定、坐标变换和位姿，完成 CBCT/STL 的 L1 静态仿体配准与严格 L2 离线动态 AR 软件工程验证。

三项软件目标主要映射官方赛题第二项多模态图像融合处理和第三项 AI 辅助判读；第一项新型荧光造影剂设计及必要验证独立维护。固定母稿见 `research/reports/planning/three_priority_capabilities_target_20260717_zh.md`，验收与安全门控见 `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`。项目侧负责主动检索、下载和校验所需公开/代理数据。当前 15 份源数据 manifest 已覆盖 47 条记录、138 个本地文件、5,514,559,510 字节；所有源记录保持非目标域和未训练准入状态。D069 MMDental 已从 68,087,010,723 字节 ZIP64 远程包中选择性物化 660 个患者的 2,124 条就诊记录及 1 例配对牙科 CBCT，并完成未配准硬组织代理表面建模；其聚合质控记录了 390 个多次就诊患者、2 个年龄冲突患者、0 个性别冲突患者和逐字段缺失量。D087 C3VD 官方样例已完成 1,515,094,074 字节下载、ZIP CRC 和 SHA256 校验，包含 766 对 RGB/depth 帧及 2,558 条位姿记录；平台另行安全物化 53 个必要资产共 106,975,431 字节，将 766 帧全部绑定到去重后的 2,556 条位姿，并完成 OCamCalib 投影、24 帧回放及三类失效注入。D090 已新增 3 段 1080p 人体乳腺前哨淋巴结 ICG 视频；D091 已新增 2 段肝切除 ICG 三面板视频，并经抽帧确认画面同时包含白光、伪彩叠加和灰度荧光显示。D094/D095 新增 53 例 ORNJ 临床影像判读表和 1,129 例头颈放疗 ORNJ 结局/下颌剂量学表，用于患者条件字段映射、患者级分组和亚组审计。上述资源均缺少可直接支撑目标域空间分割的联合影像与像素标注。

患者条件和骨活性模型已有非目标域代理训练闭环。KiTS23 患者条件代理复跑 288 个训练批次，测试 Dice/IoU/召回率/精确率为 `0.243974/0.151192/0.195572/0.553163`，ECE 为 `0.005700`，相对影像基础 Dice 的差值为 `-0.000214`，最大物理边界位移为 `183.478 mm`；no-harm 与 provisional `2 mm` 边界门均失败。D074 人脑 PpIX 显微荧光代理采用 3 个患者组、5 个真实图像样本完成骨活性多任务训练，冻结测试 macro Dice 为 `0.733064`，骨面 Dice 为 `0.102190`，非拒答覆盖率为 `0.056417`，选择性错误率为 `0.301527`；测试安全约束失败，`engineering_utility_ready=false`。两项模型均保持 `target_domain_promotion_ready=false` 和 `runtime_replacement_allowed=false`。L1/L2 证据现强制绑定坐标 frame、手性、轴方向、单位和矩阵约定；任一 provenance、标定、同步、误差或医生复核门失败均回退 L0。真实设备全倍率/全工作距离 4K 标定和真实下颌仿体物理证据尚未完成，真实病例导航默认保持 `navigation_ready=false`。

目标域晋级器现从 SHA256 绑定的逐病例预测与医生复核真值独立重算全部指标，并要求医生与项目复核员使用不同 Ed25519 密钥双签。后端提供认证审批、追加式哈希链、防重放、撤销、状态和 bundle API；离线 CLI 负责仓库外密钥、公钥信任表合并、精确目标载荷和签名；最终晋级器再次重放证据、哈希链、签名和密钥状态。生产策略哈希与公钥信任表继续保持为空，T101/T102/T107 在真实目标域数据和正式审批到位前持续关闭。操作流程见 `docs/promotion_approval_offline.md`。

2026-07-19 最终全量工程自测通过：后端 253 项，核心 unit/smoke 584 项，前端 48 个测试文件共 186 项通过、1 项跳过，Playwright E2E 5 项通过，`vue-tsc` 与 Vite build 通过。`NavigationWorkspacePage` 路由块约 61.97 kB，三维视口作为约 709.67 kB 的异步块按需加载；Vite 仅对该独立三维块保留大块提示。该结果属于项目工程自测。

## 当前模型状态

当前可运行模型/规则：

- `convnext3d_d025_proxy_segmenter`：D025 CBCT ROI 代理分割模型，用于工程闭环验证。
- `d025_lesion_smoke_segmenter`：同一 D025 代理 checkpoint 的 smoke/兼容入口。
- `keyframe_residual_attention_unet_s20260715_20260715`：当前 MP4/JPEG keyframe 比赛主线；代理测试集 Dice `0.9177`、IoU `0.8483`，三种子 Dice `0.9149 +/- 0.0041`，运行阈值 `0.4`。
- `convnext2d_keyframe_proxy_segmenter`：保留为上一代 2D ConvNeXt-style 代理对照模型。
- 当前 keyframe 主线支持 4K patch/tiling 推理和 960 长边实时 fast-output。比赛严格配置关闭启发式回退；研发配置保留 hotspot 对照能力。
- `fluorescence_hotspot_2d_segmenter`：MP4/JPEG keyframe 的阈值和连通域 hotspot baseline，作为回退和可解释对照。
- `medsam2_osteo_promptable`：MedSAM/SAM2 风格 prompt contract fallback，可用医生 ROI/bbox/point 生成可复核 mask；缺真实 MedSAM2 checkpoint，不能写成真实 MedSAM2 推理。
- `fixture_default`：测试和兜底 fixture。

当前不可声称已完成的模型：

- `nnunet_v2_osteo_baseline`：缺 checkpoint 和 adapter inference。
- `biomedclip_osteo_screening`：缺 `open_clip`、checkpoint 和 adapter inference。

最新 D025 代理模型评估见 `research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`。该评估不是术中 ICG 颌骨骨髓炎目标域性能。
2D keyframe 模型选型见 `research/reports/modeling/keyframe_model_selection_summary_20260715_zh.md`；4K 门控见 `research/reports/modeling/keyframe_residual_attention_4k_runtime_gate_20260715_zh.md`；实时 fast-output 门控见 `research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md`。
MedSAM-like prompt fallback 说明见 `research/reports/modeling/medsam_prompt_contract_20260704_zh.md`。

当前 2D MP4/JPEG keyframe segmentation path is runnable end to end:

```powershell
conda run -n osteo-vision python tools\build_keyframe_segmentation_proxy_manifest.py --input research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705 --dataset-id d046_mp4_proxy --input-domain public_fluorescence_or_osteomyelitis_proxy_mp4 --fluorescence-attribute mixed_fluorescence_and_non_fluorescence --max-frames-per-video 4 --max-samples 200 --threshold 0.62 --min-component-area 32 --min-positive-area-fraction 0.0005 --max-positive-area-fraction 0.6 --preview-sample-count 40 --review-seed-sample-count 50
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 160x256 --max-train-batches 160 --batch-size 4 --base-channels 12 --learning-rate 0.0007 --threshold 0.15 --device auto --report-stamp 20260705_threshold_calibrated
conda run -n osteo-vision python scripts\evaluate_keyframe_segmentation_proxy.py --checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-dir research\reports\modeling\keyframe_threshold_eval_20260705 --image-shape 160x256 --split val --device auto
```

These commands preserve the previous ConvNeXt baseline training path. The current competition mainline was promoted through three-seed selection, a locked test split, 4K tiled execution, the complete competition flow, and a 960-pixel live fast-output gate. Physician annotations saved through `/annotations` can be admitted with `tools\build_keyframe_training_manifest_from_manual_annotations.py`; trusted accepted/modified labels receive higher training weight while engineering or unreviewed labels remain isolated. Raw frames, masks, annotation versions, and checkpoints remain local artifacts.

The direct 4K/tiling keyframe segmentation path can be checked separately:

```powershell
conda run -n osteo-vision python tools\run_keyframe_tiling_smoke.py --width 3840 --height 2160
```

This calls the mainline `keyframe_residual_attention_unet_s20260715_20260715` adapter and verifies mask, probability map, pseudocolor overlay, and tiled inference metadata. Outputs are written under `artifacts/platform_smoke/keyframe_tiling_*` and are not committed to Git.

## 当前目录

```text
osteo-vision/
├── app/
│   └── main.py                # legacy Gradio Demo 入口
├── backend/                   # FastAPI 后端服务
├── configs/                   # 任务、推理和路径配置
├── frontend/                  # Vue 3 + TypeScript 前端
├── src/                       # 医学影像推理、训练、评估框架源码
├── scripts/                   # 训练、评估、Benchmark、模型清单脚本
├── tests/                     # unit、smoke、integration 测试
├── artifacts/                 # 运行产物和占位目录
├── docs/                      # 架构、快速开始、任务适配文档
├── research/
│   ├── literature/inventory/  # 论文、数据集清单、可行性报告、PDF 资料
│   ├── planning/              # 数据获取计划、工程路线图、下载状态
│   ├── reports/               # 既有 DOCX/XLSX 项目资料
│   ├── model-snapshots/code/  # nnU-Net、EGNet、FRS Loss 等外部代码快照
│   ├── datasets/              # 公开候选数据集落地目录
│   ├── media/                 # 原始图片素材
│   └── scripts/legacy/        # 旧报告生成和下载脚本
├── tools/
│   └── check_project_readiness.py
├── AGENTS.md
├── LICENSE
└── README.md
```

## 开发入口

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

如需临时覆盖端口：

- 后端端口：`OSTEO_BACKEND_PORT`
- 前端端口：`OSTEO_FRONTEND_PORT`
- 前端 API 地址：`VITE_OSTEO_API_URL`
- CORS 来源：`OSTEO_ALLOWED_ORIGINS`

基础检查：

```powershell
conda run -n osteo-vision python check_env.py
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
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

颌骨骨髓炎项目配置入口：

- `configs/tasks/osteo_vision.yml`
- `configs/inference/osteo_vision.yml`

## 复现当前闭环验证

推荐在固定 Conda 环境 `osteo-vision` 中运行：

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

## 资料入口

- 文献与数据集清单：`research/literature/inventory/`
- 工程准备路线：`research/planning/engineering_preparation.md`
- 数据获取计划：`research/planning/data_acquisition_plan.md`
- 外部模型快照：`research/model-snapshots/code/`
- 导出证据包 schema：`docs/export_schema_v1.md`
- 比赛演示闭环说明：`research/reports/planning/competition_demo_closed_loop_20260704_zh.md`
- 当前缺口审计：`research/reports/planning/project_gap_followup_audit_20260704_zh.md`

## 自检

```powershell
conda run -n osteo-vision python tools/check_project_readiness.py
```

该脚本只做只读检查，用于确认资料归档、候选数据集目录、开发框架和本机工具是否就绪。
