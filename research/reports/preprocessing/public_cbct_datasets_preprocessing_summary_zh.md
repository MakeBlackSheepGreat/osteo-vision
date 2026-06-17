# 公开 CBCT 数据集解压与预处理汇总（中文）

## 处理范围

本次处理 D024 DentVoxel、D025 DOLCHID、D036 ToothFairy2 三个本地数据集。原始 ZIP 与原始元数据文件只读取和解压，不在 raw/ 中做改写；所有派生清单、质检、预览和报告写入 derived/ 与 research/reports/preprocessing/。

## 汇总

| Dataset | Status | Cases | Manifest | Report |
|---|---|---:|---|---|
| d024 | processed | 100 | `research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_manifest.csv` | `research\reports\preprocessing\d024_dentvoxel_preprocessing_zh.md` |
| d025 | processed | 262 | `research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_manifest.csv` | `research\reports\preprocessing\d025_dolchid_preprocessing_zh.md` |
| d036 | processed | 480 | `research\datasets\public-candidates\d036_toothfairy2\derived\manifests\d036_toothfairy2_manifest.csv` | `research\reports\preprocessing\d036_toothfairy2_preprocessing_zh.md` |

## 下一步

1. D025 优先转换为二值病灶分割任务，先做 64³/128³ 低分辨率 smoke。
2. D036 与 D024 合并设计 jaw-roi 结构分割标签映射，服务术前 ROI。
3. 所有训练产物继续放本地 ignored 目录，长期证据只保留报告和必要预览图。
