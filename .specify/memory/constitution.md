<!--
Sync Impact Report
Version change: unratified template -> 1.0.0
Modified principles:
- Placeholder principle 1 -> I. Platform Scope
- Placeholder principle 2 -> II. Medical Safety and Physician Review
- Placeholder principle 3 -> III. Configurable Interfaces and Replaceable Models
- Placeholder principle 4 -> IV. Data Governance and Provenance
- Placeholder principle 5 -> V. Evidence-Driven Delivery
Added sections:
- Fixed Technical Boundaries
- Development Workflow and Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ updated .specify/templates/plan-template.md
- ✅ updated .specify/templates/spec-template.md
- ✅ updated .specify/templates/tasks-template.md
- ✅ checked .specify/templates/commands/ (directory not present)
- ✅ checked AGENTS.md, README.md, docs/quickstart.md, docs/architecture.md
Follow-up TODOs:
- None
-->

# Osteo Vision Constitution

## Core Principles

### I. Platform Scope
The project MUST remain a software platform for jaw osteomyelitis intraoperative
fluorescence interpretation. Features MUST serve at least one of the three
post-acquisition layers: fluorescence analysis, AI + physician review, or result
export. Device drivers, hospital HIS/EMR/PACS integration, full patient
administration, and clinical diagnosis workflows are out of scope unless a
separate plan justifies them as future extensions.

Rationale: The platform focuses on a complete software workflow around
white-light/ICG dual-channel observation while keeping device and hospital
integrations behind explicit extension boundaries.

### II. Medical Safety and Physician Review
All outputs MUST be framed as research and engineering validation evidence produced by the platform. ICG
MUST be described as a perfusion, vascular permeability, and tissue-viability
signal, not as a jaw osteomyelitis-specific probe. The system MUST preserve
physician review states for AI candidates and MUST NOT present automatic
diagnosis, automatic resection boundaries, or clinical performance claims
without real intraoperative white-light/ICG data and physician labels.

Rationale: The medical value of this project depends on conservative claims,
clear review boundaries, and traceable evidence rather than unsupported
diagnostic certainty.

### III. Configurable Interfaces and Replaceable Models
Shared behavior MUST enter through stable contracts: task YAML, inference YAML,
model adapters, pipelines, manifests, and report writers. Disease-specific logic
MUST be localized in `configs/tasks/osteo_vision.yml`,
`configs/inference/osteo_vision.yml`, dedicated adapters, or dedicated
pipelines. Model families, datasets, thresholds, and ensemble strategies MUST
remain replaceable and MUST NOT be hard-coded into shared infrastructure.

Rationale: The model and dataset strategy is intentionally unsettled. The code
must let nnU-Net, MedNeXt, U-Mamba, MedSAM-like models, threshold baselines, and
future clinical models be swapped without breaking the platform.

### IV. Data Governance and Provenance
Text files MUST be read and written as UTF-8. Real patient data, hospital data,
enterprise samples, and other sensitive medical assets MUST follow
de-identification and minimum-retention rules. Large raw data, DICOM/NIfTI
volumes, PDFs, checkpoints, nnU-Net probability arrays, and transient experiment
outputs MUST stay out of Git. Dataset and experiment work MUST preserve source,
license, manifest, preprocessing, and run evidence in the approved project
locations.

Rationale: Reproducibility and privacy are both central to a medical imaging
project. Missing provenance makes results hard to defend; careless
retention creates avoidable risk.

### V. Evidence-Driven Delivery
Every feature MUST define independently testable user value and SHOULD include
unit, smoke, contract, or integration tests proportional to its risk. The
minimum regression gate for core changes is `python tools/check_project_readiness.py`
and `python -m pytest tests/unit tests/smoke` unless the plan records a justified
exception. Reports, metrics, screenshots, JSON outputs, and failure cases MUST
be saved in the appropriate `research/reports/` or `artifacts/` location.

Rationale: The project must be demonstrable, reproducible, and adjustable under
normal development and release pressure. Evidence is the bridge between platform behavior and
credible presentation.

## Fixed Technical Boundaries

- Frontend target: TypeScript + Vue 3 + Vite.
- Backend/API target: Python 3.11, with FastAPI as the intended service layer.
- Core ML backend: PyTorch.
- Medical imaging I/O: SimpleITK, nibabel, and pydicom.
- 2D image and visualization stack: OpenCV, Pillow, matplotlib, NumPy, pandas,
  and scikit-learn.
- Configuration format: YAML.
- Temporary demo layer: Gradio is allowed for rapid platform demos and
  smoke-testable platform workflows, but it is not the long-term frontend architecture.
- Core entry boundaries: `configs/tasks/osteo_vision.yml`,
  `configs/inference/osteo_vision.yml`, `osteo_vision_core/models/adapters.py`,
  `osteo_vision_core/pipelines/`, `osteo_vision_core/preprocess/`, and `osteo_vision_core/reports/`.
- Report archive: long-lived planning, preprocessing, modeling, and experiment
  reports belong under `research/reports/`.

## Development Workflow and Quality Gates

1. A feature specification MUST identify the user workflow, medical safety
   boundary, input/output contract, evidence artifacts, and out-of-scope items.
2. A feature plan MUST pass the Constitution Check before implementation begins
   and again after design work changes the scope or architecture.
3. New preprocessing, model integration, pipeline, metric, configuration, or
   platform work MUST read and follow the matching `.agents/rules/skill-*.md` file.
4. New shared interfaces MUST include tests or a written exception in the plan.
5. Reports generated for formal research or engineering evidence SHOULD be
   bilingual Markdown files using `_zh.md` and `_en.md` suffixes when practical.
6. Any clinical or performance claim MUST be tied to a dataset, manifest,
   evaluation protocol, and saved report.

## Governance
This constitution supersedes local habits and informal project decisions when
they conflict. `AGENTS.md`, `.agents/rules/`, feature specs, implementation plans, and
reports MUST align with this document.

Amendments require a documented change to `.specify/memory/constitution.md`, a
version bump, and a Sync Impact Report at the top of the file. Dependent
templates in `.specify/templates/` and runtime guidance files such as
`AGENTS.md`, `README.md`, and `docs/` MUST be checked during each amendment.

Versioning follows semantic rules:

- MAJOR: incompatible removal or redefinition of principles.
- MINOR: new principle, new mandatory governance section, or material expansion
  of required practice.
- PATCH: wording fixes, clarifications, or non-semantic refinements.

Every implementation plan and review MUST verify compliance with the current
version. Violations are allowed only when explicitly recorded in the plan with a
simpler alternative considered and a migration path back to compliance.

**Version**: 1.0.0 | **Ratified**: 2026-06-15 | **Last Amended**: 2026-06-15
