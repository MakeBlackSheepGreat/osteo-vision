---
description: "Task list for Osteo Vision software platform target"
---

# Tasks: Osteo Vision Software Platform Target

**Input**: Design documents from `/specs/001-software-platform-target/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`

**Tests**: Tests are included because the constitution and plan require independently verifiable case workflow, medical safety wording, artifact export, and regression checks.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and demonstrated independently.

**Clarification Assumption**: The local workstation profile assumes local single-user operation with de-identified samples and local evidence bundles. If the access model changes later, update `spec.md`, `data-model.md`, and this task list before implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase when files do not overlap
- **[Story]**: User-story label, used only in user-story phases
- Every task includes an exact repository-relative file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the split frontend/backend shape while keeping the existing `osteo_vision_core/` analysis core available.

- [X] T001 Create frontend project skeleton directories in `frontend/src/`, `frontend/tests/`, and `frontend/public/`
- [X] T002 Create backend service skeleton directories in `backend/osteo_vision_api/`, `backend/tests/`, and `backend/osteo_vision_api/api/`
- [X] T003 Create frontend package metadata and scripts in `frontend/package.json`
- [X] T004 [P] Create frontend TypeScript and Vite configuration in `frontend/tsconfig.json` and `frontend/vite.config.ts`
- [X] T005 [P] Create frontend test configuration in `frontend/vitest.config.ts`
- [X] T006 Create backend package markers in `backend/osteo_vision_api/__init__.py` and `backend/tests/__init__.py`
- [X] T007 [P] Create backend app settings module in `backend/osteo_vision_api/core/settings.py`
- [X] T008 [P] Create backend application factory in `backend/osteo_vision_api/api/app.py`
- [X] T009 Document the local single-user local workstation assumption in `specs/001-software-platform-target/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared data contracts, storage paths, disclaimers, and service boundaries needed by all user stories.

**CRITICAL**: No user-story implementation should begin until this phase is complete.

- [X] T010 Create case domain dataclasses or Pydantic schemas in `backend/osteo_vision_api/domains/cases/schemas.py`
- [X] T011 Create quality flag and review-state enums in `backend/osteo_vision_api/domains/cases/enums.py`
- [X] T012 Create local artifact path manager in `backend/osteo_vision_api/core/artifacts.py`
- [X] T013 Create platform safety-boundary disclaimer constants in `backend/osteo_vision_api/core/disclaimers.py`
- [X] T014 Create case repository interface for local filesystem/SQLite-backed metadata in `backend/osteo_vision_api/domains/cases/repository.py`
- [X] T015 Create analysis service interface that wraps existing shared `osteo_vision_core/preprocess/` and `osteo_vision_core/pipelines/` boundaries in `backend/osteo_vision_api/services/analysis_service.py`
- [X] T016 Create report/export service interface in `backend/osteo_vision_api/services/export_service.py`
- [X] T017 Create API router registration module in `backend/osteo_vision_api/api/routes.py`
- [X] T018 [P] Create frontend API client shell in `frontend/src/services/apiClient.ts`
- [X] T019 [P] Create frontend route map in `frontend/src/router/index.ts`
- [X] T020 [P] Create frontend case store shell in `frontend/src/stores/caseStore.ts`
- [X] T021 [P] Create shared frontend domain types in `frontend/src/types/case.ts`
- [X] T022 Document artifact retention and Git exclusion behavior in `docs/quickstart.md`

**Checkpoint**: Core directories, data contracts, local storage paths, disclaimers, and service interfaces exist.

---

## Phase 3: User Story 1 - Review a dual-channel case (Priority: P1) MVP

**Goal**: A reviewer can open a case with white-light and fluorescence inputs, see fused evidence, and receive quality flags before export.

**Independent Test**: Load a representative sample pair and confirm the UI shows fused views, quality flags, and a candidate-region summary without requiring ROI editing or export.

### Tests for User Story 1

- [X] T023 [P] [US1] Add backend contract tests for `POST /cases`, `GET /cases/{case_id}`, and `POST /cases/{case_id}/inputs` in `backend/tests/contract/test_case_inputs_api.py`
- [X] T024 [P] [US1] Add backend unit tests for quality flag detection in `backend/tests/unit/test_quality_flags.py`
- [X] T025 [P] [US1] Add backend unit tests for analysis service fixture outputs in `backend/tests/unit/test_analysis_service.py`
- [X] T026 [P] [US1] Add frontend component tests for the case opening workflow in `frontend/tests/CaseOpenView.test.ts`
- [X] T027 [P] [US1] Add medical safety wording test for visible review boundary text in `frontend/tests/MedicalDisclaimer.test.ts`

### Implementation for User Story 1

- [X] T028 [US1] Implement case creation and retrieval endpoints in `backend/osteo_vision_api/api/cases.py`
- [X] T029 [US1] Implement input upload/import endpoint in `backend/osteo_vision_api/api/inputs.py`
- [X] T030 [US1] Implement local case metadata persistence in `backend/osteo_vision_api/domains/cases/repository.py`
- [X] T031 [US1] Implement input validation and quality flag mapping in `backend/osteo_vision_api/services/input_service.py`
- [X] T032 [US1] Implement fluorescence fusion call path using existing preprocessing logic in `backend/osteo_vision_api/services/analysis_service.py`
- [X] T033 [US1] Implement artifact manifest creation for overlay, heatmap, and normalized fluorescence in `backend/osteo_vision_api/core/artifacts.py`
- [X] T034 [US1] Implement frontend case open page in `frontend/src/pages/CaseOpenPage.vue`
- [X] T035 [US1] Implement frontend dual-channel input panel in `frontend/src/components/CaseInputPanel.vue`
- [X] T036 [US1] Implement frontend fusion viewer in `frontend/src/components/FusionViewer.vue`
- [X] T037 [US1] Implement frontend quality flag panel in `frontend/src/components/QualityFlagPanel.vue`
- [X] T038 [US1] Wire case loading state into `frontend/src/stores/caseStore.ts`
- [X] T039 [US1] Add user-facing platform safety-boundary disclaimer to `frontend/src/components/MedicalDisclaimer.vue`

**Checkpoint**: User Story 1 can be demonstrated independently with sample inputs and no export dependency.

---

## Phase 4: User Story 2 - Refine regions with physician review (Priority: P2)

**Goal**: A reviewer can draw or modify ROIs, accept or reject candidate regions, and see quantitative summaries update with review state.

**Independent Test**: Create or modify a region on a sample case and verify that metrics, review state, and review history update consistently.

### Tests for User Story 2

- [X] T040 [P] [US2] Add backend contract tests for `PATCH /cases/{case_id}/regions/{region_id}` and `POST /cases/{case_id}/review-events` in `backend/tests/contract/test_review_api.py`
- [X] T041 [P] [US2] Add backend unit tests for ROI metric calculation in `backend/tests/unit/test_roi_quantification.py`
- [X] T042 [P] [US2] Add backend unit tests for review-state transitions in `backend/tests/unit/test_review_state.py`
- [X] T043 [P] [US2] Add frontend component tests for ROI editing and review state changes in `frontend/tests/ReviewWorkspace.test.ts`

### Implementation for User Story 2

- [X] T044 [US2] Implement ROI schema and validation fields in `backend/osteo_vision_api/domains/cases/schemas.py`
- [X] T045 [US2] Implement ROI quantification service in `backend/osteo_vision_api/services/roi_service.py`
- [X] T046 [US2] Implement candidate region to ROI mapping in `backend/osteo_vision_api/services/review_service.py`
- [X] T047 [US2] Implement region update endpoint in `backend/osteo_vision_api/api/regions.py`
- [X] T048 [US2] Implement review event endpoint in `backend/osteo_vision_api/api/review_events.py`
- [X] T049 [US2] Persist review events and final review state in `backend/osteo_vision_api/domains/cases/repository.py`
- [X] T050 [US2] Implement frontend review workspace page in `frontend/src/pages/ReviewWorkspacePage.vue`
- [X] T051 [US2] Implement ROI drawing/selection component in `frontend/src/components/RoiCanvas.vue`
- [X] T052 [US2] Implement candidate region list component in `frontend/src/components/CandidateRegionList.vue`
- [X] T053 [US2] Implement review-state control component in `frontend/src/components/ReviewStateControls.vue`
- [X] T054 [US2] Implement quantitative summary component in `frontend/src/components/QuantificationPanel.vue`
- [X] T055 [US2] Wire ROI and review event actions into `frontend/src/stores/caseStore.ts`

**Checkpoint**: User Story 2 can be demonstrated after User Story 1 with manual ROI, candidate review, and quantitative update behavior.

---

## Phase 5: User Story 3 - Export an evidence bundle (Priority: P3)

**Goal**: A researcher or platform administrator can export reviewed case evidence with visuals, metrics, review states, warnings, and disclaimers.

**Independent Test**: Complete a reviewed sample case and verify that the evidence bundle includes visual artifacts, structured data, review state, warnings, and platform safety-boundary wording.

### Tests for User Story 3

- [X] T056 [P] [US3] Add backend contract tests for `POST /cases/{case_id}/exports` in `backend/tests/contract/test_export_api.py`
- [X] T057 [P] [US3] Add backend unit tests for report JSON and Markdown export content in `backend/tests/unit/test_export_service.py`
- [X] T058 [P] [US3] Add backend unit tests for artifact manifest checksums in `backend/tests/unit/test_artifact_manifest.py`
- [X] T059 [P] [US3] Add frontend component tests for export status and report links in `frontend/tests/ExportPanel.test.ts`
- [X] T060 [P] [US3] Add medical safety wording regression test for exported reports in `tests/unit/test_platform_report_safety.py`

### Implementation for User Story 3

- [X] T061 [US3] Implement export endpoint in `backend/osteo_vision_api/api/exports.py`
- [X] T062 [US3] Implement evidence bundle assembly in `backend/osteo_vision_api/services/export_service.py`
- [X] T063 [US3] Implement structured report JSON writer in `backend/osteo_vision_api/reports/platform_report.py`
- [X] T064 [US3] Implement Markdown report writer with disclaimer and review-state summary in `backend/osteo_vision_api/reports/platform_markdown.py`
- [X] T065 [US3] Implement quantification CSV writer in `backend/osteo_vision_api/reports/quantification_csv.py`
- [X] T066 [US3] Implement export artifact manifest and checksum generation in `backend/osteo_vision_api/core/artifacts.py`
- [X] T067 [US3] Persist export status and artifact references in `backend/osteo_vision_api/domains/cases/repository.py`
- [X] T068 [US3] Implement frontend export panel in `frontend/src/components/ExportPanel.vue`
- [X] T069 [US3] Implement frontend report preview page in `frontend/src/pages/ReportPreviewPage.vue`
- [X] T070 [US3] Wire export actions and artifact links into `frontend/src/stores/caseStore.ts`

**Checkpoint**: User Story 3 can be demonstrated with an exported evidence bundle and no unsupported diagnosis language.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete workflow, update documentation, and ensure generated artifacts stay in approved locations.

- [X] T071 [P] Update platform workflow documentation in `docs/architecture.md`
- [X] T072 [P] Update demo and validation instructions in `docs/quickstart.md`
- [X] T073 [P] Add the frontend/backend platform target to the current planning index and archive superseded task notes
- [X] T074 Add end-to-end smoke test for import → review → export in `tests/smoke/test_platform_case_workflow.py`
- [X] T075 Verify generated reports, JSON/CSV outputs, and preview assets are stored under `artifacts/` or `research/reports/` in `tests/unit/test_platform_artifact_locations.py`
- [X] T076 Verify large raw data, DICOM/NIfTI volumes, checkpoints, nnU-Net probability arrays, and transient artifacts are excluded from Git in `tools/check_project_readiness.py`
- [X] T077 Run `python tools/check_project_readiness.py`
- [X] T078 Run `python -m pytest tests/unit tests/smoke`
- [X] T079 Run frontend tests with the command defined in `frontend/package.json`
- [X] T080 Validate quickstart workflow in `specs/001-software-platform-target/quickstart.md`

---

## Phase 7: 2026-07-17 Three Priority Capabilities

**Purpose**: Deliver the safety-gated software closure for patient-conditioned evidence,
bone-activity spectrum review, and magnification-aware 3D registration before model retraining.

### Shared safety and contracts

- [X] T081 Freeze the three-capability target and order in `research/reports/planning/three_priority_capabilities_target_20260717_zh.md`
- [X] T082 Record long-term safety and delivery rules in `AGENTS.md`
- [X] T083 Require trusted identity for verified clinical context in `backend/osteo_vision_api/api/cases.py`
- [X] T084 Add verified clinical-context contract coverage in `backend/tests/contract/test_clinical_context_api.py`
- [X] T085 Propagate strict runtime configuration into review and prompt-fallback paths in `backend/osteo_vision_api/services/review_service.py`
- [X] T086 Decouple inference configuration resolution from artifact output root in `backend/osteo_vision_api/core/settings.py`
- [X] T087 Add strict-runtime regression coverage for temporary artifact roots in `backend/tests/unit/test_settings_runtime_paths.py`

### Patient-conditioned evidence and bone activity

- [X] T088 Implement clinical-context quality assessment and safe no-spatial-effect fallback in `backend/osteo_vision_api/services/clinical_context_assessment.py`
- [X] T089 Implement clinical-context frontend comparison and provenance UI in `frontend/src/components/ClinicalContextPanel.vue`
- [X] T090 Implement rule-derived bone-activity spectrum with trusted bone-gate degradation in `frontend/src/components/ViabilitySpectrumPanel.vue`
- [X] T091 Freeze the versioned clinical-context contract, missingness policy, and acceptance protocol in `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`
- [X] T092 Freeze the bone-activity label dictionary and physician arbitration SOP in `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`

### L1/L2 3D validation

- [X] T093 Validate transform existence, checksum, matrix, units, direction, and coordinate-chain continuity in `backend/osteo_vision_api/services/three_d_evidence.py`
- [X] T094 Validate registration error, threshold source, calibration range, and physician review in `backend/osteo_vision_api/services/three_d_evidence.py`
- [X] T095 Extend fail-closed navigation unit tests in `backend/tests/unit/test_three_d_evidence_service.py`
- [X] T096 Update navigation reason-code presentation in `frontend/src/components/NavigationSafetyStatusPanel.vue`
- [X] T097 Implement the L1 static registration adapter, backend job/API, frontend guide, and SERV-CT/phantom validation in `osteo_vision_core/`, `backend/`, and `frontend/`
- [X] T098 Implement pose-only offline pose-log composition and failure injection as a permanent L0 engineering diagnostic in `osteo_vision_core/`

### Data and final model phase

- [X] T099 Download the first traceable public/proxy datasets and manifests under `research/datasets/public-candidates/`
- [X] T100 Complete the approved starter dataset downloads and integrity/license review under `research/datasets/public-candidates/`; registered or oversized optional candidates remain tracked separately
- [ ] T101 Train and independently validate target-domain patient-conditioned segmentation after T083-T100 pass
- [ ] T102 Train and independently validate the target-domain bone-activity multitask model after T083-T100 pass
- [X] T103 Run the final engineering regression and update the target report: 250 backend tests, 535 core unit/smoke tests, 179 frontend tests with 1 skipped, Vue type-check, Vite build, full Ruff, and canonical `osteo_vision_core backend` mypy passed; the navigation route chunk is 61.97 kB and the heavyweight 3D viewport loads as a separate 709.67 kB async chunk
- [X] T104 Implement and smoke-test the patient-conditioned segmentation architecture on grouped non-target-domain proxy data without runtime promotion
- [X] T105 Implement and smoke-test the bone-activity multitask architecture on grouped non-target-domain proxy data without runtime promotion
- [X] T106 Implement fail-closed target-domain promotion verification with policy status, evidence hashes, split recomputation, trusted physician review, calibration, subgroup audit, and capability-specific safety metrics
- [ ] T107 Approve the target-domain metric policy and run T101/T102 on admitted physician-reviewed jaw-osteomyelitis data before any runtime replacement
- [X] T108 Audit and download bounded patient-conditioning, bone-activity, and navigation gap resources as D077-D089; record governance, license, source, size, SHA256, and non-target-domain boundaries
- [X] T109 Run and register the D086 24-case dental-landmark L1 proxy benchmark with noise and failure injection while blocking physical-accuracy claims
- [X] T110 Materialize D083 public bone-graft ICG video evidence with archive integrity, MP4 derivation, whole-duration keyframes, strict-model signal segmentation, temporal quantification, dark-baseline QC, and closed target-domain claims
- [X] T111 Materialize and train the five-patient KiTS23 CT/mask/clinical-context public proxy with canonical orientation, patient-level splits, 288-batch bounded conditioning, a failed no-harm gate, and runtime promotion closed
- [X] T112 Unify nine dataset manifests and extend machine validation to the full required provenance field set
- [X] T113 Implement calibrated microscope-camera PnP, independent reprojection gating, composed CBCT-to-camera transforms, frontend evidence entry, and fail-closed L1 phantom validation
- [X] T114 Implement and run focused regression for the strict L2 software gate: checksum-bound admitted MP4 and pose manifest, independent measurement and threshold-policy artifacts, FFprobe PTS-derived FPS, read-time integrity checks, persisted validated L1 camera evidence, per-frame 3D-to-2D projection, trusted physician review, overlay SHA256, failed-rerun revocation, and fail-closed L0 degradation
- [ ] T115 Validate L1/L2 physical accuracy on a real mandible phantom with independently measured dynamic ground truth, approve protocol thresholds, complete physician review, and record a durable navigation artifact before any physical-navigation claim
- [X] T116 Implement the v2 multi-entry calibration-table contract, manifest `calibration_table_id` binding, bounded `nearest_validated_entry_v1` selection, per-frame selection evidence, VFR rejection, and focused backend regression
- [ ] T117 Acquire real-device 4K calibration across the full magnification and working-distance range, independently validate entry coverage and selection error, and approve any future interpolation method before physical use
- [X] T118 Reduce the `NavigationWorkspacePage` Vite chunk warning with route-level or component-level code splitting while preserving navigation tests, type-check, and production build behavior
- [X] T119 Restrict patient-conditioned spatial effects to promoted target-domain runs with verified clinical context, physician-reviewed bone, image uncertainty, and exact image-only fallback
- [X] T120 Suppress bone-activity scores and class probabilities across abstention/ignore regions and fail closed on non-finite model output
- [X] T121 Bind L1 validation to a versioned SHA256 registration manifest, parseable model and independent point artifact; keep manual entry L0-only and revoke stale L2 active evidence after failed L1 reruns
- [X] T122 Selectively extract and verify the D069 MMDental clinical table and one paired dental CBCT from its 68 GB ZIP64 archive; validate NIfTI import and fail-closed hard-tissue proxy modeling with hash-bound evidence, aggregate-only inspection, and closed target-domain training/navigation admission
- [X] T123 Materialize the five-sample D074 human PpIX microscope fluorescence proxy with source/archive/derived-file integrity, patient-group separation, rule-derived bone-activity targets, and explicit non-jaw/non-ICG/non-target-domain boundaries
- [X] T124 Train the D074 bone-activity proxy and freeze bone-gate and abstention thresholds on validation data only; record full scans, reuse thresholds once on test, require selective-error and coverage gates, and keep runtime replacement closed after frozen-test failure
- [X] T125 Strengthen patient-conditioned manifest training with per-image SHA256, byte-size, dimension, binary-mask, promotion-policy provenance, and a fresh KiTS23 run that remains blocked by the no-harm gate
- [X] T126 Bind L1/L2 coordinate frames to handedness, axis direction, unit, source, and matrix convention; reject missing or conflicting frame provenance and degrade all affected overlays to L0
- [X] T127 Harden three-priority promotion against negative safety metrics, all-abstention metric inflation, untrusted approved-policy declarations, ineligible proxy metrics, threshold-scan tampering, zero-support class Dice, and case/source/derived-asset split leakage while keeping the approved-policy trust store closed until T107
- [X] T128 Generate checkpoint-bound patient-conditioned split, prediction, calibration, subgroup, safety, and physician-review evidence artifacts; bind source/canonical affine and spacing, compute physical boundary Hausdorff distance, and preserve no-harm, 2 mm boundary, target-domain, institution/time, and trusted-review blockers
- [X] T129 Selectively materialize the SHA256-bound D087 C3VD official archive with safe member-path checks, per-file size/SHA256/CRC evidence, explicit colon-phantom/non-jaw/non-fluorescence boundaries, and closed training/navigation admission
- [X] T130 Deterministically deduplicate the two D087 pose timestamps with source-row hashes and a keep-last audit, then bind all 766 RGB/depth frames to unique poses under an explicit 10 ms tolerance with unmatched and ambiguous counts
- [X] T131 Implement C3VD Scaramuzza OCamCalib polynomial-v1 projection, validate it against independent fixed numeric vectors, and run fail-closed offline proxy replay with tracking-loss, time-offset, and drift failure injections
- [X] T132 Remove visible input-path compaction from the case archive and enforce complete wrapping through frontend regression coverage
- [X] T133 Replace the deprecated Three.js soft-shadow mode and verify the lazy-loaded desktop 3D workbench with a real STL, zero browser warnings, nonblank canvas pixels, and measurable auto-rotation frame changes
- [X] T134 Recompute all T107 promotion metrics from checkpoint-bound, SHA256-bound per-case prediction and physician-reviewed ground-truth assets; reject tampering, missing assets, split mismatch, all-abstention inflation, zero class support, no-harm failure, and physical-boundary violations
- [X] T135 Implement authenticated append-only Ed25519 promotion approvals with physician/project-reviewer dual signatures, nonce replay prevention, revocation, trusted-key lifecycle checks, offline key/signing tooling, exact evidence-target binding, API bundle export, and independent final-gate replay; keep the production trust store empty until T107 external evidence and policy approval are complete
- [X] T136 Upgrade strict L2 to pose-manifest v3 and threshold-policy v2; bind FFprobe-PTS magnification/working-distance rates, intrinsics-switch rate, calibration ambiguity, and A/B/A oscillation to nine approved safety parameters, fail closed to L0, persist frame/summary evidence, and expose the result in the frontend
- [X] T137 Download, inspect, and register D090 three-video human breast sentinel-node ICG and D091 two-video human hepatic ICG proxies; extend unified provenance verification to 11 manifests, 43 records, 106 files, and 5,437,811,619 verified bytes while preserving non-jaw, non-target-domain, and training-ineligible boundaries
- [X] T138 Synchronize trusted physician-reviewed `ignore` annotations into candidate, frame, video-manifest, artifact, and `bone_activity_spectrum-v2` evidence; reject untrusted states and fail closed on source, dimension, mask-integrity, or checksum mismatch
- [X] T139 Implement the SHA256-bound `PatientConditionedSegmenterAdapter`, evidence outputs, and image-only safety fallback; register the KiTS23 proxy as a development-only explicit candidate, verify the registered checkpoint end to end with generated evidence, exact conditioned/image-only equality, zero delta, and runtime replacement closed, and keep it absent from the strict platform configuration
- [X] T140 Integrate patient-conditioned comparison into `AnalysisService`, API routes, and the local job worker; select exactly one trusted accepted/modified `exposed_bone` annotation bound to the active white-light JPEG, persist artifacts and reason codes, and fail closed on ambiguous or invalid gates
- [X] T141 Expose patient-conditioned image-only, conditioned, difference, uncertainty, provenance, and fallback evidence in the case workspace plus structured JSON, Markdown, quantification CSV, and export bundle regression coverage
- [X] T142 Make the official 4K proxy pair deterministically registration-verifiable, bind input SHA256, official profile and registration evidence into the strict platform summary, execute the development patient-conditioned checkpoint on the registered pair, verify four 4K evidence images with exact image-only fallback, localize all safety reasons, and complete day/night desktop browser QA
- [X] T143 Reconfirm the three capabilities as fixed continuing goals, assign public/proxy dataset acquisition to the project side, register D092 PMCanalSeg and D093 MRONJ SPECT/CT figure assets, and extend unified provenance verification to 13 manifests
- [X] T144 Implement `clinical-feature-vector-v1` with explicit list completeness, present/missing/OOD masks, runtime rebuild and checksum validation, checkpoint-consumed versus spatially-applied evidence, frontend visibility, and JSON/Markdown/CSV export coverage without retraining
- [X] T145 Run the D036 public-label digital mandible through the real FastAPI L1/L2 path with checksum-bound evidence, dual-calibration selection, same-L1-chain verification, tamper rejection, physician-review fallback to L0, and closed physical/navigation claims
- [X] T146 Expand `clinical-feature-vector-v1` to the 13-feature platform union, bind encoder schema/version and per-feature source evidence across training manifests, checkpoints and runtime, preserve safe checkpoint-subset projection, and reject incompatible or tampered contracts without enabling spatial conditioning
- [X] T147 Upgrade physician annotation export and downstream admission to `osteo-vision-manual-annotation-training-manifest-v2`, require admitted checksum-verified institutional inputs plus explicit training authorization, deidentification, mapping custody and independent physician review, and decouple case-level reviewed ignore application from training rights
- [X] T148 Download, checksum, license-audit and register D094 ClinRad ORNJ and D095 MDACC ORNJ patient-context datasets, extend unified verification to 15 manifests / 47 records / 138 files, and keep both sources outside target-domain training admission
- [X] T149 Implement the checksum-bound D074 bone-activity checkpoint runtime and adapter, require explicit selection and target-domain/promotion/registration/physician gates, emit engineering evidence only, and keep spatial class maps, continuous scores and runtime replacement closed
- [X] T150 Integrate the explicit D074 checkpoint candidate into `AnalysisService`, persist checksum-bound JSON/NPZ artifacts, expose separate JSON/Markdown/CSV/ZIP and frontend engineering evidence, reject unsafe proxy spatial outputs at the platform layer, and keep target-domain/runtime promotion closed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1; blocks all user-story implementation.
- **Phase 3 User Story 1**: Depends on Phase 2; delivers MVP import and review display.
- **Phase 4 User Story 2**: Depends on Phase 3 for loaded case state and visible fusion outputs.
- **Phase 5 User Story 3**: Depends on Phase 4 for final review states and quantitative summaries.
- **Phase 6 Polish**: Depends on all desired user stories.

### User Story Dependencies

- **US1 Review a dual-channel case**: MVP and prerequisite for the rest.
- **US2 Refine regions with physician review**: Builds on US1 case loading and fusion output.
- **US3 Export an evidence bundle**: Builds on US1 artifacts and US2 review state.

### Within Each User Story

- Tests before implementation.
- Backend schemas before services.
- Services before endpoints.
- Endpoints before frontend integration.
- Frontend store changes before page-level workflow validation.

---

## Parallel Opportunities

- Setup tasks T004, T005, T007, and T008 can run in parallel after directory creation.
- Foundational tasks T018 through T021 can run in parallel with backend service interface tasks T012 through T017.
- US1 tests T023 through T027 can run in parallel.
- US2 tests T040 through T043 can run in parallel.
- US3 tests T056 through T060 can run in parallel.
- Documentation tasks T071 through T073 can run in parallel with final validation tasks after implementation.

## Parallel Example: User Story 1

```text
Task: T023 Contract tests in backend/tests/contract/test_case_inputs_api.py
Task: T024 Quality flag tests in backend/tests/unit/test_quality_flags.py
Task: T026 Frontend case opening tests in frontend/tests/CaseOpenView.test.ts
Task: T027 Medical disclaimer tests in frontend/tests/MedicalDisclaimer.test.ts
```

## Parallel Example: User Story 2

```text
Task: T040 Review API contract tests in backend/tests/contract/test_review_api.py
Task: T041 ROI quantification tests in backend/tests/unit/test_roi_quantification.py
Task: T043 Review workspace component tests in frontend/tests/ReviewWorkspace.test.ts
```

## Parallel Example: User Story 3

```text
Task: T056 Export API contract tests in backend/tests/contract/test_export_api.py
Task: T057 Report export tests in backend/tests/unit/test_export_service.py
Task: T059 Export panel component tests in frontend/tests/ExportPanel.test.ts
Task: T060 Report safety wording test in tests/unit/test_platform_report_safety.py
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Implement only Phase 3.
3. Validate that a representative dual-channel case opens, shows fusion outputs, displays quality flags, and preserves platform safety-boundary wording.
4. Demo US1 before building ROI review or export.

### Incremental Delivery

1. US1: import and review display.
2. US2: ROI and physician review state.
3. US3: evidence bundle export.
4. Polish: full workflow checks, docs, and artifact governance.

### Validation Commands

```powershell
python tools/audit_active_documentation.py
python -m pytest tests/unit tests/smoke
python -m backend.osteo_vision_api.main
npm --prefix frontend run dev
python tools/check_project_readiness.py
python tools/benchmark_core_hotpaths.py --output artifacts/performance/core_hotpaths_current.json
```

## Notes

- Gradio remains a temporary legacy bridge; the target UI is the Vue frontend with the FastAPI backend.
- Default local ports are frontend `5174` and backend `8001`.
- The platform excludes live device SDKs, hospital system integration, and automatic diagnosis from its software boundary.
- Keep model and dataset choices replaceable through configuration, adapters, and service boundaries.
- Large medical data, checkpoints, and transient experiment outputs must not be staged for Git.
