---
description: "Task list for Osteo Vision software platform target"
---

# Tasks: Osteo Vision Software Platform Target

**Input**: Design documents from `/specs/001-software-platform-target/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`

**Tests**: Tests are included because the constitution and plan require independently verifiable case workflow, medical safety wording, artifact export, and regression checks.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and demonstrated independently.

**Clarification Assumption**: V1 assumes local single-user operation with de-identified samples and local evidence bundles. If the access model changes later, update `spec.md`, `data-model.md`, and this task list before implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other tasks in the same phase when files do not overlap
- **[Story]**: User-story label, used only in user-story phases
- Every task includes an exact repository-relative file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the split frontend/backend shape while keeping the existing `src/` analysis core available.

- [X] T001 Create frontend project skeleton directories in `frontend/src/`, `frontend/tests/`, and `frontend/public/`
- [X] T002 Create backend service skeleton directories in `backend/src/`, `backend/tests/`, and `backend/src/api/`
- [X] T003 Create frontend package metadata and scripts in `frontend/package.json`
- [X] T004 [P] Create frontend TypeScript and Vite configuration in `frontend/tsconfig.json` and `frontend/vite.config.ts`
- [X] T005 [P] Create frontend test configuration in `frontend/vitest.config.ts`
- [X] T006 Create backend package markers in `backend/src/__init__.py` and `backend/tests/__init__.py`
- [X] T007 [P] Create backend app settings module in `backend/src/core/settings.py`
- [X] T008 [P] Create backend application factory in `backend/src/api/app.py`
- [X] T009 Document local single-user V1 assumption in `specs/001-software-platform-target/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared data contracts, storage paths, disclaimers, and service boundaries needed by all user stories.

**CRITICAL**: No user-story implementation should begin until this phase is complete.

- [X] T010 Create case domain dataclasses or Pydantic schemas in `backend/src/domains/cases/schemas.py`
- [X] T011 Create quality flag and review-state enums in `backend/src/domains/cases/enums.py`
- [X] T012 Create local artifact path manager in `backend/src/core/artifacts.py`
- [X] T013 Create research-prototype disclaimer constants in `backend/src/core/disclaimers.py`
- [X] T014 Create case repository interface for local filesystem/SQLite-backed metadata in `backend/src/domains/cases/repository.py`
- [X] T015 Create analysis service interface that wraps existing shared `src/preprocess/` and `src/pipelines/` boundaries in `backend/src/services/analysis_service.py`
- [X] T016 Create report/export service interface in `backend/src/services/export_service.py`
- [X] T017 Create API router registration module in `backend/src/api/routes.py`
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

- [X] T028 [US1] Implement case creation and retrieval endpoints in `backend/src/api/cases.py`
- [X] T029 [US1] Implement input upload/import endpoint in `backend/src/api/inputs.py`
- [X] T030 [US1] Implement local case metadata persistence in `backend/src/domains/cases/repository.py`
- [X] T031 [US1] Implement input validation and quality flag mapping in `backend/src/services/input_service.py`
- [X] T032 [US1] Implement fluorescence fusion call path using existing preprocessing logic in `backend/src/services/analysis_service.py`
- [X] T033 [US1] Implement artifact manifest creation for overlay, heatmap, and normalized fluorescence in `backend/src/core/artifacts.py`
- [X] T034 [US1] Implement frontend case open page in `frontend/src/pages/CaseOpenPage.vue`
- [X] T035 [US1] Implement frontend dual-channel input panel in `frontend/src/components/CaseInputPanel.vue`
- [X] T036 [US1] Implement frontend fusion viewer in `frontend/src/components/FusionViewer.vue`
- [X] T037 [US1] Implement frontend quality flag panel in `frontend/src/components/QualityFlagPanel.vue`
- [X] T038 [US1] Wire case loading state into `frontend/src/stores/caseStore.ts`
- [X] T039 [US1] Add user-facing research-prototype disclaimer to `frontend/src/components/MedicalDisclaimer.vue`

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

- [X] T044 [US2] Implement ROI schema and validation fields in `backend/src/domains/cases/schemas.py`
- [X] T045 [US2] Implement ROI quantification service in `backend/src/services/roi_service.py`
- [X] T046 [US2] Implement candidate region to ROI mapping in `backend/src/services/review_service.py`
- [X] T047 [US2] Implement region update endpoint in `backend/src/api/regions.py`
- [X] T048 [US2] Implement review event endpoint in `backend/src/api/review_events.py`
- [X] T049 [US2] Persist review events and final review state in `backend/src/domains/cases/repository.py`
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

**Independent Test**: Complete a reviewed sample case and verify that the evidence bundle includes visual artifacts, structured data, review state, warnings, and research-prototype wording.

### Tests for User Story 3

- [X] T056 [P] [US3] Add backend contract tests for `POST /cases/{case_id}/exports` in `backend/tests/contract/test_export_api.py`
- [X] T057 [P] [US3] Add backend unit tests for report JSON and Markdown export content in `backend/tests/unit/test_export_service.py`
- [X] T058 [P] [US3] Add backend unit tests for artifact manifest checksums in `backend/tests/unit/test_artifact_manifest.py`
- [X] T059 [P] [US3] Add frontend component tests for export status and report links in `frontend/tests/ExportPanel.test.ts`
- [X] T060 [P] [US3] Add medical safety wording regression test for exported reports in `tests/unit/test_platform_report_safety.py`

### Implementation for User Story 3

- [X] T061 [US3] Implement export endpoint in `backend/src/api/exports.py`
- [X] T062 [US3] Implement evidence bundle assembly in `backend/src/services/export_service.py`
- [X] T063 [US3] Implement structured report JSON writer in `backend/src/reports/platform_report.py`
- [X] T064 [US3] Implement Markdown report writer with disclaimer and review-state summary in `backend/src/reports/platform_markdown.py`
- [X] T065 [US3] Implement quantification CSV writer in `backend/src/reports/quantification_csv.py`
- [X] T066 [US3] Implement export artifact manifest and checksum generation in `backend/src/core/artifacts.py`
- [X] T067 [US3] Persist export status and artifact references in `backend/src/domains/cases/repository.py`
- [X] T068 [US3] Implement frontend export panel in `frontend/src/components/ExportPanel.vue`
- [X] T069 [US3] Implement frontend report preview page in `frontend/src/pages/ReportPreviewPage.vue`
- [X] T070 [US3] Wire export actions and artifact links into `frontend/src/stores/caseStore.ts`

**Checkpoint**: User Story 3 can be demonstrated with an exported evidence bundle and no unsupported diagnosis language.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete workflow, update documentation, and ensure generated artifacts stay in approved locations.

- [X] T071 [P] Update platform workflow documentation in `docs/architecture.md`
- [X] T072 [P] Update demo and validation instructions in `docs/quickstart.md`
- [X] T073 [P] Add a planning report for the frontend/backend platform target in `research/reports/planning/software_platform_target_tasks_zh.md`
- [X] T074 Add end-to-end smoke test for import → review → export in `tests/smoke/test_platform_case_workflow.py`
- [X] T075 Verify generated reports, JSON/CSV outputs, and preview assets are stored under `artifacts/` or `research/reports/` in `tests/unit/test_platform_artifact_locations.py`
- [X] T076 Verify large raw data, DICOM/NIfTI volumes, checkpoints, nnU-Net probability arrays, and transient artifacts are excluded from Git in `tools/check_project_readiness.py`
- [X] T077 Run `python check_env.py`
- [X] T078 Run `python -m pytest tests/unit tests/smoke`
- [X] T079 Run frontend tests with the command defined in `frontend/package.json`
- [X] T080 Validate quickstart workflow in `specs/001-software-platform-target/quickstart.md`

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
3. Validate that a representative dual-channel case opens, shows fusion outputs, displays quality flags, and preserves research-prototype wording.
4. Demo US1 before building ROI review or export.

### Incremental Delivery

1. US1: import and review display.
2. US2: ROI and physician review state.
3. US3: evidence bundle export.
4. Polish: full workflow checks, docs, and artifact governance.

### Validation Commands

```powershell
python check_env.py
python -m pytest tests/unit tests/smoke
python -m backend.src.main
npm --prefix frontend run dev
python tools/check_project_readiness.py
```

## Notes

- Gradio remains a temporary legacy bridge; the target UI is the Vue frontend with the FastAPI backend.
- Default local ports are frontend `5174` and backend `8001`.
- V1 avoids live device SDKs, hospital system integration, and automatic diagnosis.
- Keep model and dataset choices replaceable through configuration, adapters, and service boundaries.
- Large medical data, checkpoints, and transient experiment outputs must not be staged for Git.
