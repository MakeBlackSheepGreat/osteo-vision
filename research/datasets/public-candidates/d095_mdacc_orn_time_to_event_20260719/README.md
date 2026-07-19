# D095 MDACC ORNJ Time-to-Event Context

Downloaded and audited: 2026-07-19

## Source

- Dataset: MDACC ORN Time-to-event anonymized clinical dataset
- Figshare record: <https://figshare.com/articles/dataset/MDACC_ORN_Time-to-event_anonymized_clinical_dataset/26240435/1>
- DOI: `10.6084/m9.figshare.26240435.v1`
- License: CC BY 4.0, cross-checked through the Figshare public API and DataCite.
- Governance statement: the publisher metadata identifies the table as anonymized and public.

## Local Content

- `raw/mdacc_orn_time_to_event_v1.csv`: 1,129 unique anonymized records and 61 complete columns.
- `metadata/figshare_article_26240435_v1.json`: pinned Figshare public metadata and file inventory.
- `metadata/datacite_10.6084_m9.figshare.26240435.v1.json`: independent DOI, size and license metadata.
- `d095_mdacc_orn_time_to_event_manifest.json`: source URLs, governance state, content audit, sizes, hashes and use boundaries.

The table includes age, sex, smoking, dental extraction, tumor stage, chemotherapy, radiotherapy setting, HPV/p16, tumor site, survival, ORNJ status and time, Tsai grade, mandible volume and dose-volume features. The audit found 198 ORNJ-positive records and grade counts `0=931`, `1=36`, `2=39`, `3=54`, `4=69`; all 68,869 cells are populated.

## Admission Boundary

This resource remains `target_domain_flag=false`, `training_eligible=false` and `review_required`. It contains human ORNJ outcomes and image-derived mandible dosimetry. Raw CT, mandible pixel masks, operative white-light/fluorescence frames, bone-activity labels, pathology mapping and navigation coordinates are unavailable. Its current use is limited to patient-context schema work, grouped evaluation, weak ordinal outcome engineering and subgroup/no-harm audit design.

Reproduce with:

```powershell
conda run -n osteo-vision python tools/download_d095_mdacc_orn_time_to_event.py
```
