# Fluorescence Jaw Osteomyelitis Intraoperative Video Segmentation Anchor Report

Date: 2026-07-06

## Executive Position

The near-term task should not be framed as automatic jaw osteomyelitis lesion segmentation. With no target-domain intraoperative ICG jaw osteomyelitis videos and no physician pixel-level annotations, the implementable framing is:

> intraoperative video segmentation = exposed bone segmentation + fluorescence/perfusion signal segmentation + temporal stability analysis + boundary-risk prompting + physician review.

The platform should output interpretable masks and risk layers, not a disease-final mask.

## Anchored Mask Taxonomy

| Mask | Meaning | Near-term path |
|---|---|---|
| `exposed_bone` | exposed or suspected bone surface | SAM2/MedSAM2-assisted annotation plus review |
| `soft_tissue` | surrounding soft tissue | assisted annotation, later training |
| `instrument_or_occlusion` | surgical tools, smoke, glare, occlusion | quality warning first, model later |
| `fluorescence_hotspot` | high fluorescence signal | current hotspot and D046 proxy route |
| `hypo_fluorescent_bone` | weak or absent fluorescence within exposed bone | bone gate plus fluorescence branch |
| `boundary_risk` | suspicious transition/risk zone | fusion of bone, fluorescence and temporal features |
| `uncertain` | low-confidence or low-quality region | confidence, empty-mask and over-segmentation triggers |

## Five-Layer Route

1. Segment video signals, not final disease labels.
2. Keep the ConvNeXt keyframe route, but upgrade it into a dual-branch design.
3. Use SAM2/MedSAM2 for assisted annotation and video propagation rather than fully automatic clinical inference.
4. Use OFDVDnet/FGS ideas for reference-guided denoising, temporal smoothing and leakage correction.
5. Use D025/D024/D036 as preoperative priors and report-level evidence, not as intraoperative video ground truth.

## Model Contract

The current `convnext2d_keyframe_proxy_segmenter` should evolve from a single RGB/keyframe predictor into a dual-branch model:

- white-light texture branch;
- fluorescence intensity branch;
- pseudo-color overlay branch;
- quality/occlusion branch.

Expected outputs:

- `bone_gate_mask`;
- `fluorescence_signal_mask`;
- `risk_mask`.

This is more defensible than directly predicting an osteomyelitis mask from proxy videos.

## First Implementation Stage

1. Build a new D046 manifest with reference/white-light, fluorescence, overlay, keyframes, timestamps and quality metrics.
2. Train `fluorescence_signal_mask` first: hotspot, hypo-fluorescent area, leakage/noise area.
3. Use SAM2/MedSAM2 to annotate 50-100 keyframes for `exposed_bone`, occlusion, soft tissue and boundary candidates.
4. Train the dual-branch keyframe model.
5. Use keyframe-based MP4 inference plus temporal propagation/smoothing to generate review videos.
6. Show original video, segmentation overlay and risk/uncertainty map in the frontend.
7. Report fluorescence perfusion/activity risk prompts, not automatic disease boundaries.

## Data Anchors

| Data | Role |
|---|---|
| D046 OFDVDnet/FGS proxy videos | fluorescence video quality, pseudo-color, MP4 workflow and keyframe segmentation |
| D046 osteomyelitis PMC videos | non-fluorescence surgical/diagnostic reference, not ICG ground truth |
| D025 DOLCHID | CBCT lesion proxy segmentation |
| D024 DentVoxel | jaw/tooth/canal anatomical prior |
| D036 ToothFairy2 | dental CBCT multi-structure prior |

## Success Criteria

- Official-boundary MP4/JPEG inputs can run through the pipeline.
- Each keyframe produces mask, probability map, overlay, risk map and quality metadata.
- Playback can synchronize the nearest keyframe analysis result.
- Review states can be saved and converted into weighted training manifests.
- Reports preserve the ICG, proxy-data and pseudo-label boundaries.
- 4K tiled inference is stable and empty-mask fallback remains available.

## Medical Boundary

ICG reflects perfusion, vascular permeability and tissue activity. It is not a jaw osteomyelitis-specific probe. Current D046 metrics are public/proxy/pseudo-label validation evidence and must not be described as clinical performance on target-domain intraoperative jaw osteomyelitis ICG videos.

## First Implementation Landing Status

- MP4/JPEG keyframe outputs now use the `video_signal_segmentation` contract with `bone_gate_mask`, `fluorescence_signal_mask`, `risk_mask` and `uncertain_mask`.
- A D046 video signal segmentation manifest has been generated from 20 public videos and 100 keyframe samples, with source links, local video paths, timestamps, quality status and mask type fields.
- Risk maps, uncertainty masks, review sample weights and the video segmentation manifest are wired into backend outputs, report export and frontend synchronized analysis.
- `bone_gate_mask` remains a pending-review slot and is not fabricated without physician or SAM-assisted annotation.
