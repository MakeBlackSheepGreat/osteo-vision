# 模型适配器技能

## 触发条件

命中任意一条即应阅读本文件：

- 新建模型适配器
- 集成新的深度学习模型
- 涉及模型推理、训练、评估
- 修改 `src/models/` 目录下的文件
- 涉及模型注册、模型选择、模型加载

## 背景知识

模型适配器是框架的核心组件，负责将不同来源、不同格式的模型统一到一致的接口下。常见模型类型包括：

1. **分类模型**：输出类别概率（如 BiomedCLIP、ResNet）
2. **分割模型**：输出像素级掩码（如 MedSAM、nnUNet、VISTA3D）
3. **检测模型**：输出边界框和类别（如 YOLO、Faster R-CNN）
4. **量化模型**：输出数值预测（如回归模型）
5. **多任务模型**：同时输出多种结果

## 当前实现模式

### 目录结构

```
src/models/
├── __init__.py
├── adapters.py      # 模型适配器核心（Protocol、BaseModelAdapter、具体适配器）
├── classifier.py    # 确定性分类器（fixture）
├── detector.py      # 固定检测器（fixture）
├── registry.py      # 模型注册和加载
└── segmenter.py     # 固定分割器（fixture）
```

### 核心接口

#### ModelAdapter Protocol (`adapters.py`)

```python
from typing import Protocol
from src.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec

class ModelAdapter(Protocol):
    def describe(self) -> ModelSpec: ...
    def supports(self, task_type: str, input_type: str, modality: str) -> bool: ...
    def warmup(self) -> AdapterStatus: ...
    def predict(self, request: AdapterRequest) -> AdapterResult: ...
```

#### BaseModelAdapter (`adapters.py`)

```python
from src.models.adapters import BaseModelAdapter

class MyAdapter(BaseModelAdapter):
    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
    
    def warmup(self) -> AdapterStatus:
        # 检查模型是否可用
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=True,
            enabled=self.spec.enabled,
        )
    
    def predict(self, request: AdapterRequest) -> AdapterResult:
        # 执行推理
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

### 模型选择

```python
from src.models.adapters import select_adapter, build_adapters

# 构建适配器列表
adapters = build_adapters(runtime_config)

# 选择适配器
adapter, statuses = select_adapter(
    adapters,
    task_type="classification",
    input_type="2d_image",
    modality="xray",
    policy="fixture_fallback",
)
```

### 模型注册

```python
from src.models.adapters import ADAPTER_CLASSES

# 注册新适配器
ADAPTER_CLASSES["my_model"] = MyAdapter
```

## 标准实现模式

### 新建模型适配器

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.schemas import AdapterRequest, AdapterResult, AdapterStatus, ModelSpec
from src.core.warnings import STATUS_CHECKPOINT_MISSING, warning
from src.models.adapters import BaseModelAdapter, DEPENDENCY_MODULES


class MyModelAdapter(BaseModelAdapter):
    """自定义模型适配器示例"""
    
    def __init__(self, spec: ModelSpec) -> None:
        super().__init__(spec)
        self.model = None
    
    def warmup(self) -> AdapterStatus:
        """
        检查模型是否可用
        
        Returns:
            AdapterStatus: 模型状态
        """
        reasons: list[str] = []
        warnings: list[dict[str, Any]] = []
        
        # 1. 检查是否启用
        if not self.spec.enabled:
            reasons.append("model disabled")
        
        # 2. 检查依赖
        for module in DEPENDENCY_MODULES.get(self.spec.dependency_group, []):
            try:
                __import__(module)
            except ImportError:
                reasons.append(f"missing dependency: {module}")
        
        # 3. 检查检查点
        if self.spec.checkpoint_path and not Path(self.spec.checkpoint_path).exists():
            reasons.append(f"missing checkpoint: {self.spec.checkpoint_path}")
            warnings.append(
                warning(STATUS_CHECKPOINT_MISSING, f"Missing checkpoint for {self.spec.model_id}")
            )
        
        return AdapterStatus(
            model_id=self.spec.model_id,
            family=self.spec.family,
            available=not reasons,
            enabled=self.spec.enabled,
            reasons=reasons,
            warnings=warnings,
        )
    
    def predict(self, request: AdapterRequest) -> AdapterResult:
        """
        执行推理
        
        Args:
            request: 推理请求
            
        Returns:
            AdapterResult: 推理结果
        """
        # 1. 检查模型是否可用
        status = self.warmup()
        if not status.available:
            return AdapterResult(
                model_id=self.spec.model_id,
                model_family=self.spec.family,
                prediction={"available": False, "reason": "; ".join(status.reasons)},
                warnings=status.warnings,
            )
        
        # 2. 加载模型（如果尚未加载）
        if self.model is None:
            self._load_model()
        
        # 3. 执行推理
        prediction = self._run_inference(request)
        
        # 4. 构建结果
        return AdapterResult(
            model_id=self.spec.model_id,
            model_family=self.spec.family,
            prediction=prediction,
            probability=prediction.get("probability"),
            score=prediction.get("score"),
            class_label=prediction.get("label"),
            risk_level=prediction.get("risk_level"),
        )
    
    def _load_model(self) -> None:
        """加载模型"""
        # 实现模型加载逻辑
        raise NotImplementedError
    
    def _run_inference(self, request: AdapterRequest) -> dict[str, Any]:
        """执行推理"""
        # 实现推理逻辑
        raise NotImplementedError
```

### 注册适配器

```python
from src.models.adapters import ADAPTER_CLASSES
from src.models.my_adapter import MyModelAdapter

# 注册到适配器类映射
ADAPTER_CLASSES["my_model"] = MyModelAdapter
```

### 在配置中使用

```yaml
# configs/inference/demo.yml
runtime:
  models:
    - model_id: my_model_v1
      family: my_model
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
```

## 注意事项

1. **保持接口一致**：所有适配器必须实现 `ModelAdapter` Protocol 的四个方法
2. **优雅处理错误**：对模型加载失败、推理失败等情况进行优雅处理
3. **资源管理**：及时释放模型资源，避免内存泄漏
4. **设备管理**：支持 CPU/GPU 自动切换，尊重 `device_policy` 配置
5. **依赖检查**：在 `warmup()` 中检查所有必需依赖
6. **检查点验证**：验证检查点文件存在性和完整性
7. **性能考虑**：支持模型预热、批量推理、混合精度
8. **可复现性**：设置随机种子，确保推理结果可复现

## 相关文件

- `src/models/__init__.py`：模型模块入口
- `src/models/adapters.py`：模型适配器核心
- `src/models/classifier.py`：确定性分类器
- `src/models/detector.py`：固定检测器
- `src/models/segmenter.py`：固定分割器
- `src/models/registry.py`：模型注册和加载
- `src/core/schemas.py`：数据模式定义（ModelSpec、AdapterRequest、AdapterResult 等）
- `src/core/warnings.py`：警告管理
