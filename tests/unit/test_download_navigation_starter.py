from __future__ import annotations

from tools.download_navigation_starter import DATASETS


def test_navigation_starter_uses_simplified_serv_ct_package() -> None:
    assert DATASETS["D076"]["selected_file"] == "SERV-CT.zip"
    assert DATASETS["D076"]["license_expected"] == "CC BY 4.0"
