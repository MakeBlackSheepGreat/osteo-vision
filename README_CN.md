# osteo-vision 开发框架

本仓库是颌骨骨髓炎智能化荧光诊疗项目的正式开发工程，基于通用医学影像比赛框架模板整理而来，用于分类、分割、检测、量化、可解释性、报告、Demo 和 Benchmark 开发。

本仓库只用于科研、教学、比赛和受控演示。所有输出都不是临床诊断，不能替代医生复核。

## 已包含能力

- `configs/inference/osteo_vision.yml` 作为颌骨骨髓炎 Demo 和 Benchmark 的共同运行配置。
- `configs/tasks/` 下的 TaskPackage 用于快速生成新比赛任务。
- `MedicalImagingInferenceService` 作为唯一推理入口。
- ModelSpec 和 adapter 契约覆盖 fixture、timm、MONAI Bundle、nnU-Net v2、MedSAM-like、VISTA3D-like、VLM encoder 等模型族。
- V3 实验契约覆盖 fixture 训练闭环、评估、阈值选择、模型卡、checkpoint manifest 和 promotion 草案。
- 分类、分割、检测、量化、多任务 fixture pipeline。
- 识别 2D 图像、NPZ ROI、DICOM 序列、NIfTI 体数据。
- 单病例报告、Benchmark 报告、指标、warning、发布资产模板。
- Vue 3 + TypeScript 前端、FastAPI 后端和 legacy Gradio Demo 骨架。
- unit、smoke、integration 测试。

## 快速命令

V1 前后端分离平台：

```powershell
conda activate osteo-vision
python -m backend.src.main
```

后端默认地址：`http://127.0.0.1:8001/health`

另开一个终端启动前端：

```powershell
npm --prefix frontend run dev
```

前端默认地址：`http://127.0.0.1:5174/`

基础检查：

```powershell
python check_env.py
python -m pytest tests/unit tests/smoke
python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs
python scripts/new_task.py --task-id my_competition --template classification --output-dir configs/tasks
python scripts/new_experiment.py --experiment-id my_competition_fixture --manifest tests/fixtures/benchmark_manifest_v2.csv
python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
python scripts/promote_model.py --run-dir artifacts/runs/<run_id>
```

legacy Gradio Demo：

```powershell
python app/main.py --config configs/inference/osteo_vision.yml
```

## 二次开发方式

1. 在 `configs/tasks/` 新增 TaskPackage 比赛任务配置。
2. 选择或扩展 `src/pipelines/` 中的任务 pipeline。
3. 在 `src/models/` 中替换 fixture 模型适配器。
4. 保持 legacy Demo 和 Benchmark 都调用 `MedicalImagingInferenceService`；V1 平台后端通过服务层复用共享分析能力。
5. 正式实验输出写入 `artifacts/runs/<run_id>/`，并记录配置、任务包、模型规格、命令、指标、阈值和失败样本。

## V2 模型适配边界

V2 面向 VISTA3D、MedSAM2、nnU-Net v2、TotalSegmentator 类工作流、MONAI Bundles、BiomedCLIP、Rad-DINO、MedImageInsight 等医学影像推理模型族设计接口。本仓库不下载、不内置真实权重；缺依赖和缺权重会在 adapter status 中明确提示，fixture fallback 继续用于测试和演示。

## V3 训练闭环契约

V3 新增实验层。`ExperimentSpec` 记录任务包、manifest、模型候选、划分策略、训练配置、评估配置、阈值策略和 promotion gate。`scripts/run_experiment.py` 运行确定性 fixture 流程，并在 `artifacts/runs/<run_id>/` 写出 `training_report.json`、`evaluation_report.json`、`oof_predictions.csv`、`model_card.json`、`checkpoint_manifest.json` 和 `promotion_record.json`。

Promotion 只生成可审查草案。`scripts/promote_model.py` 读取 run 目录并输出 runtime patch draft，不会自动覆盖 `configs/inference/osteo_vision.yml`。默认 gate 会检查 patient-level 信息、泄漏风险、最低指标和安全声明。

## 安全边界

- 用户上传数据默认只用于当次推理。
- 原始医学数据、个人路径、大文件、checkpoint 不进入 Git。
- 报告必须包含研究原型免责声明。
- 不输出临床诊断承诺。
