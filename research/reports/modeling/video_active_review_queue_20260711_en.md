# Video Keyframe Active Review and Small Gold-Standard Preparation

## Goal

This work adds an executable path from `frame_details_manifest.json` and `video_segmentation_manifest.json` to a focused physician-review queue and a training-manifest patch. The queue prioritizes uncertainty, temporal jumps, mask-area anomalies, domain gaps, inference failures, and pending bone-gate review.

## Implementation

- Service: `backend/src/services/active_review_queue.py`
- CLI: `tools/build_video_active_review_queue.py`
- Unit tests: `backend/tests/unit/test_active_review_queue.py`
- CLI smoke test: `tests/smoke/test_video_active_review_queue_cli.py`

The review score uses uncertainty at 0.35, temporal instability at 0.25, mask-area anomaly at 0.20, domain gap at 0.10, and failure or fallback at 0.10. High-priority routing adds up to 0.05. Selection deduplicates by source video and frame index, then applies a minimum time interval and a per-source quota.

## Output Contract

The CLI writes:

- `video_active_review_queue.json`
- `video_active_review_queue.csv`
- `video_active_review_training_patch.json`
- `video_active_review_training_patch.csv`

Each row preserves `accepted`, `modified`, `rejected`, or `review_required`. Default weights are 4.0, 4.0, 0.5, and 1.0. Modified rows require `modified_mask_path` before training-patch promotion. Rejected rows are routed to negative-candidate handling or error analysis. Pending rows remain in the review queue.

## Recorded Smoke Run

The smoke run consumed frame-details and video-segmentation manifests from the same analysis run:

- 6 input candidates.
- 3 candidates after cross-manifest deduplication.
- 3 selected review rows.
- All selected rows carried high-uncertainty and domain-gap reasons.
- 2 rows carried a mask-area anomaly reason.
- All selected rows retained pending bone-gate review.
- The initial training patch contained 0 rows, matching the pre-review gate.
- The CLI test applied an `accepted` decision and emitted one training-patch row with weight 4.0.

Example:

```powershell
conda run -n osteo-vision python tools/build_video_active_review_queue.py `
  --input <frame_details_manifest.json> <video_segmentation_manifest.json> `
  --output-dir artifacts/active_review_queue `
  --max-frames 40 `
  --max-frames-per-source 12 `
  --min-interval-sec 2.0
```

After review, a JSON or CSV file containing `review_id`, `review_state`, `modified_mask_path`, and `review_notes` can be supplied through `--review-updates`.

## Verification

- Pytest: 4 passed.
- Ruff: passed.
- Mypy: passed.
- CLI smoke: passed; JSON/CSV outputs, decision feedback, and the training patch were verified.

## Evidence Boundary

Active-review ranking supports annotation efficiency and proxy-data quality control. Public, synthetic, pseudo-labeled, and cross-domain fluorescence samples retain their original `input_domain`. Physician-reviewed rows can enter the small gold-standard candidate pool. Target-domain cases and linked pathology or culture evidence remain required for clinical interpretation.
