# D024 DentVoxel 十模型基础分割测试报告（中文）

## 定位

本报告用于早期筛选 3D 医学分割基础模型。测试对象是 D024 DentVoxel jaw-roi 任务，输出仅代表低分辨率、短训练预算下的工程可跑性和初始收敛信号，不能视为正式模型性能。

## 数据与设置

- 数据集：D024 DentVoxel jaw-roi，100 例。
- 划分：fold 0，训练 80 例，验证 20 例。
- 测试输入尺寸：[64, 64, 64]，由原始 0.3 mm CBCT 下采样得到。
- 每模型训练批次数：80；验证病例数：20。
- 设备：cuda；PyTorch：2.11.0+cu128。

## 结果汇总

| Rank | Model | Status | Mean Dice | Mean IoU | Params | Train Loss | Time(s) | Peak GPU MB |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | MONAI SegResNetDS | completed | 0.4244 | 0.3338 | 3,154,599 | 0.2285 | 3.3746 | 313.5791 |
| 2 | MONAI BasicUNet++ | completed | 0.3930 | 0.2947 | 1,747,228 | 1.2469 | 8.8461 | 843.6621 |
| 3 | MONAI SegResNet | completed | 0.3289 | 0.2534 | 719,463 | 1.4260 | 2.1014 | 156.4268 |
| 4 | MONAI SwinUNETR Tiny | completed | 0.3211 | 0.2441 | 14,928,634 | 0.6488 | 7.1951 | 789.3965 |
| 5 | MONAI HighResNet | completed | 0.3199 | 0.2266 | 809,358 | 1.5288 | 21.0827 | 1667.3638 |
| 6 | MONAI BasicUNet | completed | 0.3192 | 0.2436 | 1,438,887 | 1.1699 | 3.4903 | 304.5391 |
| 7 | MONAI 3D U-Net | completed | 0.3134 | 0.2375 | 2,454,533 | 0.5217 | 1.9931 | 115.5967 |
| 8 | MONAI DynUNet ResBlock | completed | 0.2523 | 0.2060 | 5,690,775 | 1.0542 | 4.0242 | 375.9507 |
| 9 | MONAI Attention U-Net | completed | 0.2465 | 0.1673 | 5,909,215 | 1.3742 | 4.0319 | 413.5620 |
| 10 | MONAI UNETR Tiny | completed | 0.2078 | 0.1523 | 10,728,311 | 0.9673 | 5.5514 | 516.5093 |

## 初步判断

- nnU-Net 仍应保留为正式基线；本报告中的 MONAI 模型用于快速筛选结构路线和显存/速度特征。
- 低分辨率短训练下的 Dice 值主要反映模型是否能开始学习大结构，不足以判断下颌管等细小结构的最终潜力。
- 后续正式实验应回到 nnU-Net/MedNeXt/U-Mamba 的高分辨率训练、5-fold 验证和 HD95/NSD/clDice 指标。

## 候选模型依据

- nnU-Net v2 / ResEnc：Dental CBCT and biomedical segmentation engineering baseline; retained for formal high-resolution experiments.。来源：https://github.com/MIC-DKFZ/nnUNet
- MedNeXt：3D ConvNeXt-style segmentation baseline for a later high-resolution comparison.。来源：https://github.com/MIC-DKFZ/MedNeXt
- U-Mamba / SegMamba：Mamba-based medical segmentation candidates for later long-range dependency experiments.。来源：https://github.com/bowang-lab/U-Mamba
- MONAI 3D U-Net：Classic encoder-decoder baseline for volumetric medical segmentation.。来源：https://docs.monai.io/en/stable/networks.html#unet
- MONAI BasicUNet：Compact 3D U-Net implementation with modest parameter count.。来源：https://docs.monai.io/en/stable/networks.html#basicunet
- MONAI BasicUNet++：UNet++-style nested skip connections for multiscale feature reuse.。来源：https://docs.monai.io/en/stable/networks.html#basicunetplusplus
- MONAI Attention U-Net：Attention gates are relevant for suppressing irrelevant anatomy around jaw ROIs.。来源：https://docs.monai.io/en/stable/networks.html#attentionunet
- MONAI DynUNet ResBlock：nnU-Net-inspired configurable U-Net suitable for dataset-specific planning.。来源：https://docs.monai.io/en/stable/networks.html#dynunet
- MONAI SegResNet：Residual 3D CNN baseline with favorable memory footprint.。来源：https://docs.monai.io/en/stable/networks.html#segresnet
- MONAI SegResNetDS：Residual encoder-decoder with deep-supervision support.。来源：https://docs.monai.io/en/stable/networks.html#segresnetds
- MONAI HighResNet：High-resolution residual CNN with a conservative memory profile.。来源：https://docs.monai.io/en/stable/networks.html#highresnet
- MONAI UNETR Tiny：Transformer encoder baseline for global 3D context, reduced for 8 GB GPU testing.。来源：https://docs.monai.io/en/stable/networks.html#unetr
- MONAI SwinUNETR Tiny：Shifted-window transformer baseline for hierarchical 3D context.。来源：https://docs.monai.io/en/stable/networks.html#swinunetr

## 产物

- 结果 JSON：`artifacts\runs\d024_segmentation_model_benchmark\20260615T180721Z\d024_10_model_baseline_benchmark_summary.json`
- 结果 CSV：`artifacts\runs\d024_segmentation_model_benchmark\20260615T180721Z\d024_10_model_baseline_benchmark_results.csv`
- 本报告：`research\reports\modeling\d024_10_model_baseline_benchmark_zh.md`
- 英文报告：`research\reports\modeling\d024_10_model_baseline_benchmark_en.md`

## 医学边界

D024 是 CBCT 解剖结构分割数据，不包含颌骨骨髓炎、坏死骨或 ICG 荧光标签。结果只能作为术前解剖 ROI 和后续模型选型依据，不能作为临床诊断结论。
