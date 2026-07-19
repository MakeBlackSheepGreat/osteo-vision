# 研究报告索引与状态规则

本目录同时保存当前母稿、日期化工程证据、版本快照、参赛材料和历史归档。引用报告时需核对日期、数据域、模型 ID、配置哈希和后继入口。

## 当前入口

| 类型 | 入口 | 用途 |
|---|---|---|
| 平台目标 | `planning/osteo_vision_platform_target_zh.md` | 完整软件目标与赛题映射 |
| 三项持续目标 | `planning/three_priority_capabilities_target_20260717_zh.md` | 患者条件、骨活性、L1/L2 固定目标 |
| 三项目标验收 | `planning/three_priority_capabilities_acceptance_v1_zh.md` | 数据契约、SOP、安全门和验收定义 |
| 官方设备边界 | `planning/official_technical_document_alignment_zh.md` | 4K、JPEG、MP4、USB3.0 与扩展接口边界 |
| 当前版本 | `release/README.md` | 在制版本与冻结快照索引 |
| 当前参赛材料 | `submission/README.md` | 技术方案、证据 manifest 与生成入口 |

根目录 `README_CN.md`、`docs/project_summary.md`、严格运行配置和可运行代码优先描述当前事实。

## 目录职责

- `planning/`：当前目标、验收、安全与赛题对齐母稿；被替换的阶段材料移入 `archive/`。
- `modeling/`：数据准备、训练、阈值、模型选择、校准、性能、安全门和失败样本证据。
- `preprocessing/`：格式、预处理、质量检查和数据转换证据。
- `release/`：冻结 Git tag 的版本快照与当前 release 索引。
- `submission/`：当前准备提交的材料、生成配置和可再生成证据索引。
- `archive/`：被替换的提交包、早期规划、可行性报告与显式归档材料。
- `legacy/`：早期外部交付物，只用于追溯。

## 状态优先级

1. 官方赛题原文和官方设备技术文档。
2. 当前严格配置、checkpoint sidecar、Git 提交与可运行代码。
3. 最新冻结 release 快照。
4. 当前 submission 索引和技术方案。
5. 最新日期化模型、数据和工程报告。
6. 旧规划、差距审计、外部头脑风暴与 legacy 材料。

日期化报告保留生成时指标、测试数量、路径和 Git 状态。旧报告中的主线模型、设备依赖和未完成项不会自动代表当前状态。

## 历史报告说明

下列类型默认按历史证据读取，当前目录已完成物理隔离：

- `archive/planning_superseded_20260719/` 中的 `project_gap_*`、阶段审计和早期目标报告。
- `archive/planning_superseded_20260719/` 中的 `v1_demo_closure_*` 与早期阶段编号报告。
- `modeling/` 下的早期 ConvNeXt、hotspot、D024/D025 单模型报告按日期和数据域读取，不能覆盖当前主线。
- 带固定日期的阈值扫描、失败样本、训练与内部验证报告。
- `archive/submission_20260711/` 完整提交包。
- `archive/early_planning_202606/` 早期下载状态、数据路径与框架准备材料。

历史证据保持原文。当前索引通过日期和后继入口隔离旧状态。

## 新报告规则

- 文件使用 UTF-8。
- 当前母稿避免写入瞬时工作区状态和易漂移测试数量。
- 实验报告记录输入 manifest、患者/来源分组、配置、checkpoint、阈值、指标、延迟、内存和安全边界。
- 真实患者、医院或企业样本遵循脱敏和最小保留；原始数据与密钥禁止进入 Git。
- 生成型 DOCX/PDF 通过明确提交要求进入交付包；默认源文件使用 Markdown、JSON、CSV 或 YAML。
- 新 release 以追加文件记录，已冻结快照不回写。
