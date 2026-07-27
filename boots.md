# Backend Optimization Ledger

更新时间：2026-07-27

本文件记录项目后端生产代码、共享分析核心、应用入口和后端测试代码清单，并维护后端性能/健壮性优化台账。清单只收录源码与测试 `.py` 文件，不收录 `artifacts/`、`output/`、缓存和生成目录。

## Scope

- `backend/osteo_vision_api/`：FastAPI 路由、领域模型、服务、持久化和报告导出。
- `osteo_vision_core/`：后端调用的共享预处理、模型、推理、数据、导航和报告核心。
- `app/`：平台兼容启动入口。
- `backend/tests/`：后端契约与单元测试。

## Inventory Summary

| 范围 | 文件数 | 总行数 | 最新文件 | 最新写入 |
|---|---:|---:|---|---|
| 生产 API 与服务层 | 85 | 27344 | `backend/osteo_vision_api/api/app.py` | 2026-07-26 17:22:00 |
| 共享分析核心（由后端调用） | 116 | 21062 | `osteo_vision_core/preprocess/accelerated_fusion.py` | 2026-07-25 16:25:49 |
| 应用启动与兼容入口 | 4 | 210 | `app/main.py` | 2026-07-23 13:47:25 |
| 后端测试 | 56 | 13455 | `backend/tests/unit/test_desktop_runtime_shutdown.py` | 2026-07-26 17:22:00 |

## 生产 API 与服务层

- `backend/osteo_vision_api/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/api/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/api/analysis_runs.py` （104 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/app.py` （42 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/cases.py` （76 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/dataset_review.py` （122 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/exports.py` （19 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/files.py` （156 行，最近写入 2026-07-26 08:08:42）
- `backend/osteo_vision_api/api/helpers.py` （38 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/hospital_intake.py` （50 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/inputs.py` （20 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/live_frames.py` （224 行，最近写入 2026-07-24 19:06:27）
- `backend/osteo_vision_api/api/manual_annotations.py` （263 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/multichannel_videos.py` （52 行，最近写入 2026-07-25 22:22:50）
- `backend/osteo_vision_api/api/promotion_approvals.py` （155 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/regions.py` （86 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/review_events.py` （37 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/review_identity.py` （110 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/routes.py` （196 行，最近写入 2026-07-25 22:22:50）
- `backend/osteo_vision_api/api/standard_demo_case.py` （16 行，最近写入 2026-07-25 21:37:00）
- `backend/osteo_vision_api/api/three_d_modeling.py` （427 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/three_d_runtime.py` （70 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/upload_processing.py` （273 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/uploads.py` （64 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/video_library.py` （64 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/core/artifacts.py` （46 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/disclaimers.py` （28 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/settings.py` （146 行，最近写入 2026-07-25 22:20:44）
- `backend/osteo_vision_api/domains/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/domains/annotations/__init__.py` （1 行，最近写入 2026-07-19 07:55:30）
- `backend/osteo_vision_api/domains/annotations/enums.py` （53 行，最近写入 2026-07-19 06:08:09）
- `backend/osteo_vision_api/domains/annotations/repository.py` （274 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/annotations/schemas.py` （242 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/cases/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/domains/cases/enums.py` （90 行，最近写入 2026-07-24 23:54:37）
- `backend/osteo_vision_api/domains/cases/repository.py` （243 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/cases/schemas.py` （525 行，最近写入 2026-07-25 22:48:07）
- `backend/osteo_vision_api/main.py` （15 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/reports/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/reports/dicom_secondary_capture.py` （122 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/reports/platform_markdown.py` （127 行，最近写入 2026-07-25 00:00:58）
- `backend/osteo_vision_api/reports/platform_report_sections.py` （872 行，最近写入 2026-07-25 14:30:26）
- `backend/osteo_vision_api/reports/platform_report.py` （82 行，最近写入 2026-07-25 16:23:24）
- `backend/osteo_vision_api/reports/quantification_csv.py` （125 行，最近写入 2026-07-25 03:30:57）
- `backend/osteo_vision_api/services/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/services/active_review_queue.py` （729 行，最近写入 2026-07-25 14:49:36）
- `backend/osteo_vision_api/services/analysis_outputs.py` （436 行，最近写入 2026-07-25 14:35:57）
- `backend/osteo_vision_api/services/analysis_service.py` （2344 行，最近写入 2026-07-26 02:26:51）
- `backend/osteo_vision_api/services/cbct_modeling_service.py` （1786 行，最近写入 2026-07-26 02:09:18）
- `backend/osteo_vision_api/services/clinical_context_assessment.py` （375 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/export_bundle.py` （241 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/export_core_files.py` （400 行，最近写入 2026-07-25 14:44:57）
- `backend/osteo_vision_api/services/export_service.py` （141 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/hospital_intake_service.py` （789 行，最近写入 2026-07-26 04:55:41）
- `backend/osteo_vision_api/services/input_service.py` （196 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/job_service.py` （298 行，最近写入 2026-07-26 02:10:42）
- `backend/osteo_vision_api/services/job_state.py` （39 行，最近写入 2026-07-06 19:45:58）
- `backend/osteo_vision_api/services/job_tasks.py` （364 行，最近写入 2026-07-26 02:09:18）
- `backend/osteo_vision_api/services/job_worker.py` （159 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/keyframe_report_loader.py` （117 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/keyframe_segmentation.py` （371 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/live_frame_service.py` （943 行，最近写入 2026-07-25 14:46:17）
- `backend/osteo_vision_api/services/manual_annotation_service.py` （1448 行，最近写入 2026-07-26 04:36:04）
- `backend/osteo_vision_api/services/multichannel_video_service.py` （854 行，最近写入 2026-07-26 02:27:43）
- `backend/osteo_vision_api/services/offline_pose_replay_service.py` （2364 行，最近写入 2026-07-26 04:12:04）
- `backend/osteo_vision_api/services/patient_conditioning_gate.py` （252 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/promotion_approval_service.py` （524 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_geometry.py` （77 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_manifest.py` （275 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_service.py` （1914 行，最近写入 2026-07-26 05:05:34）
- `backend/osteo_vision_api/services/roi_service.py` （25 行，最近写入 2026-06-16 00:49:13）
- `backend/osteo_vision_api/services/static_dataset_review.py` （962 行，最近写入 2026-07-26 06:15:47）
- `backend/osteo_vision_api/services/static_registration_service.py` （1295 行，最近写入 2026-07-25 14:51:26）
- `backend/osteo_vision_api/services/standard_demo_case.py` （204 行，最近写入 2026-07-26 06:33:30）
- `backend/osteo_vision_api/services/task2_sequence_service.py` （579 行，最近写入 2026-07-26 02:01:22）
- `backend/osteo_vision_api/services/three_d_case_evidence.py` （268 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/three_d_evidence.py` （997 行，最近写入 2026-07-26 06:48:43）
- `backend/osteo_vision_api/services/three_d_runtime_snapshot.py` （686 行，最近写入 2026-07-26 07:05:58）
- `backend/osteo_vision_api/services/video_analysis_details.py` （241 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/video_hotspot_outputs.py` （318 行，最近写入 2026-07-26 01:59:07）
- `backend/osteo_vision_api/services/video_keyframe_metrics.py` （288 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/video_library_service.py` （302 行，最近写入 2026-07-26 03:32:30）
- `backend/osteo_vision_api/services/video_review_writer.py` （68 行，最近写入 2026-07-11 08:18:01）
- `backend/osteo_vision_api/services/video_segmentation_manifest.py` （417 行，最近写入 2026-07-23 13:47:25）

## 共享分析核心（由后端调用）

- `osteo_vision_core/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/core/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/core/clinical_context_verification.py` （65 行，最近写入 2026-07-19 09:16:46）
- `osteo_vision_core/core/config_validator.py` （201 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/core/config.py` （35 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/core/contracts/__init__.py` （167 行，最近写入 2026-07-03 22:49:30）
- `osteo_vision_core/core/executables.py` （20 行，最近写入 2026-07-15 10:45:52）
- `osteo_vision_core/core/paths.py` （30 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/core/registry.py` （21 行，最近写入 2026-07-03 22:49:30）
- `osteo_vision_core/core/schemas.py` （270 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/core/task_package.py` （66 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/core/warnings.py` （47 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/contracts/__init__.py` （70 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/d024.py` （136 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/d036.py` （163 行，最近写入 2026-07-10 16:05:06）
- `osteo_vision_core/datasets/domain_adaptation.py` （206 行，最近写入 2026-07-19 07:55:31）
- `osteo_vision_core/datasets/group_splits.py` （99 行，最近写入 2026-07-19 07:55:31）
- `osteo_vision_core/datasets/leakage.py` （5 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/datasets/manifests.py` （41 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/ofdvdnet.py` （148 行，最近写入 2026-07-19 18:37:45）
- `osteo_vision_core/datasets/registry.py` （339 行，最近写入 2026-07-19 07:55:31）
- `osteo_vision_core/datasets/splits.py` （17 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/datasets/static_panel_detection.py` （242 行，最近写入 2026-07-11 10:12:30）
- `osteo_vision_core/datasets/training_admission.py` （1211 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/engine/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/engine/benchmark.py` （132 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/engine/contracts/__init__.py` （75 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/engine/experiment.py` （361 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/engine/inference.py` （215 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/experiments/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/experiments/promotion.py` （86 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/experiments/spec.py` （57 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/experiments/splits.py` （53 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/experiments/thresholds.py` （47 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/explain/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/explain/gradcam.py` （14 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/explain/overlay.py` （10 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/io/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/io/content_probe.py` （77 行，最近写入 2026-07-08 15:14:57）
- `osteo_vision_core/io/dicom_io.py` （17 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/io/image_io.py` （35 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/io/live_stream.py` （482 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/io/nifti_io.py` （8 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/io/official_device_quality.py` （201 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/io/video_io.py` （111 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/metrics/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/metrics/calibration.py` （111 行，最近写入 2026-07-11 03:30:42）
- `osteo_vision_core/metrics/classification.py` （42 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/metrics/detection.py` （5 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/metrics/segmentation.py` （182 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/models/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/models/adapters.py` （1188 行，最近写入 2026-07-25 03:06:54）
- `osteo_vision_core/models/bone_activity_multitask.py` （271 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/bone_activity_runtime.py` （719 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/classifier.py` （20 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/models/clinical_feature_vector.py` （639 行，最近写入 2026-07-19 10:57:21）
- `osteo_vision_core/models/contracts/__init__.py` （87 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/detector.py` （18 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/models/dual_channel_segmenter.py` （133 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/ensembles.py` （48 行，最近写入 2026-06-15 19:23:59）
- `osteo_vision_core/models/hotspot_segmenter.py` （212 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/keyframe_candidates.py` （195 行，最近写入 2026-07-19 13:10:05）
- `osteo_vision_core/models/keyframe_segmenter.py` （929 行，最近写入 2026-07-25 16:23:24）
- `osteo_vision_core/models/lesion_boundary.py` （558 行，最近写入 2026-07-25 16:23:24）
- `osteo_vision_core/models/lesion_segmenter.py` （209 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/patient_conditioned_runtime.py` （811 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/patient_conditioned_segmenter.py` （406 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/promotion_approval_gate.py` （329 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/promotion_approval.py` （342 行，最近写入 2026-07-19 05:21:00）
- `osteo_vision_core/models/prompt_segmenter.py` （210 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/registry.py` （39 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/runtime_preflight.py` （302 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/runtime_promotion.py` （616 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/segmenter.py` （26 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/three_priority_promotion.py` （1733 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/models/video_signal_masks.py` （447 行，最近写入 2026-07-24 18:39:29）
- `osteo_vision_core/models/video_signal_multimask.py` （229 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/navigation/__init__.py` （42 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/navigation/camera_registration.py` （451 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/navigation/coordinate_contract.py` （149 行，最近写入 2026-07-19 02:50:48）
- `osteo_vision_core/navigation/ocamcalib.py` （139 行，最近写入 2026-07-19 03:48:37）
- `osteo_vision_core/navigation/offline_pose_replay.py` （1119 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/navigation/rigid_registration.py` （315 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/pipelines/base.py` （23 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/classification.py` （46 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/contracts/__init__.py` （66 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/detection.py` （16 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/multitask.py` （54 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/quantification.py` （20 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/pipelines/segmentation.py` （27 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/preprocess/accelerated_fusion.py` （1217 行，最近写入 2026-07-25 16:25:49）
- `osteo_vision_core/preprocess/cbct_roi.py` （275 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/contracts/__init__.py` （75 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/ct_preprocess.py` （11 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/preprocess/fluorescence.py` （693 行，最近写入 2026-07-25 01:41:26）
- `osteo_vision_core/preprocess/fusion_ai_contract.py` （192 行，最近写入 2026-07-25 06:08:32）
- `osteo_vision_core/preprocess/image_quality.py` （41 行，最近写入 2026-07-03 22:49:30）
- `osteo_vision_core/preprocess/input_validation.py` （65 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/mask_postprocess.py` （7 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/preprocess/roi.py` （150 行，最近写入 2026-07-04 02:23:16）
- `osteo_vision_core/preprocess/task2_protocol.py` （5 行，最近写入 2026-07-25 16:23:24）
- `osteo_vision_core/preprocess/temporal_registration.py` （112 行，最近写入 2026-07-25 01:39:34）
- `osteo_vision_core/preprocess/three_channel_quality.py` （206 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/video.py` （688 行，最近写入 2026-07-22 10:56:57）
- `osteo_vision_core/reports/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/reports/benchmark.py` （25 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/reports/contracts/__init__.py` （53 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/reports/single_case.py` （35 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/reports/validators.py` （29 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/reports/writers.py` （42 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/utils/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/utils/logging.py` （192 行，最近写入 2026-07-19 18:37:57）
- `osteo_vision_core/utils/runtime.py` （249 行，最近写入 2026-07-03 22:49:30）

## 应用启动与兼容入口

- `app/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `app/components/__init__.py` （1 行，最近写入 2026-07-19 18:37:56）
- `app/components/status_panels.py` （22 行，最近写入 2026-07-19 18:37:56）
- `app/main.py` （186 行，最近写入 2026-07-23 13:47:25）

## 后端测试

- `backend/tests/__init__.py` （1 行，最近写入 2026-07-05 15:56:47）
- `backend/tests/contract/test_case_inputs_api.py` （887 行，最近写入 2026-07-25 22:43:03）
- `backend/tests/contract/test_clinical_context_api.py` （234 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_dataset_review_api.py` （406 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_export_api.py` （27 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_hospital_intake_api.py` （479 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_live_frames_api.py` （850 行，最近写入 2026-07-24 19:11:53）
- `backend/tests/contract/test_manual_annotations_api.py` （515 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_multichannel_video_api.py` （347 行，最近写入 2026-07-26 02:27:43）
- `backend/tests/contract/test_offline_pose_replay_api.py` （1269 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_promotion_approvals_api.py` （338 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_review_api.py` （308 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_standard_demo_case_api.py` （89 行，最近写入 2026-07-26 01:11:33）
- `backend/tests/contract/test_runtime_readiness_api.py` （70 行，最近写入 2026-07-25 00:16:47）
- `backend/tests/contract/test_three_d_registration_api.py` （730 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_three_d_runtime_api.py` （366 行，最近写入 2026-07-26 01:11:33）
- `backend/tests/unit/test_active_review_queue.py` （354 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_analysis_outputs.py` （74 行，最近写入 2026-07-25 14:36:59）
- `backend/tests/unit/test_analysis_service.py` （898 行，最近写入 2026-07-24 21:33:18）
- `backend/tests/unit/test_artifact_manifest.py` （14 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_bone_activity_checkpoint_backend.py` （349 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_case_repository.py` （81 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_cbct_modeling_service.py` （463 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_clinical_context_assessment.py` （220 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_export_service.py` （515 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_files_api.py` （100 行，最近写入 2026-07-26 08:09:21）
- `backend/tests/unit/test_hospital_intake_service.py` （33 行，最近写入 2026-07-26 04:55:13）
- `backend/tests/unit/test_job_service.py` （268 行，最近写入 2026-07-26 02:10:53）
- `backend/tests/unit/test_job_worker.py` （191 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_lesion_boundary.py` （188 行，最近写入 2026-07-25 16:23:24）
- `backend/tests/unit/test_manual_annotation_service.py` （377 行，最近写入 2026-07-26 04:37:53）
- `backend/tests/unit/test_navigation_job_lifecycle.py` （224 行，最近写入 2026-07-26 02:00:43）
- `backend/tests/unit/test_offline_pose_replay_service.py` （157 行，最近写入 2026-07-26 04:12:47）
- `backend/tests/unit/test_patient_conditioning_analysis.py` （421 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_platform_report.py` （38 行，最近写入 2026-07-25 16:23:24）
- `backend/tests/unit/test_platform_report_sections.py` （120 行，最近写入 2026-07-25 14:27:33）
- `backend/tests/unit/test_promotion_approval_service.py` （364 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_quality_flags.py` （67 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_review_manifest.py` （115 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_review_state.py` （165 行，最近写入 2026-07-26 05:07:50）
- `backend/tests/unit/test_reviewed_bone_activity_spectrum.py` （223 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_reviewed_ignore_annotation_sync.py` （389 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_roi_quantification.py` （14 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_settings_runtime_paths.py` （70 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_desktop_runtime_shutdown.py` （9 行，最近写入 2026-07-26 17:22:00）
- `backend/tests/unit/test_standard_demo_case.py` （43 行，最近写入 2026-07-26 06:33:54）
- `backend/tests/unit/test_static_dataset_review.py` （112 行，最近写入 2026-07-26 06:16:07）
- `backend/tests/unit/test_three_d_runtime_snapshot.py` （34 行，最近写入 2026-07-26 07:02:27）
- `backend/tests/unit/test_task2_sequence_service.py` （241 行，最近写入 2026-07-26 02:04:47）
- `backend/tests/unit/test_task3_fused_report.py` （197 行，最近写入 2026-07-25 06:12:40）
- `backend/tests/unit/test_three_d_evidence_service.py` （323 行，最近写入 2026-07-26 06:51:24）
- `backend/tests/unit/test_video_dynamic_quantification.py` （272 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_keyframe_metrics.py` （48 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_hotspot_outputs.py` （103 行，最近写入 2026-07-26 01:58:05）
- `backend/tests/unit/test_video_library_service.py` （214 行，最近写入 2026-07-26 03:30:59）
- `backend/tests/unit/test_video_signal_segmentation_contract.py` （255 行，最近写入 2026-07-23 13:47:26）

## Optimization Ledger

| 日期 | 文件 | 优化内容 | 验证证据 | 状态 |
|---|---|---|---|---|
| 2026-07-27 | `backend/osteo_vision_api/api/multichannel_videos.py`、`backend/osteo_vision_api/domains/cases/schemas.py`、`backend/osteo_vision_api/services/multichannel_video_service.py`、`frontend/src/composables/useBrowserCamera.ts`、`frontend/src/pages/CaseWorkspacePage.vue`、`frontend/src/components/CaseWorkspaceControls.vue`、`frontend/src/components/MultichannelVideoWorkspace.vue` | 浏览器摄像头输入扩展为独立白光与荧光双路采集；新增不接受文件路径的 `browser_cameras` 会话，实时接口强制提交成对当前帧。输入源、视频模式或摄像头设备变化时中止在途配准、清空融合/AI 队列并通过 generation 校验丢弃迟到响应；摄像头模式隐藏 MP4 关键帧、离线 AI、时间轴和历史证据，避免文件结果混入。双通道实时分析保持显式开启/关闭控制，白光与荧光通道禁止选择同一设备。 | `test_multichannel_video_api.py` 16 项、前端 56 个测试文件共 248 项、`typecheck` 与生产构建通过；定向 Ruff、Black、isort、mypy 和 `git diff --check` 通过。Playwright 使用两路动态 Canvas 摄像头完成浏览器实测：会话建立成功，单次配准融合约 31 ms，2.5 秒内融合 URL 与时间标签持续更新；切换回文件输入后摄像头结果立即清除，MP4 工作流恢复。 | 已完成 |
| 2026-07-26 | `frontend/src/components/MultichannelVideoWorkspace.vue`、`frontend/src/components/AnalysisQuadGrid.vue`、`frontend/src/pages/CaseWorkspacePage.vue`、`backend/osteo_vision_api/services/multichannel_video_service.py`、`backend/osteo_vision_api/services/task2_sequence_service.py` | 双通道实时配准改为浏览器从当前白光/荧光播放画面同步抓取 512px JPEG 对，后端直接处理该帧对；移除“从 12 个离线关键帧中挑最近帧”导致的数秒级画面跳变。实时路径仅编码配准荧光图与融合图，跳过归一化/伪彩副本、设备差异图和 SHA256；重复覆盖实时预览文件并以版本参数刷新浏览器缓存。单路 MP4 在暂停和拖动完成后也立即抓取当前画面进入实时分割。正式关键帧证据与完整产物仍由 Task2 批处理保留。 | 新增当前浏览器帧、融合帧快照与单路 MP4 暂停/拖动回归；`pytest backend/tests/contract/test_multichannel_video_api.py -q` 14 项、前端定向 Vitest 12 项、`typecheck`、生产构建通过。 | 已完成 |
| 2026-07-26 | `packaging/desktop/`、`backend/osteo_vision_api/api/app.py`、`scripts/build_desktop_package.ps1` | Electron 桌面宿主统一拉起 PyInstaller API；关闭最后窗口、应用退出、启动失败和渲染进程退出均先终止后端。后端接收 `SIGTERM` 后执行 CUDA 同步、缓存及 IPC 清理；5 秒内未退出时宿主使用 `taskkill /T /F` 清理进程树。发行包内置 FFmpeg/FFprobe 与依赖，严格运行预检可在脱离 Conda 的环境启动。 | `npm run desktop:test` 4 项、`pytest backend/tests/unit/test_desktop_runtime_shutdown.py -q` 2 项、前端 typecheck 与桌面 Vite build 通过。实机启动 `Osteo Vision Platform.exe` 后 `/ready` 返回 200，后端为该 Electron 主进程子进程；关闭主窗口后端端口关闭、`osteo-vision-api.exe` 和 Electron 全部退出。`nvidia-smi` 未发现该桌面包残留计算进程。 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/api/files.py` | 文件预览、下载和视频路由在应用构建时一次性解析并去重 artifact/公开视频/manifest 根目录，移除每请求重复根路径解析；删除仅做转发的私有包装函数和重复 URL 解码；非法路径、目录、损坏链接及文件系统异常统一安全降级，保留后缀白名单与越界 403 语义；字面百分号文件名可按原名访问 | 新增 `backend/tests/unit/test_files_api.py` 4 项；文件路由相关定向 40 项、后端全量 352 项、核心/Smoke 812 项通过；后端与共享核心 201 个源码文件 mypy 和 Ruff 全量通过，改动文件 Black/isort 通过。2,000 次路径解析中位数由 2,695.386 ms 降至 989.501 ms，约 2.72 倍 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/static_dataset_review.py` | D047/D048 队列、已复核清单和自动种子清单按文件签名缓存；队列同步建立 `record_id` 索引，单记录查找由重复 JSON 解析和线性扫描收敛为缓存后常量时间查找；图像尺寸与 SHA256 按文件签名复用；内部写入显式失效缓存，外部文件变化自动重载；异常记录字段按队列级降级计数跳过 | 新增 `backend/tests/unit/test_static_dataset_review.py` 3 项，数据集复核 API 7 项、后端全量 346 项通过；后端与共享核心 201 个源码文件 mypy 通过，Ruff 全量通过，定向 Black/isort 通过。20,000 条队列末项查找 25 次中位数由 29.549 ms 降至 1.655 ms，约 17.86 倍 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/review_service.py` | 复核摘要将 ROI 与候选的多轮重复扫描分别收敛为一次计数，保持已接受、已修改、已拒绝状态统计语义 | 新增复核摘要单元回归；复核单元与 API 共 12 项、后端全量 346 项通过。10,000 个 ROI 与 1,000 个候选、5 次汇总由 12.474 ms 降至 4.746 ms | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/standard_demo_case.py` | 标准演示视频优先通过 `VideoLibraryService.get_candidate` 的 `record_id` 索引直接获取；偏好记录不可读时回退到 `list_candidates(limit=1)`，移除每次初始化最多构建 500 个候选载荷的路径，保持首个可读代理回退语义 | 新增标准演示服务单元测试 2 项；标准演示 API 2 项、后端全量 346 项通过；定向 Ruff/Black/isort/mypy 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/three_d_evidence.py` | 变换文件校验先读取一次原始字节，同时完成 SHA256 和矩阵解析；JSON/CSV/TXT/TFM/NPY 解析统一复用内存载荷；删除重复文件扫描的未调用 `_sha256` 辅助函数，保留格式、矩阵形状、有限值和安全门语义 | 新增一次文件读取回归；三维证据单元 8 项、三维运行时/注册 API 26 项、后端全量 347 项和核心/Smoke 807 项通过；定向 Ruff、Black、isort、mypy 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/three_d_runtime_snapshot.py` | 模型文件 SHA256 LRU 缓存键增加文件创建时间和 inode，原子替换或同尺寸模型更新时可重新计算摘要，保持运行时快照完整性与模型路径安全门 | 新增同尺寸替换并保留 mtime 的缓存失效回归；三维运行时 API 与单元共 10 项、后端全量 348 项和核心/Smoke 808 项通过；定向 Ruff、Black、isort、mypy 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/multichannel_video_service.py` | 合成三视图拆分由每通道独立 FFmpeg 进程改为单进程 `split`/多路 `crop`；采样时间改为无 NumPy 的有限值安全实现；会话 ID 严格校验；会话 JSON 采用临时文件、`fsync` 与原子替换写入；缓存读取减少预检查 | `test_multichannel_video_api.py` 12 项通过；`test_analysis_service.py` 21 项通过；服务与相关 API 的 mypy、Ruff、Black、isort 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/analysis_service.py` | 补回 Task3 融合计时路径所需的 `perf_counter` 导入，恢复运行时计时与类型检查 | 分析服务 21 项单元测试、mypy 与 Ruff 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/cbct_modeling_service.py`、`job_tasks.py`、`job_service.py` | 三维建模任务增加输入检查、标签查找、体数据读取、掩膜清理、表面提取、STL 写入、证据整理和病例持久化阶段进度；每阶段记录百分比、当前文件和病例；取消任务后跳过病例持久化；失败任务保留失败前进度 | 新增导航任务进度与终态详情保留单元测试；CBCT 建模、任务服务和导航生命周期 34 项测试通过；三维建模 API 契约所在文件 24 项测试通过；Ruff、前端 239 项测试、typecheck、生产构建和 1440/1024 桌面浏览器检查通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/video_hotspot_outputs.py` | 将热点汇总改为单次常量附加内存扫描；候选选取由全量排序收敛为固定 Top-3 堆选择；统一有限数值门控，跳过异常帧/`NaN`/无穷值；证据产物去重、缓存同路径 SHA256 并跳过缺失或目录路径 | 新增 `backend/tests/unit/test_video_hotspot_outputs.py` 覆盖异常数值、Top-3 选择、缺失文件与去重；热点相关 339 项后端测试与核心/Smoke 626 项测试在项目受控临时目录中通过；定向 mypy、Ruff、Black、isort 通过 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/video_library_service.py` | manifest 按文件签名缓存并建立 `record_id` 索引；候选列表按 `limit` 流式生成并提前停止；路径、CSV、编码、OpenCV 句柄、FPS/尺寸和预览写入增加安全降级；预览缓存只接受普通文件 | `test_video_library_service.py` 7 项；视频库/病例输入/多通道视频/标准演示回归 49 项；后端全量 339 项；mypy、Ruff、Black、isort 均通过。20,000 行 manifest 微基准中，1,000 次末项查找中位数 290.527 ms，相比线性扫描 683.781 ms，约 2.35 倍 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/offline_pose_replay_service.py` | L2 叠加视频渲染将可见投影点判定和绘制合并为单次扫描；空解码帧安全失败；源视频存在多余帧时返回受控错误码，避免 NumPy 数组布尔判断异常；保留输入校验和双读完整性门 | 单元测试 3 项、离线位姿回放 API 契约 23 项通过；mypy、Ruff、Black、isort 通过。20,000 点、100 次合成循环中位数由 839.626 ms 降至 430.764 ms，约 1.95 倍 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/manual_annotation_service.py` | `_descriptors_for_run` 对每个来源重复扫描病例视频输入的问题收敛为每个运行一次；候选按帧索引建立一次查找表，避免每个候选重复线性遍历帧列表；病例 JPEG 解析后复用已解析路径 | 新增人工标注单元回归；人工标注 API 5 项、后端全量 339 项；mypy、Ruff、Black、isort 通过。合成 1,000 帧/256 个输入基准中，视频资产查找由每次扫描 1,000 次降至 1 次，候选帧查找由线性扫描约 42.002 ms 降至索引查找约 0.024 ms，约 1,645 倍 | 已完成 |
| 2026-07-26 | `backend/osteo_vision_api/services/hospital_intake_service.py` | 住院/医院批次准入按外部病例一次分组，移除每个病例再次扫描全部已准入记录的 O(C×R) 路径；历史批次 SHA256 清单按报告文件签名缓存，文件变化后自动重载，缓存访问加锁 | 新增医院准入服务单元测试；医院准入 API 14 项、单元 1 项、后端全量 340 项；mypy、Ruff、Black、isort 通过。22,000 条合成记录分组基准由 372.692 ms 降至 1.639 ms，约 233.89 倍；100 份大报告重复扫描基准约 2.97 倍 | 已完成 |
| 2026-07-25 | `osteo_vision_core/models/lesion_boundary.py` | 复用每类候选的单次排序结果，移除重复分组扫描和重复排序；达到候选总量或类别上限后提前停止；计数从多轮扫描收敛为单轮 `Counter`；删除未调用的 `_bbox_component` | 4096 候选、80 次重复：选择结果一致，均值 3.539 ms 降至 2.316 ms，约 1.53 倍；全量 `pytest`、Ruff、格式检查通过 | 已完成 |
| 2026-07-25 | `osteo_vision_core/models/lesion_boundary.py` | 增加数值、NaN、候选 bbox 与上限参数安全归一化；异常候选跳过并保持医生复核边界 | 新增 `backend/tests/unit/test_lesion_boundary.py`，覆盖空间 NMS、总上限、异常 bbox 和异常参数 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/task2_sequence_service.py` | 删除未使用的任务2计算预算导入 | Ruff 定向检查通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/reports/platform_report.py` | 将分析运行、输入、质控、ROI、复核事件和证据产物序列化收敛为单次缓存，复用缓存构建病例快照、最新运行和报告章节 | 64 个运行、40 次重复：输出值一致，均值 21.369 ms 降至 6.332 ms，约 3.38 倍；新增调用次数和输出回归测试通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/reports/platform_report_sections.py` | 移除报告章节读取路径中对 JSON 字典、列表的重复浅拷贝；复用只读原始容器，保留生成章节输出时的新对象边界 | 100000 帧列表的等价筛选微基准：一次额外列表拷贝 + 筛选为 3.937 ms，直接筛选为 2.449 ms，约 1.61 倍；全量 `pytest`、Ruff、Black、isort 和差异检查通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/reports/platform_report_sections.py` | 统一患者条件章节的字典读取工具，删除重复类型分支和浅拷贝；保留无效运行项跳过与最近可用证据选择语义 | 新增含无效运行项的 Task 3/骨活性证据选择回归测试；报告相关 7 项测试与全量 `pytest` 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/analysis_outputs.py` | 移除 Task 3 候选和证据载荷的重复浅拷贝；候选分值、置信度和每类上限增加有限数值与异常参数安全回退 | 新增无效数值、异常尺寸和异常上限回归测试；Task 3 与分析服务定向测试 25 项及全量 `pytest` 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/analysis_outputs.py` | 合并三类受控分析证据产物的路径规范化、去重、存在性检查与 SHA256 写入，避免同一路径重复哈希并跳过失效路径 | 新增同路径去重、失效路径跳过和错误三通道载荷回归测试；Ruff、Black、isort 与 `git diff --check` 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/analysis_service.py` | 将每次 `start_analysis` 的 YAML 配置加载收敛为单次活动配置快照，供双通道、Task 3、患者条件、视频模型选择和回退策略复用；下次分析启动仍重新读取配置 | 分析服务、Task 2 序列、Task 3 融合和患者条件定向测试 31 项通过；Ruff、Black、isort 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/export_core_files.py` | 统一导出三维、Task 3 和骨活性证据的只读字典访问，移除重复浅拷贝和分散类型分支 | 导出服务与 Task 3 报告定向测试 8 项通过；Ruff、Black、isort 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/live_frame_service.py` | 将实时帧产物路径收集从递归遍历改为显式栈遍历，避免深层或异常嵌套载荷导致递归深度失败，并减少中间集合创建 | 实时帧 API 契约测试 27 项通过；Ruff、Black 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/review_service.py` | 合并骨面门控与骨活性帧计数的重复扫描逻辑，统一保留跨 `frame_details`/`hotspot_outputs` 的去重语义 | 医生复核骨活性、忽略标注同步和复核状态测试 13 项通过；Ruff、Black 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/active_review_queue.py` | 为队列评分数值增加有限值检查，阻止 `NaN` 和无穷值进入优先级排序 | Ruff、Black 通过 | 已完成 |
| 2026-07-25 | `backend/osteo_vision_api/services/static_registration_service.py` | 复用只读阈值批准与显微镜位姿载荷，移除注册请求处理中不必要的浅拷贝 | 导航作业生命周期测试 4 项、Ruff、Black 通过 | 已完成 |
## Latest Candidate

- 已完成浏览器白光/荧光双摄像头实时闭环及文件输入隔离：当前帧成对进入配准融合与 AI 提示，切换来源后旧请求、旧预览、旧关键帧和等待队列会立即失效。
- 已完成双通道播放帧实时路径收口：当前浏览器可见的白光/荧光帧直接进入配准融合，消除低密度离线关键帧带来的数秒级刷新间隔；后续需在真实 4K 浏览器播放和桌面包环境复核端到端刷新节奏。
- 本轮已完成三维建模任务进度与取消边界增强，后端阶段状态可供前端持续轮询并在刷新后恢复。
- 本轮已完成最近未审计核心文件 `osteo_vision_core/models/lesion_boundary.py` 的优化，候选优先级、每类上限、总上限、空间抑制和医学安全回退语义均由回归测试覆盖。
- 本轮已完成 `backend/osteo_vision_api/reports/platform_report.py` 的序列化缓存优化，回归测试验证报告输出值保持一致。
- 本轮已完成 `backend/osteo_vision_api/reports/platform_report_sections.py` 的只读 JSON 容器复用和患者条件章节聚合清理，避免大规模视频证据列表与嵌套字典的冗余浅拷贝。
- 本轮已完成 `backend/osteo_vision_api/services/analysis_outputs.py` 的 Task 3 候选数值门控和证据产物统一聚合，减少重复容器拷贝、重复 SHA256 计算及失效路径导致的运行中断。
- 本轮已完成 `backend/osteo_vision_api/services/analysis_service.py` 的活动配置快照复用，消除一次分析内多处 YAML 重读和解析。
- 本轮已完成 `backend/osteo_vision_api/services/export_core_files.py` 的导出证据只读载荷复用，减少多运行报告与 CSV 导出过程中的冗余字典复制。
- 本轮已完成 `backend/osteo_vision_api/services/live_frame_service.py` 的深层输出路径迭代收集，避免递归风险。
- 本轮已完成 `backend/osteo_vision_api/services/review_service.py` 的复核帧计数重复逻辑合并和复核摘要单次计数优化。
- 本轮已完成 `backend/osteo_vision_api/services/active_review_queue.py` 的评分数值有限性门控。
- 本轮已完成 `backend/osteo_vision_api/services/static_registration_service.py` 的配准请求只读载荷复用。
- 已完成 `backend/osteo_vision_api/services/video_hotspot_outputs.py` 的热点排序、候选聚合和证据扫描审计，异常输入与缺失产物可安全降级。
- 已完成 `backend/osteo_vision_api/services/multichannel_video_service.py` 的三路视频拆分、采样和会话写入审计。
- 已完成 `backend/osteo_vision_api/services/video_library_service.py` 的清单缓存、候选索引、限量短路、路径校验和预览资源释放审计。
- 已完成 `backend/osteo_vision_api/services/offline_pose_replay_service.py` 的叠加视频单次投影点扫描、空帧降级和多余源帧受控失败审计；校验和双读继续作为 L2 证据完整性门保留。
- 已完成 `backend/osteo_vision_api/services/manual_annotation_service.py` 的运行来源索引、病例视频资产复用和 JPEG 路径重复解析收口。
- 已完成 `backend/osteo_vision_api/services/hospital_intake_service.py` 的准入记录分组和历史批次 checksum 缓存审计。
- 已完成 `backend/osteo_vision_api/services/static_dataset_review.py` 的队列/复核/种子清单签名缓存、单记录索引、图像元数据复用、写入失效和异常记录降级审计。
- 已完成 `backend/osteo_vision_api/services/standard_demo_case.py` 的偏好视频索引查找和低限量回退审计。
- 已完成 `backend/osteo_vision_api/services/three_d_evidence.py` 的变换文件单次读取、内存解析和安全校验审计。
- 已完成 `backend/osteo_vision_api/api/files.py` 的根目录预计算、路径去重、普通文件门控、异常降级和字面百分号路径审计。
- 下一候选为 `backend/osteo_vision_api/domains/cases/schemas.py`，重点检查大型病例契约中的重复验证、容器复制、兼容迁移和未引用结构。
- 已移除本轮发现的完全未调用私有函数 `_bbox_component`，并清理任务2服务中的未使用导入。

## Verification Baseline

- Python 环境：`C:\Users\876762330\.conda\envs\osteo-vision\python.exe`。
- 目标质量门：`pytest`、`ruff`、必要的运行基准和严格平台 smoke。
- 每次优化需记录行为回归、性能变化、异常输入处理和剩余未优化候选。
- 2026-07-27 双摄像头输入隔离验证：后端多通道契约 16 项、前端 248 项测试、typecheck、生产构建及定向质量门通过；动态 Canvas 浏览器实测持续刷新，配准融合约 31 ms，摄像头与 MP4 结果切换边界通过。
- 本轮验证：后端 352 项测试通过，`tests/unit + tests/smoke + backend/tests/unit` 共 812 项测试通过；后端与共享核心 201 个源码文件通过 mypy，Ruff 对 `backend/`、`osteo_vision_core/` 和 `app/` 全量检查通过。项目外部 `C:\tmp` 作为 `pytest --basetemp` 时，输入路径安全白名单会按设计拒绝仓库外测试文件；项目仓库内受控临时目录运行结果为全绿。
- 当前 Task 2 静态 4K 复现门：5 次计时的配准与 GPU 融合合计 P95 为 73.354 ms，平移误差 P95 为 1.260 px，内部 100 ms 工程门通过。
- 当前 Task 2 连续 4K 序列门：12 帧配准与 GPU 融合合计 P95 为 76.547 ms，含 JPEG 预览编码的显示就绪 P95 为 93.600 ms，连续预算漏帧率为 0，倍率 1.3x/17x 与工作距离 200/630 mm 的上下文切换均被覆盖。
- 当前比赛严格闭环复跑通过：严格配置和 checkpoint 校验通过，4K JPEG 融合、4K MP4 关键帧主线模型、工程复核、51 项病例产物与 40.9 MB 证据包均成功生成，模型回退未触发。
- 当前格式门仍有待收口项：Black 会重排 3 个文件，isort 会重排 2 个测试文件；为避免扩大当前优化批次的变更范围，后续在对应功能批次完成后统一格式化并复跑回归。
