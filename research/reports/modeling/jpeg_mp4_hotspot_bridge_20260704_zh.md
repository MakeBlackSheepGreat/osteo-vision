# JPEG/MP4 关键帧热点分割桥接报告

日期：2026-07-04

## 结论

本轮补上赛题官方输入到 AI 辅助判读之间的一段短板：JPEG 荧光图像和 MP4 关键帧现在可以进入 2D fluorescence hotspot segmentation baseline，输出二值掩码、候选区、量化摘要和证据图。

这仍是启发式基线，不是训练完成的临床模型；它的价值是让赛点二在官方 JPEG/MP4 输入上有一个可跑、可导出、可复核的最小闭环。

## 代码与配置

- 2D 热点分割实现：`src/models/hotspot_segmenter.py`
- 模型适配器：`src/models/adapters.py`
- 主线推理配置：`configs/inference/osteo_vision.yml`
- 任务推荐模型：`configs/tasks/osteo_vision.yml`
- MP4 分析接入：`backend/src/services/analysis_service.py`
- 前端标签补充：`frontend/src/utils/caseDisplay.ts`
- 测试：`tests/unit/test_model_adapters.py`、`tests/unit/test_inference_pipelines.py`、`backend/tests/contract/test_case_inputs_api.py`

## 当前能力

### JPEG / 2D 图像

新增模型：

- model_id：`fluorescence_hotspot_2d_segmenter`
- family：`fluorescence_hotspot_segmenter`
- input_type：`2d_image`
- 输出：`png_binary_mask`、伪彩图、overlay、候选连通区、阳性面积比例

真实配置验证：

```json
{
  "status": "completed",
  "model_id": "fluorescence_hotspot_2d_segmenter",
  "model_family": "fluorescence_hotspot_segmenter",
  "mask_format": "png_binary_mask",
  "positive_area_px": 250,
  "warning_codes": [
    "heuristic_hotspot_segmenter_non_diagnostic"
  ]
}
```

### MP4 / 关键帧

MP4 分析现在不仅抽取 keyframes，还会对每个 keyframe 运行热点分割，写入：

- `fused_outputs.hotspot_outputs`
- `quantitative_summary.hotspot_frame_count`
- `quantitative_summary.hotspot_candidate_count`
- `quantitative_summary.hotspot_max_positive_area_fraction`
- `candidate_regions` 中的 `video_keyframe_hotspot`
- ROI mask / heatmap / overlay artifacts

## 医学边界

该桥接使用图像强度增强、阈值和连通区分析，属于规则/启发式 baseline。它可作为医生复核队列的候选提示和工程闭环证据，不能替代医生判断，也不能作为真实颌骨骨髓炎诊断模型性能。

## 下一步

1. 用 OFDVDnet baseline manifest 生成更多 JPEG/帧序列输入，做阈值稳定性分析。
2. 将热点候选区作为 prompt，接 MedSAM 或更正式的 2D segmentation adapter。
3. 将前端 MP4 结果面板从“只显示关键帧”升级为“关键帧 + mask + 候选区 + 量化指标”。
