# Public-data gap audit for navigation, CBCT/STL and registration

Date: 2026-07-18
Status: engineering data audit; every new record remains `target_domain_flag=false` and `training_eligible=false`.

## Outcome

D024 and D036 already support maxillofacial CBCT anatomy segmentation and maxilla/mandible surface export. D025 contains lesion CBCT and histology-like evidence, while its archive lacks a separate license file and remains governance-blocked. D076 SERV-CT covers ex-vivo stereo endoscopy, cone-beam CT, depth and reprojection proxy validation.

This audit adds D085-D089. D085 is a paired planning-CT/first-day-CBCT head-neck candidate with five anatomical labels. D086 contributes small, verified Teeth3DS+ landmark archives for 340 IOS scans. D087 C3VD provides the strongest public proxy contract for L2 because it documents OBJ models, intrinsics, hand-eye calibration, temporal offsets, robot pose logs and per-frame camera poses. D088 EndoSLAM adds timed 6DoF trajectories and high-precision 3D maps. D089 ToothFairy3 is a newer maxillofacial CBCT segmentation candidate requiring registration for download.

No verified public resource was found that jointly provides jaw CBCT, reviewed jaw/lesion surfaces, physical STL coordinates, independent fiducial ground truth, microscope intrinsics with magnification/working distance, optical tracking, synchronized video and surgical-navigation TRE truth. L1 therefore still requires a measured jaw-phantom dataset. D087 and D088 can validate the L2 software contract and fail-closed behavior before the same contract is transferred to that phantom.

Tavily CLI was attempted first and returned a plan usage-limit error. The fallback used ordinary DuckDuckGo search and official OSF, DataCite, Zenodo OAI-PMH, GitHub, Grand Challenge, Mendeley and project pages. No multi-gigabyte download was started. File-level provenance, licenses, sizes and SHA256 values are recorded in `navigation_cbct_stl_manifest.json`.
