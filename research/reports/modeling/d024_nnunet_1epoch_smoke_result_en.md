# D024 DentVoxel nnU-Net 1-Epoch Smoke Test Report

Generated on: 2026-06-15

## 1. Objective

This run validated the full nnU-Net v2 workflow for the D024 DentVoxel jaw-roi task: data conversion, planning/preprocessing, training, validation prediction, metric aggregation, and visual inspection.

This is a smoke test with only 1 training epoch. The metrics should not be treated as formal model performance.

## 2. Data And Task

- Dataset: D024 DentVoxel CBCT
- nnU-Net dataset: `Dataset124_DentVoxelJawROI`
- Split: fold 0, 80 training cases and 20 validation cases
- Spacing: 0.3 mm isotropic
- Modality: CBCT, processed with CTNormalization in nnU-Net
- Labels:
  - 0 background
  - 1 maxilla
  - 2 mandible
  - 3 right mandibular canal
  - 4 left mandibular canal
  - 5 right maxillary sinus
  - 6 left maxillary sinus

## 3. Model And Configuration

- Trainer: `nnUNetTrainer_1epoch`
- Configuration: `3d_fullres`
- Network: PlainConvUNet
- Patch size: `[112, 160, 128]`
- Batch size: 2
- GPU: NVIDIA GeForce RTX 5060 Laptop GPU
- PyTorch: 2.11.0+cu128
- CUDA device: `cuda:0`

Training log:

`research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results/Dataset124_DentVoxelJawROI/nnUNetTrainer_1epoch__nnUNetPlans__3d_fullres/fold_0/training_log_2026_6_15_19_54_09.txt`

Validation summary:

`research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results/Dataset124_DentVoxelJawROI/nnUNetTrainer_1epoch__nnUNetPlans__3d_fullres/fold_0/validation/summary.json`

## 4. Runtime And Storage

- One training epoch: 145.54 s
- Training stage: about 2 min 26 s
- Validation prediction for 20 cases: about 36 min 37 s
- Total run time: about 39 min
- Validation output size:
  - `.nii.gz` predictions: 20 files, about 0.02 GB
  - `.pkl`: 20 files, about 0.06 GB
  - `.npz` softmax files: 20 files, about 30.49 GB

Note: this run used `--npz`, producing about 1.5 GB of softmax data per validation case. For ordinary smoke tests, omit `--npz`; keep probability maps only for ensemble, uncertainty, or weight-search experiments.

## 5. Metrics

Foreground mean:

- Dice: 0.1208
- IoU: 0.0763

| Label | Structure | Dice | IoU | Mean reference voxels | Mean predicted voxels |
|---:|---|---:|---:|---:|---:|
| 1 | maxilla | 0.2400 | 0.1366 | 3,060,543 | 1,064,004 |
| 2 | mandible | 0.4846 | 0.3211 | 2,173,222 | 4,368,167 |
| 3 | right mandibular canal | 0.0000 | 0.0000 | 13,399 | 0 |
| 4 | left mandibular canal | 0.0000 | 0.0000 | 12,929 | 0 |
| 5 | right maxillary sinus | 0.0000 | 0.0000 | 567,380 | 0 |
| 6 | left maxillary sinus | 0.0000 | 0.0000 | 577,956 | 0 |

Pseudo Dice from the training log:

- maxilla: 0.2461
- mandible: 0.5871
- right mandibular canal: 0.0000
- left mandibular canal: 0.0000
- right maxillary sinus: 0.0000
- left maxillary sinus: 0.0000

## 6. Visual Inspection

Three validation previews were generated:

- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0001.png`
- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0059.png`
- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0101.png`

Findings:

- Predicted labels contain only `[0, 1, 2]`.
- Ground-truth labels contain `[0, 1, 2, 3, 4, 5, 6]`.
- The model has started to respond to the larger maxilla and mandible regions.
- The mandibular canals and maxillary sinuses have no predicted output after one epoch.
- Boundaries are coarse and class confusion is visible, which is expected for a 1-epoch smoke test.

## 7. Environment And Tests

Environment check:

```text
python check_env.py
failures: []
warnings: []
```

Project tests:

```text
python -m pytest tests/unit tests/smoke
46 passed, 5 warnings
```

The warnings come from Pillow's deprecated `mode` parameter and should be addressed before Pillow 13.

## 8. Assessment

This run confirms that:

- The converted D024 jaw-roi nnU-Net dataset is valid.
- Planning and preprocessing complete successfully.
- The 8GB RTX 5060 Laptop GPU can run 3D fullres training.
- Fold 0 training, validation, and summary generation all completed normally.

Current limitations:

- One epoch is far too short for reliable segmentation.
- Small structures are not learned yet.
- Validation inference is much slower than the single training epoch.
- Saving `.npz` files created a large storage overhead.
- The current run used default mirroring; formal dental laterality experiments should use a no-mirroring strategy.

## 9. Next Steps

Recommended order:

1. Remove or archive the smoke-test `.npz` softmax files to recover about 30.49 GB.
2. Run a 5-epoch smoke test without `--npz` and check whether loss and large-structure Dice improve.
3. Switch to a no-mirroring trainer before the formal baseline.
4. Add dedicated recall, connected-component, and clDice reporting for mandibular canals and maxillary sinuses.
5. Start ResEnc, MedNeXt, and U-Mamba comparisons after the baseline stabilizes.

