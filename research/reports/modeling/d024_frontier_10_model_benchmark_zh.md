# D024 DentVoxel 第二轮前沿分割模型测试报告（中文）

## 定位

本报告回答“再找十个新分割模型试试看”的问题。测试对象仍为 D024 DentVoxel jaw-roi，属于低分辨率、短训练预算下的结构路线筛选。这里的多数实现是论文关键模块的本地轻量复现或 proxy，用于快速判断是否值得后续拉官方仓库做完整复现。

## 与论文复现的关系

- 官方级复现：需要独立安装论文仓库、按原始训练协议和数据设置跑完整实验。本轮只完成资料定位和依赖判断。
- 本地轻量复现：在当前 PyTorch/MONAI 环境内实现论文的关键结构思想，并用同一 D024 训练脚本测试可跑性和初始收敛。
- 结果解释：本轮结果不能与论文指标直接对比，也不能作为颌骨骨髓炎临床诊断性能依据。

## 数据与设置

- 数据集：D024 DentVoxel jaw-roi，100 例。
- 标签：1:maxilla, 2:mandible, 3:r_mandibular_canal, 4:l_mandibular_canal, 5:r_maxillary_sinus, 6:l_maxillary_sinus。
- 划分：fold 0，训练 80 例，验证 20 例。
- 输入尺寸：[64, 64, 64]，由原始 0.3 mm CBCT 下采样得到。
- 每模型训练批次数：80；验证病例数：20。
- 设备：cuda；GPU：NVIDIA GeForce RTX 5060 Laptop GPU；PyTorch：2.11.0+cu128。

## 第二轮十模型结果

| Rank | Model | Status | Mean Dice | Mean IoU | Params | Train Loss | Time(s) | Peak GPU MB |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | SegMamba Multi-Scale Proxy | completed | 0.2605 | 0.1772 | 251,335 | 1.0269 | 5.0798 | 668.5552 |
| 2 | 3D UX-Net Large-Kernel Proxy | completed | 0.2501 | 0.1775 | 261,375 | 1.4324 | 4.4651 | 206.4478 |
| 3 | MedNeXt Tiny Proxy | completed | 0.2315 | 0.1809 | 219,135 | 1.5939 | 2.6892 | 290.9878 |
| 4 | U-Mamba Bottleneck Proxy | completed | 0.2181 | 0.1614 | 214,335 | 1.7133 | 2.3072 | 355.8096 |
| 5 | TransBTS Bottleneck Proxy | completed | 0.2073 | 0.1537 | 234,047 | 1.1542 | 2.4004 | 356.9312 |
| 6 | SegFormer3D MLP-Decoder Proxy | completed | 0.1862 | 0.1200 | 122,343 | 1.4722 | 2.4287 | 353.6406 |
| 7 | MedNeXt K5 Proxy | completed | 0.1833 | 0.1288 | 242,655 | 1.8764 | 3.0433 | 291.2573 |
| 8 | nnFormer Window-Attention Proxy | completed | 0.1397 | 0.0890 | 275,215 | 1.0511 | 6.0105 | 659.5933 |
| 9 | RepUX-Net Multi-Branch Proxy | completed | 0.1350 | 0.1139 | 297,855 | 1.2100 | 5.8172 | 206.8755 |
| 10 | UNETR++ EPA Proxy | completed | 0.0710 | 0.0453 | 207,549 | 1.5446 | 2.3863 | 290.2378 |

## 初步判断

- 本轮最佳初始结果为 SegMamba Multi-Scale Proxy，mean Dice 0.2605。该结果只代表短训练预算下的早期信号。
- ConvNeXt/大核卷积类模型更适合先做工程化推进，因为依赖轻、显存可控，后续能自然接到 D024 和术中 ROI 任务。
- Mamba 类模型值得保留为长程依赖实验，但官方 mamba/causal-conv 依赖在 Windows 和当前 torch 版本上需要单独环境验证。
- Transformer 和 promptable foundation model 更适合后续做标注辅助、交互式边界修正或多模型融合，不建议抢在第一基线之前作为主线。

## 前沿模型来源与本地复现状态

| Model | Paper | Code | Local reproduction | Notes |
|---|---|---|---|---|
| MedNeXt | https://arxiv.org/html/2303.09975v5 | https://github.com/MIC-DKFZ/MedNeXt | Proxy: ConvNeXt-style 3D encoder-decoder with 3x3x3 and 5x5x5 depthwise blocks. | Official code is feasible later, but the current run avoids adding a separate dependency stack. |
| 3D UX-Net | https://arxiv.org/abs/2209.15076 | https://github.com/MASILab/3DUX-Net | Proxy: large-kernel depthwise 3D U-Net. | Tests whether large receptive fields help jaw ROI segmentation at low resolution. |
| RepUX-Net | https://github.com/MASILab/RepUX-Net | https://github.com/MASILab/RepUX-Net | Proxy: multi-branch large-kernel block that mimics train-time re-parameterization. | Full Bayesian frequency re-parameterization is left for a later official reproduction. |
| UNETR++ | https://arxiv.org/html/2212.04497v3 | https://github.com/amshaker/unetr_plus_plus | Proxy: efficient paired spatial/channel attention at the bottleneck. | Used as an efficient transformer route for 8GB-GPU screening. |
| TransBTS | https://github.com/Wenxuan-1119/TransBTS | https://github.com/Wenxuan-1119/TransBTS | Proxy: transformer sequence modeling only at the deepest feature map. | Full BraTS-oriented training code is not imported into the project tree. |
| nnFormer | https://arxiv.org/pdf/2109.03201 | https://github.com/282857341/nnFormer | Proxy: convolution blocks interleaved with local window attention. | Useful to compare local attention behavior against pure convolution. |
| SegFormer3D | https://github.com/OSUPCVLab/SegFormer3D | https://github.com/OSUPCVLab/SegFormer3D | Proxy: multiscale encoder features fused by simple 1x1 projections. | The official model is a stronger candidate for a later controlled reproduction. |
| U-Mamba | https://arxiv.org/abs/2401.04722 | https://github.com/bowang-lab/U-Mamba | Proxy: CNN encoder-decoder with a gated sequence-mixing bottleneck. | Official reproduction needs mamba/causal-conv setup and will be tracked separately. |
| SegMamba | https://arxiv.org/abs/2401.13560 | https://github.com/ge-xing/SegMamba | Proxy: multi-scale gated sequence-mixing blocks. | Official code depends on Mamba kernels and is better isolated in a future environment. |
| Swin-UMamba | https://arxiv.org/html/2402.03302v1 | https://github.com/JiarunLiu/Swin-UMamba | Reference only in this benchmark. | Promising route, but official setup pins older torch and mamba-ssm versions. |
| SAM-Med3D | https://arxiv.org/html/2310.15161v3 | https://github.com/uni-medical/SAM-Med3D | Reference only in this benchmark. | Promptable foundation segmentation is relevant to annotation assistance, not this supervised jaw-roi benchmark. |

## 下一步建议

1. 把本轮 top-3 与第一轮 SegResNetDS、BasicUNet++ 放入同一训练预算做复测。
2. 对 top-3 增加 Dice+CE、Dice+Focal 和类权重 CE 的消融，重点观察下颌管标签。
3. 单独建立 Linux/CUDA 兼容环境复现 U-Mamba、SegMamba 和 MedNeXt 官方代码。
4. 正式报告阶段回到 5-fold、HD95、NSD、clDice 和每类 Dice，不使用本轮低分辨率结果做临床表述。

## 产物

- 结果 JSON：`artifacts\runs\d024_frontier_segmentation_model_benchmark\20260616T015429Z\d024_frontier_10_model_benchmark_summary.json`
- 结果 CSV：`artifacts\runs\d024_frontier_segmentation_model_benchmark\20260616T015429Z\d024_frontier_10_model_benchmark_results.csv`
- 中文报告：`research\reports\modeling\d024_frontier_10_model_benchmark_zh.md`
- 英文报告：`research\reports\modeling\d024_frontier_10_model_benchmark_en.md`

## 医学边界

D024 是 CBCT 解剖结构分割数据，不包含颌骨骨髓炎、坏死骨或 ICG 荧光标签。本报告只用于模型选型和工程可行性判断。
