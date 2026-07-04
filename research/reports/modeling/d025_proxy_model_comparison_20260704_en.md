# D025 Proxy Segmentation Model Comparison

## Conclusion

The main checkpoint should not be switched from the ConvNeXt-style 3D proxy segmenter to MONAI SegResNetDS at this stage. This round continued training from the original ConvNeXt-style checkpoint for 1500 additional batches and promoted the improved candidate to the local `d025_lesion_smoke.pt` mainline checkpoint.

Under the same D025 CBCT lesion ROI 64 cubed cache, 209 training cases, and 53 validation cases, SegResNetDS underperforms the current ConvNeXt-style baseline on Mean Dice and Mean IoU. The continued ConvNeXt-style mainline now reaches Mean Dice 0.6567, Mean IoU 0.5553, and Mean HD95 15.2370. For the competition demo, the ConvNeXt-style path remains the more stable mainline choice.

## Comparison

| Model | Params | Train Batches | Best Threshold | Mean Dice | Mean IoU | Mean HD95 | Mean NSD | Sensitivity | Precision | Recommendation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt-style 3D U-Net proxy continued | 198,698 | 4500 | 0.20 | 0.6567 | 0.5553 | 15.2370 | 0.4797 | 0.6900 | 0.7238 | Promoted as local mainline |
| ConvNeXt-style 3D U-Net proxy previous | 198,698 | 3000 | 0.20 | 0.6266 | 0.5183 | 17.6413 | 0.4227 | 0.6756 | 0.6932 | Previous mainline backup |
| MONAI SegResNetDS | 3,154,514 | 3000 | 0.20 | 0.5741 | 0.4766 | 13.8795 | 0.4101 | 0.5721 | 0.7128 | Keep as comparison baseline |

## Artifacts

- Continued ConvNeXt-style evaluation: `research/reports/modeling/d025_continue_1500_eval_20260704/d025_proxy_model_evaluation_20260704_en.md`
- ConvNeXt-style mainline report: `research/reports/modeling/d025_lesion_smoke_model_20260704_en.md`
- SegResNetDS training report: `research/reports/modeling/d025_monai_segresnetds_training_20260704_en.md`
- SegResNetDS checkpoint: `artifacts/checkpoints/osteo_vision/d025_monai_segresnetds.pt`
- SegResNetDS failure previews: `research/reports/modeling/assets/d025_monai_segresnetds_20260704T094021Z/`

## Next Steps

1. Keep the continued `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt` as the mainline checkpoint.
2. Do not wire SegResNetDS into `configs/inference/osteo_vision.yml` yet; keep it as modeling evidence.
3. The next training round should prioritize nnU-Net v2/DynUNet high-resolution or patch-level training instead of stacking more lightweight models on the 64 cubed proxy cache.
4. Reports must continue to state that D025 is CBCT lesion-mask proxy data, not target-domain intraoperative ICG jaw osteomyelitis data.
