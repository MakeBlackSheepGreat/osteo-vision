# Static Near-Domain Dual-Channel Stress Evaluation

Generated: 2026-07-11T06:12:31.897178+00:00

## Summary

- Publication-derived near-domain white-light/fluorescence pairs: 6.
- Pair alignments: {"approximate_view": 6}.
- Registration probe: {"pass": 2, "weak": 4}.
- Risk flags: {"context_fusion_low_white_sensitivity": 6, "intermediate_fusion_high_disagreement": 6, "pair_registration_unreliable": 4}.
- Checkpoint SHA256: `0dd4d47f09b0a760f464619f20fdc402493d8bb62b2cfac02acb14ebff8fa397`.
- The dual-channel checkpoint remains `runtime_allowed=false`; this run is an offline stress evaluation.

## Method

Each pair is evaluated with white-only, fluorescence-only, early-fusion, intermediate-fusion, and context-fusion modes. Context fusion uses global white-light context to avoid pixel-alignment dependence. The report records probability statistics, positive-area fractions, entropy, and cross-mode disagreement. ORB/RANSAC homography is used only as a feasibility probe for approximate-view pairs. Sequential pairs skip pixel registration.

## Boundary

These pairs replace synthetic white-light inputs in the stress test and expose near-domain failure modes. Context fusion differs from fluorescence-only output by 0.0013 on average; this indicates alignment stability and possible low white-light sensitivity. It does not demonstrate a causal dual-channel benefit. The pairs have no pixel disease masks and cannot provide Dice, IoU, boundary error, or clinical performance evidence. Publication annotations may create shortcut features and require later occlusion augmentation and authorized review.
