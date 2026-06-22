# 公开 CBCT 三数据集 Dice 提升定位报告（中文）

## 定位

本报告记录对低 Dice 问题的工程修复与快速验证。结果仍来自 64³ 本地 NPZ 缓存，用于定位训练链路、loss 和采样策略是否有效，不代表正式高分辨率模型性能。

医学边界：D024 和 D036 是解剖结构分割数据；D025 是 CBCT lesion-mask 代理任务。三者都不是术中 ICG 荧光数据，不能表述为颌骨骨髓炎临床诊断性能。

## 已修复的问题

- 训练循环已改为跨 epoch 跑满 `max_train_batches`，并记录 `epochs_seen` 与 `samples_seen`。
- 新增 `--loss auto|ce|dice_ce|dice_focal|tversky_focal`；`auto` 下解剖线使用 `dice_ce`，D025 lesion 使用 `dice_focal`。
- 新增 `--class-weighting none|inverse|sqrt_inverse`，默认 `sqrt_inverse`，用于缓解 D024 下颌管和 D036 稀疏类别。
- 新增 `--foreground-oversample-ratio`，当前基于 64³ 全体积缓存的 foreground fraction 做病例级加权重采样。
- 新增 `--overfit-cases`、`--target-labels` 和诊断字段：前景比例、预测前景比例、目标前景比例。

## 关键验证结果

### Sanity Overfit

运行 ID：`20260617T132107Z`

命令设置：`SegResNetDS`，每个数据集 1 例 overfit，30 batch，`loss=auto`，`class_weighting=sqrt_inverse`。

| 数据集 | Loss | Dice | Target fg | Pred fg | 结论 |
|---|---|---:|---:|---:|---|
| D024 | dice_ce | 0.3644 | 0.0866 | 0.0643 | 能学习，不是标签或通道完全错误 |
| D036 | dice_ce | 0.1014 | 0.0862 | 0.0244 | 能学习，但类别稀疏仍明显困难 |
| D025 | dice_focal | 0.6127 | 0.0121 | 0.0273 | 不再全背景，loss 方向有效 |

D025 同样 1 例 overfit 的 CE 对照运行 ID 为 `20260617T132235Z`，Dice 为 0.5441。说明模型本身能学，`dice_focal` 在该 sanity 条件下更强。

### D025 Lesion 小预算验证

运行 ID：`20260617T132359Z`

命令设置：80 batch，20 个验证病例，`loss=auto`，`class_weighting=sqrt_inverse`，`foreground_oversample_ratio=0.75`。

| 模型 | Dice | IoU | Sensitivity | Precision | Target fg | Pred fg | 判断 |
|---|---:|---:|---:|---:|---:|---:|---|
| `uxnet_large_kernel_proxy` | 0.1450 | 0.0833 | 0.9042 | 0.0801 | 0.0056 | 0.0626 | 当前 D025 最有效方向 |
| `monai_segresnetds` | 0.1192 | 0.0711 | 0.2653 | 0.1677 | 0.0056 | 0.0088 | 更保守，precision 更高 |
| `monai_segresnet` | 0.0186 | 0.0094 | 1.0000 | 0.0094 | 0.0056 | 0.5896 | 过分割严重 |

相比旧结果，D025 已从 0 或约 0.02 Dice 提升到 0.145。真实提升方向是 lesion 专用 loss + 前景加权采样 + 大核/SegResNetDS 候选，而不是继续堆未调参模型。

### Anatomy 小预算验证

运行 ID：`20260617T132518Z`

命令设置：160 batch，20 个验证病例，`loss=auto`，`class_weighting=sqrt_inverse`。

| 数据集 | 模型 | Dice | IoU | Target fg | Pred fg | 判断 |
|---|---|---:|---:|---:|---:|---|
| D024 | `monai_swinunetr_tiny` | 0.6395 | 0.5403 | 0.0934 | 0.1068 | 当前 D024 最强 |
| D024 | `monai_segresnetds` | 0.6073 | 0.4893 | 0.0934 | 0.1075 | 资源更稳 |
| D036 | `monai_segresnetds` | 0.1642 | 0.1068 | 0.0846 | 0.1071 | 当前 D036 最强 |
| D036 | `monai_swinunetr_tiny` | 0.0812 | 0.0563 | 0.0846 | 0.1002 | 落后于 SegResNetDS |

D024 从旧 0.36 左右提升到 0.61-0.64；D036 的 SegResNetDS 在更短 160 batch 下达到 0.1642，高于旧 384 batch CE 的 0.1313。解剖线真实提升方向是 Dice+CE + sqrt inverse 类权重，首选 SegResNetDS/SwinUNETR Tiny。

## Smoke 与回归

- 运行 ID：`20260617T132823Z`
- 三数据集 × 6 个候选模型 forward/backward smoke：18/18 completed。
- 新增单测覆盖训练循环跨 epoch、loss 数值稳定、foreground sampling 权重和新增结果 schema。

## 下一步

1. D025 优先继续 `uxnet_large_kernel_proxy` 与 `monai_segresnetds`，增加 threshold sweep、connected-component 过滤和 Dice/Tversky/Focal 消融。
2. D024/D036 继续 `monai_segresnetds` 与 `monai_swinunetr_tiny`，下一轮比较 64³、96³ 和 128³ 小样本。
3. 对 D024 下颌管和 D036 稀疏标签单独报告 per-label Dice，避免 mean Dice 掩盖小结构。
4. nnU-Net v2 仍走外部 nnU-Net 链路，用作正式高分辨率基线。

## 产物

- Sanity overfit JSON：`artifacts/runs/public_cbct_segmentation_benchmark/20260617T132107Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- D025 小预算验证 JSON：`artifacts/runs/public_cbct_segmentation_benchmark/20260617T132359Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- Anatomy 小预算验证 JSON：`artifacts/runs/public_cbct_segmentation_benchmark/20260617T132518Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- 6 模型 smoke JSON：`artifacts/runs/public_cbct_segmentation_benchmark/20260617T132823Z/public_cbct_3dataset_segmentation_benchmark_summary.json`
- 英文报告：`research/reports/modeling/public_cbct_3dataset_segmentation_benchmark_en.md`
