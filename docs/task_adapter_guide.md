# 任务适配器指南

当适配新比赛任务时，请使用本指南。

## 添加配置

在 `configs/tasks/` 下创建任务包文件，描述模态、输入契约、标签契约、流水线、指标、演示输出、基准契约、推荐模型和安全规则。将疾病特定设置保存在此文件或专用运行时配置中。

### 任务配置示例

```yaml
# configs/tasks/my_competition.yml

# 1. 任务元数据
task_id: my_competition
task_name: My Competition
modality: ct  # ct, mri, xray, ultrasound, generic

# 2. 输入契约
input_contract:
  input_types: [dicom_series, nifti_volume]
  required_manifest_columns: [case_id, input_path, label, task_type, input_type]
  optional_manifest_columns: [patient_id, split, fold, metadata_path]

# 3. 标签契约
label_contract:
  type: binary
  positive_label: 1
  negative_label: 0

# 4. 流水线配置
pipelines: [classification, segmentation]

# 5. 评估指标
metrics: [accuracy, sensitivity, specificity, precision, f1, dice, iou]

# 6. 基准契约
benchmark_contract:
  manifest_version: v2
  patient_level_split_recommended: true
  threshold_analysis_required_when_labeled: true

# 7. 推荐模型
recommended_models:
  - model_id: my_model_v1
    family: my_framework

# 8. 安全配置
safety:
  disclaimer_required: true
  clinical_claim_allowed: false
```

## 选择流水线

- 使用 `classification` 进行类别或风险输出。
- 使用 `segmentation` 进行病灶掩码输出。
- 使用 `detection` 进行候选框或点输出。
- 使用 `quantification` 进行大小、面积、体积或形态字段输出。
- 使用 `multitask` 当演示需要同时显示多种证据类型时。

## 替换 Fixture 模型

在运行时 `models` 下添加 `ModelSpec`，然后在准备好真实推理时在 `src/models/adapters.py` 下连接模型适配器。保持 `MedicalImagingInferenceService` 作为单一入口点，以便 Demo、基准测试和模型比较保持一致。

可用适配器系列：

- `fixture`：测试和演示的确定性回退。
- `timm_classifier`：2D 或 2.5D 分类主干。
- `monai_bundle`：MONAI Bundle 或 Model Zoo 包。
- `nnunet_v2`：分割比赛基线。
- `medsam_like`：MedSAM、MedSAM2 或 SAM2 风格的医学分割。
- `vista3d_like`：3D 分割基础模型接口。
- `vlm_encoder`：BiomedCLIP、Rad-DINO、MedImageInsight 风格的编码器。

### 添加新适配器

```python
# src/models/my_adapter.py

from src.models.adapters import BaseModelAdapter
from src.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec


class MyAdapter(BaseModelAdapter):
    """自定义模型适配器"""
    
    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self.model = None
    
    def warmup(self) -> AdapterStatus:
        """检查模型是否可用"""
        # 实现检查逻辑
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=True,
            enabled=self.spec.enabled,
        )
    
    def predict(self, request: AdapterRequest) -> AdapterResult:
        """执行推理"""
        # 实现推理逻辑
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction={"label": "positive", "probability": 0.8},
            probability=0.8,
            score=0.8,
            class_label="positive",
            risk_level="high",
        )
```

注册适配器：

```python
# src/models/adapters.py

from src.models.my_adapter import MyAdapter

ADAPTER_CLASSES["my_model"] = MyAdapter
```

## 脚手架新任务

```powershell
python scripts/new_task.py --task-id my_competition --template multitask --output-dir configs/tasks
```

或者使用 Makefile：

```powershell
make new-task TASK_ID=my_competition
```

命令会生成任务包、V2 清单示例、运行时示例和 README 片段。它会拒绝覆盖现有文件。

## 添加实验契约

在任务包和清单存在后，创建 V3 实验规范：

```powershell
python scripts/new_experiment.py --experiment-id my_competition_fixture --task-package configs/tasks/my_competition.yml --manifest configs/tasks/my_competition_manifest.example.csv
python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
```

或者使用 Makefile：

```powershell
make new-experiment EXP_ID=my_competition_fixture
make run-experiment SPEC=artifacts/experiments/my_competition_fixture/experiment.yml
```

使用 `split_strategy` 进行固定分割、患者级别 k 折或外部分配。使用 `threshold_strategy` 进行固定阈值、Youden J 或敏感性优先选择。默认推广门控需要患者级别元数据、泄露检查、最低指标和安全声明。

## 证据规则

每个正式运行都应在 `artifacts/runs/<run_id>/` 下记录配置、清单、任务包、模型规范、命令、指标、阈值选择、警告、失败分析和生成的报告路径。

## 配置验证

使用配置验证器验证任务配置：

```python
from src.core.config_validator import validate_task_config

config = {
    "task_id": "my_competition",
    "task_name": "My Competition",
    "modality": "ct",
}

errors = validate_task_config(config)
if errors:
    print(f"配置错误: {errors}")
else:
    print("配置有效")
```

## 日志记录

使用统一日志系统记录任务适配过程：

```python
from src.utils.logging import get_logger

logger = get_logger(__name__)

logger.lifecycle("task_adapter", "started", task_id="my_competition")
logger.info("加载任务配置: configs/tasks/my_competition.yml")
logger.performance("config_loading", 50.2, task_id="my_competition")
logger.lifecycle("task_adapter", "completed", task_id="my_competition")
```

## 下一步

- 阅读 [架构概述](architecture.md) 了解框架设计
- 查看 [技能规则库](../.rules/README.md) 了解开发规范
- 运行 `make help` 查看所有可用命令
