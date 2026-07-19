# Osteo Vision Export Schema V1

本文件描述当前平台使用的导出 schema v1 病例证据包结构。schema 版本与平台发布版本独立演进。该结构用于科研、比赛和受控演示，不能作为临床诊断报告或正式 DICOM SR/SEG 实现。

## 适用范围

- 入口接口：`POST /cases/{case_id}/exports`
- 当前后端实现：`backend/src/services/export_service.py`
- 当前响应模型：`backend/src/domains/cases/schemas.py::ExportResponse`
- 当前导出格式：本地 evidence bundle ZIP、JSON 报告、Markdown 报告、量化 CSV、DICOM Secondary Capture、manifest。

## ExportResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `case_id` | string | 被导出的病例 ID。 |
| `bundle_path` | string | evidence bundle ZIP 的本地路径。 |
| `report_path` | string | 结构化 JSON 报告路径。 |
| `manifest_path` | string | 导出 manifest 路径。 |
| `dicom_path` | string/null | DICOM Secondary Capture 文件路径；当前不是 DICOM SR/SEG。 |
| `summary` | object | 导出摘要，见 `ExportSummary`。 |
| `artifact_entries` | array | 核心导出文件和随病例附带 artifact 的条目列表。 |

## ExportSummary

当前 `summary.schema_version` 为 `osteo-vision-export-summary-v1`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 导出摘要 schema 版本。 |
| `case_id` | string | 病例 ID。 |
| `analysis_run_count` | integer | 病例中分析运行数量。 |
| `candidate_region_count` | integer | 所有分析运行产生的候选区域总数。 |
| `core_artifact_count` | integer | 本次导出的核心文件数量，通常包括 JSON/Markdown/DICOM/CSV/manifest/ZIP。 |
| `included_artifact_count` | integer | 从病例已有 artifacts 中纳入 bundle 的文件数量。 |
| `total_artifact_count` | integer | `core_artifact_count + included_artifact_count`。 |
| `quantification_row_count` | integer | 量化 CSV 中写入的行数。 |
| `bundle_size_bytes` | integer/null | evidence bundle ZIP 文件大小。 |
| `formats` | string[] | 本次导出包含的 artifact kind 去重列表。 |
| `dicom_included` | boolean | 是否包含 DICOM Secondary Capture。 |

## ArtifactEntry

`artifact_entries` 中每一项使用以下通用字段。部分核心文件没有 `artifact_id`，病例派生 artifact 通常包含 `artifact_id`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `artifact_id` | string/optional | artifact ID。 |
| `kind` | string | artifact 类型。 |
| `path` | string | 本地文件路径。 |
| `checksum` | string/null | 文件校验值，当前为 SHA-256。 |
| `exists` | boolean/optional | 生成 manifest 时文件是否存在。 |
| `size_bytes` | integer/null/optional | 文件大小。 |
| `extra` | object/optional | 预留扩展字段。 |

当前可出现的 `kind`：

- `report_json`
- `report_md`
- `dicom_secondary_capture`
- `quantification_csv`
- `review_manifest_json`
- `review_manifest_csv`
- `bundle_manifest`
- `evidence_bundle`
- `overlay`
- `video_overlay`
- `video_mask`
- `video_segmentation_manifest`
- `probability_map`
- `heatmap`
- `normalized_fluorescence`
- `colorbar`
- `roi_mask`
- `keyframe`

其中 MP4 关键帧分割闭环会额外输出：

- `video_segmentation_manifest`：记录源 MP4、抽取关键帧、每帧二值掩膜、概率图、伪彩/叠加图、候选区和医学边界。
- `video_overlay`：由关键帧荧光伪彩叠加图串成的复核 MP4，便于快速浏览“分割 + 荧光叠加”效果。
- `video_mask`：由关键帧二值 mask 串成的复核 MP4，便于检查模型/规则分割区域。

`video_segmentation_manifest.frames[]` 还应保留：

- `spatial_mapping`：mask/evidence/source video 的坐标空间、宽高、mask 到源视频坐标的缩放比例、源视频像素坐标 bbox 和归一化 bbox。
- `temporal_stability`：三帧滑动统计、阳性面积波动、bbox 中心漂移和闪烁风险。该字段只用于复核稳定性提示，当前不会修改 mask。

## Bundle Manifest

ZIP 内的 `reports/{case_id}_bundle_manifest.json` 记录 evidence bundle 的组成。

| 字段 | 类型 | 说明 |
|---|---|---|
| `case_id` | string | 病例 ID。 |
| `report_json` | string | JSON 报告路径。 |
| `report_md` | string | Markdown 报告路径。 |
| `dicom_secondary_capture` | string | DICOM SC 路径。 |
| `quantification_csv` | string | CSV 路径。 |
| `review_manifest_json` | string | 医生复核/候选区沉淀 manifest JSON 路径。 |
| `review_manifest_csv` | string | 医生复核/候选区沉淀 manifest CSV 路径。 |
| `included_artifacts` | array | 纳入 bundle 的病例 artifacts。 |
| `disclaimer` | object | 平台安全边界免责声明和版本。 |

## JSON Report

JSON 报告由 `backend/src/reports/platform_report.py` 生成，包含：

- 病例快照：`case`、`case_id`、`title`、`status`、`created_at`、`updated_at`。
- 安全边界：`disclaimer_version`、`disclaimer`、`icg_signal_limitation`。
- 输入和质量：`inputs`、`quality_flags`、`warnings`。
- 分析结果：`analysis_runs`、`latest_analysis_run`。
- 医生复核：`rois`、`review_events`、`review_summary`。
- 证据文件：`artifacts`。
- 导出元数据：`export_meta`、`generated_at`。

## Quantification CSV

CSV 由 `backend/src/reports/quantification_csv.py` 写出。当前每个 analysis run 生成一行，至少包含：

- `case_id`
- `run_id`
- `roi_id`
- analysis run 的 `quantitative_summary` 展开字段
- `review_state`

后续若进入正式多 ROI 量化，应将每个 ROI 的指标拆成独立行，并补充 `roi_id`、`candidate_id`、`review_state` 和 reviewer 事件关联。

## Review Manifest

导出时会额外生成：

- `{case_id}_review_manifest.json`
- `{case_id}_review_manifest.csv`

它们用于把 AI 候选区、医生 ROI 和复核事件沉淀为可追溯的训练反馈/错误分析材料。该 manifest 不是临床标注金标准；只有经过医生明确复核、脱敏和数据治理后，才可进入后续模型再训练。

JSON 顶层字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 当前为 `osteo-vision-review-manifest-v1`。 |
| `case_id` | string | 病例 ID。 |
| `training_use` | object | 是否可用于复核回灌训练、是否需要医生复核、非目标域风险说明。 |
| `summary` | object | ROI、候选区、复核事件数量统计。 |
| `candidates` | array | AI 候选区，包含 `candidate_id`、`run_id`、分数、帧索引、bbox、mask/overlay 路径和时序稳定性元数据。 |
| `rois` | array | 医生或 AI 推广生成的 ROI，包含 `roi_id`、`candidate_id`、`geometry`、`label`、`review_state` 和指标。 |
| `review_events` | array | 医生复核动作事件，包含动作、目标、前后状态、时间戳和备注。 |

CSV 每行按 `record_type` 区分 `candidate_region`、`roi` 和 `review_event`，关键字段包括 `roi_id`、`candidate_id`、`review_state`、`label`、`frame_index`、`timestamp_sec`、`bbox_xyxy`、`geometry`、`mask_path`、`overlay_path` 和 `medical_boundary`。

## DICOM Boundary

当前 `dicom_secondary_capture` 是 DICOM Secondary Capture：

- 目标是把病例证据摘要写成可归档的派生图像。
- 已写入去标识化相关字段，例如 `PatientIdentityRemoved=YES`。
- `PatientID` 使用病例 ID 派生，不能包含真实患者身份。
- 当前不是 DICOM Structured Report，也不是 DICOM SEG。
- 不承载临床诊断、分割标签标准编码或 PACS 级互操作承诺。

下一阶段若要把标准化输出作为扩展亮点，应新增：

- DICOM SR 字段映射草案。
- DICOM SEG mask 映射草案。
- JSON/CSV 与 DICOM UID 的稳定关联。
- DICOM validator 或至少 pydicom 读取回归测试。

## 安全和治理要求

- 所有导出必须保留平台安全边界免责声明。
- ICG 信号只能表述为灌注、组织活性或风险提示证据，不能写成颌骨骨髓炎特异性诊断。
- evidence bundle 可用于竞赛评审和科研复查，不得直接作为临床诊断结论。
- 原始医疗影像、大型视频、checkpoint 和患者身份信息不得进入 Git。
