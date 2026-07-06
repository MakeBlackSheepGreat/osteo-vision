# 2D Keyframe ConvNeXt 分割代理模型报告

## 定位

本报告记录一个可训练的 2D ConvNeXt-U-Net 风格 keyframe 分割模型。它用于把官方 JPEG/MP4 keyframe 从启发式 hotspot baseline 推进到真实 PyTorch checkpoint 推理。当前训练数据为合成或伪标注代理数据，不代表真实术中 ICG 颌骨骨髓炎性能。

## 训练设置

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt`
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_manifest.json`
- Model card：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_model_card.json`
- 数据来源：manifest
- Manifest 数量：1；样本权重统计：`{"count": 200, "min": 1.0, "median": 1.0, "max": 1.0, "mean": 1.0}`
- 复核状态分布：`{"unspecified": 200}`
- 训练样本：163；验证样本：37。
- 伪标注质量门控：`{"min_positive_area_fraction": 0.0005, "max_positive_area_fraction": 0.6, "min_component_area": 32, "include_empty": false}`
- 人工复核种子集：50；路径：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\mp4_keyframe_segmentation_proxy_20260705\keyframe_segmentation_review_seed_manifest.csv`
- 训练 batch：160；batch size：4。
- 平均训练 loss：0.1683
- 设备：cuda；PyTorch：2.11.0+cu128。

## 指标

- Foreground Dice：0.9093
- Foreground IoU：0.8340
- Prediction positive fraction：0.1860

## 医学边界

2D keyframe segmentation proxy trained on synthetic or pseudo-labeled fluorescence-like frames; not real intraoperative ICG jaw osteomyelitis clinical performance.
ICG 主要反映灌注、血管通透性和组织活性差异，不是颌骨骨髓炎特异性探针；本模型输出只能作为候选区提示和医生复核辅助，不能作为自动诊断。

## 数据缺口与下一阶段

当前仍没有真实术中 ICG 颌骨骨髓炎 MP4/JPEG 像素级医生标注训练集。本轮用公开 MP4 代理数据和荧光强度伪 mask 训练可运行模型；下一阶段应把医生接受/修改后的 `review_manifest_json/csv` 样本提升为高权重训练数据，并保留 rejected 样本作为负例和错误分析。
本脚本已支持多个 manifest 合并训练和 `sample_weight` 加权 loss；这些权重只表示复核可信度或错误分析优先级，不等同于真实目标域临床标注。
