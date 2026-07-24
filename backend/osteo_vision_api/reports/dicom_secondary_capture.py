from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from backend.osteo_vision_api.domains.cases.schemas import CaseRecord
from backend.osteo_vision_api.reports.platform_report_sections import (
    latest_quantification_from_report,
    platform_safety_lines,
    quantification_summary_lines,
)
from osteo_vision_core.core.paths import ensure_dir


def write_secondary_capture_dicom(path: str | Path, case: CaseRecord, report: dict[str, Any]) -> str:
    """Write a minimal DICOM Secondary Capture image for archive/platform export."""

    output = Path(path)
    ensure_dir(output.parent)
    pixels = _render_report_pixels(case, report)
    now = datetime.now(timezone.utc)
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    dataset = FileDataset(str(output), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = file_meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.PatientName = "OsteoVision^Platform"
    dataset.PatientID = _dicom_safe_identifier(case.case_id)
    dataset.PatientIdentityRemoved = "YES"
    dataset.DeidentificationMethod = "Platform pseudonymized export; review source data locally."
    dataset.StudyDate = now.strftime("%Y%m%d")
    dataset.StudyTime = now.strftime("%H%M%S")
    dataset.ContentDate = dataset.StudyDate
    dataset.ContentTime = dataset.StudyTime
    dataset.AccessionNumber = ""
    dataset.Modality = "OT"
    dataset.Manufacturer = "Osteo Vision Platform"
    dataset.InstitutionName = ""
    dataset.StudyDescription = "Osteo Vision platform validation evidence export"
    dataset.SeriesDescription = "Secondary capture evidence summary"
    dataset.ImageType = ["DERIVED", "SECONDARY", "REPORT"]
    dataset.ConversionType = "WSD"
    dataset.BurnedInAnnotation = "YES"
    dataset.LossyImageCompression = "00"
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.Rows = int(pixels.shape[0])
    dataset.Columns = int(pixels.shape[1])
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels.tobytes()
    dataset.save_as(output, enforce_file_format=True)
    return str(output)


def _render_report_pixels(case: CaseRecord, report: dict[str, Any]) -> np.ndarray:
    width, height = 1024, 768
    image = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    quantification = latest_quantification_from_report(report)
    lines = [
        "Osteo Vision Evidence Summary",
        f"Case ID: {case.case_id}",
        f"Title: {case.title}",
        f"Status: {case.status.value}",
        f"Inputs: {len(case.inputs)}",
        f"Analysis runs: {len(case.analysis_runs)}",
        f"Review events: {len(case.review_events)}",
        "",
        "Latest quantification:",
        *quantification_summary_lines(quantification),
        "",
        "Safety boundary:",
        *platform_safety_lines(),
    ]
    x, y = 36, 32
    line_height = 17
    for raw_line in lines:
        for line in _wrap_text(raw_line, max_chars=118):
            if y > height - 36:
                break
            draw.text((x, y), line, fill=0, font=font)
            y += line_height
        if y > height - 36:
            break
    return np.asarray(image, dtype=np.uint8)


def _wrap_text(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _dicom_safe_identifier(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_." else "_" for char in value)
    return safe[:64] or "platform_case"
