# Navigation, CBCT/STL and registration public-data audit

This directory contains the bounded public-data audit performed on 2026-07-18 for L1 static registration, L2 offline pose replay and maxillofacial CBCT surface modeling.

## Records

- `D085`: paired head-neck planning CT / first-day CBCT metadata with five anatomical labels. Metadata only; patient count and file-level pairing remain unverified.
- `D086`: Teeth3DS+ / 3DTeethLand landmark archives. The small train/test landmark ZIP files, split lists, OSF metadata and original `CC BY-NC-ND 4.0` license were downloaded and hash-verified. Matching OBJ meshes are absent locally. Coordinate units and axis conventions require review.
- `D087`: C3VD metadata for model-to-video registration, hand-eye calibration, temporal synchronization and per-frame pose replay. The official sample is 1,515,094,074 bytes and was skipped.
- `D088`: EndoSLAM metadata for timed 6DoF pose and 3D map proxy validation. Dataset files remain undownloaded.
- `D089`: ToothFairy3 official dataset-page metadata. Download requires registration; test data remain private.

Every record is fixed to `target_domain_flag=false`, `training_eligible=false`, `review_state=review_required`, and `navigation_claim_allowed=false`. Metadata-only and access-controlled resources cannot enter training. D086 landmark archives are restricted to non-commercial internal engineering analysis under their original license and may not be redistributed as adapted data.

Machine-readable provenance is stored in `navigation_cbct_stl_manifest.json` and `navigation_cbct_stl_manifest.csv`. `downloaded_file_verification.csv` records the measured size and SHA256 of every downloaded source file.

Tavily was attempted first and returned a plan usage-limit error. The completed fallback used ordinary web search and official OSF, DataCite, Zenodo OAI-PMH, GitHub, Grand Challenge and Mendeley sources.
