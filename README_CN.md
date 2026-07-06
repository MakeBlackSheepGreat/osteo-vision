# osteo-vision 开发框架

本仓库是颌骨骨髓炎智能化荧光诊疗项目的正式开发工程，基于通用医学影像比赛框架模板整理而来，用于分类、分割、检测、量化、可解释性、报告、Demo 和 Benchmark 开发。

完整赛题原文和赛题方设备技术文档均为本地忽略 PDF，不进入 Git。后续方案优先围绕完整赛题的三项核心答题要求展开：新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助显微成像判读。DICOM/远程协作只能作为扩展亮点，不能替代造影剂设计要求。

本仓库只用于科研、教学、比赛和受控演示。所有输出都不是临床诊断，不能替代医生复核。

## 当前可运行闭环

当前 V1 平台已经能跑通一个研发验证版平台闭环：

1. 创建病例。
2. 上传或登记 JPEG 图片、MP4 视频，优先贴合赛题官方设备边界：4K `3840x2160`、JPEG、MP4。
3. 对白光/ICG 图片执行伪彩增强、背景扣除、轻量配准、融合、色标生成和 ROI 定量。
4. 对 MP4 抽取关键帧，并优先运行可训练的 2D ConvNeXt-style keyframe 代理分割模型，生成 mask、probability map、伪彩和叠加结果；模型不可用时回退到 fluorescence hotspot baseline。
5. 在 Vue 工作台展示候选区域、荧光融合证据、时间线摘要、医生复核状态和导出证据。
6. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP evidence bundle。

当前仍是研发验证版平台。ICG 信号主要反映灌注和组织活性差异，不是颌骨骨髓炎特异性探针；平台输出只能作为术中参考信号、风险提示和医生复核辅助。

## 当前模型状态

可运行：

- `convnext3d_d025_proxy_segmenter`：D025 CBCT ROI 代理分割模型，用于工程闭环验证。
- `d025_lesion_smoke_segmenter`：同一 D025 代理 checkpoint 的 smoke/兼容入口。
- `convnext2d_keyframe_proxy_segmenter`：MP4/JPEG keyframe 的可训练 2D ConvNeXt-style 代理分割模型，当前训练数据为合成/伪标注荧光代理帧，不代表真实术中 ICG 颌骨骨髓炎性能。
- 该 keyframe 模型默认支持 4K 友好的 patch/tiling 推理，超过配置阈值的关键帧会分块聚合概率图并记录 tile 元数据；若模型输出空 mask，MP4 分析会回退到 fluorescence hotspot baseline，避免医生复核候选区完全中断。
- `fluorescence_hotspot_2d_segmenter`：MP4/JPEG keyframe 的阈值和连通域 hotspot baseline，作为回退和可解释对照。
- `medsam2_osteo_promptable`：MedSAM/SAM2 风格 prompt contract fallback，可用医生 ROI/bbox/point 生成可复核 mask；缺真实 MedSAM2 checkpoint，不能写成真实 MedSAM2 推理。
- `fixture_default`：测试和兜底 fixture。

尚不可用：

- `nnunet_v2_osteo_baseline`：缺 checkpoint 和 adapter inference。
- `biomedclip_osteo_screening`：缺 `open_clip`、checkpoint 和 adapter inference。

最新 D025 代理模型评估见 `research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`。该评估不能代表真实术中 ICG 颌骨骨髓炎目标域性能。
2D keyframe 代理分割模型报告见 `research/reports/modeling/keyframe_convnext2d_proxy_segmenter_20260705_threshold_calibrated_zh.md`；阈值扫描报告见 `research/reports/modeling/keyframe_threshold_eval_20260705/keyframe_threshold_eval_zh.md`。
MedSAM-like prompt fallback 说明见 `research/reports/modeling/medsam_prompt_contract_20260704_zh.md`。

2D MP4/JPEG keyframe 分割模型当前已有可运行训练链路：

```powershell
conda run -n osteo-vision python tools\build_keyframe_segmentation_proxy_manifest.py --input research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705 --dataset-id d046_mp4_proxy --input-domain public_fluorescence_or_osteomyelitis_proxy_mp4 --fluorescence-attribute mixed_fluorescence_and_non_fluorescence --max-frames-per-video 4 --max-samples 200 --threshold 0.62 --min-component-area 32 --min-positive-area-fraction 0.0005 --max-positive-area-fraction 0.6 --preview-sample-count 40 --review-seed-sample-count 50
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 160x256 --max-train-batches 160 --batch-size 4 --base-channels 12 --learning-rate 0.0007 --threshold 0.15 --device auto --report-stamp 20260705_threshold_calibrated
conda run -n osteo-vision python scripts\evaluate_keyframe_segmentation_proxy.py --checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-dir research\reports\modeling\keyframe_threshold_eval_20260705 --image-shape 160x256 --split val --device auto
```

这条链路会从公开 MP4/图片代理数据生成 200 条伪标注 mask manifest，并产生 50 条人工复核种子集，再训练主线 `convnext2d_keyframe_proxy_segmenter` checkpoint，并扫描运行阈值的空 mask/过分割风险。当前校准后的代理结果使用阈值 `0.15`，在 D046 伪标注验证集上 Dice 为 `0.9093`、IoU 为 `0.8340`。导出的 `review_manifest_json/csv` 可通过 `tools\build_keyframe_training_manifest_from_review.py` 转成下一轮训练 manifest；`accepted` / `modified` 样本会写入更高 `sample_weight`，显式启用时 `rejected` 候选区可作为低权重负例或错误分析样本。生成的原始帧、mask、复核种子集和 checkpoint 均为本地运行产物，不进入 Git。

单帧 4K/tiling 分割推理可单独验证：

```powershell
conda run -n osteo-vision python tools\run_keyframe_tiling_smoke.py --width 3840 --height 2160
```

该命令直接调用主线 `convnext2d_keyframe_proxy_segmenter` adapter，验证 keyframe mask、probability map、伪彩叠加图和 tiled inference 元数据是否完整；输出写入 `artifacts/platform_smoke/keyframe_tiling_*`，不进入 Git。

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
