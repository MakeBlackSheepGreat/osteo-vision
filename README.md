# osteo-vision

颌骨骨髓炎智能化荧光诊疗正式开发工作区。

本项目以医学影像比赛框架模板为工程底座，面向完整赛题原文中的三项核心答题要求开展开发：新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助显微成像判读。根目录就是正式开发工程；既有文献、数据清单、报告和外部模型快照统一归档到 `research/`。

当前项目原则和固定边界见 `AGENTS.md` 与 `.specify/memory/constitution.md`。完整赛题原文和赛题方设备技术文档均为本地忽略 PDF，不进入 Git；当前软件平台优先覆盖白光/ICG 融合、AI + 医生复核和结果导出三层；DICOM/远程协作只作为扩展亮点，不能替代造影剂设计要求。

## 当前可运行闭环

当前 V1 平台已经能跑通一个中规中矩的研究/比赛原型闭环：

1. 创建病例。
2. 上传或登记官方边界内的 JPEG 图片、MP4 视频，优先按 4K `3840x2160`、JPEG、MP4 处理。
3. 对白光/ICG 图片执行伪彩增强、背景扣除、轻量配准、融合、色标生成和 ROI 定量。
4. 对 MP4 抽取关键帧，并优先运行可训练的 2D ConvNeXt-style keyframe 代理分割模型，生成 mask、probability map、伪彩和叠加结果；模型不可用时回退到 fluorescence hotspot baseline。
5. 展示候选区域、荧光融合证据、时间线摘要、医生复核状态和导出证据。
6. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP evidence bundle。

医学边界保持不变：当前输出是科研和竞赛原型结果，不能作为临床诊断结论；ICG 信号主要反映灌注和组织活性差异，不是颌骨骨髓炎特异性探针。

## 当前模型状态

当前可运行模型/规则：

- `convnext3d_d025_proxy_segmenter`：D025 CBCT ROI 代理分割模型，用于工程闭环验证。
- `d025_lesion_smoke_segmenter`：同一 D025 代理 checkpoint 的 smoke/兼容入口。
- `convnext2d_keyframe_proxy_segmenter`：MP4/JPEG keyframe 的可训练 2D ConvNeXt-style 代理分割模型，当前训练数据为合成/伪标注荧光代理帧，不代表真实术中 ICG 颌骨骨髓炎性能。
- 该 keyframe 模型默认支持 4K 友好的 patch/tiling 推理，超过配置阈值的关键帧会分块聚合概率图并记录 tile 元数据。
- `fluorescence_hotspot_2d_segmenter`：MP4/JPEG keyframe 的阈值和连通域 hotspot baseline，作为回退和可解释对照。
- `medsam2_osteo_promptable`：MedSAM/SAM2 风格 prompt contract fallback，可用医生 ROI/bbox/point 生成可复核 mask；缺真实 MedSAM2 checkpoint，不能写成真实 MedSAM2 推理。
- `fixture_default`：测试和兜底 fixture。

当前不可声称已完成的模型：

- `nnunet_v2_osteo_baseline`：缺 checkpoint 和 adapter inference。
- `biomedclip_osteo_screening`：缺 `open_clip`、checkpoint 和 adapter inference。

最新 D025 代理模型评估见 `research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`。该评估不是术中 ICG 颌骨骨髓炎目标域性能。
2D keyframe 代理分割模型报告见 `research/reports/modeling/keyframe_convnext2d_proxy_segmenter_20260705_zh.md`。
MedSAM-like prompt fallback 说明见 `research/reports/modeling/medsam_prompt_contract_20260704_zh.md`。

当前 2D MP4/JPEG keyframe segmentation path is runnable end to end:

```powershell
conda run -n osteo-vision python tools\build_keyframe_segmentation_proxy_manifest.py --input research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705 --dataset-id d046_mp4_proxy --input-domain public_fluorescence_or_osteomyelitis_proxy_mp4 --fluorescence-attribute mixed_fluorescence_and_non_fluorescence --max-frames-per-video 4 --max-samples 200 --threshold 0.62 --min-component-area 32 --min-positive-area-fraction 0.0005 --max-positive-area-fraction 0.6 --preview-sample-count 40 --review-seed-sample-count 50
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 128x192 --max-train-batches 80 --batch-size 4 --base-channels 8 --learning-rate 0.001 --threshold 0.5 --device auto --report-stamp 20260705
```

This builds a 200-sample pseudo-mask manifest from public MP4/image proxy data, creates a 50-row review seed set, and trains the mainline `convnext2d_keyframe_proxy_segmenter` checkpoint. Exported `review_manifest_json/csv` files can be converted back into the next training manifest with `tools\build_keyframe_training_manifest_from_review.py`; accepted/modified rows receive higher `sample_weight`, and rejected candidates can be kept as low-weight negative/error-analysis rows when explicitly requested. `scripts\train_keyframe_segmentation_proxy.py` now accepts multiple manifests under one `--manifest` flag and applies `sample_weight` during loss computation. Extracted frames, masks, review seeds, and checkpoints are local artifacts and are not committed to Git.

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

V1 前后端分离平台：

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
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml
conda run -n osteo-vision python tools\check_project_readiness.py
```

这些命令覆盖代码质量、前端构建、浏览器 E2E、JPEG/MP4 上传、4K 代理输入、关键帧分析、荧光融合、复核导出和 evidence bundle。`run_competition_flow_demo_check.py` 是当前比赛故事线的赛题对齐演示自查入口，不是赛题方验收。所有 MP4 smoke 都是合成代理视频，不代表真实术中 ICG 颌骨骨髓炎视频。

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
