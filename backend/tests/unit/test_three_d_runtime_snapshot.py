from __future__ import annotations

import hashlib
import os
from pathlib import Path

from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.services.three_d_runtime_snapshot import resolve_model_asset


def test_model_hash_cache_reloads_same_size_content_with_preserved_mtime(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    model_path = artifact_root / "three_d_models" / "reference.stl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    original = b"solid a\nendsolid a\n"
    replacement = b"solid b\nendsolid b\n"
    assert len(original) == len(replacement)
    model_path.write_bytes(original)
    settings = Settings(project_root=tmp_path, artifact_root=artifact_root)

    first = resolve_model_asset(settings, str(model_path))
    original_stat = model_path.stat()
    replacement_path = model_path.with_suffix(".replacement")
    replacement_path.write_bytes(replacement)
    os.utime(replacement_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    model_path.unlink()
    replacement_path.rename(model_path)
    second = resolve_model_asset(settings, str(model_path))

    assert first is not None
    assert second is not None
    assert first.sha256 == hashlib.sha256(original).hexdigest()
    assert second.sha256 == hashlib.sha256(replacement).hexdigest()
    assert second.sha256 != first.sha256
