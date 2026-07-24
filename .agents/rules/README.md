# 医学影像比赛框架规则库 (.agents/rules/)

本目录是医学影像比赛框架的**技能规则库**，面向所有 AI 编程助手（Agent/LLM）和 Vibe Coding 场景。

每份规则文件描述一种可复用的开发技能，包含：背景知识、使用前置条件、标准实现模式、关键代码片段和注意事项。

规则文件**不会自动触发**，需要开发者/LLM 在合适的任务开始前主动阅读并运用。

---

## 规则文件列表

| 规则大类 | 具体技能文件 | 说明 / 触发时机 |
|---------|-------------|---------------|
| **数据处理** | [skill-data-preprocessing.md](skill-data-preprocessing.md) | **新建预处理流水线必读**：CT/MRI/X 光预处理、数据增强、归一化、重采样标准模式 |
| **模型集成** | [skill-model-adapter.md](skill-model-adapter.md) | **集成新模型必读**：模型适配器标准实现、推理/训练/评估接口、模型注册流程 |
| **流水线** | [skill-pipeline-creation.md](skill-pipeline-creation.md) | **新建处理流水线必读**：分类/检测/分割/量化/多任务流水线标准实现模式 |
| **评估指标** | [skill-evaluation-metrics.md](skill-evaluation-metrics.md) | **新建评估指标必读**：分类/检测/分割指标标准实现模式 |
| **配置管理** | [skill-configuration-management.md](skill-configuration-management.md) | **修改配置文件必读**：任务配置/模型配置/流水线配置 YAML 规范 |
| **比赛集成** | [skill-competition-integration.md](skill-competition-integration.md) | **接入新比赛必读**：新比赛接入、数据集适配、评估协议对接标准流程 |

---

## 使用指引

1. **新建预处理流水线前**：阅读 `skill-data-preprocessing.md`，确认预处理步骤和数据格式要求。
2. **集成新模型前**：阅读 `skill-model-adapter.md`，确认模型适配器接口和注册流程。
3. **新建处理流水线前**：阅读 `skill-pipeline-creation.md`，确认流水线基类和配置方式。
4. **新建评估指标前**：阅读 `skill-evaluation-metrics.md`，确认指标接口和计算方式。
5. **修改配置文件前**：阅读 `skill-configuration-management.md`，确认配置模式和验证规则。
6. **接入新比赛前**：阅读 `skill-competition-integration.md`，确认比赛接入流程和数据适配方式。

> 主规范文件为根目录 `AGENTS.md`，本规则库是对 `AGENTS.md` 的具体技能补充，两者互为参考，`AGENTS.md` 优先级更高。
