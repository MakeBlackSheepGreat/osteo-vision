# Public Real-Video and Official 4K Input Validation

Date: 2026-07-11

## Scope

The competition device document specifies 3840x2160 capture, JPEG images, and MP4 videos. This validation covers visually reviewed public videos, long MP4 inputs, multiple frame rates, an unreadable MP4, a source-derived 4K JPEG, forced tiled inference, model fallback, and a short sustained-memory observation.

The platform mode is recorded as `keyframe-based playback analysis`. No full-frame 4K 30 FPS AI claim is supported by this run.

## Sources

| Record | Source | Scene | Fluorescence | Profile |
|---|---|---|---|---|
| `OFDVDNET_023` | [Dryad OFDVDnet](https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w) | Mock chicken-thigh fluorescence-guided surgery | Yes | 2048x1536, 15 FPS, 170.53 s, H.264 |
| `PMC12350196_MMC1` | [PMC12350196](https://pmc.ncbi.nlm.nih.gov/articles/PMC12350196/) | Endoscopic intramedullary debridement of tibial osteomyelitis | No | 1280x720, 29.97 FPS, 113.98 s, H.264 |

Nine-frame contact sheets were generated and visually inspected for each source. OFDVDnet shows reference, fluorescence, and overlay views in an ex vivo operative field. The PMC video shows endoscopic debridement and sclerotic-bone resection, with title and teaching frames also present. Both sources remain outside the target domain.

## Results

- Both traced public videos exceeded 60 seconds and entered keyframe selection.
- Native 15 FPS and 29.97 FPS inputs were readable. Derived 6 FPS and 29.97 FPS MP4V variants retain source relationships and SHA256 records.
- `OFDVDNET_004` reproduced an unreadable-container failure already recorded by its source manifest.
- A public-source fluorescence keyframe was resized to a 3840x2160 JPEG and processed three times with forced tiling.
- All 4K runs used 45 tiles and produced masks, probability maps, pseudocolor overlays, and uncertainty outputs.
- A deliberately missing primary checkpoint failed warmup, while `fluorescence_hotspot_2d_segmenter` produced the fallback mask.
- Eight sustained 1024x768 keyframe runs changed process RSS by 0.090 MB after warmup.

## Timing

Environment: the `osteo-vision` Conda environment and an NVIDIA GeForce RTX 5060 Laptop GPU.

| Stage | N | P50 ms | P95 ms | Min ms | Max ms |
|---|---:|---:|---:|---:|---:|
| Public-video keyframe decode/selection | 6 | 1104.421 | 1770.028 | 438.814 | 1770.028 |
| Isolated RGB load | 11 | 13.108 | 49.401 | 4.352 | 53.576 |
| Model probability inference | 8 | 287.117 | 1557.461 | 140.784 | 1558.022 |
| Postprocess estimate | 8 | 272.998 | 2600.093 | 203.073 | 2674.173 |
| Adapter end to end | 8 | 575.405 | 4195.170 | 349.735 | 4284.168 |

Forced 4K tiled inference required 3.94-4.28 seconds end to end per keyframe, including 1.52-1.56 seconds for probability inference. This supports asynchronous keyframe analysis and leaves full-frame real-time performance unverified.

The adapter supplies the probability-inference timing. RGB loading was measured separately. Postprocessing is estimated as the non-negative remainder after subtracting model inference and isolated RGB loading from adapter end-to-end time.

## Reproduction

- Script: `tools/run_public_video_4k_validation.py`
- Test: `tests/unit/test_public_video_4k_validation.py`
- Local summary: `artifacts/platform_smoke/public_video_4k_20260711/public_video_4k_validation_summary.json`
- Local derived manifest: `artifacts/platform_smoke/public_video_4k_20260711/public_video_derived_assets_manifest.json`

```powershell
conda run -n osteo-vision python tools/run_public_video_4k_validation.py --output-dir artifacts/platform_smoke/public_video_4k_20260711 --keyframes 3 --native-runs 5 --tiled-runs 3 --memory-iterations 8
```

## Evidence Boundary

OFDVDnet provides ex vivo fluorescence-processing evidence. The PMC video provides a real osteomyelitis-related surgical scene without fluorescence. Enterprise microscope raw dual-channel 4K samples, target-domain intraoperative ICG jaw-osteomyelitis cases, physician keyframe/ROI reference labels, and target-hardware long-duration evidence remain unavailable. Outputs are limited to fluorescence or perfusion signal candidates, risk prompts, uncertainty, and physician-review support.
