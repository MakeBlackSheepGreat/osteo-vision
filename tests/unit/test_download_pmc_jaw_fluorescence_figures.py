from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from tools.download_pmc_jaw_fluorescence_figures import (
    article_asset_urls,
    extract_member,
    extract_zip_member,
    resolve_figure_asset_url,
    usage_policy,
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


def test_usage_policy_blocks_no_derivatives_and_schematics() -> None:
    assert usage_policy("CC BY-NC-ND", "mronj_biofluorescence_guided_surgery") == (
        "reference_only_no_derivatives",
        False,
    )
    assert usage_policy("CC BY", "mronj_fluorescence_guidance_schematic") == (
        "literature_reference_only",
        False,
    )
    assert usage_policy("CC BY", "mandibular_fluorescence_guided_resection") == (
        "weak_label_training_seed_with_attribution",
        True,
    )


def test_extract_member_uses_basename_and_writes_bytes(tmp_path: Path) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        payload = b"figure-bytes"
        info = tarfile.TarInfo("package/images/figure-2.jpg")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    destination = tmp_path / "figure.jpg"

    member = extract_member(stream.getvalue(), "figure-2.jpg", destination)

    assert member == "package/images/figure-2.jpg"
    assert destination.read_bytes() == b"figure-bytes"


def test_article_asset_urls_maps_basename_and_figure_alt() -> None:
    html = """
    <figure id="F2">
      <h3>Figure 2.</h3>
      <img src="/pmc/blobs/hash/cdn-figure-name.jpg" alt="Figure 2">
    </figure>
    """

    assets = article_asset_urls("PMC1", _FakeSession(html))  # type: ignore[arg-type]

    expected = "https://pmc.example/pmc/blobs/hash/cdn-figure-name.jpg"
    assert assets["cdn-figure-name.jpg"] == expected
    assert assets["label:figure2"] == expected


def test_extract_zip_member_uses_basename_and_writes_bytes(tmp_path: Path) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w") as archive:
        archive.writestr("article/images/figure-2.jpg", b"figure-bytes")
    destination = tmp_path / "figure.jpg"

    member = extract_zip_member(stream.getvalue(), "figure-2.jpg", destination)

    assert member == "article/images/figure-2.jpg"
    assert destination.read_bytes() == b"figure-bytes"


def test_resolve_figure_asset_url_falls_back_to_alt_label_when_names_differ() -> None:
    figure = {"archive_name": "xml-graphic-name.jpg", "label": "Figure 2"}
    assets = {"label:figure2": "https://cdn.example/cdn-figure-name.jpg"}

    assert resolve_figure_asset_url(figure, assets) == "https://cdn.example/cdn-figure-name.jpg"
