# P0 代码与数据集下载状态

更新时间：2026-06-11

---

## 代码下载状态

| 优先级 | 名称 | 状态 | 说明 |
|--------|------|------|------|
| P0 | nnU-Net | ✅ 已下载 | `code/nnunet/` (282 files) |
| P0 | EGNet | ✅ 已下载 | `code/egnet/` (13 files) |
| P0 | FRS Loss | ✅ 已下载 | `code/frs_loss/` (14 files) |
| P0 | WaveletFusion-ViT | ❌ 无公开代码 | 论文 P016，需自行实现 |
| P0 | ICG AI Segmentation | ❌ 无公开代码 | 论文 P055，需自行实现 |

---

## 数据集下载状态

| 优先级 | 编号 | 名称 | 状态 | 说明 |
|--------|------|------|------|------|
| P0 | D024 | DentVoxel | ⚠️ 需手动下载 | 需注册 Figshare 下载 |
| P0 | D025 | 牙源性病灶 CBCT+病理 | ⚠️ 需手动下载 | 需注册 Figshare 下载 |
| P0 | D036 | ToothFairy2 | ⚠️ 需手动下载 | 需注册 Grand Challenge 下载 |
| P0 | D044 | FGS 荧光手术视频 | ⚠️ 需手动下载 | 34GB，Dryad 下载 |

---

## 手动下载指南

### D024 DentVoxel
1. 访问: https://figshare.com/articles/dataset/DentVoxel_a_fully_annotated_dental_CBCT_dataset_with_38_instance_anatomical_structures/31239889
2. 点击 "Download" 按钮
3. 保存到 `datasets/d024_dentvoxel/`

### D025 牙源性病灶 CBCT+病理
1. 访问: https://figshare.com/articles/dataset/Dental_Odontogenic_Lesion_CBCT_and_Histopathology_Integrated_Dataset_for_Benchmarking_Deep_Learning_Algorithms/30156622
2. 点击 "Download" 按钮
3. 保存到 `datasets/d025_lesion_cbct/`

### D036 ToothFairy2
1. 访问: https://toothfairy2.grand-challenge.org/dataset/
2. 注册/登录 Grand Challenge 账号
3. 点击下载链接
4. 保存到 `datasets/d036_toothfairy2/`

### D044 FGS 荧光手术视频 (34GB)
1. 访问: https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9
2. 点击 "FGS_Data_andModels.zip" (34 GB)
3. 保存到 `datasets/d044_fgs_video/`

---

## 文件夹结构

```
osteo-vision/
├── code/
│   ├── nnunet/           ✅ 已下载 (282 files)
│   ├── egnet/            ✅ 已下载 (13 files)
│   ├── frs_loss/         ✅ 已下载 (14 files)
│   ├── waveletfusion-vit/   ❌ 需自行实现
│   └── icg_ai_segmentation/ ❌ 需自行实现
└── datasets/
    ├── d024_dentvoxel/       ⚠️ 需手动下载
    ├── d025_lesion_cbct/     ⚠️ 需手动下载
    ├── d036_toothfairy2/     ⚠️ 需手动下载
    └── d044_fgs_video/       ⚠️ 需手动下载 (34GB)
```
