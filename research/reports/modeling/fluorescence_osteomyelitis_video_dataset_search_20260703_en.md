# Supplemental Search for Fluorescence Surgery and Osteomyelitis Video Datasets

Date: 2026-07-03

## Conclusion

No directly usable public “jaw osteomyelitis ICG fluorescence surgery MP4 dataset” was found in this search. The usable public evidence falls into three groups:

1. **Downloadable fluorescence surgery video datasets**: mostly mock or non-oral scenes. Useful for denoising, enhancement, false-color stabilization, and MP4 workflow validation.
2. **Bone/infection/osteomyelitis ICG clinical studies**: medically relevant, but the public material is generally papers, trial protocols, figures, or supplements rather than raw downloadable MP4 videos.
3. **Jaw osteonecrosis / jaw osteomyelitis fluorescence-guided surgery literature**: anatomically close, but mostly autofluorescence, tetracycline/minocycline fluorescence, or VELscope studies; raw videos are not openly available.

The project should not depend on finding an open jaw osteomyelitis fluorescence MP4 dataset. The practical route is to use public FGS videos for competition point 1 and video processing, use bone/infection ICG studies as medical rationale, and use CBCT-derived pseudo-videos plus public CBCT datasets for competition point 2 prototype training.

## Candidate Ranking

| Rank | Source | Availability | Content | Project use | Limitation |
|---|---|---|---|---|---|
| A | Dryad FGS video denoising dataset | Downloadable, 34 GB | ICG mock chicken thigh surgery, low-dose ICG, no-ICG leakage, calibration data, models | Best public video proxy for denoising/enhancement/false-color workflow | Not oral, jaw, bone infection, or osteomyelitis |
| A | OFDVDnet Dryad dataset | Downloadable, around 50 videos / 100 minutes | Mock fluorescence-guided surgery with reference, fluorescence, overlay views | White-light/fluorescence/overlay pipeline and denoising baseline | Mock data, not disease data |
| B | NCT04245111 fracture-infection ICG study | Clinical protocol, no open videos found | Bone/soft-tissue perfusion, infection, osteomyelitis debridement, 4-minute video-rate acquisition | Strong rationale; possible author-contact target | No public raw MP4 dataset found |
| B | NSTI ICG fluorescence study | Open paper, no raw video found | 14 infection cases including one osteomyelitis case; white-light and ICG snapshots, maps, ROI/SBR | Useful perfusion-defect evidence for infection | Not jaw; no raw video data |
| B | ICG bone perfusion systematic review | Open paper | Reviews bone perfusion ICG evidence | Supports medical boundary and recording protocol | Not a dataset |
| C | MRONJ/ORNJ fluorescence-guided surgery | Papers/abstracts | Jaw osteonecrosis, autofluorescence/tetracycline/VELscope | Closest jaw surgical boundary literature | Usually not ICG; data not openly downloadable |

## Recommended Next Actions

1. Download Dryad `10.5061/dryad.8gtht76x9` and `10.5061/dryad.v6wwpzh3w` into ignored local data storage.
2. Implement a triple-view splitter to extract reference, fluorescence, and overlay videos.
3. Generate cine MP4 videos from D025 and the 4-5 available hospital CBCT cases.
4. Create `video_dataset_candidate_inventory.csv` with modality, ICG status, bone/infection relevance, oral relevance, downloadability, training value, and demo-only flags.
5. Reframe competition point 2 as “CBCT lesion proxy + ICG video perfusion/enhancement proxy + physician review” rather than real ICG osteomyelitis segmentation.

## References

- Dryad FGS video denoising dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9
- OFDVDnet Dryad dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.v6wwpzh3w
- OFDVDnet code: https://github.com/WillianJrLin/OFDVDnet
- OFDVDnet paper: https://proceedings.mlr.press/v227/seets24a.html
- Video Denoising in Fluorescence Guided Surgery: https://arxiv.org/abs/2411.09798
- NCT04245111 protocol: https://clinicaltrials.gov/study/NCT04245111
- NCT04245111 PDF protocol: https://cdn.clinicaltrials.gov/large-docs/11/NCT04245111/Prot_SAP_000.pdf
- NSTI ICG fluorescence study: https://pmc.ncbi.nlm.nih.gov/articles/PMC11092151/
- Bone perfusion ICG systematic review: https://www.mdpi.com/2075-1729/12/2/154
- ORNJ fluorescence-guided surgery: https://journals.sagepub.com/doi/abs/10.1177/03000605221104186
- DCSO mandible VELscope paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC4628814/

## Non-Jaw Osteomyelitis Video Supplement

After broadening the search beyond jaw osteomyelitis, several open PMC surgical or imaging videos were found. These are not curated training datasets, but they are useful for MP4 ingestion, keyframe extraction, workflow demonstration, and small prototype experiments.

| Source | Scene | Video status | Project value | Limitation |
|---|---|---|---|---|
| Surgical Debridement for Acute and Chronic Osteomyelitis in Children | Pediatric acute/chronic osteomyelitis debridement | Multiple downloadable MP4 supplements | Best open osteomyelitis surgical video material found | No ICG, no segmentation labels, mostly long bones |
| Biportal Endoscopic Intramedullary Debridement for Management of Tibial Osteomyelitis | Tibial osteomyelitis endoscopic debridement | Downloadable `mmc1.mp4` | Highly relevant to bone infection debridement | Single technique video, no labels |
| Phalangeal Reaming and Irrigation for Thumb Osteomyelitis | Small-bone thumb osteomyelitis | Downloadable `mmc1.mp4` | Small-bone infection reference | No ICG or jaw data |
| Calcaneal Osteomyelitis with Pseudoarthrosis | Calcaneal osteomyelitis reconstruction | Downloadable MP4 supplement | Bone infection reconstruction reference | Not a diagnostic dataset |
| Tuberculous Osteomyelitis of the Maxilla | Maxillary osteomyelitis case | Two FLV supplements | Closest jaw-related osteomyelitis video found | FLV format, no ICG, case report |
| Mucormycotic Osteomyelitis after ACL Reconstruction | Fungal osteomyelitis | Three MP4 supplements | Bone infection video material | Non-oral |
| Abscess Pulsatility Sign of Osteomyelitis | Ultrasound osteomyelitis sign | Downloadable MP4 supplement | Diagnostic video reference | Ultrasound, not surgical/fluorescence video |

Priority pages:

- Pediatric osteomyelitis debridement: https://pmc.ncbi.nlm.nih.gov/articles/PMC10807896/
- Tibial osteomyelitis endoscopic debridement: https://pmc.ncbi.nlm.nih.gov/articles/PMC12350196/
- Thumb phalangeal osteomyelitis: https://pmc.ncbi.nlm.nih.gov/articles/PMC12147590/
