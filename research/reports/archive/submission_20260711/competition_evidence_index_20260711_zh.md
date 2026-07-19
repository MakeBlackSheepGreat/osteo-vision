# 参赛工程证据索引

生成时间：2026-07-11T02:28:52.497269+00:00

## 官方要求

- 赛题编号：HT-202604
- 核心内容：新型荧光造影剂设计、白光/荧光多模态融合与处理、AI 辅助显微成像判读。
- 设备边界：3840×2160、USB3.0、JPEG、MP4。

## Git 状态

- 分支：`main`
- 提交：`3e780e306c959ff4795773a64de9985d1a80a510`
- 工作区条目：127

## 模型清单

| model_id | family | enabled | runtime_allowed | checkpoint | SHA256 | 用途边界 |
|---|---|---:|---:|---:|---|---|
| convnext3d_d025_proxy_segmenter | convnext3d_segmenter | True | True | True | `3b6cd68118626d6204f091295c563b7175773959a583269af3cdfb2c94a08a34` | ConvNeXt-style 3D CBCT lesion ROI proxy segmentation for engineering validation |
| fluorescence_hotspot_2d_segmenter | fluorescence_hotspot_segmenter | True | True | False | `-` | heuristic 2D fluorescence hotspot mask for JPEG/keyframe platform validation evidence |
| convnext2d_keyframe_proxy_segmenter | convnext2d_keyframe_segmenter | True | True | True | `34cc08f1330c6eed1ee051c6f1318702afb6015a1ef7ce92ad92d9e90b35206b` | trainable 2D JPEG/MP4 keyframe segmentation proxy for engineering validation |
| convnext2d_video_signal_multimask_v2_grouped | video_signal_multimask | True | True | True | `3a4cd7e9bd6eb22275be4ebdf2ae667eed2f06cda8850445d0337d7c4eb0e90a` | optional fluorescence-signal and bone-gate multi-mask candidate for engineering validation |
| dual_channel_proxy_ablation_segmenter | dual_channel_segmenter | True | False | True | `0dd4d47f09b0a760f464619f20fdc402493d8bb62b2cfac02acb14ebff8fa397` | white-light and fluorescence proxy fusion segmentation for engineering validation |
| d025_lesion_smoke_segmenter | d025_lesion_segmenter | True | True | True | `3b6cd68118626d6204f091295c563b7175773959a583269af3cdfb2c94a08a34` | engineering smoke model for CBCT lesion ROI proxy segmentation |
| nnunet_v2_osteo_baseline | nnunet_v2 | True | True | False | `-` | jaw osteomyelitis segmentation baseline |
| medsam2_osteo_promptable | medsam_like | True | True | False | `-` | promptable lesion or necrotic bone ROI segmentation contract; fallback is not real MedSAM2 checkpoint inference |
| biomedclip_osteo_screening | vlm_encoder | True | True | False | `-` | auxiliary image-level screening platform workflow |
| fixture_default | fixture | True | True | False | `-` | deterministic fallback for tests and demos |

## 关键证据文件

| 路径 | 存在 | SHA256 |
|---|---:|---|
| `research/reports/planning/official_competition_problem_alignment_20260704_zh.md` | True | `54e4639c54603a3424529aa4967ca2f925722f2fdf039334d5b7c3ee1e74b7d7` |
| `research/reports/modeling/r01_r08_remediation_20260710_zh.md` | True | `ff5735960fbae384ec9bcef8381c595d547c824404fc08ec3abf2042d04f1c82` |
| `research/reports/modeling/keyframe_convnext2d_proxy_segmenter_20260710_grouped_zh.md` | True | `752bc0bd3eb944dc314e2f40399e775f0e85c76efffaa229675c08a102bd9d5a` |
| `research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/keyframe_threshold_eval.json` | True | `263eea400b219aac4478a92ec2f80d9fc79c99c0e1d6024882563afe06a414d4` |
| `research/reports/modeling/dual_channel_ablation_20260710_dual_channel.json` | True | `39bad55bf4572b228a27a81793fdbce5ba9ca0aac5832a88cc74b11e8db38445` |
| `research/reports/modeling/video_signal_multimask_v2_training_20260710_multimask_v2_grouped.json` | True | `578748222876359176b8a99c40fac75a3b08a52bf9f320a7044b07de21c4f809` |
| `research/reports/modeling/public_video_4k_validation_20260711_zh.md` | True | `384c749ba451879cf642782f92d2200f4fe1baf4a823db6e8dbba99d48bda681` |
| `research/reports/modeling/public_video_dynamic_quantification_20260711_zh.md` | True | `57e4788a06973f795b6c8f8fd770b062fcee532a3ca65c40cebc1dbc8f74e0d5` |
| `research/reports/modeling/layered_dataset_registry_quality_20260711_zh.md` | True | `667a262e1cc4a2e57b7bbecc4b1e7506d624a95b93502569c5be39835a91225f` |
| `research/reports/modeling/video_active_review_queue_20260711_zh.md` | True | `ff3cd0c4225795c272b451a5e8ad9aab6cdd49d92d0abebbc26822ccd9f2bb7e` |
| `research/reports/modeling/d047_pmc_jaw_fluorescence_dataset_20260711_zh.md` | True | `31e6019e5323c836d3d80e6320b455e52b4d6bbcabdf599dec0ed7f8d9a356ce` |
| `research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/pmc_jaw_fluorescence_figure_manifest.json` | True | `69985f75c88263a66bfc207ba9e7d06cab666c0f5fc74636788a41021e793e5e` |
| `research/reports/modeling/d048_open_clinical_bone_fluorescence_dataset_20260711_zh.md` | True | `e3ea7254355326b20b53a7e2126a628fad51abf1435a3cbeff050edf4a0714c0` |
| `research/reports/modeling/live_stream_and_static_review_20260711_zh.md` | True | `00783c63c8b254d6cd8a1e3077a4342bd3707df7fae91e3ca8a6b4ab17160f2d` |
| `research/reports/modeling/static_panel_crop_suggestions_20260711_zh.md` | True | `e8b26e0c58db426aab84c69dbaa9d551b2c6c181d3364b47219d74b4aa856fea` |
| `research/datasets/public-candidates/d047_d048_static_figure_seed_manifest.json` | True | `44f5be1c68bc432c8a4387f3d0822322c72ecab251b5c8ebf57c55a2b85e8290` |
| `research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json` | True | `d777165551affb031cabcaa713e41d2aaf836d1ab67723cbd5c5c906c62c0866` |
| `research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/mp4_keyframe_segmentation_proxy_20260710_grouped/keyframe_segmentation_proxy_manifest.csv` | True | `83595ff78bef467821ab60107a189135a2e801472cd93f3836c3ba5ea5257b05` |
| `research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.json` | True | `21216d7c683885f97d3c7396ea1a62223aba92aae52a35609b43c204bcdc7cf8` |
| `backend/src/services/active_review_queue.py` | True | `d345b1745a2c80c81b668c6a85967ff25af29d569c00259998871f805a8e2339` |
| `tools/build_keyframe_training_manifest_from_review.py` | True | `5e74a5e6c82d255e0906267c47ff1505d5fc1eb105e63c87edd2cc30b4786eeb` |
| `src/datasets/training_admission.py` | True | `689a13da0c20a1fc5712a4b9430b5ff0036dc1fb04246b9f64ae4227beb459a2` |
| `src/io/live_stream.py` | True | `6b99daf776c23a74ad58204bbc4a7644005774d8ff68472f947156fd2b17e882` |
| `tests/smoke/test_live_stream_analysis.py` | True | `1787eaff33a5f835d3ba3aba208c176ee4c1cba63907209497a95ac89c325456` |
| `backend/src/services/static_dataset_review.py` | True | `8f8e34de30a4c23882bd35543fffbe2ea22c48f4218a6ef5ce2193f46d8e75a8` |
| `src/datasets/static_panel_detection.py` | True | `3ed2969c03c6b228d53fca27815dcf6514021a9e0fba9cf29509b93460e10ff7` |
| `tools/build_static_panel_crop_suggestions.py` | True | `6fcc5441dba106baf920b90f5ce841f91b3a56457976c33ae375d858ca68935c` |
| `tools/generate_static_review_seeds.py` | True | `0ff090a956b5cf68cd9e3b3cacc165bd31f1d17bbd4fedab84912adfd7e9302c` |
| `frontend/src/components/StaticCropEditor.vue` | True | `175fea745d35274e964cf0eacb13674a2774d2bd810338e74dc57ace3f90e1e2` |
| `frontend/src/pages/DatasetReviewPage.vue` | True | `f362fde44c9df7b4f7b64d17c34d6559feb2a32dbd466b5cc316ac261b82cd52` |
| `artifacts/data_review/static_seed_batch_20260711.json` | True | `5b3cca485a0f3d0785bd995a12e2ca88cee296e167714ef82a1f86797629458d` |
| `artifacts/platform_smoke/dataset_crop_review_ui_20260711.png` | True | `5b0589f53f1d3607fc7a04b87108c7c441ad75cfc5aa062ee32980b7d4a9d18c` |
| `artifacts/data_review/d047_d048_52_crop_suggestions_contact_sheet.jpg` | True | `d467528210270b9cabd6c21255cf7b98b1617745137acf94028e79629e27bafd` |
| `artifacts/platform_smoke/dataset_crop_suggestions_ui_20260711.png` | True | `bc968b7477d6fe15a8831e901c24d21a1b06b4c5f543b08fd9055e8ac95bcdfa` |
| `research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.md` | True | `e31147ed96faa7dd9275181d130914de2ef30bd908cd28b0f57e437469f99152` |
| `research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.docx` | True | `10f61c69157f07bb33e9b002cf01faca8e975b4b443a5e3de483cfc1d94c4383` |
| `research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.pdf` | True | `ff829bffdc94f93c266b508069b3688602e8423c2670e7015ce2db638ea9210c` |
| `research/reports/submission/internal_verification_20260711_zh.md` | True | `1ea0a8683cda6f433f402cfc6f3fcdc1e500e5a401b3ebc2978640c93c9b4dbe` |

## 证据分层

- `literature`：候选造影剂、荧光机制、定量和标准化依据；不包含本项目原创实验结果。
- `proxy_engineering`：公开异域视频、代理标注、公开 CBCT 和压力样本；用于工程链路与相对比较。
- `physician_review`：当前目标域医生关键帧和像素级金标准暂缺。
- `enterprise_device`：当前企业原始双通道样片、滤光片曲线和目标硬件实机证据暂缺。

## 外部依赖

- 候选造影剂实物合成、光谱、选择性、安全性和组织仿体验证
- 真实目标域白光/NIR JPEG 或 MP4 与医生金标准
- 企业原始双通道、滤光片曲线和目标硬件实机验证

## 医学边界

平台输出用于荧光/灌注信号候选区、骨面待复核门控、边界风险、不确定性和医生复核辅助，不提供自动确诊或疾病终判。
