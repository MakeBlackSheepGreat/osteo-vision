# Public-Video Dynamic Fluorescence Quantification Validation

Date: 2026-07-11

## Source and Boundary

- Source: Dryad OFDVDnet record `OFDVDNET_023`.
- File: `OL-2021-07-20-131158-000014-record.mp4`.
- Scene: ex vivo chicken-thigh fluorescence-guided surgery proxy, 2048x1536, 15 FPS, 170.53 seconds.
- Boundary: public non-target-domain decoded 8-bit luminance proxy; no jaw osteomyelitis or intraoperative ICG claim.

## Method

`AnalysisService.start_analysis()` processed source frame indexes `319/958/1598/2237` with the current inference configuration. The run covered decoding, keyframe segmentation, decoded-pixel intensity statistics, structured frame details, and a time-intensity curve.

## Results

| Metric | Result |
|---|---:|
| Analysis status | completed |
| Curve available | true |
| Valid keyframes | 4 |
| Timestamp range | 21.266667-149.133333 s |
| Dynamic range nonzero | false |
| Curve quality | limited |
| Time to peak | 0.0 s |
| Maximum normalized rise slope | 0.0/s |
| Normalized AUC | 0.0 |
| AI inference P50/P95 | 633.504/978.138 ms |
| Inference mode | tiled for all four frames |

All four points used decoded pixels for `p95_intensity` and `background_intensity`; segmentation probability was excluded. Background-corrected P95 values were approximately 0.596-0.608. The software therefore emitted `quality_status=limited`, `dynamic_range_nonzero=false`, and zero slope/AUC.

## Evidence

- Local case repository: `artifacts/platform_smoke/public_video_dynamic_20260711/cases.json`
- Frame details: `artifacts/visual_evidence/osteo_vision/cases/public_dynamic_ofdvdnet_023/frame_details/`
- Key fields: `source=decoded_keyframe_intensity`, `source_intensity_key=p95_intensity`, `background_correction=per_frame_background_subtraction`

## Boundary

The run verifies structured curve generation and quality gating on a public real-video keyframe path. Cross-case interpretation requires the enterprise raw NIR channel, locked acquisition parameters, injection timing, and physician-reviewed ROIs.
