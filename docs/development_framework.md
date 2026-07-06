# osteo-vision Development Framework

This directory is the formal development project for intelligent fluorescence diagnosis and treatment of jaw osteomyelitis. It is based on a reusable medical-imaging competition framework and provides classification, segmentation, detection, quantification, explainability, reports, Demo, and Benchmark workflows.

This repository is platform software for research and competition validation. Outputs are not clinical diagnosis and must not replace physician review.

## What Is Included

- Config-driven runtime with `configs/inference/osteo_vision.yml` as the shared osteo-vision Demo and Benchmark authority.
- TaskPackage contracts under `configs/tasks/` for fast competition scaffolding.
- `MedicalImagingInferenceService` as the single inference entrypoint.
- ModelSpec and adapter contracts for fixture, timm, MONAI Bundle, nnU-Net v2, MedSAM-like, VISTA3D-like, and VLM encoder model families.
- V3 experiment contracts for fixture training loops, evaluation, threshold selection, model cards, checkpoint manifests, and promotion drafts.
- Fixture pipelines for classification, segmentation, detection, quantification, and multitask demos.
- Input recognition for 2D images, NPZ ROI packages, DICOM series, and NIfTI volumes.
- Single-case reports, Benchmark reports, metrics, warnings, and release asset templates.
- Vue 3 + TypeScript frontend, FastAPI backend, legacy Gradio Demo skeleton, and CLI scripts.
- Unit, smoke, and integration tests.

## Architecture Overview

The framework follows a layered architecture with clear separation of concerns:

### Core Layer (`src/core/`)
- **Configuration**: Config loading, validation, and management
- **Registry**: Component registration and discovery
- **Contracts**: Core interfaces and protocols
- **Schemas**: Data model definitions
- **Warnings**: Warning and error management

### Datasets Layer (`src/datasets/`)
- **Manifests**: Dataset manifest reading and validation
- **Splits**: Data splitting strategies
- **Leakage**: Data leakage detection

### Engine Layer (`src/engine/`)
- **Inference**: Single-case inference service
- **Experiment**: Experiment execution and management
- **Benchmark**: Benchmark evaluation
- **Training**: Model training orchestration

### Models Layer (`src/models/`)
- **Adapters**: Model adapter interface and implementations
- **Registry**: Model registration and discovery
- **Classifier**: Fixture classification models
- **Segmenter**: Fixture segmentation models
- **Detector**: Fixture detection models

### Pipelines Layer (`src/pipelines/`)
- **Base**: Pipeline base class and context
- **Classification**: Classification pipeline
- **Segmentation**: Segmentation pipeline
- **Detection**: Detection pipeline
- **Quantification**: Quantification pipeline
- **Multitask**: Multi-task pipeline

### Preprocess Layer (`src/preprocess/`)
- **Input Validation**: Input type detection and validation
- **Image Quality**: Image quality assessment
- **CT Preprocess**: CT-specific preprocessing
- **Mask Postprocess**: Mask post-processing
- **ROI**: Region of interest processing

### Reports Layer (`src/reports/`)
- **Single Case**: Single-case report generation
- **Benchmark**: Benchmark report generation
- **Writers**: Report writing utilities
- **Validators**: Report validation

### Utils Layer (`src/utils/`)
- **Logging**: Unified logging system
- **Runtime**: Runtime environment and device management

## Quick Commands

V1 split frontend/backend platform:

```powershell
conda activate osteo-vision
python -m backend.src.main
npm --prefix frontend run dev
```

Defaults:

- Backend health check: `http://127.0.0.1:8001/health`
- Frontend: `http://127.0.0.1:5174/`

Regression and research commands:

```powershell
python check_env.py
python -m pytest tests/unit tests/smoke
python scripts/model_inventory.py --config configs/inference/osteo_vision.yml
python scripts/benchmark.py --config configs/inference/osteo_vision.yml --manifest tests/fixtures/benchmark_manifest.csv --output artifacts/runs
python scripts/new_task.py --task-id my_competition --template classification --output-dir configs/tasks
python scripts/new_experiment.py --experiment-id my_competition_fixture --manifest tests/fixtures/benchmark_manifest_v2.csv
python scripts/run_experiment.py --spec artifacts/experiments/my_competition_fixture/experiment.yml
python scripts/promote_model.py --run-dir artifacts/runs/<run_id>
```

Legacy Gradio Demo:

```powershell
python app/main.py --config configs/inference/osteo_vision.yml
```

## Repository Layout

```text
AGENTS.md      Project specification for AI agents
configs/       Runtime and task example configs
  inference/   Inference configurations
  tasks/       Task configurations
src/           Core framework
  core/        Core contracts, config, registry, schemas
  datasets/    Dataset loading, splitting, leakage detection
  engine/      Inference, experiment, benchmark, training
  experiments/ Experiment specs, splits, thresholds, promotion
  explain/     GradCAM, overlay visualization
  io/          DICOM, image, NIfTI I/O
  metrics/     Classification, segmentation, detection metrics
  models/      Model adapters, registry, classifiers, segmenters
  pipelines/   Pipeline implementations
  preprocess/  Input validation, quality assessment, preprocessing
  reports/     Report generation and writing
  utils/       Logging, runtime utilities
app/           Legacy Gradio demo entrypoint
backend/       FastAPI platform backend
frontend/      Vue 3 + TypeScript platform frontend
scripts/       Training, evaluation, benchmark, export templates
tests/         Unit, smoke, and integration tests
  unit/        Unit tests
  integration/ Integration tests
  smoke/       Smoke tests
  fixtures/    Test fixtures
docs/          Architecture, quickstart, task adapter guide
artifacts/     Generated checkpoints, reports, visual evidence, release files
.rules/        Skill rules for AI agents
```

## Skill Rules Library (.rules/)

The framework includes a skill rules library for AI agents. See [.rules/README.md](.rules/README.md) for details.

| Skill File | Description |
|------------|-------------|
| [skill-data-preprocessing.md](.rules/skill-data-preprocessing.md) | Data preprocessing patterns |
| [skill-model-adapter.md](.rules/skill-model-adapter.md) | Model adapter implementation |
| [skill-pipeline-creation.md](.rules/skill-pipeline-creation.md) | Pipeline creation patterns |
| [skill-evaluation-metrics.md](.rules/skill-evaluation-metrics.md) | Evaluation metrics |
| [skill-configuration-management.md](.rules/skill-configuration-management.md) | Configuration management |
| [skill-competition-integration.md](.rules/skill-competition-integration.md) | Competition integration |

## Contracts

The framework defines contracts (interfaces) for all major components:

- **Core Contracts** (`src/core/contracts/`): Config loader, registry, logger, lifecycle
- **Dataset Contracts** (`src/datasets/contracts/`): Dataset loader, split strategy, manifest reader
- **Model Contracts** (`src/models/contracts/`): Model adapter, model registry, checkpoint manager
- **Pipeline Contracts** (`src/pipelines/contracts/`): Pipeline, pipeline registry, pipeline step
- **Preprocess Contracts** (`src/preprocess/contracts/`): Preprocessor, input validator, post-processor
- **Engine Contracts** (`src/engine/contracts/`): Inference service, experiment runner, benchmark evaluator
- **Report Contracts** (`src/reports/contracts/`): Report generator, report writer, report validator

## Type Safety

The framework uses mypy for static type checking. Configuration: `mypy.ini`

```bash
# Run type checking
mypy src/

# Run with strict mode
mypy --strict src/
```

## V2 Model Adapter Boundary

V2 plans for current medical-imaging inference model families such as VISTA3D, MedSAM2, nnU-Net v2, TotalSegmentator-style workflows, MONAI Bundles, BiomedCLIP, Rad-DINO, and MedImageInsight. The repository does not download or bundle real weights. Missing dependencies and weights are reported through adapter status, and fixture fallback remains available for tests and demos.

## V3 Training Loop Contract

V3 adds the competition experiment layer. `ExperimentSpec` records the task package, manifest, model candidate, split strategy, training config, evaluation config, threshold strategy, and promotion gate. `scripts/run_experiment.py` runs a deterministic fixture loop and writes `training_report.json`, `evaluation_report.json`, `oof_predictions.csv`, `model_card.json`, `checkpoint_manifest.json`, and `promotion_record.json` under `artifacts/runs/<run_id>/`.

Promotion is review-first. `scripts/promote_model.py` reads a run directory and writes a runtime promotion draft; it does not modify `configs/inference/osteo_vision.yml`. Patient-level metadata and leakage checks are part of the default gate.

## Reference Projects

The first version is shaped by two existing local projects:

- `D:\Agent`: breast ultrasound CAD, 2D classification, ROI segmentation, Grad-CAM, Gradio Demo.
- `D:\ct-nodule-risk`: CT nodule risk grading, shared inference service, DICOM/ROI governance, Benchmark, warning/report schema.

No data, checkpoints, historical reports, or large artifacts are copied from those projects.
