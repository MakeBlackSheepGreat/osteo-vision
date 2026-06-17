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
