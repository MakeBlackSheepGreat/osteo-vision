# 颌骨骨髓炎项目最终目标与固定技术栈

生成日期：2026-06-15

## 1. 本地资料依据

本次判断主要读取了以下本地资料：

- `research/literature/inventory/competition_feasibility_report.md`
- `research/planning/engineering_preparation.md`
- `research/planning/data_acquisition_plan.md`
- `docs/architecture.md`
- `docs/task_adapter_guide.md`
- `configs/tasks/osteo_vision.yml`
- `configs/inference/osteo_vision.yml`
- `requirements.txt`
- `environment.yml`

核心结论来自赛题资料：本项目应围绕企业已有口腔数字观察仪的白光/荧光双通道能力，形成“造影剂 + 多模态图像融合 + AI 辅助判读 + 标准化输出”的完整系统。ICG 反映灌注和组织活性差异，不能包装成骨髓炎特异性探针。

## 2. 最终项目目标

最终目标是做成一个面向颌骨骨髓炎术中辅助决策的科研/竞赛原型系统。

系统要解决的问题：

- 在术中白光视野上稳定显示 ICG 荧光信息。
- 对疑似坏死骨、炎症区域、可疑边界或风险区做 AI 辅助提示。
- 把术前影像、术中图像、AI 输出和医生复核边界组织成可展示、可复现、可交付的病例结果。
- 支持比赛答辩中的完整链路演示，而不是只展示单个模型指标。

系统不做的承诺：

- 不承诺 ICG 能特异性识别颌骨骨髓炎。
- 不承诺输出为临床诊断。
- 不在缺少真实术中白光/ICG 样本和医生标注时承诺临床级分割性能。

## 3. 赛点对应交付

| 赛点 | 固定交付 | 成功标准 |
|---|---|---|
| 赛点一：荧光图像伪彩增强 | 白光/荧光配准、伪彩叠加、热图、强度曲线、截图或视频导出 | 无训练权重时也能演示，输入输出可复现 |
| 赛点二：AI 辅助诊断 | ROI、可疑区、边界风险区的分割/检测/分类/量化接口 | 模型可替换，有评估指标，有失败样本记录 |
| 赛点三：标准输出和协作 | 结构化病例报告、DICOM secondary capture 或导出雏形、远程协作接口预留 | 结果可归档、可复核、可分享 |

## 4. 固定技术栈

固定技术栈指短期不应轻易更换的工程底座。

| 层级 | 固定选择 | 原因 |
|---|---|---|
| Runtime | Python 3.11 + conda + pip | 当前环境已建立，适合医学影像和深度学习生态 |
| 深度学习 | PyTorch | 已是 nnU-Net/MONAI/多数医学模型的共同底座 |
| 医学影像 I/O | SimpleITK、nibabel、pydicom | 覆盖 DICOM、NIfTI 和常见医学体数据 |
| 图像处理 | OpenCV、Pillow、matplotlib | 覆盖配准、伪彩、可视化和报告图生成 |
| 数据分析 | numpy、pandas、scikit-learn | 清单、指标、统计和传统 ML 基线所需 |
| 配置 | YAML | 当前 task / inference 配置均使用 YAML |
| Demo | Gradio | 适合比赛原型、快速演示和本地部署 |
| 工程质量 | pytest、mypy、ruff、black、isort | 保持可测、可维护、可审查 |
| 编排 | pyproject.toml、Makefile、scripts/、tests/、artifacts/ | 与当前仓库结构一致 |

## 5. 可变项

以下内容刻意保持可变，不写死：

- 具体分割模型：可以是 nnU-Net、ResEnc、MedNeXt、U-Mamba、MedSAM-like 或后续自研模型。
- 具体分类/检测模型：取决于真实样本、标签粒度和任务定义。
- 具体数据集组合：公开数据、企业样本、医院样本、模拟荧光数据都应通过 manifest 进入。
- 训练策略：全监督、半监督、预训练、promptable segmentation、ensemble 等都按实验记录推进。
- 评估指标权重：Dice、IoU、HD95、NSD、clDice、敏感性、特异性、医生一致性等可按任务调整。

这些可变项必须通过配置、模型适配器、数据清单和实验报告进入工程，避免散落到共享层。

## 6. 工程架构原则

1. `configs/tasks/osteo_vision.yml` 定义任务契约。
2. `configs/inference/osteo_vision.yml` 定义运行时模型、输入和报告配置。
3. `src/engine/inference.py` 保持统一推理入口。
4. 模型通过 `src/models/adapters.py` 的适配器进入。
5. 分割、分类、检测、量化、多任务能力通过 `src/pipelines/` 组织。
6. 正式运行输出写入 `artifacts/runs/<run_id>/`。
7. 研究报告写入 `research/reports/<topic>/`。

## 7. 数据策略

当前公开数据没有直接覆盖“颌骨骨髓炎术中 ICG 荧光”这个完整任务。因此数据策略分三层：

1. 公开数据用于解剖结构、口腔/颌骨 ROI、病灶候选和荧光增强的预训练或演示。
2. 少量真实术中白光/ICG 样本用于证明系统形态与临床工作流匹配。
3. 医生标注用于定义坏死骨、病灶边界、保留区和风险区，并作为赛点二强化的前提。

最低真实样本目标仍是 10-30 例脱敏病例。若拿不到真实样本，赛点二应定位为辅助演示和可接入能力，核心竞争力放在完整系统和可解释工作流。

## 8. 阶段验收

### V1：可演示系统骨架

- Gradio 能输入白光/荧光图像或视频帧。
- 能输出配准叠加、伪彩热图、ROI 统计和报告。
- 不依赖真实训练权重也能跑通。

### V2：公开数据 AI baseline

- 至少一个公开数据集完成预处理、manifest、训练或推理、评估、报告。
- 模型通过适配器接入。
- 结果包含指标、失败样本和可视化。

### V3：真实样本闭环

- 接入脱敏术中白光/ICG 样本。
- 有医生标注或复核记录。
- 输出可用于答辩的病例级证据链。

### V4：比赛交付包

- 技术方案报告。
- 软件原型。
- 演示视频或病例包。
- 模型/数据/评估报告。
- 安全声明、许可说明和复核边界。

## 9. 当前建议

短期应先固定工程交付链路：白光/荧光融合、报告、Demo、manifest、Benchmark 和模型适配器。模型与数据集继续实验推进，避免过早锁死。这样即使后续真实样本、标注形式或模型路线发生变化，项目主干仍能稳定承接。

