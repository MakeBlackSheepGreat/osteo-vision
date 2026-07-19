# Residual Attention Current-Production Live Single-Frame Fast-Output Runtime Gate

## Decision

- Combined gate: `passed`.
- Current production-model gate: `passed`; same-protocol previous ConvNeXt mainline gate: `passed`.
- Strict protocol comparability: `True`. The current production config SHA256 remained unchanged and this gate performed no model switch.
- Current production config SHA256: `9a2247035c27ba8f142d628f721bfb61d2e9b296a1201ccef375a98fc5f5e855`; isolated previous ConvNeXt snapshot SHA256: `4cbda808f7c8b4f75957dc62eb8176aff5c9db9892b00efee521e106cddf91f3`.
- These results provide non-target-domain engineering latency and output-integrity evidence only. Physician review remains required.

## Measured Protocol

- Input: consecutive frames from the public ex vivo fluorescence proxy MP4 D046/OFDVDNET_023, encoded as browser-profile JPEG at `960` maximum long side and `0.85` quality; measured size `960x720`.
- Device: `NVIDIA GeForce RTX 5060 Laptop GPU`; CUDA available: `True`.
- Each model completed model warmup and `1` excluded full-size frame, followed by `8` serial timed frames.
- Visual checks of source frames 319 and 326 confirmed a multi-viewport white-light/fluorescence ex vivo tissue scene without a title card. Its role remains a public ex vivo non-target-domain fluorescence proxy.
- Service end-to-end timing covers JPEG decode, uniquely addressed source evidence, model inference, mask/risk/uncertain-mask rendering, JPEG overlay generation, and file writes. HTTP, browser scheduling, and network transfer are excluded.

## Same-Protocol Results

| Runtime role / model | Service E2E P50 / P95 ms | Model P50 / P95 ms | Peak GPU MB | Mask/overlay | Unique paths | Gate |
|---|---:|---:|---:|---|---|---|
| `current_production_model_via_isolated_candidate_config` / `keyframe_residual_attention_unet_s20260715_20260715` | 154.685 / 176.457 | 34.368 / 36.377 | 380.134 | pass | pass | pass |
| `previous_mainline_comparator_snapshot` / `convnext2d_keyframe_proxy_segmenter` | 173.885 / 182.601 | 57.636 / 59.531 | 287.779 | pass | pass | pass |

Current-production Residual Attention service E2E P95 changed by `-3.365%` relative to the previous ConvNeXt mainline; model P95 changed by `-38.894%`. Positive values indicate higher current-production latency.

## Output Audit

- All `8` current-production frames and `8` previous-mainline frames used `live_fast`, CUDA AMP, and disabled TTA.
- Observed inference modes: current production `whole_frame`; previous mainline `whole_frame`.
- Every frame has uniquely addressed source JPEG, binary mask, risk mask, uncertain mask, and JPEG overlay evidence. Mask and overlay geometry matches the input.
- The fast-output profile omits probability, uncertainty, and pseudocolor files while retaining the renderable mask, risk prompts, and overlay used by live review.

## Boundary

The input is a public or proxy non-target-domain image and execution used direct service calls. This evidence excludes enterprise microscope transport, browser-to-API network overhead, continuous full-frame 4K inference, clinical performance on intraoperative ICG jaw osteomyelitis, and operating-room endurance.
