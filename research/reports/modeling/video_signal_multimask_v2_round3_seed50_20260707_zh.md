# 第三轮视频信号多 mask 回灌训练记录

日期：2026-07-07

## 本轮目标

第三轮围绕骨面门控样本不足推进：使用 D046 公开视频/代理关键帧批量生成 prompt-assisted `bone_gate_mask` 种子样本，并补齐前端二值 mask 编辑、后端 edited mask 保存、multi-mask manifest 回灌和 v2 smoke 训练链路。

## 结果摘要

- 批量骨面门控种子生成：50 条 `exposed_bone` prompt-assisted seed。
- multi-mask manifest：350 条样本，其中 `fluorescence_hotspot=100`、`boundary_risk=100`、`uncertain=100`、`exposed_bone=50`。
- v2 训练过滤样本：150 条，其中 `fluorescence_hotspot=100`、`exposed_bone=50`。
- 本轮 v2 smoke 指标：Dice 0.0000，IoU 0.0000，预测阳性比例 0.0000，阈值 0.5。
- 有效训练候选门槛：尚未满足。当前 50 条骨面样本均为 `review_required`，`accepted/modified` 数量未达到 30 条。

## 工程结论

本轮证明了批量 seed、前端修改、后端保存、manifest 回灌和 v2 训练入口可以运行，但 `review_required` seed 不能当作真实骨面标注。下一步应让医生或项目成员在前端编辑器中接受/修改至少 30 条骨面 mask，再重新训练并做阈值扫描、空 mask 率和过分割率评估。

## 医学与数据边界

D046 是公开/代理视频数据，不是真实术中 ICG 颌骨骨髓炎目标域数据。`medsam2_osteo_promptable` 仍为 deterministic prompt fallback，不是真实 MedSAM2 checkpoint 推理。当前 v2 checkpoint 不替换 MP4/JPEG 主线配置。
