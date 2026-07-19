# D069 MMDental patient-context starter

This directory contains a bounded, traceable extraction from the public MMDental dataset.

## Materialized data

- Source: <https://doi.org/10.6084/m9.figshare.28505276.v1>
- License: CC BY 4.0, verified from the Figshare API and DataCite metadata.
- Remote archive: `MMDental.zip`, 68,087,010,723 bytes, Figshare MD5 `99c0059775735ddb612b635547f41e3f`.
- Extraction: HTTP Range requests read the ZIP64 directory and the compressed bytes for `MMDental/medical_records.csv`; the complete archive was not downloaded.
- Local clinical table: 1,585,061 bytes, SHA256 `6c2eca1529b4d225f7f32c05fb112b3b1fac4735f5d1bc4da235ee6e84f804a0`.
- Structure: 2,124 visit records, 660 unique de-identified patient identifiers, 12 columns, ages 5 to 86, and 2,123 non-missing age values.
- Aggregate quality audit: 390 patients have multiple visit records, 2 patients have conflicting recorded ages, 0 patients have conflicting recorded sex, and per-column missing/non-missing counts are retained in `medical_records_structural_summary.json`.
- Bounded paired CBCT: case `492`, 145,668,104 bytes, SHA256 `2d4d2bf54ccd1cd2a34c0e790ac8b1e2ff9ce82d01dc39d1debf7e460f946bcf`.
- CBCT header check: NIfTI-1, `640 x 640 x 400`, signed 16-bit voxels, `0.25 x 0.25 x 0.25` spacing, with a matching clinical-record key and present age, sex, diagnosis, and history fields.
- Three-dimensional engineering check: the raw CBCT generated a 12,200,084-byte adaptive hard-tissue proxy STL with 118,452 vertices and 244,000 faces; SHA256 `37304a2c54d14378bdfe1ddf5bd8eeffb6828d64a168f1cc8c59e8d2d1af6e9c`.
- The modeling evidence remains `unregistered`, `not_reviewed`, `navigation_ready=false`, and `pending_slicer_or_physician_review`; its threshold, component statistics, physical LPS geometry, artifact hashes, and quality warnings are recorded.

The manifest binds the source page, direct file endpoint, license, remote ZIP size and MD5, ZIP64 central-directory values, selected member offset/CRC32, every local file size and SHA256, and the extraction timestamp.

## Use boundary

MMDental is a public dental CBCT and expert-record proxy. It can support the clinical-context schema, patient-level grouping, missing-value handling, bounded image-plus-context engineering, and 3D import checks. It has no osteomyelitis lesion masks, bone-activity classes, white-light/ICG pairs, or intraoperative outcomes. `target_domain_flag=false` and `training_eligible=false` remain mandatory.

The detailed public records are retained under the project's minimum-use data policy. Reports should expose aggregate structure and provenance without reproducing row-level medical text.

## Reproduce

```powershell
C:\Users\876762330\.conda\envs\osteo-vision\python.exe tools\materialize_mmdental_patient_context_starter.py --build-proxy-surface
```
