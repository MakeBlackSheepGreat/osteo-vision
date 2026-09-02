# 数据预处理技能

## 触发条件

命中任意一条即应阅读本文件：

- 新建数据预处理流水线
- 涉及 CT、MRI、X 光等医学影像预处理
- 涉及数据增强、归一化、重采样等操作
- 修改 `osteo_vision_core/preprocess/` 目录下的文件
- 涉及输入验证、图像质量评估、掩码后处理

## 背景知识

医学影像预处理是平台流水线的关键环节，直接影响模型性能。常见预处理操作包括：

1. **输入验证**：检查文件格式、大小、完整性
2. **图像质量评估**：检查分辨率、对比度、噪声水平
3. **格式转换**：DICOM → NumPy、NIfTI → NumPy、PNG/JPG → NumPy
4. **归一化**：HU 值窗宽窗位调整、Z-score 标准化、Min-Max 归一化
5. **重采样**：统一体素间距、调整图像尺寸
6. **数据增强**：随机旋转、翻转、缩放、弹性形变
7. **掩码后处理**：阈值化、连通组件分析、孔洞填充

## 当前实现模式

### 目录结构

```
osteo_vision_core/preprocess/
├── __init__.py
├── ct_preprocess.py      # CT 特定预处理（HU 转换、窗宽窗位）
├── image_quality.py      # 图像质量评估
├── input_validation.py   # 输入验证和类型检测
├── mask_postprocess.py   # 掩码后处理
└── roi.py                # 感兴趣区域处理
```

### 核心函数

#### 输入验证 (`input_validation.py`)

```python
from osteo_vision_core.preprocess.input_validation import validate_input, detect_input_type

# 检测输入类型
input_type = detect_input_type("path/to/image.png")
# 返回: "2d_image", "dicom_series", "npz_roi", "nifti_volume", "unknown"

# 验证输入并获取摘要
summary = validate_input("path/to/image.png")
# 返回: InputSummary(path=..., input_type=..., accepted=..., reason=..., metadata=..., warnings=...)
```

#### 图像质量评估 (`image_quality.py`)

```python
from osteo_vision_core.preprocess.image_quality import assess_basic_quality

# 评估图像基本质量
accepted, reason = assess_basic_quality("path/to/image.png", "2d_image")
# 返回: (True, "") 或 (False, "error message")
```

#### CT 预处理 (`ct_preprocess.py`)

```python
from osteo_vision_core.preprocess.ct_preprocess import ct_preprocess_summary

# 获取 CT 预处理摘要
summary = ct_preprocess_summary(metadata)
# 返回: {"hu_conversion": "...", "spacing": "...", "windowing": "..."}
```

#### 掩码后处理 (`mask_postprocess.py`)

```python
from osteo_vision_core.preprocess.mask_postprocess import postprocess_mask_summary

# 获取掩码后处理摘要
summary = postprocess_mask_summary(mask, threshold=0.5)
# 返回: {"threshold": 0.5, "largest_component": False, "source": "..."}
```

## 标准实现模式

### 新建预处理器

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from osteo_vision_core.core.schemas import InputSummary
from osteo_vision_core.core.warnings import STATUS_INVALID_INPUT, warning


class MyPreprocessor:
    """自定义预处理器示例"""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def preprocess(self, input_path: str | Path) -> dict[str, Any]:
        """
        预处理输入数据

        Args:
            input_path: 输入文件路径

        Returns:
            预处理结果字典，包含:
            - data: 预处理后的数据
            - metadata: 元数据
            - warnings: 警告列表
        """
        p = Path(input_path)
        warnings: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}

        # 1. 验证输入
        if not p.exists():
            warnings.append(warning(STATUS_INVALID_INPUT, "File not found", True))
            return {"data": None, "metadata": metadata, "warnings": warnings}

        # 2. 读取数据
        data = self._load_data(p)

        # 3. 执行预处理
        data = self._normalize(data)
        data = self._resize(data)

        # 4. 收集元数据
        metadata = {
            "original_shape": data.shape,
            "dtype": str(data.dtype),
            "preprocessing_steps": ["normalize", "resize"],
        }

        return {"data": data, "metadata": metadata, "warnings": warnings}

    def _load_data(self, path: Path) -> Any:
        """加载数据"""
        # 实现数据加载逻辑
        raise NotImplementedError

    def _normalize(self, data: Any) -> Any:
        """归一化"""
        # 实现归一化逻辑
        return data

    def _resize(self, data: Any) -> Any:
        """调整尺寸"""
        # 实现尺寸调整逻辑
        return data
```

### 集成到输入验证流程

```python
from osteo_vision_core.preprocess.input_validation import validate_input

# 在 validate_input 中集成自定义预处理
def validate_and_preprocess(path: str | Path) -> tuple[InputSummary, dict[str, Any]]:
    # 1. 基础验证
    summary = validate_input(path)

    # 2. 如果验证通过，执行预处理
    preprocessed = None
    if summary.accepted:
        preprocessor = MyPreprocessor()
        preprocessed = preprocessor.preprocess(path)

    return summary, preprocessed
```

## 注意事项

1. **保持可复用性**：预处理步骤应设计为独立的函数或类，避免写死单一平台的逻辑
2. **支持多种输入格式**：预处理器应支持 DICOM、NIfTI、PNG/JPG、NPZ 等多种格式
3. **处理异常情况**：对文件不存在、格式错误、内存不足等情况进行优雅处理
4. **记录预处理日志**：使用 `osteo_vision_core.utils.logging` 记录预处理步骤和结果
5. **保持向后兼容**：修改现有预处理函数时，保持接口不变或提供迁移路径
6. **性能考虑**：大数据集预处理应考虑内存使用和计算效率
7. **可复现性**：预处理步骤应确定性可复现，避免随机性（除非明确需要数据增强）

## 相关文件

- `osteo_vision_core/preprocess/__init__.py`：预处理模块入口
- `osteo_vision_core/preprocess/input_validation.py`：输入验证
- `osteo_vision_core/preprocess/image_quality.py`：图像质量评估
- `osteo_vision_core/preprocess/ct_preprocess.py`：CT 预处理
- `osteo_vision_core/preprocess/mask_postprocess.py`：掩码后处理
- `osteo_vision_core/preprocess/roi.py`：感兴趣区域处理
- `osteo_vision_core/core/schemas.py`：数据模式定义
- `osteo_vision_core/core/warnings.py`：警告管理
