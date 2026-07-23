# osteo-vision platform workspace commands

PYTHON ?= python

THREE_D_RUNTIME_DIR ?= frontend/three-d-runtime
THREE_D_RUNTIME_PORT ?= 5175

.PHONY: help install install-dev test test-core test-backend test-unit test-integration test-smoke test-frontend test-e2e lint format format-check type-check check-all release-check validate-config model-inventory benchmark platform platform-backend platform-frontend platform-three-d-runtime three-d-runtime-install three-d-runtime-dev three-d-runtime-preview three-d-runtime-typecheck three-d-runtime-test three-d-runtime-check three-d-runtime-build demo-compat docs-audit readiness performance-baseline clean clean-artifacts clean-all version build release-build

help: ## 显示命令清单
	@echo "osteo-vision platform"
	@echo "===================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

install: ## 安装运行依赖
	$(PYTHON) -m pip install -r requirements.txt
	npm --prefix frontend install
	npm --prefix $(THREE_D_RUNTIME_DIR) ci

install-dev: ## 安装项目与开发依赖
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e ".[dev]"
	npm --prefix frontend install
	npm --prefix $(THREE_D_RUNTIME_DIR) ci

test: test-core test-backend test-frontend ## 运行核心、后端和前端测试

test-core: ## 运行核心完整测试
	$(PYTHON) -m pytest tests

test-backend: ## 运行后端测试
	$(PYTHON) -m pytest backend/tests

test-unit: ## 运行全部单元测试目录
	$(PYTHON) -m pytest tests/unit backend/tests/unit

test-integration: ## 运行集成测试
	$(PYTHON) -m pytest tests/integration

test-smoke: ## 运行冒烟测试
	$(PYTHON) -m pytest tests/smoke

test-frontend: ## 运行 Vue 组件测试
	npm --prefix frontend test -- --run

test-e2e: ## 运行桌面端 Playwright E2E
	npm --prefix frontend run test:e2e

lint: ## 运行 Ruff 静态检查
	$(PYTHON) -m ruff check src backend app tests scripts tools

format: ## 格式化 Python 代码
	$(PYTHON) -m black src backend app tests scripts tools --line-length=120
	$(PYTHON) -m isort src backend app tests scripts tools --profile black --line-length=120

format-check: ## 检查 Python 格式
	$(PYTHON) -m black --check src backend app tests scripts tools --line-length=120
	$(PYTHON) -m isort --check-only src backend app tests scripts tools --profile black --line-length=120

type-check: ## 运行 Python 与 Vue 类型检查
	$(PYTHON) -m mypy src backend --config-file=pyproject.toml --hide-error-context --no-error-summary
	npm --prefix frontend run typecheck

check-all: lint type-check test ## 运行主要质量门

release-check: check-all three-d-runtime-check ## 运行平台与独立三维运行时发布质量门

validate-config: ## 验证主推理配置
	$(PYTHON) -c "from src.core.config_validator import validate_config_file; print(validate_config_file('configs/inference/osteo_vision.yml'))"

model-inventory: ## 输出模型清单
	$(PYTHON) scripts/model_inventory.py --config configs/inference/osteo_vision.yml

benchmark: ## 运行通用推理基准
	$(PYTHON) scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs

performance-baseline: ## 运行核心热路径性能与输出一致性基准
	$(PYTHON) tools/benchmark_core_hotpaths.py --output artifacts/performance/core_hotpaths_current.json

platform: ## 启动比赛严格模式平台
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_platform.ps1 -StrictCompetition

platform-backend: ## 启动 FastAPI 后端
	$(PYTHON) -m backend.src.main

platform-frontend: ## 启动 Vue 前端
	npm --prefix frontend run dev

three-d-runtime-install: ## 安装独立三维渲染运行时依赖
	npm --prefix $(THREE_D_RUNTIME_DIR) ci

three-d-runtime-dev: ## 单独启动三维渲染运行时
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_three_d_runtime.ps1 -RuntimePort $(THREE_D_RUNTIME_PORT)

three-d-runtime-preview: ## 预览独立三维渲染运行时生产静态产物
	npm --prefix $(THREE_D_RUNTIME_DIR) run preview -- --host 127.0.0.1 --port $(THREE_D_RUNTIME_PORT) --strictPort

three-d-runtime-typecheck: ## 检查独立三维渲染运行时类型
	npm --prefix $(THREE_D_RUNTIME_DIR) run typecheck

three-d-runtime-test: ## 运行独立三维渲染运行时组件测试
	npm --prefix $(THREE_D_RUNTIME_DIR) run test

three-d-runtime-check: three-d-runtime-typecheck three-d-runtime-test three-d-runtime-build ## 运行独立三维渲染运行时质量门

three-d-runtime-build: ## 构建独立三维渲染运行时静态产物
	npm --prefix $(THREE_D_RUNTIME_DIR) run build

platform-three-d-runtime: ## 启动严格平台并尝试启动独立三维渲染运行时
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_platform.ps1 -StrictCompetition -StartThreeDRuntime -ThreeDRuntimePort $(THREE_D_RUNTIME_PORT)

demo-compat: ## 启动 Gradio 兼容性入口
	$(PYTHON) app/main.py --config configs/inference/osteo_vision.yml

docs-audit: ## 审计活动文档、版本和本地链接
	$(PYTHON) tools/audit_active_documentation.py

readiness: ## 运行严格环境与模型就绪检查
	$(PYTHON) tools/check_project_readiness.py
	$(PYTHON) tools/check_runtime_readiness.py --config configs/inference/osteo_vision_competition_strict.yml --require-strict

clean: ## 清理缓存、临时测试目录和构建输出
	$(PYTHON) tools/clean_workspace.py --apply

clean-artifacts: ## 预览可清理的 E2E 和 UI 临时产物
	$(PYTHON) tools/clean_workspace.py --include-artifacts

clean-all: ## 清理缓存与可丢弃的 E2E/UI 临时产物
	$(PYTHON) tools/clean_workspace.py --apply --include-artifacts

version: ## 显示当前 Python 包版本
	@$(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

build: ## 构建 Python 包和 Vue 前端
	$(PYTHON) -m build
	npm --prefix frontend run build

release-build: build three-d-runtime-build ## 构建平台与独立三维运行时发布产物
