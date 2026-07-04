# D025 CBCT 代理分割模型评估报告

## 定位

本报告评估当前工程可用的 D025 CBCT lesion ROI 代理 checkpoint。它用于补齐模型闭环的可审计证据，不能代表真实术中 ICG 颌骨骨髓炎视频或图片性能。

## 输入与模型

- Manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv`
- Checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\d025_lesion_smoke.pt`
- Checkpoint SHA256：`56473aae9980da7ecfe2e720b8522a9ad5a6a825f00a314818fef07b9b15920d`
- 评估 split：`val`；病例数：53。
- 设备：`cuda`；PyTorch：`2.11.0+cu128`。

## 最优阈值摘要

- 最优阈值：0.2000
- Mean Dice：0.6266
- Mean IoU：0.5183
- Mean HD95：17.6413
- Mean NSD：0.4227
- Lesion sensitivity：0.6756
- Lesion precision：0.6932

## 阈值扫描

| Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision |
|---:|---:|---:|---:|---:|---:|---:|
| 0.2000 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 |
| 0.3000 | 0.6224 | 0.5164 | 16.7775 | 0.4354 | 0.6613 | 0.6998 |
| 0.4000 | 0.6219 | 0.5179 | 14.5247 | 0.4432 | 0.6508 | 0.7135 |
| 0.5000 | 0.6180 | 0.5157 | 14.1909 | 0.4451 | 0.6397 | 0.7240 |
| 0.6000 | 0.6134 | 0.5135 | 15.4929 | 0.4436 | 0.6292 | 0.7279 |
| 0.7000 | 0.6103 | 0.5121 | 14.9053 | 0.4442 | 0.6193 | 0.7385 |
| 0.8000 | 0.6050 | 0.5083 | 15.5881 | 0.4430 | 0.6066 | 0.7477 |

## 低分样本

- 病例 `DC_9` (DC): Dice=0.0000, IoU=0.0000, HD95=39.2162; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_9_failure_preview.png`
- 病例 `RC_11` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_11_failure_preview.png`
- 病例 `RC_3` (RC): Dice=0.0000, IoU=0.0000, HD95=43.0093; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_3_failure_preview.png`
- 病例 `RC_52` (RC): Dice=0.0000, IoU=0.0000, HD95=N/A; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_52_failure_preview.png`
- 病例 `KCOT_68` (KCOT): Dice=0.0055, IoU=0.0027, HD95=55.8689; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\KCOT_68_failure_preview.png`
- 病例 `DC_35` (DC): Dice=0.0220, IoU=0.0111, HD95=10.5080; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_35_failure_preview.png`
- 病例 `RC_25` (RC): Dice=0.0600, IoU=0.0309, HD95=61.1381; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\RC_25_failure_preview.png`
- 病例 `DC_26` (DC): Dice=0.0756, IoU=0.0393, HD95=81.4045; preview=`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z\DC_26_failure_preview.png`

## 输出文件

- JSON：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704.json`
- CSV：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\d025_proxy_model_evaluation_20260704_per_case.csv`
- 预览图目录：`C:\Users\876762330\Desktop\projects\osteo-vision\research\reports\modeling\assets\d025_proxy_eval_20260704T091114Z`

## 医学边界

D025 CBCT lesion ROI proxy evaluation only; not target-domain intraoperative ICG jaw osteomyelitis performance.
