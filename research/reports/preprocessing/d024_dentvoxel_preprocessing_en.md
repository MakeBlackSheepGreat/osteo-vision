# D024 DentVoxel Dataset Preprocessing Report

## Source and License

- Dataset: DentVoxel (D024)
- Modality: CBCT, 3D NIfTI
- Source archive: `research\datasets\public-candidates\d024_dentvoxel\DentVoxel_Dataset.zip`
- License: CC BY
- Run timestamp (UTC): 2026-06-16T04:47:38.471646+00:00

## Directory Layout

- Raw dataset directory: `research\datasets\public-candidates\d024_dentvoxel\raw\DentVoxel_Dataset`
- Derived artifact directory: `research\datasets\public-candidates\d024_dentvoxel\derived`
- Central report directory: `research\reports\preprocessing`
- Manifest: `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_manifest.csv`
- Label inventory: `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_label_inventory.csv`
- Quality check table: `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_quality_check.csv`
- Summary JSON: `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_preprocessing_summary.json`

## Preprocessing Method

1. Extract `DentVoxel_Dataset/` from the ZIP archive into `raw/`, skipping `._*` and `__MACOSX` resource files.
2. Pair volumes by `imgXXXX.nii.gz` and `labelXXXX.nii.gz`.
3. Read shape, spacing, dtype, and label values with `nibabel`.
4. Generate a framework-compatible manifest with `segmentation` as the task type and `nifti_volume` as the input type.
5. Generate axial, coronal, and sagittal previews for the first 5 cases; red overlay indicates non-background labels.

## Full-Dataset Check Results

- Image count: 100
- Label count: 100
- Paired cases: 100
- Images missing labels: []
- Labels missing images: []
- Manifest rows: 100
- Read-error cases: 0
- Shape distribution: `{'440x440x344': 97, '440x440x343': 2, '442x344x438': 1}`
- Spacing distribution: `{'0.3x0.3x0.3': 100}`

## Label System

Labels are defined in `dataset_DentVoxel.json`. The dataset contains 39 classes, including background, maxilla, mandible, FDI tooth instances, bilateral mandibular canals, and bilateral maxillary sinuses. The full label table is written to `d024_dentvoxel_label_inventory.csv`.

## Project Use

- Pretraining for preoperative CBCT jaw and dental structure segmentation.
- Data preparation for nnU-Net or MONAI 3D segmentation baselines.
- Anatomical ROI priors for downstream jaw osteomyelitis lesion localization.

## Limitations and Next Steps

- D024 is an anatomical CBCT segmentation dataset, not an intraoperative ICG fluorescence dataset.
- Current labels do not include jaw osteomyelitis, necrotic bone, or inflammatory boundaries.
- The next step is to convert this dataset into nnU-Net format and start with maxilla, mandible, and mandibular canal segmentation baselines.
