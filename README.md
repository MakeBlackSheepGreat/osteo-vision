# osteo-vision

颌骨骨髓炎智能化荧光诊疗正式开发工作区。

本项目以医学影像比赛框架模板为工程底座，面向 ICG 荧光成像、AI 辅助诊断、DICOM/报告输出三个竞赛赛点开展开发。根目录就是正式开发工程；既有文献、数据清单、报告和外部模型快照统一归档到 `research/`。

当前项目原则和固定边界见 `AGENTS.md` 与 `.specify/memory/constitution.md`。项目目标是做成一个面向颌骨骨髓炎术中辅助决策的纯软件平台，优先覆盖白光/ICG 融合、AI + 医生复核和结果导出三层。

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
python check_env.py
python -m pytest tests/unit tests/smoke
```

legacy Gradio Demo：

```powershell
python app/main.py --config configs/inference/osteo_vision.yml
```

颌骨骨髓炎项目配置入口：

- `configs/tasks/osteo_vision.yml`
- `configs/inference/osteo_vision.yml`

## 资料入口

- 文献与数据集清单：`research/literature/inventory/`
- 工程准备路线：`research/planning/engineering_preparation.md`
- 数据获取计划：`research/planning/data_acquisition_plan.md`
- 外部模型快照：`research/model-snapshots/code/`

## 自检

```powershell
python tools/check_project_readiness.py
```

该脚本只做只读检查，用于确认资料归档、候选数据集目录、开发框架和本机工具是否就绪。
