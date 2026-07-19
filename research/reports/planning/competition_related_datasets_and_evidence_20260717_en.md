# Competition-Related Datasets and Evidence Review

Date: 2026-07-17
Scope: competition proposal, dataset strategy, innovation claims, and joint validation planning.
Medical boundary: all outputs are research-validation and intraoperative decision-support results subject to clinician review, abstention, and safe fallback.

## Executive conclusion

No public dataset was found that jointly provides jaw osteomyelitis or osteonecrosis, synchronized native RGB/fluorescence/device-overlay streams, CBCT or a 3D model, microscope pose/zoom/working distance, patient clinical variables, and clinician pixel labels for necrotic, transition, and viable bone.

Tavily was unavailable because its quota was exhausted. The search was continued through Bing, official dataset pages, Grand Challenge, GitHub, the Dryad API, the Nature/Scientific Data article, and the Figshare DOI. This live verification added two useful resources:

- [MMDental](https://www.nature.com/articles/s41597-025-05398-7): 660 patients, 403 CBCT NIfTI volumes, and a 12-field `medical_records.csv` covering sex, age, complaints, follow-up, present and past history, oral examination, diagnosis, treatment plan, management, and clinician advice. The dataset is released under CC BY at <https://doi.org/10.6084/m9.figshare.28505276>. It does not provide necrotic/transition/viable-bone pixel labels.
- [Open-Full-Jaw](https://github.com/diku-dk/Open-Full-Jaw): 17 patient-specific jaw computational models with mandible, maxilla, teeth, periodontal-ligament meshes, and tooth principal axes. The repository license text is CC BY-NC-SA 4.0.

A layered validation strategy is feasible:

- D049-D050 cover infected-bone microscopy, human bone autofluorescence, and age-related bone microenvironments.
- D063-D065 cover dual-channel fluorescence video, fluorescence denoising, dynamic ICG signals, and the MP4/JPEG software pipeline.
- D058-D060 cover image-plus-tabular clinical fusion, missing-data handling, and multicenter testing.
- D061 supports jaw CBCT anatomy and 3D surfaces; D062 is a cross-domain osteonecrosis proxy.
- D053-D057 and D068 cover calibration, depth, pose, 2D-3D registration, drift, and failure detection.

The structured inventory is stored in `research/literature/inventory/competition_multimodal_dataset_candidates_20260717.csv`.

## High-priority datasets

| Group | Recommended resources | Valid use | Main limitation |
| --- | --- | --- | --- |
| Bone fluorescence | Zenodo 8411792; Zenodo 14212791 | fluorescence preprocessing, self-supervised learning, autofluorescence and age-related tissue studies | microscopic or biopsy scale; no operative jaw boundary truth |
| Surgical fluorescence | OFDVDnet; Zenodo 11479346; Zenodo 14942607 | dual-channel video, denoising, temporal ICG and MP4 engineering | non-jaw and non-osteomyelitis |
| Clinical-variable fusion | HECKTOR 2025; MMDental; HNSCC TCIA; Head-Neck-PET-CT | conditional segmentation, patient-context contracts, missing-value modelling, calibration and center-level validation | HECKTOR/TCIA are cancer-domain; MMDental has no pixel segmentation truth; no necrotic-bone labels or laboratory panel |
| Jaw anatomy | ToothFairy2; Open-Full-Jaw | maxilla/mandible gating, CBCT coordinates, object trees, mesh inspection and 3D surfaces | no osteomyelitis, fluorescence, or necrotic/viable-bone labels |
| Navigation proxies | C3VD; SERV-CT; SCARED; EndoSLAM; EndoMapper; MicroRGBD | calibration, depth, pose, CT-surface registration, AR projection and drift tests | non-jaw domains; several datasets require application or license checks |

Existing D036, D046, D047, and D048 assets should be reused. Newly proposed identifiers are D049 for infected mouse bone fluorescence, D050 for human bone lightsheet autofluorescence, and D051 for jaw-osteonecrosis spatial imaging data. D052 Evans blue data should remain quarantined until file access and content are verified.

## Evidence supporting the proposal

### Tetracycline and bone autofluorescence

Relevant evidence includes ORNJ tetracycline/autofluorescence research (PMID 35698727; DOI `10.1177/03000605221104186`), critical and systematic reviews (PMID 32916330; DOI `10.1016/j.pdpdt.2020.102003`; PMID 36164452; DOI `10.1155/2022/1650790`), a 56-sample autofluorescence-pathology study (PMID 40430114; DOI `10.3390/life15050686`), and a meta-analysis covering 285 patients and 314 lesions (PMID 41917690; DOI `10.1111/odi.70320`).

This evidence supports bone-activity fluorescence as an adjunct boundary signal and supports autofluorescence as a lower-risk initial validation path. It does not establish target-domain pixel-level performance or a clinical dosing protocol.

### Evans blue

The identified Dryad candidate concerns Evans-blue autofluorescence and permeability in injured mouse vocal folds. It can support the albumin-binding and vascular-permeability mechanism. It cannot support jaw dead-bone selectivity, operative safety, or human use. No open Evans-blue bone or dead-bone training dataset was found.

### Clinical variables in segmentation

The official HECKTOR 2025 page confirms more than 1,200 cases from 11 centers, with approximately 700 training cases from 8 centers and 450 test cases from 3 centers. It provides registered PET/CT, GTVp/GTVn voxel labels, age, sex, tobacco, alcohol, performance, treatment, HPV, recurrence, RFS, and other fields. MMDental provides jaw-domain CBCT plus patient records for 660 patients, including 403 CBCT volumes and 12 clinical-record fields, while providing no segmentation masks. HNSCC TCIA provides 627 head-and-neck cases with CT, radiotherapy, demographics, risk factors, stage, recurrence, and survival. These resources can validate a reusable multimodal architecture and patient-context data contract.

Direct methodological support includes clinical-input-assisted segmentation (DOI `10.1088/2632-2153/adb371`), HyperFusion (DOI `10.1016/j.media.2025.103503`), FiLM (DOI `10.1609/aaai.v32i1.11671`), and neural-network calibration (<https://proceedings.mlr.press/v70/guo17a.html>).

Clinical variables should condition features or calibrate risk while spatial boundaries remain image-supported. Claims that clinical variables improve jaw dead-bone segmentation require target-domain ablation and external validation.

### Transition zones and uncertainty

MRONJ CT and CBCT evidence demonstrates heterogeneous imaging presentation, including an 18-case CT study with extensive clinical variables (DOI `10.1038/s41598-023-39755-6`) and a CBCT quantitative review (<https://pmc.ncbi.nlm.nih.gov/articles/PMC10024109/>). ToothFairy2 supplies maxillofacial anatomical labels, and Open-Full-Jaw adds 17 patient-specific jaw mesh models for object-tree, mesh-quality, and geometry checks. Recommended outputs are continuous activity probability, necrotic/viable candidate regions, a transition or uncertain region, and clinician-reviewed versions. A displayed value of 0.80 should be described as calibrated confidence or prediction-set coverage, with no conversion into complete-resection or cure probability.

### Microscope-to-3D registration and navigation

C3VD (PMID 37713764; DOI `10.1016/j.media.2023.102956`) and navigation proxy datasets support calibration, depth, pose, projection, drift, and safe fallback testing. Direct supporting literature covers real-time endoscopic reconstruction (PMID 38786574; DOI `10.3390/jimaging10050120`), mandibular AR phantom registration (`10.1186/s12903-024-05105-9`), zygomatic implant AR navigation (`10.7717/peerj.18468`), optical-to-CBCT registration (`10.1109/TBME.2025.3606469`), microscope AR calibration (`10.1007/s11517-025-03288-z`), zoom-lens calibration (`10.1016/j.compbiomed.2024.109309`), microscopic surface reconstruction (`10.1007/s11548-024-03242-8`), and the open NousNav accuracy framework (`10.1007/s11548-025-03494-y`).

A project-specific validation set remains necessary. It should record native RGB, raw fluorescence, device overlay, hardware timestamps, frame identifiers, exposure/gain, zoom, working distance, intrinsics, distortion, cross-channel pixel mappings, phantom/fiducial tracking truth, target-registration error, drift, tracking loss, and recovery time.

## Four implementation classes

1. Directly actionable: fluorescence proxy data, HECKTOR/MMDental/TCIA multimodal pipelines, ToothFairy2/Open-Full-Jaw jaw anatomy, and C3VD/SERV-CT geometric validation.
2. Collaboration required: device SDK and synchronization data, hospital cases and clinician labels, laboratory/phantom fluorescence validation, and controlled-access dataset applications.
3. Evidence or risk reduction only: Evans-blue non-bone data, spatial omics, cross-domain osteonecrosis, publication figures, and non-target ICG videos.
4. No reliable substitute: a unified target-domain dataset and pathology/follow-up truth for a complete-resection probability.

## Recommended next actions

1. Register and inspect small samples from D049 and D050 before downloading complete multi-gigabyte archives.
2. Apply for HECKTOR and build the clinical-conditioning, missing-data, ablation, calibration, and multicenter evaluation template; evaluate MMDental's 403 CBCT volumes and 660 records through a patient-mapping and no-mask admission workflow.
3. Reuse ToothFairy2 for jaw gating, Open-Full-Jaw for patient-specific mesh and object-tree checks, and C3VD/SERV-CT for registration error gates.
4. Obtain the microscope interface specification and define a synchronized three-stream mandibular-phantom protocol.
5. Co-design clinician definitions and inter-reviewer metrics for necrotic, transition, and viable bone.
6. Contact MRONJ/ORNJ fluorescence study authors for de-identified native images, acquisition parameters, annotations, and pathology correspondence.

All external datasets must retain source, license, checksum, acquisition date, intended use, and domain labels. Patient-level splitting is mandatory. Animal, phantom, ex-vivo, microscopic, cross-domain, and publication-derived data must remain explicitly separated from target-domain clinical evidence.
