# 比赛集成技能

## 触发条件

命中任意一条即应阅读本文件：

- 接入新比赛
- 适配新数据集
- 对接新评估协议
- 修改比赛相关逻辑
- 涉及比赛规则、数据格式、提交格式等

## 背景知识

医学影像比赛集成是框架的核心应用场景，需要处理以下关键环节：

1. **数据集适配**：不同比赛的数据格式、目录结构、标签格式各不相同
2. **评估协议对接**：不同比赛的评估指标、提交格式、评估流程各不相同
3. **模型适配**：不同比赛推荐的模型架构、预训练权重各不相同
4. **流水线配置**：不同比赛的预处理、后处理、阈值设置各不相同
5. **结果提交**：不同比赛的提交格式、文件命名、评估方式各不相同

## 当前实现模式

### 目录结构

```
configs/
├── tasks/
│   ├── breast_ultrasound_classification.example.yml  # 乳腺超声分类比赛
│   ├── ct_nodule_risk.example.yml                    # CT 结节风险比赛
│   ├── generic_segmentation.example.yml              # 通用分割比赛
│   └── medical_competition_demo.yml                  # 医学竞赛演示
└── ...

src/
├── core/
│   └── task_package.py   # 任务包加载和管理
├── datasets/
│   ├── manifests.py      # 数据清单读取
│   └── splits.py         # 数据分割
└── ...
```

### 核心函数

#### 任务包加载 (`src/core/task_package.py`)

```python
from src.core.task_package import load_task_package, default_task_package

# 加载任务包
task_package = load_task_package("configs/tasks/my_competition.yml")

# 获取默认任务包
default_package = default_task_package()
```

#### 数据清单读取 (`src/datasets/manifests.py`)

```python
from src.datasets.manifests import read_manifest

# 读取数据清单
rows, info = read_manifest("path/to/manifest.csv")
# rows: [{"case_id": "...", "input_path": "...", "label": "...", ...}, ...]
# info: {"total_rows": 100, "columns": [...], "optional_columns_present": [...]}
```

#### 数据分割 (`src/datasets/splits.py`)

```python
from src.datasets.splits import patient_leakage_report

# 检查数据泄露
leakage = patient_leakage_report(rows)
# 返回: {"leakage_detected": False, "reason": "...", ...}
```

## 标准实现模式

### 接入新比赛

#### 1. 创建任务配置

```yaml
# configs/tasks/my_new_competition.yml

# 1. 任务元数据
task_id: my_new_competition
task_name: My New Competition
modality: ct  # ct, mri, xray, ultrasound, generic

# 2. 输入契约
input_contract:
  input_types: [dicom_series, nifti_volume]
  required_manifest_columns: [case_id, input_path, label, task_type, input_type]
  optional_manifest_columns: [patient_id, split, fold, metadata_path]
  accepted_extensions: [.dcm, .nii, .nii.gz]
  max_file_size_mb: 1000

# 3. 标签契约
label_contract:
  type: multiclass
  classes: [benign, malignant, uncertain]
  num_classes: 3
  positive_label: malignant
  negative_label: benign

# 4. 流水线配置
pipelines: [classification, segmentation]
pipeline_configs:
  classification:
    threshold: 0.5
    low_confidence_margin: 0.15
  segmentation:
    mask_threshold: 0.5
    min_component_size: 50

# 5. 评估指标
metrics:
  - accuracy
  - sensitivity
  - specificity
  - precision
  - f1
  - auc_roc
  - dice
  - iou

# 6. 基准测试契约
benchmark_contract:
  manifest_version: v2
  patient_level_split_recommended: true
  threshold_analysis_required_when_labeled: true
  cross_validation_folds: 5
  stratified_sampling: true
  submission_format: csv  # csv, json, nifti, dicom
  submission_columns: [case_id, prediction, probability]

# 7. 推荐模型
recommended_models:
  - model_id: my_ct_classifier
    family: my_framework
    task_types: [classification]
    input_types: [dicom_series, nifti_volume]
    priority: 1
  - model_id: my_ct_segmenter
    family: my_framework
    task_types: [segmentation]
    input_types: [dicom_series, nifti_volume]
    priority: 2

# 8. 安全配置
safety:
  disclaimer_required: true
  clinical_claim_allowed: false
  user_upload_policy: transient_inference_only
  data_retention_hours: 24
  anonymize_logs: true
```

#### 2. 创建数据清单

```csv
case_id,input_path,label,task_type,input_type,patient_id
case_001,/data/my_competition/images/case_001.nii.gz,1,classification,nifti_volume,patient_001
case_002,/data/my_competition/images/case_002.nii.gz,0,classification,nifti_volume,patient_002
case_003,/data/my_competition/images/case_003.nii.gz,1,classification,nifti_volume,patient_003
```

#### 3. 创建推理配置

```yaml
# configs/inference/my_competition.yml

paths_config: configs/paths.example.yml

runtime:
  model_version: my_competition_v1
  framework_version: v2
  task_package: configs/tasks/my_new_competition.yml
  default_task_type: classification
  default_threshold: 0.5
  low_confidence_margin: 0.15
  device_policy: auto
  use_fixture_model: false
  checkpoint_path: artifacts/checkpoints/my_ct_classifier.pt
  allow_fixture_on_missing_checkpoint: true
  model_selection_policy: fixture_fallback

  models:
    - model_id: my_ct_classifier
      family: my_framework
      task_types: [classification]
      input_types: [dicom_series, nifti_volume]
      spatial_dims: [3]
      checkpoint_path: artifacts/checkpoints/my_ct_classifier.pt
      source_url: https://example.com/my_ct_classifier
      license: MIT
      dependency_group: my_framework
      device_policy: auto
      precision: fp16
      enabled: true
      intended_use: competition platform workflow
      clinical_claim_allowed: false

  tasks:
    classification:
      pipeline: classification
      class_labels:
        benign: benign
        malignant: malignant
        uncertain: uncertain
      risk_mapping:
        low: [0.0, 0.33]
        medium: [0.33, 0.66]
        high: [0.66, 1.0]

input:
  accepted_dicom_extensions: [.dcm]
  accepted_nifti_extensions: [.nii, .nii.gz]
  max_file_size_mb: 1000

reports:
  output_dir: artifacts/reports/my_competition
  visual_dir: artifacts/visual_evidence/my_competition

benchmark:
  output_dir: artifacts/reports/my_competition/benchmark
  save_predictions: true
  save_metrics: true
  save_plots: true
```

#### 4. 运行基准测试

```python
from src.engine.benchmark import evaluate_manifest

# 运行基准测试
result = evaluate_manifest(
    config_path="configs/inference/my_competition.yml",
    manifest_path="data/my_competition/manifest.csv",
    output_dir="artifacts/reports/my_competition/benchmark",
)

print(f"Metrics: {result['metrics']}")
print(f"Report: {result['report_path']}")
```

#### 5. 生成提交文件

```python
import csv
from pathlib import Path

def generate_submission(
    predictions_path: str,
    output_path: str,
    format: str = "csv",
) -> str:
    """
    生成比赛提交文件

    Args:
        predictions_path: 预测结果路径
        output_path: 输出路径
        format: 提交格式（csv, json）

    Returns:
        提交文件路径
    """
    # 读取预测结果
    predictions = []
    with open(predictions_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            predictions.append({
                "case_id": row["case_id"],
                "prediction": row["class_label"],
                "probability": row["probability"],
            })

    # 写入提交文件
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if format == "csv":
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["case_id", "prediction", "probability"])
            writer.writeheader()
            writer.writerows(predictions)
    elif format == "json":
        import json
        with open(output, "w") as f:
            json.dump(predictions, f, indent=2)

    return str(output)
```

## 注意事项

1. **保持通用性**：比赛集成应设计为通用的、可配置的组件，避免写死单一比赛的逻辑
2. **数据格式适配**：支持多种数据格式（DICOM、NIfTI、PNG/JPG、NPZ）
3. **评估协议对接**：支持多种评估指标和提交格式
4. **错误处理**：对数据缺失、格式错误、评估失败等情况进行优雅处理
5. **性能考虑**：大数据集应考虑内存使用和计算效率
6. **可复现性**：确保比赛结果可复现，记录所有配置和随机种子
7. **文档记录**：记录比赛集成过程，便于后续维护和复用
8. **安全合规**：确保数据处理符合比赛规则和隐私要求

## 相关文件

- `src/core/task_package.py`：任务包加载和管理
- `src/datasets/manifests.py`：数据清单读取
- `src/datasets/splits.py`：数据分割
- `src/engine/benchmark.py`：基准测试
- `src/engine/inference.py`：推理服务
- `configs/tasks/*.yml`：任务配置示例
- `configs/inference/*.yml`：推理配置示例
