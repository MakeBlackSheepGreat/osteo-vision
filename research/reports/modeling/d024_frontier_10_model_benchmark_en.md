# D024 DentVoxel Second-Round Frontier Segmentation Benchmark

## Scope

This report addresses the request to screen ten additional segmentation models. The benchmark still uses D024 DentVoxel jaw-roi under a low-resolution, short-budget setup. Most implementations are local lightweight reproductions or proxies of key paper ideas, intended to decide which official repositories deserve full reproduction next.

## Reproduction Level

- Official reproduction requires installing the paper repository and running its original protocol. This round records source discovery and dependency status only.
- Local lightweight reproduction implements the key architectural idea inside the current PyTorch/MONAI environment and runs it under the same D024 protocol.
- The results cannot be compared directly with paper scores and must not be used as clinical diagnostic performance.

## Data and Setup

- Dataset: D024 DentVoxel jaw-roi, 100 cases.
- Labels: 1:maxilla, 2:mandible, 3:r_mandibular_canal, 4:l_mandibular_canal, 5:r_maxillary_sinus, 6:l_maxillary_sinus.
- Split: fold 0, 80 training cases and 20 validation cases.
- Input size: [64, 64, 64], downsampled from 0.3 mm CBCT volumes.
- Training batches per model: 80; validation cases: 20.
- Device: cuda; GPU: NVIDIA GeForce RTX 5060 Laptop GPU; PyTorch: 2.11.0+cu128.

## Results

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

## Initial Interpretation

- The best early result is SegMamba Multi-Scale Proxy with mean Dice 0.2605. This is an early signal under a short training budget only.
- ConvNeXt and large-kernel ConvNet routes are the most practical near-term engineering candidates because they keep dependencies and memory under control.
- Mamba-style models should remain long-range dependency experiments, but official mamba/causal-conv dependencies need a separate compatibility check.
- Transformer and promptable foundation models are better suited for annotation assistance, interactive boundary correction, or later ensemble work than for the first production baseline.

## Frontier Sources and Local Reproduction Status

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

## Next Steps

1. Re-run the top three models together with first-round SegResNetDS and BasicUNet++ under the same training budget.
2. Add Dice+CE, Dice+Focal, and class-weighted CE ablations, with special attention to mandibular canal labels.
3. Create a separate Linux/CUDA-compatible environment for official MedNeXt, U-Mamba, and SegMamba reproduction.
4. Return to 5-fold validation, HD95, NSD, clDice, and per-class Dice for formal reporting.

## Artifacts

- Result JSON: `artifacts\runs\d024_frontier_segmentation_model_benchmark\20260616T015429Z\d024_frontier_10_model_benchmark_summary.json`
- Result CSV: `artifacts\runs\d024_frontier_segmentation_model_benchmark\20260616T015429Z\d024_frontier_10_model_benchmark_results.csv`
- Chinese report: `research\reports\modeling\d024_frontier_10_model_benchmark_zh.md`
- English report: `research\reports\modeling\d024_frontier_10_model_benchmark_en.md`

## Medical Boundary

D024 is an anatomical CBCT segmentation dataset. It does not include jaw osteomyelitis, necrotic bone, or ICG fluorescence labels. This report is only model-selection and engineering-feasibility evidence.
