# D025 病灶 ROI 代理分割 Smoke 模型报告

## 定位

本报告记录一个小型 3D ConvNeXt-U-Net 风格分割模型在 D025 CBCT 病灶 ROI 64³ 缓存上的 smoke 训练。它用于验证训练、checkpoint、adapter 和主线 segmentation pipeline 能否闭环，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500_model_card.json`
- Runtime allowed：False
- 训练病例：209；验证病例：53。
- 训练 batch：1500；batch size：2。
- 续训来源：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`。
- 累计训练 batch：4500。
- 平均训练 loss：0.0893。
- 设备：cuda；PyTorch：2.11.0+cu128。

## Smoke 指标

- Foreground Dice：0.6452
- Foreground IoU：0.5488
- Lesion sensitivity：0.7882
- Lesion precision：0.7981
- Prediction positive fraction：0.0040
- Target positive fraction：0.0041

## 医学边界

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
