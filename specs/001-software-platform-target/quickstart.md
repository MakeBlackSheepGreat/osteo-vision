# Quickstart: Osteo Vision Software Platform Target

## Purpose

Validate the target platform workflow from environment readiness to case export.

## Prerequisites

- Conda environment created from the repository environment file
- Development dependencies installed
- At least one representative de-identified dual-channel sample

## Validation Steps

1. Audit active documentation and runtime readiness.

```powershell
python tools/audit_active_documentation.py
python tools/check_project_readiness.py
```

2. Run the baseline regression checks.

```powershell
python -m pytest tests/unit tests/smoke
```

3. Start the FastAPI backend.

```powershell
python -m backend.osteo_vision_api.main
```

Default backend health check: `http://127.0.0.1:8001/health`

4. Start the Vue frontend in a second terminal.

```powershell
npm --prefix frontend run dev
```

Default frontend URL: `http://127.0.0.1:5174/`

5. Open a representative case and confirm:

- White-light and fluorescence inputs load together
- Fused views appear
- Quality flags are visible when inputs are weak, mismatched, or unusable
- ROI selection changes the quantitative summary
- Review states are preserved
- Export creates a full evidence bundle

6. Record the current core hot-path benchmark.

```powershell
python tools/benchmark_core_hotpaths.py --output artifacts/performance/core_hotpaths_current.json
```

## Expected Outcomes

- The case workflow presents the complete platform workflow and its model evidence.
- Low-confidence cases remain clearly labeled.
- Exported results include images, structured data, and review state.
- No output reads as an automatic diagnosis.

## Target Architecture Notes

- Gradio is retained only as a compatibility check entry.
- The production platform interface uses Vue with a Python/FastAPI backend.
- Default local ports are frontend `5174` and backend `8001`.
- Analysis and report generation should remain reproducible from local files and
  saved artifacts.

## Reference Materials

- `spec.md`
- `research.md`
- `data-model.md`
- `contracts/api.md`
