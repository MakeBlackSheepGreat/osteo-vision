# DentalSegmentator Jaw ROI Preprocessing Contract

Date: 2026-07-04

## Conclusion

This update does not download or integrate the large DentalSegmentator checkpoint. It first freezes the reusable project contract: **CBCT/NPZ plus optional anatomy mask -> cropped jaw ROI NPZ plus manifest**.

The contract supports downstream model training and preoperative CBCT proxy segmentation. It crops jaw-related regions before D025 lesion proxy segmentation, nnU-Net/DynUNet, or other 3D baselines. It is not intraoperative ICG MP4/JPEG target-domain inference and is not DentalSegmentator checkpoint inference.

## Verified Sources

Tavily CLI was used to verify DentalSegmentator sources. Temporary evidence is saved under `.pytest_tmp/tavily_dentalsegmentator_search_20260704.json` and `.pytest_tmp/tavily_slicer_dentalsegmentator_search_20260704.json`; these files are not committed.

Traceable sources:

- DentalSegmentator nnU-Net v2.2 pretrained model on Zenodo: <https://zenodo.org/records/10829675>
- SlicerAutomatedDentalTools extension: <https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools>
- SlicerDentalSegmentator extension notes: <https://github.com/gaudot/SlicerDentalSegmentator>

The Zenodo record describes a dento-maxillo-facial CBCT/CT anatomy segmentation model with a roughly 229.7 MB file. The checkpoint is intentionally not downloaded in this step.

## Implemented Files

- New module: `src/preprocess/cbct_roi.py`
- New CLI: `tools/build_cbct_roi_preprocess.py`
- New tests: `tests/unit/test_cbct_roi_preprocess.py`

Core function:

```python
from src.preprocess.cbct_roi import build_cbct_anatomy_roi

result = build_cbct_anatomy_roi(
    "case.npz",
    "artifacts/preprocessing/cbct_roi/case",
    anatomy_mask_path="case_anatomy_mask.npy",
    foreground_labels=[1, 2],
    margin_voxels=(8, 8, 8),
)
```

Inputs:

- `input_npz`: 3D `image`, optional `label`.
- `anatomy_mask_path`: optional `.npy` or `.npz` anatomy mask; later produced by DentalSegmentator.
- `foreground_labels`: anatomy labels used for ROI foreground.
- `margin_voxels`: 3D bbox margin.
- `fallback_crop_shape`: deterministic center crop when no foreground exists.

Outputs:

- `*_cbct_anatomy_roi.npz`: cropped `image`, optional `label`, optional `anatomy_mask`, `source_shape`, and `roi_bbox_zyx`.
- `*_cbct_anatomy_roi_manifest.json`: bbox, normalized bbox, source path, ROI source, label values, warnings, data boundary, and medical boundary.

CLI reproduction:

```powershell
conda run -n osteo-vision python tools\build_cbct_roi_preprocess.py `
  --input case.npz `
  --output-dir artifacts\preprocessing\cbct_roi\case `
  --anatomy-mask case_anatomy_mask.npy `
  --foreground-labels 1,2 `
  --margin 8,8,8
```

## Fallback Rules

ROI source priority:

1. External `anatomy_mask_path`, matching future DentalSegmentator outputs.
2. Input NPZ `label`.
3. Finite non-zero image voxels.
4. Deterministic center crop when no foreground is available.

Each fallback is recorded in the manifest warnings to avoid overstating proxy ROI quality.

## Value for the Competition Pipeline

1. Provides a stable CBCT ROI crop before 3D proxy segmentation training.
2. Creates a clean replacement boundary for future DentalSegmentator checkpoint inference: produce an anatomy mask, then reuse this contract.
3. Supports nnU-Net/DynUNet high-resolution patch training manifests with source, bbox, labels, and non-target-domain notes.
4. Complements the official MP4/JPEG fluorescence workflow. CBCT ROI remains a preoperative anatomy prior and training proxy, not a replacement for intraoperative fluorescence input.

## Boundaries

- DentalSegmentator is a dental/maxillofacial CT/CBCT anatomy segmentation tool, not a jaw osteomyelitis lesion model.
- The current implementation does not run a DentalSegmentator checkpoint.
- D024/D025/D036, CBCT-derived ROIs, and public anatomy masks are proxy or non-target-domain data.
- Outputs are research/competition validation platform evidence and must not replace physician diagnosis.

## Verification

Passed:

```powershell
conda run -n osteo-vision python -m ruff check src\preprocess\cbct_roi.py tools\build_cbct_roi_preprocess.py tests\unit\test_cbct_roi_preprocess.py --output-format concise
conda run -n osteo-vision python -m pytest tests\unit\test_cbct_roi_preprocess.py -q
```

Tests cover:

- External anatomy mask crop and manifest.
- Input label fallback.
- Image non-zero fallback.
- Center crop fallback.
- Shape mismatch rejection.

## Next Steps

1. If the DentalSegmentator checkpoint is later downloaded, keep it in a Git-ignored checkpoint/raw directory and record source, size, hash, and download time.
2. Add a CLI for batch conversion of D024/D036/D025 or de-identified hospital CBCT into ROI manifests.
3. Feed ROI manifests into nnU-Net/DynUNet training manifests for a reproducible anatomy ROI -> lesion/risk segmentation chain.
4. In the frontend and reports, present CBCT ROI as preoperative auxiliary evidence, not as the official intraoperative MP4/JPEG fluorescence path.
