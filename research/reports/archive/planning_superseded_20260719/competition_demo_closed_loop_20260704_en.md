# Competition Demo Closed-Loop Note

## Conclusion

The competition build should prioritize a runnable, reproducible, and deliverable demo workflow rather than another model switch in this cycle. The 2026-07-04 4K proxy demo check passed: the system can ingest official technical-document JPEG/MP4 inputs, fuse white-light and ICG images, analyze MP4 keyframes, create AI candidate regions, record physician review, and export structured evidence.

This workflow is for research, competition, and controlled demonstration only; it is not official competition acceptance. The current demo-check inputs are synthetic proxy data because real intraoperative ICG jaw osteomyelitis MP4/JPEG data and physician ROI annotations are not available. The results are not target-domain clinical performance.

## Official Input Boundary

Based on the official technical document and the project alignment records, the software prioritizes:

- 4K video/image resolution: `3840x2160`.
- Image format: JPEG.
- Video format: MP4.
- Import boundary: USB3.0-exported files or uploaded files.

The demo-check script therefore generates 4K white-light JPEG, 4K ICG JPEG, and 4K MP4 proxy inputs by default, then uses the real FastAPI routes for upload, analysis, review, and export.

The full competition problem statement has higher-priority deliverables: a novel fluorescent contrast-agent design, multimodal medical-image fusion/processing, and AI-assisted microscopic-image interpretation. The software loop below mainly covers the second and third items and does not replace the required contrast-agent design.

## Four Demo Paths

### 1. 4K white-light JPEG + ICG JPEG fusion

Workflow:

1. Create a case.
2. Upload white-light JPEG and ICG JPEG inputs.
3. Attach both inputs to the same case.
4. Run pseudo-color enhancement, background subtraction, lightweight registration, fusion, heatmap generation, and ROI mask generation.
5. Export overlay, heatmap, normalized fluorescence, colorbar, ROI mask, and quantitative summary.

Competition value: multimodal medical-image fusion and processing.

### 2. 4K MP4 upload, keyframe extraction, pseudo-color enhancement, and hotspot candidates

Workflow:

1. Upload an MP4 file.
2. Extract video metadata and keyframes in the backend.
3. Run `fluorescence_hotspot_2d_segmenter` on keyframes.
4. Export keyframes, timeline manifest, frame detail manifest, and candidate regions.

Competition value: official MP4/JPEG microscope output entering an AI-assisted candidate-region workflow.

### 3. Physician review of candidate regions and ROIs

Workflow:

1. Read candidate regions from an analysis run.
2. Mark the first candidate as `accepted`.
3. Create an ROI from the candidate.
4. Record a review event.
5. Preserve review summary, review events, and ROI state in the exported report.

Competition value: AI output is presented as overlay hints, risk labels, or decision support, then remains subject to physician review.

### 4. Export JSON, CSV, Markdown, DICOM Secondary Capture, and ZIP evidence bundle

Workflow:

1. Call the case export API.
2. Generate a structured JSON report.
3. Generate a Markdown report.
4. Generate quantification CSV.
5. Generate DICOM Secondary Capture.
6. Generate bundle manifest and evidence bundle ZIP.

Competition value: structured evidence and traceable export for the software platform. The full competition statement does not list DICOM/remote collaboration as a core deliverable. The current DICOM artifact is Secondary Capture only, not DICOM SR/SEG and not a clinical diagnostic object.

## Mainline Model Decision

The current mainline remains:

| Entry | Model/rule | Status | Use |
|---|---|---|---|
| `npz_roi` | `convnext3d_d025_proxy_segmenter` | Available | D025 CBCT lesion ROI proxy segmentation for engineering validation |
| `2d_image` / MP4 keyframe | `convnext2d_keyframe_proxy_segmenter` | Available | Trainable 2D ConvNeXt-style proxy segmentation for JPEG/MP4 keyframe masks, pseudocolor, and overlays; configurable patch/tiling inference is enabled for 4K safety |
| `2d_image` / MP4 keyframe fallback | `fluorescence_hotspot_2d_segmenter` | Available | 2D fluorescence hotspot heuristic fallback and interpretable comparison |
| Compatibility entry | `d025_lesion_smoke_segmenter` | Available | Smoke-compatible entry for the same D025 proxy checkpoint |
| Comparison model | `d025_monai_segresnetds.pt` | Not wired into mainline | Modeling evidence only |

`SegResNetDS` is not wired into `configs/inference/osteo_vision.yml`. The comparison report shows lower Mean Dice and Mean IoU than the ConvNeXt-style baseline on the current D025 64-cubed proxy cache. The 2D keyframe model is now wired into the MP4 path, but it remains a synthetic/pseudo-labeled proxy and must not be reported as target-domain clinical performance. The next modeling step should be nnU-Net v2 or DynUNet high-resolution/patch-level training, without blocking the current demo workflow.

## Demo-Check Command

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

Optional small smoke run:

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py --width 320 --height 180 --frames 3 --keyframes 2 --fps 3 --output-dir .pytest_tmp\competition_demo_check_smoke
```

Default output directory:

```text
artifacts/platform_smoke/competition_demo_check_*
```

## 2026-07-04 Demo-Check Result

The default 4K demo-check command was executed:

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

Historical check summary:

- Historical run directory: `artifacts/platform_smoke/competition_acceptance_20260704T111303Z`
- Case ID: `case_c01a9b9dbf`
- JPEG fusion: passed.
- MP4 keyframe analysis: passed.
- Physician review event: recorded, candidate converted to ROI.
- Evidence bundle: generated.
- Required formats present: `report_json`, `report_md`, `dicom_secondary_capture`, `quantification_csv`, `bundle_manifest`, `evidence_bundle`, `overlay`, `heatmap`, `roi_mask`, and `keyframe`.
- Mainline models: `convnext3d_d025_proxy_segmenter` and `fluorescence_hotspot_2d_segmenter` are available.
- Medical boundary: research/competition disclaimer is included and `clinical_claim_allowed=false`.

## Current Gaps

- Real intraoperative ICG jaw osteomyelitis MP4/JPEG remains unavailable.
- Physician keyframe, ROI, and case-level labels remain unavailable.
- The video path validates engineering workflow, not target-domain diagnostic performance.
- Current DICOM output is Secondary Capture, not DICOM SR/SEG; DICOM/remote collaboration is an extension, not a core deliverable in the full competition statement.
- The full competition statement requires a novel fluorescent contrast-agent design, and the current project still lacks independent experimental or validation data for that item.
- `nnunet_v2_osteo_baseline` and `biomedclip_osteo_screening` still lack runnable checkpoints or adapter inference.
- `medsam2_osteo_promptable` now has a 2D prompt-contract fallback that can turn ROI/bbox/point prompts into review masks, but it still lacks a real MedSAM2 checkpoint and must not be reported as real MedSAM2 inference performance.

## Next Preparation

1. Keep this closed loop as the competition demo mainline.
2. Prepare nnU-Net v2/DynUNet high-resolution or patch-level training in parallel.
3. Continue searching traceable fluorescence surgery videos, osteomyelitis/osteonecrosis videos, and paper supplementary videos, while marking all non-target-domain data clearly.
4. If the hospital can only provide 4-5 CBCT cases, use them for demo calibration, case narrative, and expert feedback rather than standalone high-performance training.
5. Treat DICOM SR/SEG mapping as an extension so it does not displace the three core deliverables: contrast-agent design, dual-channel fusion, and AI interpretation.

## References

- `research/literature/inventory/official/competition_official_technical_document_20260527.pdf`
- Local ignored competition problem PDF: `HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf`
- `research/reports/planning/official_technical_document_alignment_zh.md`
- `specs/001-software-platform-target/plan.md`
- `docs/export_schema_v1.md`
- `research/reports/modeling/model_checkpoint_manifest_20260704_en.md`
- `research/reports/modeling/d025_proxy_model_comparison_20260704_en.md`
- `tools/run_competition_flow_demo_check.py`
