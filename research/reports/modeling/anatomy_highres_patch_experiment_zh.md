# 解剖高分辨率 Patch 分割实验报告（中文）

## 目标

本轮实验用于验证低 Dice 是否主要来自 `64x64x64` 全体积压缩。实验改用 `160x224x224` 高分辨率 patch cache，并将运行输入固定在项目本地 `derived/highres_patch/`。

医学边界：D024/D036 均为 CBCT 解剖结构分割数据，不包含术中 ICG 或颌骨骨髓炎临床结局标签。

## 数据缓存

| 数据集 | 病例数 | Patch 数 | 新生成 Patch | Manifest | 来源 |
| --- | ---: | ---: | ---: | --- | --- |
| D036 | 12 | 180 | 0 | `research\datasets\public-candidates\d036_toothfairy2\derived\highres_patch\anatomy4_160x224x224_class_cycle\d036_anatomy_highres_patch_manifest.csv` | project_raw |

## 实验设置

- 设备：`cuda`；GPU：`NVIDIA GeForce RTX 5060 Laptop GPU`
- 模型：`monai_segresnetds`
- 标签模式：`anatomy4`；采样策略：`class_cycle`
- Loss：`dice_focal`；类别权重：`sqrt_inverse`；AMP：`True`
- 训练 batch：`800`；验证 patch：`30`
- 采样说明：class-cycle patch centers over foreground and every target label.

## 结果

| 数据集 | 模型 | 状态 | Dice | IoU | Target FG | Pred FG | Train batches | Peak MB | Seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| D036 | monai_segresnetds | completed | 0.3860 | 0.3041 | 0.0583 | 0.0636 | 800 | 4419.7124 | 1261.3617 |

## 历史对照

| Run | 标签模式 | 数据集 | Patch | Loss | 采样 | Dice | IoU | Train batches | Peak MB | 关键类别 Dice |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `20260617T171733Z` |  | D024 | 128x160x160 |  |  | 0.2456 | 0.1809 | 80 | 1945.6973 | maxilla_or_upper_jawbone 0.5893, mandible_or_lower_jawbone 0.2843, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0000, left_maxillary_sinus 0.1089 |
| `20260617T153152Z` |  | D024 | 96x128x128 |  |  | 0.1995 | 0.1672 | 800 | 2185.0327 | maxilla_or_upper_jawbone 0.5372, mandible_or_lower_jawbone 0.2214, right_mandibular_canal 0.0063, left_mandibular_canal 0.0000, right_maxillary_sinus 0.1109, left_maxillary_sinus 0.0538 |
| `20260617T153152Z` |  | D024 | 96x128x128 |  |  | 0.1806 | 0.1466 | 800 | 953.7598 | maxilla_or_upper_jawbone 0.5792, mandible_or_lower_jawbone 0.1401, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0000, left_maxillary_sinus 0.2253 |
| `20260617T152538Z` |  | D024 | 96x128x128 |  |  | 0.1536 | 0.1139 | 300 | 953.7598 | maxilla_or_upper_jawbone 0.5311, mandible_or_lower_jawbone 0.2123, right_mandibular_canal 0.0562, left_mandibular_canal 0.0136, right_maxillary_sinus 0.0001, left_maxillary_sinus 0.1084 |
| `20260617T152345Z` |  | D024 | 96x128x128 |  |  | 0.0370 | 0.0202 | 30 | 953.7598 | maxilla_or_upper_jawbone 0.1259, mandible_or_lower_jawbone 0.0373, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0000, left_maxillary_sinus 0.0079 |
| `20260617T171733Z` |  | D036 | 128x160x160 |  |  | 0.2662 | 0.1914 | 80 | 1942.1348 | maxilla_or_upper_jawbone 0.2196, mandible_or_lower_jawbone 0.5743, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.2716, left_maxillary_sinus  |
| `20260617T152538Z` |  | D036 | 96x128x128 |  |  | 0.1655 | 0.1265 | 300 | 952.4473 | maxilla_or_upper_jawbone 0.1239, mandible_or_lower_jawbone 0.5406, right_mandibular_canal 0.0836, left_mandibular_canal 0.0408, right_maxillary_sinus 0.0029, left_maxillary_sinus 0.0000 |
| `20260617T153152Z` |  | D036 | 96x128x128 |  |  | 0.1370 | 0.1087 | 800 | 1017.8848 | maxilla_or_upper_jawbone 0.0427, mandible_or_lower_jawbone 0.5680, right_mandibular_canal 0.0455, left_mandibular_canal 0.0231, right_maxillary_sinus 0.0742, left_maxillary_sinus 0.0277 |
| `20260617T152345Z` |  | D036 | 96x128x128 |  |  | 0.0156 | 0.0084 | 30 | 952.1348 | maxilla_or_upper_jawbone 0.0084, mandible_or_lower_jawbone 0.0206, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0644, left_maxillary_sinus 0.0000 |
| `20260617T211024Z` | anatomy4 | D024 | 160x224x224 | tversky_focal | class_cycle | 0.2989 | 0.2148 | 300 | 4818.7188 | maxilla_or_upper_jawbone 0.5484, mandible_or_lower_jawbone 0.4212, mandibular_canal 0.0524, maxillary_sinus 0.1736 |
| `20260617T214431Z` | anatomy4 | D036 | 160x224x224 | dice_focal | class_cycle | 0.3860 | 0.3041 | 800 | 4419.7124 | maxilla_or_upper_jawbone 0.3769, mandible_or_lower_jawbone 0.7450, mandibular_canal 0.2217, maxillary_sinus 0.1786 |
| `20260617T213319Z` | anatomy4 | D036 | 160x224x224 | dice_focal | class_cycle | 0.2626 | 0.1897 | 300 | 4419.7124 | maxilla_or_upper_jawbone 0.3303, mandible_or_lower_jawbone 0.5885, mandibular_canal 0.0551, maxillary_sinus 0.0766 |
| `20260617T212214Z` | anatomy4 | D036 | 160x224x224 | dice_focal | small_cycle | 0.1887 | 0.1357 | 300 | 4419.7124 | maxilla_or_upper_jawbone 0.1855, mandible_or_lower_jawbone 0.5588, mandibular_canal 0.0081, maxillary_sinus 0.0086 |
| `20260617T200541Z` | anatomy6 | D024 | 160x224x224 | tversky_focal | class_cycle | 0.2090 | 0.1487 | 800 | 5307.0674 | maxilla_or_upper_jawbone 0.4701, mandible_or_lower_jawbone 0.5048, right_mandibular_canal 0.0627, left_mandibular_canal 0.0661, right_maxillary_sinus 0.0339, left_maxillary_sinus 0.1162 |
| `20260617T184454Z` | anatomy6 | D024 | 160x224x224 | tversky_focal | class_cycle | 0.1986 | 0.1424 | 300 | 5307.0674 | maxilla_or_upper_jawbone 0.4924, mandible_or_lower_jawbone 0.4566, right_mandibular_canal 0.0050, left_mandibular_canal 0.0041, right_maxillary_sinus 0.0577, left_maxillary_sinus 0.0645 |
| `20260617T190426Z` | anatomy6 | D024 | 160x224x224 | dice_focal | class_cycle | 0.1652 | 0.1146 | 300 | 4726.1831 | maxilla_or_upper_jawbone 0.4528, mandible_or_lower_jawbone 0.4206, right_mandibular_canal 0.0423, left_mandibular_canal 0.0148, right_maxillary_sinus 0.0234, left_maxillary_sinus 0.0374 |
| `20260617T193437Z` | anatomy6 | D024 | 160x224x224 | tversky_focal | small_cycle | 0.1649 | 0.1150 | 300 | 5307.0674 | maxilla_or_upper_jawbone 0.5190, mandible_or_lower_jawbone 0.3430, right_mandibular_canal 0.0015, left_mandibular_canal 0.0011, right_maxillary_sinus 0.0266, left_maxillary_sinus 0.0983 |
| `20260617T180631Z` | anatomy6 | D024 | 160x224x224 | dice_ce | class_cycle | 0.1394 | 0.0934 | 300 | 4694.5566 | maxilla_or_upper_jawbone 0.3523, mandible_or_lower_jawbone 0.3918, right_mandibular_canal 0.0168, left_mandibular_canal 0.0333, right_maxillary_sinus 0.0395, left_maxillary_sinus 0.0024 |
| `20260617T172607Z` | anatomy6 | D024 | 160x224x224 | dice_ce | small50 | 0.0910 | 0.0519 | 10 | 4694.5566 | maxilla_or_upper_jawbone 0.3031, mandible_or_lower_jawbone 0.1153, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0000, left_maxillary_sinus 0.1278 |
| `20260617T203057Z` | anatomy6 | D036 | 160x224x224 | dice_focal | small_cycle | 0.2096 | 0.1498 | 800 | 4726.1831 | maxilla_or_upper_jawbone 0.2322, mandible_or_lower_jawbone 0.6460, right_mandibular_canal 0.0055, left_mandibular_canal 0.1218, right_maxillary_sinus 0.0427, left_maxillary_sinus 0.0844 |
| `20260617T194611Z` | anatomy6 | D036 | 160x224x224 | dice_focal | small_cycle | 0.1813 | 0.1355 | 300 | 4726.1831 | maxilla_or_upper_jawbone 0.2500, mandible_or_lower_jawbone 0.5949, right_mandibular_canal 0.0142, left_mandibular_canal 0.0017, right_maxillary_sinus 0.0310, left_maxillary_sinus 0.1329 |
| `20260617T172607Z` | anatomy6 | D036 | 160x224x224 | dice_ce | small50 | 0.1433 | 0.1149 | 10 | 4692.8379 | maxilla_or_upper_jawbone 0.0000, mandible_or_lower_jawbone 0.7908, right_mandibular_canal 0.0285, left_mandibular_canal 0.0403, right_maxillary_sinus 0.0000, left_maxillary_sinus 0.0000 |
| `20260617T195718Z` | anatomy6 | D036 | 128x160x160 | dice_focal | small_cycle | 0.1264 | 0.0903 | 300 | 1958.1987 | maxilla_or_upper_jawbone 0.1922, mandible_or_lower_jawbone 0.4333, right_mandibular_canal 0.0000, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0102, left_maxillary_sinus 0.0994 |
| `20260617T190426Z` | anatomy6 | D036 | 160x224x224 | dice_focal | class_cycle | 0.1200 | 0.0899 | 300 | 4723.7612 | maxilla_or_upper_jawbone 0.0555, mandible_or_lower_jawbone 0.5613, right_mandibular_canal 0.0238, left_mandibular_canal 0.0013, right_maxillary_sinus 0.0424, left_maxillary_sinus 0.0089 |
| `20260617T184454Z` | anatomy6 | D036 | 160x224x224 | tversky_focal | class_cycle | 0.1131 | 0.0869 | 300 | 5306.5518 | maxilla_or_upper_jawbone 0.0505, mandible_or_lower_jawbone 0.5581, right_mandibular_canal 0.0097, left_mandibular_canal 0.0058, right_maxillary_sinus 0.0503, left_maxillary_sinus 0.0041 |
| `20260617T180631Z` | anatomy6 | D036 | 160x224x224 | dice_ce | class_cycle | 0.1004 | 0.0725 | 300 | 4694.0410 | maxilla_or_upper_jawbone 0.0453, mandible_or_lower_jawbone 0.5111, right_mandibular_canal 0.0001, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0309, left_maxillary_sinus 0.0081 |
| `20260617T205414Z` | anatomy6 | D036 | 160x224x224 | dice_focal | canal_focus | 0.0446 | 0.0276 | 300 | 4726.1831 | maxilla_or_upper_jawbone 0.1129, mandible_or_lower_jawbone 0.0883, right_mandibular_canal 0.0005, left_mandibular_canal 0.0000, right_maxillary_sinus 0.0273, left_maxillary_sinus 0.0322 |
| `20260617T174612Z` | coarse3 | D024 | 160x224x224 | dice_ce | class_cycle | 0.3745 | 0.2967 | 300 | 4269.7983 | jawbone 0.7987, mandibular_canal 0.0301, maxillary_sinus 0.2946 |
| `20260617T172737Z` | coarse3 | D024 | 160x224x224 | dice_ce | small50 | 0.3610 | 0.2687 | 200 | 4269.7983 | jawbone 0.7242, mandibular_canal 0.0233, maxillary_sinus 0.3355 |
| `20260617T183801Z` | coarse3 | D024 | 192x256x256 | dice_ce | class_cycle | 0.0170 | 0.0089 | 8 | 6651.5947 | jawbone 0.0503, mandibular_canal 0.0000, maxillary_sinus 0.0007 |
| `20260617T174612Z` | coarse3 | D036 | 160x224x224 | dice_ce | class_cycle | 0.3424 | 0.2698 | 300 | 4267.4702 | jawbone 0.6958, mandibular_canal 0.0810, maxillary_sinus 0.2463 |
| `20260617T172737Z` | coarse3 | D036 | 160x224x224 | dice_ce | small50 | 0.2388 | 0.1777 | 200 | 4265.6108 | jawbone 0.6122, mandibular_canal 0.1041, maxillary_sinus 0.0000 |
| `20260617T184117Z` | coarse3 | D036 | 192x256x256 | dice_ce | class_cycle | 0.0060 | 0.0030 | 8 | 6651.5947 | jawbone 0.0178, mandibular_canal 0.0000, maxillary_sinus 0.0002 |

## nnU-Net 入口

`nnUNetv2_train 124 3d_fullres 0 -tr nnUNetTrainerNoMirroring`

环境变量：

```json
{
  "nnUNet_raw": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_raw",
  "nnUNet_preprocessed": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_preprocessed",
  "nnUNet_results": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_results"
}
```

## 判断

本报告应与 `public_cbct_3dataset_segmentation_benchmark_zh.md` 分开解读：64³ 结果只代表 smoke，当前结果代表高分辨率 patch 训练链路。历史对照显示，`coarse3 + 160x224x224 + class_cycle` 已在 D024/D036 达到 0.3 以上 Dice，可作为当前可用的粗粒度解剖先验；新增 `anatomy4` 中间粒度任务后，D024 达到 `0.2989`，D036 达到 `0.3860`，说明合并左右下颌管和左右上颌窦后，模型已经能稳定学到接近或超过 0.3 Dice 的可用解剖结构表示。

本轮 loss 对照显示，`tversky_focal` 将 D024 anatomy6 从 `0.1394` 提升到 `0.1986`，`dice_focal` 将 D036 anatomy6 从 `0.1004` 提升到 `0.1200`。新增 `small_cycle` 采样后，D036 在 `160x224x224 + dice_focal` 下进一步提升到 `0.1813`，但 D024 在同类小结构强化下下降到 `0.1649`，说明 D024 更依赖大结构稳定监督，D036 更受益于小结构采样。延长到 800 batch 后，D024 anatomy6 达到 `0.2090`，D036 anatomy6 达到 `0.2096`，两者都确认了训练预算仍然带来增益。

`192x256x256` 已通过 8 batch 显存 sanity，峰值约 `6652 MB`，但短训练结果不能和 300 batch 对照直接比较。`128x160x160 + small_cycle` 在当前独立 cache 下未复现旧的高 Dice，提示旧结果可能受 cache、采样或验证切分差异影响。`canal_focus` 在 D036 上下降到 `0.0446`，说明单纯过采样下颌管会破坏 jaw/sinus 的共同表示。下一步应将 `anatomy4` 作为第一阶段结构先验，再做局部左右细分 refinement；完整 `anatomy6` 暂不直接承诺 0.3。
