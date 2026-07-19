# D093 MRONJ SPECT/CT Figure Release

Downloaded and reviewed: 2026-07-19

## Source

- Dataset: The added diagnostic value of SPECT/CT in detecting periapical and periodontal inflammation in medication-related osteonecrosis of the jaw patients
- Mendeley Data: <https://data.mendeley.com/datasets/7x7dxvg8cc/1>
- DOI: `10.17632/7x7dxvg8cc.1`
- License: CC BY 4.0, verified from the Mendeley public API snapshot

## Local Content

- `raw/Fig_1.jpg`: 1280x720 diagnostic ROC plot with two colored step curves and a diagonal reference line. It contains no anatomical image.
- `raw/Fig_2.tif`: 1280x720 MRONJ SPECT/CT composite with coronal, sagittal and transaxial CT, SPECT and hybrid views, colored jaw and lesion ROI contours, and an SUV quantification table.
- `metadata/`: pinned Mendeley snapshot and file inventory.
- `d093_mronj_spect_ct_figures_manifest.json`: source URLs, license, sizes, SHA256 values, image checks, visual-review findings and use boundaries.

## Admission Boundary

The record remains `target_domain_flag=false`, `training_eligible=false` and `review_required`. The release contains one ROC plot and one composite imaging figure. It has no raw DICOM, paired white-light/ICG frames, patient-level inventory or machine-readable pixel truth. Its permitted project use is target-condition-near visual review, figure-layout handling, ROI-table extraction checks and evidence-boundary validation.

Reproduce with:

```powershell
python tools/download_d093_mronj_spect_ct_figures.py
```
