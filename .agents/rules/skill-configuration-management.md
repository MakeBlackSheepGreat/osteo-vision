# 配置管理技能

## 触发条件

命中任意一条即应阅读本文件：

- 新建配置文件
- 修改现有配置
- 涉及任务配置、模型配置、流水线配置
- 修改 `configs/` 目录下的文件
- 涉及配置加载、配置验证、配置合并

## 背景知识

配置管理是框架的核心基础设施，负责管理所有可配置的参数。常见配置类型包括：

1. **任务配置**：定义任务的输入输出契约、流水线、指标等
2. **推理配置**：定义推理服务的运行时参数、模型列表等
3. **路径配置**：定义各种路径的映射关系
4. **模型配置**：定义模型的参数、检查点路径等

## 当前实现模式

### 目录结构

```
configs/
├── inference/
│   └── demo.yml                    # 推理配置示例
├── tasks/
│   ├── breast_ultrasound_classification.example.yml  # 乳腺超声分类任务
│   ├── ct_nodule_risk.example.yml                    # CT 结节风险任务
│   ├── generic_segmentation.example.yml              # 通用分割任务
│   └── medical_demo.yml                  # 医学研发演示任务
└── paths.example.yml                               # 路径配置示例
```

### 核心配置文件

#### 推理配置 (`configs/inference/demo.yml`)

```yaml
paths_config: configs/paths.example.yml
runtime:
  model_version: micf-fixture-v0
  framework_version: v2
  task_package: configs/tasks/medical_demo.yml
  default_task_type: classification
  default_threshold: 0.5
  low_confidence_margin: 0.1
  device_policy: auto
  use_fixture_model: true
  checkpoint_path: artifacts/checkpoints/demo_model.pt
  allow_fixture_on_missing_checkpoint: true
  model_selection_policy: fixture_fallback
  disclaimer: Platform software for research and engineering validation...
  models:
    - model_id: biomedclip_zero_shot
      family: vlm_encoder
      task_types: [classification]
      input_types: [2d_image]
      spatial_dims: [2]
      checkpoint_path: artifacts/checkpoints/biomedclip.pt
      # ... 其他参数
  tasks:
    classification:
      pipeline: classification
      class_labels:
        negative: negative
        positive: positive
      risk_mapping:
        low: [0.0, 0.33]
        medium: [0.33, 0.66]
        high: [0.66, 1.0]
    segmentation:
      pipeline: segmentation
      mask_threshold: 0.5
    # ... 其他任务
```

#### 任务配置 (`configs/tasks/medical_demo.yml`)

```yaml
task_id: medical_demo
task_name: Medical Imaging Platform Demo
modality: generic
input_contract:
  input_types: [2d_image, npz_roi, dicom_series, nifti_volume]
  required_manifest_columns: [case_id, input_path, label, task_type, input_type]
  optional_manifest_columns: [patient_id, split, fold, label_source, modality, ...]
label_contract:
  type: binary_or_missing
  positive_label: 1
  negative_label: 0
pipelines: [classification, segmentation, detection, quantification, multitask]
metrics: [accuracy, sensitivity, specificity, precision, f1, dice, iou]
demo_outputs: [prediction, probability, class_label, risk_level, ...]
benchmark_contract:
  manifest_version: v2
  patient_level_split_recommended: true
  threshold_analysis_required_when_labeled: true
recommended_models:
  - model_id: biomedclip_zero_shot
    family: vlm_encoder
  # ... 其他模型
safety:
  disclaimer_required: true
  clinical_claim_allowed: false
  user_upload_policy: transient_inference_only
```

### 配置加载

```python
from osteo_vision_core.core.config import load_yaml, runtime_config, config_hash

# 加载配置
config = load_yaml("configs/inference/demo.yml")

# 获取运行时配置
runtime = runtime_config(config)

# 计算配置哈希
hash_value = config_hash("configs/inference/demo.yml")
```

## 标准实现模式

### 新建任务配置

```yaml
# configs/tasks/my_task.yml

# 1. 任务元数据
task_id: my_task_001
task_name: My Custom Task
modality: ct  # ct, mri, xray, ultrasound, generic

# 2. 输入契约
input_contract:
  input_types: [2d_image, dicom_series, nifti_volume]
  required_manifest_columns: [case_id, input_path, label, task_type, input_type]
  optional_manifest_columns: [patient_id, split, fold, metadata_path]
  max_file_size_mb: 500
  accepted_extensions: [.png, .jpg, .dcm, .nii, .nii.gz]

# 3. 标签契约
label_contract:
  type: binary  # binary, multiclass, multilabel, regression, missing
  positive_label: 1
  negative_label: 0
  classes: [negative, positive]  # 多分类时使用
  num_classes: 2

# 4. 流水线配置
pipelines: [classification, segmentation]
pipeline_configs:
  classification:
    threshold: 0.5
    low_confidence_margin: 0.1
  segmentation:
    mask_threshold: 0.5
    min_component_size: 100

# 5. 评估指标
metrics:
  - accuracy
  - sensitivity
  - specificity
  - precision
  - f1
  - auc_roc
  - dice  # 分割任务
  - iou   # 分割任务

# 6. 基准测试契约
benchmark_contract:
  manifest_version: v2
  patient_level_split_recommended: true
  threshold_analysis_required_when_labeled: true
  cross_validation_folds: 5
  stratified_sampling: true

# 7. 推荐模型
recommended_models:
  - model_id: my_model_v1
    family: my_framework
    task_types: [classification]
    input_types: [2d_image]
    priority: 1
  - model_id: my_model_v2
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

### 新建推理配置

```yaml
# configs/inference/my_config.yml

# 1. 路径配置
paths_config: configs/paths.example.yml

# 2. 运行时配置
runtime:
  # 版本信息
  model_version: my_model_v1
  framework_version: v2

  # 任务配置
  task_package: configs/tasks/my_task.yml
  default_task_type: classification
  default_threshold: 0.5
  low_confidence_margin: 0.1

  # 设备配置
  device_policy: auto  # auto, cpu, gpu, multi_gpu
  gpu_ids: [0]
  max_batch_size: 32

  # 模型配置
  use_fixture_model: false
  checkpoint_path: artifacts/checkpoints/my_model.pt
  allow_fixture_on_missing_checkpoint: true
  model_selection_policy: fixture_fallback  # fixture_fallback, explicit, best_available

  # 性能配置
  num_workers: 4
  prefetch_factor: 2
  pin_memory: true

  # 声明
  disclaimer: Platform software for research and engineering validation. This result is not a clinical diagnosis and must not replace physician review.

  # 模型列表
  models:
    - model_id: my_model_v1
      family: my_framework
      task_types: [classification]
      input_types: [2d_image]
      spatial_dims: [2]
      checkpoint_path: artifacts/checkpoints/my_model.pt
      source_url: https://example.com/my_model
      license: MIT
      dependency_group: my_framework
      device_policy: auto
      precision: fp16
      enabled: true
      intended_use: platform validation workflow
      clinical_claim_allowed: false

  # 任务配置
  tasks:
    classification:
      pipeline: classification
      class_labels:
        negative: negative
        positive: positive
      risk_mapping:
        low: [0.0, 0.33]
        medium: [0.33, 0.66]
        high: [0.66, 1.0]
    segmentation:
      pipeline: segmentation
      mask_threshold: 0.5

# 3. 输入配置
input:
  accepted_image_extensions: [.png, .jpg, .jpeg, .tif, .tiff]
  accepted_npz_extensions: [.npz]
  accepted_dicom_extensions: [.dcm]
  accepted_nifti_extensions: [.nii, .nii.gz]
  max_file_size_mb: 500

# 4. 报告配置
reports:
  output_dir: artifacts/reports
  visual_dir: artifacts/visual_evidence
  generate_html: true
  generate_json: true
  generate_csv: true

# 5. 基准测试配置
benchmark:
  output_dir: artifacts/reports/benchmark
  save_predictions: true
  save_metrics: true
  save_plots: true
```

## 注意事项

1. **使用 YAML 格式**：所有配置文件必须使用 YAML 格式，便于人类阅读和编辑
2. **保持向后兼容**：修改配置结构时，保持旧配置可用或提供迁移路径
3. **提供默认值**：为可选配置提供合理默认值，减少配置文件冗余
4. **验证配置**：在加载配置时验证必需字段、类型、取值范围
5. **文档化配置**：为每个配置项提供清晰的注释和说明
6. **分离关注点**：将不同类型的配置放在不同的文件中
7. **使用相对路径**：配置中的路径使用相对于项目根目录的相对路径
8. **避免敏感信息**：不要在配置文件中存储密码、密钥等敏感信息

## 相关文件

- `osteo_vision_core/core/config.py`：配置加载和处理
- `osteo_vision_core/core/schemas.py`：数据模式定义
- `configs/inference/demo.yml`：推理配置示例
- `configs/tasks/*.yml`：任务配置示例
- `configs/paths.example.yml`：路径配置示例
