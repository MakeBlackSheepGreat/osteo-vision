# Anatomy High-Resolution Patch Segmentation Experiment Report

## Objective

This experiment tests whether the low Dice scores are mainly caused by `64x64x64` full-volume compression. The run uses `160x224x224` high-resolution patch caches, with runtime inputs fixed under local project `derived/highres_patch/` directories.

Medical boundary: D024/D036 are CBCT anatomical segmentation datasets. They do not contain intraoperative ICG labels or clinical jaw osteomyelitis outcome labels.

## Patch Caches

| Dataset | Cases | Patches | Generated Patches | Manifest | Source |
| --- | ---: | ---: | ---: | --- | --- |
| D036 | 12 | 180 | 0 | `research\datasets\public-candidates\d036_toothfairy2\derived\highres_patch\anatomy4_160x224x224_class_cycle\d036_anatomy_highres_patch_manifest.csv` | project_raw |

## Settings

- Device: `cuda`; GPU: `NVIDIA GeForce RTX 5060 Laptop GPU`
- Models: `monai_segresnetds`
- Label mode: `anatomy4`; sampling strategy: `class_cycle`
- Loss: `dice_focal`; class weighting: `sqrt_inverse`; AMP: `True`
- Train batches: `800`; validation patches: `30`
- Sampling: class-cycle patch centers over foreground and every target label.

## Results

| Dataset | Model | Status | Dice | IoU | Target FG | Pred FG | Train batches | Peak MB | Seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| D036 | monai_segresnetds | completed | 0.3860 | 0.3041 | 0.0583 | 0.0636 | 800 | 4419.7124 | 1261.3617 |

## Historical Comparison

| Run | Label mode | Dataset | Patch | Loss | Sampling | Dice | IoU | Train batches | Peak MB | Key class Dice |
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

## nnU-Net Entry

`nnUNetv2_train 124 3d_fullres 0 -tr nnUNetTrainerNoMirroring`

Environment:

```json
{
  "nnUNet_raw": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_raw",
  "nnUNet_preprocessed": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_preprocessed",
  "nnUNet_results": "research\\datasets\\public-candidates\\d024_dentvoxel\\derived\\nnunet\\nnUNet_results"
}
```

## Interpretation

This report must be read separately from `public_cbct_3dataset_segmentation_benchmark_en.md`: the 64-cube result is smoke evidence, while this run validates the high-resolution patch training path. The historical comparison shows that `coarse3 + 160x224x224 + class_cycle` already reaches Dice above 0.3 on D024/D036, making it usable as the current coarse anatomical-prior task. With the new intermediate `anatomy4` task, D024 reaches `0.2989` and D036 reaches `0.3860`; after merging left/right mandibular canal and left/right maxillary sinus labels, the model now learns a usable anatomical representation around or above 0.3 Dice.

The loss comparison shows that `tversky_focal` improves D024 anatomy6 from `0.1394` to `0.1986`, while `dice_focal` improves D036 anatomy6 from `0.1004` to `0.1200`. With the new `small_cycle` sampler, D036 further improves to `0.1813` under `160x224x224 + dice_focal`, while D024 drops to `0.1649` under a similar small-structure-heavy setting. This suggests that D024 still needs stable large-structure supervision, while D036 benefits more from small-structure sampling. Extending training to 800 batches raises D024 anatomy6 to `0.2090` and D036 anatomy6 to `0.2096`, confirming that training budget still provides measurable gains.

The `192x256x256` setting passed an 8-batch memory sanity check with about `6652 MB` peak usage, but the short-run Dice is not comparable to 300-batch experiments. `128x160x160 + small_cycle` did not reproduce the older high Dice after using an isolated cache, which suggests that the older result may have depended on cache, sampling, or validation split differences. `canal_focus` drops D036 to `0.0446`, showing that simply oversampling mandibular-canal centers damages the shared jaw/sinus representation. Next work should use `anatomy4` as the first-stage structural prior and then train local laterality-aware refinement; full `anatomy6` should not be claimed as 0.3-ready yet.
