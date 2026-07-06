# MedSAM-like Prompt 分割接口落地说明

日期：2026-07-04

## 结论

本轮把 `MedSAMLikeAdapter` 从空实现推进到可运行的 2D prompt 分割契约。当前实现是 **prompt contract fallback**：接收医生 ROI、候选 bbox 或 point prompt，生成可复核的二值 mask 和 overlay，用于医生复核、ROI 回写和后续真实 MedSAM/SAM2 checkpoint 接入前的工程闭环。

它不是 MedSAM2 权重推理，也不代表真实术中 ICG 颌骨骨髓炎分割性能。模型清单会明确给出 `medsam_checkpoint_missing_prompt_fallback` warning。

## 代码与配置

- Prompt fallback 实现：`src/models/prompt_segmenter.py`
- Adapter 接入：`src/models/adapters.py`
- 主配置：`configs/inference/osteo_vision.yml`
- 单元测试：`tests/unit/test_model_adapters.py`

配置项：

```yaml
model_id: medsam2_osteo_promptable
family: medsam_like
extra:
  prompt_fallback_enabled: true
  point_radius_px: 12
  output_dir: artifacts/visual_evidence/osteo_vision/prompt_masks
```

## 输入契约

当前最小支持 `2d_image`，prompt 从 `AdapterRequest.metadata` 读取：

- `roi_hints`：归一化矩形 ROI，沿用医生 ROI 工具输出。
- `prompts[].bbox_xyxy`：像素坐标矩形框。
- `prompts[].bbox_normalized`：归一化矩形框。
- `prompts[].geometry`：归一化矩形 geometry。
- `prompts[].point`：点 prompt，支持 normalized 或 pixel 坐标。

## 输出契约

输出保持与其他分割 adapter 一致：

- `segmentation_mask.format = png_binary_mask`
- `segmentation_mask.path`
- `lesion_evidence.overlay_path`
- `lesion_evidence.candidates`
- `quantification.positive_area_px`
- `quantification.positive_area_fraction`
- warning：`medsam_like_prompt_fallback_non_diagnostic`

## 对比赛闭环的帮助

1. 让“医生 ROI/bbox -> promptable segmentation -> mask/overlay -> 医生复核”这条链路有可运行接口。
2. 为后续真实 MedSAM/SAM2 checkpoint 替换预留稳定输出契约。
3. 与当前 MP4 hotspot 候选区和 ROI 画布兼容，可把关键帧候选框作为 prompt 使用。

## 边界

- 缺真实 MedSAM2 checkpoint。
- 当前只支持 2D prompt fallback，不支持视频传播、3D CBCT prompt 或 mask refinement。
- mask 由 prompt 几何生成，不是模型学习到的病灶边界。
- 所有输出只能作为研发验证版平台和医生复核辅助。

## 验证

- `conda run -n osteo-vision python -m pytest tests/unit/test_model_adapters.py -q`
- `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml`
