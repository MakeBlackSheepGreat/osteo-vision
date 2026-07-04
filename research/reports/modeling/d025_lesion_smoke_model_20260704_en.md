# D025 Lesion ROI Proxy Segmentation Smoke Model

## Scope

This report records a small 3D ConvNeXt-U-Net style smoke training run on the D025 64 cubed CBCT lesion ROI cache. It verifies the training, checkpoint, adapter, and segmentation pipeline loop; it is not intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- Train cases: 160; validation cases: 32.
- Training batches: 160; batch size: 2.
- Mean train loss: 0.6337.
- Device: cuda; PyTorch: 2.11.0+cu128.

## Smoke Metrics

- Foreground Dice: 0.1324
- Foreground IoU: 0.0739
- Lesion sensitivity: 0.8391
- Lesion precision: 0.0794
- Prediction positive fraction: 0.0519
- Target positive fraction: 0.0049

## Medical Boundary

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
