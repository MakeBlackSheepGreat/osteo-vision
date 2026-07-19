# 模型与性能证据

本目录保存训练、阈值、模型选择、运行门、性能和失败分析证据。日期化文件记录生成时事实，引用时需同时核对数据域、manifest、配置和 checkpoint。

## 当前主线

- `keyframe_model_selection_summary_20260715_zh.md`：关键帧候选比较与主线选择。
- `keyframe_residual_attention_4k_runtime_gate_20260715_zh.md`：4K tiled 运行门。
- `keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md`：视频流低延迟输出门。
- `patient_conditioning_4k_registered_runtime_20260719_zh.md`：患者条件结果的受限运行与安全回退。
- `bone_activity_multitask_d074_proxy_20260719.json`：骨活性代理模型清单和目标域关闭状态。

## 证据分区

- 关键帧与视频：`keyframe_*`、`video_*`、`ofdvdnet_*`。
- CBCT 与三维解剖：`d024_*`、`d025_*`、`d036_*`、`public_cbct_*`。
- 患者条件与骨活性：`patient_conditioning_*`、`bone_activity_*`。
- 配准、阈值、校准和模型晋级：按文件名中的 `registration`、`threshold`、`promotion`、`runtime_gate` 检索。

旧 ConvNeXt、hotspot、D024/D025 单模型报告和伪标注指标仍可用于历史对比，不能替代严格配置中的主线模型，也不能作为目标域临床性能证据。当前运行和提交事实优先读取根目录 README、严格配置、最新 release 快照及 `research/reports/submission/`。
