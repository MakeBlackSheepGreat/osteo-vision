# Model Training Data Sources and Near-Term Training Route

Date: 2026-07-03

## Summary

The project should not rely on public CBCT datasets alone. The official competition device outputs 4K MP4 video and JPEG images, so the training plan needs two connected tracks:

1. **Intraoperative white-light/ICG MP4-JPEG track**: the target domain for the software. Before expert labels exist, this track should be used for upload, QC, keyframe extraction, ROI annotation, fluorescence visualization, and evidence packaging, not for claims of clinical-grade lesion segmentation.
2. **CBCT anatomy and lesion-proxy track**: public dental CBCT datasets can train jaw/tooth/canal anatomy priors and lesion-proxy segmentation models. These models support the AI-assistance platform capability but do not replace intraoperative ICG labels.

The recommended near-term route is: use nnU-Net/SegResNetDS on CBCT anatomy and lesion proxies; use MP4/JPEG keyframes for ROI annotation, MedSAM/SAM2-assisted labeling, and lightweight ConvNeXt/2D segmentation validation workflows; fuse CBCT and ICG evidence at the report/workbench level first.

## Local Data Status

| Source | Local status | Main use | Boundary |
|---|---:|---|---|
| D024 DentVoxel | Processed, 100 cases | 3D jaw/tooth/canal anatomy prior | Not osteomyelitis, not ICG |
| D025 DOLCHID lesion CBCT | Processed, 262 cases | Lesion-proxy segmentation/classification | Odontogenic lesion proxy, not jaw osteomyelitis |
| D036 ToothFairy2 | Processed, 480 cases | Multi-structure CBCT anatomy segmentation | Anatomy performance is not lesion performance |
| D042 MODID | Local folder exists, 0 files | Oral multispectral reference | Needs download/license check |
| D044 FGS video | Local folder exists, 0 files | Fluorescence video enhancement reference | Non-oral, non-osteomyelitis |

## Priorities

1. **P0 target-domain data**: de-identified official-device MP4/JPEG files with expert keyframe ROI masks and review states.
2. **P1 public CBCT**: D024/D036 for anatomy, D025 for lesion proxy. Use nnU-Net v2 ResEnc as the reliable baseline.
3. **P2 fluorescence/spectral data**: OFDVDnet/FGS video, MODID, and ODSI-DB for denoising, enhancement, and optical-domain robustness.
4. **P3 other dental datasets**: panoramic, periapical, and oral RGB datasets for broader pretraining only.

## Immediate Actions

1. Create an `official_video_keyframe_manifest.csv` for uploaded MP4 files, extracted keyframes, timestamps, resolution, and preview paths.
2. Add a reviewed ROI annotation path for keyframes before any supervised video model training.
3. Continue D025 as the lesion-proxy mainline with high-resolution ROI crops and nnU-Net/SegResNetDS.
4. Merge D024/D036 into a 5-class anatomy prior task for jaw ROI extraction.
5. Re-download and verify D042/D044 before including them in training.

## Medical Boundary

ICG is a perfusion and tissue-viability reference signal, not a jaw osteomyelitis-specific probe. D024/D036 are anatomy datasets and D025 is an odontogenic lesion proxy. Competition and research outputs should be described as candidate regions, boundary-risk hints, and physician-review support, not automatic diagnosis.

## References

- Official technical alignment: `research/reports/planning/official_technical_document_alignment_zh.md`
- DentVoxel: https://figshare.com/articles/dataset/DentVoxel_a_fully_annotated_dental_CBCT_dataset_with_38_instance_anatomical_structures/31239889
- ToothFairy2: https://toothfairy2.grand-challenge.org/
- Scaling nnU-Net for CBCT Segmentation: https://arxiv.org/abs/2411.17213
- DOLCHID dataset: https://springernature.figshare.com/articles/dataset/Dental_Odontogenic_Lesion_CBCT_and_Histopathology_Integrated_Dataset_for_Benchmarking_Deep_Learning_Algorithms/30156622
- MRONJ CBCT nnU-Net study: https://pmc.ncbi.nlm.nih.gov/articles/PMC13077929/
- FGS video denoising dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9
- OFDVDnet paper: https://proceedings.mlr.press/v227/seets24a.html
- MODID: https://datadryad.org/dataset/doi%3A10.5061/dryad.nvx0k6dxw
- ODSI-DB: https://sites.uef.fi/spectral/databases-software/odsi-db/
