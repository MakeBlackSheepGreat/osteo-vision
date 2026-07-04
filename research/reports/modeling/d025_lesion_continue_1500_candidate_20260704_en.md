# D025 Lesion ROI Proxy Segmentation Smoke Model

## Scope

This report records a small 3D ConvNeXt-U-Net style smoke training run on the D025 64 cubed CBCT lesion ROI cache. It verifies the training, checkpoint, adapter, and segmentation pipeline loop; it is not intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500_model_card.json`
- Runtime allowed: False
- Train cases: 209; validation cases: 53.
- Training batches: 1500; batch size: 2.
- Resume source: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`.
- Total training batches: 4500.
- Mean train loss: 0.0893.
- Device: cuda; PyTorch: 2.11.0+cu128.

## Smoke Metrics

- Foreground Dice: 0.6452
- Foreground IoU: 0.5488
- Lesion sensitivity: 0.7882
- Lesion precision: 0.7981
- Prediction positive fraction: 0.0040
- Target positive fraction: 0.0041

## Medical Boundary

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
