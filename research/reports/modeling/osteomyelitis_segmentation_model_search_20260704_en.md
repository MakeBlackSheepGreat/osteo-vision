# Osteomyelitis and Bone-Infection Segmentation Model Search

Date: 2026-07-04

## Summary

Tavily CLI searches did not identify an off-the-shelf public model for target-domain intraoperative ICG jaw osteomyelitis MP4/JPEG segmentation. The closest transferable evidence is in CBCT jaw-lesion segmentation and PET-CT bone-infection segmentation.

Most relevant sources:

- MRONJ CBCT nnU-Net v2 segmentation used 52 CBCT volumes, five-fold cross-validation, and reported Dice around 0.716, IoU around 0.569, and HD95 around 4.045 mm.
- Benign jaw lesion CBCT nnU-Net v2 segmentation used several hundred CBCT scans and reported DSC around 0.70-0.72, with external-test DSC around 0.84-0.87.
- Dual-modality PET-CT bone-infection segmentation proposes early fusion of PET metabolic signal and CT bone-window anatomy, highlighting fuzzy lesion boundaries and inter-observer annotation variability.
- DentalSegmentator provides a public nnU-Net v2.2 pretrained model and Slicer extension for dento-maxillo-facial CT/CBCT anatomical structures. It is not a lesion model, but it is directly useful for jaw ROI and anatomy priors.

## Local Training Implication

The project should continue the staged strategy:

1. Keep the current D025 base12 checkpoint as the CBCT lesion proxy model.
2. Add nnU-Net v2 or MONAI SegResNetDS as the next formal baseline.
3. Use DentalSegmentator as an anatomy-prior candidate.
4. Keep intraoperative ICG MP4/JPEG as fluorescence enhancement, hotspot analysis, ROI quantification, and physician-review workflow until true target-domain annotated data exist.

Current promoted D025 proxy checkpoint:

- Validation cases: 53.
- Best threshold: 0.2.
- Mean Dice: 0.6266.
- Mean IoU: 0.5183.
- Mean HD95: 17.6413.
- Mean NSD: 0.4227.
- Lesion sensitivity: 0.6756.
- Lesion precision: 0.6932.

## Sources

- MRONJ CBCT segmentation: https://pmc.ncbi.nlm.nih.gov/articles/PMC13077929/
- PubMed MRONJ segmentation entry: https://pubmed.ncbi.nlm.nih.gov/41787411
- Benign jaw lesion nnU-Net v2 segmentation: https://pubmed.ncbi.nlm.nih.gov/41530422
- PET-CT bone infection segmentation: https://arxiv.org/abs/2605.16373
- CVPR Workshop PDF: https://openaccess.thecvf.com/content/CVPR2026W/AI4RWC/papers/Yang_Cross-Source_Supervision_for_Bone_Infection_Segmentation_in_Dual-Modality_PET-CT_CVPRW_2026_paper.pdf
- DentalSegmentator pretrained model: https://zenodo.org/records/10829675
- DentalSegmentator/Slicer extension: https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools
- Scaling nnU-Net for CBCT Segmentation: https://arxiv.org/html/2411.17213v2

## Boundary

These sources support CBCT proxy segmentation, jaw anatomy priors, bone-infection boundary reasoning, and future multimodal fusion. They do not establish target-domain intraoperative ICG jaw osteomyelitis segmentation performance.
