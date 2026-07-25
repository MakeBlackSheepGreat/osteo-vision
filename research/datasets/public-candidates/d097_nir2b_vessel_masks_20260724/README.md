# D097 NIR-IIb vessel-mask starter

This directory records the small public GitHub repository `ZhongLab2020/NIR-IIb_sO2_UNet` at commit `e5f3e95e9d72f222b98eead220e567484f2cdc72`.

- Content: 18 grayscale TIFF images paired with 18 binary vessel masks.
- Published split: 16 train pairs and 2 validation pairs.
- Window: NIR-IIb, 1500-1700 nm, as stated by the source README.
- Scene: intestinal vasculature with closed/opened-belly conditions.
- Local raw files: `raw/` and ignored by Git.
- Manifest: `d097_nir2b_vessel_masks_manifest.json` and `.csv`.

The repository does not declare a license and does not document animal/sample provenance or annotation protocol. This candidate remains `training_eligible=false`. It may be used for local decoding and segmentation-pipeline checks while permission and provenance are requested from the owner.

The dataset does not contain jaw, osteomyelitis, lesion, bone-surface, synchronized RGB, or clinical labels.
