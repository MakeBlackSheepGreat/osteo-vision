# 公开 CBCT 本地训练缓存报告

## 目标

本次把训练和推理可直接读取的数据层固定在项目本地 `derived/` 目录下。D 盘只作为静态原始数据归档来源，不作为运行时依赖。

## 处理策略

- 目标尺寸：`64x64x64`
- 图像：0.5/99.5 百分位裁剪后归一化到 `[-1, 1]`，保存为 `float16`
- 标签：最近邻重采样，保存为 `int16`
- 缓存格式：压缩 NPZ，字段包含 `image`、`label`、`original_shape`、`target_shape`、`original_spacing`、`label_values`
- manifest：`input_path` 和 `mask_path` 均指向项目本地缓存文件

## 数据集结果

| 数据集 | 任务缓存 | 病例数 | 新生成 | 复用 | 本地 manifest |
| --- | --- | ---: | ---: | ---: | --- |
| d024 | jaw_roi | 100 | 0 | 100 | `research\datasets\public-candidates\d024_dentvoxel\derived\local_preprocessed\jaw_roi_64_manifest.csv` |
| d025 | lesion_roi | 262 | 0 | 262 | `research\datasets\public-candidates\d025_lesion_cbct\derived\local_preprocessed\lesion_roi_64\d025_dolchid_lesion_roi_64_manifest.csv` |
| d036 | anatomy_roi | 480 | 0 | 480 | `research\datasets\public-candidates\d036_toothfairy2\derived\local_preprocessed\anatomy_roi_64\d036_toothfairy2_anatomy_roi_64_manifest.csv` |

## 运行边界

训练、推理和 smoke benchmark 应优先读取本地 manifest 或 D024 已有 nnU-Net 预处理目录。若 D 盘不可用，现有本地缓存仍可读取；只有重新生成缓存或重做 raw 级预处理时才需要 D 盘归档。

## 局限性

D025 和 D036 当前缓存是低分辨率工程缓存，适合 smoke 训练、模型结构筛选和推理接口验证。正式高分辨率训练仍需要后续做任务级 nnU-Net/MONAI 转换，并记录新的实验报告。
