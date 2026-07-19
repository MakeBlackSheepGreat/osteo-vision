# 项目结构总览

## 定位

`osteo-vision` 是颌骨骨髓炎智能化荧光诊疗项目的正式开发工程。根目录直接承载源码、配置、测试、脚本、前端、后端和 Demo；历史研究资料统一归档到 `research/`。

## 当前结构

```text
osteo-vision/
├── app/                    # legacy Gradio Demo
├── artifacts/              # 运行产物、报告、可视化、checkpoint 占位
├── backend/                # FastAPI 平台后端
├── configs/                # 路径、任务包、推理配置
│   ├── inference/
│   │   ├── osteo_vision.yml
│   │   └── demo.yml
│   └── tasks/
│       ├── osteo_vision.yml
│       └── *.example.yml
├── docs/                   # 架构、快速开始、任务适配、框架说明
├── frontend/               # Vue 3 + TypeScript 平台前端
├── packaging/              # 打包说明
├── research/               # 文献、数据集清单、报告、外部代码快照
├── scripts/                # 训练、评估、Benchmark、实验脚本
├── src/                    # 正式源码
├── tests/                  # unit、smoke、integration 测试
├── tools/                  # 项目级自检脚本
├── AGENTS.md
├── README.md
└── pyproject.toml
```

## 开发主入口

- 任务配置：`configs/tasks/osteo_vision.yml`
- 推理配置：`configs/inference/osteo_vision.yml`
- V1 后端：`python -m backend.src.main`，默认 `http://127.0.0.1:8001/health`
- V1 前端：`npm --prefix frontend run dev`，默认 `http://127.0.0.1:5174/`
- legacy Gradio Demo：`python app/main.py --config configs/inference/osteo_vision.yml`
- 自检：`python tools/check_project_readiness.py`

## 资料归档

- 文献与数据集清单：`research/literature/inventory/`
- 数据获取与工程路线：`research/planning/`
- 外部模型快照：`research/model-snapshots/code/`
- 历史脚本已完成归档清理；现行工具统一位于 `scripts/` 与 `tools/`。

## 注意

`configs/inference/demo.yml` 和 `configs/tasks/medical_competition_demo.yml` 保留为通用框架测试夹具；正式颌骨骨髓炎开发默认使用 `osteo_vision.yml`。
