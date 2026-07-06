# 快速开始

开始开发前请先阅读根目录 `AGENTS.md` 和 `.specify/memory/constitution.md`。本项目输出均为研究和竞赛平台验证结果，开发时必须保留医生复核边界、数据治理规则和可复现证据。

## 环境准备

### 使用 Conda

```powershell
conda env create -f environment.yml
conda activate osteo-vision
```

本项目固定使用 Conda 环境 `osteo-vision`。如果当前终端不方便激活环境，所有 Python 命令都应显式使用：

```powershell
conda run -n osteo-vision python <script-or-module>
```

### 使用 pip

```powershell
pip install -r requirements.txt
```

### 安装开发依赖

```powershell
pip install -e ".[dev]"
```

## 验证环境

```powershell
conda run -n osteo-vision python check_env.py
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python tools/check_project_readiness.py
```

赛题对齐演示自查：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

该命令默认生成 4K JPEG/MP4 代理输入，并通过真实后端接口跑完上传、白光/ICG 融合、MP4 关键帧分析、医生复核和 evidence bundle 导出。它只用于按赛题官方技术文档做工程自查，不是赛题方验收。输出目录为 `artifacts/platform_smoke/competition_demo_check_*`。

## 训练 2D Keyframe 分割模型

从公开 MP4/图片代理数据生成 keyframe + 伪 mask manifest：

```powershell
conda run -n osteo-vision python tools\build_keyframe_segmentation_proxy_manifest.py --input research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705 --dataset-id d046_mp4_proxy --input-domain public_fluorescence_or_osteomyelitis_proxy_mp4 --fluorescence-attribute mixed_fluorescence_and_non_fluorescence --max-frames-per-video 4 --max-samples 200 --threshold 0.62 --min-component-area 32 --min-positive-area-fraction 0.0005 --max-positive-area-fraction 0.6 --preview-sample-count 40 --review-seed-sample-count 50
```

训练当前主线 2D ConvNeXt-style keyframe 代理分割 checkpoint：

```powershell
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 160x256 --max-train-batches 160 --batch-size 4 --base-channels 12 --learning-rate 0.0007 --threshold 0.15 --device auto --report-stamp 20260705_threshold_calibrated
```

扫描运行阈值、空 mask 率和过分割率：

```powershell
conda run -n osteo-vision python scripts\evaluate_keyframe_segmentation_proxy.py --checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv --output-dir research\reports\modeling\keyframe_threshold_eval_20260705 --image-shape 160x256 --split val --device auto
```

该模型是可运行的软件闭环模型，训练标签来自荧光强度伪标注或代理数据；当前 20260705 manifest 为 200 条代理 keyframe，并另有 50 条人工复核种子集。当前校准阈值为 `0.15`，D046 伪标注验证 Dice 为 `0.9093`、IoU 为 `0.8340`、空 mask 率为 `0`。相关 Dice/IoU 只能作为代理伪标签验证结果，不能作为真实术中 ICG 颌骨骨髓炎分割性能。

单独验证官方规格 keyframe 的 patch/tiling 推理、mask 尺寸和叠加图输出：

```powershell
conda run -n osteo-vision python tools\run_keyframe_tiling_smoke.py --width 3840 --height 2160
```

该命令直接调用 `convnext2d_keyframe_proxy_segmenter` adapter；默认期望进入 tiled inference，并检查 mask、probability map、伪彩 overlay 和元数据完整性。输出写入 `artifacts/platform_smoke/keyframe_tiling_*`，不进入 Git。

从 evidence bundle 导出的医生复核 manifest 生成下一轮训练 manifest：

```powershell
conda run -n osteo-vision python tools\build_keyframe_training_manifest_from_review.py --input <export_dir>\<case_id>_review_manifest.json --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\review_feedback_20260705 --dataset-id review_feedback --input-domain reviewed_proxy_keyframe_non_target_domain --fluorescence-attribute proxy_or_unknown_fluorescence
```

该命令默认只提升 `accepted` / `modified` 复核样本，输出仍属于代理或非目标域训练反馈。若需要把 `rejected` 候选区作为低权重负例或错误分析样本，可显式加入：

```powershell
conda run -n osteo-vision python tools\build_keyframe_training_manifest_from_review.py --input <export_dir>\<case_id>_review_manifest.json --output-dir research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\review_feedback_20260705 --dataset-id review_feedback --input-domain reviewed_proxy_keyframe_non_target_domain --fluorescence-attribute proxy_or_unknown_fluorescence --review-states accepted,modified,rejected --accepted-weight 3.0 --modified-weight 4.0 --rejected-weight 0.5
```

训练脚本支持把原始 proxy manifest 与复核反馈 manifest 合并，并按 `sample_weight` 加权 loss：

```powershell
conda run -n osteo-vision python scripts\train_keyframe_segmentation_proxy.py --manifest research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_proxy_manifest.csv research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\review_feedback_20260705\keyframe_training_manifest_from_review.csv --output-checkpoint artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt --image-shape 160x256 --max-train-batches 160 --batch-size 4 --base-channels 12 --learning-rate 0.0007 --threshold 0.15 --device auto --report-stamp 20260705_review_feedback
```

进入下一轮训练前，需要确认样本已脱敏且复核来源可追溯；这些权重只代表复核可信度或错误分析优先级，不等同于真实术中 ICG 颌骨骨髓炎像素级医生标注。

## 使用 Makefile（推荐）

框架提供了 Makefile 来简化常用命令：

```powershell
# 显示所有可用命令
make help

# 安装依赖
make install

# 安装开发依赖
make install-dev

# 运行所有测试
make test

# 运行单元测试
make test-unit

# 运行集成测试
make test-integration

# 运行冒烟测试
make test-smoke

# 运行测试并生成覆盖率报告
make test-coverage

# 代码格式化
make format

# 代码检查
make lint

# 类型检查
make type-check

# 运行所有检查
make check-all

# 验证配置
make validate-config

# 显示模型清单
make model-inventory

# 运行基准测试
make benchmark

# 启动 V1 后端
make platform-backend

# 启动 V1 前端
make platform-frontend

# 启动 legacy Gradio Demo
make demo

# 清理临时文件
make clean
```

## 运行 V1 平台

后端：

```powershell
conda run -n osteo-vision python -m backend.src.main
```

默认健康检查地址：`http://127.0.0.1:8001/health`

前端：

```powershell
npm --prefix frontend run dev
```

默认网页地址：`http://127.0.0.1:5174/`

端口覆盖：

- `OSTEO_BACKEND_PORT`：后端端口，默认 `8001`
- `OSTEO_FRONTEND_PORT`：前端端口，默认 `5174`
- `VITE_OSTEO_API_URL`：前端访问后端的 API 地址，默认 `http://127.0.0.1:8001`
- `OSTEO_ALLOWED_ORIGINS`：后端 CORS 来源列表

## 运行 Legacy Gradio Demo

```powershell
conda run -n osteo-vision python app/main.py --config configs/inference/osteo_vision.yml
```

或者使用 Makefile：

```powershell
make demo
```

如果 Gradio 未安装，应用导入测试仍然通过，启动器会报告 UI 依赖缺失。

## 运行基准测试

```powershell
conda run -n osteo-vision python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs
```

或者使用 Makefile：

```powershell
make benchmark
```

输出：

- `artifacts/runs/<run_id>/predictions.csv`
- `artifacts/runs/<run_id>/metrics.json`
- `artifacts/runs/<run_id>/benchmark_report.json`
- `artifacts/runs/<run_id>/threshold_analysis.md`
- `artifacts/runs/<run_id>/model_specs.json`
- `artifacts/runs/<run_id>/task_package_snapshot.yml`

## V2 脚手架命令

```powershell
conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
conda run -n osteo-vision python scripts/new_task.py --task-id my_competition --template classification --output-dir configs/tasks
conda run -n osteo-vision python scripts/compare_models.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest_v2.csv --output artifacts/runs/model_comparison --models fixture_default
```

## V3 实验命令

```powershell
conda run -n osteo-vision python scripts/new_experiment.py --experiment-id my_competition_fixture --manifest tests/fixtures/benchmark_manifest_v2.csv
conda run -n osteo-vision python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
conda run -n osteo-vision python scripts/promote_model.py --run-dir artifacts/runs/<run_id>
```

实验输出：

- `artifacts/runs/<run_id>/training_report.json`
- `artifacts/runs/<run_id>/evaluation_report.json`
- `artifacts/runs/<run_id>/oof_predictions.csv`
- `artifacts/runs/<run_id>/model_card.json`
- `artifacts/runs/<run_id>/checkpoint_manifest.json`
- `artifacts/runs/<run_id>/promotion_record.json`
- `artifacts/runs/<run_id>/runtime_promotion_draft.json`（当请求生成推广草案时）

推广命令仅创建草案。在将补丁应用到 `configs/inference/osteo_vision.yml` 之前，请审查草案。

## 代码质量工具

框架集成了以下代码质量工具：

### Black（代码格式化）

```powershell
black src/ tests/ --line-length=120
```

### isort（导入排序）

```powershell
isort src/ tests/ --profile black --line-length=120
```

### Flake8（代码检查）

```powershell
flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503
```

### Mypy（类型检查）

```powershell
mypy src/ --ignore-missing-imports
```

### Pre-commit（Git 提交前检查）

```powershell
# 安装 pre-commit 钩子
pre-commit install

# 手动运行所有钩子
pre-commit run --all-files
```

## 配置验证

```powershell
conda run -n osteo-vision python -c "from src.core.config_validator import validate_config_file; print(validate_config_file('configs/inference/osteo_vision.yml'))"
```

## 当前闭环验证

以下命令用于复现当前“上传/分析/复核/导出”的可运行闭环：

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
```

`run_platform_smoke.py` 覆盖 JPEG/MP4 上传、分析 job、复核导出和 evidence bundle。`run_official_4k_pressure_smoke.py` 覆盖官方 4K JPEG/MP4 代理输入。`run_mp4_edge_case_smoke.py` 覆盖低分辨率 warning、坏签名 415 和不可解码 MP4 422。`run_keyframe_tiling_smoke.py` 直接验证 4K keyframe 分割的 tiled inference、mask 尺寸和叠加输出。`run_competition_flow_demo_check.py` 是当前比赛演示的赛题对齐自查入口，会检查 4K JPEG 融合、4K MP4 关键帧分析、医生复核、导出格式和主线模型可用性；它不是赛题方验收。所有 smoke 视频均为合成代理视频，不代表真实术中 ICG 颌骨骨髓炎视频。

导出证据包字段见 [Export Schema V1](export_schema_v1.md)。

## 日志系统

框架提供了统一的日志系统：

```python
from src.utils.logging import get_logger

logger = get_logger(__name__)

logger.info("这是一条信息")
logger.warning("这是一条警告")
logger.error("这是一条错误")

# 专用日志方法
logger.performance("model_inference", 150.5, model_id="my_model")
logger.lifecycle("inference_service", "initialized")
logger.inference("case_001", "my_model", "classification", 120.3)
logger.training(epoch=1, loss=0.5, metric=0.85)
```

## 下一步

- 阅读 [架构概述](architecture.md) 了解框架设计
- 阅读 [任务适配器指南](task_adapter_guide.md) 了解如何接入新比赛
- 查看 [技能规则库](../.rules/README.md) 了解开发规范


## V1 Platform Notes

- The local V1 platform now uses a Vue frontend in `frontend/` and a FastAPI backend in `backend/`.
- The backend stores local case metadata under `artifacts/platform/` by default.
- Runtime inputs should remain de-identified and local.
- Large generated artifacts, raw medical data, and checkpoints stay out of Git.
