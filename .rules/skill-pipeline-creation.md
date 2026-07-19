# 流水线创建技能

## 触发条件

命中任意一条即应阅读本文件：

- 新建处理流水线
- 涉及分类、检测、分割等任务
- 需要组合多个处理步骤
- 修改 `src/pipelines/` 目录下的文件
- 涉及流水线注册、流水线配置、流水线执行

## 背景知识

流水线是框架的核心执行单元，负责将预处理、模型推理、后处理等步骤组合成完整的处理流程。常见流水线类型包括：

1. **分类流水线**：输入图像 → 预处理 → 分类模型 → 后处理 → 输出类别和概率
2. **分割流水线**：输入图像 → 预处理 → 分割模型 → 后处理 → 输出掩码
3. **检测流水线**：输入图像 → 预处理 → 检测模型 → 后处理 → 输出边界框
4. **量化流水线**：输入图像 → 预处理 → 回归模型 → 后处理 → 输出数值
5. **多任务流水线**：组合多个流水线，同时执行多种任务

## 当前实现模式

### 目录结构

```
src/pipelines/
├── __init__.py
├── base.py              # 流水线基类（Pipeline、PipelineContext）
├── classification.py    # 分类流水线
├── detection.py         # 检测流水线
├── multitask.py         # 多任务流水线
├── quantification.py    # 量化流水线
└── segmentation.py      # 分割流水线
```

### 核心接口

#### PipelineContext (`base.py`)

```python
from dataclasses import dataclass
from typing import Any
from src.core.schemas import InputSummary

@dataclass
class PipelineContext:
    case_id: str                    # 病例 ID
    input_summary: InputSummary     # 输入摘要
    runtime: dict[str, Any]         # 运行时配置
    task_config: dict[str, Any]     # 任务配置
    models: dict[str, Any]          # 模型字典
    adapter_result: dict[str, Any] | None = None  # 适配器结果
```

#### Pipeline 基类 (`base.py`)

```python
from src.pipelines.base import Pipeline, PipelineContext

class Pipeline:
    task_type = "base"

    def run(self, context: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError
```

### 现有流水线实现

#### 分类流水线 (`classification.py`)

```python
from src.pipelines.classification import ClassificationPipeline

# 使用示例
pipeline = ClassificationPipeline()
result = pipeline.run(context)
# 返回: {"prediction": {...}, "probability": 0.8, "score": 0.8, "class_label": "positive", ...}
```

#### 分割流水线 (`segmentation.py`)

```python
from src.pipelines.segmentation import SegmentationPipeline

# 使用示例
pipeline = SegmentationPipeline()
result = pipeline.run(context)
# 返回: {"segmentation_mask": {...}, "lesion_evidence": {...}, "quantification": {...}, ...}
```

#### 检测流水线 (`detection.py`)

```python
from src.pipelines.detection import DetectionPipeline

# 使用示例
pipeline = DetectionPipeline()
result = pipeline.run(context)
# 返回: {"lesion_evidence": {...}, "prediction": {...}, "score": 0.9, ...}
```

#### 多任务流水线 (`multitask.py`)

```python
from src.pipelines.multitask import MultitaskPipeline

# 使用示例
pipeline = MultitaskPipeline()
result = pipeline.run(context)
# 返回: 组合多个流水线的结果
```

## 标准实现模式

### 新建流水线

```python
from __future__ import annotations

from typing import Any

from src.core.warnings import STATUS_INVALID_INPUT, warning
from src.pipelines.base import Pipeline, PipelineContext


class MyPipeline(Pipeline):
    """自定义流水线示例"""

    task_type = "my_task"

    def run(self, context: PipelineContext) -> dict[str, Any]:
        """
        执行流水线

        Args:
            context: 流水线上下文

        Returns:
            流水线结果字典
        """
        warnings: list[dict[str, Any]] = []
        prediction: dict[str, Any] = {}

        # 1. 验证输入
        if not context.input_summary.accepted:
            warnings.append(warning(STATUS_INVALID_INPUT, "Input validation failed", True))
            return {"prediction": prediction, "warnings": warnings}

        # 2. 获取配置
        threshold = float(context.task_config.get("threshold", 0.5))

        # 3. 执行预处理（可选）
        preprocessed = self._preprocess(context)

        # 4. 执行模型推理
        if context.adapter_result:
            # 使用适配器结果
            prediction = context.adapter_result.get("prediction", {})
        else:
            # 使用本地模型
            prediction = self._run_model(context, preprocessed)

        # 5. 执行后处理
        prediction = self._postprocess(prediction, threshold)

        # 6. 构建结果
        return {
            "prediction": prediction,
            "probability": prediction.get("probability"),
            "score": prediction.get("score"),
            "class_label": prediction.get("label"),
            "risk_level": prediction.get("risk_level"),
            "warnings": warnings,
        }

    def _preprocess(self, context: PipelineContext) -> dict[str, Any]:
        """
        预处理

        Args:
            context: 流水线上下文

        Returns:
            预处理结果
        """
        # 实现预处理逻辑
        return {}

    def _run_model(self, context: PipelineContext, preprocessed: dict[str, Any]) -> dict[str, Any]:
        """
        执行模型推理

        Args:
            context: 流水线上下文
            preprocessed: 预处理结果

        Returns:
            模型预测结果
        """
        # 实现模型推理逻辑
        return {}

    def _postprocess(self, prediction: dict[str, Any], threshold: float) -> dict[str, Any]:
        """
        后处理

        Args:
            prediction: 模型预测结果
            threshold: 阈值

        Returns:
            后处理结果
        """
        # 实现后处理逻辑
        return prediction
```

### 注册流水线

```python
from src.engine.inference import PIPELINE_CLASSES
from src.pipelines.my_pipeline import MyPipeline

# 注册到流水线类映射
PIPELINE_CLASSES["my_task"] = MyPipeline
```

### 在配置中使用

```yaml
# configs/inference/demo.yml
runtime:
  tasks:
    my_task:
      pipeline: my_task
      threshold: 0.5
      other_param: value
```

## 注意事项

1. **保持接口一致**：所有流水线必须继承 `Pipeline` 基类并实现 `run` 方法
2. **使用 PipelineContext**：通过 `PipelineContext` 传递所有配置和数据，不要使用全局变量
3. **处理异常情况**：对输入无效、模型不可用等情况进行优雅处理
4. **记录警告**：使用 `warnings` 列表记录非致命问题
5. **保持可复用性**：流水线应设计为独立的、可配置的组件
6. **支持适配器结果**：如果 `context.adapter_result` 存在，优先使用适配器结果
7. **性能考虑**：避免重复计算，缓存中间结果
8. **可测试性**：流水线应易于单元测试，避免依赖外部服务

## 相关文件

- `src/pipelines/__init__.py`：流水线模块入口
- `src/pipelines/base.py`：流水线基类（Pipeline、PipelineContext）
- `src/pipelines/classification.py`：分类流水线
- `src/pipelines/segmentation.py`：分割流水线
- `src/pipelines/detection.py`：检测流水线
- `src/pipelines/quantification.py`：量化流水线
- `src/pipelines/multitask.py`：多任务流水线
- `src/core/schemas.py`：数据模式定义
- `src/core/warnings.py`：警告管理
