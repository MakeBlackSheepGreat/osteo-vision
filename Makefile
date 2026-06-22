# Medical Imaging Competition Framework - Makefile
# 常用命令快捷方式

.PHONY: help install install-dev test test-unit test-integration test-smoke lint format type-check clean docs platform platform-backend platform-frontend

# 默认目标
help: ## 显示帮助信息
	@echo "osteo-vision"
	@echo "============"
	@echo ""
	@echo "可用命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# 安装相关
install: ## 安装项目依赖
	pip install -r requirements.txt

install-dev: ## 安装开发依赖
	pip install -r requirements.txt
	pip install -e ".[dev]"

install-pre-commit: ## 安装 pre-commit 钩子
	pre-commit install

# 测试相关
test: ## 运行所有测试
	pytest

test-unit: ## 运行单元测试
	pytest tests/unit/ -v

test-integration: ## 运行集成测试
	pytest tests/integration/ -v

test-smoke: ## 运行冒烟测试
	pytest tests/smoke/ -v

test-coverage: ## 运行测试并生成覆盖率报告
	pytest --cov=src --cov-report=html --cov-report=term-missing

test-fast: ## 快速运行测试（跳过慢测试）
	pytest -m "not slow" -x -q

# 代码质量相关
lint: ## 运行代码检查
	flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503

format: ## 格式化代码
	black src/ tests/ --line-length=120
	isort src/ tests/ --profile black --line-length=120

format-check: ## 检查代码格式
	black --check src/ tests/ --line-length=120
	isort --check-only src/ tests/ --profile black --line-length=120

type-check: ## 运行类型检查
	mypy src/ --ignore-missing-imports

check-all: lint format-check type-check test-unit ## 运行所有检查

# 配置相关
validate-config: ## 验证配置文件
	python -c "from src.core.config_validator import validate_config_file; print(validate_config_file('configs/inference/osteo_vision.yml'))"

# 模型相关
model-inventory: ## 显示模型清单
	python scripts/model_inventory.py --config configs/inference/osteo_vision.yml

# 基准测试相关
benchmark: ## 运行基准测试
	python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs

# 实验相关
new-task: ## 创建新任务（用法：make new-task TASK_ID=my_competition）
	python scripts/new_task.py --task-id $(TASK_ID) --template classification --output-dir configs/tasks

new-experiment: ## 创建新实验（用法：make new-experiment EXP_ID=my_experiment）
	python scripts/new_experiment.py --experiment-id $(EXP_ID) --manifest tests/fixtures/benchmark_manifest_v2.csv

run-experiment: ## 运行实验（用法：make run-experiment SPEC=path/to/experiment.yml）
	python scripts/run_experiment.py --spec $(SPEC)

# Demo 相关
platform: ## 一键启动 V1 FastAPI 后端和 Vue 前端
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_platform.ps1

platform-backend: ## 启动 V1 FastAPI 后端（默认 http://127.0.0.1:8001）
	python -m backend.src.main

platform-frontend: ## 启动 V1 Vue 前端（默认 http://127.0.0.1:5174）
	npm --prefix frontend run dev

demo: ## 启动 Gradio Demo
	python app/main.py --config configs/inference/osteo_vision.yml

demo-share: ## 启动 Gradio Demo（公共链接）
	python app/main.py --config configs/inference/osteo_vision.yml --share

# 文档相关
docs: ## 生成文档
	@echo "文档生成暂未配置"

# 环境检查
check-env: ## 检查环境配置
	python check_env.py

check-all-python: ## 运行所有 Python 检查
	python check_all.py

# 清理相关
clean: ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

clean-artifacts: ## 清理生成的 artifacts
	rm -rf artifacts/runs/*
	rm -rf artifacts/reports/*
	rm -rf artifacts/visual_evidence/*
	rm -rf artifacts/experiments/*

clean-all: clean clean-artifacts ## 清理所有临时文件和 artifacts

# Git 相关
git-status: ## 显示 Git 状态
	git status

git-add-all: ## 添加所有更改
	git add -A

git-commit: ## 提交更改（用法：make git-commit MSG="commit message")
	git commit -m "$(MSG)"

# 版本相关
version: ## 显示当前版本
	@python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

# 打包相关
build: ## 构建包
	python -m build

upload-test: ## 上传到 TestPyPI
	twine upload --repository testpypi dist/*

upload: ## 上传到 PyPI
	twine upload dist/*
