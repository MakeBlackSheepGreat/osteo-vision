# 分割模型当前状态与阈值口径同步

## 结论

当前平台软件的分割闭环已经可运行，但真实性能证据分为两层：D025 CBCT lesion ROI 代理模型有可复现验证指标；JPEG/MP4 keyframe 模型有可训练 checkpoint 和伪标注验证指标，但仍缺少真实术中 ICG 颌骨骨髓炎医生像素级标注。

本轮已把 D025 主线运行阈值从 `0.6` 同步到阈值扫描最优值 `0.2`，并对 2D MP4/JPEG keyframe 主线完成阈值扫描、续训和运行阈值同步。`convnext2d_keyframe_proxy_segmenter` 续训后推荐阈值为 `0.15`，在 D046 代理验证集上 Dice 为 `0.9093`、IoU 为 `0.8340`，空 mask 率和过分割率均为 `0`。这些调整只更新工程运行阈值和伪标注验证证据，不改变医学边界。

## 当前主线指标

| 模型 | 输入 | 数据边界 | 阈值 | Dice | IoU | HD95 | Sensitivity | Precision | 当前用途 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `convnext3d_d025_proxy_segmenter` | `npz_roi` / CBCT ROI | D025 CBCT lesion ROI 代理数据 | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.6900 | 0.7238 | 3D 代理分割主线 |
| `convnext2d_keyframe_proxy_segmenter` | JPEG / MP4 keyframe | D046 公开/代理 MP4 keyframe 伪标注 | 0.15 | 0.9093 | 0.8340 | N/A | N/A | N/A | 2D 视频关键帧分割主线 |
| `fluorescence_hotspot_2d_segmenter` | JPEG / MP4 keyframe | 启发式荧光热点 | 0.60 | N/A | N/A | N/A | N/A | N/A | 稳定 fallback 与可视化候选区 |

## 已完成同步

- `configs/inference/osteo_vision.yml` 中 D025 3D 分割相关模型运行阈值已改为 `0.2`。
- `artifacts/checkpoints/osteo_vision/d025_lesion_smoke_manifest.json` 和模型卡已同步到阈值扫描最优指标。
- `scripts/generate_model_checkpoint_manifest.py` 已新增 `runtime_threshold`、`sidecar_metric_threshold` 和 `threshold_alignment` 字段，用于防止运行阈值与报告指标再次脱节。
- `research/reports/modeling/d025_mainline_eval_20260705/` 已保存当前主线 checkpoint 的重新评估结果和失败样本预览。
- 新增 `tools/run_keyframe_tiling_smoke.py`，可直接调用 `convnext2d_keyframe_proxy_segmenter` 对官方规格 4K keyframe 做 tiled inference 自查。2026-07-05 本地 3840x2160 合成代理 keyframe 自查通过：`tile_count=45`，mask/probability/overlay 尺寸均与输入一致，输出路径在 `.pytest_tmp/keyframe_tiling_4k_smoke/`。
- MP4 keyframe 分析新增空 mask 回退：如果 trainable keyframe 模型输出空 mask，系统会记录 `keyframe_segmenter_empty_mask_fallback` 并回退到 `fluorescence_hotspot_2d_segmenter`，避免医生复核候选区完全中断。
- 新增 `scripts/evaluate_keyframe_segmentation_proxy.py`，对 2D keyframe checkpoint 扫描 `0.10-0.60` 阈值并输出 Dice、IoU、空 mask 率、阳性面积比例和过分割率。训练后完整评估见 `research/reports/modeling/keyframe_threshold_eval_20260705/`。
- `convnext2d_keyframe_proxy_segmenter` 使用 D046 代理 manifest 续训 160 个 batch，checkpoint sidecar、模型卡和 `configs/inference/osteo_vision.yml` 的运行阈值已同步到 `0.15`。

## 仍然不能声称的内容

- 不能声称当前模型已经达到真实术中 ICG 颌骨骨髓炎临床分割性能。
- 不能把 D025 CBCT lesion ROI 指标等同于显微镜 4K MP4/JPEG 分割指标。
- 不能把 2D keyframe 伪标注验证 Dice 直接等同于医生标注病灶边界 Dice。

## 下一步

1. 用 `tools/build_keyframe_training_manifest_from_review.py` 把医生复核后的 accepted/modified/rejected 样本转换为可加权训练 manifest。
2. 将 `run_keyframe_tiling_smoke.py` 和 `evaluate_keyframe_segmentation_proxy.py` 纳入常规回归，并继续观察真实/公开代理 MP4 keyframe 上的空 mask 比例和 fallback 触发率。
3. 下一轮继续训练时优先合并医生复核样本，而不是只重复 D046 伪标注训练。
4. 将 nnU-Net/DynUNet 高分辨率路线保留为下一阶段 CBCT/解剖先验增强，不阻塞当前 JPEG/MP4 软件闭环。
