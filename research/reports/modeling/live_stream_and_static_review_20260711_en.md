# Live Stream Analysis and Static Dataset Review Closure Report

Date: 2026-07-11

## Live Video Software Path

The platform now provides bounded OpenCV input for `camera://opencv/<index>`, RTSP, HTTP, HTTPS, and local video sources. Browser-camera input remains a local preview and explicitly records that backend frame transport is unavailable.

The capture layer uses a background reader and bounded queue. It records open and read timeouts, total capture duration, frames read and dropped, capture backend, resolution, frame rate, and disconnection warnings. Finite JPEG keyframes enter the existing fluorescence-candidate segmentation, risk, uncertainty, dynamic-quantification, and evidence-manifest paths.

Each output records capture time, capture-stage frame age, inference-completion frame age, the display-age limit, and `display_allowed`. Unmatched capture frames, conflicting frame identities, missing explicit display permission, and results older than `live_max_frame_age_ms` fail closed. If every result is stale, the run is marked `failed`, the case does not advance, and candidate, decision-summary, and AI-artifact publication is suppressed.

A real local synthetic MP4 completed a capture-to-analysis smoke with three keyframes through `VideoCapture`, segmentation, and manifest generation under `realtime_stream_keyframes`. This evidence does not cover the enterprise microscope interface, raw paired channels, continuous 4K capture, or operating-room latency.

## D047/D048 Static Review Workspace

The `/dataset-review` page now exposes eight D047 and fifteen D048 publication records, for 23 near-domain records. Nine records have atomic panel crops and fourteen source figures enter a new crop workspace. It persists bounding boxes, exact coordinates, panel roles, `pair_id`, crop notes, and source-image SHA256 before routing the crop into seed generation and pixel-level mask review.

All nine cropped records now have automated candidate masks. Every seed remains `review_required`, `training_eligible=false`, and `reviewer_role=automated_seed`; automated records do not enter the human-reviewed manifest. The binary editor continues to support add, erase, brush size, undo, redo, clear, accept, modify, reject, and reviewer notes.

The persistence gate validates PNG and base64 readability, exact image-mask dimensions, binary values, non-empty area, a 0.0001-0.95 area fraction, approved D047/D048 paths, provenance, license, source groups, sampling weights, and image/label SHA256 values.

The default reviewer role is `project_reviewer`. `physician_reviewed=true` is written only after an explicit `physician` selection. Project-reviewed masks can serve as near-domain engineering seeds and do not constitute physician gold-standard or target-domain labels.

The seed and reviewed manifests are connected to `tools/build_layered_dataset_registry.py`. The registry now uses 192 grouped hotspot keyframes across 48 source-video groups while retaining boundary-risk, uncertainty, and exposed-bone proxy records. It contains 504 records, zero quality errors, 393 training-admission candidates, and zero target-domain records. Admission now separates `proxy_pretrain`, `reviewed_finetune`, and `independent_evaluation`; proxy labels cannot enter the latter two stages.

## Verification

- Python: 301 tests passed.
- Frontend: 56 passed and 1 skipped; TypeScript and production build passed.
- Ruff, targeted Mypy, and `git diff --check` passed.
- Live API: `GET /dataset-review/queue` returns 23 records: fourteen awaiting crop selection and nine with automated seeds.
- Desktop screenshot: `artifacts/platform_smoke/dataset_crop_review_ui_20260711.png`.

## Boundary

Enterprise SDK access, synchronized raw white-light/NIR, target hardware, and continuous 4K validation remain unavailable. Static crops come from open publication figures and currently have no physician pixel annotations. Outputs remain research-validation evidence and physician-review support.
