# D024 DentVoxel 数据集预处理报告（中文）

## 数据来源与许可

- 数据集：DentVoxel（D024）
- 模态：CBCT，3D NIfTI
- 来源文件：`research\datasets\public-candidates\d024_dentvoxel\DentVoxel_Dataset.zip`
- 许可：CC BY
- 运行时间（UTC）：2026-06-16T04:47:38.471646+00:00

## 目录结构

- 原始数据目录：`research\datasets\public-candidates\d024_dentvoxel\raw\DentVoxel_Dataset`
- 派生产物目录：`research\datasets\public-candidates\d024_dentvoxel\derived`
- 统一报告目录：`research\reports\preprocessing`
- manifest：`research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_manifest.csv`
- 标签清单：`research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_label_inventory.csv`
- 质量检查表：`research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_quality_check.csv`
- 统计 JSON：`research\datasets\public-candidates\d024_dentvoxel\derived\manifests\d024_dentvoxel_preprocessing_summary.json`

## 预处理方法

1. 从 ZIP 解压 `DentVoxel_Dataset/` 到 `raw/`，跳过 `._*` 与 `__MACOSX` 资源文件。
2. 按 `imgXXXX.nii.gz` 与 `labelXXXX.nii.gz` 编号进行配对。
3. 使用 `nibabel` 读取每个病例的 shape、spacing、dtype 与标签值。
4. 生成框架可读 manifest，任务类型设为 `segmentation`，输入类型设为 `nifti_volume`。
5. 生成前 5 个病例的轴位、冠状位、矢状位预览图，红色叠加表示非背景标签。

## 全量检查结果

- image 数量：100
- label 数量：100
- 成功配对病例：100
- 缺失 label 的 image：[]
- 缺失 image 的 label：[]
- manifest 行数：100
- 读取异常病例数：0
- shape 分布：`{'440x440x344': 97, '440x440x343': 2, '442x344x438': 1}`
- spacing 分布：`{'0.3x0.3x0.3': 100}`

## 标签体系说明

标签值来自 `dataset_DentVoxel.json`，共 39 类，包含背景、上颌骨、下颌骨、FDI 牙位、左右下颌管与左右上颌窦。完整标签表已写入 `d024_dentvoxel_label_inventory.csv`。

## 可用于本项目的任务方向

- 术前 CBCT 颌骨/牙齿结构分割预训练。
- nnU-Net 或 MONAI 3D 分割基线数据准备。
- 为颌骨骨髓炎病灶定位提供颌骨 ROI 与解剖结构先验。

## 局限性与下一步计划

- D024 是解剖结构分割数据集，不是术中 ICG 荧光数据。
- 当前标签不包含颌骨骨髓炎、坏死骨或炎症边界。
- 下一步建议转换为 nnU-Net 数据格式，并优先抽取上颌骨/下颌骨/下颌管等结构做 baseline。
