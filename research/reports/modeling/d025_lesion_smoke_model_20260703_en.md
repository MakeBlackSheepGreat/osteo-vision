# D025 Lesion ROI Proxy Segmentation Smoke Model

## Scope

This report records a small 3D ConvNeXt-U-Net style smoke training run on the D025 64 cubed CBCT lesion ROI cache. It verifies the training, checkpoint, adapter, and segmentation pipeline loop; it is not intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- Train cases: 8; validation cases: 2.
- Training batches: 2; batch size: 1.
- Mean train loss: 0.7190.
- Device: cpu; PyTorch: 2.11.0+cu128.

## Smoke Metrics

- Foreground Dice: 0.0002
- Foreground IoU: 0.0001
- Lesion sensitivity: 0.0024
- Lesion precision: 0.0001
- Prediction positive fraction: 0.0699
- Target positive fraction: 0.0032

## Medical Boundary

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
