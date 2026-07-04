# D025 CBCT 代理分割模型评估报告

## 定位

本报告评估当前工程可用的 D025 CBCT lesion ROI 代理 checkpoint。它用于补齐模型闭环的可审计证据，不能代表真实术中 ICG 颌骨骨髓炎视频或图片性能。

## 输入与模型

- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_candidate_continue_20260704\d025_lesion_continue_1500.pt`
- Checkpoint SHA256：`7706b838a4b180753d36c999b3735a7f51a906e41ae3fdb1b2427cd0740ec802`
- 评估 split：`val`；病例数：53。
- 设备：`cuda`；PyTorch：`2.11.0+cu128`。

## 最优阈值摘要

- 最优阈值：0.2000
- Mean Dice：0.6567
- Mean IoU：0.5553
- Mean HD95：15.2370
- Mean NSD：0.4797
- Lesion sensitivity：0.6900
- Lesion precision：0.7238

## 阈值扫描

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2000 | 0.6567 | 0.5553 | 15.2370 | 0.4797 | 0.6900 | 0.7238 |
| 0.3000 | 0.6550 | 0.5556 | 13.6012 | 0.4813 | 0.6797 | 0.7364 |
| 0.4000 | 0.6521 | 0.5536 | 13.5532 | 0.4826 | 0.6695 | 0.7440 |
| 0.5000 | 0.6484 | 0.5506 | 13.5314 | 0.4912 | 0.6599 | 0.7454 |
| 0.6000 | 0.6452 | 0.5488 | 13.0859 | 0.4912 | 0.6518 | 0.7512 |
| 0.7000 | 0.6433 | 0.5474 | 11.4526 | 0.5115 | 0.6441 | 0.7920 |
| 0.8000 | 0.6386 | 0.5437 | 11.3593 | 0.5079 | 0.6329 | 0.8002 |

## 低分样本

- 病例 `DC_9` (DC): Dice=0.0000, IoU=0.0000, HD95=37.8490; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\DC_9_failure_preview.png`
- 病例 `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\RC_11_failure_preview.png`
- 病例 `RC_25` (RC): Dice=0.0000, IoU=0.0000, HD95=72.6076; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\RC_25_failure_preview.png`
- 病例 `RC_3` (RC): Dice=0.0000, IoU=0.0000, HD95=29.3383; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\RC_3_failure_preview.png`
- 病例 `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\RC_52_failure_preview.png`
- 病例 `KCOT_68` (KCOT): Dice=0.0198, IoU=0.0100, HD95=52.9394; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\KCOT_68_failure_preview.png`
- 病例 `DC_35` (DC): Dice=0.0851, IoU=0.0444, HD95=9.0389; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\DC_35_failure_preview.png`
- 病例 `DC_26` (DC): Dice=0.0910, IoU=0.0477, HD95=80.7613; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z\DC_26_failure_preview.png`

## 输出文件

- JSON：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_continue_1500_eval_20260704\d025_proxy_model_evaluation_20260704.json`
- CSV：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_continue_1500_eval_20260704\d025_proxy_model_evaluation_20260704_per_case.csv`
- 预览图目录：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T114621Z`

## 医学边界

D025 CBCT lesion ROI proxy evaluation only; not target-domain intraoperative ICG jaw osteomyelitis performance.
