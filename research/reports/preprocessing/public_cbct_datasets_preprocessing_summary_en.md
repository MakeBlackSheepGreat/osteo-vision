# Public CBCT Dataset Extraction and Preprocessing Summary

## Scope

This run processes D024 DentVoxel, D025 DOLCHID, and D036 ToothFairy2. Source ZIP files and raw metadata files are only read/extracted and are not rewritten under raw/. Derived manifests, quality checks, previews, and reports are written under derived/ and research/reports/preprocessing/.

## Summary

| Dataset | Status | Cases | Manifest | Report |
|---|---|---:|---|---|
| d024 | processed | 100 | `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_manifest.csv` | `research\reports\preprocessing\d024_dentvoxel_preprocessing_en.md` |
| d025 | processed | 262 | `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_manifest.csv` | `research\reports\preprocessing\d025_dolchid_preprocessing_en.md` |
| d036 | processed | 480 | `research\datasets\public-candidates\d036_toothfairy2\derived\manifests\d036_toothfairy2_manifest.csv` | `research\reports\preprocessing\d036_toothfairy2_preprocessing_en.md` |

## Next Steps

1. Convert D025 into a binary lesion segmentation task and start with 64³/128³ smoke runs.
2. Align D036 and D024 jaw-roi label mappings for preoperative ROI structure segmentation.
3. Keep training outputs in ignored local directories; retain only reports and essential previews as long-term evidence.
