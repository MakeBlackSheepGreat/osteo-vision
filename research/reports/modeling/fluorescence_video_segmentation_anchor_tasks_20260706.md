# 荧光视频分割落地锚定清单

日期：2026-07-06

## A. 固定术语

| 术语 | 固定含义 |
|---|---|
| `video_signal_segmentation` | 视频信号分割总任务，不等同疾病终判 |
| `bone_gate_mask` | 白光/纹理分支得到的骨面可分析区域 |
| `fluorescence_signal_mask` | 荧光强度分支得到的热点、弱荧光、漏光/噪声区域 |
| `risk_mask` | 骨面门控内的灌注/活性风险提示 |
| `review_state` | `accepted`、`modified`、`rejected`、`review_required` |

## B. 后续第一轮代码任务

1. 新增 D046 视频信号 manifest 构建脚本。
2. 在任务配置中固化七类 mask taxonomy。
3. 扩展 keyframe 输出 schema：`bone_gate_mask`、`fluorescence_signal_mask`、`risk_mask`、`uncertain_mask`。
4. 给前端复核结果增加 mask type 和 review state 字段。
5. 把医生复核事件导出为加权训练 manifest。
6. 在报告导出中加入“荧光灌注/活性风险提示”章节。

## C. 第一轮数据产物

目标输出目录建议：

```text
research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/
└── video_signal_segmentation_20260706/
    ├── video_signal_segmentation_manifest.csv
    ├── keyframes/
    ├── reference/
    ├── fluorescence/
    ├── overlay/
    ├── masks_proxy/
    └── quality/
```

建议字段：

| 字段 | 说明 |
|---|---|
| `case_id` | keyframe 或视频样本 ID |
| `source_video_path` | 原始 MP4 |
| `source_page_original_link` | 来源页面 |
| `frame_index` | 帧号 |
| `timestamp_sec` | 时间戳 |
| `reference_frame_path` | 白光/reference 帧 |
| `fluorescence_frame_path` | 荧光帧 |
| `overlay_frame_path` | 叠加帧 |
| `quality_status` | accepted / warning / rejected |
| `quality_reason` | 模糊、过曝、欠曝、遮挡、漏光等 |
| `label_source` | heuristic / sam2_assisted / physician_review |
| `mask_type` | 七类 mask 之一 |
| `review_state` | accepted / modified / rejected / review_required |
| `sample_weight` | 回灌训练权重 |

## D. 第一轮验收标准

- 至少处理 20 个 D046 公开视频样本。
- 至少生成 100 个 keyframe 样本。
- 每个 keyframe 有来源、帧号、时间戳、质量指标和至少一个 mask 类型。
- 前端可播放原 MP4，并同步展示关键帧 overlay/risk。
- 所有输出明确非目标域边界。

## E. 第一轮落地结果

- 已新增 `tools/build_video_signal_segmentation_manifest.py`，可从 D046 公开视频生成 `video_signal_segmentation_manifest.csv`。
- 已执行 20 个视频、每个 5 个关键帧的 manifest 构建，共生成 100 个 keyframe 样本，质量状态均为 `accepted`。
- 已在 `configs/tasks/osteo_vision.yml` 固化七类 mask taxonomy，并在 `configs/inference/osteo_vision.yml` 增加 `video_signal_segmentation` 运行元数据。
- 已扩展 keyframe 主线和 hotspot fallback 输出：`bone_gate_mask`、`fluorescence_signal_mask`、`risk_mask`、`uncertain_mask`。
- 已扩展后端 `video_segmentation_manifest.json`、医生复核 manifest、报告导出和前端同步分析展示。
- 当前 `bone_gate_mask` 保持 `not_available_pending_review`，没有医生/SAM 辅助标注前不伪造骨面真值。
