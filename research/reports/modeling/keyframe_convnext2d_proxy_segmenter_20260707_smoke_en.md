# 2D Keyframe ConvNeXt Proxy Segmenter Report

## Scope

This report records a trainable 2D ConvNeXt-U-Net style keyframe segmentation model. It moves official JPEG/MP4 keyframe inference from a heuristic hotspot baseline toward real PyTorch checkpoint inference. The current training data are synthetic or pseudo-labeled proxy data, not real intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_video_signal_multimask_v2.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_video_signal_multimask_v2_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_video_signal_multimask_v2_model_card.json`
- Data source: manifest
- Manifest count: 1; sample-weight stats: `{"count": 101, "min": 1.0, "median": 1.0, "max": 4.0, "mean": 1.02970302}`
- Review-state counts: `{"review_required": 100, "modified": 1}`
- Train samples: 75; validation samples: 26.
- Pseudo-label quality gates: `{}`
- Human-review seed set: 0; path: `None`
- Training batches: 2; batch size: 2.
- Mean train loss: 0.7905
- Device: cuda; PyTorch: 2.11.0+cu128.

## Metrics

- Foreground Dice: 0.1230
- Foreground IoU: 0.0662
- Prediction positive fraction: 0.3514

## Medical Boundary

2D keyframe segmentation proxy trained on synthetic or pseudo-labeled fluorescence-like frames; not real intraoperative ICG jaw osteomyelitis clinical performance.
ICG mainly reflects perfusion, vascular permeability, and tissue-activity differences. It is not a jaw-osteomyelitis-specific probe; model outputs are candidate-region prompts for physician review, not automatic diagnosis.

## Data Gap And Next Step

There is still no real target-domain intraoperative ICG jaw osteomyelitis MP4/JPEG dataset with pixel-level physician labels. This run uses public proxy MP4 data and fluorescence-intensity pseudo masks to keep a runnable model. The next step is to promote accepted/modified `review_manifest_json/csv` samples into higher-weight training data and retain rejected samples for negative/error analysis.
The script now supports multiple merged manifests and `sample_weight` weighted loss. These weights encode review confidence or error-analysis priority only; they are not target-domain clinical labels.
