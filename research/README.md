# 研究资料与证据索引

`research/` 保存可追溯的文献、数据来源、工程计划、模型证据、比赛材料和历史归档。运行代码入口位于根目录 `osteo_vision_core/`、`backend/`、`scripts/` 与 `tools/`。

## 目录

```text
research/
├── literature/inventory/   官方资料、论文清单、数据集清单与来源核验
├── datasets/               公开候选数据的 SOURCE、manifest、receipt 与本地忽略数据
├── reports/
│   ├── planning/           当前目标、验收门、赛题对齐和风险计划
│   ├── modeling/           模型、数据、阈值、性能和安全门报告
│   ├── preprocessing/      预处理与格式验证报告
│   ├── release/            版本冻结快照与当前 release 索引
│   ├── submission/         当前参赛材料和可再生成证据索引
│   ├── archive/            旧提交包、早期规划和显式归档材料
│   └── legacy/             项目早期外部交付物
├── model-snapshots/code/   外部代码快照，仅用于参考和适配评估
└── media/                  小型说明素材；患者影像禁止提交
```

`research/scripts/` 已停止使用。现行工具统一放在根目录 `scripts/` 和 `tools/`。

## 当前权威索引

### 赛题与目标

- 官方赛题对齐：`reports/planning/official_competition_problem_alignment_20260704_zh.md`（事实按当前代码和最新快照复核）
- 官方技术文档对齐：`reports/planning/official_technical_document_alignment_zh.md`
- 平台目标母稿：`reports/planning/osteo_vision_platform_target_zh.md`
- 三项持续目标：`reports/planning/three_priority_capabilities_target_20260717_zh.md`
- 三项目标验收：`reports/planning/three_priority_capabilities_acceptance_v1_zh.md`

### 模型与运行

- 当前 keyframe 选型：`reports/modeling/keyframe_model_selection_summary_20260715_zh.md`
- 4K 运行门：`reports/modeling/keyframe_residual_attention_4k_runtime_gate_20260715_zh.md`
- 实时 fast-output 门：`reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md`
- 患者条件模型证据：以 `reports/modeling/` 中 20260719 日期报告和对应 manifest 为准。
- 骨活性模型证据：以 `reports/modeling/` 中 D074 与 20260719 日期报告和对应 manifest 为准。

### 数据与导航

- 三项目标数据核验：`datasets/public-candidates/three_priority_manifest_verification_20260719_d095.json`
- 数据源 registry 与核验工具：`tools/verify_three_priority_dataset_manifests.py`
- 三维与导航证据：以 `reports/modeling/` 中 L1、L2、D036、D087 日期化报告为准。

### 发布与参赛

- 当前 release 入口：`reports/release/README.md`
- 当前参赛材料入口：`reports/submission/README.md`
- 2026-07-11 提交包：`reports/archive/submission_20260711/`

## 证据优先级

1. 官方赛题原文和官方设备技术文档。
2. 当前严格配置、checkpoint sidecar、可运行代码和自动测试。
3. 最新 release 快照与当前 submission 索引。
4. 日期化模型、数据和工程报告。
5. 早期规划、外部头脑风暴和 legacy 材料。

旧报告保留生成时模型、指标、测试数量与 Git 状态。引用时必须同时说明日期和数据域。

## 数据治理

- 原始患者数据、未脱敏资料、密钥、病例映射和医院私有数据禁止进入 Git。
- 原始公开影像、视频、批量数据和大体积派生数据保持 `.gitignore` 状态。
- 每个可用数据源需记录来源页、直接地址、许可、数据域、规模、模态、标签、临床变量、本地路径、大小、SHA256、下载时间和用途边界。
- 许可或治理不明确的资源保持候选状态。
- 软组织 ICG、公开异域视频、代理 CBCT 和伪标注不能作为颌骨骨髓炎目标域临床性能证据。

## 新报告规则

- 当前状态说明优先更新根目录或 `docs/` 活动文档。
- 实验和研究报告放入对应 topic 目录，并在文件名中保留日期。
- 发布快照保持冻结；后续状态写入新版本快照或 release 索引。
- 当前提交目录只保存准备提交的内容和生成配置。
- 被替换的提交包整体移动到 `reports/archive/submission_<date>/`。
