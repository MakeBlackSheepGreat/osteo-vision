from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/d048_open_clinical_bone_fluorescence"

ARTICLE_SELECTIONS: dict[str, dict[str, Any]] = {
    "PMC9201330": {
        "title": "Fluorescence-guided surgery for osteoradionecrosis of the jaw: a retrospective study",
        "figures": {
            "Figure 1.": {
                "medical_scene": "human_jaw_osteoradionecrosis_fluorescence_guided_resection",
                "fluorescence": "tetracycline_green_bone_fluorescence",
                "domain_tier": "near_domain",
                "asset_role": "human_clinical_jaw_surgery",
                "training_seed_allowed": True,
                "sample_weight": 0.30,
            }
        },
    },
    "PMC11355438": {
        "title": (
            "Demineralized Dentin Matrix Incorporated with rhBMP-2 Composite Graft for Treating "
            "Medication-Related Osteonecrosis of the Jaw"
        ),
        "figures": {
            "Figure 2": {
                "medical_scene": "human_maxillary_mronj_qray_fluorescence_guided_resection",
                "fluorescence": "qray_red_biofluorescence",
                "domain_tier": "near_domain",
                "asset_role": "human_clinical_jaw_surgery",
                "training_seed_allowed": True,
                "sample_weight": 0.30,
            },
            "Figure 5": {
                "medical_scene": "human_mronj_fluorescence_histopathology_correlation",
                "fluorescence": "histopathology_correlated_red_biofluorescence",
                "domain_tier": "near_domain_reference",
                "asset_role": "human_histopathology_reference",
                "training_seed_allowed": False,
                "sample_weight": 0.0,
            },
        },
    },
    "PMC12829038": {
        "title": (
            "Biofluorescence imaging-guided implantoplasty for the management of peri-implantitis: "
            "a retrospective case series"
        ),
        "figures": {
            label: {
                "medical_scene": "human_oral_peri_implantitis_biofluorescence_guided_implantoplasty",
                "fluorescence": "qray_red_biofluorescence",
                "domain_tier": "oral_fluorescence_adjacent_domain",
                "asset_role": "human_clinical_oral_surgery",
                "training_seed_allowed": True,
                "sample_weight": 0.15,
            }
            for label in ("Fig. 1", "Fig. 3", "Fig. 4", "Fig. 5", "Fig. 6", "Fig. 7", "Fig. 8")
        },
    },
    "PMC8132458": {
        "title": (
            "Fluorescent tetracycline bone labeling as an intraoperative tool to debride necrotic "
            "bone during septic hip revision: a preliminary case series"
        ),
        "figures": {
            label: {
                "medical_scene": "human_septic_hip_revision_fluorescence_guided_bone_debridement",
                "fluorescence": "minocycline_green_bone_fluorescence",
                "domain_tier": "clinical_bone_infection_adjacent_domain",
                "asset_role": "human_clinical_non_jaw_surgery",
                "training_seed_allowed": True,
                "sample_weight": 0.10,
            }
            for label in ("Figure 1", "Figure 2")
        },
    },
    "PMC7666678": {
        "title": (
            "Differences between auto-fluorescence and tetracycline-fluorescence in "
            "medication-related osteonecrosis of the jaw-a preclinical proof of concept study in "
            "the mini-pig"
        ),
        "figures": {
            label: {
                "medical_scene": "minipig_mronj_fluorescence_necrotic_viable_bone_comparison",
                "fluorescence": "autofluorescence_and_tetracycline_fluorescence",
                "domain_tier": "preclinical_jaw_fluorescence_proxy",
                "asset_role": "preclinical_jaw_proxy",
                "training_seed_allowed": True,
                "sample_weight": 0.10,
            }
            for label in ("Fig. 2", "Fig. 3", "Fig. 4", "Fig. 5")
        },
    },
    "PMC10222433": {
        "title": (
            "Chronic Periodontal Infection and Not Iatrogenic Interference Is the Trigger of "
            "Medication-Related Osteonecrosis of the Jaw: Insights from a Large Animal Study"
        ),
        "figures": {
            "Figure 15": {
                "medical_scene": "minipig_mronj_oxytetracycline_histology",
                "fluorescence": "oxytetracycline_histology_fluorescence",
                "domain_tier": "preclinical_reference",
                "asset_role": "preclinical_histology_reference",
                "training_seed_allowed": False,
                "sample_weight": 0.0,
            }
        },
    },
    "PMC12129460": {
        "title": (
            "Medication-related osteonecrosis of the jaws: a series of 22 cases highlighting "
            "their histopathological features"
        ),
        "figures": {
            "Figure 3": {
                "medical_scene": "human_mronj_red_fluorescence_histology",
                "fluorescence": "histology_red_fluorescence",
                "domain_tier": "near_domain_reference",
                "asset_role": "human_histopathology_reference",
                "training_seed_allowed": False,
                "sample_weight": 0.0,
            }
        },
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


def article_metadata(pmcid: str, session: requests.Session) -> tuple[dict[str, Any], list[dict[str, str]]]:
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    response = session.get(xml_url, timeout=60)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    figures = [
        {
            "label": _text(figure.find("label")),
            "caption": _text(figure.find("caption")),
            "archive_name": _href(figure.find(".//graphic")),
        }
        for figure in root.findall(".//fig")
    ]
    return {
        "xml_url": xml_url,
        "license_text": _text(root.find(".//license")),
    }, figures


def oa_package(pmcid: str, session: requests.Session) -> dict[str, str]:
    api_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
    response = session.get(api_url, timeout=60)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    record = root.find(".//record")
    if record is None:
        raise RuntimeError(f"No OA package record for {pmcid}")
    package_url = next(
        (link.attrib.get("href", "") for link in record.findall("link") if link.attrib.get("format") == "tgz"),
        "",
    )
    return {
        "api_url": api_url,
        "license": str(record.attrib.get("license") or "unknown"),
        "citation": str(record.attrib.get("citation") or ""),
        "package_url": package_url.replace("ftp://", "https://"),
    }


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


def download_europe_pmc_archive(pmcid: str, session: requests.Session) -> tuple[str, bytes]:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/supplementaryFiles"
    response = session.get(url, timeout=180)
    response.raise_for_status()
    return url, response.content


def extract_zip_member(package: bytes, archive_name: str, destination: Path) -> str:
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        candidates = [name for name in archive.namelist() if Path(name).name == Path(archive_name).name]
        if not candidates:
            raise FileNotFoundError(f"Figure {archive_name} was not found in Europe PMC archive")
        member = candidates[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(member))
        return member


def license_allows_training_seed(license_name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", license_name.lower()).strip()
    blocked = any(marker in normalized.split() for marker in ("nc", "nd"))
    return not blocked and ("cc by" in normalized or "cc0" in normalized)


def _usage_policy(training_seed_allowed: bool, asset_role: str) -> str:
    if not training_seed_allowed:
        return "mechanism_reference_only"
    if asset_role == "human_clinical_jaw_surgery":
        return "jaw_clinical_weak_label_seed_after_panel_crop_and_review"
    if asset_role == "human_clinical_oral_surgery":
        return "oral_adjacent_weak_label_seed_after_panel_crop_and_review"
    if asset_role == "human_clinical_non_jaw_surgery":
        return "non_jaw_bone_infection_seed_after_panel_crop_and_review"
    return "preclinical_proxy_seed_after_panel_crop_and_review"


def _session() -> requests.Session:
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
    return session


def build_dataset(output_dir: Path) -> list[dict[str, Any]]:
    session = _session()
    records: list[dict[str, Any]] = []
    for pmcid, selection in ARTICLE_SELECTIONS.items():
        metadata, figures = article_metadata(pmcid, session)
        package_meta = oa_package(pmcid, session)
        if not license_allows_training_seed(package_meta["license"]):
            raise RuntimeError(
                f"Selected D048 source {pmcid} is not under a derivative-compatible CC BY/CC0 license: "
                f"{package_meta['license']}"
            )
        assets = article_asset_urls(pmcid, session)
        archive_bytes: bytes | None = None
        archive_url = ""
        selected_by_label = selection["figures"]
        selected = [figure for figure in figures if figure["label"] in selected_by_label]
        missing = sorted(set(selected_by_label) - {figure["label"] for figure in selected})
        if missing:
            raise RuntimeError(f"Missing selected figures for {pmcid}: {missing}")
        for figure in selected:
            policy = dict(selected_by_label[figure["label"]])
            archive_name = figure["archive_name"]
            suffix = Path(archive_name).suffix.lower() or ".jpg"
            normalized_label = figure["label"].lower().replace(" ", "_").replace(".", "")
            record_id = f"{pmcid}_{normalized_label}"
            local_path = output_dir / "raw" / pmcid / f"{record_id}{suffix}"
            asset_url = resolve_figure_asset_url(figure, assets)
            archive_member = archive_name
            if asset_url:
                response = session.get(asset_url, timeout=120)
                response.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(response.content)
                download_method = "cdn_asset"
            else:
                if archive_bytes is None:
                    archive_url, archive_bytes = download_europe_pmc_archive(pmcid, session)
                archive_member = extract_zip_member(archive_bytes, archive_name, local_path)
                asset_url = archive_url
                download_method = "europe_pmc_archive_member"
            with Image.open(local_path) as image:
                image.verify()
            with Image.open(local_path) as image:
                width, height = image.size
                image_format = str(image.format or suffix.removeprefix(".")).upper()
            training_seed_allowed = bool(policy["training_seed_allowed"])
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
                    "archive_member": archive_member,
                    "download_method": download_method,
                    "local_path": str(local_path.resolve()),
                    "size_bytes": local_path.stat().st_size,
                    "sha256": sha256(local_path),
                    "image_width": width,
                    "image_height": height,
                    "image_format": image_format,
                    "license": package_meta["license"],
                    "license_text": metadata["license_text"],
                    "license_derivative_compatible": True,
                    "usage_policy": _usage_policy(training_seed_allowed, policy["asset_role"]),
                    "training_seed_allowed": training_seed_allowed,
                    "training_eligible": False,
                    "medical_scene": policy["medical_scene"],
                    "fluorescence": policy["fluorescence"],
                    "domain_tier": policy["domain_tier"],
                    "asset_role": policy["asset_role"],
                    "human_clinical": policy["asset_role"].startswith("human_clinical"),
                    "target_domain_flag": False,
                    "multi_panel": True,
                    "label_type": "figure_caption_weak_label",
                    "review_state": "review_required" if training_seed_allowed else "reference_only",
                    "sample_weight": float(policy["sample_weight"]),
                    "physician_reviewed": False,
                    "data_boundary": (
                        "Open-access article figure with explicit CC BY/CC0-compatible reuse terms. "
                        "The source remains a multi-panel publication image without physician pixel masks, "
                        "raw paired white-light/NIR frames, or target-domain intraoperative ICG ground truth."
                    ),
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
    return records


def write_outputs(output_dir: Path, records: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "open_clinical_bone_fluorescence_manifest.json"
    csv_path = output_dir / "open_clinical_bone_fluorescence_manifest.csv"
    payload = {
        "schema_version": "osteo-vision-open-clinical-bone-fluorescence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "article_count": len({record["pmcid"] for record in records}),
        "human_clinical_count": sum(bool(record["human_clinical"]) for record in records),
        "jaw_clinical_count": sum(record["asset_role"] == "human_clinical_jaw_surgery" for record in records),
        "training_seed_count": sum(bool(record["training_seed_allowed"]) for record in records),
        "reference_only_count": sum(not bool(record["training_seed_allowed"]) for record in records),
        "video_count": 0,
        "records": records,
        "medical_boundary": (
            "D048 expands traceable CC BY/CC0-compatible fluorescence surgery evidence beyond D047. "
            "Every asset remains non-target-domain until real jaw-osteomyelitis white-light/ICG data and "
            "physician-reviewed masks are obtained. Multi-panel sources require crop review before training."
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
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "record_count": len(records),
                "training_seed_count": sum(bool(record["training_seed_allowed"]) for record in records),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
