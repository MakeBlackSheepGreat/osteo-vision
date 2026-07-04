# D025 病灶 ROI 代理分割 Smoke 模型报告

## 定位

本报告记录一个小型 3D ConvNeXt-U-Net 风格分割模型在 D025 CBCT 病灶 ROI 64³ 缓存上的 smoke 训练。它用于验证训练、checkpoint、adapter 和主线 segmentation pipeline 能否闭环，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- Checkpoint SHA256：`3b6cd68118626d6204f091295c563b7175773959a583269af3cdfb2c94a08a34`
- 上一版主线备份：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_base12\d025_lesion_smoke_before_continue_20260704.pt`
- 训练病例：209；验证病例：53。
- 本轮续训 batch：1500；累计训练 batch：4500；batch size：2。
- 续训学习率：0.0002；平均训练 loss：0.0893。
- 设备：cuda；PyTorch：2.11.0+cu128。

## Smoke 指标

- Foreground Dice：0.6452
- Foreground IoU：0.5488
- Lesion sensitivity：0.7882
- Lesion precision：0.7981
- Prediction positive fraction：0.0041
- Target positive fraction：0.0041

## 阈值扫描评估

- 最优阈值：0.20。
- Mean Dice：0.6567，较上一版 0.6266 提升 0.0301。
- Mean IoU：0.5553，较上一版 0.5183 提升 0.0370。
- Mean HD95：15.2370，较上一版 17.6413 下降 2.4043。
- 评估报告：`research/reports/modeling/d025_continue_1500_eval_20260704/d025_proxy_model_evaluation_20260704_zh.md`

## 医学边界

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
