from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.components.status_panels import result_markdown, warning_markdown
from src.core.config import load_yaml
from src.core.paths import artifact_dirs
from src.engine.inference import MedicalImagingInferenceService
from src.preprocess.fluorescence import fuse_white_light_fluorescence

DEFAULT_CONFIG = "configs/inference/osteo_vision.yml"


def _file_path(file_obj: Any) -> str | None:
    if file_obj is None:
        return None
    if isinstance(file_obj, (str, Path)):
        return str(file_obj)
    return str(getattr(file_obj, "name", "") or "")


def analyze_upload(file_obj: Any, task_type: str, config_path: str = DEFAULT_CONFIG):
    path = _file_path(file_obj)
    if not path:
        return "No file selected.", "No warnings.", None
    service = MedicalImagingInferenceService.from_config(config_path)
    result = service.diagnose(path, task_type=task_type).to_dict()
    return result_markdown(result), warning_markdown(result), result.get("report_path")


def analyze_fluorescence_pair(
    white_light_file: Any,
    fluorescence_file: Any,
    alpha: float = 0.45,
    threshold: float = 0.6,
    colormap: str = "green",
    config_path: str = DEFAULT_CONFIG,
):
    white_path = _file_path(white_light_file)
    fluorescence_path = _file_path(fluorescence_file)
    if not white_path or not fluorescence_path:
        return "Select both white-light and fluorescence images.", "No warnings.", None, None, None, None

    artifacts = artifact_dirs(load_yaml(config_path))
    output_dir = artifacts["visual"] / "fluorescence_demo"
    report = fuse_white_light_fluorescence(
        white_path,
        fluorescence_path,
        output_dir,
        case_id=Path(white_path).stem,
        alpha=alpha,
        threshold=threshold,
        colormap=colormap,
    )
    outputs = report.get("outputs", {})
    return (
        fluorescence_result_markdown(report),
        fluorescence_warning_markdown(report),
        outputs.get("overlay_path"),
        outputs.get("heatmap_path"),
        outputs.get("normalized_fluorescence_path"),
        outputs.get("report_path"),
    )


def fluorescence_result_markdown(report: dict[str, Any] | None) -> str:
    if not report:
        return "No fluorescence result yet."
    quantification = report.get("quantification", {})
    fusion = report.get("fusion", {})
    return (
        f"Status: `completed`\n\n"
        f"Case: `{report.get('case_id')}`\n\n"
        f"Fusion: `{fusion.get('method')}` / `{fusion.get('colormap')}`\n\n"
        f"Threshold: `{quantification.get('threshold')}`\n\n"
        f"Mean intensity: `{quantification.get('mean_intensity')}`\n\n"
        f"Max intensity: `{quantification.get('max_intensity')}`\n\n"
        f"P95 intensity: `{quantification.get('p95_intensity')}`\n\n"
        f"Positive area: `{quantification.get('positive_area_px')}` px "
        f"(`{quantification.get('positive_area_fraction')}`)"
    )


def fluorescence_warning_markdown(report: dict[str, Any] | None) -> str:
    if not report:
        return "No warnings."
    warnings: list[dict[str, Any]] = []
    fusion = report.get("fusion", {})
    if fusion.get("fluorescence_resized_to_white_light"):
        warnings.append(
            {
                "code": "resize_only_initial_demo",
                "message": "Fluorescence image was resized to match the white-light image before V2 fusion.",
            }
        )
    warnings.append(
        {
                "code": "platform_safety_boundary",
            "message": "This fluorescence fusion output is not a clinical diagnosis and requires physician review.",
        }
    )
    return warning_markdown({"warnings": warnings})


def build_demo_app(config_path: str = DEFAULT_CONFIG):
    try:
        import gradio as gr
    except Exception:
        return {"gradio_available": False, "config_path": config_path}

    with gr.Blocks(title="osteo-vision") as demo:
        gr.Markdown("# osteo-vision")
        gr.Markdown("Platform software for research and competition validation. Outputs are not clinical diagnosis.")
        with gr.Tabs():
            with gr.Tab("White-light + ICG fluorescence"):
                with gr.Row():
                    with gr.Column():
                        white_light = gr.File(label="White-light image")
                        fluorescence = gr.File(label="ICG fluorescence image")
                        alpha = gr.Slider(0.0, 1.0, value=0.45, step=0.05, label="Overlay alpha")
                        threshold = gr.Slider(0.0, 1.0, value=0.6, step=0.05, label="ROI threshold")
                        colormap = gr.Radio(["green", "amber", "magenta"], value="green", label="Pseudo-color")
                        run_fusion = gr.Button("Fuse fluorescence")
                    with gr.Column():
                        fusion_result = gr.Markdown("No fluorescence result yet.")
                        fusion_warnings = gr.Markdown("No warnings.")
                        overlay = gr.Image(label="Overlay")
                        heatmap = gr.Image(label="Heatmap")
                        normalized = gr.Image(label="Normalized fluorescence")
                        fusion_report = gr.File(label="JSON report")
                run_fusion.click(
                    lambda white, fluor, a, t, cmap: analyze_fluorescence_pair(
                        white,
                        fluor,
                        a,
                        t,
                        cmap,
                        config_path,
                    ),
                    [white_light, fluorescence, alpha, threshold, colormap],
                    [fusion_result, fusion_warnings, overlay, heatmap, normalized, fusion_report],
                )
            with gr.Tab("Single-file model inference"):
                with gr.Row():
                    with gr.Column():
                        file_input = gr.File(label="Input image / ROI / DICOM / NIfTI")
                        task = gr.Dropdown(
                            choices=["classification", "segmentation", "detection", "quantification", "multitask"],
                            value="classification",
                            label="Task",
                        )
                        run = gr.Button("Analyze")
                    with gr.Column():
                        result = gr.Markdown("No result yet.")
                        warnings = gr.Markdown("No warnings.")
                        report = gr.File(label="Report")
                run.click(
                    lambda file_obj, task_type: analyze_upload(file_obj, task_type, config_path),
                    [file_input, task],
                    [result, warnings, report],
                )
    return demo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    app = build_demo_app(args.config)
    if isinstance(app, dict):
        print("Gradio is not installed; demo app cannot launch.")
        return 1
    app.launch(server_name=args.host, server_port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
