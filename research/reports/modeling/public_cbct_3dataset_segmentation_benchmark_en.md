# Public CBCT Three-Dataset Dice Improvement Diagnosis

## Scope

This report records the engineering fixes and quick validation runs for the low-Dice issue. Results still use local 64³ NPZ caches and are intended to validate the training loop, loss functions, and sampling strategy. They are not formal high-resolution model performance.

Medical boundary: D024 and D036 are anatomical CBCT segmentation datasets; D025 is a CBCT lesion-mask proxy task. None of them is intraoperative ICG fluorescence data, so these results must not be presented as clinical jaw-osteomyelitis diagnostic performance.

## Fixed Issues

- The training loop now runs across epochs until `max_train_batches` is reached and records `epochs_seen` and `samples_seen`.
- Added `--loss auto|ce|dice_ce|dice_focal|tversky_focal`; `auto` uses `dice_ce` for anatomy tasks and `dice_focal` for D025 lesion.
- Added `--class-weighting none|inverse|sqrt_inverse`, defaulting to `sqrt_inverse` to reduce rare-label collapse.
- Added `--foreground-oversample-ratio`, implemented as foreground-fraction weighted case sampling for the current 64³ full-volume caches.
- Added `--overfit-cases`, `--target-labels`, and diagnostic fields for dataset foreground fraction, target foreground fraction, and prediction foreground fraction.

## Key Results

### Sanity Overfit

Run ID: `20260617T132107Z`

Setup: `SegResNetDS`, one overfit case per dataset, 30 batches, `loss=auto`, `class_weighting=sqrt_inverse`.

| Dataset | Loss | Dice | Target fg | Pred fg | Interpretation |
|---|---|---:|---:|---:|---|
| D024 | dice_ce | 0.3644 | 0.0866 | 0.0643 | Trainable; labels and channels are not fundamentally broken |
| D036 | dice_ce | 0.1014 | 0.0862 | 0.0244 | Trainable, but sparse labels remain difficult |
| D025 | dice_focal | 0.6127 | 0.0121 | 0.0273 | No longer all-background; the loss direction is effective |

The D025 CE overfit control is run `20260617T132235Z`, with Dice 0.5441. The model can learn; `dice_focal` is stronger in this sanity condition.

### D025 Lesion Short Validation

Run ID: `20260617T132359Z`

Setup: 80 batches, 20 validation cases, `loss=auto`, `class_weighting=sqrt_inverse`, `foreground_oversample_ratio=0.75`.

| Model | Dice | IoU | Sensitivity | Precision | Target fg | Pred fg | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| `uxnet_large_kernel_proxy` | 0.1450 | 0.0833 | 0.9042 | 0.0801 | 0.0056 | 0.0626 | Best current D025 direction |
| `monai_segresnetds` | 0.1192 | 0.0711 | 0.2653 | 0.1677 | 0.0056 | 0.0088 | More conservative, higher precision |
| `monai_segresnet` | 0.0186 | 0.0094 | 1.0000 | 0.0094 | 0.0056 | 0.5896 | Severe over-segmentation |

D025 improved from 0 or about 0.02 Dice to 0.145. The real improvement direction is lesion-specific loss, foreground-weighted sampling, and UXNet/SegResNetDS candidates, not adding more uncalibrated models.

### Anatomy Short Validation

Run ID: `20260617T132518Z`

Setup: 160 batches, 20 validation cases, `loss=auto`, `class_weighting=sqrt_inverse`.

| Dataset | Model | Dice | IoU | Target fg | Pred fg | Interpretation |
|---|---|---:|---:|---:|---:|---|
| D024 | `monai_swinunetr_tiny` | 0.6395 | 0.5403 | 0.0934 | 0.1068 | Best current D024 result |
| D024 | `monai_segresnetds` | 0.6073 | 0.4893 | 0.0934 | 0.1075 | More resource-stable |
| D036 | `monai_segresnetds` | 0.1642 | 0.1068 | 0.0846 | 0.1071 | Best current D036 result |
| D036 | `monai_swinunetr_tiny` | 0.0812 | 0.0563 | 0.0846 | 0.1002 | Behind SegResNetDS |

D024 improved from about 0.36 to 0.61-0.64. D036 SegResNetDS reached 0.1642 in 160 batches, above the older 384-batch CE result of 0.1313. The anatomy improvement direction is Dice+CE with sqrt-inverse class weights, led by SegResNetDS/SwinUNETR Tiny.

## Smoke and Regression

- Run ID: `20260617T132823Z`
- Three datasets × six selected models forward/backward smoke: 18/18 completed.
- New unit tests cover cross-epoch training, stable loss values, foreground sampling weights, and the new result schema.

## Next Steps

1. Continue D025 with `uxnet_large_kernel_proxy` and `monai_segresnetds`; add threshold sweep, connected-component filtering, and Dice/Tversky/Focal ablations.
2. Continue D024/D036 with `monai_segresnetds` and `monai_swinunetr_tiny`; compare 64³, 96³, and 128³ small-sample settings next.
3. Report per-label Dice for D024 mandibular canal and D036 sparse labels so mean Dice does not hide small-structure behavior.
4. Keep nnU-Net v2 on the external nnU-Net path as the formal high-resolution baseline.

## Artifacts

- Sanity overfit JSON: `artifacts/runs/public_cbct_segmentation_benchmark/20260617T132107Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- D025 short-validation JSON: `artifacts/runs/public_cbct_segmentation_benchmark/20260617T132359Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- Anatomy short-validation JSON: `artifacts/runs/public_cbct_segmentation_benchmark/20260617T132518Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- Six-model smoke JSON: `artifacts/runs/public_cbct_segmentation_benchmark/20260617T132823Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- Chinese report: `research/reports/modeling/public_cbct_3dataset_segmentation_benchmark_zh.md`
