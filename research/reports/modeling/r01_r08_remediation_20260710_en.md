# R01-R08 Remediation and Evidence Report

## 1. Verdict

The R01-R08 platform engineering remediation was implemented and reviewed on 10-11 July 2026. Each item now has code, tests, runtime evidence, or an evidence index within the current proxy-engineering scope. All reported model metrics use pseudo-labels or prompt-assisted seeds from public non-target-domain D046 videos. They do not estimate intraoperative ICG jaw-osteomyelitis clinical performance.

| ID | Issue | Status | Primary evidence |
|---|---|---|---|
| R01 | Source-video leakage | Completed | 48 source groups; train/val/test groups 28/14/6; `leakage_detected=false` |
| R02 | All-zero multi-mask model | Engineering fix completed | Independent heads, validity masks, per-head thresholds; zero empty-mask rate on test |
| R03 | Credibility of historical 0.9093 | Completed | Historical value withdrawn as generalization evidence; test Dice 0.9214, video-bootstrap 95% CI 0.9127-0.9302 |
| R04 | Final platform evidence chain | Platform index completed | Evidence organized by contrast agent, fusion, AI, device boundary, and medical boundary |
| R05 | White-light/fluorescence AI | Proxy architecture and interface verified | Four ablations run; runtime permission blocks configured execution and preserves traditional fusion |
| R06 | Dynamic ICG quantification | Decoded-frame software path verified | Decoded pixel/ROI intensity, background correction, normalization, time-to-peak, slope, AUC, and QC |
| R07 | 4K analysis stability | Public non-target-domain keyframe validation completed | Long MP4, multiple frame rates, unreadable encoding, derived 4K JPEG, 45 tiles, fallback, and memory observation |
| R08 | Uncertainty | Proxy-task technical calibration verified | Temperature scaling, entropy, TTA variance, ECE/Brier, uncertain mask, review priority |

## 2. Evidence by issue

### R01-R03

`src/datasets/group_splits.py` enforces group-exclusive splits before frame extraction and causes manifest building, training, or evaluation to fail on leakage. The rebuilt manifest contains 192 frames from 48 source videos. The independent test split contains 24 frames from six held-out sources.

At threshold 0.45, held-out proxy performance is Dice 0.9214, IoU 0.8546, Boundary F1 0.9844, empty-mask rate 0, over-segmentation rate 0, ECE 0.00524, and Brier score 0.01973. The historical Dice 0.9093 is retained only as an obsolete proxy experiment.

The multi-mask implementation aggregates labels per image and independently supervises `fluorescence_signal` and `bone_gate`. Test Dice values are 0.4984 and 0.8722, respectively, with no empty masks. Bone-gate labels remain review-required prompt-assisted seeds.

### R04-R05

The official evidence map covers contrast-agent design, multimodal fusion and processing, and AI-assisted interpretation. Physical contrast-agent experiments, target-domain cases, physician gold standards, and microscope validation remain external dependencies.

The dual-channel model includes white-only, fluorescence-only, early-fusion, and intermediate-fusion modes. Early fusion was selected using validation Dice 0.8573 and achieved test Dice 0.8654. The white-light input is synthetically derived from source luminance. The backend now checks `enabled`, `runtime_allowed`, checkpoint availability, and adapter warmup. The current dual-channel configuration uses `runtime_allowed=false` and records a skipped state with traditional fusion available.

### R06-R08

Video summaries now expose a sparse-keyframe time-intensity curve with per-frame background correction, baseline-to-peak normalization, time-to-peak, maximum normalized rise slope, normalized AUC, and quality flags. Current MP4/JPEG values use a decoded 8-bit luminance domain. A public OFDVDnet run emitted `available=true` and `quality_status=limited` because the selected interval had little dynamic range.

A five-run 4K smoke used 512-pixel tiles with 64-pixel overlap and produced 45 tiles per image. Model-inference P50 was 1587.4 ms. End-to-end P50/P95 were 3481.8/7577.3 ms. Full-resolution masks, probability maps, uncertainty maps, pseudocolor, and overlays passed existence and geometry checks. These results support keyframe-based playback analysis and do not establish full-frame 30 FPS processing.

The public-video extension covered a 170.53-second OFDVDnet ex vivo fluorescence proxy and a 113.98-second non-fluorescence tibial-osteomyelitis procedure. Derived 4K-JPEG single-keyframe latency was 3.94-4.28 seconds, with 1.52-1.56 seconds for probability inference. Enterprise 3840x2160 MP4 remains pending.

Runtime uncertainty uses checkpoint temperature 1.4138, predictive entropy, horizontal-flip TTA variance, risk and uncertain masks, and physician-review priority. Proxy calibration cannot establish clinical disease-risk calibration.

## 3. Main artifacts

- `artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy_grouped_20260710.pt`
- `artifacts/checkpoints/osteo_vision/keyframe_video_signal_multimask_v2_grouped.pt`
- `artifacts/checkpoints/osteo_vision/dual_channel_proxy_20260710.pt`
- `research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/`
- `research/reports/modeling/video_signal_multimask_v2_training_20260710_multimask_v2_grouped.json`
- `research/reports/modeling/dual_channel_ablation_20260710_dual_channel.json`
- `artifacts/platform_smoke/keyframe_tiling_20260710_grouped_5run/`
- `research/reports/modeling/public_video_4k_validation_20260711_en.md`
- `research/reports/modeling/public_video_dynamic_quantification_20260711_en.md`

## 4. Medical boundary

The platform reports fluorescence/perfusion signal candidates, review-required bone gating, boundary risk, uncertainty, and physician-review evidence. Proxy metrics cannot support automatic diagnosis, final disease masks, or replacement of physician judgement. Target-domain MP4/JPEG data, physician pixel annotations, physical contrast-agent experiments, and microscope validation still require external collaboration.
