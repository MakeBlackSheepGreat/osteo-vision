# Backend Optimization Ledger

更新时间：2026-07-25

本文件记录项目后端生产代码、共享分析核心、应用入口和后端测试代码清单，并维护后端性能/健壮性优化台账。清单只收录源码与测试 `.py` 文件，不收录 `artifacts/`、`output/`、缓存和生成目录。

## Scope

- `backend/osteo_vision_api/`：FastAPI 路由、领域模型、服务、持久化和报告导出。
- `osteo_vision_core/`：后端调用的共享预处理、模型、推理、数据、导航和报告核心。
- `app/`：平台兼容启动入口。
- `backend/tests/`：后端契约与单元测试。

## Inventory Summary

| 范围 | 文件数 | 总行数 | 最新文件 | 最新写入 |
|---|---:|---:|---|---|
| 生产 API 与服务层 | 81 | 27889 | `backend/osteo_vision_api/reports/platform_report.py` | 2026-07-25 14:18:23 |
| 共享分析核心（由后端调用） | 116 | 23525 | `osteo_vision_core/models/lesion_boundary.py` | 2026-07-25 10:26:38 |
| 应用启动与兼容入口 | 4 | 210 | `app/main.py` | 2026-07-23 13:47:25 |
| 后端测试 | 46 | 13900 | `backend/tests/unit/test_platform_report.py` | 2026-07-25 14:18:23 |

## 生产 API 与服务层

- `backend/osteo_vision_api/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/api/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/api/analysis_runs.py` （104 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/app.py` （42 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/cases.py` （76 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/dataset_review.py` （122 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/exports.py` （19 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/files.py` （136 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/helpers.py` （38 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/hospital_intake.py` （50 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/inputs.py` （20 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/live_frames.py` （224 行，最近写入 2026-07-24 19:06:27）
- `backend/osteo_vision_api/api/manual_annotations.py` （263 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/promotion_approvals.py` （155 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/regions.py` （86 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/review_events.py` （37 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/review_identity.py` （110 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/routes.py` （174 行，最近写入 2026-07-25 00:17:05）
- `backend/osteo_vision_api/api/three_d_modeling.py` （427 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/three_d_runtime.py` （70 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/upload_processing.py` （273 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/uploads.py` （64 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/api/video_library.py` （64 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/core/artifacts.py` （46 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/disclaimers.py` （28 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/core/settings.py` （132 行，最近写入 2026-07-22 16:19:34）
- `backend/osteo_vision_api/domains/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/domains/annotations/__init__.py` （1 行，最近写入 2026-07-19 07:55:30）
- `backend/osteo_vision_api/domains/annotations/enums.py` （53 行，最近写入 2026-07-19 06:08:09）
- `backend/osteo_vision_api/domains/annotations/repository.py` （274 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/annotations/schemas.py` （242 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/cases/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/domains/cases/enums.py` （90 行，最近写入 2026-07-24 23:54:37）
- `backend/osteo_vision_api/domains/cases/repository.py` （243 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/domains/cases/schemas.py` （443 行，最近写入 2026-07-24 23:53:51）
- `backend/osteo_vision_api/main.py` （15 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/reports/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/reports/dicom_secondary_capture.py` （122 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/reports/platform_markdown.py` （127 行，最近写入 2026-07-25 00:00:58）
- `backend/osteo_vision_api/reports/platform_report_sections.py` （876 行，最近写入 2026-07-25 06:11:13）
- `backend/osteo_vision_api/reports/platform_report.py` （94 行，最近写入 2026-07-25 14:18:23）
- `backend/osteo_vision_api/reports/quantification_csv.py` （125 行，最近写入 2026-07-25 03:30:57）
- `backend/osteo_vision_api/services/__init__.py` （1 行，最近写入 2026-07-05 15:56:48）
- `backend/osteo_vision_api/services/active_review_queue.py` （726 行，最近写入 2026-07-19 07:55:30）
- `backend/osteo_vision_api/services/analysis_outputs.py` （451 行，最近写入 2026-07-25 03:25:38）
- `backend/osteo_vision_api/services/analysis_service.py` （2306 行，最近写入 2026-07-25 03:19:13）
- `backend/osteo_vision_api/services/cbct_modeling_service.py` （1653 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/clinical_context_assessment.py` （375 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/export_bundle.py` （241 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/export_core_files.py` （400 行，最近写入 2026-07-25 03:30:48）
- `backend/osteo_vision_api/services/export_service.py` （141 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/hospital_intake_service.py` （766 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/input_service.py` （196 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/job_service.py` （288 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/job_state.py` （39 行，最近写入 2026-07-06 19:45:58）
- `backend/osteo_vision_api/services/job_tasks.py` （320 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/job_worker.py` （159 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/keyframe_report_loader.py` （117 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/keyframe_segmentation.py` （371 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/live_frame_service.py` （941 行，最近写入 2026-07-24 19:11:53）
- `backend/osteo_vision_api/services/manual_annotation_service.py` （1409 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/offline_pose_replay_service.py` （2363 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/patient_conditioning_gate.py` （252 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/promotion_approval_service.py` （524 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_geometry.py` （77 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_manifest.py` （275 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/review_service.py` （1910 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/roi_service.py` （25 行，最近写入 2026-06-16 00:49:13）
- `backend/osteo_vision_api/services/static_dataset_review.py` （858 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/static_registration_service.py` （1294 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/task2_sequence_service.py` （582 行，最近写入 2026-07-25 10:26:38）
- `backend/osteo_vision_api/services/three_d_case_evidence.py` （268 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/three_d_evidence.py` （978 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/three_d_runtime_snapshot.py` （677 行，最近写入 2026-07-23 14:12:42）
- `backend/osteo_vision_api/services/video_analysis_details.py` （241 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/video_hotspot_outputs.py` （257 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/video_keyframe_metrics.py` （288 行，最近写入 2026-07-23 13:47:25）
- `backend/osteo_vision_api/services/video_library_service.py` （164 行，最近写入 2026-07-23 13:47:25）
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
- `osteo_vision_core/models/keyframe_segmenter.py` （931 行，最近写入 2026-07-25 00:29:12）
- `osteo_vision_core/models/lesion_boundary.py` （603 行，最近写入 2026-07-25 10:26:38）
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
- `osteo_vision_core/preprocess/accelerated_fusion.py` （1216 行，最近写入 2026-07-25 05:59:40）
- `osteo_vision_core/preprocess/cbct_roi.py` （275 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/contracts/__init__.py` （75 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/ct_preprocess.py` （11 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/preprocess/fluorescence.py` （693 行，最近写入 2026-07-25 01:41:26）
- `osteo_vision_core/preprocess/fusion_ai_contract.py` （192 行，最近写入 2026-07-25 06:08:32）
- `osteo_vision_core/preprocess/image_quality.py` （41 行，最近写入 2026-07-03 22:49:30）
- `osteo_vision_core/preprocess/input_validation.py` （65 行，最近写入 2026-07-23 13:47:26）
- `osteo_vision_core/preprocess/mask_postprocess.py` （7 行，最近写入 2026-07-19 18:37:56）
- `osteo_vision_core/preprocess/roi.py` （150 行，最近写入 2026-07-04 02:23:16）
- `osteo_vision_core/preprocess/task2_protocol.py` （6 行，最近写入 2026-07-25 06:05:13）
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
- `backend/tests/contract/test_case_inputs_api.py` （886 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_clinical_context_api.py` （234 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_dataset_review_api.py` （406 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_export_api.py` （27 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_hospital_intake_api.py` （479 行，最近写入 2026-07-23 13:47:25）
- `backend/tests/contract/test_live_frames_api.py` （850 行，最近写入 2026-07-24 19:11:53）
- `backend/tests/contract/test_manual_annotations_api.py` （515 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_offline_pose_replay_api.py` （1269 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_promotion_approvals_api.py` （338 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_review_api.py` （308 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_runtime_readiness_api.py` （70 行，最近写入 2026-07-25 00:16:47）
- `backend/tests/contract/test_three_d_registration_api.py` （730 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/contract/test_three_d_runtime_api.py` （362 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_active_review_queue.py` （354 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_analysis_service.py` （898 行，最近写入 2026-07-24 21:33:18）
- `backend/tests/unit/test_artifact_manifest.py` （14 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_bone_activity_checkpoint_backend.py` （349 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_case_repository.py` （81 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_cbct_modeling_service.py` （463 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_clinical_context_assessment.py` （220 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_export_service.py` （515 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_job_service.py` （241 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_job_worker.py` （191 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_lesion_boundary.py` （190 行，最近写入 2026-07-25 10:26:38）
- `backend/tests/unit/test_manual_annotation_service.py` （312 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_navigation_job_lifecycle.py` （167 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_offline_pose_replay_service.py` （132 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_patient_conditioning_analysis.py` （421 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_platform_report.py` （40 行，最近写入 2026-07-25 14:18:23）
- `backend/tests/unit/test_platform_report_sections.py` （98 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_promotion_approval_service.py` （364 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_quality_flags.py` （67 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_review_manifest.py` （115 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_review_state.py` （128 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_reviewed_bone_activity_spectrum.py` （223 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_reviewed_ignore_annotation_sync.py` （389 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_roi_quantification.py` （14 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_settings_runtime_paths.py` （70 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_task2_sequence_service.py` （213 行，最近写入 2026-07-25 00:36:19）
- `backend/tests/unit/test_task3_fused_report.py` （197 行，最近写入 2026-07-25 06:12:40）
- `backend/tests/unit/test_three_d_evidence_service.py` （286 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_dynamic_quantification.py` （272 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_keyframe_metrics.py` （48 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_library_service.py` （98 行，最近写入 2026-07-23 13:47:26）
- `backend/tests/unit/test_video_signal_segmentation_contract.py` （255 行，最近写入 2026-07-23 13:47:26）

## Optimization Ledger

| 日期 | 文件 | 优化内容 | 验证证据 | 状态 |
|---|---|---|---|---|
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
| 待处理 | `backend/osteo_vision_api/services/video_hotspot_outputs.py` | 最近仍未审计的视频热点产物服务，后续检查热点排序、候选聚合与证据扫描 | 未开始 | 待审计 |

## Latest Candidate

- 本轮已完成最近未审计核心文件 `osteo_vision_core/models/lesion_boundary.py` 的优化，候选优先级、每类上限、总上限、空间抑制和医学安全回退语义均由回归测试覆盖。
- 本轮已完成 `backend/osteo_vision_api/reports/platform_report.py` 的序列化缓存优化，回归测试验证报告输出值保持一致。
- 本轮已完成 `backend/osteo_vision_api/reports/platform_report_sections.py` 的只读 JSON 容器复用和患者条件章节聚合清理，避免大规模视频证据列表与嵌套字典的冗余浅拷贝。
- 本轮已完成 `backend/osteo_vision_api/services/analysis_outputs.py` 的 Task 3 候选数值门控和证据产物统一聚合，减少重复容器拷贝、重复 SHA256 计算及失效路径导致的运行中断。
- 本轮已完成 `backend/osteo_vision_api/services/analysis_service.py` 的活动配置快照复用，消除一次分析内多处 YAML 重读和解析。
- 本轮已完成 `backend/osteo_vision_api/services/export_core_files.py` 的导出证据只读载荷复用，减少多运行报告与 CSV 导出过程中的冗余字典复制。
- 本轮已完成 `backend/osteo_vision_api/services/live_frame_service.py` 的深层输出路径迭代收集，避免递归风险。
- 本轮已完成 `backend/osteo_vision_api/services/review_service.py` 的复核帧计数重复逻辑合并。
- 本轮已完成 `backend/osteo_vision_api/services/active_review_queue.py` 的评分数值有限性门控。
- 本轮已完成 `backend/osteo_vision_api/services/static_registration_service.py` 的配准请求只读载荷复用。
- 下一候选为 `backend/osteo_vision_api/services/video_hotspot_outputs.py`，后续从热点排序、候选聚合与证据扫描开始审计。
- 已移除本轮发现的完全未调用私有函数 `_bbox_component`，并清理任务2服务中的未使用导入。

## Verification Baseline

- Python 环境：`C:\Users\876762330\.conda\envs\osteo-vision\python.exe`。
- 目标质量门：`pytest`、`ruff`、必要的运行基准和严格平台 smoke。
- 每次优化需记录行为回归、性能变化、异常输入处理和剩余未优化候选。
- 本轮验证：任务2/任务3定向测试 20 项通过；病灶边界、报告缓存、报告章节和分析产物回归测试通过；全量 Python `pytest` 通过；Ruff、Black、isort 和 `git diff --check` 通过。
