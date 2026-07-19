# Layered Dataset Registry and Quality Gate Report

## Result

- Registered records: 504
- Quality gate: passed
- Errors: 0
- Warnings: 63
- Target-domain records: 0
- Records eligible for training admission checks: 393
- Quarantined missing-file records: 3
- Rows reassigned by source group: 95
- Domain tiers: `{"derived_proxy": 393, "fluorescence_proxy": 56, "near_domain": 55}`
- Label types: `{"automated_seed_mask": 9, "none": 102, "prompt_assisted_mask": 1, "proxy_mask": 392}`
- Usage policies: `{"engineering_source_reference": 74, "jaw_clinical_weak_label_seed_after_panel_crop_and_review": 4, "literature_reference_only": 1, "mechanism_reference_only": 3, "non_jaw_bone_infection_seed_after_panel_crop_and_review": 2, "oral_adjacent_weak_label_seed_after_panel_crop_and_review": 7, "preclinical_proxy_seed_after_panel_crop_and_review": 4, "proxy_pretrain_only_with_boundary": 192, "proxy_training_allowed_with_boundary": 201, "reference_only_no_derivatives": 1, "weak_label_training_seed_with_attribution": 15}`

## Gate Coverage

The automated checks cover provenance URLs, local files, SHA256, group split leakage, duplicate content, label-review consistency, target-domain flags, and sample-weight contracts.
Source rows with missing local files are quarantined. Multi-mask rows with inconsistent source-group splits are assigned a canonical video-level split, with every correction retained in the issue log.

## Data Boundary

The registry contains OFDVDnet mock chicken-thigh fluorescence videos, public osteomyelitis debridement videos, jaw-fluorescence article figures, and proxy or semi-automatic multi-mask samples. The target-domain count is zero. Raw multi-panel article figures are registered as near-domain source assets and do not directly enter segmentation training. Training metrics remain non-target-domain engineering evidence.

## Operational Use

Training candidates should pass this gate first. Doctor-reviewed accepted, modified, and rejected samples retain weights 4.0, 4.0, and 0.5; review_required remains 1.0.
