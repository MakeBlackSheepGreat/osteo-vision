# D025 DOLCHID 数据预处理报告（中文）

## 数据来源与目录

- 数据集：DOLCHID
- 来源 ZIP：`research\datasets\public-candidates\d025_lesion_cbct\DOLCHID.zip`
- 原始解压目录：`research\datasets\public-candidates\d025_lesion_cbct\raw\DOLCHID`
- 派生产物目录：`research\datasets\public-candidates\d025_lesion_cbct\derived`
- 元数据策略：No original metadata file was found in the archive; generated metadata is written only under derived/.

## 解压结果

- 新解压文件数：None
- 已存在跳过文件数：None
- 不安全路径条目数：0

## 配对检查

- 病例总数：262
- 完整配对病例：262
- 子目录文件数：`{'cbct_image': 262, 'cbct_label': 262, 'hist_image': 262, 'hist_label': 262}`
- 诊断前缀分布：`{'AME': 72, 'DC': 44, 'KCOT': 92, 'RC': 54}`

## 质量检查

- 质检行数：262
- 状态分布：`{'ok': 262}`
- CBCT shape 分布：`{'512x512x507': 14, '512x512x508': 24, '512x512x505': 30, '512x512x511': 50, '512x512x509': 82, '502x462x489': 1, '505x462x483': 1, '500x462x475': 1, '512x512x510': 10, '497x463x210': 1, '512x512x480': 2, '505x462x499': 1, '527x513x489': 1, '513x457x440': 1, '511x463x396': 1, '492x404x428': 1, '508x463x483': 1, '512x512x410': 4, '462x462x367': 1, '463x463x340': 1, '510x500x483': 1, '512x521x515': 1, '512x435x422': 1, '513x462x464': 1, '510x463x389': 1, '512x512x494': 1, '509x462x484': 1, '512x462x483': 1, '512x462x442': 1, '480x487x483': 1, '462x462x354': 1, '512x512x409': 2, '513x512x521': 1, '462x484x464': 1, '512x512x472': 1, '513x512x510': 1, '485x475x426': 1, '512x513x505': 1, '513x513x510': 1, '509x463x433': 1, '505x462x482': 1, '462x462x424': 1, '512x512x383': 1, '507x462x478': 1, '502x462x398': 1, '507x462x412': 1, '513x494x409': 1, '505x461x364': 1, '462x462x338': 1, '489x463x409': 1, '509x462x480': 1, '512x504x472': 1, '510x494x473': 1}`
- CBCT spacing 分布：`{'0.3x0.3x0.3': 240, '0.3x0.3x0.300002': 2, '0.3x0.3x0.300004': 1, '0.3x0.3x0.299999': 7, '0.3x0.3x0.300685': 1, '0.3x0.3x0.300001': 8, '0.3x0.3x0.299998': 3}`
- CBCT 标签值出现统计：`{'0': 262, '1': 262}`
- 病理标签值出现统计：`{'0': 233, '255': 262}`

## 预处理产物

- manifest：`research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_manifest.csv`
- 质检 CSV：`research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_quality_check.csv`
- 诊断组清单：`research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_diagnosis_inventory.csv`
- 统计 JSON：`research\datasets\public-candidates\d025_lesion_cbct\derived\manifests\d025_dolchid_preprocessing_summary.json`
- 预览图病例数：5

## 项目用途与限制

DOLCHID 是目前最接近赛点二的数据，可用于 CBCT 病灶区域分割和 ROI 先验探索。它仍不是术中 ICG 荧光数据；诊断组含义需要进一步核对数据来源文档，不能直接包装成颌骨骨髓炎临床诊断性能。
