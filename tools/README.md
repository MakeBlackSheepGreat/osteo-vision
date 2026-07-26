# 核验工具

`tools/` 承担平台运行前检查、数据治理、证据生成、压力验证和工作区维护。

| 类别 | 入口 |
|---|---|
| 运行与质量 | `check_project_readiness.py`、`check_runtime_readiness.py`、`run_platform_smoke.py` |
| 类型检查环境 | `run_project_mypy.py`：为 pre-commit 定位已安装项目依赖的 Python 3.11/Conda 解释器 |
| 数据准入 | `admit_hospital_data_batch.py`、`verify_three_priority_dataset_manifests.py` |
| 证据与报告 | `build_competition_evidence_index.py`、`run_competition_flow_demo_check.py` |
| 性能与压力 | `benchmark_core_hotpaths.py`、`run_official_4k_pressure_smoke.py`、`run_competition_fusion_performance_gate.py`、`run_task2_temporal_registration_gate.py`、`run_keyframe_live_fast_output_gate.py` |
| 维护 | `audit_active_documentation.py`、`clean_workspace.py` |

补充分类：

- `download_*.py`：受控获取公开或近似数据；下载结果需带来源、许可、哈希和用途边界。
- `materialize_*.py`、`build_*_manifest.py`：把原始或公开数据转换为可审计的代理数据、训练清单或展示证据。
- `run_*_validation.py`、`run_*_gate.py`：对运行边界、配准验证或候选模型执行可复核门控。
- `build_challenge_cup_figures.py`、`build_challenge_cup_report.py`：生成挑战杯报告图包和聚合交付稿；图包以报告包内的 `assets/sources/` 为最小重建输入，构建完成后更新 SHA256 manifest。对应说明位于 `research/reports/submission/challenge_cup_report_draft_20260721/README.md`。

所有工具应保留输入来源、配置、哈希、失败原因和安全边界。清理工具只允许在校验过的仓库根目录内删除缓存及 E2E、UI 等明确可丢弃产物；病例库、人工标注、smoke 证据、检索材料、训练运行和数据集目录始终排除。执行清理时，活动进程锁定的日志或目录会作为失败项写入 JSON，其他候选仍继续处理；命令以退出码 `1` 提示存在未清理项。

`run_competition_fusion_performance_gate.py` 的 100 ms 门只统计任务2配准估计与变换、GPU 归一化、伪彩和 Alpha 融合；AI 推理、文件解码、证据编码、磁盘写入和网络传输保留独立阶段指标。默认排除一次预热并执行 10 次 4K 计时。

`run_task2_temporal_registration_gate.py` 使用可配置帧数的4K确定性遮挡与平滑形变序列验证 `adaptive_multiscale_registration_v2` 的局部残差补偿、变换时序平滑、倍率/工作距离变化状态重置、抖动、位移误差、逐帧配准融合延迟和 JPEG 预览就绪延迟。任务2的100 ms门只统计配准与融合；预览就绪采用单独的200 ms内部连续显示门。连续门同时记录局部形变残差改善率、CUDA 零拷贝交接、计算超限率和重复超限次数；使用`--frames 120`可生成长序列证据。该门属于内部工程序列证据，真实显微镜双通道同步、组织形变精度和设备标定仍需独立验证。

严格主线的任务3全证据输出对4K连通域使用分辨率自适应最小面积、候选排序和可审计上限。原始连通域数、面积过滤数、上限抑制数、边界类型评估数和医生复核保留数分别记录，避免大量碎片候选占用接口、报告和前端资源。
