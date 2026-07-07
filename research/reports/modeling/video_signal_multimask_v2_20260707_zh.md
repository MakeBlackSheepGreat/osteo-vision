# 视频信号分割第二轮落地记录

日期：2026-07-07

## 目标

第二轮围绕 `video_signal_segmentation` 的骨面门控缺口推进：在不替换当前 MP4/JPEG 主线模型的前提下，新增基于医生 ROI 或候选框 prompt 的 `bone_gate_mask` 生成、复核记录、导出字段和训练回灌 manifest。

## 工程结果

- 后端新增候选区骨面门控生成接口：对指定 keyframe candidate 调用 `medsam2_osteo_promptable` 的 prompt fallback，输出二值 mask 与叠加图。
- 复核清单新增 `bone_gate_mask_path`、`bone_gate_overlay_path`、`label_source`、`prompt_source`、`sample_weight` 等字段。
- 新增 `tools/build_video_signal_multimask_training_manifest.py`，可合并 D046 荧光信号 mask 与 prompt-assisted review 骨面 mask。
- 新增 `scripts/train_video_signal_multimask_v2.py`，可按 `mask_type` 过滤训练 v2 checkpoint，默认不允许直接进入运行主线。
- 前端视频同步分析区支持对当前关键帧触发“生成骨面门控”，并展示骨面门控 mask/叠加结果。

## 医学与数据边界

当前 `medsam2_osteo_promptable` 仍是 deterministic prompt fallback，不是真实 MedSAM2 checkpoint 推理。D046、公开视频、prompt-assisted review 样本均不能表述为真实术中 ICG 颌骨骨髓炎临床标注；所有输出仍需医生复核，不能替代临床诊断。
