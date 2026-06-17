# D024 DentVoxel 10-Model Baseline Segmentation Benchmark

## Scope

This report screens 3D medical segmentation backbones on the D024 DentVoxel jaw-roi task. The results reflect low-resolution, short-budget engineering feasibility and early convergence only; they are not final model performance.

## Data and Setup

- Dataset: D024 DentVoxel jaw-roi, 100 cases.
- Split: fold 0, 80 training cases and 20 validation cases.
- Test input size: [64, 64, 64], downsampled from 0.3 mm CBCT volumes.
- Training batches per model: 80; validation cases: 20.
- Device: cuda; PyTorch: 2.11.0+cu128.

## Summary Results

| Rank | Model | Status | Mean Dice | Mean IoU | Params | Train Loss | Time(s) | Peak GPU MB |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | MONAI SegResNetDS | completed | 0.4244 | 0.3338 | 3,154,599 | 0.2285 | 3.3746 | 313.5791 |
| 2 | MONAI BasicUNet++ | completed | 0.3930 | 0.2947 | 1,747,228 | 1.2469 | 8.8461 | 843.6621 |
| 3 | MONAI SegResNet | completed | 0.3289 | 0.2534 | 719,463 | 1.4260 | 2.1014 | 156.4268 |
| 4 | MONAI SwinUNETR Tiny | completed | 0.3211 | 0.2441 | 14,928,634 | 0.6488 | 7.1951 | 789.3965 |
| 5 | MONAI HighResNet | completed | 0.3199 | 0.2266 | 809,358 | 1.5288 | 21.0827 | 1667.3638 |
| 6 | MONAI BasicUNet | completed | 0.3192 | 0.2436 | 1,438,887 | 1.1699 | 3.4903 | 304.5391 |
| 7 | MONAI 3D U-Net | completed | 0.3134 | 0.2375 | 2,454,533 | 0.5217 | 1.9931 | 115.5967 |
| 8 | MONAI DynUNet ResBlock | completed | 0.2523 | 0.2060 | 5,690,775 | 1.0542 | 4.0242 | 375.9507 |
| 9 | MONAI Attention U-Net | completed | 0.2465 | 0.1673 | 5,909,215 | 1.3742 | 4.0319 | 413.5620 |
| 10 | MONAI UNETR Tiny | completed | 0.2078 | 0.1523 | 10,728,311 | 0.9673 | 5.5514 | 516.5093 |

## Initial Interpretation

- nnU-Net should remain the formal engineering baseline; the MONAI models here screen architecture families and resource behavior.
- Low-resolution short-budget Dice mainly indicates whether a model starts learning large anatomical structures; it is not enough to judge final mandibular canal performance.
- The next formal stage should return to high-resolution nnU-Net/MedNeXt/U-Mamba training, 5-fold validation, and HD95/NSD/clDice reporting.

## Evidence Basis

- nnU-Net v2 / ResEnc: Dental CBCT and biomedical segmentation engineering baseline; retained for formal high-resolution experiments.. Source: https://github.com/MIC-DKFZ/nnUNet
- MedNeXt: 3D ConvNeXt-style segmentation baseline for a later high-resolution comparison.. Source: https://github.com/MIC-DKFZ/MedNeXt
- U-Mamba / SegMamba: Mamba-based medical segmentation candidates for later long-range dependency experiments.. Source: https://github.com/bowang-lab/U-Mamba
- MONAI 3D U-Net: Classic encoder-decoder baseline for volumetric medical segmentation.. Source: https://docs.monai.io/en/stable/networks.html#unet
- MONAI BasicUNet: Compact 3D U-Net implementation with modest parameter count.. Source: https://docs.monai.io/en/stable/networks.html#basicunet
- MONAI BasicUNet++: UNet++-style nested skip connections for multiscale feature reuse.. Source: https://docs.monai.io/en/stable/networks.html#basicunetplusplus
- MONAI Attention U-Net: Attention gates are relevant for suppressing irrelevant anatomy around jaw ROIs.. Source: https://docs.monai.io/en/stable/networks.html#attentionunet
- MONAI DynUNet ResBlock: nnU-Net-inspired configurable U-Net suitable for dataset-specific planning.. Source: https://docs.monai.io/en/stable/networks.html#dynunet
- MONAI SegResNet: Residual 3D CNN baseline with favorable memory footprint.. Source: https://docs.monai.io/en/stable/networks.html#segresnet
- MONAI SegResNetDS: Residual encoder-decoder with deep-supervision support.. Source: https://docs.monai.io/en/stable/networks.html#segresnetds
- MONAI HighResNet: High-resolution residual CNN with a conservative memory profile.. Source: https://docs.monai.io/en/stable/networks.html#highresnet
- MONAI UNETR Tiny: Transformer encoder baseline for global 3D context, reduced for 8 GB GPU testing.. Source: https://docs.monai.io/en/stable/networks.html#unetr
- MONAI SwinUNETR Tiny: Shifted-window transformer baseline for hierarchical 3D context.. Source: https://docs.monai.io/en/stable/networks.html#swinunetr

## Artifacts

- Result JSON: `artifacts\runs\d024_segmentation_model_benchmark\20260615T180721Z\d024_10_model_baseline_benchmark_summary.json`
- Result CSV: `artifacts\runs\d024_segmentation_model_benchmark\20260615T180721Z\d024_10_model_baseline_benchmark_results.csv`
- Chinese report: `research\reports\modeling\d024_10_model_baseline_benchmark_zh.md`
- This report: `research\reports\modeling\d024_10_model_baseline_benchmark_en.md`

## Medical Boundary

D024 is an anatomical CBCT segmentation dataset. It does not contain jaw osteomyelitis, necrotic bone, or ICG fluorescence labels. These outputs are only anatomical ROI and model-selection evidence, not clinical diagnostic claims.
