# 核验工具

`tools/` 承担平台运行前检查、数据治理、证据生成、压力验证和工作区维护。

| 类别 | 入口 |
|---|---|
| 运行与质量 | `check_project_readiness.py`、`check_runtime_readiness.py`、`run_platform_smoke.py` |
| 类型检查环境 | `run_project_mypy.py`：为 pre-commit 定位已安装项目依赖的 Python 3.11/Conda 解释器 |
| 数据准入 | `admit_hospital_data_batch.py`、`verify_three_priority_dataset_manifests.py` |
| 证据与报告 | `build_competition_evidence_index.py`、`run_competition_flow_demo_check.py` |
| 性能与压力 | `benchmark_core_hotpaths.py`、`run_official_4k_pressure_smoke.py` |
| 维护 | `audit_active_documentation.py`、`clean_workspace.py` |

补充分类：

- `download_*.py`：受控获取公开或近似数据；下载结果需带来源、许可、哈希和用途边界。
- `materialize_*.py`、`build_*_manifest.py`：把原始或公开数据转换为可审计的代理数据、训练清单或展示证据。
- `run_*_validation.py`、`run_*_gate.py`：对运行边界、配准验证或候选模型执行可复核门控。
- `build_challenge_cup_figures.py`、`build_challenge_cup_report.py`：生成挑战杯报告图包和聚合交付稿；图包以报告包内的 `assets/sources/` 为最小重建输入，构建完成后更新 SHA256 manifest。对应说明位于 `research/reports/submission/challenge_cup_report_draft_20260721/README.md`。

所有工具应保留输入来源、配置、哈希、失败原因和安全边界。清理工具只允许在校验过的仓库根目录内删除缓存及 E2E、UI 等明确可丢弃产物；病例库、人工标注、smoke 证据、检索材料、训练运行和数据集目录始终排除。执行清理时，活动进程锁定的日志或目录会作为失败项写入 JSON，其他候选仍继续处理；命令以退出码 `1` 提示存在未清理项。
