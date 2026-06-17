from __future__ import annotations

from app.main import build_demo_app


def test_demo_app_builds_or_returns_fallback() -> None:
    app = build_demo_app("configs/inference/demo.yml")
    assert app is not None

