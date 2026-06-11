# osteo-vision

颌骨骨髓炎智能化荧光诊疗 (Osteomyelitis Intelligent Fluorescence Diagnosis and Treatment)

## 项目简介

本项目面向颌骨骨髓炎智能化荧光诊疗竞赛，核心研究方向为 ICG 荧光成像 + AI 辅助诊断，用于颌骨骨髓炎术中决策支持。

## 竞赛赛道

1. **赛点一**: 荧光图像伪彩色增强（白光 + ICG 融合）
2. **赛点二**: AI 辅助诊断（目标检测/分割）
3. **赛点三**: DICOM 标准输出与远程协作

## 项目结构

```
osteo-vision/
├── code/
│   ├── egnet/          # EGNet 边界区域闭环分割模型
│   ├── frs_loss/       # 模糊粗糙集损失函数
│   └── nnunet/         # nnU-Net 自动配置分割框架
├── datasets/           # 数据集目录
├── docs/               # 参考文档、图片
├── output/
│   └── literature/     # 文献综述、数据集清单、可行性报告
├── scripts/
│   └── docx-gen/       # C# DOCX 报告生成器
└── *.docx, *.pdf       # 项目文档
```

## 核心模型

| 模型 | 用途 | 来源 |
|------|------|------|
| nnU-Net | 基线分割（自动配置） | [github.com/MIC-DKFZ/nnUNet](https://github.com/MIC-DKFZ/nnUNet) |
| EGNet | 边界区域闭环分割 (2026 SOTA) | [github.com/ITXIAOWU123/EGNet](https://github.com/ITXIAOWU123/EGNet) |
| FRS Loss | 模糊粗糙集损失函数 | [github.com/MohsinFurkh/Fuzzy-Rough-Set-Loss](https://github.com/MohsinFurkh/Fuzzy-Rough-Set-Loss) |

## 技术栈

- **分割**: nnU-Net + EGNet 边界分支 + FRS Loss
- **不确定性估计**: Stochastic Segmentation Networks / MC Dropout
- **半监督学习**: WaveletFusion-ViT (骨髓炎分类 AUC 0.96)

## 重要数据集

- **D024 DentVoxel**: 38 结构标注牙科 CBCT（最高相关性）
- **D036 ToothFairy2**: 42 类 CBCT 分割 (MICCAI 2024)
- **D039 ToothPix**: 8655 全景图像，30186 像素级标注
- **D044 FGS Video**: ICG 荧光手术视频去噪 (34GB)

## 使用方法

```bash
# 生成 DOCX 报告（需要 .NET 10）
cd scripts/docx-gen && dotnet run

# 下载待处理论文
bash scripts/download_pending.sh
```

## 许可证

MIT License - Copyright (c) 2026 ZHIJIE YANG
