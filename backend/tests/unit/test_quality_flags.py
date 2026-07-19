from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from backend.src.domains.cases.enums import InputChannel
from backend.src.domains.cases.schemas import CaseRecord, InputCreateRequest
from backend.src.services.input_service import InputService


def test_quality_flags_detect_dimension_mismatch(tmp_path: Path) -> None:
    white = tmp_path / "white.png"
    fluorescence = tmp_path / "fluorescence.png"
    Image.fromarray(np.zeros((20, 20, 3), dtype=np.uint8)).save(white)
    Image.fromarray(np.zeros((12, 12), dtype=np.uint8)).save(fluorescence)
    case = CaseRecord(case_id="case_quality", title="quality")
    service = InputService()

    updated = service.add_inputs(
        case,
        [
            InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(white)),
            InputCreateRequest(channel=InputChannel.FLUORESCENCE, path=str(fluorescence)),
        ],
    )

    assert any(flag.code == "mismatched" for flag in updated.quality_flags)
    assert any(flag.code in {"weak_signal", "underexposed"} for flag in updated.quality_flags)


def test_camera_input_is_registered_without_file_validation() -> None:
    case = CaseRecord(case_id="case_camera", title="camera")

    updated = InputService().add_inputs(
        case,
        [InputCreateRequest(channel=InputChannel.VIDEO, path="camera://browser/default")],
    )

    assert updated.inputs[0].channel == InputChannel.VIDEO
    assert updated.inputs[0].path == "camera://browser/default"
    assert updated.inputs[0].metadata["input_type"] == "browser_camera"
    assert updated.inputs[0].quality_flags == []
    assert updated.quality_flags == []


def test_replacing_an_official_input_channel_keeps_only_the_latest_asset(tmp_path: Path) -> None:
    first_white = tmp_path / "first_white.jpg"
    replacement_white = tmp_path / "replacement_white.jpg"
    Image.fromarray(np.full((20, 20, 3), 80, dtype=np.uint8)).save(first_white)
    Image.fromarray(np.full((20, 20, 3), 160, dtype=np.uint8)).save(replacement_white)
    case = CaseRecord(case_id="case_replacement", title="replacement")
    service = InputService()

    initial = service.add_inputs(
        case,
        [InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(first_white))],
    )
    replaced = service.add_inputs(
        initial,
        [InputCreateRequest(channel=InputChannel.WHITE_LIGHT, path=str(replacement_white))],
    )

    assert len(replaced.inputs) == 1
    assert replaced.inputs[0].channel == InputChannel.WHITE_LIGHT
    assert replaced.inputs[0].path == str(replacement_white)
