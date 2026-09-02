# Osteo-Vision Foundation Segmentation Model Design Report

Date: 2026-06-17

## Executive Summary

The low Dice scores in the current three-dataset benchmark are primarily caused by the experimental setup: all volumes are compressed into `64x64x64` full-volume caches for smoke testing. This destroys fine structures such as mandibular canals, dental roots, small bone defects, and lesion boundaries. It also omits the core components of robust 3D medical segmentation systems: patch-based high-resolution training, foreground oversampling, deep supervision, sliding-window inference, and postprocessing.

The foundation design should have two layers:

- Reliable baseline: nnU-Net v2 3D fullres / ResEnc as the formal high-resolution baseline.
- Project-controlled model: a lightweight 3D Residual ConvNeXt / UXNet-style model trained under the same high-resolution patch-based system.

The existing `64x64x64` benchmark should remain as a smoke, loss/sampling, and candidate-screening tool. It should not be used as formal performance evidence.

## Why The Current Dice Is Abnormally Low

### 1. Excessive Resolution Reduction

Current local caches are all `64x64x64`:

| Dataset | Task | Cases | Cache Shape | Example Foreground Fraction |
|---|---:|---:|---|---:|
| D024 DentVoxel | jaw ROI | 100 | `64x64x64` | about 8.7%-9.6% |
| D025 lesion CBCT | lesion ROI | 262 | `64x64x64` | about 0.28%-1.35% |
| D036 ToothFairy2 | anatomy ROI | 480 | `64x64x64` | about 4.2%-8.6% |

Dental CBCT contains very fine structures. Strongly downsampling each case to a 64-cube volume directly damages small canals, alveolar bone boundaries, root apex regions, and focal bone changes. Low Dice, low clDice, and broken boundaries are expected under this setup.

### 2. The Benchmark Is Not A Formal Training System

The current `scripts/benchmark_public_cbct_segmentation_models.py` has fixed the training-loop, loss, and sampling diagnostics, but it remains limited:

- Input data comes from full-volume 64-cube NPZ caches.
- Training budget is tens to hundreds of batches for quick diagnosis.
- Many frontier candidates are proxy or tiny implementations.
- The system does not yet include nnU-Net-style patch planning, deep supervision, multi-scale supervision, sliding-window fusion, and postprocessing.

Therefore, the current benchmark is useful for checking whether a model can learn and whether a loss/sampling direction is viable. It should not be compared directly with ToothFairy2, DentalSegmentator, or MedNeXt paper-level results.

## Evidence

### ToothFairy2 / Scaling nnU-Net for CBCT Segmentation

References:

- https://arxiv.org/html/2411.17213v2
- Local snapshot: `research/model-snapshots/code/nnunet/documentation/competitions/Toothfairy2/readme.md` (third-party documentation)

Key choices:

- nnU-Net ResEnc L.
- Patch size increased to `160x320x320`.
- Left/right mirroring disabled to preserve dental laterality.
- 1500 training epochs.
- CTNormalization.
- Deeper residual encoder.
- Two-model ensemble.
- Class-wise volume cutoff postprocessing.

The reported ToothFairy2 test result is mean Dice `0.9253` and HD95 `18.472`. The important point is that the performance comes from a complete high-resolution nnU-Net training and inference system, not from an isolated architecture swap.

### nnU-Net v2 Training Defaults

The local nnU-Net snapshot confirms:

- `oversample_foreground_percent = 0.33`
- `num_iterations_per_epoch = 250`
- `num_epochs = 1000`
- loss uses `DC_and_CE_loss`
- deep supervision uses `DeepSupervisionWrapper`
- inference uses sliding-window logit fusion with Gaussian weighting

These mechanisms are central for 3D medical segmentation under large-volume, small-foreground, and limited-VRAM constraints.

### DentalSegmentator

References:

- https://zenodo.org/records/10829675
- https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools

Key choices:

- Built on nnU-Net v2.2.
- Trained on 470 multi-institution dento-maxillo-facial CT/CBCT scans.
- Provides key dental anatomy labels, including upper skull/maxilla, mandible, upper teeth, lower teeth, and mandibular canal.
- Provides public pretrained weights and a 3D Slicer extension.

The practical implication for this project is to first stabilize a five-class anatomical prior before training every 39/42 class label and the lesion task together.

### MedNeXt

References:

- https://github.com/MIC-DKFZ/MedNeXt
- https://arxiv.org/html/2303.09975v5

Key choices:

- Fully ConvNeXt 3D encoder-decoder.
- Residual inverted bottlenecks.
- Kernel sizes commonly include 3, 5, and 7.
- Deep supervision support.
- Training follows the nnU-Net schedule: 1000 epochs, 250 batches per epoch, `128x128x128` patches, batch size 2, and sliding-window inference.

The implication is that ConvNeXt-style designs should be model replacements inside a full nnU-Net-like training system, rather than standalone 64-cube full-volume experiments.

### U-Mamba / SegMamba / 3D UX-Net

References:

- https://u-mamba.github.io
- https://github.com/MASILab/3DUX-Net

Key choices:

- U-Mamba places Mamba blocks in the bottleneck or encoder to combine CNN local features and long-range dependencies.
- 3D UX-Net uses large-kernel depthwise convolution to mimic hierarchical transformer receptive fields.
- These models should still be evaluated inside a full 3D segmentation training system.

The implication is that Mamba and large-kernel modules are useful second-stage enhancements. The first priority is to fix resolution, patch sampling, loss, inference, and evaluation.

## Foundation Model Design

### B0: Reliable Formal Baseline

Name: `OsteoVision-nnUNet-ResEnc`

Purpose:

- Segment D024/D036 anatomical structures such as jaw bones, teeth, mandibular canal, and maxillary sinus.
- Provide preoperative anatomical ROI and risk-region priors for intraoperative fluorescence analysis.

Training setup:

- Framework: nnU-Net v2.
- Configuration: 3D fullres; start with ResEnc S/M, then test ResEnc L if VRAM allows.
- Input: high-resolution local derived data inside the project; no dependency on the D drive being online.
- Normalization: CTNormalization for CBCT-like volumes.
- Augmentation: disable left/right mirroring, or keep only axes that preserve laterality.
- Loss: Dice + CE.
- Sampler: foreground oversampling, starting at 0.33.
- Inference: sliding-window + Gaussian weighting + TTA.
- Postprocessing: validation-optimized class-wise connected components, volume cutoffs, and anatomical sanity rules.

8GB GPU fallback:

- Start with ResEnc S/M.
- Patch sizes from `96x128x128` or `96x160x160`.
- Batch size 1.
- AMP enabled.
- Use gradient accumulation and checkpointing when needed.

### B1: Five-Class Anatomical Prior

Name: `OsteoVision-DentalPrior-5`

Suggested labels:

| ID | Class |
|---:|---|
| 0 | background |
| 1 | maxilla / upper skull |
| 2 | mandible |
| 3 | upper teeth |
| 4 | lower teeth |
| 5 | mandibular canal |

Purpose:

- Provide a stable anatomical prior for the platform demonstration system.
- Produce interpretable large-structure ROIs first.
- Reduce class sparsity before moving to D024 full-39 or D036 full-42 labels.

Evaluation:

- mean Dice.
- per-class Dice.
- HD95 / NSD.
- mandibular canal reported separately with clDice, HD95, and breakage rate.

### B2: Project-Controlled Candidate Model

Name: `OsteoSeg-ResUX-Lite`

Role:

- A controllable project model inspired by MedNeXt and 3D UX-Net.
- Trained under the same patch-based system as B0.

Architecture draft:

```text
Input CBCT patch
  -> Conv stem 3x3x3
  -> Residual encoder stage 1, channels 24/32
  -> Downsample
  -> Residual ConvNeXt / large-kernel stage 2
  -> Downsample
  -> Residual ConvNeXt / large-kernel stage 3
  -> Downsample
  -> Bottleneck: large-kernel depthwise block, optional Mamba block later
  -> Decoder with skip connections
  -> Deep supervision heads at 1/2, 1/4, 1/8 scale
  -> Final segmentation logits
```

Constraints:

- 3D patch input, initially `96x128x128`.
- Large-kernel depthwise convolution starts with kernel 5 or 7.
- Residual inverted bottleneck expansion ratio 2 or 4.
- InstanceNorm3d or GroupNorm for small-batch stability.
- Deep supervision enabled by default.
- Output class count is driven by task configuration.

The first version should avoid complex Mamba integration. Add `B2-MambaBot` only after B0 and the plain B2 model are stable.

### B3: Lesion / Necrotic-Bone Proxy Head

Name: `OsteoVision-LesionCascade`

Purpose:

- D025 lesion-mask proxy task.
- Later migration to suspicious necrotic bone or low-perfusion auxiliary prompts if real intraoperative labels become available.

Recommended flow:

1. Use B0/B1 to obtain mandible/maxilla ROIs.
2. Crop high-resolution patches inside the ROI.
3. Train a binary lesion head.
4. Use Dice+Focal or Tversky+Focal loss.
5. Use positive patch oversampling, starting at 0.5-0.75.
6. Apply threshold sweep and connected-component filtering after inference.

Metric focus:

- Prioritize sensitivity and stable non-zero Dice.
- Improve precision through thresholding, connected components, and ROI restriction.
- Do not present D025 scores as clinical diagnostic performance for jaw osteomyelitis.

## Data And Training Plan

### Anatomy Track

Data:

- D024: DentVoxel; start with jaw ROI / five-class prior, then full-39.
- D036: ToothFairy2; start with merged classes, then full-42.

Training:

- Generate high-resolution patches from local NIfTI or nnU-Net derived data.
- Preserve original spacing metadata.
- Use foreground-centered patch sampling.
- Report per-class Dice, clDice, and HD95 for small structures.

### Lesion Track

Data:

- D025: lesion-mask proxy data only.

Training:

- Use ROI cropping to avoid whole-volume background domination.
- Use mixed positive/negative patch sampling.
- Use Dice+Focal or Tversky+Focal loss.
- Report Dice, IoU, sensitivity, precision, case-level detection, and volume FP/FN.

## Acceptance Criteria

### Stage 1: Training-System Correctness

- Overfit 1-2 cases for D024/D036/D025, with Dice clearly increasing.
- Patch loader outputs high-resolution patches with spacing, case_id, and label set.
- B0/B2/B3 complete at least one forward/backward pass.
- Sliding-window inference reconstructs full-size predictions.

### Stage 2: Small High-Resolution Validation

- D024 jaw/five-class task: first target Dice > 0.75.
- D036 merged-class task: first target Dice > 0.55-0.70, then move to full-42.
- D025 lesion task: stable non-zero Dice and sensitivity, avoiding all-background or extreme over-segmentation.

### Stage 3: Formal Validation

- Five-fold cross validation.
- Save softmax probabilities for ensemble and uncertainty analysis.
- Report Dice, IoU, HD95, NSD, and clDice.
- Group reports by jaw, teeth, canal, sinus, and lesion.

## Recommended Implementation Order

1. Add a high-resolution patch dataset and loader; keep the 64-cube benchmark for smoke only.
2. Run D024/D036 five-class anatomical prior training.
3. Use nnU-Net v2 ResEnc as the formal B0 baseline.
4. Implement `OsteoSeg-ResUX-Lite` and compare it under the same data/training system.
5. Implement the D025 ROI-crop lesion cascade.
6. Add U-Mamba bottleneck, MedNeXt, and ensemble weight search after stable baselines.

## Medical Boundary

This design supports a research validation platform. D024/D036 are anatomical segmentation datasets, and D025 is a CBCT lesion-mask proxy dataset. They are not intraoperative ICG fluorescence labels or clinical jaw osteomyelitis outcome data. Model outputs should be framed as intraoperative reference signals, risk prompts, and physician-review assistance.
