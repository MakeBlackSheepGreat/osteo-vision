# D047 PMC Jaw-Fluorescence Dataset Closure Report

## Result

- Source articles: four open-access PMC articles.
- Downloaded images: ten, each with a source page, direct asset or archive URL, license, SHA256, and local path.
- Static human-review candidates: eight CC BY figures.
- Reference-only figures: two, including one CC BY-NC-ND clinical figure and one mechanism schematic.
- Target-domain records: zero.
- Engineering panel crops: seven, all retained at `review_required`.
- Physician pixel annotations: zero; training candidates: zero.

## Dataset Value

The figures cover mandibular chronic sclerosing osteomyelitis, ONJ/MRONJ bone exposure, bone resection, autofluorescence or VELscope inspection, and selected histopathology relationships. Their disease and anatomy conditions are closer to the project target than the ex-vivo chicken-thigh fluorescence videos.

Every source is a multi-panel publication figure. Seven fluorescence-panel engineering crops now exist, no pixel mask is generated, and no raw source figure directly enters segmentation training.

## License And Training Gates

- `weak_label_training_seed_with_attribution`: routed to human review with `review_required` and `training_eligible=false`.
- `reference_only_no_derivatives`: permanently excluded from crops, derivatives, and training.
- `literature_reference_only`: retained for mechanism discussion and manual reference.
- Weak-seed priority uses `sampling_weight=0.25`; review confidence retains the common `sample_weight=1.0` contract.

After panel cropping and prompt-mask creation, a record still requires accepted or modified review, source-group splitting, license validation, and training admission before it can become a training candidate.

## Quality Gate

All ten D047 images are registered as `near_domain`, `unlabeled` source assets. The updated registry contains 403 records and passes its quality gate:

- `near_domain`: 46 records.
- `training_eligible`: 301 records; D047 raw multi-panel figures are excluded.
- License-verification warnings: 23, all on public source records excluded from training.
- Image and training-label SHA256 values were recomputed for all 403 records with zero quality errors.
- Target-domain records remain zero, so all current metrics remain non-target-domain engineering evidence.

## Visual Review

The contact sheet was inspected. The eight review candidates contain jaw surgical fields, bone resection, autofluorescence, or pathology-correlated panels. The CC BY-NC-ND clinical figure and the schematic are excluded from the review seed queue.

## Reproduction

```powershell
conda run -n osteo-vision python tools/download_pmc_jaw_fluorescence_figures.py
conda run -n osteo-vision python tools/build_pmc_figure_review_seed.py
conda run -n osteo-vision python tools/build_layered_dataset_registry.py
```

## Boundary

D047 improves target-condition-near coverage. Real intraoperative ICG jaw-osteomyelitis MP4/JPEG, synchronized raw white-light/NIR channels, physician pixel labels, and pathology or culture linkage remain unavailable. Publication figures cannot support target-domain clinical performance claims.
