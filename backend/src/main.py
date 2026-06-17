from __future__ import annotations

import uvicorn

from backend.src.api.app import app
from backend.src.core.settings import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port)


if __name__ == "__main__":
    main()
