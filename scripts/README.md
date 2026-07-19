# 工程脚本

`scripts/` 保存可复现的训练、评估、数据转换、模型清单和平台启动脚本。

- `start_platform.ps1`：启动 FastAPI 与 Vue 工作站，并执行严格运行预检。
- `train_*.py`、`benchmark_*.py`、`evaluate_*.py`：研发训练、候选比较和独立评估。
- `preprocess_*.py`、`convert_*.py`、`materialize_*.py`：公开或代理数据的受控预处理。
- `model_inventory.py`、`generate_model_checkpoint_manifest.py`：模型来源、权重和用途边界记录。
- `archive/`：已退出活动入口的框架检查脚本，仅用于追溯。

脚本默认把运行产物写入 `artifacts/` 或临时目录。涉及真实患者、医院或企业数据时，先执行批次准入与脱敏检查。
