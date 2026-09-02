from __future__ import annotations

from types import SimpleNamespace

from osteo_vision_core.utils.runtime import probe_accelerator


def _torch_stub(*, available: bool = True, raises: bool = False) -> SimpleNamespace:
    def is_available() -> bool:
        if raises:
            raise RuntimeError("driver unavailable")
        return available

    return SimpleNamespace(
        __version__="2.11.0",
        version=SimpleNamespace(cuda="12.8"),
        cuda=SimpleNamespace(
            is_available=is_available,
            device_count=lambda: 1,
            get_device_name=lambda _index: "NVIDIA Test GPU",
        ),
    )


def test_probe_accelerator_prefers_a_usable_cuda_device() -> None:
    status = probe_accelerator(torch_module=_torch_stub())

    assert status.selected_device == "cuda"
    assert status.gpu_acceleration_enabled is True
    assert status.fallback_active is False
    assert status.gpu_name == "NVIDIA Test GPU"


def test_probe_accelerator_retains_cpu_fallback_when_cuda_is_unavailable() -> None:
    status = probe_accelerator(torch_module=_torch_stub(available=False))

    assert status.selected_device == "cpu"
    assert status.gpu_acceleration_enabled is False
    assert status.fallback_active is True
    assert status.fallback_reason == "cuda_unavailable"


def test_probe_accelerator_handles_cuda_driver_probe_errors() -> None:
    status = probe_accelerator(torch_module=_torch_stub(raises=True))

    assert status.selected_device == "cpu"
    assert status.fallback_reason == "cuda_probe_failed"


def test_probe_accelerator_honors_explicit_cpu_policy() -> None:
    status = probe_accelerator("cpu", torch_module=_torch_stub())

    assert status.selected_device == "cpu"
    assert status.fallback_active is False
    assert status.fallback_reason == "cpu_policy"
