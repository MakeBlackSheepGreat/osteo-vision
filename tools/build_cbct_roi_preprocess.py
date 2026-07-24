from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osteo_vision_core.preprocess.cbct_roi import build_cbct_anatomy_roi


def _parse_ints(value: str | None) -> list[int] | None:
    if value is None or value.strip() == "":
        return None
    return [int(part.strip()) for part in value.replace("x", ",").split(",") if part.strip()]


def _parse_triplet(value: str | None) -> tuple[int, int, int] | None:
    parsed = _parse_ints(value)
    if parsed is None:
        return None
    if len(parsed) != 3:
        raise argparse.ArgumentTypeError(f"Expected three comma-separated values, got: {value}")
    return (parsed[0], parsed[1], parsed[2])


def _margin_arg(value: str) -> int | tuple[int, int, int]:
    parsed = _parse_ints(value)
    if parsed is None:
        return 8
    if len(parsed) == 1:
        return int(parsed[0])
    if len(parsed) == 3:
        return (parsed[0], parsed[1], parsed[2])
    raise argparse.ArgumentTypeError(f"Expected one or three comma-separated margin values, got: {value}")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a traceable CBCT anatomy ROI crop from an NPZ volume.")
    parser.add_argument("--input", required=True, help="Input NPZ with a 3D image and optional label.")
    parser.add_argument("--output-dir", required=True, help="Output directory for ROI NPZ and manifest.")
    parser.add_argument("--case-id", default=None)
    parser.add_argument(
        "--anatomy-mask", default=None, help="Optional .npy/.npz anatomy mask, e.g. DentalSegmentator output."
    )
    parser.add_argument(
        "--foreground-labels", default=None, help="Comma-separated anatomy labels to use as foreground."
    )
    parser.add_argument("--margin", type=_margin_arg, default=8, help="One value or z,y,x margin voxels. Default: 8.")
    parser.add_argument(
        "--fallback-crop-shape", default=None, help="Optional z,y,x center crop shape when no foreground exists."
    )
    parser.add_argument("--source-kind", default="cbct_proxy_npz")
    parser.add_argument("--image-key", default=None)
    parser.add_argument("--label-key", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build_cbct_anatomy_roi(
        args.input,
        args.output_dir,
        case_id=args.case_id,
        anatomy_mask_path=args.anatomy_mask,
        foreground_labels=_parse_ints(args.foreground_labels),
        margin_voxels=args.margin,
        fallback_crop_shape=_parse_triplet(args.fallback_crop_shape),
        source_kind=args.source_kind,
        image_key=args.image_key,
        label_key=args.label_key,
    )
    print(json.dumps({"roi_npz_path": result.roi_npz_path, "manifest_path": result.manifest_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
