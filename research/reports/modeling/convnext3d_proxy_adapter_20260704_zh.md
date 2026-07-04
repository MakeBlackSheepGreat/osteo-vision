# ConvNeXt-style 3D 代理分割模型接入报告

日期：2026-07-04

## 结论

本轮把 ConvNeXt-style 3D 病灶分割候选从 D025 smoke 模型内部实现，提升为正式模型适配器 family：`convnext3d_segmenter`。它已进入 `configs/inference/osteo_vision.yml` 和 `configs/tasks/osteo_vision.yml`，可由模型清单识别，并能在主线 `MedicalImagingInferenceService` 中被优先选择。

该模型仍是 D025 CBCT lesion ROI 代理模型，不是术中 ICG 颌骨骨髓炎目标域模型。

## 代码与配置

- 适配器：`src/models/adapters.py`
- 模型结构与推理：`src/models/lesion_segmenter.py`
- 推理配置：`configs/inference/osteo_vision.yml`
- 任务推荐模型：`configs/tasks/osteo_vision.yml`
- 单元测试：`tests/unit/test_model_adapters.py`

## 当前能力

- 模型 ID：`convnext3d_d025_proxy_segmenter`
- 模型 family：`convnext3d_segmenter`
- 输入类型：`npz_roi`
- 输出：`npz_volume_mask`、阳性体素比例、概率统计、代理模型边界 warning
- checkpoint：`artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- model version：`osteo-vision-convnext3d-proxy-v0`

## 验证记录

已验证真实配置下模型清单显示 `convnext3d_d025_proxy_segmenter` 可用。

已使用 D025 本地 ROI 样本运行主线推理，结果：

```json
{
  "status": "completed",
  "model_version": "osteo-vision-convnext3d-proxy-v0",
  "model_id": "convnext3d_d025_proxy_segmenter",
  "model_family": "convnext3d_segmenter",
  "mask_format": "npz_volume_mask",
  "warning_codes": [
    "convnext3d_proxy_model_non_target_domain"
  ]
}
```

## 医学边界

该模型只证明“正式 adapter + checkpoint + 配置 + 推理 + 报告”的工程链路。它使用 CBCT ROI 代理数据，不能写成真实术中 MP4/JPEG 或 ICG 颌骨骨髓炎分割性能。

## 下一步

1. 扩大 D025/公开 CBCT 训练轮次，形成阈值分析和失败样本。
2. 将 JPEG/MP4 关键帧接入 2D 候选区模型或 promptable 分割模型。
3. 若继续走 ConvNeXt/MedNeXt 路线，需要补正式训练配置、checkpoint manifest 和模型卡版本冻结。
