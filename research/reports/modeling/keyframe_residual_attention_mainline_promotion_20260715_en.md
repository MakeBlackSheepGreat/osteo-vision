# Residual Attention Keyframe Mainline Promotion Report

## Decision

`keyframe_residual_attention_unet_s20260715_20260715` is now the competition-platform mainline for JPEG/MP4 keyframe segmentation. The strict runtime, development runtime, and task package select the promoted checkpoint. `convnext2d_keyframe_proxy_segmenter` remains available as the previous engineering comparator.

- Strict configuration SHA256: `9a2247035c27ba8f142d628f721bfb61d2e9b296a1201ccef375a98fc5f5e855`.
- Runtime threshold: `0.4`; checkpoint SHA256: `826e90c2ee3efd45d0d0d979e85a2a3e2dcd60d853d8497f6328e46a406e0d39`.
- Strict startup preflight passed with one required model, zero errors, and zero warnings.
- The post-promotion 4K flow passed for `3840x2160` JPEG/MP4 input, 2/2 keyframe probability maps, engineering review, and evidence export without heuristic fallback.
- The eight-frame 960-pixel live fast-output gate passed. Current mainline service E2E P95 was `176.457 ms`; model P95 was `36.377 ms`.

## Model Selection

| Measure | Residual Attention mainline | Previous ConvNeXt comparator |
|---|---:|---:|
| Locked proxy test Dice | 0.917681 | 0.898711 |
| Locked proxy test IoU | 0.848335 | 0.816431 |
| Three-seed Dice | 0.914894 +/- 0.004139 | Single baseline run |
| Empty-mask / over-segmentation rate | 0 / 0 | 0 / 0 |
| 4K tiled model P95 | 724.432 ms | 800.159 ms |
| 4K full-evidence E2E P95 | 5776.683 ms | 5775.993 ms |
| Consecutive 960x720 fast-output model P95 | 36.377 ms | 59.531 ms |
| Consecutive 960x720 fast-output E2E P95 | 176.457 ms | 182.601 ms |

Residual Attention passed the locked proxy test, multi-seed stability, 4K model-runtime, and consecutive fast-output gates. Full-evidence 4K output remains an offline keyframe path at about 5.78 seconds. Playback synchronization uses the independent `live_fast` output profile.

## Runtime Contract

- `runtime.required_model_ids`, `runtime.tasks.segmentation.model_id`, and the strict model entry select the promoted checkpoint.
- `clinical_claim_allowed=false`, `target_domain=false`, and physician-review boundaries remain enforced.
- Strict competition runtime sets `allow_heuristic_keyframe_fallback=false`; an unavailable model produces a structured failed analysis.
- 4K execution uses 512-pixel tiles, 64-pixel overlap, and batch size 4. Live execution uses the frontend 960-pixel limit, JPEG quality 0.85, CUDA AMP, disabled TTA, and serial frame processing.
- The `/annotations` physician workspace provides version audit, reviewer identity, submission/review states, and training admission. Trusted accepted/modified annotations can be admitted through `tools/build_keyframe_training_manifest_from_manual_annotations.py`; engineering or unreviewed records remain isolated.

## Post-Promotion Evidence

| Evidence | Result | SHA256 |
|---|---|---|
| Strict runtime preflight | Passed | `2f6169b395719ac2f174d1d75c5425d39891d148a62bdf268e2722b12aa8b04b` |
| Post-promotion 4K competition flow | Passed | `b51dc0d7df0d668bc6da2fe8eebf1d1a88fb10775a0a7780285ae0c4a2efe46b` |
| Consecutive proxy-video live fast-output | Passed | `6aa6c72e8c2898c8978e70c5a945d41d466d7a486afe57a95d9f9d614f10005b` |
| Candidate 4K technical gate | Passed | `0a4ea2acf9036de44fe5561c0feb5c31a36f131be7eb6f435f227eb16cff0ac3` |
| Post-promotion checkpoint manifest | Passed, no invalid promotion evidence | `c4e413ca2084f28c0396a8ca747dd30d1b0f70f6d09b5a1b42407393fa140f8a` |

## Evidence Boundary

Accuracy evidence uses public, proxy, and pseudo-labeled non-target-domain data. Consecutive frames come from the public ex-vivo fluorescence proxy video D046/OFDVDNET. These results establish model selection, software execution, output integrity, and physician-review feedback mechanics. They do not establish clinical performance for intraoperative ICG jaw osteomyelitis. Every candidate region requires physician review.
