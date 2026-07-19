# 架构概述

> 归档于 2026-07-19。本文记录通用医学影像框架阶段的分层与 V1/V2/V3 命名，仅用于追溯。当前平台架构以 `docs/development_framework.md`、`docs/project_structure.md` 和实际代码为准。

本工程是一个用于颌骨骨髓炎智能化荧光诊疗项目的医学影像比赛版平台框架。它将可复用的框架能力与疾病特定配置、模型适配器分离。

## 分层架构

框架采用分层架构，每层都有明确的职责：

### 核心层 (`src/core/`)

- **配置管理**：配置加载、验证和管理
- **注册表**：组件注册和发现
- **契约**：核心接口和协议
- **数据模式**：数据模型定义
- **警告管理**：警告和错误管理

### 数据集层 (`src/datasets/`)

- **清单**：数据集清单读取和验证
- **分割**：数据分割策略
- **泄露检测**：数据泄露检测

### 引擎层 (`src/engine/`)

- **推理**：单例推理服务
- **实验**：实验执行和管理
- **基准测试**：基准评估
- **训练**：模型训练编排

### 模型层 (`src/models/`)

- **适配器**：模型适配器接口和实现
- **注册表**：模型注册和发现
- **分类器**：Fixture 分类模型
- **分割器**：Fixture 分割模型
- **检测器**：Fixture 检测模型

### 流水线层 (`src/pipelines/`)

- **基础**：流水线基础上下文
- **分类**：分类流水线
- **分割**：分割流水线
- **检测**：检测流水线
- **量化**：量化流水线
- **多任务**：多任务流水线

### 预处理层 (`src/preprocess/`)

- **输入验证**：输入类型检测和验证
- **图像质量**：图像质量评估
- **CT 预处理**：CT 特定预处理
- **掩码后处理**：掩码后处理
- **ROI**：感兴趣区域处理

### 报告层 (`src/reports/`)

- **单例**：单例报告生成
- **基准测试**：基准报告生成
- **写入器**：报告写入工具
- **验证器**：报告验证

### 工具层 (`src/utils/`)

- **日志**：统一日志系统
- **运行时**：运行时环境和设备管理

## 数据流

```text
输入路径
  -> 输入验证
  -> 任务包和模型适配器选择
  -> 选择的流水线
  -> Fixture 或配置的模型适配器
  -> PredictionResult
  -> 单例报告
```

基准测试读取清单并为每一行重复相同的 `diagnose()` 调用。V2 将运行证据写入 `artifacts/runs/<run_id>/`，包括配置、清单、任务包和模型规范快照。

## V3 实验流程

```text
ExperimentSpec
  -> 任务包、清单和模型规范验证
  -> 固定分割、患者级别 k 折或外部分配
  -> 确定性 fixture 折评分
  -> OOF 预测和折指标
  -> 阈值分析
  -> 模型卡和检查点清单
  -> 推广门控
  -> 运行时推广草案
```

`scripts/promote_model.py` 从 `promotion_record.json` 写入补丁草案。它保持 `configs/inference/osteo_vision.yml` 不变，以便运行时推广保持可审查。

## 模型适配器边界

V2 不下载或捆绑模型权重。高级模型系列表示为具有状态检查的本地适配器：

- `fixture`：测试和演示的确定性回退。
- `timm_classifier`：2D 或 2.5D 分类主干。
- `monai_bundle`：MONAI Bundle 或 Model Zoo 包。
- `nnunet_v2`：分割比赛基线。
- `medsam_like`：MedSAM、MedSAM2 或 SAM2 风格的医学分割。
- `vista3d_like`：3D 分割基础模型接口。
- `vlm_encoder`：BiomedCLIP、Rad-DINO、MedImageInsight 风格的编码器。

## 安全边界

该框架是研发验证版平台。报告包含免责声明，不将结果作为临床诊断呈现。

## 契约接口

框架为所有主要组件定义了契约（接口）：

- **核心契约** (`src/core/contracts/`)：配置加载器、注册表、日志、生命周期
- **数据集契约** (`src/datasets/contracts/`)：数据集加载器、分割策略、清单读取器
- **模型契约** (`src/models/contracts/`)：模型适配器、模型注册表、检查点管理器
- **流水线契约** (`src/pipelines/contracts/`)：流水线、流水线注册表、流水线步骤
- **预处理契约** (`src/preprocess/contracts/`)：预处理器、输入验证器、后处理器
- **引擎契约** (`src/engine/contracts/`)：推理服务、实验运行器、基准评估器
- **报告契约** (`src/reports/contracts/`)：报告生成器、报告写入器、报告验证器

## 技能规则库

框架包含一个技能规则库，用于 AI 代理。详见 [.rules/README.md](../.rules/README.md)。

## 类型安全

框架使用 mypy 进行静态类型检查。配置：`mypy.ini`

```bash
# 运行类型检查
mypy src/

# 使用严格模式运行
mypy --strict src/
```


## V1 Platform Boundary Update

The platform target is now implemented as a split frontend/backend workbench:

- `frontend/` contains the Vue 3 review surface.
- `backend/` contains the FastAPI orchestration layer.
- `src/` continues to host shared analysis, preprocessing, and report utilities.
- Case workflows are local-first and evidence-oriented.
- Exported bundles carry disclaimers and review-state context.
