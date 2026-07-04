# D025 病灶 ROI 代理分割 Smoke 模型报告

## 定位

本报告记录一个小型 3D ConvNeXt-U-Net 风格分割模型在 D025 CBCT 病灶 ROI 64³ 缓存上的 smoke 训练。它用于验证训练、checkpoint、adapter 和主线 segmentation pipeline 能否闭环，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- 训练病例：160；验证病例：32。
- 训练 batch：160；batch size：2。
- 平均训练 loss：0.6337。
- 设备：cuda；PyTorch：2.11.0+cu128。

## Smoke 指标

- Foreground Dice：0.1324
- Foreground IoU：0.0739
- Lesion sensitivity：0.8391
- Lesion precision：0.0794
- Prediction positive fraction：0.0519
- Target positive fraction：0.0049

## 医学边界

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
