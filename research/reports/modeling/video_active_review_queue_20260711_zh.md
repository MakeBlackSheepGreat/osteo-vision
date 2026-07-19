# 视频关键帧主动复核与小金标准准备闭环

## 目标

本轮建立了从 `frame_details_manifest.json`、`video_segmentation_manifest.json` 到医生复核队列，再到训练 manifest 补丁的可运行闭环。队列用于压缩人工检查量，并优先呈现高不确定性、时序跳变、mask 面积异常、域差距、推理失败及骨面门控待复核帧。

## 工程实现

- 服务模块：`backend/src/services/active_review_queue.py`
- 命令行工具：`tools/build_video_active_review_queue.py`
- 单元测试：`backend/tests/unit/test_active_review_queue.py`
- CLI smoke：`tests/smoke/test_video_active_review_queue_cli.py`

评分由五类信号组成：不确定性 0.35、时序不稳定 0.25、mask 面积异常 0.20、域差距 0.10、失败或回退 0.10。高优先级帧可获得 0.05 的路由加分。系统按来源视频与帧号去重，并对同一视频施加最小时间间隔和单视频数量上限。

## 输出契约

工具同时生成：

- `video_active_review_queue.json`
- `video_active_review_queue.csv`
- `video_active_review_training_patch.json`
- `video_active_review_training_patch.csv`

每条复核记录保留 `accepted`、`modified`、`rejected`、`review_required` 四种状态。默认样本权重依次为 4.0、4.0、0.5、1.0。`modified` 记录需提供 `modified_mask_path` 才能进入训练补丁；`rejected` 记录进入负例候选或错误分析；待复核记录留在队列中。

## 实际 smoke

输入为同一运行产生的 frame-details 与 video-segmentation 两份 manifest。运行结果：

- 原始候选 6 帧。
- 跨 manifest 去重后 3 帧。
- 选入复核队列 3 帧。
- 3 帧均触发高不确定性与域差距提示。
- 2 帧触发 mask 面积异常提示。
- 3 帧均保留骨面门控待复核提示。
- 初始训练补丁为 0 行，符合人工复核前的数据门控要求。
- CLI 测试回填 `accepted` 后成功生成 1 条权重 4.0 的训练补丁记录。

运行命令：

```powershell
conda run -n osteo-vision python tools/build_video_active_review_queue.py `
  --input <frame_details_manifest.json> <video_segmentation_manifest.json> `
  --output-dir artifacts/active_review_queue `
  --max-frames 40 `
  --max-frames-per-source 12 `
  --min-interval-sec 2.0
```

医生完成复核后，可提供带 `review_id`、`review_state`、`modified_mask_path` 和 `review_notes` 的 JSON 或 CSV，并通过 `--review-updates` 生成训练补丁。

## 验证

- Pytest：4 项通过。
- Ruff：通过。
- Mypy：通过。
- 实际 CLI smoke：通过，JSON/CSV 队列、状态回填与训练补丁均成功生成。

## 证据边界

主动复核评分用于提高人工标注效率与代理数据质控。公开视频、合成数据、伪标签和异域荧光数据继续保留原始 `input_domain`。只有医生复核完成的记录具备小金标准候选资格，临床含义仍需目标域病例、病理或培养证据支持。
