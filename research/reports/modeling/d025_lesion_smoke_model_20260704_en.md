# D025 Lesion ROI Proxy Segmentation Smoke Model

## Scope

This report records a small 3D ConvNeXt-U-Net style smoke training run on the D025 64 cubed CBCT lesion ROI cache. It verifies the training, checkpoint, adapter, and segmentation pipeline loop; it is not intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke_model_card.json`
- Checkpoint SHA256: `3b6cd68118626d6204f091295c563b7175773959a583269af3cdfb2c94a08a34`
- Previous mainline backup: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_base12\d025_lesion_smoke_before_continue_20260704.pt`
- Train cases: 209; validation cases: 53.
- Continued-training batches: 1500; total training batches: 4500; batch size: 2.
- Continued-training learning rate: 0.0002; mean train loss: 0.0893.
- Device: cuda; PyTorch: 2.11.0+cu128.

## Smoke Metrics

- Foreground Dice: 0.6452
- Foreground IoU: 0.5488
- Lesion sensitivity: 0.7882
- Lesion precision: 0.7981
- Prediction positive fraction: 0.0041
- Target positive fraction: 0.0041

## Threshold-Sweep Evaluation

- Best threshold: 0.20.
- Mean Dice: 0.6567, up by 0.0301 from the previous 0.6266.
- Mean IoU: 0.5553, up by 0.0370 from the previous 0.5183.
- Mean HD95: 15.2370, down by 2.4043 from the previous 17.6413.
- Evaluation report: `research/reports/modeling/d025_continue_1500_eval_20260704/d025_proxy_model_evaluation_20260704_en.md`

## Medical Boundary

D025 CBCT lesion-mask proxy; not intraoperative ICG jaw osteomyelitis evidence.
