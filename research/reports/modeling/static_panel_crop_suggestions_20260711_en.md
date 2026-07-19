# D047/D048 Publication Figure Panel Crop Suggestions

Date: 2026-07-11

## 1. Objective

This work establishes a traceable multi-panel decomposition workflow for 14 uncropped D047/D048 publication figures. The resulting records add oral fluorescence, approximate white-light/fluorescence bone pairs, fluorescence microscopy, and histopathology review evidence. Every record remains non-target-domain review material without physician ground-truth status.

## 2. Implementation

- Added `src/datasets/static_panel_detection.py` with white-gutter projections, recursive splitting, weak-seam two-column fallback, bbox deduplication, and crop quality gates.
- Added `tools/build_static_panel_crop_suggestions.py` to create stable child records and a unified suggestion manifest.
- Visually audited all 14 local source figures and checked panel roles, pair relationships, and temporal limitations against publication captions.
- Exposed suggested bbox, method, score, warnings, panel role, and pair alignment through the backend queue.
- Updated the crop editor to show the original suggestion as an amber dashed box and the editable crop as a green solid box.
- Crop persistence keeps `review_state=review_required` and `training_eligible=false`, while invalidating any stale automated seed for that record.

## 3. Dataset Result

| Item | Count |
|---|---:|
| Source multi-panel figures | 14 |
| Atomic crop suggestions | 52 |
| Quality pass | 40 |
| Quality warning | 12 |
| `fluorescence_signal` | 19 |
| `paired_white_light` | 13 |
| `paired_fluorescence` | 13 |
| `histopathology` | 7 |
| Unique pair IDs | 14 |
| Current static review queue | 61 |
| Human or physician reviewed | 0 |
| Training eligible | 0 |

All child records retain their original `source_group_id`. The existing nine automated mask seeds remain available, while the 52 new records stay at the crop-review stage.

## 4. Quality Controls

The quality gates cover out-of-bounds coordinates, invalid dimensions, area below 2% of the source figure, short side below 96 px, extreme aspect ratio, near-full-image crops, white or black border residue, and duplicate or high-IoU candidates.

PMC12829038 C-D pairs are labeled `weak_sequential` and are limited to coarse dual-modal representation. Selected PMC7666678 and PMC8132458 pairs are labeled `approximate_view`. They are excluded from pixel-registration supervision. Publication labels, arrows, and scale boxes remain possible shortcut features and require down-weighting or occlusion augmentation during later training.

## 5. Evidence

- Manifest: `research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json`
- Review workbench: `http://127.0.0.1:5174/dataset-review`
- Contact sheet: `artifacts/data_review/d047_d048_52_crop_suggestions_contact_sheet.jpg`
- UI screenshot: `artifacts/platform_smoke/dataset_crop_suggestions_ui_20260711.png`

## 6. Medical and Training Boundary

- Suggestions only reduce panel-localization workload.
- Suggested panel roles and pair IDs require authorized review.
- Crop acceptance does not create a physician mask or training admission.
- Mask review remains a separate accepted, modified, or rejected operation.
- D047/D048 cannot support target-domain clinical performance claims for intraoperative ICG jaw osteomyelitis.
