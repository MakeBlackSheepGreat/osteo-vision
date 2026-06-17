# Quickstart: Osteo Vision Software Platform Target

## Purpose

Validate the target platform workflow from environment readiness to case export.

## Prerequisites

- Conda environment created from the repository environment file
- Development dependencies installed
- At least one representative dual-channel sample or fixture case

## Validation Steps

1. Check the local environment.

```powershell
python check_env.py
```

2. Run the baseline regression checks.

```powershell
python -m pytest tests/unit tests/smoke
```

3. Start the V1 backend.

```powershell
python -m backend.src.main
```

Default backend health check: `http://127.0.0.1:8001/health`

4. Start the V1 frontend in a second terminal.

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

6. Verify the project-level readiness checks.

```powershell
python tools/check_project_readiness.py
```

## Expected Outcomes

- The case workflow is understandable as a software platform rather than a
  single-model demo.
- Low-confidence cases remain clearly labeled.
- Exported results include images, structured data, and review state.
- No output reads as an automatic diagnosis.

## Target Architecture Notes

- Gradio remains a temporary legacy bridge.
- The target implementation is a Vue frontend plus Python/FastAPI backend.
- Default local ports are frontend `5174` and backend `8001`.
- Analysis and report generation should remain reproducible from local files and
  saved artifacts.

## Reference Materials

- `spec.md`
- `research.md`
- `data-model.md`
- `contracts/api.md`
