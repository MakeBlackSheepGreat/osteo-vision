from __future__ import annotations

import argparse
import csv
import hashlib
import re
import tarfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "research" / "datasets" / "public-candidates" / "d046_fluorescence_osteomyelitis_videos" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "research" / "literature" / "inventory" / "video_download_manifest_20260703.csv"


@dataclass(frozen=True)
class VideoRecord:
    record_id: str
    group: str
    title: str
    source_page: str
    download_url: str
    local_rel_path: str
    fluorescence: str
    medical_scene: str
    usable_for_training: str
    notes: str
    oa_package_url: str = ""


def pmc(article_id: str, filename: str) -> str:
    return f"https://pmc.ncbi.nlm.nih.gov/articles/instance/{article_id}/bin/{filename}"


CHILD_DEBRIDEMENT_CDN: dict[int, str] = {
    1: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/b701a19a68b7/jxt-13-e21.00039-s001-pmcvs_normal.mp4",
    2: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/f20ed6365290/jxt-13-e21.00039-s002-pmcvs_normal.mp4",
    3: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/7e6786261212/jxt-13-e21.00039-s003-pmcvs_normal.mp4",
    4: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/1ca2dc50d3fa/jxt-13-e21.00039-s004-pmcvs_normal.mp4",
    5: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/72c5cf137c20/jxt-13-e21.00039-s005-pmcvs_normal.mp4",
    6: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/81919eb867f0/jxt-13-e21.00039-s006-pmcvs_normal.mp4",
    7: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/c362d4656aec/jxt-13-e21.00039-s007-pmcvs_normal.mp4",
    8: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/ad5165f4a971/jxt-13-e21.00039-s008-pmcvs_normal.mp4",
    9: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/db5d53d38db3/jxt-13-e21.00039-s009-pmcvs_normal.mp4",
    10: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/2e1a7b1e6f2d/jxt-13-e21.00039-s010-pmcvs_normal.mp4",
    11: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/1ec533b3fe25/jxt-13-e21.00039-s011-pmcvs_normal.mp4",
    12: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/5df63b201467/jxt-13-e21.00039-s012-pmcvs_normal.mp4",
    13: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/544848a787ae/jxt-13-e21.00039-s013-pmcvs_normal.mp4",
    14: "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/2847/10807896/f3f229b54a71/jxt-13-e21.00039-s014-pmcvs_normal.mp4",
}


RECORDS: list[VideoRecord] = [
    *[
        VideoRecord(
            record_id=f"PMC10807896_S{i:03d}",
            group="osteomyelitis_pmc",
            title="Surgical Debridement for Acute and Chronic Osteomyelitis in Children",
            source_page="https://pmc.ncbi.nlm.nih.gov/articles/PMC10807896/",
            download_url=CHILD_DEBRIDEMENT_CDN[i],
            local_rel_path=f"osteomyelitis_pmc/PMC10807896_child_debridement/jxt-13-e21.00039-s{i:03d}.mp4",
            fluorescence="no",
            medical_scene="pediatric acute/chronic osteomyelitis debridement",
            usable_for_training="no_labels_demo_or_self_supervised_only",
            notes="Non-fluorescence surgical technique video.",
        )
        for i in range(1, 15)
    ],
    VideoRecord(
        "PMC12350196_MMC1",
        "osteomyelitis_pmc",
        "Biportal Endoscopic Intramedullary Debridement for Management of Tibial Osteomyelitis",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC12350196/",
        pmc("12350196", "mmc1.mp4"),
        "osteomyelitis_pmc/PMC12350196_tibial_endoscopic_debridement/mmc1.mp4",
        "no",
        "tibial osteomyelitis endoscopic intramedullary debridement",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence technique video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/42/81/PMC12350196.tar.gz",
    ),
    VideoRecord(
        "PMC12147590_MMC1",
        "osteomyelitis_pmc",
        "Phalangeal Reaming and Irrigation for Combined Proximal and Distal Phalangeal Osteomyelitis of the Thumb",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC12147590/",
        pmc("12147590", "mmc1.mp4"),
        "osteomyelitis_pmc/PMC12147590_thumb_phalangeal_osteomyelitis/mmc1.mp4",
        "no",
        "thumb phalangeal osteomyelitis reaming and irrigation",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence small-bone osteomyelitis video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/e5/79/PMC12147590.tar.gz",
    ),
    VideoRecord(
        "PMC12078111_S001",
        "osteomyelitis_pmc",
        "Treatment for Calcaneal Osteomyelitis with Pseudoarthrosis",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC12078111/",
        pmc("12078111", "jprs-02-04-0150-s001.mp4"),
        "osteomyelitis_pmc/PMC12078111_calcaneal_osteomyelitis/jprs-02-04-0150-s001.mp4",
        "no",
        "calcaneal osteomyelitis reconstruction",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence reconstruction video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/d8/33/PMC12078111.tar.gz",
    ),
    VideoRecord(
        "PMC4405963_V001",
        "osteomyelitis_pmc",
        "Tuberculous osteomyelitis of the maxilla",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4405963/",
        pmc("4405963", "NJMS-5-188-v001.flv"),
        "osteomyelitis_pmc/PMC4405963_maxilla_tuberculous_osteomyelitis/NJMS-5-188-v001.flv",
        "no",
        "maxillary tuberculous osteomyelitis case video",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence FLV; transcode before model pipeline use.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/99/d4/PMC4405963.tar.gz",
    ),
    VideoRecord(
        "PMC4405963_V002",
        "osteomyelitis_pmc",
        "Tuberculous osteomyelitis of the maxilla",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC4405963/",
        pmc("4405963", "NJMS-5-188-v002.flv"),
        "osteomyelitis_pmc/PMC4405963_maxilla_tuberculous_osteomyelitis/NJMS-5-188-v002.flv",
        "no",
        "maxillary tuberculous osteomyelitis case video",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence FLV; transcode before model pipeline use.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/99/d4/PMC4405963.tar.gz",
    ),
    VideoRecord(
        "PMC10547659_ESM1",
        "osteomyelitis_pmc",
        "Abscess pulsatility: a sonographic sign of osteomyelitis",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC10547659/",
        pmc("10547659", "13089_2023_339_MOESM1_ESM.mp4"),
        "osteomyelitis_pmc/PMC10547659_osteomyelitis_ultrasound/13089_2023_339_MOESM1_ESM.mp4",
        "no",
        "osteomyelitis ultrasound diagnostic video",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence ultrasound video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/84/1d/PMC10547659.tar.gz",
    ),
    *[
        VideoRecord(
            record_id=f"PMC12914110_MMC{i}",
            group="osteomyelitis_pmc",
            title="Mucormycotic osteomyelitis following anterior cruciate ligament reconstruction",
            source_page="https://pmc.ncbi.nlm.nih.gov/articles/PMC12914110/",
            download_url=pmc("12914110", f"mmc{i}.mp4"),
            local_rel_path=f"osteomyelitis_pmc/PMC12914110_mucormycotic_osteomyelitis/mmc{i}.mp4",
            fluorescence="no",
            medical_scene="fungal osteomyelitis case video",
            usable_for_training="no_labels_demo_or_self_supervised_only",
            notes="Non-fluorescence case video.",
            oa_package_url="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/ca/1b/PMC12914110.tar.gz",
        )
        for i in range(1, 4)
    ],
    VideoRecord(
        "PMC12879947_S001",
        "osteomyelitis_pmc",
        "Tibialization of Fibula for Large Segment Tibia Loss Following Chronic Osteomyelitis",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC12879947/",
        pmc("12879947", "gox-14-e7440-s001.mp4"),
        "osteomyelitis_pmc/PMC12879947_chronic_osteomyelitis_reconstruction/gox-14-e7440-s001.mp4",
        "no",
        "chronic osteomyelitis reconstruction",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence reconstruction video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/e3/6c/PMC12879947.tar.gz",
    ),
    VideoRecord(
        "PMC12456365_V1",
        "osteomyelitis_pmc",
        "A rare case report of metacarpal osteomyelitis following a domestic cat bite",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC12456365/",
        pmc("12456365", "JDRS-2025-36-3-763-771-V1.mp4"),
        "osteomyelitis_pmc/PMC12456365_metacarpal_osteomyelitis/JDRS-2025-36-3-763-771-V1.mp4",
        "no",
        "metacarpal osteomyelitis case video",
        "no_labels_demo_or_self_supervised_only",
        "Non-fluorescence small-bone osteomyelitis video.",
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/78/4c/PMC12456365.tar.gz",
    ),
    VideoRecord(
        "DRYAD_OFDVDNET_DATA",
        "fluorescence_proxy",
        "OFDVDnet fluorescence-guided surgery video dataset",
        "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
        "https://datadryad.org/downloads/file_stream/3078626",
        "fluorescence_proxy/ofdvdnet_dryad_v6wwpzh3w/data.zip",
        "yes",
        "mock chicken-thigh fluorescence-guided surgery",
        "enhancement_or_self_supervised_only",
        "ICG-like fluorescence proxy; not osteomyelitis.",
    ),
    VideoRecord(
        "DRYAD_OFDVDNET_README",
        "fluorescence_proxy",
        "OFDVDnet fluorescence-guided surgery video dataset README",
        "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
        "https://datadryad.org/downloads/file_stream/3082579",
        "fluorescence_proxy/ofdvdnet_dryad_v6wwpzh3w/README.md",
        "yes",
        "mock chicken-thigh fluorescence-guided surgery",
        "documentation",
        "Source README.",
    ),
    VideoRecord(
        "DRYAD_FGS_DATA_MODELS",
        "fluorescence_proxy",
        "FGS video denoising dataset and models",
        "https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9",
        "https://datadryad.org/downloads/file_stream/3822101",
        "fluorescence_proxy/fgs_video_denoising_dryad_8gtht76x9/FGS_Data_and_Models.zip",
        "yes",
        "mock fluorescence-guided surgery",
        "enhancement_or_self_supervised_only",
        "Large ICG-like fluorescence proxy; not osteomyelitis.",
    ),
    VideoRecord(
        "DRYAD_FGS_README",
        "fluorescence_proxy",
        "FGS video denoising dataset README",
        "https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9",
        "https://datadryad.org/downloads/file_stream/3822102",
        "fluorescence_proxy/fgs_video_denoising_dryad_8gtht76x9/README.md",
        "yes",
        "mock fluorescence-guided surgery",
        "documentation",
        "Source README.",
    ),
]


def selected_records(groups: set[str] | None) -> Iterable[VideoRecord]:
    for record in RECORDS:
        if groups is None or record.group in groups:
            yield record


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(record: VideoRecord, session: requests.Session, overwrite: bool = False) -> dict[str, str]:
    local_path = RAW_ROOT / record.local_rel_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists() and local_path.stat().st_size > 0 and not overwrite:
        return build_manifest_row(record, local_path, "exists", "skipped_existing")

    tmp_path = local_path.with_name(local_path.name + ".part")
    headers = {
        "User-Agent": "Mozilla/5.0 osteo-vision research downloader",
        "Referer": record.source_page,
    }
    status = "downloaded"
    error = ""
    try:
        response = session.get(record.download_url, headers=headers, stream=True, timeout=(30, 180), allow_redirects=True)
        response = _retry_after_pmc_pow(session, response, record.download_url, headers)
        with response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        tmp_path.replace(local_path)
        if local_path.stat().st_size < 1024 and local_path.suffix.lower() not in {".md", ".txt"}:
            status = "suspicious_small_file"
            error = "downloaded file smaller than 1KB"
        elif "text/html" in content_type and local_path.suffix.lower() not in {".md", ".txt"}:
            status = "suspicious_content_type"
            error = f"content-type={content_type}"
        if status.startswith("suspicious") and record.oa_package_url:
            recovered = _safe_recover_from_oa_package(record, local_path, session, headers)
            if recovered:
                status = "downloaded_via_oa_package"
                error = "direct link returned HTML; extracted from PMC OA package"
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        if tmp_path.exists():
            tmp_path.unlink()
        if record.oa_package_url:
            recovered = _safe_recover_from_oa_package(record, local_path, session, headers)
            if recovered:
                status = "downloaded_via_oa_package"
                error = f"direct download failed; extracted from PMC OA package after {type(exc).__name__}"
    return build_manifest_row(record, local_path, status, error)


def _safe_recover_from_oa_package(
    record: VideoRecord,
    local_path: Path,
    session: requests.Session,
    headers: dict[str, str],
) -> bool:
    try:
        return _recover_from_oa_package(record, local_path, session, headers)
    except Exception:
        return False


def _recover_from_oa_package(
    record: VideoRecord,
    local_path: Path,
    session: requests.Session,
    headers: dict[str, str],
) -> bool:
    package_path = _download_oa_package(record.oa_package_url, session, headers)
    if not package_path.exists():
        return False
    target_name = local_path.name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(package_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile() or Path(member.name).name != target_name:
                    continue
                source = archive.extractfile(member)
                if source is None:
                    continue
                with local_path.open("wb") as handle:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        if chunk:
                            handle.write(chunk)
                return local_path.exists() and local_path.stat().st_size > 0
    except tarfile.TarError:
        return False
    return False


def _download_oa_package(url: str, session: requests.Session, headers: dict[str, str]) -> Path:
    parsed = urlparse(url)
    package_url = url
    package_dir = RAW_ROOT / "oa_packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    package_path = package_dir / Path(parsed.path).name
    if package_path.exists() and package_path.stat().st_size > 0:
        return package_path
    tmp_path = package_path.with_name(package_path.name + ".part")
    if parsed.scheme == "ftp":
        with tmp_path.open("wb") as handle:
            with urllib.request.urlopen(package_url, timeout=180) as response:  # noqa: S310
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    else:
        with session.get(package_url, headers=headers, stream=True, timeout=(30, 180), allow_redirects=True) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
    tmp_path.replace(package_path)
    return package_path


def _retry_after_pmc_pow(
    session: requests.Session,
    response: requests.Response,
    url: str,
    headers: dict[str, str],
) -> requests.Response:
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        return response
    text = response.text
    if "POW_CHALLENGE" not in text or "Preparing to download" not in text:
        return response
    challenge = _extract_js_const(text, "POW_CHALLENGE")
    difficulty = int(_extract_js_const(text, "POW_DIFFICULTY") or "4")
    cookie_name = _extract_js_const(text, "POW_COOKIE_NAME") or "cloudpmc-viewer-pow"
    cookie_path = _extract_js_const(text, "POW_COOKIE_PATH") or "/"
    nonce = _solve_pow(challenge, difficulty)
    session.cookies.set(cookie_name, f"{challenge},{nonce}", path=cookie_path, domain=".nih.gov")
    response.close()
    return session.get(url, headers=headers, stream=True, timeout=(30, 180), allow_redirects=True)


def _extract_js_const(text: str, name: str) -> str:
    match = re.search(rf'{name}\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _solve_pow(challenge: str, difficulty: int) -> int:
    prefix = "0" * difficulty
    nonce = 0
    while True:
        digest = hashlib.sha256(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            return nonce
        nonce += 1


def build_manifest_row(record: VideoRecord, local_path: Path, status: str, error: str) -> dict[str, str]:
    exists = local_path.exists()
    size = local_path.stat().st_size if exists else 0
    checksum = ""
    if exists and size <= 1024 * 1024 * 1024:
        checksum = sha256_for_file(local_path)
    return {
        "record_id": record.record_id,
        "group": record.group,
        "title": record.title,
        "source_page_original_link": record.source_page,
        "direct_download_link": record.download_url,
        "local_path": str(local_path),
        "fluorescence": record.fluorescence,
        "medical_scene": record.medical_scene,
        "usable_for_training": record.usable_for_training,
        "notes": record.notes,
        "download_status": status,
        "error_or_note": error,
        "size_bytes": str(size),
        "sha256": checksum,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(rows: list[dict[str, str]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record_id",
        "group",
        "title",
        "source_page_original_link",
        "direct_download_link",
        "local_path",
        "fluorescence",
        "medical_scene",
        "usable_for_training",
        "notes",
        "download_status",
        "error_or_note",
        "size_bytes",
        "sha256",
        "downloaded_at_utc",
    ]
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public fluorescence and osteomyelitis video candidates.")
    parser.add_argument("--groups", nargs="*", default=None, help="Groups to download: osteomyelitis_pmc fluorescence_proxy")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    groups = set(args.groups) if args.groups else None
    downloaded_rows: dict[str, dict[str, str]] = {}
    records = list(selected_records(groups))
    session = requests.Session()
    for index, record in enumerate(records, start=1):
        print(f"[{index}/{len(records)}] {record.record_id} -> {record.local_rel_path}", flush=True)
        row = download(record, session, overwrite=args.overwrite)
        downloaded_rows[record.record_id] = row
        print(f"  {row['download_status']} {row['size_bytes']} bytes", flush=True)
    rows: list[dict[str, str]] = []
    for record in RECORDS:
        if record.record_id in downloaded_rows:
            rows.append(downloaded_rows[record.record_id])
            continue
        local_path = RAW_ROOT / record.local_rel_path
        status = "exists" if local_path.exists() and local_path.stat().st_size > 0 else "not_requested_or_missing"
        rows.append(build_manifest_row(record, local_path, status, ""))
    write_manifest(rows)
    print(f"manifest={MANIFEST_PATH}", flush=True)


if __name__ == "__main__":
    main()
