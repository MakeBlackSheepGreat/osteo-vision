# D024 DentVoxel 分割模型选型与调优报告（中文）

## 目标定位

当前训练目标是 D024 DentVoxel 牙科 CBCT 解剖结构分割，用于建立术前颌骨 ROI、下颌管保护区和后续颌骨骨髓炎病灶定位先验。D024 不包含骨髓炎、坏死骨或术中 ICG 荧光标签，因此本阶段不把它作为病灶分割数据集。

## 数据任务

第一任务是 `jaw-roi`：保留上颌骨、下颌骨、左右下颌管、左右上颌窦，重映射为 0-6 的少类标签。该任务用于优先跑通 8GB GPU 下的数据转换、训练、推理和评估闭环。

第二任务是 `full-39`：保留 DentVoxel 原始 0-38 标签，覆盖颌骨、牙齿、下颌管和上颌窦。该任务用于多结构分割和完整解剖先验。

## 模型路线

M0 使用 nnU-Net v2 3D fullres 自动规划，作为第一可靠基线。CBCT 通道在 `dataset.json` 中写为 `CT`，使 nnU-Net 使用 CT normalization；报告中仍标注来源模态为 CBCT。

M1 使用 nnU-Net ResEnc 小/中配置，并默认禁用左右镜像增强。牙位和左右下颌管具有明确 laterality，ToothFairy2 经验也显示禁用左右镜像是关键改进。

M2 使用 MedNeXt Small/Base，优先 3x3x3 kernel，再做 5x5x5 kernel 消融。MedNeXt 代表 ConvNeXt 后设计路线，适合验证 3D 大核卷积是否改善 CBCT 结构连续性。

M3 使用 U-Mamba bottleneck/encoder 版本，作为长程依赖建模实验。SegMamba 与自研 Mamba+ConvNeXt hybrid 暂列 M4，等 M0-M3 指标稳定后再进入。

## 指标与融合

基础指标固定为 Dice、IoU、HD95、NSD。下颌管等管状结构额外报告 clDice，用于观察断裂和拓扑连续性。第一阶段训练损失仍使用 Dice+CE，不急于加入 clDice/cbDice loss。

融合按三步推进：先做 5-fold softmax 概率平均和 TTA；再做 nnU-Net、MedNeXt、U-Mamba 的均权概率融合；最后在验证集上搜索全局权重或 per-class 权重，目标函数同时考虑 mean Dice、HD95 和下颌管 clDice。

## 实施产物

- 转换脚本：`scripts/convert_d024_to_nnunet.py`
- 标签分组与任务定义：`src/datasets/d024.py`
- 分割指标扩展：`src/metrics/segmentation.py`
- 概率融合工具：`src/models/ensembles.py`
- 报告目录：`research/reports/modeling/`

## 推荐命令

```powershell
conda activate osteo-vision
python scripts/convert_d024_to_nnunet.py --task jaw-roi
$env:nnUNet_raw='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_raw'
$env:nnUNet_preprocessed='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_preprocessed'
$env:nnUNet_results='research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results'
nnUNetv2_plan_and_preprocess -d 124 -c 3d_fullres --verify_dataset_integrity
nnUNetv2_train 124 3d_fullres 0 -tr nnUNetTrainerNoMirroring
```

## 证据依据

- ToothFairy2 冠军方案使用 nnU-Net ResEnc L，并强调禁用左右镜像、patch 调整、后处理和 ensemble。
- DentalSegmentator 使用公开 nnU-Net v2 权重完成牙颌面 CT/CBCT 五结构分割，证明 nnU-Net 在牙科 CBCT 场景的工程成熟度。
- MedNeXt 是成熟的 3D ConvNeXt 医学分割网络，适合作为 ConvNeXt 后设计对照。
- U-Mamba 是最接近 nnU-Net 生态的医学 Mamba 分割实现，优先级高于从零自研 Mamba-3 适配。

## 下一步

先完成 `jaw-roi` 的转换检查和一个小 split smoke 训练。若 8GB GPU 显存不足，优先降低 patch/batch，保留 NoMirroring 策略。拿到稳定 baseline 后，再进入 MedNeXt、U-Mamba 和融合实验。
