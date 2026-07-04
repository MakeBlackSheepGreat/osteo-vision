# OFDVDnet Fluorescence Enhancement Baseline Report

## Result

- Processed records: 48
- Source manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\research\literature\inventory\ofdvdnet_video_manifest_20260704.csv`
- Baseline manifest: `C:\Users\876762330\Desktop\projects\osteo-vision\research\literature\inventory\ofdvdnet_fluorescence_baseline_manifest_20260704.csv`
- Output directory: `C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\ofdvdnet\baseline_enhancement`
- Frame position: `0.5`
- Threshold / colormap / alpha: `0.6` / `green` / `0.45`

## Method

The baseline samples the middle frame, crops the top-right fluorescence view and bottom-left reference view, applies Gaussian denoising, percentile normalization, CLAHE contrast enhancement, pseudo-color mapping, and alpha overlay on the reference view.

## Summary Metrics

- Mean positive area fraction: `0.0605206875`
- Mean P95 intensity: `0.6327693333333333`
- Mean intensity: `0.13323664583333333`
- Records with nonzero positive area: `48`

## Medical Boundary

OFDVDnet mock chicken-thigh fluorescence-guided surgery proxy; not jaw osteomyelitis or real intraoperative target-domain data.

This baseline is only for track-1 fluorescence enhancement, pseudo-color stability, and evidence-display validation. It is not jaw-osteomyelitis diagnostic model performance.
