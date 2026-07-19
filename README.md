# osteo-vision

Research-validation platform for fluorescence-assisted intraoperative decision support in jaw osteomyelitis. Current engineering version: `0.3.0-rc.2`.

The platform accepts microscope-exported JPEG images, MP4 videos, and optional standardized metadata. It provides fluorescence processing, AI candidate regions, physician review, 3D reference workflows, and traceable evidence exports. Device drivers, private SDKs, and acquisition integration remain with the device provider.

Every output requires physician review. Outputs do not establish a diagnosis, a resection boundary, or validated intraoperative navigation. ICG primarily reflects perfusion, vascular permeability, and tissue activity; it has no demonstrated specificity for jaw osteomyelitis in this project.

Chinese documentation: [README_CN.md](README_CN.md)

## Competition Scope

The repository is organized around the three official solution areas:

1. A novel fluorescent-agent design and validation plan.
2. White-light and fluorescence registration, fusion, enhancement, and quantification.
3. AI-assisted candidate regions, risk, uncertainty, and physician review.

The confirmed software input boundary is `3840x2160`, JPEG, MP4, and USB3.0 file storage. DICOM, remote collaboration, and 3D reference workflows are platform extensions.

## Runnable Workflow

1. Admit de-identified data batches with authorization, checksum, duplicate, and decode checks.
2. Create a case and record constrained clinical context.
3. Upload paired white-light/fluorescence JPEGs, an optional device overlay, or an MP4 video.
4. Run registration, pseudocolor, fusion, quality control, ROI quantification, and keyframe or continuous-frame inference.
5. Review `fluorescence_signal_mask`, `risk_mask`, `uncertain_mask`, candidate regions, overlays, and performance metadata.
6. Save, modify, submit, and independently review pixel annotations.
7. Export JSON, Markdown, CSV, DICOM Secondary Capture, and a ZIP evidence bundle.
8. Import CBCT/STL assets in the separate 3D workspace and run gated L1 static registration or L2 offline pose replay.

## Safety-Gated Priorities

| Capability | Engineering state | Runtime boundary |
|---|---|---|
| Patient-conditioned segmentation | Clinical contracts, persistence, UI, proxy training, and difference evidence exist | The KiTS23 proxy failed the no-harm gate; strict runtime preserves the image-only baseline |
| Bone-activity stratification | Reviewed bone gate, low/transition/high/indeterminate classes, continuous score, and feedback exist | The D074 proxy failed the utility gate; spatial candidates remain disabled |
| 3D registration and offline AR | CBCT/STL, calibration metadata, L1 tasks, L2 replay, and evidence are runnable | Any provenance, coordinate, error, synchronization, or review failure falls back to `L0/unregistered_3d_reference` |

The competition mainline is `keyframe_residual_attention_unet_s20260715_20260715`. It supports 4K tiled inference with a 512-pixel tile and 64-pixel overlap, plus a 960-pixel live-frame profile. Reported proxy metrics are non-target-domain engineering evidence.

The verified local data inventory currently covers 15 manifests, 47 records, 138 files, and about 5.51 GB. It contains zero target-domain and zero training-admitted records. Real paired jaw-osteomyelitis white-light/ICG cases, physician pixel ground truth, full device calibration, and physical phantom accuracy remain external validation needs.

## Repository Layout

```text
backend/           FastAPI API and application services
frontend/          Vue 3 and TypeScript desktop workstation
src/               inference, models, datasets, metrics, and navigation core
configs/           task, development, and competition-strict runtime profiles
scripts/           training, evaluation, experiment, and launch scripts
tools/             admission, verification, performance, and evidence tools
tests/             core unit, smoke, and integration tests
backend/tests/     backend unit, contract, and integration tests
docs/              current engineering documentation
research/          literature, source manifests, modeling evidence, and archives
artifacts/         local generated outputs excluded from Git by default
app/               Gradio compatibility entry point
start_platform.cmd root user launch entry point
```

See [docs/project_structure.md](docs/project_structure.md) for directory ownership and archive rules.

## Start

```powershell
conda env create -f environment.yml
conda activate osteo-vision
npm --prefix frontend install
start_platform.cmd
```

Default endpoints:

- Backend: `http://127.0.0.1:8001`
- Frontend: `http://127.0.0.1:5174/`

See [docs/quickstart.md](docs/quickstart.md) for identity configuration, offline approvals, and manual startup.

## Quality Gates

```powershell
conda run -n osteo-vision python -m ruff check src backend tests scripts tools
conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python -m pytest backend/tests
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
conda run -n osteo-vision python tools/check_runtime_readiness.py --config configs/inference/osteo_vision_competition_strict.yml --require-strict
conda run -n osteo-vision python tools/check_project_readiness.py
conda run -n osteo-vision python tools/audit_active_documentation.py
```

Core hot-path performance and output-integrity benchmark:

```powershell
conda run -n osteo-vision python tools/benchmark_core_hotpaths.py --repeats 3 --output artifacts/performance/core_hotpaths_current.json
```

## Documentation

- [Quick start](docs/quickstart.md)
- [Current project status](docs/project_summary.md)
- [Repository ownership](docs/project_structure.md)
- [Engineering architecture](docs/development_framework.md)
- [Export schema](docs/export_schema_v1.md)
- [Offline promotion approval](docs/promotion_approval_offline.md)
- [Research archive index](research/README.md)
- [Changelog](CHANGELOG.md)
- [Release snapshots](research/reports/release/)
- [Current submission entry](research/reports/submission/)

## Data Governance

- Patient data is de-identified and minimized by default.
- Hospital files require batch admission before case analysis or training review.
- Raw imaging, videos, weights, databases, keys, 3D models, and large derived assets stay outside version control.
- Only independently reviewed annotations from trusted physician identities may be evaluated for high-weight training admission.
- Every public, proxy, and pseudo-labeled source retains provenance, license, checksum, and use boundaries.
