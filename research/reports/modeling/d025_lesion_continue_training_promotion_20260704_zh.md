# D025 代理分割模型续训与提升记录

## 结论

已在原 `d025_lesion_smoke.pt` 主线 checkpoint 上继续训练 1500 batch，并将指标更好的续训候选提升为本地主线 checkpoint。该提升只针对 D025 CBCT lesion ROI 64³ 代理数据有效，不代表真实术中 ICG 颌骨骨髓炎目标域性能。

## 训练设置

- 续训来源：`artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- 续训候选：`artifacts/checkpoints/osteo_vision/d025_candidate_continue_20260704/d025_lesion_continue_1500.pt`
- 当前主线：`artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- 旧主线备份：`artifacts/checkpoints/osteo_vision/d025_candidate_base12/d025_lesion_smoke_before_continue_20260704.pt`
- 训练数据：D025 DOLCHID CBCT lesion ROI 64³ cache。
- 训练病例：209；验证病例：53。
- 本轮续训 batch：1500；累计训练 batch：4500。
- 学习率：0.0002；batch size：2；设备：CUDA。

## 指标对比

| 模型 | 训练 batch | 最优阈值 | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 续训 ConvNeXt-style 主线 | 4500 | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.4797 | 0.6900 | 0.7238 | 已提升 |
| 旧 ConvNeXt-style 主线 | 3000 | 0.20 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 | 已备份 |
| MONAI SegResNetDS 对照 | 3000 | 0.20 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 | 不接主线 |

## 判断

续训候选在 Mean Dice、Mean IoU、Mean HD95、Mean NSD、敏感性和精确率上均优于旧 ConvNeXt-style 主线，因此本地提升是合理的。SegResNetDS 的 HD95 仍有对照价值，但 Dice/IoU 和敏感性不足，继续不接入 `configs/inference/osteo_vision.yml`。

## 边界

- 当前模型仍是 CBCT lesion ROI 代理分割模型，不是术中 ICG 视频/JPEG 模型。
- 当前验证集来自 D025 代理数据，不能外推为临床诊断能力。
- 比赛演示中仍必须保留医生复核边界和平台安全边界免责声明。

## 后续

1. 保持续训后的 `d025_lesion_smoke.pt` 作为本地比赛闭环主线 checkpoint。
2. 下一阶段优先准备 nnU-Net v2/DynUNet 高分辨率或 patch 级训练。
3. 若继续在 64³ D025 缓存上训练，应设置独立候选输出，先评估再决定是否提升。
