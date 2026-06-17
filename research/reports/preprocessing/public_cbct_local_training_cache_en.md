# Public CBCT Local Training Cache Report

## Objective

This run fixes training- and inference-readable data under the local project `derived/` directories. Drive D is treated only as a static raw-data archive source and is not a runtime dependency.

## Method

- Target shape: `64x64x64`
- Image preprocessing: 0.5/99.5 percentile clipping, normalization to `[-1, 1]`, stored as `float16`
- Label preprocessing: nearest-neighbor resampling, stored as `int16`
- Cache format: compressed NPZ with `image`, `label`, `original_shape`, `target_shape`, `original_spacing`, and `label_values`
- Manifest contract: `input_path` and `mask_path` point to local project cache files

## Dataset Results

| Dataset | Cache task | Cases | Generated | Reused | Local manifest |
| --- | --- | ---: | ---: | ---: | --- |
| d024 | jaw_roi | 100 | 0 | 100 | `research\datasets\public-candidates\d024_dentvoxel\derived\local_preprocessed\jaw_roi_64_manifest.csv` |
| d025 | lesion_roi | 262 | 0 | 262 | `research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv` |
| d036 | anatomy_roi | 480 | 0 | 480 | `research\datasets\public-candidates\d036_toothfairy2\derived\local_preprocessed\anatomy_roi_64\d036_toothfairy2_anatomy_roi_64_manifest.csv` |

## Runtime Boundary

Training, inference, and smoke benchmarks should use the local manifests or the existing local D024 nnU-Net preprocessing directories. If drive D is unavailable, the local caches remain readable; the archive is needed only when regenerating caches or repeating raw-level preprocessing.

## Limitations

D025 and D036 caches are low-resolution engineering caches for smoke training, architecture screening, and inference-interface validation. Formal high-resolution training still needs task-specific nnU-Net/MONAI conversion and a separate experiment report.
