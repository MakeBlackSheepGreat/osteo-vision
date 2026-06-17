# V1 Demonstrable Prototype Closure Plan

Generated on: 2026-06-15

## 1. Goal

This stage moves the project from research organization into a demonstrable prototype: white-light image plus ICG fluorescence image in, pseudo-color fusion, heatmap, normalized fluorescence, ROI intensity statistics, and case report out.

The V1 demo does not require GPU, trained weights, or changes to the public task/model adapter contracts.

## 2. Fixed Capabilities

- Add a "White-light + ICG fluorescence" dual-channel entry point to the demo.
- Keep the parameters fixed as alpha, threshold, and colormap.
- Keep the outputs fixed as overlay, heatmap, normalized fluorescence, and JSON report.
- Generate a Markdown report as well for presentation and physician review.
- Preserve the existing single-file model inference entry point for classification, segmentation, detection, quantification, and multitask fixture workflows.

## 3. Artifact Governance

Long-term archive:

- `research/reports/planning/`: stage plans and goals.
- `research/reports/preprocessing/`: preprocessing reports.
- `research/reports/modeling/`: model selection, training, and evaluation reports.
- Necessary preview assets: a small number of images used by reports.

Local temporary artifacts:

- `.pytest_tmp/`
- `.pytest_cache/`
- `artifacts/reports/`
- `artifacts/visual_evidence/`
- nnU-Net validation `.npz`
- nnU-Net intermediate preprocessing, validation, and probability-map files

Temporary artifacts may be used for local inspection but should not be treated as long-term evidence or committed to Git.

## 4. D024 Role

D024 remains a V2 technical baseline for validating CBCT jaw-structure segmentation, training, evaluation, and reporting. D024 does not contain jaw osteomyelitis, necrotic bone, or intraoperative ICG labels, so it is not part of the V1 fluorescence demo path.

## 5. Acceptance

- `python check_env.py` passes.
- `python -m pytest tests/unit tests/smoke` passes.
- The demo launches and shows the dual-channel fluorescence fusion entry point.
- The dual-channel handler directly returns Markdown, three image paths, and a JSON report path.

