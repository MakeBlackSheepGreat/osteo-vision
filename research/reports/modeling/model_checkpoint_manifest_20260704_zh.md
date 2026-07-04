# 模型 Checkpoint Manifest

## 结论

- 配置：`C:\Users\876762330\Desktop\projects\osteo-vision\configs\inference\osteo_vision.yml`
- 模型版本：`osteo-vision-convnext3d-proxy-v0`
- 模型总数：7；当前可用：4。
- Fixture fallback：True；选择策略：`fixture_fallback`。

## 当前可用模型

- `convnext3d_d025_proxy_segmenter` / `convnext3d_segmenter`：checkpoint 存在=True；临床声明=False；原因：无。
- `fluorescence_hotspot_2d_segmenter` / `fluorescence_hotspot_segmenter`：checkpoint 存在=False；临床声明=False；原因：无。
- `d025_lesion_smoke_segmenter` / `d025_lesion_segmenter`：checkpoint 存在=True；临床声明=False；原因：无。
- `fixture_default` / `fixture`：checkpoint 存在=False；临床声明=False；原因：无。

## 不可用或待实现模型

- `nnunet_v2_osteo_baseline` / `nnunet_v2`：checkpoint 存在=False；临床声明=False；原因：adapter inference not implemented; missing checkpoint: artifacts/checkpoints/osteo_vision/nnunet_v2。
- `medsam2_osteo_promptable` / `medsam_like`：checkpoint 存在=False；临床声明=False；原因：adapter inference not implemented; missing checkpoint: artifacts/checkpoints/osteo_vision/medsam2.pt。
- `biomedclip_osteo_screening` / `vlm_encoder`：checkpoint 存在=False；临床声明=False；原因：adapter inference not implemented; missing dependency: open_clip; missing checkpoint: artifacts/checkpoints/osteo_vision/biomedclip.pt。

## 边界

当前可用模型仍以 CBCT ROI 代理和 2D 荧光热点启发式为主，不得写成真实术中 ICG 颌骨骨髓炎临床性能。该 manifest 只用于说明工程链路、checkpoint 来源、可用性和缺失项。
