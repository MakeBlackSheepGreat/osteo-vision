# 公开视频动态荧光量化链路验证

日期：2026-07-11

## 验证对象

- 来源：Dryad OFDVDnet，`OFDVDNET_023`。
- 文件：`OL-2021-07-20-131158-000014-record.mp4`。
- 场景：离体鸡腿荧光手术代理视频，2048×1536，15 FPS，170.53 秒。
- 边界：公开非目标域、离体、解码 8-bit luminance 代理；不属于颌骨骨髓炎术中 ICG 病例。

## 运行方法

通过 `AnalysisService.start_analysis()` 指定四个公开源关键帧索引 `319/958/1598/2237`，使用当前 `configs/inference/osteo_vision.yml` 完成解码、关键帧分割、帧强度统计、结构化 frame details 和时间强度曲线输出。

## 结果

| 指标 | 结果 |
|---|---:|
| 分析状态 | completed |
| 曲线可用 | true |
| 有效关键帧 | 4 |
| 时间戳范围 | 21.266667-149.133333 s |
| 背景扣除 | per-frame background subtraction |
| 归一化 | baseline-to-peak unit range |
| 动态范围非零 | false |
| 曲线质量 | limited |
| 达峰时间 | 0.0 s |
| 最大归一化上升斜率 | 0.0/s |
| 归一化 AUC | 0.0 |
| AI 推理 P50/P95 | 633.504/978.138 ms |
| 推理模式 | 4 帧均为 tiled |

四个关键帧均从解码像素生成 `p95_intensity` 与 `background_intensity`，分割概率未进入强度曲线。该公开视频选取区间的 P95 背景扣除值约为 0.596-0.608，动态范围很小，因此软件正确输出 `quality_status=limited`、`dynamic_range_nonzero=false` 和零斜率/AUC。该结果验证真实公开视频关键帧链路可以生成结构化曲线及质量门控，同时提示稳定展示型视频无法提供有效灌注动力学变化。

## 结构化证据

- 本地病例仓库：`artifacts/platform_smoke/public_video_dynamic_20260711/cases.json`
- Frame details manifest：运行产物位于 `artifacts/visual_evidence/osteo_vision/cases/public_dynamic_ofdvdnet_023/frame_details/`
- 关键字段：`source=decoded_keyframe_intensity`、`source_intensity_key=p95_intensity`、`background_correction=per_frame_background_subtraction`

## 结论边界

当前链路证明公开真实视频可以产出背景扣除、归一化、达峰时间、斜率、AUC 和质量字段。OFDVDnet 片段缺少 ICG 注射协议和明显灌注变化，所得曲线只用于软件工程验证。跨病例或临床解释仍需企业原始 NIR 通道、锁定曝光/增益/光源/工作距离、注射时刻和医生 ROI。
