# D024 DentVoxel nnU-Net 1-Epoch Smoke Test 结果报告

生成时间：2026-06-15

## 1. 运行目标

本轮用于验证 D024 DentVoxel jaw-roi 任务能否完成 nnU-Net v2 的完整链路：数据转换、plan/preprocess、训练、验证预测、指标汇总与可视化检查。

本轮定位为 smoke test，只训练 1 个 epoch，结果不能作为正式模型性能。

## 2. 数据与任务

- 数据集：D024 DentVoxel CBCT
- nnU-Net 数据集：`Dataset124_DentVoxelJawROI`
- 训练/验证划分：fold 0，80 例训练，20 例验证
- spacing：0.3 mm isotropic
- 输入模态：CBCT，nnU-Net 中按 CTNormalization 处理
- 标签：
  - 0 background
  - 1 maxilla
  - 2 mandible
  - 3 right mandibular canal
  - 4 left mandibular canal
  - 5 right maxillary sinus
  - 6 left maxillary sinus

## 3. 模型与配置

- Trainer：`nnUNetTrainer_1epoch`
- Configuration：`3d_fullres`
- Network：PlainConvUNet
- Patch size：`[112, 160, 128]`
- Batch size：2
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- PyTorch：2.11.0+cu128
- CUDA device：`cuda:0`

训练日志：

`research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results/Dataset124_DentVoxelJawROI/nnUNetTrainer_1epoch__nnUNetPlans__3d_fullres/fold_0/training_log_2026_6_15_19_54_09.txt`

验证摘要：

`research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_results/Dataset124_DentVoxelJawROI/nnUNetTrainer_1epoch__nnUNetPlans__3d_fullres/fold_0/validation/summary.json`

## 4. 时间与资源

- 单 epoch 训练时间：145.54 s
- 训练阶段：约 2 分 26 秒
- 20 例验证预测：约 36 分 37 秒
- 本轮总耗时：约 39 分钟
- 验证目录文件体积：
  - `.nii.gz` 预测：20 个，约 0.02 GB
  - `.pkl`：20 个，约 0.06 GB
  - `.npz` softmax：20 个，约 30.49 GB

说明：本轮使用了 `--npz`，每例 softmax 约 1.5 GB。后续普通 smoke test 建议取消 `--npz`，仅在 ensemble、uncertainty 或权重搜索阶段保存概率图。

## 5. 结果指标

Foreground mean：

- Dice：0.1208
- IoU：0.0763

| Label | Structure | Dice | IoU | Mean reference voxels | Mean predicted voxels |
|---:|---|---:|---:|---:|---:|
| 1 | maxilla | 0.2400 | 0.1366 | 3,060,543 | 1,064,004 |
| 2 | mandible | 0.4846 | 0.3211 | 2,173,222 | 4,368,167 |
| 3 | right mandibular canal | 0.0000 | 0.0000 | 13,399 | 0 |
| 4 | left mandibular canal | 0.0000 | 0.0000 | 12,929 | 0 |
| 5 | right maxillary sinus | 0.0000 | 0.0000 | 567,380 | 0 |
| 6 | left maxillary sinus | 0.0000 | 0.0000 | 577,956 | 0 |

训练日志中的 pseudo Dice：

- maxilla：0.2461
- mandible：0.5871
- right mandibular canal：0.0000
- left mandibular canal：0.0000
- right maxillary sinus：0.0000
- left maxillary sinus：0.0000

## 6. 可视化检查

生成了 3 个验证病例预览：

- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0001.png`
- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0059.png`
- `research/reports/modeling/assets/d024_nnunet_1epoch_preview_d024_0101.png`

观察结论：

- 预测标签仅包含 `[0, 1, 2]`。
- 真值包含 `[0, 1, 2, 3, 4, 5, 6]`。
- 模型已经开始响应上颌骨和下颌骨的大体骨性区域。
- 管状结构和上颌窦在 1 个 epoch 后没有预测输出。
- 预测存在明显粗糙边界与类别混淆，符合 1-epoch smoke test 的预期。

## 7. 环境与测试

运行环境检查：

```text
python check_env.py
failures: []
warnings: []
```

项目测试：

```text
python -m pytest tests/unit tests/smoke
46 passed, 5 warnings
```

测试通过。当前警告来自 Pillow `mode` 参数弃用，预计 Pillow 13 后需要更新相关图像保存代码。

## 8. 判断

本轮成功证明：

- D024 jaw-roi 转换后的 nnU-Net 数据结构有效。
- plan/preprocess 可完整执行。
- 8GB RTX 5060 Laptop GPU 可以跑通 3D fullres 训练。
- fold 0 训练、验证、summary 输出均正常。

当前不足：

- 1 epoch 指标偏低，细小结构完全未学习。
- 验证推理比训练更耗时，保存 `.npz` 显著增加磁盘占用。
- 目前使用默认 mirroring，正式牙科左右结构实验应使用 no-mirroring 策略。

## 9. 下一步

建议按以下顺序推进：

1. 清理或暂存本轮 `.npz` softmax 文件，释放约 30.49 GB。
2. 运行 5-epoch smoke test，取消 `--npz`，验证 loss 和大结构 Dice 是否持续改善。
3. 进入正式 baseline 前切换 no-mirroring trainer。
4. 对下颌管和上颌窦单独统计 recall、connected components 和 clDice。
5. 在 baseline 稳定后再开始 ResEnc、MedNeXt、U-Mamba 对比。

