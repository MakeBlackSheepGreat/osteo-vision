# Final Goal And Fixed Technical Stack For The Jaw Osteomyelitis Project

Generated on: 2026-06-15

## 1. Local Evidence Reviewed

This planning note is based on the following local materials:

- `research/reports/planning/official_competition_problem_alignment_20260704_zh.md`
- `research/reports/archive/early_planning_202606/engineering_preparation.md`
- `research/reports/archive/early_planning_202606/data_acquisition_plan.md`
- `docs/architecture.md`
- `docs/development_framework.md`
- `configs/tasks/osteo_vision.yml`
- `configs/inference/osteo_vision.yml`
- `requirements.txt`
- `environment.yml`

The key conclusion is that this project should deliver an integrated system around the dental observation device's white-light and fluorescence channels: contrast agent, multimodal image fusion, AI-assisted interpretation, and standardized output. ICG should be treated as a perfusion and tissue-viability signal, not as a jaw osteomyelitis-specific tracer.

## 2. Final Project Goal

The final goal is a research and competition validation platform for intraoperative decision support in jaw osteomyelitis.

The system should:

- Display ICG fluorescence information reliably on top of the intraoperative white-light view.
- Provide AI-assisted prompts for suspected necrotic bone, inflammatory regions, suspicious margins, or risk zones.
- Organize preoperative imaging, intraoperative images, AI outputs, and physician review boundaries into reproducible case-level outputs.
- Support an end-to-end competition demo, not only a single model metric.

The system should not:

- Claim that ICG specifically identifies jaw osteomyelitis.
- Present outputs as clinical diagnosis.
- Claim clinical-grade segmentation performance before real intraoperative white-light/ICG samples and physician annotations are available.

## 3. Deliverables By Competition Track

| Track | Fixed deliverable | Success criteria |
|---|---|---|
| Track 1: fluorescence pseudo-color enhancement | White-light/fluorescence registration, pseudo-color overlay, heatmap, intensity curve, image or video export | Demonstrable without trained weights; reproducible inputs and outputs |
| Track 2: AI-assisted diagnosis | Segmentation, detection, classification, or quantification interfaces for ROI, suspicious regions, and boundary risk zones | Model-replaceable, evaluated with metrics, with failure cases recorded |
| Track 3: standardized output and collaboration | Structured case report, DICOM secondary capture or export platform workflow, remote collaboration hooks | Archivable, reviewable, and shareable outputs |

## 4. Fixed Technical Stack

The fixed technical stack is the engineering base that should not be changed casually.

| Layer | Fixed choice | Reason |
|---|---|---|
| Runtime | Python 3.11 + conda + pip | Already used locally and compatible with the medical imaging ecosystem |
| Deep learning | PyTorch | Common backend for nnU-Net, MONAI, and most medical imaging models |
| Medical imaging I/O | SimpleITK, nibabel, pydicom | Covers DICOM, NIfTI, and common medical volume workflows |
| Image processing | OpenCV, Pillow, matplotlib | Covers registration, pseudo-color rendering, visualization, and report figures |
| Data analysis | numpy, pandas, scikit-learn | Needed for manifests, metrics, statistics, and classical baselines |
| Configuration | YAML | Current task and runtime configs already use YAML |
| Demo/UI | Gradio | Practical for local demos and competition presentations |
| Quality gates | pytest, mypy, ruff, black, isort | Keeps the codebase testable and maintainable |
| Orchestration | pyproject.toml, Makefile, scripts/, tests/, artifacts/ | Matches the current repository layout |

## 5. Variable Components

The following items should remain variable:

- Specific segmentation models, such as nnU-Net, ResEnc, MedNeXt, U-Mamba, MedSAM-like models, or future custom models.
- Specific classification or detection models, depending on sample availability, label granularity, and task definition.
- Specific dataset combinations, including public datasets, enterprise samples, hospital samples, and simulated fluorescence data.
- Training strategies, including supervised learning, semi-supervised learning, pretraining, promptable segmentation, and ensembles.
- Metric weighting, including Dice, IoU, HD95, NSD, clDice, sensitivity, specificity, and physician agreement.

These variable components must enter the project through configuration files, model adapters, manifests, and experiment reports rather than being scattered across shared framework code.

## 6. Architecture Principles

1. `configs/tasks/osteo_vision.yml` defines the task contract.
2. `configs/inference/osteo_vision.yml` defines runtime models, inputs, and reports.
3. `src/engine/inference.py` remains the unified inference entry point.
4. Models enter through adapters in `src/models/adapters.py`.
5. Segmentation, classification, detection, quantification, and multitask workflows are organized through `src/pipelines/`.
6. Formal run outputs go to `artifacts/runs/<run_id>/`.
7. Research reports go to `research/reports/<topic>/`.

## 7. Data Strategy

No public dataset currently covers the complete task of intraoperative ICG fluorescence for jaw osteomyelitis. The data strategy should therefore have three layers:

1. Public datasets for anatomical understanding, oral/jaw ROI extraction, lesion candidates, and fluorescence enhancement pretraining or demonstration.
2. A small number of real intraoperative white-light/ICG samples to show workflow compatibility.
3. Physician annotations to define necrotic bone, lesion boundaries, preservation zones, or risk zones, which are required before Track 2 can be treated as a core strength.

The minimum real-sample target remains 10-30 de-identified cases. Without real samples, Track 2 should be framed as an auxiliary demo and integration capability; the main strength should be the complete system and explainable workflow.

## 8. Milestones

### V1: Demonstrable System Skeleton

- Gradio accepts white-light/fluorescence images or video frames.
- The system outputs registration overlays, pseudo-color heatmaps, ROI statistics, and reports.
- The full flow runs without real trained weights.

### V2: Public-Data AI Baseline

- At least one public dataset has preprocessing, manifest generation, training or inference, evaluation, and reporting.
- The model is connected through an adapter.
- Results include metrics, failure cases, and visualizations.

### V3: Real-Sample Workflow

- De-identified intraoperative white-light/ICG samples are connected.
- Physician annotation or review is available.
- Case-level evidence is ready for a competition presentation.

### V4: Competition Package

- Technical report.
- Platform software.
- Demo video or case package.
- Model, data, and evaluation reports.
- Safety statement, license notes, and physician review boundary.

## 9. Current Recommendation

The near-term priority should be to stabilize the engineering delivery chain: white-light/fluorescence fusion, reporting, demo, manifests, benchmarking, and model adapters. Models and datasets should continue as experiments. This keeps the project robust even if real samples, annotation formats, or model choices change later.
