# 数据获取与落地计划

更新时间：2026-06-12

## 本地目录约定

大型数据不入 Git，统一放在 `datasets/` 下：

```text
datasets/
  d024_dentvoxel/
  d025_lesion_cbct/
  d036_toothfairy2/
  d042_modid/
  d044_fgs_video/
```

每个数据集目录建议包含：

```text
SOURCE.md          来源、下载日期、许可、引用方式
checksums.txt      原始压缩包或关键文件校验
raw/               原始文件
derived/           转换后的训练格式
preview/           少量可视化截图
```

## P0 数据集

| 编号 | 名称 | 目标路径 | 作用 | 获取方式 |
| --- | --- | --- | --- | --- |
| D024 | DentVoxel | `datasets/d024_dentvoxel/` | CBCT 颌骨/牙齿结构预训练 | Figshare 手动下载 |
| D025 | Dental Odontogenic Lesion CBCT + Histopathology | `datasets/d025_lesion_cbct/` | 最接近颌骨病灶 AI 任务 | Figshare 手动下载 |
| D036 | ToothFairy2 | `datasets/d036_toothfairy2/` | nnU-Net 3D 多结构分割基线 | Grand Challenge 注册下载 |
| D044 | FGS Video Denoising | `datasets/d044_fgs_video/` | ICG 荧光视频增强和演示 | Dryad 手动下载，约 34 GB |

## P1 数据集

| 编号 | 名称 | 目标路径 | 作用 |
| --- | --- | --- | --- |
| D042 | MODID | `datasets/d042_modid/` | 多光谱口腔病灶，支撑融合思路 |
| D005 | Dental panoramic mandible segmentation | `datasets/d005_mandible_panorama/` | 低成本 ROI 演示 |
| D014 | Panoramic radiographs dental condition | `datasets/d014_panorama_pretrain/` | 全景片预训练 |

## 医院/企业样本需求

如果要把赛点二做成强项，需要尽快确认以下样本：

1. 术中白光图像或视频。
2. 同视野 ICG 荧光图像或视频。
3. 医生标注的坏死骨、病灶边界、保留区或风险区。
4. 术前 CBCT/CT/MRI 与术中图像的病例对应关系。
5. 设备导出格式、分辨率、帧率、时间戳和通道同步方式。

最低样本目标：10-30 例脱敏病例。

理想样本目标：50 例以上，含至少 2 名医生独立标注，用于一致性评估。

## 记录模板

下载或接收数据后，在对应目录的 `SOURCE.md` 中记录：

```markdown
# 数据来源

- 数据集/样本名称：
- 来源链接或提供方：
- 下载/接收日期：
- 许可或使用限制：
- 是否可用于公开演示：
- 是否可用于模型训练：
- 引用格式：
- 原始文件列表：
- 处理记录：
```
