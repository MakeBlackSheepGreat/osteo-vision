"""Runtime utilities for the medical imaging competition framework.

This module provides utilities for runtime environment detection, device management,
and performance monitoring.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator


@dataclass
class RuntimeEnvironment:
    """Runtime environment information."""
    
    python_version: str
    platform: str
    os_name: str
    os_version: str
    machine: str
    processor: str
    cuda_available: bool
    cuda_version: str | None
    gpu_count: int
    gpu_names: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "machine": self.machine,
            "processor": self.processor,
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "gpu_count": self.gpu_count,
            "gpu_names": self.gpu_names,
        }


def detect_environment() -> RuntimeEnvironment:
    """
    Detect current runtime environment.
    
    Returns:
        RuntimeEnvironment with system information
    """
    cuda_available = False
    cuda_version = None
    gpu_count = 0
    gpu_names: list[str] = []
    
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_version = torch.version.cuda
            gpu_count = torch.cuda.device_count()
            gpu_names = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
    except ImportError:
        pass
    
    return RuntimeEnvironment(
        python_version=sys.version,
        platform=platform.platform(),
        os_name=platform.system(),
        os_version=platform.release(),
        machine=platform.machine(),
        processor=platform.processor(),
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        gpu_count=gpu_count,
        gpu_names=gpu_names,
    )


def get_device(policy: str = "auto") -> str:
    """
    Get compute device based on policy.
    
    Args:
        policy: Device policy ("auto", "cpu", "gpu", "multi_gpu")
        
    Returns:
        Device string ("cpu", "cuda", "cuda:0", etc.)
    """
    if policy == "cpu":
        return "cpu"
    
    if policy in ("gpu", "multi_gpu"):
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
    
    # Auto policy
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    
    return "cpu"


def get_available_gpus() -> list[dict[str, Any]]:
    """
    Get list of available GPUs.
    
    Returns:
        List of GPU information dictionaries
    """
    gpus: list[dict[str, Any]] = []
    
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                gpus.append({
                    "index": i,
                    "name": props.name,
                    "total_memory_mb": props.total_mem / (1024 * 1024),
                    "major": props.major,
                    "minor": props.minor,
                })
    except ImportError:
        pass
    
    return gpus


def get_memory_usage() -> dict[str, Any]:
    """
    Get current memory usage.
    
    Returns:
        Dictionary with memory usage information
    """
    import psutil
    
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    
    return {
        "rss_mb": mem_info.rss / (1024 * 1024),
        "vms_mb": mem_info.vms / (1024 * 1024),
        "percent": process.memory_percent(),
    }


@contextmanager
def timer() -> Generator[dict[str, float], None, None]:
    """
    Context manager for timing code blocks.
    
    Usage:
        with timer() as t:
            # code to time
        print(f"Elapsed: {t['elapsed_ms']:.2f}ms")
    """
    result: dict[str, float] = {"elapsed_ms": 0.0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        result["elapsed_ms"] = elapsed


class PerformanceMonitor:
    """
    Monitor and track performance metrics.
    """
    
    def __init__(self) -> None:
        self._metrics: dict[str, list[float]] = {}
        self._start_times: dict[str, float] = {}
    
    def start(self, operation: str) -> None:
        """Start timing an operation."""
        self._start_times[operation] = time.perf_counter()
    
    def stop(self, operation: str) -> float:
        """
        Stop timing an operation.
        
        Returns:
            Elapsed time in milliseconds
        """
        if operation not in self._start_times:
            return 0.0
        
        elapsed = (time.perf_counter() - self._start_times[operation]) * 1000
        self._metrics.setdefault(operation, []).append(elapsed)
        del self._start_times[operation]
        return elapsed
    
    def get_stats(self, operation: str) -> dict[str, float]:
        """
        Get statistics for an operation.
        
        Returns:
            Dictionary with min, max, mean, std, count
        """
        if operation not in self._metrics:
            return {}
        
        values = self._metrics[operation]
        if not values:
            return {}
        
        import statistics
        return {
            "min_ms": min(values),
            "max_ms": max(values),
            "mean_ms": statistics.mean(values),
            "std_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
            "count": len(values),
            "total_ms": sum(values),
        }
    
    def get_all_stats(self) -> dict[str, dict[str, float]]:
        """Get statistics for all operations."""
        return {op: self.get_stats(op) for op in self._metrics}
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._start_times.clear()
