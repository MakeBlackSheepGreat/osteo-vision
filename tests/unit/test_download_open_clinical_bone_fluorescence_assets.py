from __future__ import annotations

import io
import zipfile
from pathlib import Path

from tools.download_open_clinical_bone_fluorescence_assets import (
    ARTICLE_SELECTIONS,
    article_asset_urls,
    extract_zip_member,
    license_allows_training_seed,
    resolve_figure_asset_url,
)


class _FakeResponse:
    def __init__(self, text: str, url: str = "https://pmc.example/articles/PMC1/") -> None:
        self.text = text
        self.url = url

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, text: str) -> None:
        self.text = text

    def get(self, _url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(self.text)


def test_license_gate_accepts_derivative_compatible_cc_and_blocks_restricted_cc() -> None:
    assert license_allows_training_seed("CC BY")
    assert license_allows_training_seed("CC0 1.0")
    assert not license_allows_training_seed("CC BY-NC")
    assert not license_allows_training_seed("CC BY-NC-ND")
    assert not license_allows_training_seed("publisher copyright")


def test_selection_contains_human_jaw_and_adjacent_clinical_assets() -> None:
    roles = {figure["asset_role"] for article in ARTICLE_SELECTIONS.values() for figure in article["figures"].values()}

    assert "human_clinical_jaw_surgery" in roles
    assert "human_clinical_oral_surgery" in roles
    assert "human_clinical_non_jaw_surgery" in roles
    assert "preclinical_jaw_proxy" in roles


def test_article_asset_urls_supports_xml_basename_and_html_alt_fallback() -> None:
    page = """
    <figure>
      <img src="/pmc/blobs/hash/cdn-name.jpg" alt="Figure 1.">
    </figure>
    """

    assets = article_asset_urls("PMC1", _FakeSession(page))  # type: ignore[arg-type]

    expected = "https://pmc.example/pmc/blobs/hash/cdn-name.jpg"
    assert assets["cdn-name.jpg"] == expected
    assert resolve_figure_asset_url({"archive_name": "xml-name.jpg", "label": "Figure 1."}, assets) == expected


def test_extract_zip_member_uses_basename_and_writes_bytes(tmp_path: Path) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w") as archive:
        archive.writestr("article/assets/figure.jpg", b"open-figure")
    destination = tmp_path / "figure.jpg"

    member = extract_zip_member(stream.getvalue(), "figure.jpg", destination)

    assert member == "article/assets/figure.jpg"
    assert destination.read_bytes() == b"open-figure"
