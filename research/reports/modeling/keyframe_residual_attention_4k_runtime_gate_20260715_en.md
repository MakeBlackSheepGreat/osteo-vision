# Residual Attention U-Net 4K Candidate Runtime Gate

## Verdict

- Technical gate passed: `True`
- Candidate model: `keyframe_residual_attention_unet_s20260715_20260715`
- Threshold: `0.4`
- Candidate selected by production config: `False`
- Automatic replacement performed: `False`
- Failed checks: `[]`

## 4K Runtime

- Input: `[3840, 2160]`; tile `512`, overlap `64`, `45` tiles.
- Repeated runs: `3`.
- Model P50/P95: `415.683` / `724.432` ms.
- End-to-end P50/P95: `2181.523` / `5776.683` ms.
- Peak GPU memory: `723.579` MB.
- Positive-area fraction range: `0.02770291` - `0.02770291`.

## Failure Thresholds

- Official 4K dimensions, CUDA, tiled execution, and deterministic repeated masks are required.
- End-to-end P95 limit: `15000.0` ms; model P95 limit: `3000.0` ms.
- Peak GPU memory limit: `2048.0` MB.
- Positive-area fraction range: `0.0001` - `0.6`.

## Same-Protocol Mainline Comparison

- Comparable: `True`; mainline model: `convnext2d_keyframe_proxy_segmenter`.
- Mainline model P50/P95: `515.397` / `800.159` ms.
- Mainline end-to-end P50/P95: `2252.741` / `5775.993` ms.
- Mainline peak GPU memory: `656.318` MB.
- Candidate deltas: model P50 `-19.347`%, model P95 `-9.464`%, end-to-end P50 `-3.161`%, end-to-end P95 `0.012`%, GPU memory `10.248`%.
- Negative latency deltas indicate lower candidate latency; positive memory deltas indicate higher candidate usage.

## Runtime Risk

- Continuous-playback full-evidence latency risk: `True`.
- Candidate end-to-end P95 is `5776.683` ms. This supports offline full-evidence keyframes and cannot sustain per-frame playback refresh.

## Full Platform Flow

- Full flow passed: `True`; case: `case_9667cba505`.
- Configured model: `keyframe_residual_attention_unet_s20260715_20260715`; executed models: `['keyframe_residual_attention_unet_s20260715_20260715']`.
- Analysis methods: `['trainable_keyframe_segmenter']`; heuristic fallback: `False`.
- Missing required formats: `[]`.
- Per-frame model and method verified: `True`; per-frame probability files verified: `True`.

## Configuration Boundary

- Current production segmentation model: `convnext2d_keyframe_proxy_segmenter`.
- Current production required models: `['convnext2d_keyframe_proxy_segmenter']`.
- The candidate remains outside the production config; this run produced isolated candidate-gate evidence.
- Mainline strict preflight after the gate: `True`.

## Medical Boundary

The gate covers deterministic platform execution on a synthetic 4K keyframe and public proxy-label evaluation. Target-domain intraoperative ICG jaw osteomyelitis performance remains unmeasured, and all candidate regions require physician review.
