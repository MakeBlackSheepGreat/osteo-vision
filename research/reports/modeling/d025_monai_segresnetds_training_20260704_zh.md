# D025 MONAI SegResNetDS 代理分割训练报告

## 定位

本报告记录 MONAI SegResNetDS 在 D025 CBCT lesion ROI 64³ 缓存上的训练与验证。它是模型路线对比证据，不代表真实术中 ICG 颌骨骨髓炎视频或图片性能。

## 模型与训练

- 模型：`d025_monai_segresnetds_proxy_segmenter` / `monai_segresnetds`。
- 参数量：3,154,514。
- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- 训练病例：209；验证病例：53。
- 完成 batch：3000；epoch：29；batch size：2。
- 学习率：0.0006；正类权重：8.0；平均训练 loss：0.1982。
- 设备：`cuda`；GPU：`NVIDIA GeForce RTX 5060 Laptop GPU`；峰值显存 MB：578.0757。

## 最优阈值摘要

- 最优阈值：0.2000
- Mean Dice：0.5741
- Mean IoU：0.4766
- Mean HD95：13.8795
- Mean NSD：0.4101
- Lesion sensitivity：0.5721
- Lesion precision：0.7128

## 阈值扫描

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2000 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 |
| 0.3000 | 0.5710 | 0.4743 | 13.9005 | 0.4104 | 0.5611 | 0.7190 |
| 0.4000 | 0.5672 | 0.4710 | 13.8881 | 0.4100 | 0.5504 | 0.7295 |
| 0.5000 | 0.5629 | 0.4674 | 12.1757 | 0.4224 | 0.5414 | 0.7779 |
| 0.6000 | 0.5604 | 0.4653 | 12.0888 | 0.4199 | 0.5333 | 0.7864 |
| 0.7000 | 0.5560 | 0.4611 | 11.6675 | 0.4243 | 0.5237 | 0.7886 |
| 0.8000 | 0.5504 | 0.4562 | 11.6745 | 0.4177 | 0.5124 | 0.7974 |

## 与当前 ConvNeXt-style 代理模型对比

- ConvNeXt-style baseline：Dice=0.6266，IoU=0.5183，threshold=0.2000。
- SegResNetDS 本轮：Dice=0.5741，IoU=0.4766，threshold=0.2000。
- 差值：Dice -0.0525；IoU -0.0418。若未超过当前 baseline，不应替换主线 checkpoint。

## 低分样本

- 病例 `DC_30` (DC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_30_failure_preview.png`
- 病例 `DC_35` (DC): Dice=0.0000, IoU=0.0000, HD95=77.9190; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_35_failure_preview.png`
- 病例 `DC_9` (DC): Dice=0.0000, IoU=0.0000, HD95=37.2630; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\DC_9_failure_preview.png`
- 病例 `KCOT_40` (KCOT): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\KCOT_40_failure_preview.png`
- 病例 `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=34.4430; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_11_failure_preview.png`
- 病例 `RC_25` (RC): Dice=0.0000, IoU=0.0000, HD95=40.6295; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_25_failure_preview.png`
- 病例 `RC_3` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_3_failure_preview.png`
- 病例 `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z\RC_52_failure_preview.png`

## 输出文件

- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_monai_segresnetds.pt`
- JSON：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_monai_segresnetds_training_20260704.json`
- CSV：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_monai_segresnetds_training_20260704_per_case.csv`
- 预览图目录：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_monai_segresnetds_20260704T094021Z`

## 医学边界

D025 CBCT lesion ROI proxy training only; not target-domain intraoperative ICG jaw osteomyelitis performance.
