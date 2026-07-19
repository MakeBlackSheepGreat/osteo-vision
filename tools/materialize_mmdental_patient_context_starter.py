from __future__ import annotations

import argparse
import binascii
import csv
import gzip
import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = ROOT / "research/datasets/public-candidates/mmdental_patient_context_starter_20260719"

DATASET_ID = "D069"
DATASET_NAME = "MMDental - tooth CBCT images with expert medical records"
FIGSHARE_ARTICLE_ID = 28_505_276
FIGSHARE_FILE_ID = 53_187_695
FIGSHARE_API_URL = f"https://api.figshare.com/v2/articles/{FIGSHARE_ARTICLE_ID}"
FIGSHARE_DOWNLOAD_URL = f"https://ndownloader.figshare.com/files/{FIGSHARE_FILE_ID}"
DATACITE_URL = "https://api.datacite.org/dois/10.6084/m9.figshare.28505276"
ARTICLE_XML_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12241571/fullTextXML"
SOURCE_PAGE_URL = (
    "https://springernature.figshare.com/articles/dataset/"
    "MMDental_-_A_multimodal_dataset_of_tooth_CBCT_images_with_expert_medical_records/"
    "28505276"
)
REMOTE_ZIP_SIZE = 68_087_010_723
REMOTE_ZIP_MD5 = "99c0059775735ddb612b635547f41e3f"

EOCD_SIGNATURE = b"PK\x05\x06"
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
CENTRAL_FILE_SIGNATURE = b"PK\x01\x02"
LOCAL_FILE_SIGNATURE = b"PK\x03\x04"


class RangeReader(Protocol):
    size: int

    def read_range(self, start: int, end: int) -> bytes:
        """Return the inclusive byte range [start, end]."""


class CurlRangeReader:
    def __init__(self, url: str, size: int) -> None:
        self.url = url
        self.size = size

    def read_range(self, start: int, end: int) -> bytes:
        if start < 0 or end < start or end >= self.size:
            raise ValueError(f"Invalid range {start}-{end} for {self.size} bytes")
        expected = end - start + 1
        payload = _curl_bytes(
            self.url,
            expected_status=206,
            max_bytes=expected,
            byte_range=(start, end),
        )
        if len(payload) != expected:
            raise RuntimeError(f"Range response length mismatch: expected {expected}, got {len(payload)}")
        return payload


class BytesRangeReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.size = len(payload)

    def read_range(self, start: int, end: int) -> bytes:
        if start < 0 or end < start or end >= self.size:
            raise ValueError(f"Invalid range {start}-{end} for {self.size} bytes")
        return self.payload[start : end + 1]


@dataclass(frozen=True)
class ZipMember:
    name: str
    compression_method: int
    flags: int
    crc32: int
    compressed_size: int
    uncompressed_size: int
    local_header_offset: int


@dataclass(frozen=True)
class ZipDirectory:
    entry_count: int
    central_directory_offset: int
    central_directory_size: int
    zip64: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _crc32(path: Path) -> int:
    value = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value = binascii.crc32(chunk, value)
    return value & 0xFFFFFFFF


def _binary_stl_geometry_summary(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    if len(payload) < 84:
        raise RuntimeError(f"Binary STL is truncated: {path}")
    triangle_count = struct.unpack_from("<I", payload, 80)[0]
    expected_size = 84 + triangle_count * 50
    if len(payload) != expected_size:
        raise RuntimeError(f"Binary STL length mismatch: expected {expected_size}, got {len(payload)}")
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]
    finite = True
    for triangle in struct.iter_unpack("<12fH", memoryview(payload)[84:]):
        coordinates = triangle[3:12]
        for offset in range(0, 9, 3):
            for axis in range(3):
                value = float(coordinates[offset + axis])
                finite = finite and math.isfinite(value)
                minimum[axis] = min(minimum[axis], value)
                maximum[axis] = max(maximum[axis], value)
    if triangle_count == 0 or not finite:
        raise RuntimeError("Binary STL must contain finite, non-empty geometry")
    return {
        "triangle_count": triangle_count,
        "vertex_reference_count": triangle_count * 3,
        "bounds_min_xyz": minimum,
        "bounds_max_xyz": maximum,
        "extent_xyz": [maximum[index] - minimum[index] for index in range(3)],
        "finite_geometry": finite,
    }


def _curl_bytes(
    url: str,
    *,
    expected_status: int = 200,
    max_bytes: int = 16 * 1024 * 1024,
    byte_range: tuple[int, int] | None = None,
) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required for this Figshare endpoint")
    command = [
        curl,
        "--silent",
        "--show-error",
        "--location",
        "--fail",
        "--retry",
        "3",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--max-time",
        "180",
        "--max-filesize",
        str(max_bytes),
        "--proto",
        "=https",
        "--user-agent",
        "osteo-vision-public-dataset-materializer/1.0",
        "--write-out",
        "%{stderr}__OSTEO_HTTP_STATUS__=%{http_code}\n",
    ]
    if byte_range is not None:
        command.extend(["--range", f"{byte_range[0]}-{byte_range[1]}"])
    command.append(url)
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=240,
    )
    stderr = completed.stderr.decode("utf-8", errors="replace")
    status_lines = [line for line in stderr.splitlines() if line.startswith("__OSTEO_HTTP_STATUS__=")]
    status = int(status_lines[-1].split("=", 1)[1]) if status_lines else 0
    if completed.returncode != 0 or status != expected_status:
        detail = "\n".join(
            line for line in stderr.splitlines() if not line.startswith("__OSTEO_HTTP_STATUS__=")
        ).strip()
        raise RuntimeError(f"curl failed for {url}: exit={completed.returncode}, HTTP={status}, detail={detail}")
    if len(completed.stdout) > max_bytes:
        raise RuntimeError(f"Response exceeded the {max_bytes}-byte safety limit")
    if not completed.stdout:
        raise RuntimeError(f"Empty response from {url}")
    return completed.stdout


def _write_download(url: str, destination: Path) -> None:
    payload = _curl_bytes(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def _zip_directory(reader: RangeReader) -> ZipDirectory:
    tail_size = min(reader.size, 256 * 1024)
    tail_offset = reader.size - tail_size
    tail = reader.read_range(tail_offset, reader.size - 1)
    eocd_index = tail.rfind(EOCD_SIGNATURE)
    if eocd_index < 0 or eocd_index + 22 > len(tail):
        raise RuntimeError("ZIP end-of-central-directory record was not found")

    (
        signature,
        disk_number,
        central_disk,
        disk_entry_count,
        total_entry_count,
        central_size_32,
        central_offset_32,
        comment_length,
    ) = struct.unpack_from("<4s4H2LH", tail, eocd_index)
    if signature != EOCD_SIGNATURE:
        raise RuntimeError("Invalid ZIP end-of-central-directory signature")
    if disk_number != 0 or central_disk != 0 or disk_entry_count != total_entry_count:
        raise RuntimeError("Multi-disk ZIP archives are not supported")
    if eocd_index + 22 + comment_length > len(tail):
        raise RuntimeError("Truncated ZIP end-of-central-directory comment")

    requires_zip64 = total_entry_count == 0xFFFF or central_size_32 == 0xFFFFFFFF or central_offset_32 == 0xFFFFFFFF
    if not requires_zip64:
        return ZipDirectory(
            entry_count=total_entry_count,
            central_directory_offset=central_offset_32,
            central_directory_size=central_size_32,
            zip64=False,
        )

    eocd_absolute = tail_offset + eocd_index
    locator_offset = eocd_absolute - 20
    if locator_offset < 0:
        raise RuntimeError("ZIP64 locator offset is invalid")
    locator = reader.read_range(locator_offset, eocd_absolute - 1)
    locator_signature, zip64_disk, zip64_offset, total_disks = struct.unpack("<4sLQL", locator)
    if locator_signature != ZIP64_LOCATOR_SIGNATURE:
        raise RuntimeError("ZIP64 locator was not found before the ZIP terminator")
    if zip64_disk != 0 or total_disks != 1:
        raise RuntimeError("Multi-disk ZIP64 archives are not supported")

    zip64_record = reader.read_range(zip64_offset, zip64_offset + 55)
    (
        zip64_signature,
        _record_size,
        _version_made,
        _version_needed,
        disk_number_64,
        central_disk_64,
        disk_entry_count_64,
        total_entry_count_64,
        central_size_64,
        central_offset_64,
    ) = struct.unpack("<4sQ2H2L4Q", zip64_record)
    if zip64_signature != ZIP64_EOCD_SIGNATURE:
        raise RuntimeError("Invalid ZIP64 end-of-central-directory signature")
    if disk_number_64 != 0 or central_disk_64 != 0 or disk_entry_count_64 != total_entry_count_64:
        raise RuntimeError("Multi-disk ZIP64 archives are not supported")
    return ZipDirectory(
        entry_count=total_entry_count_64,
        central_directory_offset=central_offset_64,
        central_directory_size=central_size_64,
        zip64=True,
    )


def _zip64_values(
    extra: bytes,
    *,
    uncompressed_size: int,
    compressed_size: int,
    local_header_offset: int,
    disk_start: int,
) -> tuple[int, int, int, int]:
    cursor = 0
    while cursor + 4 <= len(extra):
        field_id, field_size = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        field_end = cursor + field_size
        if field_end > len(extra):
            raise RuntimeError("Truncated ZIP extra field")
        if field_id != 0x0001:
            cursor = field_end
            continue
        values = extra[cursor:field_end]
        value_cursor = 0

        def take_u64() -> int:
            nonlocal value_cursor
            if value_cursor + 8 > len(values):
                raise RuntimeError("Truncated ZIP64 64-bit extra value")
            value = struct.unpack_from("<Q", values, value_cursor)[0]
            value_cursor += 8
            return value

        def take_u32() -> int:
            nonlocal value_cursor
            if value_cursor + 4 > len(values):
                raise RuntimeError("Truncated ZIP64 32-bit extra value")
            value = struct.unpack_from("<L", values, value_cursor)[0]
            value_cursor += 4
            return value

        if uncompressed_size == 0xFFFFFFFF:
            uncompressed_size = take_u64()
        if compressed_size == 0xFFFFFFFF:
            compressed_size = take_u64()
        if local_header_offset == 0xFFFFFFFF:
            local_header_offset = take_u64()
        if disk_start == 0xFFFF:
            disk_start = take_u32()
        return (
            uncompressed_size,
            compressed_size,
            local_header_offset,
            disk_start,
        )
    raise RuntimeError("Required ZIP64 extra field was not found")


def _central_members(reader: RangeReader) -> tuple[ZipDirectory, list[ZipMember]]:
    directory = _zip_directory(reader)
    start = directory.central_directory_offset
    end = start + directory.central_directory_size - 1
    payload = reader.read_range(start, end)
    members: list[ZipMember] = []
    cursor = 0
    while cursor < len(payload) and len(members) < directory.entry_count:
        if cursor + 46 > len(payload):
            raise RuntimeError("Truncated central-directory file header")
        (
            signature,
            _version_made,
            _version_needed,
            flags,
            compression_method,
            _modified_time,
            _modified_date,
            crc32,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
            comment_length,
            disk_start,
            _internal_attributes,
            _external_attributes,
            local_header_offset,
        ) = struct.unpack_from("<4s6H3L5H2L", payload, cursor)
        if signature != CENTRAL_FILE_SIGNATURE:
            raise RuntimeError(f"Invalid central-directory signature at byte {cursor}")
        variable_start = cursor + 46
        name_end = variable_start + name_length
        extra_end = name_end + extra_length
        record_end = extra_end + comment_length
        if record_end > len(payload):
            raise RuntimeError("Truncated central-directory variable fields")
        name_bytes = payload[variable_start:name_end]
        extra = payload[name_end:extra_end]
        if (
            uncompressed_size == 0xFFFFFFFF
            or compressed_size == 0xFFFFFFFF
            or local_header_offset == 0xFFFFFFFF
            or disk_start == 0xFFFF
        ):
            (
                uncompressed_size,
                compressed_size,
                local_header_offset,
                disk_start,
            ) = _zip64_values(
                extra,
                uncompressed_size=uncompressed_size,
                compressed_size=compressed_size,
                local_header_offset=local_header_offset,
                disk_start=disk_start,
            )
        if disk_start != 0:
            raise RuntimeError("Multi-disk ZIP member is not supported")
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        name = name_bytes.decode(encoding)
        members.append(
            ZipMember(
                name=name,
                compression_method=compression_method,
                flags=flags,
                crc32=crc32,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                local_header_offset=local_header_offset,
            )
        )
        cursor = record_end
    if len(members) != directory.entry_count:
        raise RuntimeError(f"Central-directory entry mismatch: expected {directory.entry_count}, got {len(members)}")
    return directory, members


def _find_member(members: list[ZipMember], suffix: str) -> ZipMember:
    normalized_suffix = suffix.replace("\\", "/").lower()
    matches = [member for member in members if member.name.replace("\\", "/").lower().endswith(normalized_suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one ZIP member ending in {suffix!r}, found {len(matches)}")
    return matches[0]


def _extract_member(reader: RangeReader, member: ZipMember) -> bytes:
    if member.flags & 0x0001:
        raise RuntimeError("Encrypted ZIP members are not supported")
    header = reader.read_range(member.local_header_offset, member.local_header_offset + 29)
    (
        signature,
        _version_needed,
        flags,
        compression_method,
        _modified_time,
        _modified_date,
        _crc32,
        _compressed_size,
        _uncompressed_size,
        name_length,
        extra_length,
    ) = struct.unpack("<4s5H3L2H", header)
    if signature != LOCAL_FILE_SIGNATURE:
        raise RuntimeError("Invalid local ZIP member header")
    if flags != member.flags or compression_method != member.compression_method:
        raise RuntimeError("Central and local ZIP headers disagree")
    data_start = member.local_header_offset + 30 + name_length + extra_length
    if member.compressed_size == 0:
        compressed = b""
    else:
        compressed = reader.read_range(data_start, data_start + member.compressed_size - 1)
    if member.compression_method == 0:
        payload = compressed
    elif member.compression_method == 8:
        payload = zlib.decompress(compressed, -zlib.MAX_WBITS)
    else:
        raise RuntimeError(f"Unsupported ZIP compression method {member.compression_method}")
    if len(payload) != member.uncompressed_size:
        raise RuntimeError(f"Uncompressed size mismatch: expected {member.uncompressed_size}, got {len(payload)}")
    crc32 = binascii.crc32(payload) & 0xFFFFFFFF
    if crc32 != member.crc32:
        raise RuntimeError(f"CRC32 mismatch: expected {member.crc32:08x}, got {crc32:08x}")
    return payload


def _materialize_member(
    reader: RangeReader,
    member: ZipMember,
    destination: Path,
) -> None:
    if (
        destination.is_file()
        and destination.stat().st_size == member.uncompressed_size
        and _crc32(destination) == member.crc32
    ):
        return
    payload = _extract_member(reader, member)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.partial")
    partial.write_bytes(payload)
    if partial.stat().st_size != member.uncompressed_size or _crc32(partial) != member.crc32:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Extracted ZIP member failed integrity validation: {member.name}")
    partial.replace(destination)


def _nifti_gzip_header_summary(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rb") as handle:
        header = handle.read(348)
    if len(header) != 348:
        raise RuntimeError(f"Truncated NIfTI header in {path}")
    if struct.unpack_from("<I", header, 0)[0] == 348:
        endian = "little"
        prefix = "<"
    elif struct.unpack_from(">I", header, 0)[0] == 348:
        endian = "big"
        prefix = ">"
    else:
        raise RuntimeError(f"Invalid NIfTI sizeof_hdr in {path}")
    dimensions = struct.unpack_from(f"{prefix}8h", header, 40)
    dimension_count = int(dimensions[0])
    if dimension_count < 1 or dimension_count > 7:
        raise RuntimeError(f"Invalid NIfTI dimension count {dimension_count}")
    pixdim = struct.unpack_from(f"{prefix}8f", header, 76)
    unit_code = int(header[123])
    spatial_unit_code = unit_code & 0x07
    temporal_unit_code = unit_code & 0x38
    return {
        "header_bytes": 348,
        "endianness": endian,
        "shape": [int(value) for value in dimensions[1 : dimension_count + 1]],
        "datatype_code": int(struct.unpack_from(f"{prefix}h", header, 70)[0]),
        "bitpix": int(struct.unpack_from(f"{prefix}h", header, 72)[0]),
        "voxel_spacing": [float(value) for value in pixdim[1 : dimension_count + 1]],
        "spatial_unit": {1: "meter", 2: "millimeter", 3: "micrometer"}.get(spatial_unit_code, "unknown"),
        "spatial_unit_code": spatial_unit_code,
        "temporal_unit_code": temporal_unit_code,
        "vox_offset": float(struct.unpack_from(f"{prefix}f", header, 108)[0]),
        "magic": header[344:348].rstrip(b"\x00").decode("ascii", errors="replace"),
    }


def _csv_summary(path: Path) -> dict[str, Any]:
    encodings = ("utf-8-sig", "utf-8", "gb18030")
    rows: list[dict[str, str]] | None = None
    selected_encoding = ""
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                rows = list(csv.DictReader(handle))
            selected_encoding = encoding
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        raise RuntimeError("medical_records.csv could not be decoded safely")
    columns = list(rows[0].keys()) if rows else []
    lower_columns = {column.lower().strip(): column for column in columns}
    age_column = lower_columns.get("age")
    sex_column = lower_columns.get("sex")
    filename_column = lower_columns.get("filename")
    ages: list[float] = []
    sex_counts: dict[str, int] = {}
    unique_ids: set[str] = set()
    rows_by_patient: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if age_column:
            try:
                ages.append(float(str(row.get(age_column, "")).strip()))
            except ValueError:
                pass
        if sex_column:
            value = str(row.get(sex_column, "")).strip().lower() or "missing"
            sex_counts[value] = sex_counts.get(value, 0) + 1
        if filename_column:
            value = str(row.get(filename_column, "")).strip()
            if value:
                unique_ids.add(value)
                rows_by_patient.setdefault(value, []).append(row)
    non_missing_by_column = {column: sum(bool(str(row.get(column, "")).strip()) for row in rows) for column in columns}
    patient_level_sex_counts: dict[str, int] = {}
    sex_conflict_patient_count = 0
    age_conflict_patient_count = 0
    patients_with_present_history = 0
    patients_with_past_history = 0
    patients_with_diagnosis = 0
    for patient_rows in rows_by_patient.values():
        sex_values = {
            str(row.get(sex_column, "")).strip().lower()
            for row in patient_rows
            if sex_column and str(row.get(sex_column, "")).strip()
        }
        age_values = {
            str(row.get(age_column, "")).strip()
            for row in patient_rows
            if age_column and str(row.get(age_column, "")).strip()
        }
        if len(sex_values) > 1:
            sex_conflict_patient_count += 1
        elif len(sex_values) == 1:
            value = next(iter(sex_values))
            patient_level_sex_counts[value] = patient_level_sex_counts.get(value, 0) + 1
        if len(age_values) > 1:
            age_conflict_patient_count += 1
        patients_with_present_history += int(
            any(bool(str(row.get("Present medical history", "")).strip()) for row in patient_rows)
        )
        patients_with_past_history += int(
            any(bool(str(row.get("Past medical history", "")).strip()) for row in patient_rows)
        )
        patients_with_diagnosis += int(any(bool(str(row.get("Diagnosis", "")).strip()) for row in patient_rows))
    return {
        "encoding": selected_encoding,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "unique_filename_count": len(unique_ids),
        "repeated_visit_record_count": len(rows) - len(unique_ids),
        "patients_with_multiple_visit_records": sum(len(patient_rows) > 1 for patient_rows in rows_by_patient.values()),
        "age_non_missing_count": len(ages),
        "age_min": min(ages) if ages else None,
        "age_max": max(ages) if ages else None,
        "sex_counts": sex_counts,
        "patient_level_sex_counts": patient_level_sex_counts,
        "sex_conflict_patient_count": sex_conflict_patient_count,
        "age_conflict_patient_count": age_conflict_patient_count,
        "patients_with_present_medical_history": patients_with_present_history,
        "patients_with_past_medical_history": patients_with_past_history,
        "patients_with_diagnosis": patients_with_diagnosis,
        "column_non_missing_counts": non_missing_by_column,
        "column_missing_counts": {column: len(rows) - count for column, count in non_missing_by_column.items()},
    }


def _paired_context_summary(path: Path, case_id: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if str(row.get("Filename", "")).strip() == case_id]
    if not rows:
        raise RuntimeError(f"CBCT case {case_id} has no matching clinical record")
    return {
        "case_id": case_id,
        "visit_record_count": len(rows),
        "age_present": any(bool(str(row.get("Age", "")).strip()) for row in rows),
        "sex_present": any(bool(str(row.get("Sex", "")).strip()) for row in rows),
        "diagnosis_present": any(bool(str(row.get("Diagnosis", "")).strip()) for row in rows),
        "medical_history_present": any(
            bool(
                str(row.get("Present medical history", "")).strip() or str(row.get("Past medical history", "")).strip()
            )
            for row in rows
        ),
    }


def _validated_modeling_artifacts(
    *,
    source_cbct_path: Path,
    modeling_manifest_path: Path,
) -> tuple[dict[str, Any] | None, list[Path]]:
    if not modeling_manifest_path.is_file():
        return None, []
    payload = json.loads(modeling_manifest_path.read_text(encoding="utf-8"))
    source_paths = payload.get("source_paths")
    if not isinstance(source_paths, list) or len(source_paths) != 1:
        raise RuntimeError("D069 modeling evidence must bind exactly one source CBCT")
    if Path(str(source_paths[0])).resolve() != source_cbct_path.resolve():
        raise RuntimeError("D069 modeling evidence source path does not match the extracted CBCT")
    if payload.get("modeling_status") != "completed":
        raise RuntimeError("D069 modeling evidence is incomplete")
    surface = payload.get("surface_model")
    evidence = payload.get("three_d_evidence")
    if not isinstance(surface, dict) or not isinstance(evidence, dict):
        raise RuntimeError("D069 modeling evidence lacks surface or safety fields")
    surface_path = Path(str(surface.get("path") or "")).resolve(strict=True)
    surface_sha256 = _sha256(surface_path)
    if surface_sha256 != str(surface.get("sha256") or "").lower():
        raise RuntimeError("D069 proxy surface SHA256 does not match its modeling manifest")
    stl_summary = _binary_stl_geometry_summary(surface_path)
    if stl_summary["triangle_count"] != int(surface.get("face_count", 0)):
        raise RuntimeError("D069 proxy surface triangle count does not match its modeling manifest")
    if (
        evidence.get("navigation_ready") is not False
        or evidence.get("registration_status") != "unregistered"
        or evidence.get("doctor_review_status") != "not_reviewed"
        or evidence.get("segmentation_review_status") != "not_reviewed"
    ):
        raise RuntimeError("D069 proxy surface must remain unregistered, unreviewed, and non-navigation")
    return (
        {
            "source_cbct_path": str(source_cbct_path.resolve()),
            "source_cbct_sha256": _sha256(source_cbct_path),
            "modeling_manifest_path": str(modeling_manifest_path.resolve()),
            "modeling_manifest_sha256": _sha256(modeling_manifest_path),
            "surface_path": str(surface_path),
            "surface_sha256": surface_sha256,
            "vertex_count": int(surface.get("vertex_count", 0)),
            "face_count": int(surface.get("face_count", 0)),
            "proxy_method": payload.get("proxy_method"),
            "decimation_step": int(payload.get("decimation_step", 0)),
            "surface_quality": surface.get("surface_quality"),
            "binary_stl_geometry": stl_summary,
            "registration_status": evidence.get("registration_status"),
            "doctor_review_status": evidence.get("doctor_review_status"),
            "navigation_ready": evidence.get("navigation_ready"),
            "orientation_review_status": evidence.get("orientation_review_status"),
            "data_boundary": evidence.get("data_boundary"),
        },
        [modeling_manifest_path, surface_path],
    )


def materialize(
    output_dir: Path,
    *,
    cbct_case_id: str | None = "492",
    build_proxy_surface: bool = False,
) -> dict[str, Any]:
    dataset_dir = output_dir / "d069"
    metadata_dir = dataset_dir / "metadata"
    raw_dir = dataset_dir / "raw"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    article_path = metadata_dir / "figshare_article_28505276.json"
    datacite_path = metadata_dir / "datacite_10.6084_m9.figshare.28505276.json"
    article_xml_path = metadata_dir / "PMC12241571_fullTextXML.xml"
    _write_download(FIGSHARE_API_URL, article_path)
    _write_download(DATACITE_URL, datacite_path)
    _write_download(ARTICLE_XML_URL, article_xml_path)

    article_metadata = json.loads(article_path.read_text(encoding="utf-8"))
    file_records = article_metadata.get("files")
    if not isinstance(file_records, list) or len(file_records) != 1:
        raise RuntimeError("Unexpected Figshare file list")
    remote_file = file_records[0]
    if int(remote_file.get("id", 0)) != FIGSHARE_FILE_ID:
        raise RuntimeError("Figshare file identifier changed")
    if int(remote_file.get("size", 0)) != REMOTE_ZIP_SIZE:
        raise RuntimeError("Figshare ZIP size changed; review before extraction")
    if str(remote_file.get("computed_md5", "")).lower() != REMOTE_ZIP_MD5:
        raise RuntimeError("Figshare ZIP MD5 changed; review before extraction")

    reader = CurlRangeReader(FIGSHARE_DOWNLOAD_URL, REMOTE_ZIP_SIZE)
    directory, members = _central_members(reader)
    member = _find_member(members, "medical_records.csv")
    payload = _extract_member(reader, member)
    medical_records_path = raw_dir / "medical_records.csv"
    medical_records_path.write_bytes(payload)
    summary = _csv_summary(medical_records_path)
    summary_path = dataset_dir / "medical_records_structural_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    extracted_cbct_members: list[dict[str, Any]] = []
    cbct_paths: list[Path] = []
    paired_context: list[dict[str, Any]] = []
    modeling_artifact_summary: dict[str, Any] | None = None
    modeling_artifact_paths: list[Path] = []
    if cbct_case_id:
        cbct_member = _find_member(members, f"/{cbct_case_id}/{cbct_case_id}.nii.gz")
        cbct_path = raw_dir / "cbct" / cbct_case_id / f"{cbct_case_id}.nii.gz"
        _materialize_member(reader, cbct_member, cbct_path)
        nifti_summary = _nifti_gzip_header_summary(cbct_path)
        paired_summary = _paired_context_summary(medical_records_path, cbct_case_id)
        cbct_paths.append(cbct_path)
        paired_context.append(paired_summary)
        extracted_cbct_members.append(
            {
                **asdict(cbct_member),
                "local_path": str(cbct_path.resolve()),
                "size_bytes": cbct_path.stat().st_size,
                "sha256": _sha256(cbct_path),
                "nifti_header": nifti_summary,
                "paired_context": paired_summary,
            }
        )
        if build_proxy_surface:
            from backend.src.core.settings import load_settings
            from backend.src.services.cbct_modeling_service import (
                build_cbct_surface_model,
            )

            modeling_result = build_cbct_surface_model(
                settings=load_settings(),
                source_path=cbct_path,
                case_id=f"d069_mmdental_{cbct_case_id}",
                dataset_id=DATASET_ID,
                decimation_step=4,
                source_role="volume",
                source_original_filename=cbct_path.name,
            )
            if modeling_result.get("modeling_status") != "completed":
                raise RuntimeError("D069 CBCT proxy modeling did not produce closed engineering evidence")
        modeling_manifest_path = (
            ROOT
            / "artifacts/platform/three_d_models"
            / f"{cbct_case_id}_nii"
            / f"d069_mmdental_{cbct_case_id}_cbct_balanced_hard_tissue_proxy.three_d_evidence.json"
        )
        modeling_artifact_summary, modeling_artifact_paths = _validated_modeling_artifacts(
            source_cbct_path=cbct_path,
            modeling_manifest_path=modeling_manifest_path,
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    local_assets = [
        article_path,
        datacite_path,
        article_xml_path,
        medical_records_path,
        summary_path,
        *cbct_paths,
        *modeling_artifact_paths,
    ]
    local_file_rows = [
        {
            "local_path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in local_assets
    ]
    clinical_variables = (
        "sex, age, chief complaint, follow-up, present and past medical history, oral examination, "
        "diagnosis, treatment plan, management and physician advice"
    )
    recommended_use = (
        "Jaw-domain clinical-context schema, missing-value handling, patient-level grouping and "
        "image-plus-context engineering with one checksum-bound paired CBCT case."
    )
    data_boundary = (
        "Public de-identified dental proxy without osteomyelitis lesion masks, bone-activity labels, "
        "white-light/ICG pairs or intraoperative outcomes. It cannot validate patient-conditioned spatial "
        "effects or clinical segmentation performance."
    )
    manifest = {
        "schema_version": "osteo-vision-mmdental-patient-context-starter-v1",
        "generated_at_utc": generated_at,
        "record_count": 1,
        "total_size_bytes": sum(path.stat().st_size for path in local_assets),
        "dataset_id": DATASET_ID,
        "dataset_name": DATASET_NAME,
        "source_page_url": SOURCE_PAGE_URL,
        "doi": "10.6084/m9.figshare.28505276.v1",
        "article_doi": "10.1038/s41597-025-05398-7",
        "license": "CC BY 4.0",
        "license_review_status": "verified_from_figshare_api_and_datacite",
        "remote_zip": {
            "file_id": FIGSHARE_FILE_ID,
            "file_name": "MMDental.zip",
            "direct_download_url": FIGSHARE_DOWNLOAD_URL,
            "size_bytes": REMOTE_ZIP_SIZE,
            "computed_md5": REMOTE_ZIP_MD5,
            "download_strategy": "HTTP Range selective extraction; full 68 GB ZIP was not downloaded",
            "central_directory": asdict(directory),
            "member_count": len(members),
        },
        "extracted_member": {
            **asdict(member),
            "local_path": str(medical_records_path.resolve()),
            "size_bytes": medical_records_path.stat().st_size,
            "sha256": _sha256(medical_records_path),
            "structural_summary": summary,
        },
        "extracted_cbct_members": extracted_cbct_members,
        "paired_context_summary": paired_context,
        "derived_modeling_artifact": modeling_artifact_summary,
        "local_assets": local_file_rows,
        "modalities": "dental CBCT NIfTI plus expert medical records",
        "clinical_variables": clinical_variables,
        "recommended_use": recommended_use,
        "target_domain_flag": False,
        "training_eligible": False,
        "review_state": "review_required",
        "data_boundary": data_boundary,
        "records": [
            {
                "dataset_id": DATASET_ID,
                "dataset_name": DATASET_NAME,
                "source_page_url": SOURCE_PAGE_URL,
                "direct_download_url": FIGSHARE_DOWNLOAD_URL,
                "license": "CC BY 4.0",
                "license_review_status": "verified_from_figshare_api_and_datacite",
                "domain_tier": "human_dental_cbct_clinical_context_proxy",
                "modality": "dental CBCT NIfTI plus expert medical records",
                "labels": "expert medical records; no pixel segmentation labels",
                "patient_count": 660,
                "clinical_variables": clinical_variables,
                "recommended_use": recommended_use,
                "target_domain_flag": False,
                "training_eligible": False,
                "review_state": "review_required",
                "download_status": "verified_selective_range_extraction",
                "downloaded_at_utc": generated_at,
                "data_boundary": data_boundary,
                "local_files": local_file_rows,
            }
        ],
    }
    manifest_path = output_dir / "mmdental_patient_context_starter_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Selectively materialize the MMDental clinical table without downloading its 68 GB ZIP."
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT.relative_to(ROOT)),
        help="Output directory relative to the repository root unless absolute.",
    )
    parser.add_argument(
        "--cbct-case-id",
        default="492",
        help="One bounded de-identified CBCT case to pair with the clinical table; use an empty value to skip.",
    )
    parser.add_argument(
        "--build-proxy-surface",
        action="store_true",
        help="Run the fail-closed raw-CBCT hard-tissue proxy modeling check after extraction.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    manifest = materialize(
        output_dir.resolve(),
        cbct_case_id=args.cbct_case_id.strip() or None,
        build_proxy_surface=args.build_proxy_surface,
    )
    print(
        json.dumps(
            {
                "manifest": str((output_dir / "mmdental_patient_context_starter_manifest.json").resolve()),
                "row_count": manifest["extracted_member"]["structural_summary"]["row_count"],
                "remote_zip_bytes_avoided": REMOTE_ZIP_SIZE,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
