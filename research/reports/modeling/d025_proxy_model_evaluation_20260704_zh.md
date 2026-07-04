# D025 CBCT 代理分割模型评估报告

## 定位

本报告评估当前工程可用的 D025 CBCT lesion ROI 代理 checkpoint。它用于补齐模型闭环的可审计证据，不能代表真实术中 ICG 颌骨骨髓炎视频或图片性能。

## 输入与模型

- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Checkpoint SHA256：`c7a840a9266c6434a1fb96321bfa103dd0fd1011570c8a28e9ee5e38f16d97e1`
- 评估 split：`val`；病例数：53。
- 设备：`cuda`；PyTorch：`2.11.0+cu128`。

## 最优阈值摘要

- 最优阈值：0.6000
- Mean Dice：0.1363
- Mean IoU：0.0787
- Mean HD95：71.0074
- Mean NSD：0.0454
- Lesion sensitivity：0.4979
- Lesion precision：0.0837

## 阈值扫描

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.3000 | 0.0764 | 0.0411 | 78.8490 | 0.0199 | 0.8789 | 0.0412 |
| 0.4000 | 0.0903 | 0.0493 | 76.7364 | 0.0278 | 0.8032 | 0.0497 |
| 0.5000 | 0.1085 | 0.0604 | 74.4368 | 0.0359 | 0.6910 | 0.0615 |
| 0.6000 | 0.1363 | 0.0787 | 71.0074 | 0.0454 | 0.4979 | 0.0837 |
| 0.7000 | 0.0433 | 0.0240 | 46.8874 | 0.0082 | 0.0267 | 0.1425 |

## 低分样本

- 病例 `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=81.8805; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\RC_11_failure_preview.png`
- 病例 `RC_25` (RC): Dice=0.0000, IoU=0.0000, HD95=73.1764; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\RC_25_failure_preview.png`
- 病例 `RC_39` (RC): Dice=0.0000, IoU=0.0000, HD95=65.3198; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\RC_39_failure_preview.png`
- 病例 `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=74.6375; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\RC_52_failure_preview.png`
- 病例 `DC_9` (DC): Dice=0.0022, IoU=0.0011, HD95=77.9555; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\DC_9_failure_preview.png`
- 病例 `RC_34` (RC): Dice=0.0028, IoU=0.0014, HD95=82.5481; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z\RC_34_failure_preview.png`

## 输出文件

- JSON：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704.json`
- CSV：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704_per_case.csv`
- 预览图目录：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T011243Z`

## 医学边界

D025 CBCT lesion ROI proxy evaluation only; not target-domain intraoperative ICG jaw osteomyelitis performance.
