# Tetracycline / Bone Autofluorescence Value Assessment

Date: 2026-07-04

## Conclusion

The tetracycline and bone-autofluorescence materials are useful for the contrast-agent rationale and surgical boundary argument, but they are not direct MP4 training data for the current segmentation model.

Given that near-term contrast-agent synthesis and wet-lab validation are difficult, these papers should support the competition report's contrast-agent section: bone-affinity fluorescence, viable-versus-necrotic bone contrast, and autofluorescence-guided jaw necrosis surgery provide a defensible future validation path. The software work should continue to prioritize official MP4/JPEG input, fluorescence fusion, frame-level segmentation, overlay display, physician review, and evidence export.

## Local Materials

The download status is recorded in `research/literature/inventory/tetracycline_mronj_download_status_20260703.md`.

- `P061_2025_tetracycline_fluorescence_MRONJ_scoping_review.pdf`
- `P062_2010_tetracycline_bone_fluorescence_osteonecrosis_pubmed.html`
- `P063_2020_auto_vs_tetracycline_fluorescence_MRONJ_minipig.pdf`
- `P066_2025_autofluorescence_guided_ONJ_histopathology.pdf`
- `P068_2022_fluorescence_guided_surgery_osteoradionecrosis_jaw.pdf`

## Project Use

1. Support the scientific rationale for the contrast-agent design section.
2. Explain why fluorescence-based boundary guidance is relevant to jaw necrosis and related jaw-bone disease workflows.
3. Provide a future validation path for more specific bone-boundary signals while the current software uses ICG-like or proxy fluorescence.

## Limitations

- These materials are not public raw MP4 segmentation datasets.
- MRONJ, ONJ, and ORNJ evidence is adjacent to, but not identical with, jaw osteomyelitis.
- Tetracycline and autofluorescence should be described as literature-supported routes and future validation directions, not as a completed in-house contrast agent.

## Current Recommendation

Use ICG as the near-term engineering baseline for software demonstration. Use tetracycline/autofluorescence evidence to strengthen the contrast-agent chapter and future validation plan. Keep the software deliverable centered on MP4 input, frame masks, fluorescence overlay, candidate review, and evidence export.
