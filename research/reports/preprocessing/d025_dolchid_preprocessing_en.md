# D025 DOLCHID Preprocessing Report

## Source and Layout

- Dataset: DOLCHID
- Source ZIP: `research\datasets\public-candidates\d025_lesion_cbct\DOLCHID.zip`
- Raw directory: `research\datasets\public-candidates\d025_lesion_cbct\raw\DOLCHID`
- Derived directory: `research\datasets\public-candidates\d025_lesion_cbct\derived`
- Metadata policy: No original metadata file was found in the archive; generated metadata is written only under derived/.

## Extraction

- Newly extracted files: None
- Existing files skipped: None
- Unsafe path entries: 0

## Pairing Check

- Total case IDs: 262
- Fully paired cases: 262
- Directory counts: `{'cbct_image': 262, 'cbct_label': 262, 'hist_image': 262, 'hist_label': 262}`
- Diagnosis prefix distribution: `{'AME': 72, 'DC': 44, 'KCOT': 92, 'RC': 54}`

## Quality Check

- Quality rows: 262
- Status counts: `{'ok': 262}`
- CBCT shape distribution: `{'512x512x507': 14, '512x512x508': 24, '512x512x505': 30, '512x512x511': 50, '512x512x509': 82, '502x462x489': 1, '505x462x483': 1, '500x462x475': 1, '512x512x510': 10, '497x463x210': 1, '512x512x480': 2, '505x462x499': 1, '527x513x489': 1, '513x457x440': 1, '511x463x396': 1, '492x404x428': 1, '508x463x483': 1, '512x512x410': 4, '462x462x367': 1, '463x463x340': 1, '510x500x483': 1, '512x521x515': 1, '512x435x422': 1, '513x462x464': 1, '510x463x389': 1, '512x512x494': 1, '509x462x484': 1, '512x462x483': 1, '512x462x442': 1, '480x487x483': 1, '462x462x354': 1, '512x512x409': 2, '513x512x521': 1, '462x484x464': 1, '512x512x472': 1, '513x512x510': 1, '485x475x426': 1, '512x513x505': 1, '513x513x510': 1, '509x463x433': 1, '505x462x482': 1, '462x462x424': 1, '512x512x383': 1, '507x462x478': 1, '502x462x398': 1, '507x462x412': 1, '513x494x409': 1, '505x461x364': 1, '462x462x338': 1, '489x463x409': 1, '509x462x480': 1, '512x504x472': 1, '510x494x473': 1}`
- CBCT spacing distribution: `{'0.3x0.3x0.3': 240, '0.3x0.3x0.300002': 2, '0.3x0.3x0.300004': 1, '0.3x0.3x0.299999': 7, '0.3x0.3x0.300685': 1, '0.3x0.3x0.300001': 8, '0.3x0.3x0.299998': 3}`
- CBCT label-value presence: `{'0': 262, '1': 262}`
- Histology label-value presence: `{'0': 233, '255': 262}`

## Artifacts

- Manifest: `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_manifest.csv`
- Quality CSV: `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_quality_check.csv`
- Diagnosis inventory: `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_diagnosis_inventory.csv`
- Summary JSON: `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_preprocessing_summary.json`
- Preview cases: 5

## Project Use and Boundary

DOLCHID is the closest current dataset for the multimodal processing capability because it contains CBCT lesion masks and paired histology images. It is still not intraoperative ICG fluorescence data. Diagnosis-group meanings must be verified from source documentation before any clinical wording is used.
