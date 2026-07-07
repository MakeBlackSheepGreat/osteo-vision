# Round-3 Video-Signal Multi-Mask Feedback Training Record

Date: 2026-07-07

## Goal

Round 3 addresses the lack of bone-gate samples by generating prompt-assisted `bone_gate_mask` seed samples from D046 public/proxy keyframes, while adding binary mask editing, edited-mask persistence, multi-mask manifest feedback, and a v2 smoke training path.

## Results

- Prompt-assisted bone-gate seed batch: 50 `exposed_bone` samples.
- Multi-mask manifest: 350 rows, including `fluorescence_hotspot=100`, `boundary_risk=100`, `uncertain=100`, and `exposed_bone=50`.
- v2 filtered training rows: 150 rows, including `fluorescence_hotspot=100` and `exposed_bone=50`.
- v2 smoke metrics: Dice 0.0000, IoU 0.0000, prediction-positive fraction 0.0000, threshold 0.5.
- Effective training-candidate gate: not met. The 50 bone-gate samples are still `review_required`; accepted/modified samples have not reached the 30-row threshold.

## Engineering Conclusion

The platform now runs batch seeding, frontend edits, backend persistence, manifest feedback, and v2 smoke training. However, `review_required` seed masks must not be treated as real bone-surface labels. The next step is to accept or modify at least 30 bone-gate masks through review before retraining and running threshold, empty-mask, and over-segmentation checks.

## Medical And Data Boundary

D046 is public/proxy video data, not real target-domain intraoperative ICG jaw osteomyelitis data. `medsam2_osteo_promptable` remains a deterministic prompt fallback, not real MedSAM2 checkpoint inference. The current v2 checkpoint must not replace the MP4/JPEG mainline configuration.
