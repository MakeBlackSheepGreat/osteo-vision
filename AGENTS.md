# AGENTS.md

## Project Overview

本仓库是 **颌骨骨髓炎智能化荧光诊疗** 正式开发工程，面向竞赛和科研原型开发。

核心方向：

- ICG 荧光图像与白光图像融合、伪彩增强和 ROI 定量。
- 颌骨骨髓炎/坏死骨区域的 AI 辅助分割、检测、分类和不确定性提示。
- 研究原型报告、DICOM/结构化输出和远程协作接口。

所有输出均为科研和竞赛原型结果，不能作为临床诊断结论，必须保留医生复核边界。

## Project Target

当前项目的最终目标是一个面向颌骨骨髓炎术中辅助决策的纯软件平台。

平台只聚焦双通道数据进入软件后的后三层：

- 荧光分析层：白光/ICG 图像、帧序列或视频片段的配准、伪彩、融合、归一化、质控和定量。
- AI 与医生交互判读层：候选区域、边界风险、不确定性提示、ROI 标注和医生复核状态。
- 结果输出层：关键截图、结构化 JSON、量化 CSV、Markdown/PDF 报告、病例证据包和后续 DICOM 扩展。

比赛版可优先使用离线图片、同步帧序列、短视频和公开数据完成演示闭环；正式版再逐步接入真实脱敏样本和更完整的协作形态。

目标母稿见 `research/reports/planning/osteo_vision_platform_target_zh.md`，后续若需删减比赛版内容，优先从该文档裁剪。

## Competition Requirements

赛题要求提交一套面向颌骨骨髓炎术中辅助决策的完整技术方案。实现重点围绕企业已有口腔数字观察仪的可见光 + 荧光双通道能力，形成“造影剂 + 多模态图像融合 + AI 辅助判读”的集成方案。

固定赛点：

- 赛点一：荧光图像伪彩色增强，围绕白光/ICG 荧光融合、可视化和定量展示。
- 赛点二：基于目标检测或分割模型的智能辅助诊断，自动标注病灶疑似区域、边界风险区或需要医生复核的区域。
- 赛点三：DICOM 标准输出与远程协作功能，至少提供结构化结果、病例证据导出或后续 DICOM/会诊扩展的雏形。

医学边界：

- ICG 主要反映血流灌注、血管通透性和组织活性差异，不是颌骨骨髓炎特异性探针。
- 输出应定位为术中参考信号、风险提示和医生复核辅助，不得表述为自动确诊或替代医生判断。
- 若缺少真实术中白光/ICG 样本和医生标注，赛点二只能作为原型验证或辅助演示，不能承诺临床级诊断性能。

## Fixed Technical Stack

- Runtime: Python 3.11, conda, pip。
- Frontend: TypeScript + Vue。
- Backend/API: Python, 后续以 FastAPI 承载接口。
- Core ML backend: PyTorch。
- Medical imaging I/O: SimpleITK, nibabel, pydicom。
- 2D processing and visualization: OpenCV, Pillow, matplotlib。
- Data and analysis: numpy, pandas, scikit-learn。
- Configuration: YAML。
- Temporary demo/prototyping only: Gradio。
- Quality gates: pytest, mypy, ruff, black, isort。
- Project orchestration: pyproject.toml, Makefile, scripts/, tests/, artifacts/。

模型家族和数据集保持可变。它们只能通过任务配置、适配器、清单和实验记录进入工程，不在本文件里写死具体候选。

## Working Rules

- 必须使用 UTF-8 编码读取、写入和修改文本文件。
- 除非用户明确要求其他语言，回复以中文为主；每次回复开头称呼用户为 Sir。
- 回答保持结构化、审慎和可核验，避免过分夸赞；不确定时说明不确定性，必要时主动索要补充信息或证据。
- 避免固定 AI 腔句式，尤其避免先否定再转折的套话表达。
- 回答和文档中避免过分夸大效果，尤其避免临床性能承诺。
- 对真实医疗数据、患者信息、医院样本和企业样本，默认按脱敏和最小保留原则处理。
- 大型数据、论文 PDF、checkpoint、DICOM/NIfTI 原始数据不进入 Git。
- `D:\projects\osteo-vision` 只作为静态原始数据归档位置；训练、推理和 Demo 运行不得依赖 D 盘 junction 或 D 盘在线状态。
- 训练和推理优先使用项目本地 `research/datasets/**/derived/` 下的预处理数据、缓存 manifest 或任务级转换结果。
- `.pytest_tmp/`、`.pytest_cache/`、`artifacts/` 运行输出、nnU-Net 概率图和验证中间结果均按本地临时产物处理；长期证据只保留报告和必要预览图。
- 报告统一存放在 `research/reports/` 下，按主题使用子目录；预处理报告放 `research/reports/preprocessing/`，建模和实验报告放 `research/reports/modeling/`。
- 正式研究报告默认分别撰写中文和英文 Markdown 版本，文件名使用 `_zh.md` 和 `_en.md` 后缀。
- 修改共享框架能力时，优先保持可配置、可复用、可测试。
- 接入颌骨骨髓炎专用逻辑时，优先从 `configs/tasks/osteo_vision.yml`、`configs/inference/osteo_vision.yml` 和独立适配器进入，避免把疾病专用假设散落到共享层。

## Current Structure

```text
osteo-vision/
├── app/                    # Gradio Demo 入口
├── artifacts/              # 运行产物、报告、可视化、checkpoint 占位
├── configs/
│   ├── inference/          # 推理配置，主入口 osteo_vision.yml
│   └── tasks/              # 任务包配置，主入口 osteo_vision.yml
├── docs/                   # 架构、快速开始、任务适配和框架说明
├── packaging/              # 打包说明
├── research/               # 文献、数据集清单、报告、外部代码快照归档
├── scripts/                # 训练、评估、Benchmark、模型清单脚本
├── src/                    # 正式源码
├── tests/                  # unit、smoke、integration 测试
└── tools/                  # 项目级只读自检工具
```

## Key Files

- `configs/tasks/osteo_vision.yml`：颌骨骨髓炎任务包。
- `configs/inference/osteo_vision.yml`：颌骨骨髓炎推理运行配置。
- `src/engine/inference.py`：统一推理服务入口。
- `src/pipelines/`：分类、分割、检测、量化和多任务流水线。
- `src/models/adapters.py`：模型适配器边界。
- `research/literature/inventory/`：论文、数据集清单和可行性报告。
- `research/model-snapshots/code/`：nnU-Net、EGNet、FRS Loss 外部代码快照。

## Development Commands

```powershell
python check_env.py
python -m pytest tests/unit tests/smoke
python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
python app/main.py --config configs/inference/osteo_vision.yml
python tools/check_project_readiness.py
```

## Architecture Notes

- 配置文件统一使用 YAML，放在 `configs/`。
- 数据清单通过 `src/datasets/` 读取，数据分割通过 `src/datasets/splits.py` 做患者级泄漏检查。
- 输入验证通过 `src/preprocess/input_validation.py`，医学影像 I/O 通过 `src/io/`。
- 流水线应继承 `src/pipelines/base.py` 的 `Pipeline`。
- 模型集成应实现 `src/models/adapters.py` 中的适配器接口，并通过注册表进入。
- 报告输出应保留研究原型免责声明。

## Research Archive

`research/` 只保存启动前资料和迁移参考：

- `research/literature/inventory/`：文献、数据集、可行性报告。
- `research/planning/`：工程准备、数据获取计划、历史下载状态。
- `research/reports/`：统一报告目录，按 planning、preprocessing、modeling 等主题归档中英双语 Markdown 报告和相关可视化资产。
- `research/reports/planning/osteo_vision_platform_target_zh.md`：当前项目目标母稿。
- `research/model-snapshots/code/`：外部模型代码快照。
- `research/scripts/legacy/`：旧报告生成和下载脚本。

外部模型快照不直接作为主线源码修改；需要接入时迁移到 `src/models/`、`src/pipelines/` 或配置层。

## Rule Library

根目录 `.rules/` 是开发技能规则库。命中以下任务时，先阅读对应文件：

- 数据预处理：`.rules/skill-data-preprocessing.md`
- 模型适配：`.rules/skill-model-adapter.md`
- 流水线创建：`.rules/skill-pipeline-creation.md`
- 指标实现：`.rules/skill-evaluation-metrics.md`
- 配置管理：`.rules/skill-configuration-management.md`
- 比赛接入：`.rules/skill-competition-integration.md`

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read
`specs/001-software-platform-target/plan.md`
<!-- SPECKIT END -->
