# D025 病灶 ROI 代理分割 Smoke 模型报告

## 定位

本报告记录一个小型 3D ConvNeXt-U-Net 风格分割模型在 D025 CBCT 病灶 ROI 64³ 缓存上的 smoke 训练。它用于验证训练、checkpoint、adapter 和主线 segmentation pipeline 能否闭环，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- 训练病例：8；验证病例：2。
- 训练 batch：2；batch size：1。
- 平均训练 loss：0.7190。
- 设备：cpu；PyTorch：2.11.0+cu128。

## Smoke 指标

- Foreground Dice：0.0002
- Foreground IoU：0.0001
- Lesion sensitivity：0.0024
- Lesion precision：0.0001
- Prediction positive fraction：0.0699
- Target positive fraction：0.0032

## 医学边界

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
