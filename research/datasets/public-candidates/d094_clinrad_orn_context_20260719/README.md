# D094 ClinRad ORNJ Patient Context

Downloaded and audited: 2026-07-19

## Source

- Dataset: Available Data for Early Imaging Identification of Osteoradionecrosis and Classification Using the Novel ClinRad System: Results from A Retrospective Observational Cohort.
- Figshare record: <https://figshare.com/articles/dataset/Available_Data_for_Early_Imaging_Identification_of_Osteoradionecrosis_and_Classification_Using_the_Novel_ClinRad_System_Results_from_A_Retrospective_Observational_Cohort_/28292186/2>
- DOI: `10.6084/m9.figshare.28292186.v2`
- License: CC BY 4.0, cross-checked through the Figshare public API and DataCite.

## Local Content

- `raw/clinrad_orn_anonymized_cohort_v2.xlsx`: 53 unique anonymized human ORNJ records and 12 columns.
- `metadata/figshare_article_28292186_v2.json`: pinned Figshare public metadata and file inventory.
- `metadata/datacite_10.6084_m9.figshare.28292186.v2.json`: independent DOI, size and license metadata.
- `d094_clinrad_orn_context_manifest.json`: source URLs, license, patient count, content audit, sizes, hashes and use boundaries.

The table includes age, sex, diagnosis-code presence, HPV/p16 status, primary tumor location, radiotherapy dose and fractions, systemic therapy, time to ORNJ, Watson stage/grade and free-text CT, CBCT, panoramic or clinical findings. The audit found 53 patients aged 43 to 81 years, with Watson class counts `S0/G1=14`, `S1/G2=28`, `S2/G3=9` and `S3/G4=2`.

## Admission Boundary

This resource remains `target_domain_flag=false`, `training_eligible=false` and `review_required`. It contains real human ORNJ clinical context and image-derived interpretation labels. Raw CT/CBCT, intraoperative white-light/fluorescence frames, ROI coordinates, pixel masks, pathology mapping and navigation coordinates are unavailable. Its current use is limited to patient-context schema work, weak severity-label engineering and safety-boundary auditing.

Reproduce with:

```powershell
conda run -n osteo-vision python tools/download_d094_clinrad_orn_context.py
```
