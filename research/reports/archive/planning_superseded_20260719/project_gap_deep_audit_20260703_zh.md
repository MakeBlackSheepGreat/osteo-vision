# 项目深度缺口自查：工程、前后端与模型

日期：2026-07-03

说明：本报告把“真实 4K 术中白光/ICG MP4/JPEG 缺失”和“医生关键帧 ROI 标注暂时做不了”作为已知暂缓项，不再反复展开；重点列其他可推进、可修复、可评估的缺口。

## 1. 本轮核验命令

| 检查项 | 结果 |
|---|---|
| `conda run -n osteo-vision python -m pytest -q` | 通过，83 个测试通过。 |
| `npm --prefix frontend run build` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过，4 个测试通过。 |
| `npm --prefix frontend run typecheck` | 通过，使用 `vue-tsc --noEmit`。 |
| `npm test` | 通过，已改为调用前端测试。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `black --check` / `isort --check-only`（本轮核心改动文件范围） | 通过；未对大型历史 benchmark 脚本做全量格式化，避免无关 diff。 |
| `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml` | `d025_lesion_smoke_segmenter` 与 `fixture_default` 可用；D025 是 CBCT 病灶 ROI 代理 smoke 模型。nnU-Net、MedSAM-like、BiomedCLIP 仍明确标记为 adapter 推理未实现，且缺 checkpoint；BiomedCLIP 还缺 `open_clip`。 |
| `conda run -n osteo-vision python scripts/train_d025_lesion_smoke_model.py --max-train-batches 2 --max-val-cases 2 --max-train-cases 8 --base-channels 2 --device cpu` | 通过；生成 D025 代理 checkpoint、manifest、model card 和中英文建模报告。 |
| `conda run -n osteo-vision python -m pytest backend/tests/unit/test_export_service.py backend/tests/contract/test_export_api.py -q` | 通过；导出 zip 中已包含最小 DICOM Secondary Capture，并可由 pydicom 读取。 |
| `conda run -n osteo-vision python -m pytest backend/tests/unit/test_job_service.py backend/tests/contract/test_case_inputs_api.py backend/tests/contract/test_export_api.py backend/tests/unit/test_export_service.py -q` | 通过；后台 job 可落盘，完成任务可在 registry 重建后查询，未完成任务重启后会标记失败并说明中断。 |
| `conda run -n osteo-vision python -m pytest backend/tests/unit/test_video_library_service.py backend/tests/contract/test_case_inputs_api.py -q` | 通过；公开视频候选清单可被后端读取，MP4 候选可一键导入病例 video input。 |
| `npm --prefix frontend run typecheck` / `npm --prefix frontend test -- --run` / `npm --prefix frontend run build` | 通过；前端左侧控制面板已具备加载公开视频候选、选择候选和导入病例的最小入口。 |
| `conda run -n osteo-vision python -c "...VideoLibraryService(...).list_candidates(...)"` | 真实 `video_download_manifest_20260703.csv` 当前识别到 21 条本地存在且系统可读的 MP4 候选。 |
| `conda run -n osteo-vision python scripts/prepare_ofdvdnet_dataset.py` | 通过；OFDVDnet `data.zip` 已解压并生成详细 manifest、前端视频库 combined manifest、三视图预览和中英文报告。50 个视频中 48 个可读，2 个保留错误记录但不进入可导入候选。 |
| `conda run -n osteo-vision python -c "...load_settings(); VideoLibraryService(...).list_candidates(...)"` | 通过；后端默认读取 `video_library_manifest_20260704.csv`，当前可导入视频候选 69 条，其中 OFDVDnet 48 条。 |
| `conda run -n osteo-vision python tools/run_platform_smoke.py` | 通过；生成病例、上传白光/ICG、运行融合、上传 MP4、后台关键帧分析、导出 zip 证据包和 DICOM Secondary Capture。最近摘要：`artifacts/platform_smoke/20260703T161913Z/platform_smoke_summary.json`。 |

## 2. 后端缺口

### B1. 视频处理已具备后台任务入口，并补了 JSON 持久化 job registry

相关文件：

- `backend/src/api/uploads.py`
- `backend/src/services/analysis_service.py`
- `backend/src/services/job_service.py`
- `src/preprocess/video.py`

已完成基础修复：

- `/uploads/raw` 对视频默认只保存文件和读取元数据，关键帧抽取进入后台 job，并可通过 `/uploads/jobs/{job_id}` 查询。
- 新增 `/cases/{case_id}/analysis-jobs` 和 `/analysis-jobs/{job_id}`，MP4 关键帧分析可走后台任务。
- 前端 MP4 上传会轮询 keyframe job，MP4 分析会走后台 analysis job。
- `JobRegistry` 已从纯内存改为 `artifacts/platform/jobs/jobs.json` JSON 落盘；完成/失败任务可在服务重建后查询。若服务在 job 未完成时重启，未完成任务会标记为 failed，并写入 “Job did not complete before process restart.”，避免前端持续等待。

剩余缺口：当前仍不是 Celery/RQ/数据库级任务队列；没有取消、重试、任务优先级、并发 worker 管理和长视频分片进度。`MAX_VIDEO_UPLOAD_BYTES` 仍固定为 1GB，真实 4K 长视频可能超过该体量。

### B2. 视频关键帧证据链仍需增强

已完成基础修复：`src/preprocess/video.py` 现在同时输出最长边 1280 的预览帧和原始分辨率证据帧，并记录帧号、时间戳、预览/证据尺寸和基础质量指标。

剩余缺口：证据帧目前仍是高质量 JPEG，不是无损序列；还没有医生时间点、荧光峰值或运动质量驱动的抽帧策略。

### B3. 视频抽帧策略太粗

当前只有 uniform sampling。赛题场景需要至少补：

- 医生指定时间点抽帧。
- 按荧光强度峰值或变化率抽帧。
- 按模糊/过曝/遮挡过滤。
- 输出帧号、时间戳、采样策略和质量评分。

### B4. 文件校验仍需强化

已完成基础修复：`.mp4` 现在会通过 OpenCV 检查是否可打开、是否有有效尺寸、帧数和可解码帧；伪装成 MP4 的 HTML/reCAPTCHA 文件会被拒绝。

剩余缺口：

- MIME/content sniff。
- ffprobe 编码层校验。
- 视频编码、帧率、时长、分辨率、旋转信息校验。
- 超长视频的任务化处理和结构化错误分级。

### B5. `selected_input_ids` 语义已修复，仍需 API 状态码细化

已完成基础修复：空列表仍表示默认全选；非空但匹配不到病例输入时，分析运行会进入 `failed`，并返回 blocking warning `selected_input_not_found`，不再静默退回全部输入。

剩余缺口：HTTP API 目前仍返回病例记录和失败 run，尚未改成 400/422 状态码。

### B6. `roi_hints` 已接入记录链路，尚未参与算法

已完成基础修复：`roi_hints` 会进入 `AnalysisRun.parameters`、融合/视频结果和 `roi_hint_count` 定量摘要，保证前端或后续接口传入的 ROI 提示不会丢失。

剩余缺口：ROI hint 尚未真正约束融合量化、关键帧筛选、候选区生成或模型 prompt。

### B7. 实时视频只是登记状态

当前 `realtime_video` 模式只生成一条“流式 AI 未接入”的完成记录，不采集帧、不推理、不保存视频片段。它适合展示“预留入口”，但不能写成实时分析能力。

### B8. JSON 病例仓库不是并发安全

`JsonCaseRepository` 每次读整个 JSON、写整个 JSON，没有文件锁、事务、版本号或并发冲突检测。单人本地演示够用；只要前后端多请求并发、后续远程协作或多人复核，就容易丢更新。

### B9. 证据包已改为 zip，并补了最小 DICOM Secondary Capture

已完成基础修复：导出现在生成 `_evidence_bundle.zip`，包含 JSON 报告、Markdown 报告、量化 CSV、bundle manifest、最小 DICOM Secondary Capture，并把已有病例 artifact 一并打包。DICOM 文件路径会写入导出 manifest，API 返回值也包含 `dicom_path`。

剩余缺口：DICOM Secondary Capture 目前只是病例摘要和免责声明的二次捕获雏形，不是正式 DICOM SR；manifest 也还没有形成正式病例证据包规范版本。后续若要对接医院系统，需要补 DICOM SR、编码体系、机构级 de-identification 策略和接收端兼容性验证。

### B10. 后端 lint 已清

`conda run -n osteo-vision python -m ruff check src backend tests scripts --output-format concise` 已通过。

## 3. 前端缺口

### F1. TypeScript 类型检查已接入

已完成基础修复：前端新增 `typecheck` 脚本，使用 `vue-tsc --noEmit`；本轮已通过。裸 `tsc --noEmit` 不再作为 Vue SFC 项目的推荐检查方式。

### F2. 根目录 npm 脚本已修复

根目录 `package.json` 已新增 `frontend:test`、`frontend:typecheck`、`frontend:build`，`npm test` 已改为调用前端测试并通过。

### F3. 前端测试覆盖很薄

当前前端只有 4 个轻量测试，主要验证页面/文本存在。没有覆盖：

- MP4 上传按钮和上传状态。
- 关键帧预览渲染。
- 摄像头开启/停止状态。
- API 失败提示。
- 导出后路径展示。
- 移动端或全屏分析布局。

### F4. 本地路径输入只适合单机模式

左侧输入框允许手动输入 `D:\...` 路径。因为前后端运行在同一台电脑，本地演示可以用；如果将来变成院内部署或多人访问，浏览器端路径对后端没有意义，必须改成上传文件、文件库选择或设备采集服务。

### F5. 上传后预抽取关键帧未绑定病例

`/uploads/raw` 返回 keyframes，前端只提示数量；这些预抽取帧没有作为病例 artifact 保存。真正写入病例和分析时会再次抽帧。这里存在重复计算和孤立文件问题。

### F6. 实时视频 UI 容易被误解

界面有“实时视频”按钮和状态，但后端没有流式分析。虽然文案有说明“尚未接入”，比赛演示时仍需要明确标成“实时预览/接口预留”，避免评审误解。

## 4. 模型缺口

### M1. 已有 D025 代理模型 adapter，真实目标域模型 adapter 仍缺失

`src/models/adapters.py` 已新增 `D025LesionSegmenterAdapter`，可加载本地 `d025_lesion_smoke_segmenter` checkpoint，并对 `npz_roi` 输入输出体素级 mask、量化摘要和证据路径。

剩余缺口：`TimmClassifierAdapter`、`MonaiBundleAdapter`、`NnUNetV2Adapter`、`MedSAMLikeAdapter`、`Vista3DLikeAdapter`、`VLMEncoderAdapter` 仍没有真实推理实现。所有未实现 adapter 仍默认标记 `adapter inference not implemented`，避免未来补了 checkpoint 后被误报为可用。

### M2. NPZ 代理分割已接主线，其他输入仍主要走 fixture pipeline

当输入为 D025 风格 `npz_roi` 且 checkpoint 存在时，`configs/inference/osteo_vision.yml` 会优先选择 `d025_lesion_smoke_segmenter`，`SegmentationPipeline` 也会优先使用 adapter 输出。

剩余缺口：JPEG、MP4、DICOM/NIfTI、检测、量化和多数多任务路径仍依赖 fixture 或规则逻辑。`src/engine/inference.py` 仍初始化 `load_fixture_models()`，说明主线还不是完整 nnU-Net/MedSAM/ConvNeXt 临床模型推理。

### M3. 当前模型清单新增 D025 smoke 模型，但核心候选仍不可用

`scripts/model_inventory.py` 当前结果：

- `d025_lesion_smoke_segmenter`：可用；任务为 D025 CBCT lesion ROI 代理分割，只支持 `npz_roi`。
- `nnunet_v2_osteo_baseline`：缺 checkpoint。
- `medsam2_osteo_promptable`：缺 checkpoint。
- `biomedclip_osteo_screening`：缺 `open_clip` 依赖和 checkpoint。
- `fixture_default`：可用。

同时，nnU-Net、MedSAM-like、BiomedCLIP 三个外部模型均明确标记为 `adapter inference not implemented`。

本地已生成 `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`、`d025_lesion_smoke_manifest.json` 和 `d025_lesion_smoke_model_card.json`；它们是本地运行产物，不进入 Git。

### M4. ConvNeXt 还停留在 benchmark 脚本，没有接入主线

ConvNeXt/MedNeXt 风格 3D 模型定义在 `scripts/benchmark_d024_frontier_segmentation_models.py`，不是 `src/models/` 的正式模型，也没有配置项、checkpoint manifest、推理适配器或导出路径。它是研究候选，不是系统当前可调用模型。

### M5. D025 病灶代理已有 smoke 训练闭环，但性能不具备报告价值

D025 已有 262 例 lesion ROI 64 缓存。本轮新增 `scripts/train_d025_lesion_smoke_model.py`，默认可跑少量 batch 生成 checkpoint、manifest、model card 和中英文建模报告：

- `research/reports/modeling/d025_lesion_smoke_model_20260703_zh.md`
- `research/reports/modeling/d025_lesion_smoke_model_20260703_en.md`

本轮 2 batch CPU smoke 的验证指标很低，Foreground Dice 约 0.0002，只能证明训练/推理/adapter/报告链路打通，不能作为性能依据。仍需长训练、交叉验证、失败样本分析、nnU-Net baseline 和 ConvNeXt/MedNeXt 候选复测。

### M6. OFDVDnet 已转成可演示 manifest，仍缺去噪/增强 baseline

OFDVDnet `data.zip` 已解压到本地 raw/extracted 目录，并生成：

- 详细 manifest：`research/literature/inventory/ofdvdnet_video_manifest_20260704.csv`
- 前端视频库 combined manifest：`research/literature/inventory/video_library_manifest_20260704.csv`
- 中英文报告：`research/reports/modeling/ofdvdnet_manifest_20260704_zh.md`、`research/reports/modeling/ofdvdnet_manifest_20260704_en.md`
- 三视图预览：`research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/ofdvdnet/previews/`

处理结果：50 个视频中 48 个可由 OpenCV 读取；2 个视频记录为不可读（`moov atom not found`），不会进入前端可导入候选。每条可读视频已记录 overlay / fluorescence / reference 三视图裁剪坐标，可用于赛点一的荧光增强、伪彩稳定和三视图演示。

剩余缺口：还没有真正实现 OFDVDnet 去噪/增强 baseline，也没有将三视图裁剪接成正式训练 dataset loader。该数据仍是模拟鸡腿荧光代理，不是颌骨骨髓炎目标域数据。

### M7. 旧模型快照不完整

`tools/check_project_readiness.py` 提示 EGNet 和 FRS Loss 快照缺关键文件。若不准备继续走这两条路线，应在研究归档中降级；若要引用，需要补完整代码或从报告里移除“已具备”的表述。

### M8. 模型评估仍是早期筛选，不是可报告性能

当前 artifact 中的 `20260702T064108Z` 是 fixture benchmark，只有测试 fixture manifest，accuracy 0.5。不能作为项目模型性能。D024/D036/D025 的公开 CBCT benchmark 也只能作为代理任务，不应写成颌骨骨髓炎临床诊断性能。

## 5. 数据与研究资产缺口

### R1. 旧论文清单只剩链接，不是本地 PDF 库

`paper_inventory.csv` 60 条旧记录已改为 `link_only_no_local_pdf`。当前真实可读资料基线是 `local_paper_assets_20260703.csv`：5 个 PDF + 3 个 HTML。后续报告引用必须从真实文件或重新下载后的 PDF 出发。

### R2. 视频数据已形成 manifest 到病例输入的最小桥

已有 `video_download_manifest_20260703.csv`。本轮新增 `VideoLibraryService` 和 `/video-library/candidates`，可读取公开视频候选清单，并默认只返回本地存在且当前系统可读的 MP4 候选。`/cases/{case_id}/video-library/{record_id}/inputs` 可把候选视频一键导入病例 video input；导入后仍走现有 MP4 校验、关键帧分析和证据导出链路。前端左侧控制面板已具备加载公开视频候选、选择候选、导入病例的最小入口。

当前 combined manifest 可识别 69 条本地存在且系统可读的 MP4 候选，其中 21 条来自骨髓炎公开视频，48 条来自 OFDVDnet 荧光代理数据。FLV、未下载、reCAPTCHA 占位、非 MP4 文件和 OFDVDnet 中不可读的 2 条视频不会默认作为可导入候选暴露。

剩余缺口：当前只是最小选择入口，还不是正式数据集管理页；OFDVDnet 还没有去噪/增强 baseline 和训练 loader。公开视频仍是非目标域代理资料，不具备真实术中 ICG 颌骨骨髓炎标注。

### R3. D042 / D044 目录为空

MODID 和旧 FGS video 候选目录存在但 0 文件。若继续保留，需要明确“未下载”；若不作为近期路线，应从当前任务优先级里降级。

## 6. 工程治理缺口

### G1. 质量门依赖不完整

已完成基础修复：`mypy`、`black`、`isort` 已安装到 `osteo-vision` 环境，`requirements.txt` 已同步，`ruff` 和 `mypy` 均已通过。

剩余缺口：候选模型依赖仍不完整，尤其是 BiomedCLIP 需要的 `open_clip`，以及后续真实训练/推理可能需要的专用依赖。

### G2. 工作区改动未分批固化

当前有大量未提交改动和新增文件，包含官方文档对齐、视频输入、前后端工作台、下载清单、研究报告等。继续开发前应按主题分批检查和提交，否则后续很难定位问题来源。

### G3. 代码中存在生成缓存文件

`backend/tests/**/__pycache__`、`frontend/dist/`、日志等虽然被 gitignore 屏蔽，但本地目录较乱。需要定期清理运行产物，避免误把本地状态当成项目能力。

## 7. 排除真实数据和医生标注后的优先级

### 近期 P0

1. OFDVDnet 已解压并生成三视图预览、详细 manifest 和前端视频库 combined manifest；下一步接去噪/增强 baseline 和训练 dataset loader。
2. D025 lesion ROI 64 已跑通小型可复现 smoke 训练闭环；下一步需要扩大训练批次、保存失败样本和做阈值分析。
3. 选择一个正式模型路线进入主线 adapter：优先 ConvNeXt/MedNeXt 小模型或 nnU-Net baseline，而不是只停留在 D025 smoke checkpoint。
4. 为 BiomedCLIP/MedSAM/nnU-Net 补依赖、checkpoint manifest 和不可用时的前端展示。
5. JSON job registry 已解决基础落盘问题；下一步升级为可取消、可重试、带长视频分片进度的持久化队列。

### 近期 P1

1. DICOM Secondary Capture 已有最小导出雏形；下一步补 DICOM SR 或至少固定证据包 manifest 版本。
2. 将 ConvNeXt 候选从 benchmark 脚本迁入 `src/models/`，接配置和 adapter。
3. D046 视频候选和 OFDVDnet combined manifest 已接入后端列表、病例导入接口和前端最小选择入口；下一步做正式数据集管理页、过滤器和视频预览。
4. 补前端 MP4 上传、关键帧、摄像头、导出交互测试。
5. 对 zip 证据包定义稳定 manifest 版本和病例证据包目录规范。

## 8. 本轮已落地修复

本轮已完成的非真实数据依赖修复如下：

- 质量门：`ruff`、`mypy`、Python 测试、前端 typecheck、前端测试、前端 build 均已跑通；本轮核心改动文件范围的 `black` / `isort` 检查也已通过。
- 视频输入：MP4 增加 OpenCV 可读性校验，伪装/损坏 MP4 会被拒绝。
- 视频任务：上传预抽帧和 MP4 分析已具备后台 job 与查询接口，前端会轮询任务状态。
- 后台任务：`JobRegistry` 已落盘到 JSON，服务重建后可查询已完成任务，未完成任务会被标记为中断失败。
- 视频数据桥：新增公开视频候选读取与导入接口，combined manifest 当前可识别 69 条本地可读 MP4 候选，可导入病例 video input。
- OFDVDnet 数据：已解压并生成 50 条详细记录、48 条可读视频库候选和 192 张三视图预览；后端默认视频库可导入候选提升到 69 条。
- 视频证据：关键帧输出拆成预览帧和全分辨率证据帧，并记录基础质量指标。
- 分析语义：`selected_input_ids` 不再静默退回全量输入；`roi_hints` 进入运行记录。
- 导出闭环：证据包从路径 JSON 改成真实 zip，包含报告、量化 CSV、manifest、最小 DICOM Secondary Capture 和病例 artifact。
- 前端工程：新增 `vue-tsc` 类型检查，根目录 `npm test` 可用。
- 模型边界：非 fixture adapter 明确标记为“推理未实现”，避免把未接入模型误写成可用模型。
- 模型闭环：新增 D025 CBCT lesion ROI 代理 smoke 模型，已生成本地 checkpoint、manifest、model card，并接入 segmentation adapter 与主线配置；该模型只用于工程验证。
- 闭环证据：新增 `tools/run_platform_smoke.py`，可一键跑通病例创建、双通道融合、MP4 后台分析和 zip 导出。
