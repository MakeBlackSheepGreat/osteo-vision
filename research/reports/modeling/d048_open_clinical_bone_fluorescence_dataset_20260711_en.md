# D048 Open Clinical Bone-Fluorescence Asset Search and Download Report

Date: 2026-07-11

## Outcome

D048 adds 18 traceable original publication figures from seven open-access articles beyond D047. PMC OA metadata and full-text license statements independently confirm CC BY terms for every selected source. Each downloaded file has recorded provenance, dimensions, size, SHA256, and reuse boundaries.

- Human clinical surgery figures: 11.
- Human jaw ORN/MRONJ fluorescence-surgery figures: 2.
- Human oral adjacent-domain fluorescence-surgery figures: 7.
- Human non-jaw infection-debridement figures: 2.
- Large-animal jaw fluorescence proxy figures: 4.
- Fluorescence histopathology reference figures: 3.
- License-compatible weak-label review seeds: 15.
- Engineering panel crops: two, both from human jaw clinical near-domain figures and retained at `review_required`.
- Immediately training-eligible figures: 0.
- Newly located open supplementary videos: 0.

Every source image is a multi-panel publication figure. Two engineering crops now cover the closest human jaw clinical figures. Candidate masks, an `accepted` or `modified` review state, and group-safe splitting remain mandatory. All D048 records retain `training_eligible=false`.

## Artifacts

- Downloader: `tools/download_open_clinical_bone_fluorescence_assets.py`
- JSON manifest: `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.json`
- CSV manifest: `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.csv`
- Raw images: `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/raw/`
- Local visual audit: `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/derived/contact_sheet_20260711.jpg`
- Jaw-panel review updates: `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/jaw_clinical_panel_review_updates_20260711.json`

The manifest records the PMC page, full-text XML, OA API, OA package, image asset URL, local path, license text, image dimensions, file size, SHA256, and download timestamp. Git ignore rules cover `raw/` and `derived/`.

## Included Sources

| Source | Scene | Figures | License | Current role |
|---|---|---:|---|---|
| [PMC9201330](https://pmc.ncbi.nlm.nih.gov/articles/PMC9201330/) | Human jaw osteoradionecrosis fluorescence-guided resection | Figure 1 | CC BY 4.0 | Jaw clinical near-domain seed |
| [PMC11355438](https://pmc.ncbi.nlm.nih.gov/articles/PMC11355438/) | Human maxillary MRONJ with Qray red biofluorescence and pathology correlation | Figures 2 and 5 | CC BY 4.0 | Figure 2 seed; Figure 5 mechanism reference |
| [PMC12829038](https://pmc.ncbi.nlm.nih.gov/articles/PMC12829038/) | Human oral peri-implantitis BIS-guided implantoplasty | Figures 1 and 3-8 | CC BY 4.0 | Oral fluorescence adjacent-domain seeds |
| [PMC8132458](https://pmc.ncbi.nlm.nih.gov/articles/PMC8132458/) | Human septic hip revision with tetracycline fluorescence-guided debridement | Figures 1 and 2 | CC BY 4.0 | Non-jaw infection-debridement seeds |
| [PMC7666678](https://pmc.ncbi.nlm.nih.gov/articles/PMC7666678/) | Mini-pig MRONJ auto-fluorescence and tetracycline fluorescence | Figures 2-5 | CC BY 4.0 | Large-animal jaw proxy seeds |
| [PMC10222433](https://pmc.ncbi.nlm.nih.gov/articles/PMC10222433/) | Mini-pig MRONJ oxytetracycline histology | Figure 15 | CC BY 4.0 | Mechanism reference |
| [PMC12129460](https://pmc.ncbi.nlm.nih.gov/articles/PMC12129460/) | Human MRONJ red-fluorescence histology | Figure 3 | CC BY 4.0 | Mechanism reference |

## Visual Audit

- `PMC9201330_Figure 1` contains exposed jaw bone, pre-resection green fluorescence, post-resection homogeneous fluorescence, and white-light surgical panels.
- `PMC11355438_Figure 2` contains maxillary MRONJ debridement and one Qray red-fluorescence panel. Manual panel cropping is essential.
- The seven `PMC12829038` case figures contain several oral surgical and red/blue-violet fluorescence panels, together with radiographs and follow-up photographs. Only reviewed fluorescence surgical panels may enter a training queue.
- The two `PMC8132458` figures show human infection debridement under white light and ultraviolet excitation. Their non-jaw anatomy requires a low adjacent-domain weight.
- `PMC7666678` combines mini-pig jaw macroscopic, fluorescence, and pathology panels. These records remain preclinical proxies.
- Three pathology reference figures remain excluded from surgical-field segmentation training.

## Training Admission Boundary

Derivative-compatible licensing clears a reuse gate. Medical and labeling gates still apply.

1. Send every multi-panel source to a `review_required` queue.
2. Record panel boundaries and retain genuine fluorescence surgical panels with any matched white-light panel.
3. Preserve `pmcid`, figure label, crop box, and source SHA256 for every crop.
4. Generate candidate regions through a prompt-assisted mask workflow.
5. Admit `accepted` and `modified` items at low weight; route `rejected` items to negatives or error analysis.
6. Keep every source article, case, or original figure in one split only.
7. Suggested initial sampling weights are 0.30 for human jaw clinical figures, 0.15 for oral adjacent-domain figures, and 0.10 for non-jaw infection or large-animal proxy figures.
8. Keep `target_domain_flag=false` until genuine jaw-osteomyelitis white-light/ICG data and physician-reviewed ground truth exist.

## Supplementary Video Audit

The Europe PMC `supplementaryFiles` endpoint was checked for relevant open articles. Available files were PDF, DOCX, XLSX, JPG, and GIF assets. No MP4, MOV, AVI, MPEG, WMV, M4V, or WebM file was present.

No clearly licensed CC BY/CC0 jaw osteomyelitis, ONJ, or MRONJ fluorescence-surgery supplementary video was located. This remains a first-order data risk.

## Excluded or Reference-Only Candidates

| Article | License evidence | Decision |
|---|---|---|
| [10.1016/j.pdpdt.2023.103867](https://doi.org/10.1016/j.pdpdt.2023.103867) | Crossref records CC BY-NC-ND 4.0 | Derivative cropping and training blocked; literature reference only |
| [10.1016/j.pdpdt.2024.104370](https://doi.org/10.1016/j.pdpdt.2024.104370) | Crossref records CC BY-NC 4.0 | Excluded from D048 pending a separate non-commercial-use review |
| [10.1016/j.oooo.2020.10.018](https://doi.org/10.1016/j.oooo.2020.10.018) | Crossref does not provide an open derivative license | No training asset downloaded |
| [10.1016/j.joms.2017.10.024](https://doi.org/10.1016/j.joms.2017.10.024) | Crossref does not provide an open derivative license | No training asset downloaded |

## Medical Boundary

D048 strengthens visual priors for jaw necrosis, oral fluorescence surgery, and infected-bone debridement. Genuine jaw-osteomyelitis paired white-light/ICG video, raw device NIR intensity, physician pixel masks, pathology or culture linkage, and an independent case-level test set remain unavailable. Proxy training metrics support engineering validation and domain-transfer preparation only.
