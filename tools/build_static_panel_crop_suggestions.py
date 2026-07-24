from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from osteo_vision_core.datasets.static_panel_detection import (  # noqa: E402
    DETECTOR_VERSION,
    crop_quality_warnings,
    detect_panel_crop_suggestions,
)

DATASET_QUEUE_PATHS = {
    "d047": Path(
        "research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/derived/figure_review/"
        "pmc_figure_review_queue.json"
    ),
    "d048": Path(
        "research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/derived/figure_review/"
        "pmc_figure_review_queue.json"
    ),
}
OUTPUT_MANIFEST = Path("research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json")

EXPECTED_PANEL_COUNTS = {
    "review_PMC12113262_figure_8": 2,
    "review_PMC7666678_fig_2": 3,
    "review_PMC7666678_fig_3": 5,
    "review_PMC7666678_fig_4": 4,
    "review_PMC7666678_fig_5": 7,
    "review_PMC8132458_figure_1": 2,
    "review_PMC8132458_figure_2": 2,
}

FLUORESCENCE_RANGES = {
    "review_PMC12829038_fig_1": ("D", "G"),
    "review_PMC12829038_fig_3": ("C", "F"),
    "review_PMC12829038_fig_4": ("C", "H"),
    "review_PMC12829038_fig_5": ("C", "G"),
    "review_PMC12829038_fig_6": ("C", "G"),
    "review_PMC12829038_fig_7": ("C", "G"),
    "review_PMC12829038_fig_8": ("C", "G"),
}

CURATED_LAYOUTS: dict[str, list[dict[str, Any]]] = {
    "review_PMC12113262_figure_8": [
        {"bbox": (8, 7, 383, 382), "role": "histopathology"},
        {"bbox": (402, 7, 383, 382), "role": "histopathology"},
    ],
    "review_PMC7666678_fig_2": [
        {"bbox": (0, 437, 649, 435), "role": "paired_white_light", "pair": "PMC7666678_fig2_b_c", "label": "B"},
        {"bbox": (0, 877, 649, 432), "role": "paired_fluorescence", "pair": "PMC7666678_fig2_b_c", "label": "C"},
    ],
    "review_PMC7666678_fig_3": [
        {"bbox": (0, 0, 323, 214), "role": "paired_white_light", "pair": "PMC7666678_fig3_a_b"},
        {"bbox": (326, 0, 323, 214), "role": "paired_fluorescence", "pair": "PMC7666678_fig3_a_b"},
        {"bbox": (0, 217, 323, 432), "role": "histopathology"},
        {"bbox": (326, 217, 323, 214), "role": "histopathology"},
        {"bbox": (326, 434, 323, 215), "role": "histopathology"},
    ],
    "review_PMC7666678_fig_4": [
        {"bbox": (0, 0, 323, 214), "role": "paired_white_light", "pair": "PMC7666678_fig4_a_b"},
        {"bbox": (326, 0, 323, 214), "role": "paired_fluorescence", "pair": "PMC7666678_fig4_a_b"},
        {"bbox": (0, 217, 323, 214), "role": "paired_white_light", "pair": "PMC7666678_fig4_c_d"},
        {"bbox": (326, 217, 323, 214), "role": "paired_fluorescence", "pair": "PMC7666678_fig4_c_d"},
    ],
    "review_PMC7666678_fig_5": [
        {"bbox": (0, 0, 380, 252), "role": "paired_white_light", "pair": "PMC7666678_fig5_a_b"},
        {"bbox": (383, 0, 379, 252), "role": "paired_fluorescence", "pair": "PMC7666678_fig5_a_b"},
        {"bbox": (0, 255, 380, 236), "role": "histopathology"},
        {"bbox": (383, 255, 379, 236), "role": "histopathology"},
        {"bbox": (0, 494, 312, 556), "role": "fluorescence_signal"},
        {"bbox": (315, 494, 447, 277), "role": "fluorescence_signal"},
        {"bbox": (315, 774, 447, 276), "role": "fluorescence_signal"},
    ],
    "review_PMC8132458_figure_1": [
        {
            "bbox": (0, 0, 258, 169),
            "role": "fluorescence_signal",
            "pair": "PMC8132458_fig1_a_b_sequence",
            "alignment": "sequential",
        },
        {
            "bbox": (261, 0, 259, 169),
            "role": "fluorescence_signal",
            "pair": "PMC8132458_fig1_a_b_sequence",
            "alignment": "sequential",
        },
    ],
    "review_PMC8132458_figure_2": [
        {
            "bbox": (0, 0, 335, 450),
            "role": "paired_white_light",
            "pair": "PMC8132458_fig2_a_b",
            "alignment": "approximate_view",
        },
        {
            "bbox": (338, 0, 335, 450),
            "role": "paired_fluorescence",
            "pair": "PMC8132458_fig2_a_b",
            "alignment": "approximate_view",
        },
    ],
}

for _record_id, _boxes in {
    "review_PMC12829038_fig_1": [(803, 0, 386, 386), (1200, 0, 385, 386), (1598, 0, 387, 386), (0, 419, 386, 387)],
    "review_PMC12829038_fig_3": [(803, 0, 386, 386), (1200, 0, 385, 386), (1598, 0, 387, 386), (0, 419, 386, 387)],
    "review_PMC12829038_fig_4": [(800, 0, 389, 386), (1200, 0, 386, 386), (1599, 0, 386, 386), (0, 419, 386, 387)],
    "review_PMC12829038_fig_5": [(800, 0, 389, 386), (1200, 0, 386, 386), (1597, 0, 388, 386), (0, 419, 386, 387)],
    "review_PMC12829038_fig_6": [(800, 0, 389, 386), (1200, 0, 386, 386), (1599, 0, 386, 386), (0, 419, 386, 387)],
    "review_PMC12829038_fig_7": [(799, 0, 389, 386), (1199, 0, 385, 386), (1597, 0, 388, 386), (0, 419, 385, 387)],
    "review_PMC12829038_fig_8": [(795, 0, 387, 384), (1191, 0, 385, 384), (1596, 0, 389, 384), (0, 417, 384, 385)],
}.items():
    CURATED_LAYOUTS[_record_id] = [
        {
            "bbox": bbox,
            "role": "fluorescence_signal",
            "pair": f"{_record_id}_C_D_weak_sequence" if index < 2 else "",
            "alignment": "weak_sequential" if index < 2 else "",
            "label": chr(ord("C") + index),
        }
        for index, bbox in enumerate(_boxes)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review-only panel crop suggestions for D047/D048 figures.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true", help="Append suggestion child records to source review queues.")
    parser.add_argument("--output", type=Path, default=OUTPUT_MANIFEST)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    manifest_records: list[dict[str, Any]] = []
    queue_updates: dict[str, tuple[Path, dict[str, Any]]] = {}
    for dataset_id, relative_queue_path in DATASET_QUEUE_PATHS.items():
        queue_path = (project_root / relative_queue_path).resolve()
        payload = json.loads(queue_path.read_text(encoding="utf-8"))
        source_records = [
            dict(record)
            for record in payload.get("records", [])
            if isinstance(record, dict) and record.get("record_kind") != "crop_suggestion"
        ]
        generated_children: list[dict[str, Any]] = []
        for source_record in source_records:
            if str(source_record.get("cropped_image_path") or "").strip():
                continue
            image_path = _resolved_image_path(source_record, queue_path.parent.parent.parent, project_root)
            with Image.open(image_path) as image:
                suggestions = _suggestions_for_record(source_record, image)
            if len(suggestions) <= 1:
                continue
            parent_record_id = str(source_record["record_id"])
            source_record["record_kind"] = "source_figure"
            source_record["crop_suggestion_generated"] = True
            source_record["crop_suggestion_child_count"] = len(suggestions)
            source_record["crop_suggestion_method"] = DETECTOR_VERSION
            for index, suggestion_payload in enumerate(suggestions):
                panel_label = str(
                    suggestion_payload.pop("panel_label", "")
                    or (chr(ord("A") + index) if index < 26 else str(index + 1))
                )
                role = str(suggestion_payload.pop("panel_role", "") or "unclassified")
                pair_id = str(suggestion_payload.pop("pair_id", "") or "")
                pair_alignment = str(suggestion_payload.pop("pair_alignment", "") or "")
                suggestion_id = _suggestion_id(parent_record_id, suggestion_payload["bbox"])
                child_record_id = f"{parent_record_id}_panel_{panel_label.lower()}_{suggestion_id[-8:]}"
                child = dict(source_record)
                child.update(
                    {
                        "record_id": child_record_id,
                        "source_record_id": f"{source_record.get('source_record_id')}_panel_{panel_label.lower()}",
                        "parent_record_id": parent_record_id,
                        "panel_label": panel_label,
                        "record_kind": "crop_suggestion",
                        "crop_suggestion_generated": True,
                        "crop_suggestion_child_count": 0,
                        "suggestion_id": suggestion_id,
                        "suggested_crop_bbox": suggestion_payload["bbox"],
                        "suggested_panel_role": role,
                        "suggested_pair_id": pair_id,
                        "suggested_pair_alignment": pair_alignment,
                        "suggestion_method": suggestion_payload["method"],
                        "suggestion_score": suggestion_payload["score"],
                        "suggestion_quality_status": suggestion_payload["quality_status"],
                        "suggestion_quality_warnings": suggestion_payload["quality_warnings"],
                        "crop_review_action": "pending",
                        "crop_bbox": None,
                        "cropped_image_path": None,
                        "panel_role": "unclassified",
                        "pair_id": "",
                        "crop_notes": "",
                        "mask_path": None,
                        "mask_source": None,
                        "positive_area_fraction": None,
                        "review_update_path": None,
                        "review_state": "review_required",
                        "training_eligible": False,
                    }
                )
                generated_children.append(child)
                manifest_records.append(
                    {
                        "dataset_id": dataset_id,
                        "record_id": child_record_id,
                        "parent_record_id": parent_record_id,
                        "source_group_id": str(source_record.get("source_group_id") or ""),
                        "source_url": str(source_record.get("source_url") or ""),
                        "source_image_path": str(image_path),
                        "source_checksum": str(source_record.get("source_checksum") or ""),
                        "panel_label": panel_label,
                        "suggestion_id": suggestion_id,
                        "suggested_crop_bbox": suggestion_payload["bbox"],
                        "suggested_panel_role": role,
                        "suggested_pair_id": pair_id,
                        "suggested_pair_alignment": pair_alignment,
                        "suggestion_method": suggestion_payload["method"],
                        "suggestion_score": suggestion_payload["score"],
                        "suggestion_quality_status": suggestion_payload["quality_status"],
                        "suggestion_quality_warnings": suggestion_payload["quality_warnings"],
                        "review_state": "review_required",
                        "training_eligible": False,
                        "medical_boundary": (
                            "Automated panel crops are review-only non-target-domain suggestions. "
                            "They require authorized review before mask creation and cannot support clinical claims."
                        ),
                    }
                )
        payload["records"] = source_records + generated_children
        payload["record_count"] = len(payload["records"])
        payload["training_eligible_count"] = sum(bool(record.get("training_eligible")) for record in payload["records"])
        payload["crop_suggestion_record_count"] = len(generated_children)
        payload["crop_suggestion_method"] = DETECTOR_VERSION
        queue_updates[dataset_id] = (queue_path, payload)

    manifest = {
        "schema_version": "osteo-vision-static-crop-suggestions-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "detector_version": DETECTOR_VERSION,
        "record_count": len(manifest_records),
        "review_required_count": len(manifest_records),
        "training_eligible_count": 0,
        "records": manifest_records,
        "medical_boundary": (
            "All entries are automated non-target-domain crop suggestions. "
            "They remain review_required and training_eligible=false until separate crop and mask review."
        ),
    }
    output_path = (project_root / args.output).resolve()
    if args.apply:
        for _dataset_id, (queue_path, payload) in queue_updates.items():
            _atomic_write_json(queue_path, payload)
        _atomic_write_json(output_path, manifest)
    print(
        json.dumps(
            {
                "applied": args.apply,
                "output": str(output_path),
                **{k: manifest[k] for k in ("record_count", "review_required_count", "training_eligible_count")},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _suggestions_for_record(source_record: dict[str, Any], image: Image.Image) -> list[dict[str, Any]]:
    record_id = str(source_record.get("record_id") or "")
    curated = CURATED_LAYOUTS.get(record_id)
    if curated:
        payloads: list[dict[str, Any]] = []
        for index, entry in enumerate(curated):
            x, y, width, height = entry["bbox"]
            bbox = {"x": x, "y": y, "width": width, "height": height}
            warnings = crop_quality_warnings(image, bbox)
            payloads.append(
                {
                    "bbox": bbox,
                    "score": 0.99 if not warnings else 0.9,
                    "quality_status": "warning" if warnings else "pass",
                    "quality_warnings": warnings,
                    "method": "curated_visual_panel_audit_v1",
                    "panel_label": str(entry.get("label") or chr(ord("A") + index)),
                    "panel_role": str(entry.get("role") or "unclassified"),
                    "pair_id": str(entry.get("pair") or ""),
                    "pair_alignment": str(entry.get("alignment") or ("approximate_view" if entry.get("pair") else "")),
                }
            )
        return payloads
    return [
        suggestion.to_dict()
        for suggestion in detect_panel_crop_suggestions(
            image,
            expected_panel_count=EXPECTED_PANEL_COUNTS.get(record_id),
        )
    ]


def _resolved_image_path(source_record: dict[str, Any], dataset_root: Path, project_root: Path) -> Path:
    raw_value = str(source_record.get("local_path") or "").strip()
    path = Path(raw_value)
    if not path.is_absolute():
        path = dataset_root / path
    path = path.resolve()
    if project_root not in path.parents:
        raise ValueError(f"Source image escapes the project root: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _panel_metadata(parent_record_id: str, panel_label: str) -> tuple[str, str]:
    fluorescence_range = FLUORESCENCE_RANGES.get(parent_record_id)
    if fluorescence_range and fluorescence_range[0] <= panel_label <= fluorescence_range[1]:
        return "fluorescence_signal", ""
    if parent_record_id == "review_PMC12113262_figure_8":
        return "histopathology", ""
    explicit = {
        ("review_PMC8132458_figure_1", "A"): ("paired_white_light", "PMC8132458_case1"),
        ("review_PMC8132458_figure_1", "B"): ("paired_fluorescence", "PMC8132458_case1"),
        ("review_PMC8132458_figure_2", "A"): ("paired_white_light", "PMC8132458_case2"),
        ("review_PMC8132458_figure_2", "B"): ("paired_fluorescence", "PMC8132458_case2"),
        ("review_PMC7666678_fig_2", "B"): ("paired_white_light", "PMC7666678_fig2_bc"),
        ("review_PMC7666678_fig_2", "C"): ("paired_fluorescence", "PMC7666678_fig2_bc"),
        ("review_PMC7666678_fig_3", "A"): ("paired_white_light", "PMC7666678_fig3_ab"),
        ("review_PMC7666678_fig_3", "B"): ("paired_fluorescence", "PMC7666678_fig3_ab"),
        ("review_PMC7666678_fig_3", "C"): ("histopathology", ""),
        ("review_PMC7666678_fig_3", "D"): ("histopathology", ""),
        ("review_PMC7666678_fig_4", "A"): ("paired_white_light", "PMC7666678_fig4_ab"),
        ("review_PMC7666678_fig_4", "B"): ("paired_fluorescence", "PMC7666678_fig4_ab"),
        ("review_PMC7666678_fig_4", "C"): ("paired_white_light", "PMC7666678_fig4_cd"),
        ("review_PMC7666678_fig_4", "D"): ("paired_fluorescence", "PMC7666678_fig4_cd"),
    }
    return explicit.get((parent_record_id, panel_label), ("unclassified", ""))


def _suggestion_id(parent_record_id: str, bbox: dict[str, int]) -> str:
    payload = f"{DETECTOR_VERSION}|{parent_record_id}|{bbox['x']}|{bbox['y']}|{bbox['width']}|{bbox['height']}"
    return f"suggestion_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
