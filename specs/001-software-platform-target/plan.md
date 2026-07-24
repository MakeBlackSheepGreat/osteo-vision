# Implementation Plan: Osteo Vision Software Platform Target

**Branch**: `[001-software-platform-target]` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-software-platform-target/spec.md`

**Note**: This plan is aligned with the project constitution and the target
current platform target in `research/reports/planning/osteo_vision_platform_target_zh.md`.

## Summary

Build a pure software, browser-based workbench for jaw osteomyelitis fluorescence
cases. The target shape is a Vue frontend for case review and evidence display,
a Python/FastAPI backend for case orchestration and exports, and a PyTorch-based
analysis layer for fluorescence fusion, quality flags, ROI quantification, and
review-state tracking. The 2026-07-17 expansion adds patient-conditioned evidence,
bone-activity spectrum review, and magnification-aware L0/L1/L2 3D registration
validation. Gradio remains a temporary bridge only.

## Technical Context

**Language/Version**: TypeScript for the frontend; Python 3.11 for the backend
and analysis layer; YAML for runtime configuration

**Primary Dependencies**: Vue 3, Vite, Pinia, Vue Router, Element Plus or Naive UI,
FastAPI, PyTorch, OpenCV, SimpleITK, nibabel, pydicom, Pillow, matplotlib,
NumPy, pandas, scikit-learn

**Storage**: Local filesystem for uploaded inputs, derived visuals, reports, and
evidence bundles; SQLite for case/workflow metadata; report archives in
`research/reports/`; transient runs in `artifacts/`

**Testing**: pytest for backend and analysis, frontend component tests with
Vitest or equivalent, and end-to-end smoke checks for the case workflow

**Target Platform**: Browser-based workstation software for Windows and Linux
desktops, with local deployment as the default operating mode

**Project Type**: Web application with a split frontend/backend architecture and
a shared medical-imaging analysis core

**Performance Goals**: A single representative case should load, review, and
export within the versioned acceptance limits; short sequences should remain
interactive during ROI selection and review; safety-gate decisions should be
available in the same API response that exposes the associated evidence

**Constraints**: Enterprise device SDKs, drivers, and hardware acquisition remain
outside this software repository; HIS/PACS/EMR integration is an extension boundary;
automatic diagnosis claims are prohibited; physician review is required; official
JPEG/MP4 files, browser video streams, and offline dual-channel inputs must be
supported; the workstation path must remain usable without a GPU

**Scale/Scope**: Single-user or small-team case review workflow, one case at a
time for live demo, with batch export and later multi-case expansion kept open

**Osteo Vision Layer**: cross_cutting

**Medical Safety Boundary**: The platform remains a research and competition
platform, treats ICG as a perfusion/viability signal, preserves physician
review states, and avoids unsupported clinical certainty language

**Priority Capability Order**: common safety gates and regression baseline;
versioned contracts and acceptance protocols; API/persistence/UI/report closure;
public and proxy data admission; L1 static phantom registration; L2 offline
dynamic validation; target-domain collection; patient-conditioned and
bone-activity model training last

**Input/Output Contract**: White-light and fluorescence images, synchronized
frames, or short video clips in; fused overlays, heatmaps, ROI summaries,
quality flags, structured JSON, CSV quantification, Markdown/PDF reports, and
case evidence bundles out

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Competition scope**: The feature stays inside the three post-acquisition
  layers: fluorescence analysis, AI + physician review, and result export.
- **Medical safety**: All outputs remain research/competition evidence; review
  states and disclaimers are preserved; no automatic diagnosis or resection
  guidance is claimed.
- **Configurable architecture**: Case behavior enters through configs,
  manifests, adapters, pipelines, and report writers rather than hard-coded
  model or dataset assumptions.
- **Data governance**: Sensitive medical data, raw imaging, checkpoints, and
  transient artifacts are kept out of Git and stored with provenance.
- **Evidence and tests**: The plan includes smoke checks, unit/integration
  coverage, reproducible artifacts, and export verification.

## Project Structure

### Documentation (this feature)

```text
specs/001-software-platform-target/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
frontend/
├── osteo_vision_core/
│   ├── components/
│   ├── pages/
│   ├── stores/
│   ├── services/
│   ├── composables/
│   └── assets/
└── tests/

backend/
├── osteo_vision_core/
│   ├── api/
│   ├── core/
│   ├── domains/
│   ├── services/
│   ├── pipelines/
│   ├── preprocess/
│   ├── reports/
│   └── models/
└── tests/

osteo_vision_core/
├── core/
├── datasets/
├── engine/
├── models/
├── pipelines/
├── preprocess/
├── reports/
└── utils/

tests/
├── contract/
├── integration/
└── unit/
```

**Structure Decision**: Keep the existing shared analysis/framework core in
`osteo_vision_core/`, add a Vue-based `frontend/` for case review and a Python `backend/`
service layer for orchestration and export, and keep the feature documents under
`specs/001-software-platform-target/`.

## Complexity Tracking

No constitution violations require justification for this feature. The selected
architecture stays within the current scope and technical boundaries.
