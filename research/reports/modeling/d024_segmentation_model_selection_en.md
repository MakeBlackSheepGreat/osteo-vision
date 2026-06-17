# D024 DentVoxel Segmentation Model Selection and Tuning Report

## Objective

The current training target is anatomical segmentation on the D024 DentVoxel dental CBCT dataset. The output will support preoperative jaw ROI extraction, mandibular canal protection zones, and downstream jaw osteomyelitis lesion-localization priors. D024 does not contain osteomyelitis, necrotic bone, or intraoperative ICG fluorescence labels, so this stage must not be treated as lesion segmentation.

## Data Tasks

The first task is `jaw-roi`: maxilla, mandible, bilateral mandibular canals, and bilateral maxillary sinuses are retained and remapped to sequential labels 0-6. This task is intended to close the conversion, training, inference, and evaluation loop on the local 8GB GPU.

The second task is `full-39`: DentVoxel labels 0-38 are preserved for full anatomical multi-structure segmentation across jaws, teeth, canals, and sinuses.

## Model Route

M0 uses nnU-Net v2 3D fullres automatic planning as the reliable baseline. The CBCT channel is written as `CT` in `dataset.json` so nnU-Net uses CT normalization, while reports still identify the source modality as CBCT.

M1 uses nnU-Net ResEnc small or medium configurations with left/right mirroring disabled by default. Tooth IDs and mandibular canals are laterality-sensitive, and the ToothFairy2 experience shows that disabling left/right mirroring is an important improvement.

M2 uses MedNeXt Small/Base, starting with a 3x3x3 kernel before testing 5x5x5. MedNeXt represents the 3D ConvNeXt route and tests whether large-kernel ConvNet designs improve CBCT structural continuity.

M3 uses U-Mamba bottleneck or encoder variants as the long-range dependency experiment. SegMamba and a custom Mamba+ConvNeXt hybrid remain M4 candidates after M0-M3 have stable metrics.

## Metrics and Ensemble

Core metrics are Dice, IoU, HD95, and NSD. Tubular structures such as the mandibular canals also report clDice to monitor breaks and topology continuity. The first training stage keeps Dice+CE as the baseline loss and does not add clDice/cbDice loss yet.

Ensembling proceeds in three steps: 5-fold softmax probability averaging with TTA, then equal-weight probability fusion across nnU-Net, MedNeXt, and U-Mamba, then validation-driven global or per-class weight search using an objective that balances mean Dice, HD95, and mandibular canal clDice.

## Implemented Artifacts

- Conversion script: `scripts/convert_d024_to_nnunet.py`
- Label grouping and task definitions: `src/datasets/d024.py`
- Segmentation metrics extension: `src/metrics/segmentation.py`
- Probability ensemble utilities: `src/models/ensembles.py`
- Report directory: `research/reports/modeling/`

## Recommended Commands

```powershell
conda activate osteo-vision
python scripts/convert_d024_to_nnunet.py --task jaw-roi
$env:nnUNet_raw='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_raw'
$env:nnUNet_preprocessed='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_preprocessed'
$env:nnUNet_results='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results'
nnUNetv2_plan_and_preprocess -d 124 -c 3d_fullres --verify_dataset_integrity
nnUNetv2_train 124 3d_fullres 0 -tr nnUNetTrainerNoMirroring
```

## Evidence

- The ToothFairy2 winning route uses nnU-Net ResEnc L and emphasizes no left/right mirroring, patch tuning, postprocessing, and ensembling.
- DentalSegmentator provides public nnU-Net v2 weights for dento-maxillo-facial CT/CBCT segmentation, demonstrating engineering maturity in dental CBCT.
- MedNeXt is a mature 3D ConvNeXt medical segmentation architecture and is the preferred ConvNeXt-style comparator.
- U-Mamba is the most practical medical Mamba implementation close to the nnU-Net ecosystem, so it has higher priority than adapting Mamba-3 from scratch.

## Next Step

Run conversion checks and a small-split smoke training for `jaw-roi`. If the 8GB GPU runs out of memory, reduce patch size or batch size while keeping the NoMirroring strategy. After the baseline stabilizes, proceed to MedNeXt, U-Mamba, and ensemble experiments.
