# DeepSeek Brainstorm Reuse Assessment

Date: 2026-07-04

## Source and Bottom Line

Source file: `C:\Users\876762330\Downloads\chat-export-1783173330966.md`.

The brainstorm contains several ideas that can be reused in this project, but they should not be adopted blindly. The reusable core is the competition-oriented software loop: official 4K JPEG/MP4 input, white-light/fluorescence fusion or pseudo-color enhancement, frame-level candidate masks, fluorescence overlay, clinician review, and evidence export. CBCT should remain the preoperative/proxy lesion segmentation and anatomical-prior branch. Tetracycline and bone autofluorescence should support the contrast-agent rationale and boundary-visualization mechanism.

The project should not currently claim clinical-grade intraoperative ICG jaw osteomyelitis video segmentation, wet-lab contrast-agent validation, real VISTA3D/MAISI deployment, or a core strategy based on the 2011 NIR-labeled tetracycline derivative.

## A. Already Reusable

### 1. Official JPEG/MP4 to Segmentation Overlay Loop

The brainstorm repeatedly emphasized MP4 upload, keyframe extraction, segmentation, overlay visualization, and report export. This is already aligned with the project and partially implemented:

- MP4 analysis integration: `backend/src/services/analysis_service.py`
- Keyframe hotspot segmentation outputs: `video_segmentation_manifest_path`, `segmentation_review_video_path`, `mask_review_video_path`
- Export artifacts: `video_segmentation_manifest`, `video_overlay`, `video_mask`
- Report: `research/reports/modeling/jpeg_mp4_hotspot_bridge_20260704_zh.md`

This directly supports the competition sections on multimodal image fusion and AI-assisted interpretation. The current implementation is a heuristic hotspot baseline, not a trained clinical model.

### 2. D025 CBCT Proxy Lesion Model

The brainstorm suggested using CT/CBCT as the realistic data path. This matches the current project direction. The local D025 proxy model already has reportable evidence:

- Validation cases: 53
- Mean Dice: 0.6266
- Mean IoU: 0.5183
- Lesion sensitivity: 0.6756
- Lesion precision: 0.6932

It is suitable as a preoperative CBCT proxy lesion segmentation model and AI interpretation prototype. It should not be described as a real intraoperative ICG video model.

### 3. OFDVDnet Fluorescence Proxy Videos

The brainstorm mentioned fluorescence enhancement and denoising. The project already processed an OFDVDnet baseline:

- Processed video records: 48
- Use: fluorescence view crop, denoising, normalization, CLAHE, pseudo-color, fusion
- Report: `research/reports/modeling/ofdvdnet_fluorescence_baseline_20260704_zh.md`

It can support fluorescence enhancement, pseudo-color stability, and low-SNR processing demonstrations. It is not jaw osteomyelitis data and not a lesion segmentation training set.

### 4. Tetracycline and Bone Autofluorescence

The tetracycline and bone autofluorescence discussion is useful. The project already has a local assessment:

- `research/reports/planning/tetracycline_autofluorescence_value_assessment_20260704_zh.md`
- Local materials include P061, P062, P063, P066, and P068.

These materials can strengthen the contrast-agent section: ICG remains the enterprise baseline and engineering signal, while tetracycline/autofluorescence provides a literature-supported mechanism closer to necrotic-vs-viable bone boundary visualization.

## B. Add to Near-Term Project Tasks

### 1. Minimal MedSAM/SAM2 Interactive Segmentation Loop

MedSAM/SAM2 is relevant. The project now has a 2D prompt-contract fallback for `MedSAMLikeAdapter`, which is the minimal interface before a real MedSAM/SAM2 checkpoint is integrated:

1. Use hotspot candidates or clinician ROI boxes as prompts.
2. Let the MedSAM-like adapter accept `2d_image + bbox/points/roi_hints`.
3. Output mask, overlay, candidates, and quantification.
4. Save clinician review results as future training samples.

This is more realistic than claiming a fully trained target-domain surgical video model. The boundary is that the current fallback is not real MedSAM2 weight inference.

### 2. DentalSegmentator as a CBCT ROI Entry Point

The brainstorm mentioned DentalSegmentator, ToothFairy2, and DentVoxel. The project already has D024/D025/D036, and local reports identify DentalSegmentator as a pretrained anatomical-prior candidate. This update adds `src/preprocess/cbct_roi.py`, freezing its project role as a local contract: anatomy masks for mandible, maxilla, teeth, or mandibular canal can drive CBCT ROI crops and manifests before lesion models operate on the data.

Near-term target:

- Done: a DentalSegmentator-style anatomy-mask-to-ROI contract now writes cropped NPZ files and manifests.
- Pending: download and record the DentalSegmentator checkpoint, license, and source.
- Pending: run it offline on 1-3 public CBCT samples and export mandible/maxilla/teeth/canal masks for downstream D025 or hospital CBCT preprocessing.

### 3. 4K Video Engineering Improvements

The brainstorm correctly identified temporal flicker and the 4K information bottleneck as real engineering gaps:

- Temporal smoothing: smooth mask area, bounding boxes, and connected components across sampled keyframes.
- Patch-based 4K inference: preserve the original 4K image, run ROI/patch inference, and map outputs back to full resolution.

These are more aligned with official 4K JPEG/MP4 input than switching model families immediately.

### 4. 3D Slicer Data Exchange Before a Full Plugin

3D Slicer, SlicerIGT, and 3D printing guides are useful, but a full plugin should not be the short-term mainline. A lighter path is:

- Export CBCT segmentation masks as NIfTI/STL.
- Export lesion boundary and safety margin models.
- Describe the future route to Slicer planning or navigation in the report.

## C. Report-Ready but Not Short-Term Commitments

- nnU-Net v2 / DynUNet high-resolution training: strong next-stage baseline, but should not block the current demo loop.
- VELscope / bone autofluorescence: valuable as a no-dye imaging strategy, not an implemented function yet.
- Domain adaptation and synthetic data: useful future plan, not proof of target-domain performance.
- SlicerIGT, navigation, and 3D printing guides: good extension scenario, not the short-term core.

## D. Use Carefully or Avoid as Core Claims

- The 2011 NIR-labeled tetracycline derivative should only be a forward-looking note, not the core contrast-agent strategy.
- MAISI requires heavy compute and synthetic data cannot replace real jaw osteomyelitis labels.
- VISTA3D is a useful foundation-model reference, but there is no validated adapter/checkpoint path in this project yet.
- Grad-CAM is more natural for classification. For the current segmentation mainline, probability maps, uncertainty maps, candidate provenance, and clinician review state are more appropriate.
- Do not claim clinical-grade real intraoperative MP4 segmentation performance without target-domain MP4/JPEG and clinician keyframe labels.

## Recommended Competition Route

```text
Contrast-agent section:
ICG baseline + tetracycline natural fluorescence / bone autofluorescence evidence + validation plan

Software section:
Official 4K JPEG/MP4 input + white-light/fluorescence fusion + pseudo-color + keyframe hotspot/mask candidates

AI section:
D025 CBCT proxy lesion segmentation + 2D fluorescence hotspot segmentation + MedSAM/SAM2 interactive correction plan

Clinical boundary:
Research/competition prototype only; missing target-domain samples remain a first-order risk
```

## Action List

1. Implement a minimal prompt-based `MedSAMLikeAdapter` interface for bbox-to-mask output. This is now available as a prompt-contract fallback; real MedSAM2 checkpoint integration remains pending.
2. Add temporal smoothing and 4K coordinate remapping notes to MP4 keyframe results. This has been added to backend manifests as `spatial_mapping` and `temporal_stability` metadata without changing the masks.
3. DentalSegmentator now has a local CBCT ROI preprocessing contract; real checkpoint download, license recording, and sample inference remain pending.
4. Move tetracycline and bone autofluorescence into the final technical proposal contrast-agent section.
5. Keep Slicer/navigation/guides as an extension path and first implement NIfTI/STL/JSON exchange.
6. Keep the D025 ConvNeXt-style proxy model as the current runnable mainline while preparing nnU-Net/DynUNet high-resolution baselines.

## Conclusion

The immediately reusable outcome from the brainstorm is not a list of large model names. It is a practical three-part route: tetracycline/autofluorescence for contrast-agent rationale, D025/nnU-Net/DentalSegmentator for CBCT proxy segmentation, and MP4 keyframe hotspot segmentation for the official input-to-output software loop. The project now has MedSAM prompt fallback, a DentalSegmentator-style CBCT ROI contract, and MP4 4K spatial/temporal review metadata. The next useful additions are real checkpoint integration, batch CBCT ROI conversion, and more stable long 4K video outputs.
