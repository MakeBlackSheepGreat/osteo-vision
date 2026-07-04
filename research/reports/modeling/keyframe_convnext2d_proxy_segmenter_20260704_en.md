# 2D Keyframe ConvNeXt Proxy Segmenter Report

## Scope

This report records a trainable 2D ConvNeXt-U-Net style keyframe segmentation model. It moves official JPEG/MP4 keyframe inference from a heuristic hotspot baseline toward real PyTorch checkpoint inference. The current training data are synthetic or pseudo-labeled proxy data, not real intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy.pt`
- Manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_manifest.json`
- Model card: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_convnext2d_proxy_model_card.json`
- Data source: manifest
- Train samples: 163; validation samples: 37.
- Training batches: 80; batch size: 4.
- Mean train loss: 0.3012
- Device: cuda; PyTorch: 2.11.0+cu128.

## Metrics

- Foreground Dice: 0.8640
- Foreground IoU: 0.7614
- Prediction positive fraction: 0.2029

## Medical Boundary

2D keyframe segmentation proxy trained on synthetic or pseudo-labeled fluorescence-like frames; not real intraoperative ICG jaw osteomyelitis clinical performance.
