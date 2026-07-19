# 评估指标技能

## 触发条件

命中任意一条即应阅读本文件：

- 新建评估指标
- 涉及分类、检测、分割等评估
- 需要计算准确率、召回率、F1 分数等
- 修改 `src/metrics/` 目录下的文件
- 涉及指标计算、阈值分析、结果评估

## 背景知识

评估指标是比赛框架的核心组件，用于量化模型性能。常见评估指标类型包括：

1. **分类指标**：准确率、精确率、召回率、F1 分数、AUC-ROC、敏感性、特异性
2. **分割指标**：Dice 系数、IoU（交并比）、Hausdorff 距离、平均表面距离
3. **检测指标**：召回率、精确率、mAP（平均精度均值）、FROC
4. **校准指标**：ECE（期望校准误差）、MCE（最大校准误差）、可靠性图

## 当前实现模式

### 目录结构

```
src/metrics/
├── __init__.py
├── calibration.py      # 校准指标
├── classification.py   # 分类指标
├── detection.py        # 检测指标
└── segmentation.py     # 分割指标
```

### 核心函数

#### 分类指标 (`classification.py`)

```python
from src.metrics.classification import classification_metrics, threshold_sweep

# 计算分类指标
metrics = classification_metrics(y_true, y_score, threshold=0.5)
# 返回: {"accuracy": 0.85, "sensitivity": 0.8, "specificity": 0.9, "precision": 0.85, "f1": 0.82, ...}

# 阈值扫描
sweep = threshold_sweep(y_true, y_score)
# 返回: {"available": True, "best": {"threshold": 0.45, "youden_j": 0.7}, "rows": [...]}
```

#### 分割指标 (`segmentation.py`)

```python
from src.metrics.segmentation import dice_score, iou_score

# 计算 Dice 系数
dice = dice_score(intersection=100, pred_area=200, true_area=150)
# 返回: 0.571...

# 计算 IoU
iou = iou_score(intersection=100, union=250)
# 返回: 0.4
```

#### 检测指标 (`detection.py`)

```python
from src.metrics.detection import candidate_recall

# 计算候选召回率
recall = candidate_recall(found=8, total=10)
# 返回: 0.8
```

## 标准实现模式

### 新建评估指标

```python
from __future__ import annotations

from typing import Any


def my_custom_metric(
    y_true: list[int],
    y_pred: list[float],
    threshold: float = 0.5,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    自定义评估指标示例

    Args:
        y_true: 真实标签列表
        y_pred: 预测值列表
        threshold: 分类阈值
        **kwargs: 其他参数

    Returns:
        指标结果字典
    """
    if not y_true:
        return {"available": False, "reason": "labels_missing"}

    # 1. 二值化预测
    y_binary = [1 if pred >= threshold else 0 for pred in y_pred]

    # 2. 计算基础统计
    tp = sum(1 for t, p in zip(y_true, y_binary) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_binary) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_binary) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_binary) if t == 1 and p == 0)
    total = max(1, len(y_true))

    # 3. 计算指标
    accuracy = (tp + tn) / total
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)

    # 4. 返回结果
    return {
        "available": True,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "threshold": threshold,
        "total_samples": len(y_true),
    }


def my_segmentation_metric(
    pred_mask: list[list[int]],
    true_mask: list[list[int]],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    自定义分割评估指标示例

    Args:
        pred_mask: 预测掩码
        true_mask: 真实掩码
        **kwargs: 其他参数

    Returns:
        指标结果字典
    """
    if not pred_mask or not true_mask:
        return {"available": False, "reason": "masks_missing"}

    # 1. 计算交集和并集
    intersection = 0
    pred_sum = 0
    true_sum = 0

    for pred_row, true_row in zip(pred_mask, true_mask):
        for pred_val, true_val in zip(pred_row, true_row):
            if pred_val == 1 and true_val == 1:
                intersection += 1
            if pred_val == 1:
                pred_sum += 1
            if true_val == 1:
                true_sum += 1

    union = pred_sum + true_sum - intersection

    # 2. 计算指标
    dice = 2 * intersection / max(1, pred_sum + true_sum)
    iou = intersection / max(1, union)

    # 3. 返回结果
    return {
        "available": True,
        "dice": dice,
        "iou": iou,
        "intersection": intersection,
        "pred_area": pred_sum,
        "true_area": true_sum,
        "union": union,
    }
```

### 集成到评估流程

```python
from src.metrics.classification import classification_metrics
from src.metrics.segmentation import dice_score, iou_score

# 在 benchmark 中使用
def evaluate_predictions(predictions: list[dict], ground_truth: list[dict]) -> dict[str, Any]:
    """评估预测结果"""
    results = {}

    # 1. 分类评估
    y_true = [gt["label"] for gt in ground_truth]
    y_score = [pred["probability"] for pred in predictions]
    results["classification"] = classification_metrics(y_true, y_score)

    # 2. 分割评估（如果有掩码）
    if "mask" in predictions[0]:
        dice_scores = []
        iou_scores = []
        for pred, gt in zip(predictions, ground_truth):
            if "mask" in gt:
                dice = dice_score(
                    intersection=pred["mask"]["intersection"],
                    pred_area=pred["mask"]["pred_area"],
                    true_area=pred["mask"]["true_area"],
                )
                iou = iou_score(
                    intersection=pred["mask"]["intersection"],
                    union=pred["mask"]["union"],
                )
                dice_scores.append(dice)
                iou_scores.append(iou)

        if dice_scores:
            results["segmentation"] = {
                "mean_dice": sum(dice_scores) / len(dice_scores),
                "mean_iou": sum(iou_scores) / len(iou_scores),
                "num_samples": len(dice_scores),
            }

    return results
```

## 注意事项

1. **处理空输入**：当输入列表为空时，返回 `{"available": False, "reason": "..."}` 而不是抛出异常
2. **避免除零错误**：使用 `max(1, ...)` 或 `max(1e-12, ...)` 避免除零
3. **保持数值稳定**：使用适当的数值精度，避免浮点数溢出
4. **支持批量计算**：指标函数应支持批量输入，提高计算效率
5. **提供置信区间**：对于重要指标，考虑提供置信区间或标准差
6. **记录计算过程**：使用日志记录指标计算过程，便于调试
7. **支持多种阈值**：分类指标应支持自定义阈值
8. **可复现性**：指标计算应确定性可复现，避免随机性

## 相关文件

- `src/metrics/__init__.py`：指标模块入口
- `src/metrics/calibration.py`：校准指标
- `src/metrics/classification.py`：分类指标
- `src/metrics/detection.py`：检测指标
- `src/metrics/segmentation.py`：分割指标
- `src/core/schemas.py`：数据模式定义
