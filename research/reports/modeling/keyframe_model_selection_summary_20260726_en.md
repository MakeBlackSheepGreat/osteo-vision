# Multi-seed Keyframe Segmentation Model Selection

## Conclusion

- Recommended family: `residual_attention_unet_keyframe_segmenter`.
- Validation-selected checkpoint: `C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\keyframe_residual_attention_unet_s20260726_20260727.pt`.
- Locked threshold: `0.35`.
- `runtime_replacement_allowed=false` remains in force until strict 4K tiled and platform-flow gates pass.

## Held-out test comparison

| Model | Seeds | Dice mean +/- SD | IoU mean +/- SD | Recall | P95 ms | Peak MB | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net baseline | 1 | 0.8987 +/- 0.0000 | 0.8176 +/- 0.0000 | 0.8881 | 3.33 | 22.19 | baseline |
| multiscale_depthwise_unet_keyframe_segmenter | 3 | 0.9041 +/- 0.0099 | 0.8258 +/- 0.0160 | 0.9017 | 4.53 | 21.14 | hold |
| nested_skip_unet_keyframe_segmenter | 3 | 0.9147 +/- 0.0044 | 0.8438 +/- 0.0068 | 0.9064 | 2.78 | 27.04 | pass |
| plain_unet_keyframe_segmenter | 3 | 0.9121 +/- 0.0051 | 0.8395 +/- 0.0078 | 0.9028 | 2.71 | 24.13 | pass |
| residual_attention_unet_keyframe_segmenter | 3 | 0.9167 +/- 0.0027 | 0.8476 +/- 0.0039 | 0.9066 | 6.83 | 27.02 | pass |

## Evidence boundary

All metrics use public non-target-domain fluorescence proxy masks. They do not measure clinical performance on intraoperative ICG jaw osteomyelitis and cannot justify an autonomous diagnosis claim.
