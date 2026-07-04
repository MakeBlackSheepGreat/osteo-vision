# D025 Proxy Segmenter Continued-Training Promotion

## Conclusion

The original `d025_lesion_smoke.pt` mainline checkpoint was continued for 1500 additional batches, and the improved candidate has been promoted to the local mainline checkpoint. This improvement only applies to the D025 CBCT lesion ROI 64-cubed proxy data and is not target-domain intraoperative ICG jaw osteomyelitis performance.

## Training Setup

- Resume source: `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- Continued candidate: `artifacts/checkpoints/osteo_vision/d025_candidate_continue_20260704/d025_lesion_continue_1500.pt`
- Current mainline: `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
- Previous mainline backup: `artifacts/checkpoints/osteo_vision/d025_candidate_base12/d025_lesion_smoke_before_continue_20260704.pt`
- Training data: D025 DOLCHID CBCT lesion ROI 64-cubed cache.
- Train cases: 209; validation cases: 53.
- Continued-training batches: 1500; total training batches: 4500.
- Learning rate: 0.0002; batch size: 2; device: CUDA.

## Metric Comparison

| Model | Train Batches | Best Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Continued ConvNeXt-style mainline | 4500 | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.4797 | 0.6900 | 0.7238 | Promoted |
| Previous ConvNeXt-style mainline | 3000 | 0.20 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 | Backed up |
| MONAI SegResNetDS comparison | 3000 | 0.20 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 | Not wired into mainline |

## Decision

The continued candidate improves Mean Dice, Mean IoU, Mean HD95, Mean NSD, sensitivity, and precision over the previous ConvNeXt-style mainline, so local promotion is justified. SegResNetDS still has boundary-distance comparison value, but its Dice/IoU and sensitivity remain insufficient for mainline wiring.

## Boundary

- The model remains a CBCT lesion ROI proxy segmenter, not an intraoperative ICG video/JPEG model.
- The validation set is D025 proxy data and must not be extrapolated to clinical diagnostic performance.
- The competition demo must keep physician review and research-prototype disclaimers.

## Next Steps

1. Keep the continued `d025_lesion_smoke.pt` as the local competition-flow mainline checkpoint.
2. Prioritize nnU-Net v2/DynUNet high-resolution or patch-level training next.
3. If more 64-cubed D025 training is attempted, write to an isolated candidate output and promote only after evaluation.
