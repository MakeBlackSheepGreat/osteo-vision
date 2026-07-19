# Competition Submission Internal Verification

Date: 2026-07-11

## Environment and Quality Gates

- Conda environment: `osteo-vision`
- Python: 3.11.15
- `check_env.py`: 0 failures, 0 warnings
- Pytest: 304 tests passed across unit, smoke, backend unit, and backend contract suites
- Frontend: 58 tests passed and one skipped; TypeScript and production build passed
- Ruff: passed for `backend src tests scripts tools`
- Mypy: passed for the dataset registry, training admission, review-promotion, and keyframe-training core files
- Black and `git diff --check`: passed
- Project readiness: core files, CSV files, dataset directories, and platform workspace checks passed

The test run retained one Starlette TestClient/httpx compatibility warning and two `torch.jit.interface` deprecation warnings.

## Verified Engineering Paths

- Dynamic quantification uses decoded MP4/JPEG pixels or supplied ROIs and keeps segmentation probability separate.
- A public OFDVDnet real-video run emitted a structured curve with `available=true` and `quality_status=limited` because the selected interval had little dynamic range.
- Dual-channel AI remains skipped under `runtime_allowed=false`; traditional fusion remains available.
- The multi-mask checkpoint runs through explicit candidate selection and keeps `bone_gate_mask` at `review_required`.
- Public-video validation covered long MP4 files, multiple frame rates, an unreadable H.264 failure, a derived 4K JPEG, 45-tile inference, fallback, and a short memory observation.
- The layered registry contains 504 records, passes its quality gate with zero errors, exposes 393 training-admission candidates, and retains zero target-domain records.
- D047 adds ten jaw-fluorescence publication figures. Eight CC BY figures enter a static human-review queue, while two remain reference-only under license or usage rules.
- D048 adds 18 CC BY publication figures, including 15 weak-label review seeds.
- The static D047/D048 review queue contains 61 actionable records. Nine have atomic panel crops, and 14 source figures have produced 52 traceable crop suggestions that remain review-required and training-ineligible.
- Automated candidate masks were generated for all nine cropped records. They remain `review_required`, `training_eligible=false`, and absent from the human-reviewed manifest.
- The hotspot proxy layer now uses 192 grouped keyframes across 48 source-video groups. Boundary-risk, uncertainty, and exposed-bone proxies remain separately registered with zero group leakage.
- Training admission now separates `proxy_pretrain`, `reviewed_finetune`, and `independent_evaluation`; proxy and pending-review labels cannot enter the latter two stages.
- Registered image and label SHA256 values pass the quality gate. The 23 license warnings belong to source records excluded from training.
- A one-batch domain-aware registry training smoke completed and recorded registry and quality-report SHA256 values in the checkpoint sidecar.
- Review promotion now preserves row-level provenance, license, usage policy, source groups, sampling weights, and image/label checksums. Accepted or modified masks must pass existence, readability, size, non-empty, binary, and area checks. Training eligibility is fail-closed.
- A bounded OpenCV live-input layer now supports OpenCV camera indexes, RTSP, HTTP, HTTPS, and local video sources. It records read timeouts, dropped frames, capture timestamps, inference-time frame age, and display eligibility.
- A real local-MP4 capture-to-analysis smoke completed through `realtime_stream_keyframes`, segmentation, uncertainty, manifests, and frame-age gating.
- Unmatched capture frames, conflicting identities, missing explicit display permission, and all-stale runs now fail closed. All-stale runs do not advance the case or publish stale AI artifacts.
- The `/dataset-review` workspace exposes 61 actionable records: 52 atomic panel suggestions and nine cropped records with automated seeds. Generated source-parent records are excluded from the actionable list.
- The 52 suggestions include 19 fluorescence-signal, 13 paired-white-light, 13 paired-fluorescence, and seven histopathology panels across 14 pair IDs. Forty pass the automated crop gate and 12 retain review warnings.
- The crop workspace records exact bounds, panel roles, white-light/fluorescence `pair_id`, notes, and source checksums before mask review.
- Static mask persistence validates PNG format, dimensions, binary values, non-empty area, and area bounds. The unified reviewed manifest is connected to the default layered-registry build path.
- Enterprise 3840x2160 MP4 validation remains pending.

## Documents

- Final Markdown, DOCX, and PDF are stored under `research/reports/submission/`.
- The PDF contains 15 pages and was rendered page by page for visual review.
- The evidence index records model checkpoints, SHA256 values, runtime permissions, evidence tiers, and external dependencies.

## Remaining Dependencies

Compound synthesis and wet-lab validation, target-domain cases, physician gold-standard annotations, enterprise raw dual-channel data, filter curves, and target-hardware validation remain external dependencies.
