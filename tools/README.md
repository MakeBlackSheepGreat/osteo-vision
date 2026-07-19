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

所有工具应保留输入来源、配置、哈希、失败原因和安全边界。清理工具只允许在校验过的仓库根目录内删除缓存及 E2E、UI 等明确可丢弃产物；病例库、人工标注、smoke 证据、检索材料、训练运行和数据集目录始终排除。执行清理时，活动进程锁定的日志或目录会作为失败项写入 JSON，其他候选仍继续处理；命令以退出码 `1` 提示存在未清理项。
