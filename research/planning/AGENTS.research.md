# AGENTS.md

## Project Overview

Research project for **颌骨骨髓炎智能化荧光诊疗** (Osteomyelitis Intelligent Fluorescence Diagnosis and Treatment) competition.

Core focus: ICG fluorescence imaging + AI-assisted diagnosis for jaw osteomyelitis intraoperative decision support.

## Project Structure

```
osteo-vision/
├── docs/                    # WeChat images, reference documents
├── output/
│   ├── literature/
│   │   ├── papers/          # 61 PDF research papers
│   │   ├── dataset_inventory.csv  # 35 datasets cataloged
│   │   ├── paper_inventory.csv
│   │   └── *.md             # Feasibility reports
│   └── 项目可行性报告.docx
├── scripts/
│   ├── docx-gen/            # C# DOCX generator (OpenXml)
│   ├── create_report.csx    # Report generation script
│   └── download_*.sh/.js    # Paper download scripts
└── *.docx, *.pdf            # Project documents
```

## Key Files

- `output/literature/paper_inventory.csv` - 论文清单（60篇，含相关度标记）
- `output/literature/dataset_inventory.csv` - 数据集清单（45个，含相关度标记）
- `output/literature/literature_and_dataset_summary.md` - 文献与数据集汇总（精简版）
- `output/literature/competition_feasibility_report.md` - 可行性报告

## Competition Tracks

1. **赛点一**: Fluorescence image pseudo-color enhancement (white light + ICG fusion)
2. **赛点二**: AI-assisted diagnosis (object detection/segmentation)
3. **赛点三**: DICOM standard output & remote collaboration

## Core Models (with open-source code)

| Model | Use Case | Repository |
|-------|----------|------------|
| nnU-Net | Baseline segmentation (auto-config) | github.com/MIC-DKFZ/nnUNet |
| TransUNet | Boundary-blurred lesion segmentation | github.com/Beckschen/TransUNet |
| EGNet | Boundary-region closed-loop (2026 SOTA) | github.com/ITXIAOWU123/EGNet |
| FRS Loss | Fuzzy rough set loss for模糊边界 | github.com/MohsinFurkh/Fuzzy-Rough-Set-Loss |
| MedSAM | Interactive ROI annotation | github.com/bowang-lab/MedSAM |

## Recommended Tech Stack

- **Segmentation**: nnU-Net + EGNet boundary branch + FRS Loss
- **Uncertainty**: Stochastic Segmentation Networks or MC Dropout
- **Semi-supervised**: WaveletFusion-ViT approach (AUC 0.96 on osteomyelitis classification)

## Important Datasets

- **D024 DentVoxel**: 38-structure annotated dental CBCT (highest relevance)
- **D025**: Odontogenic lesion CBCT + histopathology (closest to osteomyelitis)
- **D036 ToothFairy2**: 42-class CBCT segmentation (MICCAI 2024)
- **D037 MMDental**: 660 patients CBCT + medical records
- **D039 ToothPix**: 8655 panoramic images with 30186 pixel-level annotations
- **D042 MODID**: 243 multispectral oral disease images (16 bands)
- **D044 FGS Video**: ICG fluorescence surgery video denoising (34GB)
- **D005**: Panoramic radiograph + mandible segmentation
- **D014**: 27.9K panoramic radiographs (large-scale pretraining)

## Script Usage

```bash
# Generate DOCX report (requires .NET 10)
cd scripts/docx-gen && dotnet run

# Download pending papers
bash scripts/download_pending.sh
```

## Platform Notes

- Windows environment (paths use C:\Users\...)
- Scripts assume Git Bash for .sh files
- C# scripts target .NET 10.0
