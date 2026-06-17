# 快速开始

开始开发前请先阅读根目录 `AGENTS.md` 和 `.specify/memory/constitution.md`。本项目输出均为研究和竞赛原型结果，开发时必须保留医生复核边界、数据治理规则和可复现证据。

## 环境准备

### 使用 Conda

```powershell
conda env create -f environment.yml
conda activate osteo-vision
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
python check_env.py
python -m pytest tests/unit tests/smoke tests/integration
python check_all.py
```

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
python -m backend.src.main
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
python app/main.py --config configs/inference/osteo_vision.yml
```

或者使用 Makefile：

```powershell
make demo
```

如果 Gradio 未安装，应用导入测试仍然通过，启动器会报告 UI 依赖缺失。

## 运行基准测试

```powershell
python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs
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
python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
python scripts/new_task.py --task-id my_competition --template classification --output-dir configs/tasks
python scripts/compare_models.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest_v2.csv --output artifacts/runs/model_comparison --models fixture_default
```

## V3 实验命令

```powershell
python scripts/new_experiment.py --experiment-id my_competition_fixture --manifest tests/fixtures/benchmark_manifest_v2.csv
python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
python scripts/promote_model.py --run-dir artifacts/runs/<run_id>
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
python -c "from src.core.config_validator import validate_config_file; print(validate_config_file('configs/inference/osteo_vision.yml'))"
```

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
