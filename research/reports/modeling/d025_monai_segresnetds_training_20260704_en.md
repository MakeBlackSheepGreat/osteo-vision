# D025 MONAI SegResNetDS Proxy Segmentation Training

## Scope

This report records MONAI SegResNetDS training and validation on the D025 64 cubed CBCT lesion ROI cache. It is model-route comparison evidence, not target-domain intraoperative ICG jaw osteomyelitis performance.

## Model and Training

- Model: `d025_monai_segresnetds_proxy_segmenter` / `monai_segresnetds`.
- Parameters: 3,154,514.
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- Training cases: 209; validation cases: 53.
- Completed batches: 3000; epochs: 29; batch size: 2.
- Learning rate: 0.0006; positive class weight: 8.0; mean train loss: 0.1982.
- Device: `cuda`; GPU: `NVIDIA GeForce RTX 5060 Laptop GPU`; peak GPU MB: 578.0757.

## Best Threshold Summary

- Best threshold: 0.2000
- Mean Dice: 0.5741
- Mean IoU: 0.4766
- Mean HD95: 13.8795
- Mean NSD: 0.4101
- Lesion sensitivity: 0.5721
- Lesion precision: 0.7128

## Threshold Sweep

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2000 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 |
| 0.3000 | 0.5710 | 0.4743 | 13.9005 | 0.4104 | 0.5611 | 0.7190 |
| 0.4000 | 0.5672 | 0.4710 | 13.8881 | 0.4100 | 0.5504 | 0.7295 |
| 0.5000 | 0.5629 | 0.4674 | 12.1757 | 0.4224 | 0.5414 | 0.7779 |
| 0.6000 | 0.5604 | 0.4653 | 12.0888 | 0.4199 | 0.5333 | 0.7864 |
| 0.7000 | 0.5560 | 0.4611 | 11.6675 | 0.4243 | 0.5237 | 0.7886 |
| 0.8000 | 0.5504 | 0.4562 | 11.6745 | 0.4177 | 0.5124 | 0.7974 |

## Comparison With Current ConvNeXt-Style Proxy

- ConvNeXt-style baseline: Dice=0.6266, IoU=0.5183, threshold=0.2000.
- SegResNetDS run: Dice=0.5741, IoU=0.4766, threshold=0.2000.
- Delta: Dice -0.0525; IoU -0.0418. If it does not beat the current baseline, it should not replace the main checkpoint.

## Low-Scoring Cases

- Case `DC_30` (DC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_30_failure_preview.png`
- Case `DC_35` (DC): Dice=0.0000, IoU=0.0000, HD95=77.9190; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_35_failure_preview.png`
- Case `DC_9` (DC): Dice=0.0000, IoU=0.0000, HD95=37.2630; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_9_failure_preview.png`
- Case `KCOT_40` (KCOT): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\KCOT_40_failure_preview.png`
- Case `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=34.4430; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_11_failure_preview.png`
- Case `RC_25` (RC): Dice=0.0000, IoU=0.0000, HD95=40.6295; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_25_failure_preview.png`
- Case `RC_3` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_3_failure_preview.png`
- Case `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_52_failure_preview.png`

## Outputs

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_monai_segresnetds.pt`
- JSON: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_monai_segresnetds_training_20260704.json`
- CSV: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_monai_segresnetds_training_20260704_per_case.csv`
- Preview directory: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z`

## Medical Boundary

D025 CBCT lesion ROI proxy training only; not target-domain intraoperative ICG jaw osteomyelitis performance.
