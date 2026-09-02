# Multi-seed Keyframe Segmentation Model Selection

## Conclusion

- Recommended family: `residual_attention_unet_keyframe_segmenter`.
- Validation-selected checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260715_20260715.pt`.
- Locked threshold: `0.4`.
- `runtime_replacement_allowed=false` remains in force until strict 4K tiled and platform-flow gates pass.

## Held-out test comparison

| Model | Seeds | Dice mean +/- SD | IoU mean +/- SD | Recall | P95 ms | Peak MB | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net baseline | 1 | 0.8987 +/- 0.0000 | 0.8164 +/- 0.0000 | 0.8908 | 3.57 | 22.19 | baseline |
| multiscale_depthwise_unet_keyframe_segmenter | 3 | 0.8978 +/- 0.0113 | 0.8149 +/- 0.0183 | 0.8933 | 4.25 | 20.14 | hold |
| residual_attention_unet_keyframe_segmenter | 3 | 0.9149 +/- 0.0041 | 0.8435 +/- 0.0071 | 0.9099 | 5.13 | 26.03 | pass |

## Evidence boundary

All metrics use public non-target-domain fluorescence proxy masks. They do not measure clinical performance on intraoperative ICG jaw osteomyelitis and cannot justify an autonomous diagnosis claim.
