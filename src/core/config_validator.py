"""Configuration validation utilities.

This module provides functions for validating configuration files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_task_config(config: dict[str, Any]) -> list[str]:
    """
    Validate task configuration.
    
    Args:
        config: Task configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []
    
    # Required fields
    required_fields = ["task_id", "task_name", "modality"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate modality
    valid_modalities = ["ct", "mri", "xray", "ultrasound", "generic"]
    if "modality" in config and config["modality"] not in valid_modalities:
        errors.append(f"Invalid modality: {config['modality']}. Must be one of {valid_modalities}")
    
    # Validate input_contract
    if "input_contract" in config:
        contract = config["input_contract"]
        if not isinstance(contract, dict):
            errors.append("input_contract must be a dictionary")
        elif "input_types" in contract:
            valid_types = ["2d_image", "video_file", "video_stream", "npz_roi", "dicom_series", "nifti_volume"]
            for t in contract["input_types"]:
                if t not in valid_types:
                    errors.append(f"Invalid input type: {t}")
    
    # Validate label_contract
    if "label_contract" in config:
        contract = config["label_contract"]
        if not isinstance(contract, dict):
            errors.append("label_contract must be a dictionary")
        elif "type" in contract:
            valid_types = ["binary", "multiclass", "multilabel", "regression", "binary_or_missing", "missing"]
            if contract["type"] not in valid_types:
                errors.append(f"Invalid label type: {contract['type']}")
    
    return errors


def validate_model_config(config: dict[str, Any]) -> list[str]:
    """
    Validate model configuration.
    
    Args:
        config: Model configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []
    
    # Required fields
    required_fields = ["model_id", "family"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate task_types
    if "task_types" in config:
        valid_types = ["classification", "segmentation", "detection", "quantification", "multitask", "*"]
        for t in config["task_types"]:
            if t not in valid_types:
                errors.append(f"Invalid task type: {t}")
    
    # Validate input_types
    if "input_types" in config:
        valid_types = ["2d_image", "video_file", "video_stream", "npz_roi", "dicom_series", "nifti_volume", "*"]
        for t in config["input_types"]:
            if t not in valid_types:
                errors.append(f"Invalid input type: {t}")
    
    # Validate precision
    if "precision" in config:
        valid_precisions = ["fp32", "fp16", "bf16", "int8", "deterministic"]
        if config["precision"] not in valid_precisions:
            errors.append(f"Invalid precision: {config['precision']}")
    
    # Validate device_policy
    if "device_policy" in config:
        valid_policies = ["auto", "cpu", "gpu", "multi_gpu"]
        if config["device_policy"] not in valid_policies:
            errors.append(f"Invalid device_policy: {config['device_policy']}")
    
    return errors


def validate_pipeline_config(config: dict[str, Any]) -> list[str]:
    """
    Validate pipeline configuration.
    
    Args:
        config: Pipeline configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []
    
    # Required fields
    if "pipeline" not in config:
        errors.append("Missing required field: pipeline")
    
    # Validate threshold
    if "threshold" in config:
        threshold = config["threshold"]
        if not isinstance(threshold, (int, float)):
            errors.append("threshold must be a number")
        elif not 0 <= threshold <= 1:
            errors.append("threshold must be between 0 and 1")
    
    return errors


def validate_inference_config(config: dict[str, Any]) -> list[str]:
    """
    Validate inference configuration.
    
    Args:
        config: Inference configuration dictionary
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []
    
    # Validate runtime section
    if "runtime" in config:
        runtime = config["runtime"]
        
        # Validate models
        if "models" in runtime:
            for i, model in enumerate(runtime["models"]):
                model_errors = validate_model_config(model)
                for err in model_errors:
                    errors.append(f"Model {i}: {err}")
        
        # Validate tasks
        if "tasks" in runtime:
            for task_name, task_config in runtime["tasks"].items():
                task_errors = validate_pipeline_config(task_config)
                for err in task_errors:
                    errors.append(f"Task {task_name}: {err}")
    
    return errors


def validate_config_file(path: str | Path) -> tuple[bool, list[str]]:
    """
    Validate a configuration file.
    
    Args:
        path: Path to configuration file
        
    Returns:
        Tuple of (is_valid, errors)
    """
    import yaml
    
    p = Path(path)
    if not p.exists():
        return False, [f"File not found: {p}"]
    
    try:
        with open(p, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return False, [f"Failed to parse YAML: {e}"]
    
    if not isinstance(config, dict):
        return False, ["Configuration must be a dictionary"]
    
    # Determine config type and validate
    if "task_id" in config:
        errors = validate_task_config(config)
    elif "runtime" in config:
        errors = validate_inference_config(config)
    elif "model_id" in config:
        errors = validate_model_config(config)
    else:
        errors = []
    
    return len(errors) == 0, errors
