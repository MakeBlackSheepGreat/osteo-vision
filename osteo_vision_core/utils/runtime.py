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


@dataclass(frozen=True)
class AcceleratorRuntimeStatus:
    """Selected compute path and the evidence used to select it."""

    requested_policy: str
    selected_device: str
    gpu_acceleration_enabled: bool
    fallback_active: bool
    fallback_reason: str | None
    torch_version: str | None
    cuda_runtime_version: str | None
    gpu_count: int
    gpu_name: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_policy": self.requested_policy,
            "selected_device": self.selected_device,
            "gpu_acceleration_enabled": self.gpu_acceleration_enabled,
            "fallback_active": self.fallback_active,
            "fallback_reason": self.fallback_reason,
            "torch_version": self.torch_version,
            "cuda_runtime_version": self.cuda_runtime_version,
            "gpu_count": self.gpu_count,
            "gpu_name": self.gpu_name,
        }


def probe_accelerator(policy: str = "auto", *, torch_module: Any | None = None) -> AcceleratorRuntimeStatus:
    """Select CUDA when it is usable and retain a reasoned CPU fallback otherwise."""

    requested_policy = _resolve_accelerator_policy(policy)
    if requested_policy == "cpu":
        return AcceleratorRuntimeStatus(
            requested_policy=requested_policy,
            selected_device="cpu",
            gpu_acceleration_enabled=False,
            fallback_active=False,
            fallback_reason="cpu_policy",
            torch_version=_torch_version(torch_module),
            cuda_runtime_version=None,
            gpu_count=0,
            gpu_name=None,
        )

    try:
        module = torch_module
        if module is None:
            import torch as module
    except Exception:
        return AcceleratorRuntimeStatus(
            requested_policy=requested_policy,
            selected_device="cpu",
            gpu_acceleration_enabled=False,
            fallback_active=True,
            fallback_reason="torch_unavailable",
            torch_version=None,
            cuda_runtime_version=None,
            gpu_count=0,
            gpu_name=None,
        )

    try:
        if not bool(module.cuda.is_available()):
            return AcceleratorRuntimeStatus(
                requested_policy=requested_policy,
                selected_device="cpu",
                gpu_acceleration_enabled=False,
                fallback_active=True,
                fallback_reason="cuda_unavailable",
                torch_version=_torch_version(module),
                cuda_runtime_version=_cuda_version(module),
                gpu_count=0,
                gpu_name=None,
            )
        gpu_count = int(module.cuda.device_count())
        if gpu_count < 1:
            return AcceleratorRuntimeStatus(
                requested_policy=requested_policy,
                selected_device="cpu",
                gpu_acceleration_enabled=False,
                fallback_active=True,
                fallback_reason="cuda_device_missing",
                torch_version=_torch_version(module),
                cuda_runtime_version=_cuda_version(module),
                gpu_count=0,
                gpu_name=None,
            )
        gpu_name = str(module.cuda.get_device_name(0))
    except Exception:
        return AcceleratorRuntimeStatus(
            requested_policy=requested_policy,
            selected_device="cpu",
            gpu_acceleration_enabled=False,
            fallback_active=True,
            fallback_reason="cuda_probe_failed",
            torch_version=_torch_version(module),
            cuda_runtime_version=_cuda_version(module),
            gpu_count=0,
            gpu_name=None,
        )

    return AcceleratorRuntimeStatus(
        requested_policy=requested_policy,
        selected_device="cuda",
        gpu_acceleration_enabled=True,
        fallback_active=False,
        fallback_reason=None,
        torch_version=_torch_version(module),
        cuda_runtime_version=_cuda_version(module),
        gpu_count=gpu_count,
        gpu_name=gpu_name,
    )


def _resolve_accelerator_policy(policy: str) -> str:
    requested = str(policy or "auto").strip().lower()
    if requested == "cuda":
        requested = "gpu"
    if requested not in {"auto", "cpu", "gpu", "multi_gpu"}:
        requested = "auto"
    override = os.environ.get("OSTEO_ACCELERATOR_POLICY", "").strip().lower()
    if requested == "auto" and override in {"auto", "cpu", "gpu", "multi_gpu", "cuda"}:
        return "gpu" if override == "cuda" else override
    return requested


def _torch_version(torch_module: Any | None) -> str | None:
    value = getattr(torch_module, "__version__", None)
    return str(value) if value else None


def _cuda_version(torch_module: Any | None) -> str | None:
    version = getattr(torch_module, "version", None)
    value = getattr(version, "cuda", None)
    return str(value) if value else None


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

    accelerator = probe_accelerator()
    cuda_available = accelerator.gpu_acceleration_enabled
    cuda_version = accelerator.cuda_runtime_version
    gpu_count = accelerator.gpu_count
    gpu_names = [accelerator.gpu_name] if accelerator.gpu_name else []
    if cuda_available:
        try:
            import torch

            gpu_names = [str(torch.cuda.get_device_name(index)) for index in range(gpu_count)]
        except Exception:
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
    return probe_accelerator(policy).selected_device


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
                gpus.append(
                    {
                        "index": i,
                        "name": props.name,
                        "total_memory_mb": props.total_memory / (1024 * 1024),
                        "major": props.major,
                        "minor": props.minor,
                    }
                )
    except Exception:
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
