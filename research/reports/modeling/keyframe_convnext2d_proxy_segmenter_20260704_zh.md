# 2D Keyframe ConvNeXt 分割代理模型报告

## 定位

本报告记录一个可训练的 2D ConvNeXt-U-Net 风格 keyframe 分割模型。它用于把官方 JPEG/MP4 keyframe 从启发式 hotspot baseline 推进到真实 PyTorch checkpoint 推理。当前训练数据为合成或伪标注代理数据，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_model_card.json`
- 数据来源：manifest
- 训练样本：163；验证样本：37。
- 训练 batch：80；batch size：4。
- 平均训练 loss：0.3012
- 设备：cuda；PyTorch：2.11.0+cu128。

## 指标

- Foreground Dice：0.8640
- Foreground IoU：0.7614
- Prediction positive fraction：0.2029

## 医学边界

2D keyframe segmentation proxy trained on synthetic or pseudo-labeled fluorescence-like frames; not real intraoperative ICG jaw osteomyelitis clinical performance.
