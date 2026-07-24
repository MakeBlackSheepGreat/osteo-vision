# 工程脚本

`scripts/` 保存可复现的训练、评估、数据转换、模型清单和平台启动脚本。

- `start_platform.ps1`：启动 FastAPI 与 Vue 工作站，并执行严格运行预检；传入 `-StartThreeDRuntime` 时会额外尝试启动独立三维渲染运行时，渲染运行时故障只记录警告，主平台继续可用。
- `start_three_d_runtime.ps1`：单独启动 `frontend/three-d-runtime` 的三维渲染运行时，默认端口 `5175`。该脚本会检查后端健康状态、运行时包的本地依赖完整性、主页面端口隔离和运行时标识；`-PreflightOnly` 与 `-SkipBackendCheck` 支持无副作用启动器检查。
- `train_*.py`、`benchmark_*.py`、`evaluate_*.py`：研发训练、候选比较和独立评估。
- `preprocess_*.py`、`convert_*.py`：公开或代理数据的受控预处理。
- `model_inventory.py`、`generate_model_checkpoint_manifest.py`：模型来源、权重和用途边界记录。
- `generate_thesis_docx.py`：论文或可行性材料的 DOCX 生成入口；图片仅从报告包内的相对路径读取，缺图时直接失败并以临时文件原子替换交付件。挑战杯图包与报告聚合入口位于 `tools/`。
- `archive/`：已退出活动入口的框架检查脚本，仅用于追溯。

脚本默认把运行产物写入 `artifacts/` 或临时目录。涉及真实患者、医院或企业数据时，先执行批次准入与脱敏检查。

下载、数据物化、平台 smoke、证据图生成和报告汇总属于受控核验工作流，统一进入 `tools/`。新增脚本时按“训练或评估流程进入 `scripts/`，前置检查、数据治理、可运行性验证与交付证据进入 `tools/`”归类，避免同一职责出现多个入口。

独立三维渲染运行时的启动、构建、测试和部署边界见 [three_d_renderer_runtime.md](../docs/three_d_renderer_runtime.md)。
