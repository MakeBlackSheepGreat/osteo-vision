# ConvNeXt-style 3D Proxy Segmenter Adapter Report

Date: 2026-07-04

## Conclusion

This update promotes the ConvNeXt-style 3D lesion segmentation candidate from an internal D025 smoke-model implementation to a formal adapter family: `convnext3d_segmenter`. It is now registered in `configs/inference/osteo_vision.yml` and `configs/tasks/osteo_vision.yml`, appears in the model inventory, and can be selected by the main `MedicalImagingInferenceService`.

This remains a D025 CBCT lesion ROI proxy model. It is not target-domain intraoperative ICG jaw-osteomyelitis evidence.

## Files

- Adapter: `src/models/adapters.py`
- Model and inference helpers: `src/models/lesion_segmenter.py`
- Runtime config: `configs/inference/osteo_vision.yml`
- Task recommendation config: `configs/tasks/osteo_vision.yml`
- Unit test: `tests/unit/test_model_adapters.py`

## Current Capability

- Model ID: `convnext3d_d025_proxy_segmenter`
- Model family: `convnext3d_segmenter`
- Input type: `npz_roi`
- Output: `npz_volume_mask`, positive voxel fraction, probability statistics, and proxy-domain warning
- Checkpoint: `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- Model version: `osteo-vision-convnext3d-proxy-v0`

## Verification

The model inventory reports `convnext3d_d025_proxy_segmenter` as available under the real Osteo Vision config.

Mainline inference was also verified on a local D025 ROI sample:

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

## Medical Boundary

The adapter proves the engineering path across adapter, checkpoint, configuration, inference, and reporting. It uses CBCT ROI proxy data and must not be presented as real intraoperative MP4/JPEG or ICG jaw-osteomyelitis segmentation performance.

## Next Steps

1. Extend D025/public-CBCT training with threshold analysis and failure examples.
2. Connect JPEG/MP4 keyframes to a 2D candidate-region model or promptable segmentation model.
3. If the ConvNeXt/MedNeXt path remains the main route, add formal training configs, checkpoint manifests, and frozen model-card versions.
