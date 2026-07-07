# Video Signal Segmentation Round-2 Landing Note

Date: 2026-07-07

## Goal

Round 2 focuses on the missing `bone_gate_mask` in `video_signal_segmentation`. The current MP4/JPEG mainline remains unchanged while the platform gains prompt-assisted bone-gate generation, review persistence, export fields, and a training-feedback manifest path.

## Engineering Result

- Added a backend candidate-level bone-gate generation API using the `medsam2_osteo_promptable` prompt fallback.
- Extended review manifests with `bone_gate_mask_path`, `bone_gate_overlay_path`, `label_source`, `prompt_source`, and `sample_weight`.
- Added `tools/build_video_signal_multimask_training_manifest.py` to merge D046 fluorescence signal masks and prompt-assisted review bone-gate masks.
- Added `scripts/train_video_signal_multimask_v2.py` for mask-type-filtered v2 training. The v2 checkpoint is not promoted into the runtime mainline by default.
- Added frontend controls in video synchronized analysis to generate and display keyframe-level bone-gate masks and overlays.

## Medical And Data Boundary

`medsam2_osteo_promptable` is still a deterministic prompt fallback, not real MedSAM2 checkpoint inference. D046, public videos, and prompt-assisted review samples must not be reported as real intraoperative ICG jaw osteomyelitis clinical labels. All outputs require physician review and are not clinical diagnoses.
