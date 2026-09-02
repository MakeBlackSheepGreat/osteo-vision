# DentalSegmentator 颌骨 ROI 预处理契约落地说明

日期：2026-07-04

## 结论

本轮没有下载或接入 DentalSegmentator 的大型 checkpoint，而是先把它在本项目中的可复用位置固化为一个本地预处理契约：**CBCT/NPZ + 可选解剖 mask -> 颌骨/牙颌面 ROI 裁剪 NPZ + manifest**。

这一步直接服务后续平台闭环中的 AI 模型训练和术前 CBCT 代理分割：先把颌骨相关区域从全体积中稳定裁出来，再交给 D025 病灶代理模型、nnU-Net/DynUNet 或其他 3D segmentation baseline。它不是术中 ICG MP4/JPEG 目标域模型，也不是 DentalSegmentator 权重推理结果。

## 外部来源核验

本轮使用 Tavily CLI 核验 DentalSegmentator 相关来源，结果保存于本地临时文件 `.pytest_tmp/tavily_dentalsegmentator_search_20260704.json` 和 `.pytest_tmp/tavily_slicer_dentalsegmentator_search_20260704.json`，不进入 Git。

可追溯来源：

- DentalSegmentator nnU-Net v2.2 预训练模型 Zenodo 记录：<https://zenodo.org/records/10829675>
- SlicerAutomatedDentalTools 扩展：<https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools>
- SlicerDentalSegmentator 扩展说明：<https://github.com/gaudot/SlicerDentalSegmentator>

Zenodo 记录显示 DentalSegmentator 预训练模型面向牙颌面 CBCT/CT 解剖分割，文件约 229.7 MB。当前阶段不下载该权重，避免把大型 checkpoint 放入仓库。

## 已落地代码

- 新增模块：`src/preprocess/cbct_roi.py`
- 新增 CLI：`tools/build_cbct_roi_preprocess.py`
- 新增测试：`tests/unit/test_cbct_roi_preprocess.py`

核心函数：

```python
from src.preprocess.cbct_roi import build_cbct_anatomy_roi

result = build_cbct_anatomy_roi(
    "case.npz",
    "artifacts/preprocessing/cbct_roi/case",
    anatomy_mask_path="case_anatomy_mask.npy",
    foreground_labels=[1, 2],
    margin_voxels=(8, 8, 8),
)
```

输入支持：

- `input_npz`：包含 3D `image`，可选 `label`。
- `anatomy_mask_path`：可选 `.npy` 或 `.npz` 解剖 mask；后续可由 DentalSegmentator 生成。
- `foreground_labels`：可指定用于 ROI 的解剖标签；不指定时使用 mask/label 的全部非零区域。
- `margin_voxels`：3D bbox 外扩边距。
- `fallback_crop_shape`：无前景时用于确定性中心裁剪。

输出：

- `*_cbct_anatomy_roi.npz`：裁剪后的 `image`、可选 `label`、可选 `anatomy_mask`、`source_shape` 和 `roi_bbox_zyx`。
- `*_cbct_anatomy_roi_manifest.json`：记录 bbox、归一化 bbox、输入路径、ROI 来源、标签值、warning、数据边界和医学边界。

命令行复现：

```powershell
conda run -n osteo-vision python tools\build_cbct_roi_preprocess.py `
  --input case.npz `
  --output-dir artifacts\preprocessing\cbct_roi\case `
  --anatomy-mask case_anatomy_mask.npy `
  --foreground-labels 1,2 `
  --margin 8,8,8
```

## Fallback 规则

ROI 来源优先级：

1. 外部 `anatomy_mask_path`，对应未来 DentalSegmentator 解剖分割输出。
2. 输入 NPZ 自带 `label`。
3. 图像非零体素 fallback。
4. 无任何前景时使用中心裁剪 fallback。

所有 fallback 都会写入 manifest warning，避免把粗糙代理 ROI 误解为模型分割结果。

## 对平台模型闭环的帮助

1. 为 CBCT 代理训练提供稳定 ROI 裁剪入口，减少全体积背景对 3D 分割模型的干扰。
2. 给未来 DentalSegmentator 权重接入预留明确边界：真实权重只需要产出 anatomy mask，即可复用当前 ROI 契约。
3. 支持 nnU-Net/DynUNet 高分辨率 patch 训练前的统一 ROI manifest，便于追踪病例、bbox、标签来源和非目标域声明。
4. 与当前平台软件主线互补：MP4/JPEG 走术中荧光融合和 2D keyframe 代理分割，hotspot 作为回退；CBCT ROI 作为术前解剖先验和模型训练代理，不替代术中荧光输入。

## 医学和数据边界

- DentalSegmentator 是牙颌面 CT/CBCT 解剖结构分割工具，不是颌骨骨髓炎病灶模型。
- 当前实现不执行 DentalSegmentator checkpoint 推理；只是一个可消费其输出的 ROI contract。
- D024/D025/D036、CBCT 派生 ROI 和公开解剖 mask 都是代理或非目标域数据。
- 任何输出只能作为研发验证版平台和医生复核辅助，不能替代医生诊断。

## 验证

已通过：

```powershell
conda run -n osteo-vision python -m ruff check src\preprocess\cbct_roi.py tools\build_cbct_roi_preprocess.py tests\unit\test_cbct_roi_preprocess.py --output-format concise
conda run -n osteo-vision python -m pytest tests\unit\test_cbct_roi_preprocess.py -q
```

测试覆盖：

- 外部 anatomy mask ROI 裁剪和 manifest。
- 输入 label fallback。
- 无 label 时图像非零 fallback。
- 无前景时中心裁剪 fallback。
- anatomy mask 与 image 形状不一致时报错。

## 下一步

1. 若后续下载 DentalSegmentator 权重，应放入 Git 忽略的 checkpoint/raw 目录，并记录来源、大小、hash 和下载时间。
2. 增加一个 CLI，把 D024/D036/D025 或医院脱敏 CBCT 批量转为 ROI manifest。
3. 将 ROI manifest 接入 nnU-Net/DynUNet 训练清单，形成“解剖 ROI -> 病灶/风险区域分割”的可复现实验链。
4. 前端报告中只展示 CBCT ROI 作为术前辅助证据，避免与官方术中 MP4/JPEG 荧光链路混淆。
