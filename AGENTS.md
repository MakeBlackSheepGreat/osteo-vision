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

完整赛题原文为本地忽略 PDF：`HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf`；赛题方设备技术文档为本地忽略 PDF：`research/literature/inventory/official/competition_official_technical_document_20260527.pdf`。讨论赛题目标、交付物、评审标准和方案优先级时，必须读取这些本地一手资料；完整赛题原文优先于此前阶段性报告、二手整理和内部 Demo 设想。

赛题要求提交一套面向颌骨骨髓炎术中辅助决策的完整技术解决方案。实现重点围绕荧光手术显微镜平台，形成“新型荧光造影剂设计 + 多模态医学图像融合与处理 + AI 辅助显微成像判读”的集成方案。

系统设计、报告撰写、功能裁剪和技术路线取舍必须优先贴合赛题官方技术文档；官方文档高于二手资料、通用医学影像经验和临时讨论结论。引用或改写赛题要求时应标明来自官方技术文档，并避免把未被官方文档支持的扩展能力包装成必做项。

官方设备输入边界：赛题方手术显微镜包含 4K 超高清影像摄录系统，分辨率 3840x2160；影像通过 USB3.0 存储，图片格式为 JPEG，视频格式为 MP4。系统必须优先支持 4K MP4 视频流/视频上传文件和 JPEG 图片上传，再向其他格式扩展。

完整赛题答题要求：

- 面向颌骨骨髓炎病灶精准示踪的新型荧光造影剂设计方案，重点说明显微荧光成像条件下的示踪机理、靶向或选择性依据、必要实验或验证数据支持，以及与显微荧光成像系统的适配性。
- 面向荧光手术显微镜术中应用需求的多模态医学图像融合与处理方法，包括白光通道与荧光通道等多源图像的获取、配准、融合，以及在显微成像系统中的实时显示或辅助导航应用。
- 基于人工智能的颌骨骨髓炎病灶识别与辅助判读方法，结合显微白光与荧光成像信息，说明算法总体思路、特征提取或模型构建方式，以及在荧光手术显微镜术中以叠加提示、风险标注或决策辅助形式呈现的应用模式。

DICOM 标准输出与远程协作可作为软件平台扩展亮点和证据包能力，但完整赛题原文未将其列为核心答题要求，不得再把 DICOM/远程协作表述为赛题固定赛点或替代造影剂设计要求。

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
- 每次用户对本项目提出新的要求、纠正、偏好或流程约束时，必须先把其中可长期遵守、会影响后续工作的内容写入或更新到本文件，再继续执行后续任务；一次性执行事项不得误写成长期规则。
- 回答保持结构化、审慎和可核验，避免过分夸赞；不确定时说明不确定性，必要时主动索要补充信息或证据。
- 避免固定 AI 腔句式，尤其避免先否定再转折的套话表达。
- 回答和文档中避免过分夸大效果，尤其避免临床性能承诺。
- 讨论赛题交付、验收、方案设计、模型闭环或比赛可行性时，必须先复核赛题原文和赛题官方技术文档，再说明工程自测、内部验收或 Demo 结果；不得用内部 smoke/acceptance 脚本替代赛题方要求。
- 对真实医疗数据、患者信息、医院样本和企业样本，默认按脱敏和最小保留原则处理。
- 若医院或企业无法提供真实术中 MP4 视频，不得因此停滞训练路线；当前可预期医院真实 CBCT 病例也只有约 4-5 例，真实项目病例和医生关键帧/ROI 标注目前也暂时不可获得，应把“真实目标域 MP4/JPEG 缺失”“真实 CBCT 样本极少”和“医生关键帧/ROI 标注暂缺”作为一级风险显式写入报告，并并行探索公开荧光手术视频数据集、公开骨髓炎/骨坏死视频资料和由真实 CBCT 派生的伪视频/帧序列代理数据。搜索骨髓炎视频资料时不局限于颌骨，可纳入糖尿病足、长骨、脊柱、骨感染清创、MRONJ/骨坏死等相近场景，但必须区分公开视频、教学视频、论文补充视频和可训练数据集。所有代理视频、公开异域视频和 CBCT 派生视频必须明确标注为非目标域数据，不得包装成真实术中 ICG 颌骨骨髓炎视频。
- 后续数据集寻找、自制数据和分割模型训练必须围绕完整赛题三项核心要求组织：新型荧光造影剂设计验证数据、多模态白光/荧光融合处理数据、AI 辅助显微成像判读数据；不得只围绕内部 Demo 或 DICOM/导出链路设计数据路线。
- 当前阶段不把新型造影剂实物合成或湿实验验证作为软件开发前置条件；造影剂章节可用 ICG 基线、四环素/自体荧光等文献证据和未来验证方案支撑。短期工程优先实现赛题软件闭环：输入官方边界内 MP4/JPEG，输出帧级分割结果、荧光伪彩/叠加结果、医生复核和证据报告。
- 短期开发评估中不得把真实项目病例和医生关键帧/ROI 标注作为当前闭环前置条件；列项目缺口时应将其归入外部数据依赖，并继续推进可由公开数据、代理数据和工程实现验证的其他缺口。
- 比赛版开发必须优先保持完整演示闭环可运行；模型训练、模型替换和新架构探索不得阻塞官方 4K JPEG/MP4 输入、荧光融合/伪彩、AI 辅助候选区、医生复核和证据包导出主流程。当前主线模型以已验证 checkpoint 和模型清单为准；未超过主线指标的训练候选只作为建模报告证据，不得直接接入比赛主线配置。
- 后续涉及“分割模型实现、训练、接入、优化”的任务时，必须优先产出可运行的模型结构、训练脚本、推理 adapter、配置入口、checkpoint/manifest 记录和最小测试；不得只停留在文献检索、报告、接口契约或数据规划。若真实目标域数据缺失，只能做代理或伪标注训练，也要明确边界后继续实现可运行的训练与推理闭环。
- 当用户明确要求推进分割模型或指出分割模型落实不足时，必须把当轮优先级切换到代码级实现、训练/推理跑通和可核验输出；除非存在不可绕过的环境或数据阻塞，不得用继续调研、泛化方案讨论或文档整理替代模型闭环实现。
- 面对分割模型数据集缺口时，必须把“真实目标域数据缺失”作为核心待解决工程问题处理，直接提出可执行的数据闭环方案，包括公开视频/荧光代理/CBCT 派生数据的分层使用、伪标注质量门控、人工复核小金标准集、医生复核反馈再训练和明确的不可声称边界；不得用“继续寻找公开数据集”替代数据闭环设计。
- 面向官方 4K JPEG/MP4 的 keyframe 分割推理不得默认假设整帧一次性推理一定可承载；应优先提供可配置的 patch/tiling 推理、帧级时序平滑元数据、医生 ROI/复核数据沉淀和回退策略，确保 4K 演示闭环稳定。
- 分割模型的复核回灌训练必须保留样本权重与复核状态：`accepted`/`modified` 样本可作为高权重训练数据，`rejected` 样本默认作为负例或错误分析数据，训练报告必须说明这些权重仍不等同于真实目标域临床标注。
- 本项目涉及外部资料、文献、数据集、网页链接、近期信息、竞品/开源项目或事实核验时，必须灵活主动使用 Tavily 相关 skills（如 `tavily-search`、`tavily-extract`、`tavily-research`），并优先保留可追溯来源链接。
- 下载外部视频、公开数据集或论文补充材料时，必须同步保存可追溯 manifest，至少记录原始页面链接、直接下载链接、本地路径、荧光/非荧光属性、医学场景、文件大小、校验状态和下载时间；大型视频文件只放 `research/datasets/**/raw/` 等 Git 忽略目录，不进入版本库。
- 本项目固定使用 Conda 环境 `osteo-vision`，路径为 `C:\Users\876762330\.conda\envs\osteo-vision`；执行项目自查、测试、训练、推理、Demo 或依赖检查前必须确认已进入该环境，或显式使用 `conda run -n osteo-vision ...`。
- 不得使用当前默认 `base` 环境作为本项目运行环境；`base` 当前为 Python 3.13，缺少项目所需的 PyTorch/Gradio 等关键依赖，容易导致误判。
- 大型数据、论文 PDF、checkpoint、DICOM/NIfTI 原始数据不进入 Git。
- 官方赛题原文、设备技术文档、企业资料和内部研究 PDF 不得进入 Git 或推送到 GitHub；只能作为本地忽略文件读取。仓库内可提交脱敏后的摘录、复核记录、路径说明和非敏感结论，但不得提交原始官方 PDF。
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
conda activate osteo-vision
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
