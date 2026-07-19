# 早期框架检查脚本归档

归档日期：2026-07-19。

本目录保存通用医学影像框架阶段的 `check_env.py` 与 `check_all.py`，仅用于历史追溯。脚本包含 fixture、V3 实验和早期 Gradio 入口假设，已退出当前平台质量门。

当前检查入口：

- `make docs-audit`：活动文档、版本和本地链接。
- `make check-all`：静态检查、类型检查及核心、后端、前端测试。
- `make readiness`：比赛严格配置、模型和运行环境就绪检查。
- `make performance-baseline`：核心热路径性能与输出一致性基准。
