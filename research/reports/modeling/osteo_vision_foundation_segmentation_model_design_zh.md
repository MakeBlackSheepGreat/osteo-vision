# Osteo-Vision 基础分割模型设计报告（中文）

日期：2026-06-17

## 结论摘要

当前三数据集快速 benchmark 的 Dice 偏低，主要原因应归结为实验范式仍停留在 `64x64x64` 全体积缩略 smoke，单个网络结构的新旧只属于次要因素。该设置会显著破坏牙根、下颌管、小骨质缺损和病灶边界等细结构，也缺少正式 3D 医学分割系统中关键的 patch-based 高分辨率训练、前景过采样、deep supervision、滑窗推理和后处理。

后续基础模型设计应分为两层：

- 工程可靠基线：以 nnU-Net v2 3D fullres / ResEnc 为正式基线，优先复现牙科 CBCT 领域已有强证据。
- 项目自研候选：在同一训练范式下实现轻量 3D Residual ConvNeXt / UXNet 风格模型，作为可控、可替换、可消融的项目模型。

`64x64x64` benchmark 继续保留为 smoke、loss/采样验证和候选模型初筛工具，不再作为正式性能判断依据。

## 当前异常来源

### 1. 分辨率压缩过重

当前本地缓存均为 `64x64x64`：

| 数据集 | 当前任务 | 样本数 | 缓存形状 | 前景比例示例 |
|---|---|---:|---|---:|
| D024 DentVoxel | jaw ROI | 100 | `64x64x64` | 约 8.7%-9.6% |
| D025 lesion CBCT | lesion ROI | 262 | `64x64x64` | 约 0.28%-1.35% |
| D036 ToothFairy2 | anatomy ROI | 480 | `64x64x64` | 约 4.2%-8.6% |

牙科 CBCT 的有效结构尺度很细。下颌管、牙槽骨边缘、根尖区域、局灶性骨质改变被强制缩放到 64 体素立方后，空间信息损失会直接反映为低 Dice、低 clDice 和边界断裂。

### 2. 当前 benchmark 仍属于快速验证系统

现有 `scripts/benchmark_public_cbct_segmentation_models.py` 已修复训练循环、loss 和采样诊断，但仍有明确限制：

- 输入来自全体积 64³ NPZ 缓存。
- 训练预算为几十到几百 batch，用于快速定位。
- 多数前沿模型是 proxy 或 tiny 实现，不能等同官方论文实现。
- 缺少 nnU-Net 式 patch planning、deep supervision、多尺度标签监督、滑窗融合和后处理。

因此，该 benchmark 可用于判断“模型能否学习”和“loss/采样方向是否有效”，不能与 ToothFairy2、DentalSegmentator 或 MedNeXt 论文指标直接比较。

## 参考证据

### ToothFairy2 / Scaling nnU-Net for CBCT Segmentation

参考：

- https://arxiv.org/html/2411.17213v2
- 本地快照：`research/model-snapshots/code/nnunet/documentation/competitions/Toothfairy2/readme.md`

关键做法：

- 使用 nnU-Net ResEnc L。
- patch size 放大到 `160x320x320`。
- 禁用 left/right mirroring，以保护牙科结构的左右语义。
- 训练 1500 epochs。
- 使用 CTNormalization。
- 使用更深 residual encoder。
- 两模型 ensemble。
- class-wise volume cutoff 后处理。

公开结果显示，该方案在 ToothFairy2 中达到 mean Dice `0.9253`、HD95 `18.472`。重要信息是：性能来自高分辨率 patch 训练和完整 nnU-Net 系统，单独更换网络名称无法复现这类结果。

### nnU-Net v2 默认训练范式

本地 nnU-Net 快照显示：

- `oversample_foreground_percent = 0.33`
- `num_iterations_per_epoch = 250`
- `num_epochs = 1000`
- loss 使用 `DC_and_CE_loss`
- deep supervision 使用 `DeepSupervisionWrapper`
- 推理使用 sliding-window logits 融合和 Gaussian weighting

这些机制正是医学 3D 分割在大体积、小前景、显存受限条件下稳定工作的基础。

### DentalSegmentator

参考：

- https://zenodo.org/records/10829675
- https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools

关键做法：

- 基于 nnU-Net v2.2。
- 使用 470 例多机构 dento-maxillo-facial CT/CBCT 训练。
- 输出牙颌面关键结构，包括上颌/颅底、下颌骨、上下牙、下颌管等。
- 已有 3D Slicer 扩展和公开预训练模型。

对本项目的启示是：可先稳定做 5 类解剖先验，随后再推进所有 39/42 类完整标签和病灶任务。

### MedNeXt

参考：

- https://github.com/MIC-DKFZ/MedNeXt
- https://arxiv.org/html/2303.09975v5

关键做法：

- fully ConvNeXt 3D encoder-decoder。
- residual inverted bottleneck。
- kernel size 常见为 3/5/7。
- deep supervision 可用。
- 训练框架沿用 nnU-Net schedule：1000 epochs、250 batches/epoch、patch `128x128x128`、batch size 2、滑窗推理。

对本项目的启示是：ConvNeXt 后设计应作为 nnU-Net 风格训练系统里的模型替换项，脱离 patch training 的 64³ 全体积实验只能用于轻量筛选。

### U-Mamba / SegMamba / 3D UX-Net

参考：

- https://u-mamba.github.io
- https://github.com/MASILab/3DUX-Net

关键做法：

- U-Mamba 将 Mamba block 放在 bottleneck 或 encoder，强调 CNN 局部特征与长程依赖结合。
- 3D UX-Net 使用 large-kernel depthwise convolution 模拟层级 transformer 的大感受野。
- 这类模型仍应放入完整 3D 分割训练系统中验证。

对本项目的启示是：Mamba/large-kernel 结构可以作为第二阶段增强模块，但基础系统先要正确处理分辨率、patch、采样、loss、推理和评估。

## 基础模型设计

### B0：正式可靠基线

名称：`OsteoVision-nnUNet-ResEnc`

用途：

- D024/D036 颌骨、牙齿、下颌管、上颌窦等解剖结构分割。
- 为术中荧光分析提供术前解剖 ROI 和风险区先验。

训练方案：

- 框架：nnU-Net v2。
- 配置：3D fullres，优先 ResEnc S/M，显存允许再试 L。
- 输入：本地项目内高分辨率派生数据，禁止依赖 D 盘在线。
- normalization：CBCT 按 CTNormalization 路线。
- augmentation：禁用 left/right mirroring 或仅保留不破坏左右语义的轴向增强。
- loss：Dice + CE。
- sampler：foreground oversampling，起点 0.33。
- inference：sliding-window + Gaussian weighting + TTA。
- postprocess：按类别连通域、体积阈值和解剖合理性规则做验证集优化。

8GB GPU 约束下的降级：

- 先用 ResEnc S/M。
- patch 从 `96x128x128` 或 `96x160x160` 起步。
- batch size 1。
- AMP 开启。
- 必要时使用 gradient accumulation 和 checkpointing。

### B1：五类解剖先验任务

名称：`OsteoVision-DentalPrior-5`

标签建议：

| ID | 类别 |
|---:|---|
| 0 | background |
| 1 | maxilla / upper skull |
| 2 | mandible |
| 3 | upper teeth |
| 4 | lower teeth |
| 5 | mandibular canal |

用途：

- 作为比赛和演示更稳定的解剖先验。
- 先获得可解释的大结构 ROI。
- 降低 D036 42 类、D024 39 类从零训练的类别稀疏问题。

评估：

- mean Dice。
- per-class Dice。
- HD95 / NSD。
- mandibular canal 单独报告 clDice、HD95 和断裂率。

### B2：项目自研候选模型

名称：`OsteoSeg-ResUX-Lite`

定位：

- 作为项目可控模型，吸收 MedNeXt 和 3D UX-Net 的设计思想。
- 训练流程完全对齐 B0 的 patch-based 系统。

结构草案：

```text
Input CBCT patch
  -> Conv stem 3x3x3
  -> Residual encoder stage 1, channels 24/32
  -> Downsample
  -> Residual ConvNeXt / large-kernel stage 2
  -> Downsample
  -> Residual ConvNeXt / large-kernel stage 3
  -> Downsample
  -> Bottleneck: large-kernel depthwise block, optional Mamba block later
  -> Decoder with skip connections
  -> Deep supervision heads at 1/2, 1/4, 1/8 scale
  -> Final segmentation logits
```

关键约束：

- 3D patch 输入，初始推荐 `96x128x128`。
- large-kernel depthwise convolution 从 kernel 5 或 7 起步。
- residual inverted bottleneck expansion ratio 2 或 4。
- InstanceNorm3d / GroupNorm，避免小 batch 下 BatchNorm 不稳定。
- deep supervision 默认开启。
- 输出头按任务配置决定类别数，不在模型代码中写死数据集标签。

第一版不要直接加入复杂 Mamba。等 B0 和 B2 plain 版本稳定后，再加入 `B2-MambaBot` 消融。

### B3：病灶/坏死骨代理分割头

名称：`OsteoVision-LesionCascade`

用途：

- D025 lesion mask 代理任务。
- 后续若获得真实术中标注，可迁移为疑似坏死骨/低灌注区域辅助提示。

推荐流程：

1. 使用 B0/B1 解剖模型得到 mandible/maxilla ROI。
2. 在 ROI 内裁剪高分辨率 patch。
3. 使用二分类 lesion head。
4. 训练 loss 使用 Dice+Focal 或 Tversky+Focal。
5. 采样使用 positive patch oversampling，起点 0.5-0.75。
6. 推理后做 threshold sweep 和 connected component 过滤。

目标口径：

- 优先保证 sensitivity 和稳定非零 Dice。
- precision 通过阈值、连通域、ROI 限制逐步提升。
- 不把 D025 指标表述为颌骨骨髓炎临床诊断性能。

## 数据与训练方案

### 解剖线

数据：

- D024：DentVoxel，先做 jaw ROI / 5 类先验，再做 full-39。
- D036：ToothFairy2，先做合并类，再做 full-42。

训练：

- 从本地 NIfTI 或 nnU-Net 派生数据生成高分辨率 patch。
- 保留原始 spacing 信息。
- patch sampling 包含前景类中心采样。
- 小结构类使用 per-class Dice、clDice、HD95 单独评估。

### 病灶线

数据：

- D025：lesion mask 代理数据，只作为 CBCT lesion 分割训练。

训练：

- 先做 ROI crop，避免整例背景主导。
- 使用 positive/negative patch 混合采样。
- loss 使用 Dice+Focal 或 Tversky+Focal。
- 指标固定报告 Dice、IoU、sensitivity、precision、case-level detection、volume FP/FN。

## 实验验收标准

### 第一阶段：训练系统正确性

- 单例 overfit：D024/D036/D025 各 1-2 例，Dice 必须明显上升。
- patch loader：能输出高分辨率 patch，包含 spacing、case_id、label set。
- forward/backward：B0/B2/B3 至少完成一次。
- 推理：完整体积 sliding-window 输出能还原到原尺寸。

### 第二阶段：小样本高分辨率验证

- D024 jaw/5 类任务：目标先达到 Dice > 0.75。
- D036 合并类任务：目标先达到 Dice > 0.55-0.70，随后逐步上 full-42。
- D025 lesion：目标先达到非零 Dice 和稳定 sensitivity，避免全背景或极端过分割。

### 第三阶段：正式验证

- 5-fold cross validation。
- 保存 softmax probability 用于 ensemble 和不确定性分析。
- 报告 Dice、IoU、HD95、NSD、clDice。
- 分组报告 jaw、teeth、canal、sinus、lesion。

## 后续实现建议

优先级顺序：

1. 新增高分辨率 patch dataset 和 loader，保留 64³ benchmark 只做 smoke。
2. 跑通 D024/D036 5 类解剖先验任务。
3. 将 nnU-Net v2 ResEnc 作为正式 B0 基线。
4. 实现 `OsteoSeg-ResUX-Lite`，并用同一数据/训练系统对照。
5. 对 D025 实现 ROI-crop lesion cascade。
6. 再考虑 U-Mamba bottleneck、MedNeXt、ensemble 权重搜索。

## 医学边界

本设计服务于研发验证版平台。D024/D036 是解剖结构分割数据，D025 是 CBCT lesion mask 代理数据，均不等同术中 ICG 荧光标注或真实颌骨骨髓炎临床结局。模型输出应表述为术中参考信号、风险提示和医生复核辅助。
