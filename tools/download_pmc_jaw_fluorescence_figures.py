from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import tarfile
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures"

ARTICLE_SELECTIONS: dict[str, dict[str, Any]] = {
    "PMC12113262": {
        "title": "Autofluorescence-Guided Surgery in the Management of Osteonecrosis of the Jaw",
        "scene": "osteonecrosis_of_the_jaw_autofluorescence_guided_surgery",
        "figures": {"Figure 2", "Figure 3", "Figure 4", "Figure 5", "Figure 6", "Figure 8"},
        "fluorescence": "bone_autofluorescence_blue_light",
    },
    "PMC4628814": {
        "title": "Fluorescence-guided bone resection in diffuse chronic sclerosing osteomyelitis of the mandible",
        "scene": "mandibular_chronic_sclerosing_osteomyelitis_fluorescence_guided_resection",
        "figures": {"Figure 2", "Figure 3"},
        "fluorescence": "velscope_bone_autofluorescence",
    },
    "PMC11760707": {
        "title": "Clinical outcome and volumetric 3D analysis of biofluorescence-guided surgery for MRONJ",
        "scene": "mronj_biofluorescence_guided_surgery",
        "figures": {"Fig. 1"},
        "fluorescence": "qray_red_biofluorescence",
    },
    "PMC9509235": {
        "title": "The Therapeutic Effectiveness Using Fluorescence-Guided Surgery for MRONJ",
        "scene": "mronj_fluorescence_guidance_schematic",
        "figures": {"Figure 6"},
        "fluorescence": "schematic_bone_fluorescence",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _href(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return next((value for key, value in element.attrib.items() if key.endswith("href")), "")


def article_metadata(pmcid: str, session: requests.Session) -> tuple[dict[str, Any], list[dict[str, str]]]:
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    response = session.get(xml_url, timeout=60)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    figures: list[dict[str, str]] = []
    for figure in root.findall(".//fig"):
        figures.append(
            {
                "label": _text(figure.find("label")),
                "caption": _text(figure.find("caption")),
                "archive_name": _href(figure.find(".//graphic")),
            }
        )
    license_text = _text(root.find(".//license"))
    return {"xml_url": xml_url, "license_text": license_text}, figures


def oa_package(pmcid: str, session: requests.Session) -> dict[str, str]:
    api_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
    response = session.get(api_url, timeout=60)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    record = root.find(".//record")
    if record is None:
        raise RuntimeError(f"No OA package record for {pmcid}")
    tgz = next(
        (link.attrib.get("href", "") for link in record.findall("link") if link.attrib.get("format") == "tgz"), ""
    )
    if not tgz:
        raise RuntimeError(f"No OA tgz package for {pmcid}")
    return {
        "api_url": api_url,
        "license": str(record.attrib.get("license") or "unknown"),
        "citation": str(record.attrib.get("citation") or ""),
        "package_url": tgz.replace("ftp://", "https://"),
    }


def download_package(url: str, session: requests.Session) -> bytes:
    response = session.get(url, timeout=180)
    response.raise_for_status()
    return response.content


def download_europe_pmc_archive(pmcid: str, session: requests.Session) -> tuple[str, bytes]:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/supplementaryFiles"
    response = session.get(url, timeout=180)
    response.raise_for_status()
    return url, response.content


def _normalized_figure_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


class _ImageAssetParser(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.assets: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        source = attributes.get("src") or attributes.get("data-src")
        if not source:
            return
        resolved = urljoin(self.page_url, html.unescape(source))
        basename = Path(resolved.split("?", 1)[0]).name
        if basename:
            self.assets[basename] = resolved
        alt_label = _normalized_figure_label(attributes.get("alt", ""))
        if alt_label:
            self.assets[f"label:{alt_label}"] = resolved


def article_asset_urls(pmcid: str, session: requests.Session) -> dict[str, str]:
    page_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    response = session.get(page_url, timeout=60)
    response.raise_for_status()
    parser = _ImageAssetParser(str(response.url or page_url))
    parser.feed(response.text)
    return parser.assets


def resolve_figure_asset_url(figure: dict[str, str], assets: dict[str, str]) -> str | None:
    archive_basename = Path(figure["archive_name"]).name
    return assets.get(archive_basename) or assets.get(f"label:{_normalized_figure_label(figure['label'])}")


def extract_member(package: bytes, archive_name: str, destination: Path) -> str:
    with tarfile.open(fileobj=io.BytesIO(package), mode="r:gz") as archive:
        candidates = [member for member in archive.getmembers() if Path(member.name).name == Path(archive_name).name]
        if not candidates:
            raise FileNotFoundError(f"Figure {archive_name} was not found in OA package")
        member = candidates[0]
        extracted = archive.extractfile(member)
        if extracted is None:
            raise FileNotFoundError(f"Figure {archive_name} could not be read from OA package")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(extracted.read())
        return member.name


def extract_zip_member(package: bytes, archive_name: str, destination: Path) -> str:
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        candidates = [name for name in archive.namelist() if Path(name).name == Path(archive_name).name]
        if not candidates:
            raise FileNotFoundError(f"Figure {archive_name} was not found in Europe PMC archive")
        member = candidates[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(member))
        return member


def usage_policy(license_name: str, scene: str) -> tuple[str, bool]:
    normalized = license_name.lower()
    if "nd" in normalized:
        return "reference_only_no_derivatives", False
    if "schematic" in scene:
        return "literature_reference_only", False
    if "cc by" in normalized:
        return "weak_label_training_seed_with_attribution", True
    return "license_review_required", False


def build_dataset(output_dir: Path) -> list[dict[str, Any]]:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131.0 Safari/537.36 Osteo-Vision/1.0"
            )
        }
    )
    records: list[dict[str, Any]] = []
    for pmcid, selection in ARTICLE_SELECTIONS.items():
        metadata, figures = article_metadata(pmcid, session)
        package_meta = oa_package(pmcid, session)
        assets = article_asset_urls(pmcid, session)
        europe_pmc_archive: bytes | None = None
        europe_pmc_archive_url = ""
        selected = [figure for figure in figures if figure["label"] in selection["figures"]]
        missing = sorted(set(selection["figures"]) - {figure["label"] for figure in selected})
        if missing:
            raise RuntimeError(f"Missing selected figures for {pmcid}: {missing}")
        policy, training_seed_allowed = usage_policy(package_meta["license"], selection["scene"])
        for figure in selected:
            archive_name = figure["archive_name"]
            suffix = Path(archive_name).suffix.lower() or ".jpg"
            record_id = f"{pmcid}_{figure['label'].lower().replace(' ', '_').replace('.', '')}"
            local_path = output_dir / "raw" / pmcid / f"{record_id}{suffix}"
            asset_url = resolve_figure_asset_url(figure, assets)
            package_member = archive_name
            if asset_url:
                image_response = session.get(asset_url, timeout=120)
                image_response.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(image_response.content)
                download_method = "cdn_asset"
            else:
                if europe_pmc_archive is None:
                    europe_pmc_archive_url, europe_pmc_archive = download_europe_pmc_archive(pmcid, session)
                package_member = extract_zip_member(europe_pmc_archive, archive_name, local_path)
                asset_url = europe_pmc_archive_url
                download_method = "europe_pmc_archive_member"
            records.append(
                {
                    "record_id": record_id,
                    "pmcid": pmcid,
                    "article_title": selection["title"],
                    "figure_label": figure["label"],
                    "caption": figure["caption"],
                    "source_page_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                    "full_text_xml_url": metadata["xml_url"],
                    "oa_api_url": package_meta["api_url"],
                    "package_url": package_meta["package_url"],
                    "asset_url": asset_url,
                    "package_member": package_member,
                    "download_method": download_method,
                    "local_path": str(local_path.resolve()),
                    "size_bytes": local_path.stat().st_size,
                    "sha256": sha256(local_path),
                    "license": package_meta["license"],
                    "license_text": metadata["license_text"],
                    "usage_policy": policy,
                    "training_seed_allowed": training_seed_allowed,
                    "medical_scene": selection["scene"],
                    "fluorescence": selection["fluorescence"],
                    "domain_tier": "jaw_fluorescence_target_condition_near_domain",
                    "target_domain_flag": False,
                    "label_type": "figure_caption_weak_label",
                    "review_state": "review_required",
                    "sample_weight": 0.25 if training_seed_allowed else 0.0,
                    "physician_reviewed": False,
                    "data_boundary": (
                        "Public article figure from a jaw fluorescence-related scene. It is a multi-panel weak-label source, "
                        "without pixel annotations or direct intraoperative ICG jaw-osteomyelitis ground truth."
                    ),
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
    return records


def write_outputs(output_dir: Path, records: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pmc_jaw_fluorescence_figure_manifest.json"
    csv_path = output_dir / "pmc_jaw_fluorescence_figure_manifest.csv"
    payload = {
        "schema_version": "osteo-vision-pmc-jaw-fluorescence-figures-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "training_seed_count": sum(1 for record in records if record["training_seed_allowed"]),
        "reference_only_count": sum(1 for record in records if not record["training_seed_allowed"]),
        "records": records,
        "medical_boundary": (
            "These public multi-panel article figures provide target-condition-near visual references and weak-label seeds. "
            "They do not provide target-domain video, physician pixel masks, or clinical performance evidence."
        ),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = list(records[0]) if records else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    records = build_dataset(output_dir)
    write_outputs(output_dir, records)
    print(json.dumps({"output_dir": str(output_dir), "record_count": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
