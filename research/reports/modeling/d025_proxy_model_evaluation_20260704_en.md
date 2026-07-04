# D025 CBCT Proxy Segmentation Model Evaluation

## Scope

This report evaluates the currently runnable D025 CBCT lesion ROI proxy checkpoint. It is auditable model-loop evidence, not target-domain intraoperative ICG jaw osteomyelitis performance.

## Inputs and Model

- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Checkpoint SHA256: `56473aae9980da7ecfe2e720b8522a9ad5a6a825f00a314818fef07b9b15920d`
- Evaluation split: `val`; cases: 53.
- Device: `cuda`; PyTorch: `2.11.0+cu128`.

## Best Threshold Summary

- Best threshold: 0.2000
- Mean Dice: 0.6266
- Mean IoU: 0.5183
- Mean HD95: 17.6413
- Mean NSD: 0.4227
- Lesion sensitivity: 0.6756
- Lesion precision: 0.6932

## Threshold Sweep

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2000 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 |
| 0.3000 | 0.6224 | 0.5164 | 16.7775 | 0.4354 | 0.6613 | 0.6998 |
| 0.4000 | 0.6219 | 0.5179 | 14.5247 | 0.4432 | 0.6508 | 0.7135 |
| 0.5000 | 0.6180 | 0.5157 | 14.1909 | 0.4451 | 0.6397 | 0.7240 |
| 0.6000 | 0.6134 | 0.5135 | 15.4929 | 0.4436 | 0.6292 | 0.7279 |
| 0.7000 | 0.6103 | 0.5121 | 14.9053 | 0.4442 | 0.6193 | 0.7385 |
| 0.8000 | 0.6050 | 0.5083 | 15.5881 | 0.4430 | 0.6066 | 0.7477 |

## Low-Scoring Cases

- Case `DC_9` (DC): Dice=0.0000, IoU=0.0000, HD95=39.2162; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_9_failure_preview.png`
- Case `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_11_failure_preview.png`
- Case `RC_3` (RC): Dice=0.0000, IoU=0.0000, HD95=43.0093; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_3_failure_preview.png`
- Case `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_52_failure_preview.png`
- Case `KCOT_68` (KCOT): Dice=0.0055, IoU=0.0027, HD95=55.8689; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\KCOT_68_failure_preview.png`
- Case `DC_35` (DC): Dice=0.0220, IoU=0.0111, HD95=10.5080; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_35_failure_preview.png`
- Case `RC_25` (RC): Dice=0.0600, IoU=0.0309, HD95=61.1381; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_25_failure_preview.png`
- Case `DC_26` (DC): Dice=0.0756, IoU=0.0393, HD95=81.4045; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_26_failure_preview.png`

## Outputs

- JSON: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704.json`
- CSV: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704_per_case.csv`
- Preview directory: `C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z`

## Medical Boundary

D025 CBCT lesion ROI proxy evaluation only; not target-domain intraoperative ICG jaw osteomyelitis performance.
