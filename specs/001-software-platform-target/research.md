# Research: Osteo Vision Software Platform Target

## Decision 1: Platform Shape

**Decision**: Build a browser-based workbench with a split frontend/backend
architecture rather than a single monolithic demo.

**Rationale**: The project target needs a realistic software surface for case
review, physician interaction, and evidence export while still staying small
enough to deliver as a pure software platform.

**Alternatives considered**:

- Gradio-only demo. Faster to validate, but too narrow for the target workflow.
- Electron desktop shell. Feels product-like, but adds packaging complexity.
- PySide6/Qt. Strong for local tools, but less aligned with the chosen web stack.

## Decision 2: Frontend Stack

**Decision**: Use TypeScript + Vue 3 + Vite, with Pinia, Vue Router, and a UI
library such as Element Plus or Naive UI.

**Rationale**: This stack supports image-heavy review screens, layered overlays,
curve panels, and stateful case workspaces while staying consistent with the
project’s fixed technical stack.

**Alternatives considered**:

- React. Viable, but not the chosen long-term stack for this repo.
- Streamlit. Useful for quick demos, but less suitable for the target workbench.

## Decision 3: Backend and Analysis Stack

**Decision**: Use Python 3.11 with FastAPI for service boundaries and PyTorch,
OpenCV, SimpleITK, nibabel, pydicom, Pillow, matplotlib, NumPy, pandas, and
scikit-learn for analysis, fusion, and report generation.

**Rationale**: This aligns with the medical-imaging ecosystem already used in
the repository and supports both classical image processing and model-based
analysis.

**Alternatives considered**:

- Node-based analysis backend. Poor fit for medical-imaging libraries.
- Pure frontend processing. Too limited for analysis-heavy workloads.

## Decision 4: Storage and Artifact Strategy

**Decision**: Store case metadata in SQLite, keep uploads and derived outputs on
the local filesystem, and preserve long-lived reports in `research/reports/`
with transient runs in `artifacts/`.

**Rationale**: The competition target values reproducibility, low operational
overhead, and local inspectability more than distributed infrastructure.

**Alternatives considered**:

- PostgreSQL first. Better for multi-user scale, but unnecessary at this stage.
- Object storage first. Good for deployment, but too heavy for the current demo
  workflow.

## Decision 5: Workflow Architecture

**Decision**: Model the platform as a five-layer flow:
presentation, API/orchestration, analysis, storage, and asynchronous task
execution.

**Rationale**: This preserves a clear boundary between UI, review logic, fusion
analysis, and export packaging, and it leaves room for future device or hospital
integration without changing the case-level workflow.

**Alternatives considered**:

- Single-process monolith. Simpler initially, but harder to separate the review
  UI from the analysis core later.
- Direct model invocation from the UI. Too brittle for export and review-state
  tracking.

## Decision 6: Temporary Demo Path

**Decision**: Keep Gradio as a temporary bridge only.

**Rationale**: It is useful for smoke-testable platform workflows and competition demos, but
the target architecture should be a Vue frontend plus Python backend.

**Alternatives considered**:

- Make Gradio the permanent UI. Too limiting for the intended platform shape.
