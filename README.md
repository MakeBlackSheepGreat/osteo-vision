# osteo-vision

颌骨骨髓炎智能化荧光诊疗正式开发工作区。

本项目以医学影像比赛框架模板为工程底座，面向 ICG 荧光成像、AI 辅助诊断、DICOM/报告输出三个竞赛赛点开展开发。根目录就是正式开发工程；既有文献、数据清单、报告和外部模型快照统一归档到 `research/`。

当前项目原则和固定边界见 `AGENTS.md` 与 `.specify/memory/constitution.md`。项目目标是做成一个面向颌骨骨髓炎术中辅助决策的纯软件平台，优先覆盖白光/ICG 融合、AI + 医生复核和结果导出三层。

## 当前可运行闭环

当前 V1 平台已经能跑通一个中规中矩的研究/比赛原型闭环：

1. 创建病例。
2. 上传或登记官方边界内的 JPEG 图片、MP4 视频，优先按 4K `3840x2160`、JPEG、MP4 处理。
3. 对白光/ICG 图片执行伪彩增强、背景扣除、轻量配准、融合、色标生成和 ROI 定量。
4. 对 MP4 抽取关键帧，并运行可解释的 2D fluorescence hotspot baseline。
5. 展示候选区域、荧光融合证据、时间线摘要、医生复核状态和导出证据。
6. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP evidence bundle。

医学边界保持不变：当前输出是科研和竞赛原型结果，不能作为临床诊断结论；ICG 信号主要反映灌注和组织活性差异，不是颌骨骨髓炎特异性探针。

## 当前模型状态

当前可运行模型/规则：

- `convnext3d_d025_proxy_segmenter`：D025 CBCT ROI 代理分割模型，用于工程闭环验证。
- `d025_lesion_smoke_segmenter`：同一 D025 代理 checkpoint 的 smoke/兼容入口。
- `fluorescence_hotspot_2d_segmenter`：MP4/JPEG keyframe 的阈值和连通域 hotspot baseline，不是训练型病灶模型。
- `fixture_default`：测试和兜底 fixture。

当前不可声称已完成的模型：

- `nnunet_v2_osteo_baseline`：缺 checkpoint 和 adapter inference。
- `medsam2_osteo_promptable`：缺 checkpoint、prompt contract 和 adapter inference。
- `biomedclip_osteo_screening`：缺 `open_clip`、checkpoint 和 adapter inference。

最新 D025 代理模型评估见 `research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`。该评估不是术中 ICG 颌骨骨髓炎目标域性能。

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

比赛演示一键验收：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_acceptance.py
```

该命令会生成 4K JPEG/MP4 代理输入，通过后端真实接口完成上传、双通道融合、MP4 关键帧分析、医生复核和 evidence bundle 导出。输出默认写入 `artifacts/platform_smoke/competition_acceptance_*`，不进入 Git。

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
conda run -n osteo-vision python tools\run_competition_flow_acceptance.py
conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml
conda run -n osteo-vision python tools\check_project_readiness.py
```

这些命令覆盖代码质量、前端构建、浏览器 E2E、JPEG/MP4 上传、4K 代理输入、关键帧分析、荧光融合、复核导出和 evidence bundle。`run_competition_flow_acceptance.py` 是当前比赛故事线的主验收入口。所有 MP4 smoke 都是合成代理视频，不代表真实术中 ICG 颌骨骨髓炎视频。

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
