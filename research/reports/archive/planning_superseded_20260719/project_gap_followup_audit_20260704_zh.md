# 项目缺口补充自查：排除真实病例与医生关键帧后的工程清单

日期：2026-07-04

本轮按当前约束处理：真实项目病例、真实术中白光/ICG MP4/JPEG、医生关键帧/ROI 标注暂时做不了，继续作为外部数据依赖和一级风险记录；本报告只列其他仍能推进、修复或验证的缺口。

## 2026-07-04 后续更新：2D keyframe 分割模型已接入

本报告早期段落中多处写到“MP4/JPEG 关键帧仍只有 hotspot baseline”。该判断在后续实现后已经更新：当前 `configs/inference/osteo_vision.yml` 已新增 `convnext2d_keyframe_proxy_segmenter`，`backend/src/services/analysis_service.py` 的 MP4 keyframe 分析会优先调用该可训练 PyTorch adapter，输出 `png_binary_mask`、probability、pseudo-color、overlay、候选连通区和量化结果；模型不可用时才回退到 `fluorescence_hotspot_2d_segmenter`。

当前边界不变：该 2D 模型使用合成/伪标注荧光代理帧训练，属于工程闭环代理模型，不代表真实术中 ICG 颌骨骨髓炎目标域性能。

## 0. 当前可推进缺口总表

本节用于快速决策，刻意排除“真实项目病例”和“医生关键帧/ROI 标注”这两个当前外部不可控前置项。

| 类别 | 当前缺口 | 优先级 | 下一步动作 |
|---|---|---:|---|
| 后端存储 | 默认平台病例仓库已从 JSON 整体读写迁移到 SQLite，并补了 `version` 乐观锁；剩余缺口是更细粒度的表级追加写入和冲突后自动合并策略。 | P1 | 后续把 ROI、analysis run、artifact 改成表级追加或补冲突重放/合并流程。 |
| 后台任务 | job 已具备持久化、进度、取消/重试、重启恢复、限流、同病例/同源任务锁，并新增本地 `LocalJobWorker` 与 `OSTEO_JOB_EXECUTION_MODE=worker`；剩余缺口是常驻 worker 管理、优先级、真正队列后端和更强跨进程并发控制。 | P1 | 短期用 `tools/run_job_worker_once.py` drain queued jobs；后续评估 SQLite job queue 或 RQ/Celery，把长视频分析彻底从 FastAPI 进程中拆出。 |
| 4K 上传校验 | MP4/JPEG 已新增官方设备 profile：记录 JPEG/MP4、3840x2160、ffprobe 编码/码率/旋转可用性和前端可读规格提示；本轮已补合成 3840x2160 JPEG/MP4 代理压力 smoke。剩余缺口是真实长视频、旋转/码率异常和分片上传。 | P1 | 继续用更长代理 MP4 与真实样例做上传/抽帧/分析压力测试，并把码率/旋转异常接入更明确的前端处理建议。 |
| 视频关键帧 | 关键帧抽取已从单一 uniform sampling 升级为默认 `quality_peak`，已支持上传预抽帧复用、候选帧 trace、轻量重复帧去重、`timeline_manifest.json`、当前帧详情和当前帧单帧重算；仍不等同医生关键帧。 | P1 | 下一步做真实/代理 4K 长视频压力测试、真实逐帧进度和更完整的时间轴详情抽屉。 |
| 荧光融合 | 双通道融合仍是 resize + 归一化 + alpha blend；ROI 约束量化已接入，但缺真正配准、背景扣除、颜色标尺和时序峰值分析。 | P0 | 先做可解释的 V2 融合报告，再做配准算法和颜色标尺。 |
| ROI 交互 | `RoiCanvas` 已从占位升级为可保存的矩形 ROI 画布，并能写入病例 `rois` 与复核事件；已保存 ROI 会作为 `roi_hints` 进入后续分析，约束双通道融合 ROI 量化、候选区评分和 MP4 hotspot 候选筛选。 | P1 | 下一步把 ROI 继续接入关键帧选择、promptable model 和更完整的人工编辑历史。 |
| 模型主线 | 可用模型包括 D025/ConvNeXt3D CBCT ROI 代理、`convnext2d_keyframe_proxy_segmenter` 训练型 keyframe 代理分割、hotspot 回退、MedSAM-like prompt fallback 和 fixture；nnU-Net、BiomedCLIP 仍未真正可用。 | P0 | 继续补正式目标域/近域数据、失败样本和实验对比表；nnU-Net/DynUNet 作为下一阶段 3D 基线。 |
| MP4 AI 结果 | MP4 已能抽关键帧并优先调用 2D ConvNeXt-style 代理分割模型，输出 mask、probability、伪彩、overlay、video segmentation manifest、overlay/mask review MP4、候选 metadata 和医生复核 ROI；模型不可用时回退 hotspot baseline。 | P0 | 继续补完整时间轴详情抽屉、真实训练模型、真实/代理 4K 长视频压力证据和更稳定的失败态报告。 |
| 前端评审体验 | 公开视频候选已具备详情卡、来源链接、数据边界、关键帧缩略图、视频规格、荧光/非荧光筛选、训练用途筛选和独立视频库页；Playwright 浏览器级闭环已覆盖建病例、双通道分析、候选区接受、ROI 复核、导出、MP4 上传分析、热点时间轴筛选/点击切换、公开视频导入、移动端工作台和全屏分析截图。剩余缺口是批量预览/导入、失败态截图和可交付操作录像。 | P2 | 增加批量预览/导入、失败态截图和演示录像。 |
| 导出规范 | 当前是 evidence bundle + Secondary Capture 雏形，不是正式 DICOM SR，也缺稳定 schema 文档。 | P1 | 固定 bundle schema v1，后续再做 DICOM SR。 |
| 数据治理 | 视频库和 OFDVDnet 可支撑代理实验，但目标域边界很强；论文 PDF 证据链不完整。 | P1 | 把每个数据源标注为目标域/非目标域/仅演示/可训练。 |
| 工程治理 | 工作区 diff 很大，混合前后端、模型、报告、manifest 与脚本。 | P0 | 按主题分批 review、测试、提交，防止继续堆叠风险。 |

## 1. 本轮核验结果

| 核验项 | 当前结果 |
|---|---|
| `conda run -n osteo-vision python check_env.py` | 通过；Python 3.11.15；无 failure/warning。 |
| `conda run -n osteo-vision python tools/check_project_readiness.py` | 主体 OK；仍提示 EGNet、FRS Loss 代码快照缺关键文件。 |
| `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml` | `convnext3d_d025_proxy_segmenter`、`fluorescence_hotspot_2d_segmenter`、`d025_lesion_smoke_segmenter` 和 `fixture_default` 可用；nnU-Net、MedSAM-like、BiomedCLIP 不可用。 |
| `conda run -n osteo-vision python scripts/generate_model_checkpoint_manifest.py --config configs/inference/osteo_vision.yml --output-dir research/reports/modeling --date-stamp 20260704` | 通过；生成 `model_checkpoint_manifest_20260704.json/.csv/_zh.md/_en.md`，记录 7 个模型、4 个当前可用模型、3 个缺 checkpoint 的候选模型，且 `clinical_claim_allowed` 全部为 false。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；新增本地 worker、官方输入 profile、模型 checkpoint manifest 测试后仍通过；仍有 FastAPI TestClient 与 torch JIT deprecation warning。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；8 个前端测试文件、19 个测试通过；已覆盖 MP4 hotspot 预览面板/时间轴筛选/叠加框派生逻辑、timeline manifest 摘要、导出下载 URL、后台 job 继续查询/取消/重试、公开视频候选筛选/详情/关键帧预览字段和 ROI geometry 测试，但整体交互覆盖仍偏薄。 |
| `npm --prefix frontend run build` | 通过；Vite build 成功。 |
| `conda run -n osteo-vision python tools/run_platform_smoke.py` | 通过；最新摘要为 `artifacts/platform_smoke/20260703T234527Z/platform_smoke_summary.json`；`artifact_count=20`，MP4 分析 run 生成 3 帧 hotspot 输出、4 个热点候选区、frame index/detail/timeline manifest、evidence bundle、导出 summary 和 artifact entries，并已复用上传阶段预抽帧路径；同时覆盖 SQLite 临时病例仓库、job 进度、取消/重试兼容路径和默认任务限流配置。 |
| `npm --prefix frontend run test:e2e` | 通过；3 个 Playwright Chromium 浏览器级闭环测试，覆盖 `/cases` 新建病例、`/case` 双通道输入/分析/导出、`/review` 候选区接受和手动 ROI 保存、`/report` 报告页、`/data` 视频库页、MP4 浏览器上传、MP4 keyframe hotspot 分析、热点时间轴筛选/点击切换、公开视频导入、移动端工作台和全屏分析视图，并在 `artifacts/e2e/browser_smoke/` 保存 8 张截图。 |
| `git diff --check` | 无 whitespace error；仅提示多处 LF 将在 Git 触碰时转换为 CRLF。 |

当前结论：工程链路基本能跑通，主要缺口不是“跑不起来”，而是能力深度、模型真实性、数据域边界、前后端交互完整性和可评审表达。

## 2. 后端缺口

### B1. 病例仓库已默认迁移 SQLite，并已补 version 乐观锁

证据文件：`backend/src/domains/cases/repository.py`

当前新增 `SQLiteCaseRepository`，默认 `case_store_path` 已改为 `artifacts/platform/cases.sqlite`，`build_router()` 会按配置选择 SQLite 或 JSON 仓库；`.json` 路径仍自动使用旧 `JsonCaseRepository`，用于兼容既有测试和导出。SQLite 路径提供事务化写入、WAL journal 和 `export_json()`，解决了“默认平台仍用 JSON 整体读写”的主要架构落差。

本轮已补 `CaseRecord.version` 和 `CaseVersionConflictError`：SQLite `save()` 会用 `WHERE case_id AND version` 做乐观锁更新，成功后自动递增版本；JSON 兼容仓库也会检查版本，避免后写覆盖先写。FastAPI 已注册 409 `case_version_conflict` 处理器；前端类型与病例管理页同步显示版本。新增测试覆盖 SQLite/JSON stale save 被拒绝。

剩余缺口：病例仍是整条 payload 保存，虽然能阻止静默覆盖，但冲突后还没有自动合并或重放。后续更正式的做法是把 ROI、analysis run、artifact、review event 改成表级追加写入，或者在 409 后由前端提示重载并重试。

优先级：P1。

### B2. 后台任务已有本地持久 worker，但还不是正式队列系统

证据文件：

- `backend/src/api/analysis_runs.py`
- `backend/src/api/uploads.py`
- `backend/src/core/settings.py`
- `backend/src/services/job_service.py`
- `backend/src/services/job_worker.py`
- `tools/run_job_worker_once.py`

当前 job registry 已能 JSON 落盘；已补分析任务取消端点、前端取消/重试入口、canceled 状态保护和可持久化 `progress` 字段，前端任务面板已能显示进度条、进度百分比和进度消息。本轮继续补了限流、任务锁和本地 worker：`case_analysis` 可通过 `OSTEO_MAX_ACTIVE_CASE_ANALYSIS_JOBS` 限制活动任务数，并对同一 `case_id` 阻止重复提交；`upload_keyframe_extraction` 可通过 `OSTEO_MAX_ACTIVE_UPLOAD_KEYFRAME_JOBS` 限制活动任务数，并对同一 `source_path` 阻止重复关键帧任务。容量不足会返回 429，重复任务会返回 409，并带结构化错误码。

新增 `LocalJobWorker` 后，queued job 在服务重启后会保留，可由 `conda run -n osteo-vision python tools/run_job_worker_once.py --limit N` 处理；`OSTEO_JOB_EXECUTION_MODE=worker` 可让 API 只入队、不用 FastAPI BackgroundTasks 立即执行。`JobRegistry` 读取时会刷新落盘状态，因此 API 能看到本地 worker 写回的 completed/failed 结果。

剩余架构问题是它仍是 JSON 文件级本地队列，不是常驻 worker 服务，也没有优先级、延迟重试、并发 worker 锁租约和可观测性面板。服务重启后 running job 仍会标记 failed，这是合理的本地平台验证策略，但还不是正式任务队列。

优先级：P1。

### B3. 前端轮询窗口过短，不适合真实 4K 长视频

证据文件：

- `frontend/src/stores/caseStore.ts`
- `frontend/src/pages/CaseWorkspacePage.vue`

前端上传关键帧和分析 job 原本都是 30 次、每 500 ms 轮询，最长约 15 秒。当前已将上传关键帧轮询扩展到最多约 180 秒、分析 job 轮询扩展到最多约 300 秒，并在分析卡片中显示后台任务 ID、任务状态、错误信息、进度条、“继续查询”“取消”“重试”按钮；但仍缺独立任务详情页和真实逐帧进度。真实 4K MP4 或较长公开视频仍可能超过该窗口。

优先级：P0。

### B4. 上传校验已补官方设备 profile，但还缺真实 4K 压力验证

证据文件：

- `backend/src/api/uploads.py`
- `src/io/official_device_quality.py`
- `src/io/image_io.py`
- `src/io/video_io.py`
- `src/preprocess/input_validation.py`

目前已增加上传内容签名探针，能在 `/uploads/raw` 阶段拦截 `.jpg/.png/.tiff/.bmp/.mp4` 扩展名与实际内容不匹配的文件；本轮继续新增官方设备 profile：图片会记录目标 JPEG 与 3840x2160 匹配状态，视频会记录 MP4 `ftyp`、3840x2160、OpenCV 基础 metadata、ffprobe 可用时的 codec、pix_fmt、bit_rate、duration、rotation 等字段，并把不匹配项作为非阻断 warning / `official_profile_mismatch` 质量提示返回前端。前端上传完成提示和病例输入清单会显示“官方规格匹配/需确认”。

剩余缺口是真实 4K 长视频压力验证、色彩空间/码率策略的更细分处理、超大文件断点/分片上传，以及将旋转异常自动归一化后再进入分析。`MAX_VIDEO_UPLOAD_BYTES` 固定 1GB，真实 4K 长视频仍可能不够。

优先级：P1。

### B5. 视频关键帧策略已从 uniform sampling 升级为质量/信号优先

证据文件：`src/preprocess/video.py`

当前默认使用 `quality_peak` 策略：先在有限 uniform 候选池中探测帧，再按荧光样信号、清晰度和曝光质量打分，选择时间上分散的高分帧，并在结果中保留 `selection_trace`、`sampling_strategy`、`selection_score` 和质量摘要。`uniform` 仍保留为可选策略。前端已能按阳性面积、ROI 命中和候选数量筛选热点时间轴；本轮已补独立 `frame_index_manifest.json`、分析阶段 `frame_details_manifest.json` 和用户指定秒级时间点抽帧。剩余缺口是运动/重复帧过滤、整段视频时间轴缓存和真实逐帧进度。因此它是工程增强关键帧，不应写成医生关键帧替代。

优先级：P0。

### B6. 上传预抽帧与分析抽帧已打通复用，仍缺更完整时间轴缓存

证据文件：

- `backend/src/api/uploads.py`
- `backend/src/services/analysis_service.py`
- `src/preprocess/video.py`

本轮已修复主要重复计算：`extract_keyframes()` 现在会在抽帧目录写入 `keyframe_manifest.json`；上传阶段生成的 manifest 位于 `uploads/keyframes/<upload_stem>/keyframe_manifest.json`。MP4 分析阶段会按源视频路径、采样策略和请求帧数查找该 manifest；若预抽帧数量足够且文件仍存在，则直接复用上传预抽帧，并在 `fused_outputs.keyframe_report_source` 与 `quantitative_summary.keyframe_source` 标记为 `reused_upload_preextract`。复用后的关键帧会作为病例 artifact 进入后续 evidence bundle，不再只是孤立上传产物。

剩余缺口：当前只复用“同源视频 + 同采样策略 + 请求帧数不超过预抽帧数量”的简单场景；还没有面向整段视频的时间轴缓存、运动去重缓存、用户手动选择帧缓存和跨病例缓存清理策略。

优先级：P1。

### B7. 实时视频只是登记记录

证据文件：

- `backend/src/services/analysis_service.py`
- `frontend/src/pages/CaseWorkspacePage.vue`

后端对 `realtime_video` 返回 completed，并写入“streaming AI inference is not connected”。前端文案也说明未接入，但按钮仍叫“实时视频”。比赛展示时容易被误解，应改成“实时预览/接口预留”或真正接入帧采样。

优先级：P1。

### B8. 双通道融合算法仍是 resize-only 初版

证据文件：`src/preprocess/fluorescence.py`

当前融合为荧光灰度 Min-Max 归一化、伪彩、alpha blend；若尺寸不同只 resize 到白光尺寸。缺少双通道配准、光照/曝光校正、ICG 背景扣除、时序峰值分析、ROI 约束量化、4K 性能策略和可解释的颜色标尺。

优先级：P0。

### B9. ROI hints 只进入记录，未约束算法

证据文件：`backend/src/services/analysis_service.py`

`roi_hints` 已进入参数和摘要；前端 `RoiCanvas` 现在已支持手动矩形 ROI 拖拽、标签、复核状态和保存，保存结果会写入病例 `rois` 与复核事件。后端会把病例已保存 ROI 与请求中的 `roi_hints` 合并，参与双通道融合 ROI 量化、候选区评分说明和 MP4 hotspot 候选筛选。剩余核心缺口是 ROI 尚未参与关键帧选择和 promptable model。

优先级：P0。

### B10. 导出仍是 Secondary Capture 雏形，不是 DICOM SR

证据文件：

- `backend/src/services/export_service.py`
- `backend/src/reports/dicom_secondary_capture.py`

证据包 zip 已可用，最小 DICOM Secondary Capture 也可读；但这只是把摘要渲染成二次捕获图像，不是结构化 DICOM SR，也没有机构级脱敏策略、编码体系、接收端兼容性验证和稳定 bundle schema 版本。

优先级：P1。

### B11. 文件预览接口缺少访问控制

证据文件：`backend/src/api/files.py`

接口限制了 artifact root 和图片后缀，路径穿越风险基本被压住；但没有登录、token、一次性下载链接和审计日志。单机演示可接受，远程协作时必须补。

优先级：P2。

## 3. 前端缺口

### F1. 前端测试覆盖仍停留在存在性检查

证据文件：`frontend/tests/`

当前已有 MP4 hotspot 预览、热点时间轴筛选、导出面板、后台 job 查询/取消/重试、公开视频候选详情和 ROI geometry 等前端测试。本轮新增并扩展 Playwright Chromium 浏览器级闭环测试，覆盖实际前后端服务下的建病例、双通道分析、导出、候选区接受、ROI 保存、报告页、视频库页、MP4 浏览器上传、MP4 keyframe hotspot 分析、热点时间轴筛选/点击切换、公开视频导入、移动端工作台和全屏分析视图。剩余覆盖仍偏薄：尚未系统覆盖 API 失败提示、摄像头状态和可交付操作录像。

优先级：P0。

### F2. 左侧本地路径输入只适合单机演示

证据文件：`frontend/src/components/CaseWorkspaceControls.vue`

界面仍保留 `D:\...` 路径输入。当前前后端同机运行可以用；如果评审或学校侧远程打开前端，这些路径对后端无意义。应逐步以文件上传、视频库选择和设备采集服务为主，手动路径保留为“本机调试模式”。

优先级：P1。

### F3. 公开视频候选入口太粗

证据文件：

- `frontend/src/components/CaseWorkspaceControls.vue`
- `frontend/src/pages/CaseWorkspacePage.vue`

当前已从单一下拉框升级为“下拉选择 + 候选详情卡”，能展示标题、record_id、荧光/非荧光、医学场景、训练可用性、文件大小、读取状态、数据边界和原始来源链接。本轮继续补了按需关键帧预览：选择本地可读 MP4 候选时，后端会在 artifact root 下生成安全的 `preview.jpg`，前端候选卡直接显示缩略图，并展示视频规格和预览状态。

本轮继续补齐筛选和独立入口：工作台公开视频选择器新增荧光/非荧光和训练用途筛选；新增 `/data` 视频库页，可独立浏览本地可读公开视频候选、查看荧光/非荧光数量、训练用途分布、本地体量、生成预览和导入当前病例。

剩余缺口是批量预览、批量导入、分页/搜索和真实浏览器端到端测试。

优先级：P2。

### F4. 导出体验还停留在路径文本

证据文件：`frontend/src/components/AnalysisWorkspaceCard.vue`

当前已补 `/files/download` 下载接口，导出响应会返回 `summary` 和 `artifact_entries`，前端导出区可显示证据包 ZIP、JSON 报告、manifest、DICOM 二次捕获下载入口、导出摘要和证据文件列表，并保留本地路径用于核验。剩余缺口是导出失败重试、导出格式选择和更完整的 manifest 详情页。

优先级：P2。

### F5. 调试面板会直接展示病例 JSON

证据文件：`frontend/src/pages/CaseWorkspacePage.vue`

当前页面的“开发调试数据”已改为仅在 Vite dev 环境且 URL 带 `?debug` 时显示，默认比赛演示和报告截图不会暴露完整病例 JSON 与本地路径。剩余缺口是后续如需远程协作，应提供脱敏后的结构化诊断调试视图，而不是直接展示原始 case 对象。

优先级：P2。

### F6. 前端 API base URL 是构建时配置

证据文件：`frontend/src/services/apiClient.ts`

默认 `http://127.0.0.1:8001`，可用 `VITE_OSTEO_API_URL` 覆盖。打包后切换部署地址不方便，后续可补运行时配置文件或启动脚本注入。

优先级：P2。

## 4. 模型缺口

### M1. 真实主线模型仍未接入

证据文件：

- `configs/inference/osteo_vision.yml`
- `src/models/adapters.py`
- `src/engine/inference.py`

当前可用模型包括新增的 `convnext3d_d025_proxy_segmenter`、D025 CBCT lesion ROI 代理 smoke 模型和 fixture fallback。`convnext3d_d025_proxy_segmenter` 已作为正式 `convnext3d_segmenter` family 进入配置和模型选择，真实配置下可完成 `npz_roi` 分割推理。nnU-Net、MedSAM-like、BiomedCLIP 仍显示 adapter inference not implemented；BiomedCLIP 还缺 `open_clip` 和 checkpoint。`src/engine/inference.py` 仍保留 fixture models 供非目标输入 fallback，说明主线还不是完整临床/竞赛模型推理。

优先级：P0。

### M2. D025 smoke 模型只证明链路，不证明性能

证据文件：

- `src/models/lesion_segmenter.py`
- `scripts/train_d025_lesion_smoke_model.py`
- `research/reports/modeling/d025_lesion_smoke_model_20260703_zh.md`

D025 模型是 64 立方 CBCT ROI 代理，训练脚本默认小 batch smoke。它适合证明训练、checkpoint、adapter、推理和报告链路；不能写成颌骨骨髓炎术中 ICG 性能。下一步要扩大训练、做阈值分析、失败样本、交叉验证，并和 nnU-Net/ConvNeXt/MedNeXt baseline 对比。

优先级：P0。

### M3. ConvNeXt 候选没有迁入正式模型层

证据文件：

- `scripts/benchmark_d024_frontier_segmentation_models.py`
- `src/models/lesion_segmenter.py`
- `src/models/adapters.py`
- `configs/inference/osteo_vision.yml`
- `configs/tasks/osteo_vision.yml`
- `research/reports/modeling/convnext3d_proxy_adapter_20260704_zh.md`

本轮已部分修复：正式 `src/models/lesion_segmenter.py` 中的 tiny ConvNeXt-style 3D block + U-Net 风格小模型已通过 `ConvNeXt3DLesionSegmenterAdapter` 注册为 `convnext3d_segmenter` family，并在 `configs/inference/osteo_vision.yml` 中新增 `convnext3d_d025_proxy_segmenter`。真实配置下，该模型可被模型清单识别为可用，并可对 D025 `npz_roi` 样本输出 `npz_volume_mask`。

剩余缺口：这仍复用 D025 smoke checkpoint，属于 CBCT ROI 代理链路；已新增 `research/reports/modeling/model_checkpoint_manifest_20260704_zh.md` 作为当前 checkpoint 可审计清单，但还没有正式 ConvNeXt/MedNeXt 长训练、失败样本可视化，也没有接入 JPEG/MP4 关键帧或前端模型结果展示。

优先级：P0。

### M4. MedSAM 路线还没有 prompt/交互闭环

证据文件：`src/models/adapters.py`

MedSAM-like adapter 是空类，前端也没有可输出到模型的框、点、涂鸦或 ROI prompt。若选择 MedSAM，需要先定义 2D frame/3D volume 的 prompt 数据结构，并把医生 ROI 工具接到 adapter。

优先级：P1。

### M5. MP4/JPEG 目标输入尚未进入 AI 分割模型

证据文件：

- `backend/src/services/analysis_service.py`
- `src/engine/inference.py`
- `src/pipelines/segmentation.py`
- `src/models/hotspot_segmenter.py`
- `research/reports/modeling/jpeg_mp4_hotspot_bridge_20260704_zh.md`

本轮已部分修复：JPEG / 2D 荧光图像现在可通过 `fluorescence_hotspot_2d_segmenter` 进入主线 segmentation adapter，输出 `png_binary_mask`、伪彩图、overlay、候选连通区和阳性面积比例。MP4 分析现在不再只抽关键帧；每个 keyframe 会进入热点分割 baseline，结果写入 `fused_outputs.hotspot_outputs`、`quantitative_summary.hotspot_*`、`candidate_regions` 和 ROI mask/heatmap/overlay artifacts。

剩余缺口：该桥接仍是启发式强度阈值/连通区 baseline，不是训练完成的目标域 AI 模型；前端已能优先展示 MP4 hotspot 关键帧、叠加图、掩膜和热点时间轴，并能在摘要区显示 hotspot 统计。后端已把 top hotspot bbox 写入 `CandidateRegion.metadata`，复核页可把候选转为 AI ROI，工作台图像预览会叠加已保存 ROI 和候选框；热点时间轴点击后可切换四宫格到对应关键帧，并可按阳性面积、ROI 命中和候选数量筛选；本轮新增当前帧详情面板，展示候选数量、阳性面积、ROI 命中、Top BBox 和证据帧/叠加图/掩膜链接。尚未完成的是完整时间轴缓存、运动去重和真实训练模型。

优先级：P0。

### M6. OFDVDnet 已入库，但未转成训练/增强 baseline

证据文件：

- `scripts/prepare_ofdvdnet_dataset.py`
- `scripts/run_ofdvdnet_fluorescence_baseline.py`
- `src/datasets/ofdvdnet.py`
- `research/literature/inventory/ofdvdnet_video_manifest_20260704.csv`
- `research/literature/inventory/video_library_manifest_20260704.csv`
- `research/literature/inventory/ofdvdnet_fluorescence_baseline_manifest_20260704.csv`

当前 OFDVDnet 50 条记录、48 条可读 MP4 已进入 combined manifest，并有三视图预览。本轮已新增最小赛点一 baseline：从详细 manifest 读取三视图布局，裁剪右上角荧光视图和左下角参考视图，对荧光视图做高斯去噪、百分位归一化、CLAHE 对比度增强、伪彩映射，并生成参考融合图、CSV manifest 和中英文报告。

本轮 baseline 处理 48 条可读记录，输出：

- `research/literature/inventory/ofdvdnet_fluorescence_baseline_manifest_20260704.csv`
- `research/reports/modeling/ofdvdnet_fluorescence_baseline_20260704_zh.md`
- `research/reports/modeling/ofdvdnet_fluorescence_baseline_20260704_en.md`
- `research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/derived/ofdvdnet/baseline_enhancement/`

剩余缺口：还没有把该 baseline 接成训练 dataset loader、伪彩稳定评估和输入输出成对训练流程。前端视频库候选已可按需显示关键帧预览，但 OFDVDnet baseline 输出本身还没有进入专门的数据管理页或训练入口。它仍是模拟鸡腿荧光代理，不是目标域。

优先级：P0。

### M7. 模型评估指标仍缺正式实验管理

证据文件：`scripts/train_d025_lesion_smoke_model.py`

已有基础 dice/iou/sensitivity/precision，并已补 `model_checkpoint_manifest_20260704.*` 记录模型可用性、checkpoint hash、sidecar manifest/model card 和缺失项；但仍缺交叉验证、患者级拆分审计、阈值曲线、校准、不确定性、失败样本可视化和实验对比表。现有 benchmark/fixture 指标不能作为项目性能。

优先级：P0。

### M8. 外部模型快照不完整

证据文件：`tools/check_project_readiness.py`

readiness 检查仍提示 EGNet 和 FRS Loss 缺关键文件。若后续不走这两条路线，应从“可用模型资产”降级为“文献/代码参考”；若要使用，必须补完整代码和 license 说明。

优先级：P2。

## 5. 数据与研究资产缺口

### R1. 视频库数量可观，但域边界很明显

当前 manifest 状态：

- `research/literature/inventory/video_library_manifest_20260704.csv`：77 条记录，69 条本地存在且为可导入 MP4。
- `research/literature/inventory/ofdvdnet_video_manifest_20260704.csv`：50 条记录。
- `research/literature/inventory/video_download_manifest_20260703.csv`：29 条记录。

这些视频能支撑演示和代理实验，但仍要严格区分：骨髓炎公开视频、教学视频、论文补充视频、mock fluorescence proxy、非荧光手术视频。不能写成真实术中 ICG 颌骨骨髓炎训练集。

优先级：P0。

### R2. 论文资料库还没有形成“可引用 PDF 证据链”

当前 `paper_inventory.csv` 有 60 条记录，`local_paper_assets_20260703.csv` 有 8 条本地资产记录。旧 60 条多数是链接/条目型资料；报告引用仍应优先从本地可读 PDF/HTML 或重新下载后的原文出发。

优先级：P1。

### R3. D042/D044 等候选目录仍有空目录或未落地资产

`tools/check_project_readiness.py` 只确认目录存在，不代表数据完整。MODID、FGS video 等目录需要继续标注“未下载/未解压/不可训练/仅候选”，避免报告里把目录存在写成数据可用。

优先级：P2。

## 6. 工程治理缺口

### G1. 当前工作区改动过多，尚未分批固化

`git status --short` 显示大量前后端、配置、模型、报告、manifest、脚本新增和修改。继续开发前应按主题分批审查和提交，例如：视频输入与 job、导出 DICOM、视频库/OFDVDnet、D025 模型、前端工作台、研究报告。

优先级：P0。

### G2. 生成产物已被忽略，但本地目录仍会干扰判断

`frontend/dist/`、`artifacts/platform_smoke/`、`artifacts/platform/`、checkpoint、derived 数据都在本地存在。它们不进 Git 是对的，但做自查时必须区分“源码能力”和“本机运行产物”。

优先级：P1。

### G3. 依赖版本约束仍不够精确

Python 质量门通过，但模型路线依赖仍未收束：nnU-Net、MedSAM、BiomedCLIP/open_clip、视频 ffmpeg/ffprobe 等还没有明确安装策略和最小版本锁定。前端依赖能 build，但缺真实端到端测试。

优先级：P1。

## 7. 建议开发顺序

1. 补赛点二的可评审模型：当前已完成模型 checkpoint manifest；下一步选择 ConvNeXt/MedNeXt 小模型或 nnU-Net baseline 做正式训练、失败样本和实验对比表，D025 smoke 只保留为链路验证。
2. 补 MP4/JPEG 时间轴：关键帧 -> 图像分割/候选区 -> ROI 量化 -> 导出证据，再增加逐帧/候选区浏览。
3. 补赛点一：OFDVDnet 已有最小去噪/增强/伪彩 baseline；下一步接 dataset loader、稳定性评估和输入输出成对训练流程。
4. 导出规范化：固定 evidence bundle schema v1，后续再做 DICOM SR。
5. 后台任务如需处理真实长 4K 视频，再从 FastAPI BackgroundTasks 迁到 SQLite job queue 或 RQ/Celery。
6. 强化前端评审体验：批量预览/导入、分页/搜索和更完整交互测试。
7. 固化当前工作区：按主题分批检查、提交，避免继续堆 diff。

## 8. 本轮新增修复记录

本轮已完成一项明确缺口修复：赛点一 OFDVDnet 荧光增强 baseline。

- 新增 `src/datasets/ofdvdnet.py`：读取 OFDVDnet 详细 manifest、解析三视图裁剪坐标、读取指定帧并返回 overlay / fluorescence / reference 视图。
- 扩展 `src/preprocess/fluorescence.py`：新增荧光信号增强函数和参考图融合函数，包含去噪、归一化、CLAHE、伪彩和量化。
- 新增 `scripts/run_ofdvdnet_fluorescence_baseline.py`：批处理 48 条可读 OFDVDnet 视频，生成增强图、伪彩图、融合图、baseline manifest 和中英文报告。
- 新增 `tests/unit/test_ofdvdnet_fluorescence_baseline.py`：用临时合成 MP4 验证三视图读取和 baseline 输出。
- 真实运行结果：48 条可读记录全部处理完成；平均阳性面积比例约 `0.0605`，平均 P95 强度约 `0.6328`。该指标仅用于代理增强链路质控，不代表颌骨骨髓炎诊断性能。

本轮还完成一项模型接入修复：ConvNeXt-style 3D 代理分割模型进入正式 adapter。

- 新增 `convnext3d_segmenter` family，对应适配器 `ConvNeXt3DLesionSegmenterAdapter`。
- 更新 `configs/inference/osteo_vision.yml`：新增 `convnext3d_d025_proxy_segmenter`，并把 `model_version` 改为 `osteo-vision-convnext3d-proxy-v0`，顶层 checkpoint 改为真实存在的 `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`，避免旧 `demo_model.pt` 造成误报。
- 更新 `configs/tasks/osteo_vision.yml`：将 `convnext3d_d025_proxy_segmenter` 纳入推荐模型。
- 新增 `research/reports/modeling/convnext3d_proxy_adapter_20260704_zh.md` 和英文版。
- 真实配置推理验证：D025 本地 `npz_roi` 样本可完成主线分割，输出 model family `convnext3d_segmenter` 和 `npz_volume_mask`。

本轮继续完成一项模型证据链修复：生成 checkpoint manifest。

- 新增 `scripts/generate_model_checkpoint_manifest.py`：从 `configs/inference/osteo_vision.yml` 读取模型清单，记录 adapter 可用性、checkpoint 是否存在、sha256、sidecar manifest/model card、医学边界和缺失原因。
- 新增 `research/reports/modeling/model_checkpoint_manifest_20260704.json`、`.csv`、`_zh.md`、`_en.md`：当前 7 个模型中 4 个可用，3 个候选模型缺 checkpoint 或 adapter，所有模型 `clinical_claim_allowed=false`。
- 更新 `tools/check_project_readiness.py`：readiness 自查新增 Model Evidence 小节，显示模型总数、可用数和仍缺 checkpoint 的模型。
- 新增 `tests/unit/test_model_checkpoint_manifest.py`：覆盖 manifest 构建、缺 checkpoint 记录、sidecar 读取、JSON/CSV/中英文报告输出。
- 该 manifest 是工程可审计证据，不代表目标域临床性能；`convnext3d_d025_proxy_segmenter` 复用 D025 smoke checkpoint，应继续按 CBCT ROI 代理模型表达。

本轮继续完成一项官方输入质控修复：MP4/JPEG 官方设备 profile。

- 新增 `src/io/official_device_quality.py`：统一评估官方 JPEG/MP4、3840x2160、视频 codec、pix_fmt、bit_rate、rotation 和 ffprobe 可用性。
- 更新 `src/io/image_io.py`、`src/io/video_io.py` 和 `src/preprocess/input_validation.py`：输入 metadata 新增 `official_input_profile`，不满足官方设备 profile 的可读文件会产生非阻断 warning。
- 更新 `backend/src/services/input_service.py` 和 `backend/src/domains/cases/enums.py`：官方规格不匹配会进入病例 `quality_flags`，code 为 `official_profile_mismatch`，避免被误写成文件不可用。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue` 和 `frontend/src/utils/caseDisplay.ts`：上传后和病例输入清单显示“官方规格匹配/需确认”，评审可以直接看到代理视频/图片与赛题官方输入边界的差异。
- 更新 `tests/unit/test_input_validation.py` 和 `backend/tests/contract/test_case_inputs_api.py`：覆盖非 4K MP4、非 JPEG/非 4K 图片的官方 profile 和质量提示。
- 该修复不把非 4K 代理数据拦掉，原因是当前仍需用公开/合成代理数据跑通闭环；报告和前端会明确提示其不是官方 4K 目标输入。

本轮继续完成一项 MP4 闭环效率修复：上传预抽帧进入分析复用。

- 更新 `src/preprocess/video.py`：每次抽帧都会写入 `keyframe_manifest.json`，记录源视频、采样策略、关键帧路径、质量摘要和 manifest 路径。
- 更新 `backend/src/services/analysis_service.py`：MP4 分析会优先查找 `uploads/keyframes/<upload_stem>/keyframe_manifest.json`；当源路径、采样策略和帧数满足条件时直接复用上传阶段关键帧。
- 分析结果新增 `fused_outputs.keyframe_report_source`、`fused_outputs.keyframe_manifest_path` 和 `quantitative_summary.keyframe_source`，可审计是否复用了上传预抽帧。
- 新增 `backend/tests/contract/test_case_inputs_api.py::test_video_analysis_reuses_uploaded_keyframes`：覆盖上传 MP4、后台预抽帧、写入病例、运行分析、复用 manifest 和 evidence bundle artifact 路径。
- 该修复减少重复解码，保证“上传 -> 预览关键帧 -> 分析 -> 导出”使用同一批可追溯关键帧；后续还需做医生指定时间点和完整时间轴缓存。

本轮继续完成一项病例存储安全修复：version 乐观锁。

- 更新 `backend/src/domains/cases/schemas.py`：`CaseRecord` 增加 `version` 字段，默认从 1 开始。
- 更新 `backend/src/domains/cases/repository.py`：SQLite 与 JSON 仓库的 `save()` 都会校验版本，成功保存自动递增；SQLite 使用事务和 `WHERE case_id AND version` 防止并发覆盖。
- 新增 `CaseVersionConflictError`，并在 `backend/src/api/app.py` 注册 409 `case_version_conflict` 响应，提示前端重载病例后重试。
- 更新 `frontend/src/types/case.ts` 和 `frontend/src/pages/CaseManagementPage.vue`：前端类型包含病例版本，病例管理页显示 `vN`。
- 扩展 `backend/tests/unit/test_case_repository.py`：覆盖 SQLite/JSON 两份旧病例对象并发保存时，第二次 stale save 被拒绝，原保存结果不被覆盖。
- 该修复解决静默覆盖问题；后续仍需表级追加写入或冲突重放，才能让后台 job 与人工复核在高并发下更自然地合并。

本轮新增一项官方输入桥接修复：JPEG/MP4 关键帧热点分割 baseline。

- 新增 `src/models/hotspot_segmenter.py`：对 2D 荧光样图或关键帧执行增强、阈值、连通区候选生成和 mask/overlay 输出。
- 新增 `fluorescence_hotspot_segmenter` adapter，并在 `configs/inference/osteo_vision.yml` 中注册 `fluorescence_hotspot_2d_segmenter`。
- `backend/src/services/analysis_service.py` 的 MP4 分析路径现在会对关键帧生成 `hotspot_outputs`、候选区、热点量化摘要和 ROI mask/heatmap/overlay artifacts。
- 新增 `research/reports/modeling/jpeg_mp4_hotspot_bridge_20260704_zh.md` 和英文版。
- 真实配置 JPEG 推理验证：`tests/fixtures/platform/fluorescence.png` 可输出 `model_family=fluorescence_hotspot_segmenter` 和 `png_binary_mask`。

本轮继续完成一项前端闭环修复：MP4 hotspot 输出进入工作台可视化。

- 更新 `frontend/src/components/analysisPreview.ts`：新增 MP4 预览派生逻辑，优先从 `hotspot_outputs` 读取关键帧、热点叠加图和热点掩膜；若没有 hotspot 输出，再回退到普通关键帧。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：MP4 分析完成提示改为同时显示抽帧数量和热点候选区数量；上传关键帧轮询最多约 180 秒。
- 更新 `frontend/src/stores/caseStore.ts`：后台分析 job 轮询最多约 300 秒，并保留任务 ID、任务状态和超时标记，避免长视频分析被 15 秒短窗口误判。
- 更新 `frontend/src/components/AnalysisResultPanels.vue`：视频模式下摘要优先展示 `hotspot_frame_count`、`hotspot_candidate_count`、最大/平均关键帧阳性占比；候选区面积展示改为候选分数对应的阳性占比。
- 新增 `frontend/tests/AnalysisPreviewPanels.test.ts`：覆盖 hotspot 输出优先展示和无 hotspot 时回退关键帧的逻辑。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 均通过；平台 smoke 仍可生成 `artifact_count=20`、frame index/detail manifest 和 evidence bundle。

本轮继续完成一项导出体验修复：证据包从“路径文本”升级为可下载文件列表。

- 更新 `backend/src/api/files.py`：新增 `/files/download` 接口，只允许下载 artifact 根目录内的 `.zip`、`.json`、`.md`、`.csv`、`.dcm` 和常见图片文件，避免任意路径下载。
- 更新 `frontend/src/services/apiClient.ts`：新增 `fileDownloadUrl()`。
- 更新 `frontend/src/stores/caseStore.ts`：保存完整 `ExportResponse`，不再只保存 bundle path。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue` 和 `frontend/src/components/AnalysisWorkspaceCard.vue`：导出后显示证据包 ZIP、JSON 报告、manifest、DICOM 二次捕获的下载入口，并保留本地路径。
- 更新 `backend/tests/contract/test_export_api.py` 和 `frontend/tests/ExportPanel.test.ts`：覆盖证据包下载接口和前端下载 URL。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和平台 smoke 均通过。并发运行 `conda run` 时曾触发 Windows 临时文件占用，顺序重跑后通过。

本轮继续完成一项长视频任务体验修复：后台分析任务可继续查询。

- 更新 `frontend/src/stores/caseStore.ts`：将后台分析 job 轮询拆为可复用 `pollAnalysisJob()`，新增 `refreshActiveAnalysisJob()`，允许超时后查询同一个 job 并刷新病例结果，避免重复提交分析任务。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：新增后台分析任务状态面板，显示 job ID、状态、错误/超时提示和“继续查询”按钮。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：接入继续查询动作，并把查询结果同步到页面操作提示。
- 新增 `frontend/tests/CaseStoreJobs.test.ts`：验证继续查询已存在 job 时不会重新启动分析任务，并会刷新病例分析结果。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 均通过。

本轮继续完成一项任务控制修复：后台分析任务支持取消和重试。

- 更新 `backend/src/services/job_service.py`：新增 `cancel()` 和 `is_canceled()`，并让 `mark_running()`、`mark_completed()`、`mark_failed()` 不覆盖已取消任务状态。
- 更新 `backend/src/api/analysis_runs.py`：新增 `POST /analysis-jobs/{job_id}/cancel`，只允许取消 case analysis job；后台任务运行前后都会检查 canceled 状态。
- 更新 `frontend/src/services/apiClient.ts`：`BackendJob.status` 增加 `canceled`，新增 `cancelAnalysisJob()`。
- 更新 `frontend/src/stores/caseStore.ts`：新增 `cancelActiveAnalysisJob()` 和 `retryActiveAnalysisJob()`，重试会读取旧 job payload 并提交新 job。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue` 和 `frontend/src/pages/CaseWorkspacePage.vue`：任务面板新增“取消”和“重试”按钮，并同步操作提示。
- 更新 `backend/tests/unit/test_job_service.py`、`backend/tests/contract/test_case_inputs_api.py` 和 `frontend/tests/CaseStoreJobs.test.ts`：覆盖 canceled 状态保护、取消端点和前端取消/重试路径。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过。

本轮继续完成一项任务详情修复：后台任务增加持久化进度。

- 更新 `backend/src/services/job_service.py`：job 创建时写入 `progress`，运行、完成、失败、取消和服务重启失败都会保留阶段、百分比、消息和可选 details。
- 更新 `backend/src/api/analysis_runs.py` 和 `backend/src/api/uploads.py`：分析 job 与 MP4 关键帧抽取 job 在主要阶段更新进度。
- 更新 `frontend/src/services/apiClient.ts` 和 `frontend/src/stores/caseStore.ts`：前端保存并同步 `BackendJob.progress`。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：后台任务面板显示进度条、百分比和阶段消息。
- 更新 `backend/tests/unit/test_job_service.py`、`backend/tests/contract/test_case_inputs_api.py` 和 `frontend/tests/CaseStoreJobs.test.ts`：覆盖进度持久化、完成进度和前端进度同步。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过。并发 `conda run` 曾触发 Windows 临时文件占用，顺序重跑后通过。

本轮继续完成一项导出可评审性修复：导出响应和前端面板增加 manifest 摘要。

- 更新 `backend/src/domains/cases/schemas.py`：`ExportResponse` 新增 `summary` 和 `artifact_entries`。
- 更新 `backend/src/services/export_service.py`：导出时生成 `osteo-vision-export-summary-v1`，记录分析次数、候选区数量、核心/包含证据文件数量、量化行数、bundle 大小、包含格式和 DICOM 状态，并返回所有核心导出文件与病例证据文件条目。
- 更新 `frontend/src/types/case.ts`、`frontend/src/pages/CaseWorkspacePage.vue` 和 `frontend/src/components/AnalysisWorkspaceCard.vue`：前端导出区显示导出摘要和证据文件列表，避免评审只能看到 zip 路径或下载按钮。
- 更新 `backend/tests/contract/test_export_api.py`、`backend/tests/unit/test_export_service.py` 和 `frontend/tests/ExportPanel.test.ts`：覆盖导出摘要、DICOM 包含状态和证据包条目。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 导出响应已包含 `summary.total_artifact_count=26` 和完整 `artifact_entries`。

本轮继续完成一项前端评审可用性修复：公开视频候选详情与调试信息收敛。

- 新增 `frontend/src/utils/videoCandidates.ts`：集中格式化公开视频候选的荧光/非荧光属性、文件大小、读取状态、来源链接和详情字段。
- 更新 `frontend/src/components/CaseWorkspaceControls.vue`：公开视频候选从单一下拉框升级为详情卡，展示标题、record_id、荧光属性、医学场景、训练可用性、文件大小、读取状态、数据边界和原始来源链接；“实时视频”按钮文案改为“实时预览”，避免误导为已接入流式 AI。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：开发调试 JSON 面板改为仅在 Vite dev 环境且 URL 带 `?debug` 时显示，默认演示不暴露本地路径和完整病例对象。
- 新增 `frontend/tests/VideoCandidateDetails.test.ts`：覆盖候选选择、荧光标签、可读状态、来源链接、文件大小和数据边界字段。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 均通过；当前前端测试为 7 个文件、11 个测试通过。`conda run -n osteo-vision python tools/run_platform_smoke.py` 同步通过，最新摘要为 `artifacts/platform_smoke/20260703T181900Z/platform_smoke_summary.json`。

本轮继续完成一项官方输入质量修复：上传内容签名与视频探针增强。

- 新增 `src/io/content_probe.py`：读取文件头，识别 JPEG、PNG、BMP、TIFF、MP4 `ftyp` 和 HTML/captcha 类伪文件，并提供扩展名一致性检查。
- 更新 `backend/src/api/uploads.py`：上传落盘后、进入病例前先校验扩展名和内容签名；伪图片/伪 MP4 会返回 415，不再进入后续分析链路；同时保留 content-type mismatch 的非阻塞 warning。
- 更新 `src/io/video_io.py`：视频 metadata 增加 `content_probe`、`official_resolution_match` 和可用时的 ffprobe stream/format 信息。
- 更新 `tests/unit/test_input_validation.py` 和 `backend/tests/contract/test_case_inputs_api.py`：覆盖伪图片上传拦截、MP4 content probe、官方分辨率匹配字段和签名 mismatch 检测。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q` 均通过；当前 Python 测试为 92 个通过，仍有 FastAPI TestClient 和 torch JIT deprecation warning。`conda run -n osteo-vision python tools/run_platform_smoke.py` 同步通过，最新摘要为 `artifacts/platform_smoke/20260703T181900Z/platform_smoke_summary.json`。

本轮继续完成一项医生复核闭环修复：ROI 画布从占位升级为可保存标注。

- 重写 `frontend/src/components/RoiCanvas.vue`：支持在画布上拖拽创建归一化矩形 ROI，设置 ROI 标签与复核状态，展示已保存 ROI，并提供清除/保存操作。
- 新增 `frontend/src/utils/roiGeometry.ts`：统一矩形 ROI 的归一化、面积计算、后端 payload 和 persisted geometry 读取。
- 更新 `frontend/src/pages/ReviewWorkspacePage.vue`：接入 `RoiCanvas` 的保存事件，保存后调用后端 region API 写入病例 `rois`，并追加 `manual_roi_saved` 复核事件。
- 更新 `frontend/src/services/apiClient.ts` 和 `frontend/src/stores/caseStore.ts`：`updateRegion()` 支持 geometry、label 和 review state 一起提交。
- 新增 `frontend/tests/RoiGeometry.test.ts`：覆盖拖拽点转矩形、归一化 payload、面积和 persisted ROI 读取。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 均通过；当前前端测试为 8 个文件、13 个测试通过。`conda run -n osteo-vision python -m pytest backend/tests/contract/test_review_api.py -q` 通过；并发 `conda run` 曾触发 Windows 临时文件占用，顺序重跑后通过。`conda run -n osteo-vision python tools/run_platform_smoke.py` 同步通过，最新摘要为 `artifacts/platform_smoke/20260703T181900Z/platform_smoke_summary.json`。

本轮继续完成一项 ROI 反向约束修复：已保存 ROI 进入后续分析。

- 新增 `src/preprocess/roi.py`：统一读取归一化矩形 ROI，提供 ROI 强度量化和候选 bbox 与 ROI 重叠筛选。
- 更新 `src/preprocess/fluorescence.py`：双通道融合报告的 `quantification` 增加 ROI 内阳性面积、平均强度、P95 强度和逐 ROI 明细。
- 更新 `src/models/hotspot_segmenter.py`：2D/MP4 hotspot baseline 支持 `roi_hints`，候选连通区会按 ROI 重叠过滤，并记录过滤前后候选数。
- 更新 `backend/src/services/analysis_service.py`：后端会把病例中已保存的 `rois` 与请求 `roi_hints` 合并；双通道候选评分优先使用 ROI 内强度，MP4 分析记录 `roi_filter_applied`、ROI 内 hotspot 面积比例等摘要。
- 更新 `frontend/src/services/apiClient.ts`、`frontend/src/stores/caseStore.ts` 和 `frontend/src/pages/CaseWorkspacePage.vue`：工作台重新运行双通道、MP4 或实时预览分析时，会把当前病例已保存 ROI 作为 `roi_hints` 提交。
- 新增 `tests/unit/test_roi_preprocess.py`，并扩展 `backend/tests/contract/test_case_inputs_api.py`：覆盖已保存 ROI 自动进入分析、ROI 量化和候选筛选。
- 验证结果：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；当前 Python 测试为 96 个通过，最新 smoke 摘要为 `artifacts/platform_smoke/20260703T183714Z/platform_smoke_summary.json`。

本轮继续完成一项关键帧策略修复：MP4 抽帧从单一均匀采样升级为质量/信号优先。

- 更新 `src/preprocess/video.py`：新增默认 `quality_peak` 采样策略，在有限候选池中计算荧光样信号、清晰度和曝光质量评分，选择时间上分散的高分帧；同时保留 `uniform` 策略作为可选回退。
- 关键帧结果新增 `sampling_strategy`、`selection_trace`、`selection_score`、`selection_rank` 和更完整的质量摘要，方便报告说明和问题排查。
- 更新 `backend/src/services/analysis_service.py`：MP4 分析路径可通过 `keyframe_sampling_strategy` 参数指定采样策略，默认使用 `quality_peak`。
- 新增 `tests/unit/test_video_preprocess.py`：覆盖质量/信号优先策略会选中荧光样热点帧，并确认 uniform 策略仍保持可用。
- 验证结果：`conda run -n osteo-vision python check_env.py`、`conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 摘要为 `artifacts/platform_smoke/20260703T191635Z/platform_smoke_summary.json`。

本轮继续完成一项后端存储修复：病例仓库默认迁移到 SQLite。

- 新增 `SQLiteCaseRepository`：以 `cases` 表保存完整病例 payload，启用 WAL journal，写入时使用 `BEGIN IMMEDIATE` 事务，并提供 `export_json()` 保留 JSON 导出能力。
- 新增 `build_case_repository()`：`.json` 路径继续使用 `JsonCaseRepository`，非 JSON 默认使用 SQLite，兼容现有测试与临时工作流。
- 更新 `backend/src/core/settings.py`：默认 `case_store_path` 从 `artifacts/platform/cases.json` 改为 `artifacts/platform/cases.sqlite`，新增 `case_store_backend`，也可通过 `OSTEO_CASE_STORE_BACKEND` 显式覆盖。
- 更新 `backend/src/api/routes.py`：平台 API 不再硬编码 JSON 仓库，`/ready` 会返回当前存储路径和存储后端。
- 更新 `tools/run_platform_smoke.py`：平台 smoke 的临时病例仓库改用 `cases.sqlite`，让 smoke 覆盖新主线。
- 新增 `backend/tests/unit/test_case_repository.py`，并更新 `tests/unit/test_platform_artifact_locations.py`：覆盖 SQLite 持久化、JSON 导出、仓库选择兼容和默认路径。
- 验证结果：`conda run -n osteo-vision python -m pytest backend/tests/unit/test_case_repository.py tests/unit/test_platform_artifact_locations.py backend/tests/contract/test_case_inputs_api.py::test_case_input_and_analysis_contract -q`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 已使用 `cases.sqlite` 临时仓库。

本轮继续完成一项后台任务修复：进程内 job 增加限流和任务锁。

- 更新 `backend/src/services/job_service.py`：新增 active job 判定、`JobCapacityError` 和 `JobConflictError`；`create()` 支持 `max_active` 与 `singleton_keys`，可在同一锁内原子检查容量和重复任务。
- 更新 `backend/src/core/settings.py`：新增 `max_active_case_analysis_jobs` 和 `max_active_upload_keyframe_jobs`，分别可通过 `OSTEO_MAX_ACTIVE_CASE_ANALYSIS_JOBS` 与 `OSTEO_MAX_ACTIVE_UPLOAD_KEYFRAME_JOBS` 配置，默认各允许 1 个活动任务。
- 更新 `backend/src/api/analysis_runs.py`：`case_analysis` job 按 `case_id` 加锁；同一病例已有 queued/running 分析任务时返回 409，活动任务超限时返回 429。
- 更新 `backend/src/api/uploads.py`：MP4 上传关键帧异步任务按 `source_path` 加锁；活动关键帧任务超限时返回 429，并清理已落盘的上传文件，避免失败上传残留。
- 更新 `backend/src/api/routes.py`：把配置中的限流参数传入 analysis 与 uploads 路由。
- 更新 `backend/tests/unit/test_job_service.py` 和 `backend/tests/contract/test_case_inputs_api.py`：覆盖容量限制、同 key 锁、任务完成后可再次提交、分析 job 429 和上传关键帧 job 429。
- 验证结果：`conda run -n osteo-vision python -m pytest backend/tests/unit/test_job_service.py backend/tests/contract/test_case_inputs_api.py::test_analysis_job_capacity_limit_returns_429 backend/tests/contract/test_case_inputs_api.py::test_upload_keyframe_job_capacity_limit_returns_429 -q`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 摘要为 `artifacts/platform_smoke/20260703T191635Z/platform_smoke_summary.json`。

本轮继续完成一项后台任务修复：新增本地持久 worker 和 worker 执行模式。

- 更新 `backend/src/services/job_service.py`：新增 `list_jobs()`、`claim_next_queued()` 和读取时落盘刷新；queued job 重启后保留，running job 初始化时仍按未完成任务标记 failed，避免卡死。
- 新增 `backend/src/services/job_worker.py`：`LocalJobWorker` 可处理 `case_analysis` 与 `upload_keyframe_extraction` queued job，完成后写回 job result/progress。
- 新增 `tools/run_job_worker_once.py`：提供一次性 drain CLI，支持 `--limit` 和重复 `--kind`。
- 更新 `backend/src/core/settings.py`、`backend/src/api/routes.py`、`backend/src/api/analysis_runs.py` 和 `backend/src/api/uploads.py`：新增 `job_store_path` 和 `OSTEO_JOB_EXECUTION_MODE=worker`，worker 模式下 API 只入队，不再交给 FastAPI BackgroundTasks 立即执行；`/ready` 返回 job store 与执行模式。
- 更新 `backend/tests/unit/test_job_service.py`、`backend/tests/unit/test_job_worker.py` 和 `backend/tests/contract/test_case_inputs_api.py`：覆盖 queued job 重启保留、最早 queued claim、worker 处理 case analysis、worker 处理上传关键帧，以及 worker 模式下 API 入队后由本地 worker 完成。
- 验证结果：`conda run -n osteo-vision python -m ruff check backend/src/services/job_service.py backend/src/services/job_worker.py backend/src/core/settings.py backend/src/api/routes.py backend/src/api/analysis_runs.py backend/src/api/uploads.py backend/tests/unit/test_job_service.py backend/tests/unit/test_job_worker.py backend/tests/contract/test_case_inputs_api.py tools/run_job_worker_once.py --output-format concise`、`conda run -n osteo-vision python -m pytest backend/tests/unit/test_job_service.py backend/tests/unit/test_job_worker.py backend/tests/contract/test_case_inputs_api.py -q` 和 `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` 均通过。

本轮继续完成一项前端评审体验修复：公开视频候选支持关键帧预览。

- 更新 `backend/src/services/video_library_service.py`：`VideoLibraryService` 支持 `preview_root`，新增 `ensure_preview()`，对本地可读 MP4 按需生成 `preview.jpg`，并返回 preview 状态、帧索引、分辨率、fps 和时长。
- 更新 `backend/src/api/video_library.py`：新增 `POST /video-library/candidates/{record_id}/preview`，不可读候选返回 422，可读候选返回带 `preview_path` 的候选 payload。
- 更新 `backend/src/api/routes.py`：公开视频预览目录固定在 `settings.artifact_root / "video_library_previews"`，因此可复用 `/files/preview` 的 artifact root 安全限制。
- 更新 `frontend/src/types/case.ts`、`frontend/src/services/apiClient.ts` 和 `frontend/src/utils/videoCandidates.ts`：前端候选类型新增 preview 字段，API client 新增 `createVideoCandidatePreview()`，详情字段新增视频规格和预览状态。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue` 与 `frontend/src/components/CaseWorkspaceControls.vue`：选择公开视频候选时自动生成/复用预览图，并在候选详情卡中显示关键帧缩略图。
- 更新 `backend/tests/unit/test_video_library_service.py`、`backend/tests/contract/test_case_inputs_api.py` 和 `frontend/tests/VideoCandidateDetails.test.ts`：覆盖预览生成、预览文件访问、前端规格和预览状态格式化。
- 验证结果：`conda run -n osteo-vision python -m pytest backend/tests/unit/test_video_library_service.py backend/tests/contract/test_case_inputs_api.py::test_video_library_candidate_can_be_imported_as_case_input -q`、`npm --prefix frontend test -- --run VideoCandidateDetails.test.ts`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 摘要为 `artifacts/platform_smoke/20260703T191635Z/platform_smoke_summary.json`。

本轮继续完成一项前端数据管理修复：公开视频筛选与独立视频库页。

- 更新 `frontend/src/utils/videoCandidates.ts`：新增荧光/非荧光筛选、训练用途分桶、候选过滤和筛选结果摘要函数。
- 更新 `frontend/src/components/CaseWorkspaceControls.vue`：工作台公开视频候选下拉框增加“通道”和“用途”筛选，候选数量会按当前筛选动态显示。
- 新增 `frontend/src/pages/DataLibraryPage.vue`：提供独立 `/data` 视频库页，展示本地可读候选总数、荧光/非荧光数量、训练用途分布、本地文件体量，并支持按需生成预览、打开原始来源和导入当前病例。
- 更新 `frontend/src/router/index.ts` 与 `frontend/src/App.vue`：把视频库页接入路由和顶部导航。
- 更新 `frontend/tests/VideoCandidateDetails.test.ts`：覆盖公开视频候选按荧光通道和训练用途筛选。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run` 和 `npm --prefix frontend run build` 均通过；当前前端测试为 8 个文件、15 个测试通过。

本轮继续完成一项 MP4 评审体验修复：热点输出增加时间轴。

- 更新 `frontend/src/components/analysisPreview.ts`：新增 `hotspotTimelineFromRun()`，从 `fused_outputs.hotspot_outputs` 提取帧号、时间戳、候选区数量、阳性面积比例、ROI 命中比例和预览图。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：在四宫格结果下方展示“MP4 热点时间轴”，便于评审快速看到每个关键帧的热点强度和 ROI 命中情况。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：将最新 analysis run 的 hotspot timeline 传入分析卡片。
- 更新 `frontend/tests/AnalysisPreviewPanels.test.ts`：覆盖热点时间轴派生字段、百分比格式和预览 URL。
- 验证结果：`npm --prefix frontend run typecheck` 和 `npm --prefix frontend test -- --run AnalysisPreviewPanels.test.ts` 均通过；后续仍需补更完整的 bbox/ROI 编辑。

本轮继续完成一项候选复核闭环修复：MP4 hotspot 候选可转为 AI ROI。

- 更新 `backend/src/domains/cases/schemas.py`：`CandidateRegion` 新增 `metadata` 字段，用于保存帧号、时间戳、bbox、归一化 rect、热点面积比例和证据图路径。
- 更新 `backend/src/services/analysis_service.py`：MP4 hotspot 候选会记录 top 连通区 `bbox_xyxy` 和 `bbox_normalized`，为后续 ROI 复核提供几何依据。
- 更新 `backend/src/services/review_service.py` 与 `backend/src/api/regions.py`：新增候选区转 ROI 能力，`POST /cases/{case_id}/regions/from-candidate/{candidate_id}` 会把候选 metadata 中的 bbox 转为 AI ROI。
- 更新 `frontend/src/services/apiClient.ts`、`frontend/src/stores/caseStore.ts`、`frontend/src/components/CandidateRegionList.vue` 和 `frontend/src/pages/ReviewWorkspacePage.vue`：复核页候选列表显示帧位置与 bbox，并提供“转为 ROI”入口。
- 更新 `backend/tests/contract/test_case_inputs_api.py`：覆盖 MP4 分析候选带 bbox metadata，并验证候选转 AI ROI 后 geometry 与 metrics 写入病例。
- 验证结果：`conda run -n osteo-vision python -m pytest backend/tests/contract/test_case_inputs_api.py::test_video_input_analysis_extracts_keyframes -q`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 摘要为 `artifacts/platform_smoke/20260703T204957Z/platform_smoke_summary.json`。

本轮继续完成一项预览复核修复：分析预览图叠加 ROI 与候选框。

- 更新 `frontend/src/components/analysisPreview.ts`：新增 `AnalysisPreviewOverlay`、`candidateOverlaysFromRegions()` 和 `roiOverlaysFromRegions()`，统一把候选 bbox 与已保存 ROI 转成归一化叠加框。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：把当前病例已保存 ROI 和最新候选 bbox 传入分析预览面板。
- 更新 `frontend/src/components/AnalysisQuadGrid.vue`：在关键帧、热点叠加、掩膜和双通道结果图上绘制 ROI/候选叠加框，候选框与 ROI 使用不同视觉样式。
- 更新 `frontend/tests/AnalysisPreviewPanels.test.ts`：覆盖候选框和 ROI 叠加框的派生逻辑。
- 验证结果：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q` 和 `conda run -n osteo-vision python tools/run_platform_smoke.py` 均通过；最新 smoke 摘要为 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`。后续仍需补更多真实图像纵横比和失败态截图验证。

## 9. 2026-07-04 二次复查补充：排除外部数据依赖后的剩余缺口

本次复查继续排除“真实项目病例”和“医生关键帧/ROI 标注”两个短期做不了的外部前置项，重点看代码、模型、数据治理和可评审闭环。当前结论是：项目不是“跑不起来”，而是 Demo 能跑、证据能出，但模型真实性、视频交互深度、导出标准化、工程固化和浏览器级验证仍不足。

### 9.1 后端代码缺口

| 编号 | 缺口 | 证据位置 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| B-01 | `realtime_video` 仍只是登记浏览器摄像头输入，后端明确返回“streaming AI inference is not connected”，没有真正帧采样、缓存、推理和流式输出。 | `backend/src/services/analysis_service.py`、`frontend/src/pages/CaseWorkspacePage.vue` | P1 | 若比赛不展示实时 AI，界面统一叫“实时预览/接口预留”；若要展示，先做低帧率抽样 + hotspot baseline。 |
| B-02 | 病例仓库虽迁到 SQLite 并有 version 乐观锁，但 ROI、analysis run、artifact、review event 仍整体 payload 保存，冲突后不能自动合并。 | `backend/src/domains/cases/repository.py` | P1 | 把 ROI、analysis run、artifact、review event 改成表级追加或补 409 后前端重载/重试流程。 |
| B-03 | job 系统是本地 JSON 队列 + 一次性 worker，能演示但还不是常驻队列；缺优先级、租约、跨进程锁、可观测性面板和失败重试策略。 | `backend/src/services/job_service.py`、`backend/src/services/job_worker.py`、`tools/run_job_worker_once.py` | P1 | 短期保留 worker 模式；长视频稳定后评估 SQLite job queue、RQ 或 Celery。 |
| B-04 | 4K MP4/JPEG 只做了 profile 检查，没有真实 4K 长视频压力测试、旋转归一化、分片上传、码率/色彩空间策略。 | `src/io/official_device_quality.py`、`backend/src/api/uploads.py` | P1 | 用代理 4K MP4 做上传、抽帧、分析、导出压力测试，并记录失败分级。 |
| B-05 | 双通道融合仍是 resize + 归一化 + alpha blend，缺配准、背景扣除、颜色标尺、时序峰值和更严谨的 ROI 统计。 | `src/preprocess/fluorescence.py` | P0 | 先做赛点一 V2：配准/背景扣除/颜色标尺/ROI 报告。 |
| B-06 | MP4 hotspot 已进入候选区，前端已有时间轴筛选；本轮已补 `frame_index_manifest.json`、分析 `frame_details`、`frame_details_manifest.json` 和用户指定秒级时间点抽帧。仍缺整段视频时间轴缓存、运动去重和逐帧重算。 | `src/preprocess/video.py`、`backend/src/services/analysis_service.py` | P0 | 基于现有 manifest 继续做跳转、重算和运动去重。 |
| B-07 | 导出是 evidence bundle + DICOM Secondary Capture，不是 DICOM SR；bundle schema 还没有正式文档和版本兼容说明。 | `backend/src/services/export_service.py`、`backend/src/reports/dicom_secondary_capture.py` | P1 | 固定 `osteo-vision-export-summary-v1` 和 bundle schema v1，再决定是否做 DICOM SR。 |
| B-08 | `/files/preview`、`/files/download` 只做 artifact root 和后缀限制，没有登录、token、一次性链接、审计日志。 | `backend/src/api/files.py` | P2 | 单机演示可接受；远程协作前补最小 token 或 session。 |

### 9.2 前端代码缺口

| 编号 | 缺口 | 证据位置 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| F-01 | Playwright Chromium 浏览器级闭环已能证明 `/cases`、`/case`、`/review`、`/report`、`/data` 在桌面视口下可打开，并完成“建病例 -> 双通道分析 -> 候选区接受 -> ROI 复核 -> 导出 -> 视频库”“MP4 上传 -> MP4 keyframe hotspot 分析 -> 热点时间轴筛选/点击切换 -> 公开视频导入 -> 病例输入同步”，且已补移动端工作台和全屏分析视图截图验证。 | `frontend/e2e/platform.browser.pw.ts`、`frontend/playwright.config.ts` | P2 | 下一步补 API 失败态、摄像头状态和演示录像。 |
| F-02 | MP4 热点时间轴已能点击切换四宫格当前帧，并能按阳性面积、ROI 命中或候选数量做条件筛选；本轮已补当前帧详情面板，展示候选数量、阳性面积、ROI 命中、Top BBox 和证据链接。剩余是详情抽屉/页、逐帧重算和后端完整时间轴缓存。 | `frontend/src/components/AnalysisWorkspaceCard.vue`、`frontend/src/components/analysisPreview.ts` | P2 | 增加更完整详情抽屉/页，并继续对齐后端重算和跳转能力。 |
| F-03 | 候选区现在可直接接受/拒绝/修改，后端会写回 `CandidateRegion.status` 并追加 `candidate_region_state_update` 复核事件；剩余缺口是候选几何编辑和更完整的修改历史。 | `frontend/src/components/CandidateRegionList.vue`、`frontend/src/pages/ReviewWorkspacePage.vue`、`backend/src/services/review_service.py` | P2 | 下一步补候选 bbox 编辑和修改前后对比。 |
| F-04 | ROI/候选框已能叠加到预览图，Playwright 已补移动端和桌面全屏截图，并校验横向溢出与空白图片；剩余是更多真实图像比例下的 overlay 坐标人工复核。 | `frontend/src/components/AnalysisQuadGrid.vue`、`frontend/e2e/platform.browser.pw.ts` | P2 | 用更多真实 4K/JPEG/MP4 输出图检查 overlay 坐标。 |
| F-05 | 视频库页已有筛选、预览、导入，但缺搜索、分页、批量预览、批量导入和批量打标签。 | `frontend/src/pages/DataLibraryPage.vue` | P2 | 下一步做搜索/分页，批量能力可后置。 |
| F-06 | 前端 API 地址是构建时 `VITE_OSTEO_API_URL`，打包后改部署地址不方便。 | `frontend/src/services/apiClient.ts` | P2 | 增加运行时配置 JSON 或启动脚本注入。 |
| F-07 | 本地路径输入仍是显眼入口，只适合同机演示；远程评审时路径不可用。 | `frontend/src/components/CaseWorkspaceControls.vue` | P1 | 把上传和视频库入口作为默认主入口，本地路径标为“本机调试”。 |

### 9.3 模型缺口

| 编号 | 缺口 | 证据位置 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| M-01 | 当前 7 个模型中只有 4 个可用；nnU-Net、MedSAM-like、BiomedCLIP 均不可用。 | `scripts/model_inventory.py` 输出、`research/reports/modeling/model_checkpoint_manifest_20260704.json` | P0 | 先选一个正式主线训练，不要继续只堆候选名。 |
| M-02 | 可用的 `convnext3d_d025_proxy_segmenter` 和 `d025_lesion_smoke_segmenter` 复用 D025 CBCT ROI 代理 checkpoint，不是术中 ICG MP4/JPEG 目标域模型。 | `configs/inference/osteo_vision.yml`、`src/models/adapters.py` | P0 | 把 ConvNeXt/MedNeXt 作为 CBCT 代理主线训练，报告中严格写“代理模型”。 |
| M-03 | `fluorescence_hotspot_2d_segmenter` 是阈值/连通区启发式 baseline，不是训练模型；只能支撑赛点一/二平台展示。 | `src/models/hotspot_segmenter.py`、`src/models/adapters.py` | P0 | 用公开荧光视频帧做自监督增强或弱监督分割 baseline，再和阈值 baseline 对比。 |
| M-04 | MedSAM-like adapter 仍未实现推理，也未定义 point/box/mask prompt 数据合同；ROI 画布还未接入 promptable model。 | `src/models/adapters.py`、`frontend/src/components/RoiCanvas.vue` | P1 | 若走 MedSAM，先实现 2D frame box prompt 最小闭环。 |
| M-05 | nnU-Net adapter 未实现，checkpoint 目录缺失；CBCT 代理数据还没转成 nnU-Net 标准 dataset + train/infer 流程。 | `src/models/adapters.py`、`configs/inference/osteo_vision.yml` | P1 | 做 D025/ToothFairy2 到 nnU-Net 格式转换和最小训练脚本。 |
| M-06 | BiomedCLIP 缺 `open_clip` 与 checkpoint，且对分割帮助有限，当前更适合后置为图像级检索/说明，不宜做主线。 | `configs/inference/osteo_vision.yml`、`src/models/adapters.py` | P2 | 暂不作为近期主线；等分割闭环稳定后再接。 |
| M-07 | 模型评估缺正式交叉验证、患者级拆分审计、阈值曲线、失败样本、校准和不确定性。 | `scripts/train_d025_lesion_smoke_model.py` | P0 | 建立 experiment report：Dice/IoU/HD95、阈值曲线、失败样本图。 |
| M-08 | EGNet 和 FRS Loss 快照缺关键文件，不能列为可用模型资产。 | `tools/check_project_readiness.py` | P2 | 仅作为文献/代码参考，除非补齐源码和 license。 |

### 9.4 数据、研究和工程治理缺口

| 编号 | 缺口 | 证据位置 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| D-01 | 视频库有 77 条 manifest、69 条本地可导入 MP4，但多为非目标域公开视频/教学视频/代理荧光视频，不能当作真实 ICG 颌骨骨髓炎训练集。 | `research/literature/inventory/video_library_manifest_20260704.csv` | P0 | 每条数据继续标注目标域/非目标域、荧光/非荧光、训练/演示/仅参考。 |
| D-02 | OFDVDnet 代理荧光 baseline 已生成，但还没接入 dataset loader、训练增强任务和稳定性评估。 | `src/datasets/ofdvdnet.py`、`research/literature/inventory/ofdvdnet_fluorescence_baseline_manifest_20260704.csv` | P0 | 做帧级增强数据集和 baseline 对比表。 |
| D-03 | 论文 inventory 有 60 条，local paper assets 只有 8 条；报告引用仍需要更多本地可读 PDF/HTML 原文支撑。 | `research/literature/inventory/paper_inventory.csv`、`local_paper_assets_20260703.csv` | P1 | 下一轮集中补可下载原文和引用摘录。 |
| G-01 | 工作区改动很大：本次 `git status --porcelain` 统计为 modified 69、untracked 70、total 139，风险是后续难以审查和回滚。 | `git status --short` | P0 | 先按主题分批 review，再分批提交：后端 job/输入、前端工作台、模型/数据、报告/manifest。 |
| G-02 | 已有 Playwright Chromium 浏览器闭环、本地截图、移动端工作台截图和全屏分析截图；还缺更多失败状态和可交付操作录像。 | `frontend/e2e/platform.browser.pw.ts`、`artifacts/e2e/browser_smoke/` | P2 | 下一步补失败态截图和一段稳定演示流程录像。 |
| G-03 | 依赖版本没有完全锁住，nnU-Net、MedSAM、BiomedCLIP/open_clip、ffmpeg/ffprobe 安装策略仍未明确。 | `requirements.txt`、`configs/inference/osteo_vision.yml` | P1 | 分模型依赖组写安装说明和失败降级策略。 |

### 9.5 本次二次复查质量门

| 命令 | 结果 |
|---|---|
| `conda run -n osteo-vision python check_env.py` | 通过；Python 3.11.15，无 failure/warning。 |
| `conda run -n osteo-vision python tools/check_project_readiness.py` | 通过；仍提示 EGNet/FRS Loss 快照缺关键文件，nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。 |
| `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml` | 通过；7 个模型，4 个可用，3 个不可用。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；8 个测试文件、18 个测试。 |
| `npm --prefix frontend run build` | 通过。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；仍有 FastAPI TestClient 与 torch JIT deprecation warning。 |
| `npm --prefix frontend run test:e2e` | 通过；3 个 Chromium 浏览器闭环测试通过，8 张截图输出到 `artifacts/e2e/browser_smoke/`。 |
| `conda run -n osteo-vision python tools/run_platform_smoke.py` | 通过；最新摘要 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`。 |
| `git diff --check` | 无 whitespace error；只有 LF 将被 Git 转 CRLF 的 warning。 |

## 10. 2026-07-04 浏览器闭环修复记录

本轮完成一项 P0 工程缺口修复：从“只有组件/逻辑测试”推进到“真实浏览器最小闭环可验证”。

- 新增 `@playwright/test`，并增加 `frontend/playwright.config.ts`：测试会启动隔离端口的 FastAPI 后端和 Vite 前端，后端使用 `.pytest_tmp/playwright/` 下的独立 SQLite、job store 和 artifact root，不污染默认平台数据。
- 新增 `frontend/e2e/platform.browser.pw.ts`：在 Chromium 中执行真实前后端流程，覆盖 `/cases` 新建病例、`/case` 写入双通道 fixture、运行双通道分析、导出证据包、`/review` 手动 ROI 绘制保存、`/report` 报告页打开、`/data` 视频库列表打开。
- 新增截图证据：`artifacts/e2e/browser_smoke/01-case-workspace.png`、`02-review-workspace.png`、`03-data-library.png`，该目录已加入 `.gitignore`，截图只作为本地验证产物。
- 修复 `frontend/src/components/RoiCanvas.vue`：ROI 保存成功后，组件会根据 `rois.length` 增长清空未保存草稿，页面状态从“当前 ROI 尚未保存”正确切换为“已保存 ROI 可随证据包导出”。这是 Playwright 首轮验证发现的真实 UI 状态问题。
- 新增脚本：`npm --prefix frontend run test:e2e` 和根目录 `npm run frontend:e2e`。

验证结果：`npm --prefix frontend run test:e2e`、`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`conda run -n osteo-vision python tools/check_project_readiness.py`、`conda run -n osteo-vision python tools/run_platform_smoke.py` 和 `git diff --check` 均通过；`git diff --check` 仍只有 LF/CRLF warning。剩余前端验证缺口是失败态和摄像头状态。

## 11. 2026-07-04 MP4 与公开视频导入闭环修复记录

本轮继续推进前端闭环，把浏览器 E2E 从“双通道 + 复核 + 导出”扩展到赛题核心的 MP4 输入与公开视频代理数据入口。

- 扩展 `frontend/e2e/platform.browser.pw.ts`：新增第二个 Chromium 测试，运行时生成一个小型合成 MP4，经过浏览器文件选择上传到后端，再触发 `MP4关键帧` 后台分析，验证 `MP4 热点时间轴` 和关键帧 hotspot 结果真实出现在页面上。
- 同一测试继续验证 `/data` 视频库导入：新建独立病例，从公开视频候选卡点击“导入病例”，再到病例档案确认出现 1 条“短视频 / 摄像头”输入，回到病例工作台确认“官方 MP4 视频路径”自动同步。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：新增病例输入路径同步逻辑；当从病例档案加载病例或从视频库导入 MP4 后，工作台会从当前病例 inputs 自动填充白光、ICG 和 MP4 路径，避免公开视频导入后仍需要用户手动复制路径。
- 修复 `frontend/src/pages/CaseWorkspacePage.vue`：MP4 分析完成提示原先用字符串读取数字字段，导致页面显示“已抽取 0 帧、生成 0 个热点候选区”，但实际结果区已有关键帧和候选区；现在数字/字符串都会正确格式化，E2E 也会校验帧数和候选区数大于 0。
- 更新 `frontend/playwright.config.ts`：每次 E2E 使用独立 `.pytest_tmp/playwright/<run_id>/` 作为后端 SQLite、job store 和 artifact root，避免上一次失败留下 queued job 影响后续浏览器测试。

新增截图证据：

- `artifacts/e2e/browser_smoke/04-mp4-hotspot-workflow.png`
- `artifacts/e2e/browser_smoke/05-video-library-import.png`

验证结果：`npm --prefix frontend run test:e2e` 通过，当前为 3 个 Chromium E2E 测试；随后 `npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build`、`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`、`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`、`conda run -n osteo-vision python -m pytest -q`、`conda run -n osteo-vision python tools/check_project_readiness.py`、`conda run -n osteo-vision python tools/run_platform_smoke.py` 和 `git diff --check` 均通过。

## 12. 2026-07-04 当前决策版缺口清单

本节是面向当前问题的压缩版结论：真实项目病例、真实术中白光/ICG MP4/JPEG 和医生关键帧/ROI 标注继续列为外部数据依赖，不作为短期工程闭环的前置条件。下面只列还能由我们继续推进、修复或验证的缺口。

| 领域 | 目前还缺什么 | 优先级 | 代码/文件证据 |
|---|---|---:|---|
| 后端实时视频 | 浏览器摄像头现在只是注册 `camera://browser/default` 并返回“streaming AI inference is not connected”，没有真正流式采样、缓存、推理和推送。 | P1 | `backend/src/services/analysis_service.py`、`frontend/src/pages/CaseWorkspacePage.vue` |
| 后端病例存储 | SQLite + version 乐观锁已能防覆盖，但 ROI、analysis run、artifact、review event 仍作为整条病例 payload 保存，冲突后不能自动合并。 | P1 | `backend/src/domains/cases/repository.py` |
| 后端任务队列 | JSON job registry + 本地 worker 能演示后台任务，但不是常驻队列系统；缺优先级、租约、跨进程锁、自动重试和任务可观测面板。 | P1 | `backend/src/services/job_service.py`、`backend/src/services/job_worker.py` |
| 4K 输入链路 | 已有 JPEG/MP4 官方 profile 检查，但缺真实或代理 4K 长视频压力测试、旋转归一化、分片上传、码率/色彩空间策略。 | P1 | `backend/src/api/uploads.py`、`src/io/official_device_quality.py` |
| 关键帧策略 | `quality_peak` 能按荧光样信号和质量挑帧，并已生成独立 frame index manifest；前端已能提交秒级关键时间点。仍缺运动/重复帧去重、整段时间轴缓存和逐帧进度。 | P0 | `src/preprocess/video.py`、`backend/src/services/analysis_service.py` |
| 荧光融合 | 当前仍是 resize + 归一化 + alpha blend；ROI 量化已经接入，但缺配准、背景扣除、颜色标尺、时序峰值和更稳定的荧光归一化。 | P0 | `src/preprocess/fluorescence.py` |
| MP4 AI 输出 | hotspot 能出掩膜、overlay、候选框和时间轴，时间轴已支持条件筛选和当前帧详情；但仍是启发式阈值/连通区 baseline，不是训练模型；缺真实训练模型、逐帧重算和更完整详情页。 | P0 | `src/models/hotspot_segmenter.py`、`frontend/src/components/AnalysisWorkspaceCard.vue` |
| 候选区复核 | 候选区已能直接接受、拒绝、修改并写回 `CandidateRegion.status`，同时记录复核事件；仍缺候选 bbox 几何编辑和修改历史对比。 | P2 | `frontend/src/components/CandidateRegionList.vue`、`frontend/src/pages/ReviewWorkspacePage.vue`、`backend/src/services/review_service.py` |
| ROI 与模型联动 | 手动 ROI 已能进入融合量化和 hotspot 筛选，但还没有接入关键帧选择、MedSAM/其他 promptable model 或 ROI 编辑历史回放。 | P1 | `frontend/src/components/RoiCanvas.vue`、`src/preprocess/roi.py` |
| 前端时间轴体验 | 热点时间轴能点击切换四宫格当前帧，并能按阳性面积、ROI 命中、候选数量筛选；本轮已补当前帧详情。剩余是详情抽屉/页、失败态和更多真实图像比例复核。 | P2 | `frontend/src/components/AnalysisWorkspaceCard.vue`、`frontend/src/components/analysisPreview.ts` |
| 前端布局验证 | 桌面 Chromium、移动端工作台、移动端全屏和桌面全屏已通过截图验证，并检查横向溢出和空白图片；更多真实图像比例下的 overlay 坐标仍需复核。 | P2 | `frontend/e2e/platform.browser.pw.ts`、`frontend/src/components/AnalysisQuadGrid.vue` |
| 视频库管理 | 视频库已有筛选、预览、导入；缺搜索、分页、批量导入、批量打标签和训练集清单导出。 | P2 | `frontend/src/pages/DataLibraryPage.vue` |
| 导出标准 | 现在是 evidence bundle + JSON/Markdown/CSV + DICOM Secondary Capture；还不是 DICOM SR，也缺正式 bundle schema 文档和版本兼容说明。 | P1 | `backend/src/services/export_service.py`、`backend/src/reports/dicom_secondary_capture.py` |
| 文件访问安全 | `/files/preview` 和 `/files/download` 适合单机演示；远程协作前还缺 token、审计日志、一次性链接和权限模型。 | P2 | `backend/src/api/files.py` |
| 模型主线 | 当前可用模型仍是 D025/ConvNeXt3D CBCT 代理、2D hotspot baseline 和 fixture；nnU-Net、MedSAM-like、BiomedCLIP 尚不可用。 | P0 | `configs/inference/osteo_vision.yml`、`src/models/adapters.py` |
| ConvNeXt 代理模型 | `convnext3d_d025_proxy_segmenter` 可用，但 checkpoint 来自 D025 CBCT ROI 代理，不是术中 ICG MP4/JPEG 目标域模型；只能证明链路。 | P0 | `artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`、`src/models/adapters.py` |
| nnU-Net | adapter 未实现，checkpoint 目录缺失，CBCT 代理数据还没转成 nnU-Net 标准 dataset + train/infer 流程。 | P1 | `src/models/adapters.py`、`configs/inference/osteo_vision.yml` |
| MedSAM | MedSAM-like adapter 未实现，缺 checkpoint，缺 box/point/mask prompt 数据合同，ROI 画布还没有作为 prompt 输入。 | P1 | `src/models/adapters.py`、`frontend/src/components/RoiCanvas.vue` |
| BiomedCLIP | 缺 `open_clip` 和 checkpoint；它对分割主线帮助有限，更适合后置为图像级检索、说明或辅助筛查。 | P2 | `src/models/adapters.py`、`configs/inference/osteo_vision.yml` |
| 模型评估 | 缺正式交叉验证、患者级拆分审计、Dice/IoU/HD95 曲线、阈值曲线、失败样本图、校准和不确定性评估。 | P0 | `scripts/train_d025_lesion_smoke_model.py`、`research/reports/modeling/` |
| OFDVDnet 代理数据 | OFDVDnet baseline 已能做增强/伪彩/融合输出，但还没有接成训练 dataset loader、稳定性评估和输入输出成对训练流程。 | P0 | `src/datasets/ofdvdnet.py`、`scripts/run_ofdvdnet_fluorescence_baseline.py` |
| 外部代码快照 | EGNet、FRS Loss 快照缺关键文件，不能作为可运行资产，只能作为文献参考。 | P2 | `research/model-snapshots/code/egnet/`、`research/model-snapshots/code/frs_loss/` |
| 工程治理 | 当前工作区 diff 很大，本次复查 `git status --short` 为 69 个 modified、72 个 untracked、总计 141 条；后续需要分主题 review/提交。 | P0 | `git status --short` |
| 本地命令运行 | Windows 下并行执行多个 `conda run -n osteo-vision ...` 偶发使用同一个临时文件导致 file lock；质量门建议串行跑 conda 命令。 | P2 | 本轮 `check_env.py` 与 `model_inventory.py` 并行时曾触发 `__conda_tmp_*.txt` 占用，串行重跑通过。 |

本轮实际核验：`check_env.py`、`check_project_readiness.py`、`model_inventory.py`、ruff、mypy、pytest、前端 typecheck、Vitest、Vite build、Playwright E2E、`tools/run_platform_smoke.py` 均通过。最新 smoke 摘要为 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`；Playwright 为 3 个 Chromium E2E 测试通过；Vitest 为 8 个文件、18 个测试通过。

## 13. 2026-07-04 本轮缺口修复记录：时间轴筛选与候选区状态写回

本轮完成两个直接影响赛点二可评审闭环的修复。

1. MP4 热点时间轴条件筛选。
   - 更新 `frontend/src/components/analysisPreview.ts`：`HotspotTimelineItem` 增加 `roiScore` 和 `candidateCount` 数值字段，并新增 `filterHotspotTimelineItems()`，支持按阳性面积、ROI 命中和候选数量筛选。
   - 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：在 MP4 热点时间轴上方增加筛选按钮组，筛选后保留空状态提示。
   - 更新 `frontend/src/pages/CaseWorkspacePage.vue`：页面持有筛选状态，筛选结果变化后自动校正当前选中帧，避免四宫格仍显示被筛掉的帧。
   - 更新 `frontend/tests/AnalysisPreviewPanels.test.ts` 和 `frontend/e2e/platform.browser.pw.ts`：单元测试覆盖筛选逻辑，浏览器 E2E 覆盖“阳性面积/有候选”筛选后仍可点击帧并切换预览。

2. 候选区复核状态写回。
   - 更新 `backend/src/services/review_service.py`：新增 `update_candidate_region()`，将医生复核结果写回 `CandidateRegion.status`，同步记录 `candidate_region_state_update` 复核事件，并在 `review_summary` 中统计 accepted/modified/rejected candidates。
   - 更新 `backend/src/api/regions.py`：新增 `PATCH /cases/{case_id}/candidate-regions/{candidate_id}`。
   - 更新 `frontend/src/services/apiClient.ts`、`frontend/src/stores/caseStore.ts`、`frontend/src/components/CandidateRegionList.vue` 和 `frontend/src/pages/ReviewWorkspacePage.vue`：候选区列表新增接受、修改、拒绝按钮；旧的复核状态按钮也改为优先写回候选区状态。
   - 更新 `backend/tests/contract/test_case_inputs_api.py` 和 `frontend/e2e/platform.browser.pw.ts`：合同测试验证候选状态、review event、review summary 和候选转 ROI 后的状态延续；浏览器 E2E 验证候选区接受后页面显示“已接受”。

验证结果：

- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run`：通过，8 个测试文件、18 个测试。
- `npm --prefix frontend run build`：通过。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`：通过。
- `conda run -n osteo-vision python -m pytest -q`：通过。
- `npm --prefix frontend run test:e2e`：通过，3 个 Chromium E2E。
- `conda run -n osteo-vision python tools/check_project_readiness.py`：通过，仍提示 EGNet/FRS Loss 快照缺关键文件和 nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。
- `conda run -n osteo-vision python tools/run_platform_smoke.py`：通过，最新摘要为 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`。

剩余：时间轴筛选、候选状态写回、移动端截图、全屏分析截图、当前帧详情、frame index/detail manifest 和用户指定时间点抽帧已有基础闭环；候选 bbox 编辑、失败态截图、完整时间轴缓存、运动去重、逐帧重算和演示录像仍未完成。

## 14. 2026-07-04 本轮缺口修复记录：移动端与全屏截图验证

本轮继续完成一项前端可评审性缺口修复：移动端工作台和全屏分析视图不再只靠推测，已经进入 Playwright 浏览器级截图验证。

- 更新 `frontend/e2e/platform.browser.pw.ts`：新增 `mobile viewport and fullscreen analysis stay framed` 测试。
- 测试在 390×844 移动端视口下新建病例、写入双通道、运行双通道分析，验证页面无明显横向溢出和空白图片。
- 测试打开“全屏分析视图”，分别在移动端视口和 1440×900 桌面视口验证全屏四宫格可见、无明显横向溢出、无空白图片。
- 新增截图证据：
  - `artifacts/e2e/browser_smoke/06-mobile-case-workspace.png`
  - `artifacts/e2e/browser_smoke/07-mobile-analysis-fullscreen.png`
  - `artifacts/e2e/browser_smoke/08-desktop-analysis-fullscreen.png`

验证结果：`npm --prefix frontend run test:e2e` 通过，当前为 3 个 Chromium E2E 测试。剩余前端可评审缺口是 API 失败态截图、摄像头状态截图、更多真实 4K 图像比例下的 overlay 坐标复核，以及一段稳定演示录像。

## 15. 2026-07-04 本轮缺口修复记录：MP4 frame index 与当前帧详情

本轮继续补赛题官方 MP4 输入链路的证据颗粒度，目标是让“关键帧 -> hotspot -> 候选区 -> 医生复核”不只停留在缩略图时间轴，而是有后端 manifest 和前端当前帧详情可追溯。

- 更新 `src/preprocess/video.py`：`extract_keyframes()` 除 `keyframe_manifest.json` 外，同步写入 `frame_index_manifest.json`，记录源视频 metadata、采样策略、selected keyframes、预览/证据路径、质量评分和选择分数。
- 更新 `backend/src/services/analysis_service.py`：MP4 分析结果新增 `fused_outputs.frame_index_manifest_path`、`fused_outputs.frame_details` 和 `fused_outputs.frame_details_manifest_path`；每帧详情合并 keyframe、hotspot 输出、量化指标、Top BBox、证据帧、overlay、mask 和医学边界说明。
- 更新证据导出链路：frame index manifest 与 frame details manifest 作为 `report_json` artifact 写入病例 artifacts，后续 evidence bundle 可包含这些逐帧证据。
- 更新 `frontend/src/components/analysisPreview.ts`：新增 `HotspotFrameDetail`、`hotspotFrameDetailsFromRun()` 和 `selectedHotspotFrameDetailFromRun()`，优先读取后端 `frame_details`，旧结果可从 `hotspot_outputs` 回退派生。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue` 与 `frontend/src/components/AnalysisWorkspaceCard.vue`：MP4 热点时间轴下方新增“当前帧详情”面板，展示候选数量、阳性面积、ROI 命中、Top BBox、证据帧/叠加图/掩膜链接和非诊断边界。
- 更新 `backend/tests/contract/test_case_inputs_api.py`、`backend/tests/unit/test_job_worker.py`、`tests/unit/test_video_preprocess.py`、`frontend/tests/AnalysisPreviewPanels.test.ts` 和 `frontend/e2e/platform.browser.pw.ts`：覆盖 manifest 生成、上传预抽帧复用、分析 frame details、前端详情派生和浏览器 MP4 流程中当前帧详情可见。

定向验证结果：

- `conda run -n osteo-vision python -m pytest tests/unit/test_video_preprocess.py backend/tests/contract/test_case_inputs_api.py::test_video_analysis_reuses_uploaded_keyframes backend/tests/contract/test_case_inputs_api.py::test_video_input_analysis_extracts_keyframes backend/tests/unit/test_job_worker.py::test_local_job_worker_processes_queued_upload_keyframes -q`：通过。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run AnalysisPreviewPanels.test.ts`：通过。

剩余：当前 frame index scope 仍是 selected keyframes，不是整段视频每一帧的全量索引；下一步应补整段时间轴缓存、运动/重复帧去重、逐帧重算和失败态截图。

## 16. 2026-07-04 本轮缺口修复记录：MP4 用户指定时间点抽帧

本轮继续补 MP4 关键帧策略中的“用户指定时间点”缺口。该能力只表示评审或操作者可以指定视频秒数，让系统抽取对应帧进入 hotspot 分析；它不等同于医生真实关键帧标注，也不替代医生复核。

- 更新 `src/preprocess/video.py`：`extract_keyframes()` 新增 `requested_timestamps_sec` 与 `requested_frame_indexes` 参数；当存在有效指定值时，采样策略切换为 `manual`，按 fps 将秒数转换为帧号，并对越界帧做裁剪、重复帧去重。
- 更新 `backend/src/services/analysis_service.py`：MP4 分析参数支持 `keyframe_timestamps_sec` / `requested_timestamps_sec` 和 `keyframe_frame_indexes` / `requested_frame_indexes`；手动指定时不复用上传预抽帧，而是重新按请求帧生成 keyframe manifest、frame index manifest 和 frame details。
- 更新 `frontend/src/components/CaseWorkspaceControls.vue` 与 `frontend/src/pages/CaseWorkspacePage.vue`：工作台新增“关键时间点（秒）”输入框，支持逗号、空格、中文逗号和分号分隔；有效输入会作为 `keyframe_timestamps_sec` 提交，完全无效时前端提示格式错误。
- 更新 `tests/unit/test_video_preprocess.py`：覆盖秒级时间点转换、越界裁剪、重复帧去重和手动帧号选择。
- 更新 `backend/tests/contract/test_case_inputs_api.py`：覆盖 API 参数进入 MP4 分析后，输出 keyframes、frame details 和 frame index manifest 均使用指定帧。
- 更新 `frontend/e2e/platform.browser.pw.ts`：浏览器 MP4 流程在运行分析前填写关键时间点，并继续验证当前帧详情可见。

定向验证结果：

- `conda run -n osteo-vision python -m pytest tests/unit/test_video_preprocess.py backend/tests/contract/test_case_inputs_api.py::test_video_analysis_uses_requested_timestamps -q`：通过。
- `npm --prefix frontend run typecheck`：通过。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`：通过。

剩余：仍需补整段视频时间轴缓存、运动/重复帧去重、逐帧重算、失败态截图和稳定演示录像。

## 17. 2026-07-04 排除外部数据前置项后的前后端与模型缺口复查

本节按当前约束重新划分：真实项目病例、真实术中白光/ICG MP4/JPEG、医生关键帧/ROI 标注暂时作为外部数据依赖，不再作为短期工程闭环前置条件。下面只列我们仍可继续推进、修复、验证或写入评估材料的缺口。

### 17.1 P0：近期必须优先补的缺口

| 编号 | 缺口 | 影响 | 证据位置 | 建议动作 |
|---|---|---|---|---|
| P0-01 | 赛点二仍缺真实可解释的主线模型。当前能跑的是 `convnext3d_d025_proxy_segmenter`、`d025_lesion_smoke_segmenter`、`fluorescence_hotspot_2d_segmenter` 和 `fixture_default`，其中前两者是 D025 CBCT ROI 代理，hotspot 是启发式阈值/连通区。 | 可以演示链路，但不能说已经完成颌骨骨髓炎术中 AI 分割/诊断模型。 | `configs/inference/osteo_vision.yml`、`src/models/adapters.py`、`scripts/model_inventory.py` | 固定一个近期主线：优先把 ConvNeXt/MedNeXt 风格 3D 小模型在 D025/ToothFairy2/自有 CBCT 代理数据上做正式训练和失败样本报告；nnU-Net 可作为第二基线，不要同时摊太多候选。 |
| P0-02 | 荧光融合仍是 resize + 归一化 + alpha blend。缺配准、背景扣除、颜色标尺、时序峰值和 4K 性能策略。 | 赛点一能演示，但专业度和医学解释力不够；4K 视频下可能出现错位或不稳定。 | `src/preprocess/fluorescence.py` | 做 V2 融合：双通道配准开关、背景扣除、颜色条/阈值图例、ROI 时间曲线和 4K 下采样策略。 |
| P0-03 | MP4 分析仍只处理 selected keyframes，不是整段视频时间轴。 | 评审会看到关键帧热点，但看不到全视频连续证据，也不能回到任意时间点复算。 | `src/preprocess/video.py` 中 `frame_index_scope: selected_keyframes` | 补全视频 frame cache 或低频时间轴索引；至少记录全视频 frame_count/fps/duration、抽样点和未处理范围。 |
| P0-04 | 运动/重复帧去重没有真正实现。当前只做手动请求重复帧号去重和质量峰值的最小间隔。 | 长视频中可能抽到多个几乎相同的帧，浪费候选位并降低演示说服力。 | `src/preprocess/video.py` | 在 `quality_peak` 中加入灰度 thumbnail hash 或 SSIM 近似去重，manifest 记录 duplicate/skipped 信息。 |
| P0-05 | 前端/后端缺逐帧重算能力。 | 用户点击时间轴后只能查看已分析帧，不能选择新时间点后让后端单帧重算。 | `frontend/src/components/AnalysisWorkspaceCard.vue`、`backend/src/services/analysis_service.py` | 增加“按当前时间点重算”API 和前端按钮，复用 `requested_timestamps_sec`。 |
| P0-06 | 模型评估报告缺正式交叉验证、患者级拆分、Dice/IoU/HD95 曲线、阈值曲线和失败样本图。 | 目前学校评估只能看到工程跑通，模型可信度不足。 | `research/reports/modeling/`、`scripts/train_d025_lesion_smoke_model.py` | 先对 D025/CBCT 代理主线出一个小规模但完整的训练评估报告，明确非目标域。 |
| P0-07 | 工作区改动过大，当前 `git diff --stat` 显示 69 个 modified 文件、72 个 untracked 文件，混合后端、前端、模型、报告、下载 manifest。 | 后续继续开发会难以 review，也容易把临时产物或大文件混进提交。 | `git status --short`、`git diff --stat` | 先按“平台后端/前端 MP4/模型清单与训练/研究报告与 manifest”分批 review 和提交。 |

### 17.2 后端代码缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| B-01 | 实时视频仍是接口预留。 | `realtime_video` 只登记 `camera://browser/default`，后端明确返回 streaming AI inference 未接入。 | UI 文案改为“实时预览接口预留”，或实现浏览器帧采样上传/缓存/分析。 |
| B-02 | 本地任务队列不是正式队列系统。 | JSON job registry + `LocalJobWorker` 能跑后台任务，但没有常驻 worker、优先级、租约、跨进程锁、自动重试和观测面板。 | 短期继续用 worker drain；中期换 SQLite queue/RQ/Celery。 |
| B-03 | 病例仓库仍是整条 payload 保存。 | SQLite + version 乐观锁已防覆盖，但 ROI、analysis run、artifact、review event 未表级追加。 | 拆分 ROI/analysis/artifact/review event 表，或补 409 后的前端重载重试流程。 |
| B-04 | 4K MP4/JPEG 缺真实压力测试。 | 已有官方 profile、content probe、ffprobe 字段；未验证真实 4K 长视频、旋转、码率、超大文件。 | 用代理 4K MP4 做上传/预抽帧/分析/导出压力脚本，记录耗时和内存。 |
| B-05 | 文件预览/下载缺权限模型。 | `_resolve_artifact_path()` 限制 artifact root 和后缀，但没有 token、审计日志、一次性链接。 | 单机演示可保留；远程协作前补短期 token 和下载审计。 |
| B-06 | DICOM 仍是 Secondary Capture。 | 可导出 `.dcm`，但不是 DICOM SR，没有结构化编码、接收端兼容和脱敏策略。 | 先固定 evidence bundle schema v1；DICOM SR 作为后续增强。 |
| B-07 | 进度上报还不是真实逐帧。 | job 有 progress 字段，但长视频分析阶段没有按帧持续更新。 | 在 keyframe/hotspot 循环中写进度，前端轮询展示。 |

### 17.3 前端代码缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| F-01 | 左侧本地路径输入仍偏单机。 | 工作台仍支持 `D:\...` 手动路径；远程打开前端时路径对后端不可用。 | 默认引导上传/视频库选择，本地路径标为“开发调试”。 |
| F-02 | API 失败态缺浏览器截图证据。 | Playwright 已覆盖成功路径、移动端和全屏；失败态没有截图和断言。 | 增加上传格式错误、后端 409/429、分析失败、导出失败的 E2E 截图。 |
| F-03 | 摄像头状态缺完整交互。 | 有浏览器摄像头入口和状态文案，但后端实时分析未接。 | 增加“仅预览/未接推理”状态截图，避免比赛演示误解。 |
| F-04 | 候选 bbox 不能几何编辑。 | 候选可接受/拒绝/修改状态，也可转 ROI；bbox 本身不可拖拽改边界。 | 将候选 bbox 叠加到 ROI canvas，支持拖拽后写回 `bbox_normalized` 和 review event。 |
| F-05 | MP4 时间轴详情仍是轻量面板。 | 已有筛选、点击切换、当前帧详情；缺详情抽屉、跳转复算、失败帧解释。 | 增加帧详情抽屉，显示完整 manifest 字段和重算入口。 |
| F-06 | 视频库缺批量能力。 | 有筛选、详情、预览、导入；缺搜索、分页、批量导入、批量打标签、训练清单导出。 | 先补搜索和导出 manifest，批量导入后置。 |
| F-07 | 演示录像缺失。 | 已有截图，但没有一段稳定可交付操作录像。 | 固定一套 smoke 数据，录制“上传 MP4 -> hotspot -> 复核 -> 导出”的演示流程。 |

### 17.4 模型与数据缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| M-01 | nnU-Net 不可用。 | adapter inference not implemented；checkpoint 目录缺失。 | 做 D025/ToothFairy2 到 nnU-Net 格式转换，先跑 2D/3D 最小训练和推理。 |
| M-02 | MedSAM-like 不可用。 | adapter 是空实现；缺 checkpoint；缺 point/box/mask prompt 合同。 | 若要用 MedSAM，先做 2D frame box prompt 最小闭环，把 ROI 画布输出接到 adapter。 |
| M-03 | BiomedCLIP 不适合近期主线。 | 缺 `open_clip` 和 checkpoint；更偏图像级筛查/检索。 | 暂不作为分割主线，等主线稳定后再用于辅助说明或检索。 |
| M-04 | ConvNeXt3D 只是代理模型。 | 可用 checkpoint 来自 D025 CBCT ROI 代理，不是术中 ICG MP4/JPEG。 | 可作为近期工程主线，但报告必须写“代理模型/非目标域”。 |
| M-05 | OFDVDnet 仍未变成训练集。 | 已能跑荧光增强 baseline；还没有成对训练 loader、稳定性指标和视频增强训练流程。 | 先把 OFDVDnet 作为赛点一增强/伪彩稳定性数据，不强行用于骨髓炎诊断。 |
| M-06 | 外部代码快照不完整。 | readiness 显示 EGNet 和 FRS Loss 缺关键文件。 | 降级为文献参考；除非补完整源码和 license，否则不列为可运行资产。 |
| M-07 | 数据域边界仍强。 | 公开视频、OFDVDnet、CBCT 代理数据都不是真实术中 ICG 颌骨骨髓炎目标域。 | 所有报告继续标注目标域/非目标域/仅演示/可训练属性。 |
| M-08 | 不确定性和失败样本体系缺失。 | 当前有 warnings，但没有模型级不确定性、校准、失败类型归因。 | 先做阈值敏感性、连通域后处理对比、失败样本图册。 |

### 17.5 本轮重新核验结果

| 命令 | 结果 |
|---|---|
| `conda run -n osteo-vision python check_env.py` | 通过；Python 3.11.15；无 failure/warning。 |
| `conda run -n osteo-vision python tools/check_project_readiness.py` | 通过；仍提示 EGNet/FRS Loss 快照缺关键文件，nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。 |
| `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml` | 通过；7 个模型中 4 个可用、3 个不可用。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；101 个测试。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；8 个文件、18 个测试。 |
| `npm --prefix frontend run build` | 通过。 |
| `npm --prefix frontend run test:e2e` | 通过；3 个 Chromium E2E。 |
| `conda run -n osteo-vision python tools/run_platform_smoke.py` | 通过；最新摘要 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`。 |

结论：当前项目不是“跑不起来”，而是“能演示的工程闭环已经形成，模型真实性、视频连续证据、融合算法深度、远程/失败态可评审性和提交治理仍不足”。短期最值得做的是：运动/重复帧去重、整段视频时间轴缓存、荧光融合 V2、候选 bbox 几何编辑、ConvNeXt/nnU-Net 代理模型正式训练评估，以及把当前大工作区按主题拆分提交。

## 18. 2026-07-04 本轮缺口修复记录：MP4 运动/重复帧去重与时间轴 Manifest

本轮先处理 MP4 输入链路里最影响赛题展示可信度的两个工程缺口：重复帧去重和整段视频时间轴证据。该能力仍属于工程关键帧选择与低频时间轴索引，不等同医生关键帧，也不是目标域训练模型。

已完成：

- 更新 `src/preprocess/video.py`：`quality_peak` 关键帧候选增加 16×16 灰度 thumbnail 签名，以 mean absolute similarity 做视觉相似度判断；默认启用重复候选去重，manifest 记录 `duplicate_candidate_count`、`skipped_duplicate_count`、`backfilled_duplicate_count`、`duplicate_of_frame_index` 和 `duplicate_similarity`。
- 更新 `src/preprocess/video.py`：新增 `timeline_manifest.json`，schema 为 `osteo-vision-video-timeline-manifest-v1`；覆盖整段视频时长，记录抽样 stride、全视频 frame_count/fps/duration、candidate frame、selected keyframe、重复帧标记、质量分数和证据路径。
- 更新 `frame_index_manifest.json`：`frame_index_scope` 从单纯 `selected_keyframes` 升级为 `selected_keyframes_with_candidate_trace`，同时写入 candidate trace、deduplication 摘要和 `timeline_manifest_path`。
- 更新 `backend/src/services/analysis_service.py`：MP4 分析结果 `fused_outputs` 新增 `timeline_manifest_path`；上传预抽帧复用时同步保留 upload 阶段的 `timeline_manifest.json`；证据 artifact 中新增 timeline manifest，后续 evidence bundle 可打包。
- 更新测试：
  - `tests/unit/test_video_preprocess.py` 覆盖重复候选帧标记、timeline manifest、candidate trace 和 keyframe manifest 路径。
  - `backend/tests/contract/test_case_inputs_api.py` 覆盖上传预抽帧复用时 timeline manifest 继续传入分析结果。
  - `backend/tests/unit/test_job_worker.py` 覆盖本地 worker 关键帧任务生成 timeline manifest。

验证结果：

- `conda run -n osteo-vision python -m pytest tests\unit\test_video_preprocess.py -q`：通过，5 个测试。
- `conda run -n osteo-vision python -m pytest backend\tests\contract\test_case_inputs_api.py::test_video_analysis_reuses_uploaded_keyframes backend\tests\contract\test_case_inputs_api.py::test_video_input_analysis_extracts_keyframes backend\tests\contract\test_case_inputs_api.py::test_video_analysis_uses_requested_timestamps backend\tests\unit\test_job_worker.py::test_local_job_worker_processes_queued_upload_keyframes -q`：通过，4 个测试。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`：通过。
- `conda run -n osteo-vision python -m pytest -q`：通过。
- `npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build`、`npm --prefix frontend run test:e2e`：均通过。
- `conda run -n osteo-vision python tools\run_platform_smoke.py`：通过，最新摘要为 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`，`artifact_count=20`，导出 summary `total_artifact_count=26`，证据包已包含 `timeline_manifest.json`。

剩余：

- 当前 timeline manifest 是“整段视频时长覆盖 + 候选帧/选中帧详尽记录”的低频索引，不对长视频每一帧都做质量推理；真实 4K 长视频压力测试后再决定是否扩大逐帧索引。
- 后续还需将 timeline manifest 从摘要面板扩展为可筛选详情抽屉，并继续验证更长 4K 视频上的交互性能。
- 重复帧去重仍是轻量 thumbnail 相似度方法，后续可以替换为 SSIM/光流/场景切换检测，但当前足够支撑比赛版平台的关键帧去重。

## 19. 2026-07-04 本轮缺口修复记录：MP4 当前帧单帧重算

本轮继续补 MP4 时间轴交互闭环。上一轮已经能生成 timeline manifest 和当前帧详情，本轮把“查看当前帧”推进为“选中当前帧后可触发后端单帧重算”。

已完成：

- 更新 `frontend/src/components/analysisPreview.ts`：`HotspotFrameDetail` 增加 `frameIndex` 和 `timestampSec` 数值字段，供页面层提交手动重算参数。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：当前帧详情面板新增“重算当前帧”按钮，避免操作者回到左侧手动输入秒数。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：新增 `reanalyzeSelectedHotspotFrame()`，优先用当前帧 `timestampSec` 提交 `keyframe_timestamps_sec`，否则用 `frameIndex` 提交 `keyframe_frame_indexes`；后台任务参数固定 `keyframe_count=1`，复用现有 `mode=video_file`、ROI hints、阈值、伪彩和 alpha 设置。
- 更新 `frontend/tests/AnalysisPreviewPanels.test.ts`：覆盖帧号和时间戳字段派生。
- 更新 `frontend/e2e/platform.browser.pw.ts`：浏览器 MP4 闭环现在覆盖“上传 MP4 -> 手动关键时间点分析 -> 时间轴筛选/点击 -> 重算当前帧 -> 返回 1 帧 hotspot 结果”。

定向验证结果：

- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run AnalysisPreviewPanels.test.ts`：通过。
- `npm --prefix frontend run test:e2e`：通过，3 个 Chromium E2E，其中 MP4 流程已覆盖当前帧重算。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`：通过。
- `conda run -n osteo-vision python -m pytest -q`：通过。
- `npm --prefix frontend test -- --run` 和 `npm --prefix frontend run build`：通过。
- `conda run -n osteo-vision python tools\check_project_readiness.py`：通过；仍提示 EGNet/FRS Loss 快照缺关键文件和 nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。
- `conda run -n osteo-vision python tools\run_platform_smoke.py`：通过；最新摘要为 `artifacts/platform_smoke/20260703T233318Z/platform_smoke_summary.json`。

剩余：

- 当前帧重算已经可用，但前端还没有展示 `timeline_manifest.json` 的完整抽样覆盖、重复帧组和候选 trace。
- 仍需做真实或代理 4K 长视频压力测试，验证单帧重算在大文件上的响应时间。
- 仍未接入训练模型；重算结果继续来自 2D hotspot 启发式 baseline，必须保留医生复核边界。

## 20. 2026-07-04 本轮缺口修复记录：时间轴 Manifest 前端证据面板

本轮继续补 MP4 证据可解释性。上一轮 `timeline_manifest.json` 已能进入 evidence bundle，但评审需要在前端直接看到“为什么选这些帧、有没有重复帧、候选帧 trace 是什么”，因此本轮把 manifest 摘要接入工作台。

已完成：

- 更新 `backend/src/services/analysis_service.py`：MP4 分析结果 `fused_outputs.timeline_summary` 新增 `frame_count`、`fps`、`duration_sec`、`timeline_stride`、`selected_frame_count`、`candidate_frame_count`、`duplicate_candidate_count`、`skipped_duplicate_count`、`candidate_trace`、`selected_trace` 和 `duplicate_trace`。
- 更新 `frontend/src/components/analysisPreview.ts`：新增 `TimelineManifestSummary`、`TimelineTraceItem` 和 `timelineManifestSummaryFromRun()`，把后端 timeline summary 转成前端展示标签。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：MP4 热点时间轴区域新增“时间轴 Manifest”证据面板，展示全时长低频索引、采样策略、帧数、时长、FPS、索引步长、选中关键帧、候选帧、重复候选、跳过重复、候选 Trace、重复帧组和 JSON 下载入口。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：把 `timelineManifestSummaryFromRun()` 接入分析卡片。
- 更新 `frontend/tests/AnalysisPreviewPanels.test.ts`：覆盖 timeline summary 标签、候选 trace 和重复帧组标签。
- 更新 `frontend/e2e/platform.browser.pw.ts`：浏览器 MP4 流程现在断言“时间轴 Manifest”和“候选 Trace”真实可见。
- 更新 `backend/tests/contract/test_case_inputs_api.py`：覆盖后端分析结果中的 timeline summary。

验证结果：

- `conda run -n osteo-vision python -m pytest backend\tests\contract\test_case_inputs_api.py::test_video_analysis_reuses_uploaded_keyframes backend\tests\contract\test_case_inputs_api.py::test_video_input_analysis_extracts_keyframes -q`：通过。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run AnalysisPreviewPanels.test.ts`：通过，6 个测试。
- `npm --prefix frontend run test:e2e`：通过，3 个 Chromium E2E。

剩余：

- 时间轴 Manifest 已经可见，但仍未做真实 4K 长视频压力测试；需要记录大文件上传、预抽帧、单帧重算和导出的耗时/内存。
- 当前前端展示的是 summary 和前若干 trace，完整 JSON 通过下载入口查看；如后续评审需要，可以增加独立详情抽屉。
- 赛点二模型仍是启发式 hotspot baseline + CBCT 代理模型，还需推进正式模型训练评估。

## 21. 2026-07-04 当前项目缺口再复查：代码、模型与可评审闭环

本节是最新状态汇总。真实项目病例、真实术中白光/ICG MP4/JPEG、医生关键帧/ROI 标注暂时作为外部依赖，不再重复列为当前可开发前置项。下面只列项目内部仍能推进的缺口。

### 21.1 当前最大内部缺口

| 排名 | 缺口 | 当前证据 | 影响 | 建议动作 |
|---:|---|---|---|---|
| 1 | 赛点二缺一个可正式汇报的主线模型。 | `scripts/model_inventory.py` 显示 7 个模型中 4 个可用，nnU-Net、MedSAM-like、BiomedCLIP 不可用；可用项仍是 D025/ConvNeXt3D 代理、D025 smoke、2D hotspot 启发式和 fixture。 | 工程能演示，但 AI 辅助诊断/分割的科研可信度仍不够。 | 固定 ConvNeXt3D/MedNeXt 或 nnU-Net 其中一条，做代理数据正式训练、患者级拆分、Dice/IoU/HD95、阈值曲线和失败样本图。 |
| 2 | 荧光融合仍是初版算法。 | `src/preprocess/fluorescence.py` 标记 `registration: resize_only_initial_demo`，方法是归一化、伪彩、alpha blend。 | 赛点一能展示，但专业度不足，4K/双通道错位时解释力弱。 | 做融合 V2：配准开关、背景扣除、颜色标尺、ROI 时间曲线和 4K 下采样策略。 |
| 3 | 4K 长视频压力证据仍不完整。 | 上传 profile、ffprobe、timeline manifest 都已接入；已新增 `tools/run_official_4k_pressure_smoke.py`，能生成 3840x2160 JPEG/MP4 并完成上传、抽帧、分析、导出；但还不是长时真实视频。 | 赛题官方输入是 3840x2160 MP4/JPEG，评审可能追问大文件和真实编码稳定性。 | 继续扩展到更长代理 MP4、真实样例、旋转/码率异常和分片上传失败分级。 |
| 4 | 前端可评审失败态不足。 | E2E 已覆盖成功路径、移动端、全屏、MP4、公开视频导入；缺 409/429、上传错误、分析失败、导出失败截图。 | 学校或比赛方看不到系统面对异常输入时是否稳。 | 增加失败态 E2E 和截图集，作为报告/答辩证据。 |
| 5 | 工作区改动过大。 | `git diff --stat` 当前约 69 个 modified 文件、72 个 untracked 文件，混合前后端、模型、报告、manifest、脚本。 | 后续 review、提交、回滚和答辩版本冻结风险高。 | 按主题拆分：平台后端、前端 MP4、模型与训练、研究资料与报告。 |

### 21.2 后端代码缺口

| 编号 | 缺口 | 当前状态 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| B-01 | `realtime_video` 还不是实时 AI。 | 后端只登记摄像头输入并返回 `realtime_stream_not_connected`，没有帧采样、缓存、推理和流式输出。 | P1 | UI 改成“实时预览/接口预留”，或实现低帧率抽样 + hotspot baseline。 |
| B-02 | 本地任务队列仍是 JSON registry。 | `JobRegistry` 可持久化、取消、进度、限流；`LocalJobWorker` 可 drain queued job，但没有常驻服务、租约、优先级和跨进程队列锁。 | P1 | 短期保留；长视频阶段改 SQLite queue/RQ/Celery，并补任务观测页。 |
| B-03 | 病例仓库仍是整条 payload 保存。 | SQLite + version 乐观锁已防覆盖，但 ROI、analysis run、artifact、review event 没有表级追加。 | P1 | 拆分子表，或至少补前端 409 后重载、重放和合并提示。 |
| B-04 | 4K profile 只检查，不处理。 | 能记录分辨率、容器、codec、rotation、bitrate；旋转、色彩空间、码率异常只是 warning。 | P1 | 增加旋转归一化、码率/时长分级、超大文件分片或明确限制。 |
| B-05 | 文件预览/下载缺权限模型。 | `/files/preview` 和 `/files/download` 限制 artifact root 与后缀，但没有 token、审计、一次性链接。 | P2 | 单机 Demo 可接受；远程协作前补短期 token 和下载日志。 |
| B-06 | 导出仍是 Secondary Capture，不是 DICOM SR。 | evidence bundle、JSON、CSV、Markdown、DICOM Secondary Capture 可用；结构化 DICOM SR 与接收端兼容未做。 | P1 | 先固定 bundle schema v1；DICOM SR 放到下一阶段。 |
| B-07 | 长视频进度不够细。 | job 有 progress 字段，但分析内部不是逐关键帧/逐阶段连续写进度。 | P2 | 在抽帧、hotspot、导出循环里持续更新进度和当前帧信息。 |

### 21.3 前端代码缺口

| 编号 | 缺口 | 当前状态 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| F-01 | 本地路径输入仍偏单机。 | 工作台仍展示 `D:\data\...` 路径输入；远程前端访问时这些路径对后端无意义。 | P1 | 默认引导上传/视频库选择，把本地路径标为开发调试模式。 |
| F-02 | 候选 bbox 基础几何编辑已补；剩余是更细的编辑体验。 | 候选可接受/修改/拒绝，可转 AI ROI，可在预览叠加；已能选择候选后在 ROI canvas 拖拽重画 bbox 并写回 `bbox_normalized`、`bbox_xyxy` 和复核事件。 | P2 | 后续补边角 handle、修改前后对比和编辑历史详情。 |
| F-03 | timeline manifest 还不是详情工作台。 | 已有 summary、候选 trace、重复帧组和 JSON 下载；缺完整可筛选抽屉、失败帧解释和跳转复算。 | P2 | 增加详情抽屉：按 frame、score、duplicate、selected 筛选，并支持重算入口。 |
| F-04 | 视频库缺批量能力。 | 已有筛选、详情、预览、导入；缺搜索、分页、批量导入、批量打标签、训练 manifest 导出。 | P2 | 先补搜索和 manifest 导出；批量导入后置。 |
| F-05 | API 失败态截图缺失。 | Playwright 成功路径通过；失败路径没有可交付截图。 | P1 | 增加上传格式错误、429 限流、409 冲突、分析失败、导出失败测试与截图。 |
| F-06 | 摄像头能力容易被误解。 | 前端有摄像头入口，但后端实时分析未接。 | P2 | 截图和文案明确“仅预览/接口预留”，避免被评审理解成实时 AI 已完成。 |
| F-07 | 缺稳定演示录像。 | 当前有浏览器截图和 smoke 产物，没有固定操作录像。 | P2 | 录制“上传 MP4 -> hotspot -> timeline -> ROI/候选复核 -> 导出”流程。 |

### 21.4 模型与训练缺口

| 编号 | 缺口 | 当前状态 | 优先级 | 建议动作 |
|---|---|---|---:|---|
| M-01 | nnU-Net 不可用。 | adapter inference not implemented；checkpoint 目录缺失。 | P0 | 做 D025/ToothFairy2/CBCT 代理数据到 nnU-Net 格式转换，先跑最小 2D/3D 训练和推理。 |
| M-02 | MedSAM-like 不可用。 | adapter 是空实现；缺 checkpoint；缺 point/box/mask prompt 合同。 | P0 | 若采用 MedSAM，先做 2D frame box prompt 最小闭环，把 ROI/bbox 输出接 adapter。 |
| M-03 | BiomedCLIP 不适合作为近期分割主线。 | 缺 `open_clip` 和 checkpoint；定位更像图像级筛查/检索。 | P2 | 暂不作为主线；后续可用于辅助检索或图像级风险提示。 |
| M-04 | ConvNeXt3D 仍是代理模型。 | checkpoint 可用，但来自 D025 CBCT ROI 代理，不是术中 ICG MP4/JPEG。 | P0 | 可作为近期主线继续训练，但所有报告必须标注“非目标域代理模型”。 |
| M-05 | 2D hotspot 是启发式，不是训练模型。 | MP4/JPEG hotspot 来自强度阈值、连通域和 ROI 规则。 | P0 | 保留为可解释 baseline；另起训练模型路线，不把它写成 AI 诊断性能。 |
| M-06 | OFDVDnet 仍是增强/质控数据，不是骨髓炎训练集。 | 可跑荧光 baseline，但没有骨髓炎标签、成对训练 loader 和稳定性指标。 | P1 | 用于赛点一伪彩/增强稳定性，不用于赛点二诊断主张。 |
| M-07 | 外部代码快照不完整。 | readiness 显示 EGNet 缺 `CRA.py/Fusion.py/Transformer.py/bgnet.py/lib/tester.py`；FRS Loss 缺 `models.py/loss_function.py/FRS.py`。 | P2 | 降级为文献参考；除非补完整源码和 license，否则不列为可运行资产。 |
| M-08 | 模型不确定性体系缺失。 | 当前只有 warnings 和阈值，缺校准、置信区间、失败类型归因。 | P1 | 做阈值敏感性、连通域后处理对比、失败样本图册和不确定性提示。 |

### 21.5 最新验证状态

| 命令 | 结果 |
|---|---|
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；仍有 FastAPI TestClient 与 torch JIT deprecation warning。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；8 个文件、19 个测试。 |
| `npm --prefix frontend run build` | 通过。 |
| `npm --prefix frontend run test:e2e` | 通过；3 个 Chromium E2E。 |
| `conda run -n osteo-vision python tools/check_project_readiness.py` | 通过；仍提示 EGNet/FRS Loss 快照缺文件，nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。 |
| `conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision.yml` | 通过；7 个模型中 4 个可用、3 个不可用。 |
| `conda run -n osteo-vision python tools/run_platform_smoke.py` | 通过；最新摘要 `artifacts/platform_smoke/20260704T000429Z/platform_smoke_summary.json`，证据包包含 `timeline_manifest.json`。 |
| `git diff --check` | 无 whitespace error；仅有 LF 将被 Git 转 CRLF 的提示。 |

当前结论：排除真实病例和医生关键帧这两个外部不可控项后，项目最需要补的不是基础闭环，而是主线模型可信度、荧光融合算法深度、4K 长视频压力证据、异常态可评审证据和版本治理。

## 22. 2026-07-04 本轮缺口修复记录：候选 bbox 几何编辑

本轮补齐前端复核闭环中的一个明确缺口：AI 候选区域过去只能接受/修改状态/拒绝，或一键转 ROI，但候选 bbox 本身不能被医生修边。现在已支持把候选 bbox 载入 ROI 画布，医生拖拽重画后直接写回候选 metadata，并保留复核事件。

已完成：

- 更新 `backend/src/services/review_service.py`：`PATCH /cases/{case_id}/candidate-regions/{candidate_id}` 现在接收 `geometry`；当 geometry 是归一化矩形时，会写回 `metadata.bbox_normalized`、`metadata.review_geometry`、`metadata.geometry_review_source=physician_review`，并按 `image_width/image_height` 重新计算 `metadata.bbox_xyxy`。
- 更新 `frontend/src/services/apiClient.ts` 与 `frontend/src/stores/caseStore.ts`：候选区更新接口支持 `geometry`、`label` 和 `reviewer_notes`，不再只改复核状态。
- 更新 `frontend/src/components/CandidateRegionList.vue`：带 bbox 的候选新增“编辑框”入口，并高亮当前正在编辑的候选。
- 更新 `frontend/src/components/RoiCanvas.vue`：支持从外部候选 geometry 初始化草稿，保存按钮可切换为“保存候选框”，保存时保留候选 ID。
- 更新 `frontend/src/pages/ReviewWorkspacePage.vue`：候选“编辑框”会进入“候选框几何编辑”模式，保存后调用候选区更新接口，默认写为 `modified` 状态。
- 更新 `frontend/e2e/platform.browser.pw.ts`：MP4 浏览器闭环新增“进入医生复核 -> 编辑候选框 -> 保存候选框 -> 候选状态变为已修改”的浏览器级断言。
- 更新 `backend/tests/contract/test_case_inputs_api.py`：覆盖候选 bbox geometry 更新、像素 bbox 重算、review label 写入，以及候选转 ROI 时使用编辑后的 geometry。

验证结果：

- `conda run -n osteo-vision python -m ruff check backend\src\services\review_service.py backend\tests\contract\test_case_inputs_api.py --output-format concise`：通过。
- `npm --prefix frontend run typecheck`：通过。
- `conda run -n osteo-vision python -m pytest backend\tests\contract\test_case_inputs_api.py::test_video_input_analysis_extracts_keyframes -q`：通过。
- `npm --prefix frontend test -- --run`：通过；8 个前端测试文件、19 个测试。
- `npm --prefix frontend run test:e2e`：通过；3 个 Chromium E2E，MP4 流程已覆盖候选 bbox 编辑。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary`：通过。
- `conda run -n osteo-vision python -m pytest -q`：通过；仍有 FastAPI TestClient 与 torch JIT deprecation warning。
- `npm --prefix frontend run build`：通过。
- `git diff --check`：无 whitespace error；仅有 LF 将被 Git 转 CRLF 的提示。
- `conda run -n osteo-vision python tools\run_platform_smoke.py`：通过；最新摘要 `artifacts/platform_smoke/20260704T000429Z/platform_smoke_summary.json`。

剩余：

- 当前编辑方式是“选择候选 -> ROI 画布重画矩形 -> 保存”，尚未做角点/边线 handle 级精修。
- 复核事件记录了状态变化和 notes，但还没有前端展示修改前后 bbox 的对比。
- 该能力改进的是医生复核交互，不改变模型本身仍为 hotspot baseline/CBCT 代理模型的边界。

## 23. 2026-07-04 本轮缺口修复记录：官方 4K JPEG/MP4 代理压力 smoke

本轮补齐“只支持小样例 MP4，缺少官方 3840x2160 输入压力证据”的工程缺口。当前验证仍是合成代理输入，不是真实手术长视频；它证明的是官方规格文件进入平台后的上传、profile、抽帧、融合、hotspot、导出链路可以跑通。

已完成：

- 新增 `tools/run_official_4k_pressure_smoke.py`：自动生成 3840x2160 白光 JPEG、3840x2160 ICG 代理 JPEG 和 3840x2160 MP4 代理视频。
- 脚本通过 FastAPI TestClient 完成完整链路：建病例、上传 4K JPEG/MP4、验证官方 profile、写入双通道、运行 4K JPEG 融合、写入 MP4、运行 MP4 keyframe hotspot 分析、导出 evidence bundle。
- 输出 `official_4k_pressure_smoke_summary.json` 和 `official_4k_pressure_smoke_report.md`，记录每个阶段耗时、Python heap 峰值、官方规格匹配状态、关键帧/热点数量、timeline manifest 和证据包路径。
- 当前环境没有安装 `psutil`，因此 RSS 记录为空；脚本已自动回退到 `tracemalloc` Python heap 记录。最新运行中 Python heap peak 约 `621.402 MB`。

最新运行结果：

- 命令：`conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 6 --keyframes 3`
- 结果：通过，`pass=true`。
- 摘要：`artifacts/platform_smoke/20260704T001144Z_4k/official_4k_pressure_smoke_summary.json`
- 报告：`artifacts/platform_smoke/20260704T001144Z_4k/official_4k_pressure_smoke_report.md`
- 官方 profile：
  - 白光 JPEG：3840x2160，`official_profile_match`。
  - ICG 代理 JPEG：3840x2160，`official_profile_match`。
  - MP4：3840x2160，`official_profile_match`；当前仅提示 `ffprobe_unavailable`，OpenCV metadata 可用。
- 性能摘要：
  - 上传官方 4K MP4：约 `3.0779 s`。
  - 4K JPEG 融合：约 `1.0648 s`。
  - 4K MP4 keyframe hotspot 分析：约 `5.0375 s`。
  - 证据包导出：约 `0.2439 s`。
  - 证据包总 artifact：`26`。

验证结果：

- `conda run -n osteo-vision python -m ruff check tools\run_official_4k_pressure_smoke.py --output-format concise`：通过。
- `conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 6 --keyframes 3`：通过。

剩余：

- 这仍是短视频代理 pressure smoke，不是 10 分钟级真实 4K 手术长视频。
- 需要继续补旋转 metadata、异常 codec、超大文件、分片/断点上传、长时间后台任务进度和失败分级。
- 若后续要报告 RSS/系统级内存，需在 `osteo-vision` 环境中安装或锁定 `psutil`，或用 Windows 性能计数器补采样。

## 24. 2026-07-04 当前项目缺口再盘点：排除真实项目病例与医生关键帧后的可推进问题

本节按用户最新口径重新盘点：真实项目病例、真实术中 MP4/JPEG 和医生关键帧/ROI 标注目前确实无法作为短期闭环前置条件，因此本节不再把它们作为“本轮必须完成项”重复展开。下面只列项目内部、公开代理数据、工程实现和报告治理层面还能继续推进的问题。

### 24.1 本轮自查命令

| 命令 | 结果 |
|---|---|
| `conda run -n osteo-vision python check_env.py` | 通过；Python `3.11.15`，无 failure/warning。 |
| `conda run -n osteo-vision python tools\check_project_readiness.py` | 通过；仍提示 EGNet/FRS Loss 快照缺关键文件，nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。 |
| `conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml` | 通过；7 个模型中 4 个可用、3 个不可用。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；102 个测试通过，仍有 FastAPI TestClient 与 torch JIT deprecation warning。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；8 个文件、19 个测试。 |
| `npm --prefix frontend run build` | 通过。 |
| `npm --prefix frontend run test:e2e` | 通过；3 个 Chromium E2E。 |
| `conda run -n osteo-vision python tools\run_platform_smoke.py` | 通过；最新摘要 `artifacts/platform_smoke/20260704T002257Z/platform_smoke_summary.json`。 |
| `conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 6 --keyframes 3` | 通过；最新摘要 `artifacts/platform_smoke/20260704T002314Z_4k/official_4k_pressure_smoke_summary.json`。 |
| `git diff --check` | 无 whitespace error；仅有 Git 将 LF 转 CRLF 的 warning。 |

### 24.2 当前能拿来演示的内容

- 4K 官方规格 JPEG/MP4 代理输入链路已经跑通：上传、profile、预抽帧、双通道融合、MP4 hotspot、timeline manifest、导出 evidence bundle 都有 smoke 证据。
- Vue + FastAPI 主线已经能完成“建病例 -> 上传/写入输入 -> 双通道分析或 MP4 关键帧分析 -> 医生复核 -> 候选框编辑 -> 导出证据包”。
- 公开代理视频库目前 manifest 共 77 条，其中本地系统可读 MP4 为 69 条：48 条荧光代理视频、21 条非荧光骨髓炎/相近手术视频。
- ConvNeXt-style 3D 代理模型已经作为正式 adapter family 接入配置和推理清单，但它仍是 D025 CBCT ROI 代理模型。

### 24.3 代码与系统缺口总表

| 优先级 | 缺口 | 证据/位置 | 影响 | 建议动作 |
|---|---|---|---|---|
| P0 | 主线模型可信度不足。 | `model_inventory` 显示 nnU-Net、MedSAM-like、BiomedCLIP 不可用；可用模型仍是 CBCT 代理和启发式 hotspot。 | 赛点二能演示，但科研和比赛汇报时 AI 说服力不足。 | 先固定 ConvNeXt3D/MedNeXt 或 nnU-Net 一条主线，补患者级拆分、Dice/IoU/HD95、阈值曲线、失败样本图。 |
| P0 | MP4/JPEG 目标域分割模型缺失。 | 当前 MP4 结果来自 `src/models/hotspot_segmenter.py` 强度阈值与连通域。 | 视频 AI 只能叫热点 baseline，不能叫训练好的病灶分割。 | 建立 2D 关键帧候选区模型或 promptable MedSAM 最小闭环；输入用公开视频/代理帧，输出仍标注非目标域。 |
| P0 | 荧光融合仍是 V1。 | `src/preprocess/fluorescence.py` 的 registration 为 `resize_only_initial_demo`。 | 赛点一可展示但算法深度不足，遇到双通道错位和背景噪声时解释力弱。 | 做融合 V2：配准、背景扣除、颜色标尺、ROI 时间曲线、4K 下采样策略。 |
| P1 | 4K 压力仍是短代理视频。 | 最新 4K smoke 只有 6 帧、6 fps，且 `ffprobe_unavailable`。 | 官方文档要求 4K MP4，答辩可能追问长视频、大文件、异常编码。 | 扩展到 1-10 分钟代理视频、旋转 metadata、异常 codec、超大文件、分片/断点上传和失败分级。 |
| P1 | 前端失败态证据不足。 | E2E 目前覆盖 8 张成功/布局截图，没有上传错误、409、429、分析失败、导出失败截图。 | 学校评估时只能看到顺风流程，看不到系统稳定性。 | 增加失败态 Playwright 测试和截图集。 |
| P1 | 工作区改动过大，版本未冻结。 | `git status --short` 当前 142 条 modified/untracked。 | 后续 review、提交、回滚和答辩版本管理风险高。 | 按平台后端、前端 MP4、模型训练、研究资料、报告治理拆主题提交。 |

### 24.4 后端代码缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| B-01 | `realtime_video` 仍不是实时 AI。 | `backend/src/services/analysis_service.py` 只返回 `realtime_stream_not_connected`，没有流式抽帧和推理。 | 保持“接口预留”文案，或补低帧率抽样 + hotspot baseline。 |
| B-02 | 上传仍是整文件进入后端本地存储。 | `backend/src/api/uploads.py` 支持 1GB MP4 上限、流式写入和签名校验，但无分片、断点续传、上传进度 API。 | 先补大文件失败分级；后续接分片上传。 |
| B-03 | 上传预抽帧任务缺前端独立任务面板。 | 上传后页面同步等待 `waitForUploadJob()`，最长 180 秒，只有文本提示。 | 将 upload job 纳入同一任务面板，显示进度、取消、失败重试。 |
| B-04 | 本地任务队列仍是 JSON registry。 | `backend/src/services/job_service.py` 可持久化，但没有租约、心跳、优先级、跨进程安全队列。 | 长视频阶段改 SQLite queue/RQ/Celery；取消逻辑要能在抽帧循环内生效。 |
| B-05 | 病例仓库仍是整条 JSON payload 存 SQLite。 | `backend/src/domains/cases/repository.py` 有 version 乐观锁，但 ROI/run/artifact/review event 未拆表。 | 阶段性可用；正式协作前拆子表或补冲突合并流程。 |
| B-06 | API 错误对前端不够友好。 | 后端 409/429/415 有 detail，但 `frontend/src/utils/caseDisplay.ts` 只显示 `接口请求失败，状态码 xxx`。 | 解析 `ApiError.body.detail.message` 并映射中文可操作提示。 |
| B-07 | 文件下载/预览没有远程协作权限模型。 | `backend/src/api/files.py` 限制 artifact root 和后缀，但没有 token、审计、一次性链接。 | 单机 Demo 可接受；远程会诊前补 token 与下载日志。 |
| B-08 | DICOM 只做到 Secondary Capture。 | `backend/src/services/export_service.py` 输出 `dicom_secondary_capture`，不是 DICOM SR/SEG。 | 扩展输出能力短期保留结构化 JSON/CSV + Secondary Capture；下一阶段补 DICOM SR/SEG，但不得替代造影剂、融合处理和 AI 判读三项核心答题要求。 |
| B-09 | 图像质量判断仍偏粗。 | `src/preprocess/image_quality.py` 主要做文件存在、空文件、视频可解码；JPEG 质量主要检查官方 profile。 | 补过曝、欠曝、模糊、弱荧光、通道错配的可量化质量分级。 |

### 24.5 前端代码缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| F-01 | 本地路径输入仍容易误导。 | `frontend/src/components/CaseWorkspaceControls.vue` 仍有 `D:\data\...` 文本路径入口。 | 默认主推文件上传/视频库；把手填路径标为开发调试入口。 |
| F-02 | 失败提示不够可操作。 | `errorMessage()` 未解析后端 detail；上传 HTML 冒充 JPG 只会显示状态码。 | 增加 ApiError detail 翻译和失败态截图。 |
| F-03 | 时间轴 Manifest 还不是完整工作台。 | `AnalysisWorkspaceCard.vue` 展示 summary 和前若干 trace，完整 JSON 只能下载。 | 做详情抽屉：按帧号、score、selected、duplicate 筛选并支持跳转重算。 |
| F-04 | ROI/候选框编辑仍是重画矩形。 | `RoiCanvas.vue` 已支持候选框载入和保存，但无角点 handle、边线拖拽、前后对比。 | 补 handle 编辑、修改历史和 bbox before/after。 |
| F-05 | 视频库缺训练导出能力。 | `DataLibraryPage.vue` 有列表、筛选、预览、导入；无搜索、分页、批量导入、训练 manifest 导出。 | 先补搜索与 manifest 导出，批量动作后置。 |
| F-06 | 摄像头入口仍可能被误解。 | UI 已写“流式 AI 推理仍为接口预留”，但按钮仍叫实时预览。 | 答辩截图和报告必须标注“预览/接口预留”，避免被认为已完成实时 AI。 |
| F-07 | 缺固定演示录像。 | 目前有 e2e 截图和 smoke 产物，没有稳定操作录屏。 | 录制 3 分钟 demo：上传 MP4 -> timeline -> ROI/候选复核 -> 导出。 |

### 24.6 模型、训练和数据缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| M-01 | nnU-Net 配置存在但不可运行。 | `adapter inference not implemented`，checkpoint 目录缺失。 | 把 D025/ToothFairy2/CBCT 代理数据转 nnU-Net，先跑最小 2D/3D 训练推理。 |
| M-02 | MedSAM-like 还只是候选名。 | 缺 checkpoint，缺 prompt 合同，adapter 空实现。 | 若走 MedSAM，先做 2D keyframe box prompt 闭环，与 ROI/bbox 复核联动。 |
| M-03 | ConvNeXt3D 仍是非目标域代理。 | checkpoint 只有 `d025_lesion_smoke.pt`，来自 CBCT ROI 代理。 | 可作为主线雏形，但报告必须写“非目标域代理模型”；补正式训练配置、模型卡、失败样本。 |
| M-04 | 2D hotspot 不是训练模型。 | 使用阈值、CLAHE/归一化、连通域和 ROI 规则。 | 保留为可解释 baseline，不在报告中写成病灶诊断模型。 |
| M-05 | OFDVDnet 和公开视频只能做代理。 | 视频库 69 条本地可读 MP4 中，荧光代理 48 条、非荧光 21 条；但都不是真实 ICG 颌骨骨髓炎目标域。 | 用于伪彩增强、自监督预训练、演示和鲁棒性测试，不用于临床性能主张。 |
| M-06 | 模型不确定性与校准缺失。 | 当前主要有 warning 和固定阈值；没有置信区间、阈值敏感性、校准曲线。 | 补阈值 sweep、风险分级、低置信提示和失败样本图册。 |
| M-07 | 外部代码快照不完整。 | readiness 仍显示 EGNet 缺 `CRA.py/Fusion.py/Transformer.py/bgnet.py/lib/tester.py`，FRS Loss 缺 `models.py/loss_function.py/FRS.py`。 | 降级为文献参考；补完整源码和 license 前不作为可运行资产。 |
| M-08 | 公开数据目录有空占位。 | `d042_modid` 和 `d044_fgs_video` 当前文件数为 0；真实可用数据主要在 D024/D025/D036/D046。 | 清理空目录或写明“待获取/占位”，避免误报数据已就绪。 |

### 24.7 规格、文档与治理缺口

| 编号 | 缺口 | 当前状态 | 建议动作 |
|---|---|---|---|
| G-01 | Spec checklist 仍未勾选。 | `specs/001-software-platform-target/checklists/platform_requirements.md` 仍是全空 checklist。 | 对照当前实现逐项更新，未完成项保留为缺口。 |
| G-02 | README/quickstart 与最新 MP4 能力不同步。 | README 仍偏“框架 + legacy demo”，没有突出 4K MP4/JPEG、视频库、E2E 和 4K smoke。 | 更新 README_CN/README/docs，形成评审快速启动说明。 |
| G-03 | 报告与代码版本没有冻结标签。 | 当前大量未提交文件混在一起，产物路径在本地 artifacts。 | 在可演示版本完成后生成 release note、commit、tag 或至少留冻结清单。 |
| G-04 | 证据包 schema 还未版本化为正式交付协议。 | Export summary 有 schema_version，但没有独立 schema 文档和兼容性说明。 | 写 `docs/export_schema_v1.md`，明确 JSON/CSV/DICOM/manifest 字段。 |

当前结论：排除真实项目病例和医生关键帧两个外部不可控项后，短期最该补的是 **主线模型可信度、荧光融合 V2、失败态可评审证据、长视频/异常编码压力测试、前端错误提示和版本冻结**。其中模型可信度仍是最大短板；前后端基础闭环已经能跑，但还不是可以被称为“稳定比赛版”的状态。

## 25. 2026-07-04 本轮缺口修复记录：前端失败态与可读错误提示

本轮优先补第 24 节中的 F-02/F-05：成功路径已经有 E2E 截图，但失败态和后端错误信息此前不够可评审。当前已让上传错误、队列冲突、队列容量和双通道缺失分析失败显示可读中文提示，并新增浏览器失败态截图。

已完成：

- 更新 `frontend/src/utils/caseDisplay.ts`：`errorMessage()` 现在会解析后端 `ApiError.body.detail`，不再只显示“接口请求失败，状态码 xxx”。
- 新增错误映射：
  - 415 上传图片内容与后缀不匹配。
  - 415 MP4 容器签名缺失。
  - 413 文件过大。
  - 409 已有后台任务冲突。
  - 429 后台任务队列满。
  - 409 病例版本冲突。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：双通道分析如果后端返回 `failed` run，会把首个 blocking warning 翻译成用户可读错误提示，而不是显示“分析完成”。
- 新增 `frontend/tests/CaseDisplayErrors.test.ts`：覆盖上传签名错误、409/429 队列错误和缺双通道 warning 翻译。
- 更新 `frontend/e2e/platform.browser.pw.ts`：新增浏览器失败态流程，覆盖：
  - 上传 HTML 内容伪装成 `.jpg` 后显示“上传文件内容与图片后缀不匹配”。
  - 未提供白光/ICG 时直接运行双通道分析，显示“需要同时提供白光和 ICG 荧光输入后才能进行融合分析”，且分析卡显示“未通过”。
- 新增 E2E 证据截图：
  - `artifacts/e2e/browser_smoke/09-upload-error-state.png`
  - `artifacts/e2e/browser_smoke/10-analysis-failure-state.png`

验证结果：

- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run CaseDisplayErrors.test.ts`：通过，3 个测试。
- `npm --prefix frontend run test:e2e`：通过，4 个 Chromium E2E，新增失败态测试通过。

剩余：

- 当前失败态已覆盖上传 415 和缺双通道分析失败；还需继续补 409/429、导出失败、文件预览/下载 403/404 的浏览器级截图。
- 后端长视频任务失败仍需要更细分错误码，例如 codec 不支持、旋转未归一化、视频不可解码、超大文件、关键帧抽取为空。
- 失败态截图已经能支撑一次答辩说明，但还未形成独立的“异常输入测试报告”。

## 26. 2026-07-04 本轮缺口修复记录：荧光融合 V2 轻量升级

本轮开始补第 24 节中的 P0 算法缺口：原先 `src/preprocess/fluorescence.py` 只做 resize、min-max normalize、伪彩和 alpha blend，报告里明确标记 `resize_only_initial_demo`。现在保留轻量可解释路线，但把融合升级为 V2：背景扣除、平移配准元数据和荧光色标输出。

已完成：

- 更新 `src/preprocess/fluorescence.py`：
  - `fuse_white_light_fluorescence()` 默认写入 `algorithm_version=fluorescence_fusion_v2`。
  - 新增低百分位背景扣除：`subtract_fluorescence_background()`，默认用 5th percentile floor subtraction，报告写入 baseline、percentile 和 applied 状态。
  - 新增轻量平移配准：`register_fluorescence_to_reference()`，默认用 OpenCV phase correlation 估计白光/荧光之间的小幅平移；低响应或位移过大时不会强行扭曲图像，而是在 `registration_details` 中记录未应用原因。
  - 新增 `fluorescence_colorbar()`，输出带阈值 marker 的伪彩色标图。
  - 融合 JSON/Markdown 报告新增 `registration_details`、`background_correction` 和 `colorbar_path`。
- 更新 `backend/src/domains/cases/enums.py`：新增 artifact kind `colorbar`。
- 更新 `backend/src/services/analysis_service.py`：证据 artifact 中纳入 `colorbar_path`。
- 更新 `frontend/src/utils/caseDisplay.ts`：导出 artifact 列表中将 `colorbar` 显示为“荧光色标”。
- 更新 `app/main.py`：legacy Gradio warning 文案从 V1 resize demo 改为 V2 fusion 前 resize。
- 更新 `tests/unit/test_fluorescence_preprocess.py`：覆盖背景扣除、色标生成和 V2 融合报告字段。

验证结果：

- `conda run -n osteo-vision python -m ruff check src/preprocess/fluorescence.py backend/src/services/analysis_service.py backend/src/domains/cases/enums.py tests/unit/test_fluorescence_preprocess.py app/main.py --output-format concise`：通过。
- `conda run -n osteo-vision python -m pytest tests/unit/test_fluorescence_preprocess.py backend/tests/unit/test_analysis_service.py -q`：通过，8 个测试。

剩余：

- 当前配准仍是轻量平移估计，不是完整双通道形变配准；真实显微镜双通道错位需要用真实标定图或更可靠的特征/互信息方法验证。
- 目前还没有 ROI 时间曲线；该能力更适合在 MP4 关键帧/帧序列路径上补。
- 色标已经进入 artifact/export，但主界面还没有独立的色标查看卡片；后续可以在热图面板旁显示 colorbar。

## 27. 2026-07-04 当前项目缺口复查：排除真实病例与医生关键帧后的剩余问题

本节按当前实际约束更新：真实项目病例、真实术中 MP4/JPEG、医生关键帧/ROI 标注目前不作为短期闭环前置条件。它们仍是一级外部风险，但本节重点列还能由工程、公开代理数据、模型训练流程和文档治理继续推进的问题。

### 27.1 本次复查命令与结论

| 命令 | 结果 |
|---|---|
| `conda run -n osteo-vision python check_env.py` | 通过；Python `3.11.15`，无 failure/warning。 |
| `conda run -n osteo-vision python tools\check_project_readiness.py` | 通过；仍提示 EGNet/FRS Loss 外部代码快照缺关键文件，nnU-Net/MedSAM/BiomedCLIP checkpoint 缺失。 |
| `conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml` | 通过；7 个模型条目中 4 个可用、3 个不可用。 |
| `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` | 通过。 |
| `conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` | 通过。 |
| `conda run -n osteo-vision python -m pytest -q` | 通过；仍有 FastAPI TestClient 与 torch JIT deprecation warning。 |
| `npm --prefix frontend run typecheck` | 通过。 |
| `npm --prefix frontend test -- --run` | 通过；9 个测试文件、22 个测试。 |
| `npm --prefix frontend run build` | 通过。 |
| `npm --prefix frontend run test:e2e` | 通过；4 个 Chromium E2E，含失败态截图流程。 |
| `conda run -n osteo-vision python tools\run_platform_smoke.py` | 通过；最新摘要 `artifacts/platform_smoke/20260704T005251Z/platform_smoke_summary.json`，导出 evidence bundle 含 `colorbar`，`total_artifact_count=27`。 |
| `conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 6 --keyframes 3` | 通过；最新摘要 `artifacts/platform_smoke/20260704T005308Z_4k/official_4k_pressure_smoke_summary.json`。 |
| `git diff --check` | 无 whitespace error；仅有 Git 将 LF 转 CRLF 的 warning。 |

当前代码质量门禁是通过的，工程主线能跑；项目的问题主要不是“跑不起来”，而是模型可信度、长视频鲁棒性、前端审阅深度、远程/导出规范和版本冻结还不够比赛版稳定。

### 27.2 当前最高优先级缺口

| 优先级 | 缺口 | 当前证据 | 影响 | 建议动作 |
|---|---|---|---|---|
| P0 | 赛点二模型可信度仍不足。 | `model_inventory` 显示可用模型是 `convnext3d_d025_proxy_segmenter`、`d025_lesion_smoke_segmenter`、`fluorescence_hotspot_2d_segmenter`、`fixture_default`；nnU-Net、MedSAM-like、BiomedCLIP 不可用。 | AI 辅助诊断能演示，但不能支撑“已训练颌骨骨髓炎术中模型”的说法。 | 先定一条主线：ConvNeXt/MedNeXt 3D CBCT 代理训练，或 2D keyframe + promptable MedSAM 最小闭环；必须补患者级拆分、Dice/IoU/HD95、阈值曲线和失败样本。 |
| P0 | MP4/JPEG 关键帧没有训练型病灶模型。 | 视频分析仍主要依赖 `fluorescence_hotspot_2d_segmenter` 强度阈值、连通域和 ROI 规则。 | 对官方 4K MP4 可以产出热点，但只能叫可解释 hotspot baseline。 | 建立 2D keyframe 数据集清单、弱标注/伪标注流程和最小训练脚本；输出仍标注非目标域代理。 |
| P1 | 4K MP4 只做了 6 帧代理 smoke。 | `run_official_4k_pressure_smoke.py --frames 6 --keyframes 3` 通过，但 `ffprobe_unavailable`，且不是长手术视频。 | 答辩可能追问 1-10 分钟视频、异常编码、旋转 metadata、码率和超大文件。 | 补 1-10 分钟代理 MP4、旋转 metadata、异常 codec、不可解码视频、超大文件和更明确失败分级。 |
| P1 | 实时视频仍是接口预留。 | `backend/src/services/analysis_service.py` 对 `mode=realtime_video` 返回 `realtime_stream_not_connected`。 | 前端“实时预览”容易被误解为实时 AI 已完成。 | 保持文案边界，或做低帧率抽样 + hotspot baseline 的最小实时链路。 |
| P1 | 上传和任务队列仍是本地本地验证级。 | `backend/src/api/uploads.py` 整文件流式写入，MP4 上限 1GB；`backend/src/services/job_service.py` 使用 JSON registry。 | 长视频并发、断点续传、跨进程任务可靠性不足。 | 先补失败码和进度面板；随后改分片上传、SQLite job queue 或正式后台队列。 |
| P1 | 前端分析查看深度不够。 | timeline summary、trace、筛选已有；colorbar 已进 artifact/export，但主界面未作为独立查看卡片展示。 | 演示可看，但评审深挖算法证据时信息不够顺手。 | 在分析面板显示荧光色标、V2 配准/背景扣除元数据、完整 frame detail 抽屉和 artifact 快速预览。 |
| P1 | 医生复核交互还停在矩形重画。 | `RoiCanvas` 能保存 ROI、候选框能回写 geometry，但没有角点 handle、边线拖拽和修改前后对比。 | 可完成闭环，但不像成熟审阅工作台。 | 补 bbox handle 编辑、before/after 对比和复核事件可视化。 |
| P1 | 证据导出还不是完整 DICOM 标准方案。 | 目前导出含 JSON/CSV/Markdown/ZIP 和 `dicom_secondary_capture`。 | 可作为扩展输出雏形，但还不能说 DICOM SR/SEG 完整实现，也不能写成完整赛题原文核心赛点。 | 短期写清 Secondary Capture 边界；中期补 DICOM SR/SEG schema 和兼容说明。 |
| P1 | 版本治理未冻结。 | `git status --short` 仍有大量 modified/untracked 文件。 | 后续 review、提交、答辩版本和回滚风险高。 | 按后端平台、前端工作台、模型/数据、报告/文献四组拆分 review 与提交。 |

### 27.3 后端代码剩余问题

| 编号 | 问题 | 证据/位置 | 建议 |
|---|---|---|---|
| B-01 | 实时 AI 未连接。 | `backend/src/services/analysis_service.py` 的 `realtime_stream_not_connected`。 | 将实时入口明确标为预览/预留，或接入低帧率 keyframe 抽样分析。 |
| B-02 | 上传没有分片/断点续传。 | `backend/src/api/uploads.py` 使用 `request.stream()` 写入单文件，只有大小上限和签名校验。 | 补分片协议、上传进度、取消、重试和临时文件清理策略。 |
| B-03 | 后台任务持久化偏弱。 | `backend/src/services/job_service.py` 使用 `jobs.json`，无租约、心跳、优先级和跨进程锁。 | 单机比赛版可暂用；长视频和多用户前改 SQLite/RQ/Celery。 |
| B-04 | 病例库仍是 JSON payload 主体。 | `backend/src/domains/cases/repository.py` 有 SQLite 和 version，但 ROI/run/artifact/event 未拆细表。 | 正式协作前拆表或补冲突合并策略。 |
| B-05 | 长视频错误码不够细。 | 当前已有 413/415/409/429 等基础错误，但 codec、旋转、抽帧为空、弱信号等还不系统。 | 统一定义 medically sensitive warning/error taxonomy。 |
| B-06 | 文件访问缺远程权限模型。 | `backend/src/api/files.py` 主要限制 artifact root 和后缀。 | 远程协作前补 token、下载审计、一次性链接和过期策略。 |
| B-07 | DICOM 仍是 Secondary Capture。 | `backend/src/services/export_service.py`、`backend/src/reports/dicom_secondary_capture.py`。 | 下一阶段补 DICOM SR/SEG 或至少写独立导出 schema 文档。 |

### 27.4 前端代码剩余问题

| 编号 | 问题 | 证据/位置 | 建议 |
|---|---|---|---|
| F-01 | 本地路径输入仍像正式入口。 | `frontend/src/components/CaseWorkspaceControls.vue` 仍有 `D:\data\...` 占位路径。 | 默认突出文件上传/视频库；手填路径标为开发调试。 |
| F-02 | 失败态还没覆盖全部浏览器场景。 | 已覆盖 415 上传坏图和缺双通道分析失败；缺 409/429、导出失败、403/404 文件预览截图。 | 补 Playwright 失败态截图集。 |
| F-03 | 荧光 V2 元数据没有充分前端化。 | `colorbar` 已进入 artifact/export；主分析卡没有直接展示色标、背景扣除和配准响应。 | 热图旁展示 colorbar；报告卡显示 algorithm_version、registration response、background baseline。 |
| F-04 | 时间轴详情仍偏摘要。 | `AnalysisWorkspaceCard.vue` 展示 summary、trace 和前端筛选，但完整 manifest 主要靠下载。 | 做 frame detail 抽屉，支持帧号、score、duplicate、ROI hit、candidate count 过滤和跳转。 |
| F-05 | ROI/候选框编辑不够精修。 | 当前是加载候选框后重画矩形保存。 | 增加角点/边线 handle、键盘微调、修改前后对比。 |
| F-06 | 视频库还不能直接服务训练。 | `DataLibraryPage.vue` 有列表、预览、导入；缺训练 manifest 导出和批量操作。 | 补搜索、分页、批量导入和训练 manifest 导出。 |
| F-07 | 缺固定演示录像。 | 已有 E2E 截图和 smoke 产物，但无稳定录屏。 | 录一条 3 分钟演示：4K/MP4 上传、timeline、复核、导出。 |

### 27.5 模型、训练和数据剩余问题

| 编号 | 问题 | 当前状态 | 建议 |
|---|---|---|---|
| M-01 | 主线模型需要收敛到一条可报告路线。 | ConvNeXt-style 3D 代理可用，但仍是 D025 CBCT ROI proxy。 | 以 ConvNeXt/MedNeXt 3D 为近期主线，明确“CBCT 代理模型”；同步保留 2D keyframe hotspot baseline。 |
| M-02 | nnU-Net 配置存在但不可运行。 | 缺 `artifacts/checkpoints/osteo_vision/nnunet_v2`，adapter inference 未实现。 | 将 D024/D025/D036 派生数据转 nnU-Net 标准格式，先跑最小推理/训练闭环。 |
| M-03 | MedSAM-like 未落地。 | 缺 `medsam2.pt`，缺 point/box/mask prompt contract，adapter 未实现。 | 若采用 MedSAM，先做 2D keyframe box prompt：前端 ROI/bbox -> adapter -> mask -> 回写候选。 |
| M-04 | BiomedCLIP 仍是候选项。 | 缺 `open_clip` 和 checkpoint，adapter 未实现。 | 降为后续图像级检索/筛查参考，短期不要放主线。 |
| M-05 | hotspot 不是训练模型。 | `src/models/hotspot_segmenter.py` 是阈值/连通域规则。 | 作为可解释 baseline 保留；报告中避免写成病灶诊断模型。 |
| M-06 | 正式评估缺失。 | 现有 smoke 证明链路，不证明目标域性能。 | 输出实验报告：患者级拆分、Dice/IoU/HD95、阈值 sweep、校准曲线、不确定性和失败样本图。 |
| M-07 | 外部模型快照不完整。 | readiness 显示 EGNet/FRS Loss 缺关键源码。 | 补完整源码与 license 前只作为文献参考，不作为可运行模型资产。 |
| M-08 | 数据目录有空占位。 | `d042_modid`、`d044_fgs_video` 文件数为 0；`d046_fluorescence_osteomyelitis_videos` 已有 460 个文件。 | 空目录标注待获取或清理；数据报告按真实可用目录更新。 |
| M-09 | 视频代理数据来源需要持续审计。 | `video_library_manifest_20260704.csv` 共 77 条，`download_status=exists` 71 条、`downloaded` 3 条、未下到 3 条；荧光 52 条、非荧光 25 条。 | 后续训练/演示只用已校验本地文件，并在 manifest 中继续区分荧光、非荧光、骨髓炎、非目标域代理。 |

### 27.6 规格、报告和治理剩余问题

| 编号 | 问题 | 当前状态 | 建议 |
|---|---|---|---|
| G-01 | Spec Kit 平台 checklist 未同步。 | `specs/001-software-platform-target/checklists/platform_requirements.md` 仍是全空 `[ ]`。 | 对照当前实现逐项打勾，未完成项转缺口。 |
| G-02 | README/quickstart 需要同步最新能力。 | 当前实现已包含 4K MP4、视频库、失败态、colorbar、platform smoke；文档仍可能滞后。 | 更新 `README.md`、`README_CN.md`、`docs/` 快速启动和演示脚本。 |
| G-03 | 证据包 schema 还没有正式文档。 | export summary 有 `schema_version`，但缺独立字段说明。 | 写 `docs/export_schema_v1.md`，定义 JSON/CSV/DICOM/manifest 字段。 |
| G-04 | 运行产物和源码需要分层管理。 | `artifacts/`、checkpoint、raw/derived 数据按规则不进 Git，但本地很多运行产物会干扰人工自查。 | 做一次非破坏性清单整理，提交前只 stage 源码、测试、报告、manifest。 |
| G-05 | 环境小缺口。 | 4K smoke 因缺 `psutil` 只能记录 Python heap，RSS 为空。 | 若要报告系统内存，锁定 `psutil` 依赖或用 Windows 性能计数器采样。 |

### 27.7 建议后续开发顺序

1. 先冻结当前能跑版本：补 README/quickstart、更新 Spec checklist、按主题拆分提交，避免当前大工作区继续失控。
2. 再补模型主线：以 ConvNeXt/MedNeXt 3D CBCT 代理训练为主，2D MP4 keyframe hotspot/MedSAM prompt 为辅，先产出正式评估报告。
3. 接着补 4K 长视频鲁棒性：长代理 MP4、异常 codec、旋转 metadata、超大文件、失败码和前端失败态截图。
4. 然后补前端证据展示：colorbar、融合 V2 元数据、timeline/frame detail 抽屉、ROI handle 编辑。
5. 最后推进 DICOM SR/SEG、远程权限、任务队列和分片上传，这些更偏正式版平台能力。

## 28. 2026-07-04 本轮缺口修复记录：前端荧光融合 V2 证据展示

本轮补第 27 节中的 F-03：荧光融合 V2 已在后端生成 `colorbar_path`、背景扣除、平移配准和算法版本元数据，但前端主分析工作台此前没有直接展示这些证据。现在主分析卡已经能把 V2 元数据作为可审阅证据展示出来，减少评审时只能下载 JSON 才能看到算法细节的问题。

已完成：

- 更新 `frontend/src/components/analysisPreview.ts`：
  - 新增 `FusionEvidenceSummary` 和 `fusionEvidenceSummaryFromRun()`。
  - 从 `fused_outputs.fusion`、`fused_outputs.outputs` 和 `fused_outputs.quantification` 中提取 `algorithm_version`、融合方法、阈值、alpha、背景扣除 baseline、配准方法、平移估计、配准响应、输入尺寸和 `colorbar_path`。
  - 将底层字段转换为前端可读标签，例如“背景扣除 + 平移配准 + 伪彩融合”“已扣除 · P5 · baseline 12.5”“已应用 · 相位相关平移”。
- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：根据最新 analysis run 生成 `fusionEvidenceSummary`，并传入主分析卡。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：
  - 在四宫格分析视图下方新增“荧光融合证据”面板。
  - 直接展示荧光色标图、阈值、alpha、融合方法、背景扣除、配准状态、平移估计、配准响应和输入尺寸。
  - 导出证据文件列表新增 `colorbar` 的中文标签“荧光色标”。
- 更新 `frontend/tests/AnalysisPreviewPanels.test.ts`：新增单元测试覆盖荧光融合 V2 元数据解析、色标预览链接和中文展示标签。

验证结果：

- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend test -- --run AnalysisPreviewPanels.test.ts`：通过；7 个测试。
- `npm --prefix frontend test -- --run`：通过；9 个测试文件、23 个测试。
- `npm --prefix frontend run build`：通过。
- `npm --prefix frontend run test:e2e`：通过；4 个 Chromium E2E。

剩余：

- 该修复只解决“V2 证据在前端可见”的问题，不改变后端融合算法本身。
- 配准仍是轻量 phase correlation 平移估计，缺真实显微镜双通道标定验证。
- 下一步前端证据展示还应继续补完整 frame detail 抽屉、导出失败截图、ROI/bbox handle 级编辑和模型结果对比视图。

## 29. 2026-07-04 本轮缺口修复记录：D025/ConvNeXt 代理模型训练与正式评估

本轮继续补第 27 节中的 P0/M-01/M-06：此前 D025 checkpoint 主要是 2-batch smoke，只能证明训练、adapter 和推理链路存在，缺少足够可审计的模型评估证据。现在已对本地 D025 CBCT lesion ROI 代理数据进行一轮更充分训练，并新增独立评估脚本，输出阈值扫描、Dice/IoU/HD95/NSD、失败样本预览和中英报告。

已完成：

- 新增 `scripts/evaluate_d025_proxy_model.py`：
  - 读取 `d025_dolchid_lesion_roi_64_manifest.csv` 和当前 `d025_lesion_smoke.pt` checkpoint。
  - 对指定 split 做多阈值扫描。
  - 输出 per-case CSV、JSON 汇总、中英 Markdown 报告和低分样本预览图。
  - 指标包括 Dice、IoU、HD95、NSD、lesion sensitivity、lesion precision、预测阳性体素比例和目标阳性体素比例。
  - 报告内显式写明这是 D025 CBCT ROI 代理评估，不是术中 ICG 颌骨骨髓炎性能。
- 新增 `tests/unit/test_d025_proxy_model_evaluation.py`：
  - 使用临时 NPZ ROI、临时 checkpoint 和临时 manifest 验证评估脚本能生成 JSON、CSV、中英报告和失败样本预览。
- 重新训练当前本地 D025 代理 checkpoint：
  - 命令：`conda run -n osteo-vision python scripts\train_d025_lesion_smoke_model.py --max-train-cases 160 --max-val-cases 32 --max-train-batches 160 --batch-size 2 --base-channels 4 --learning-rate 0.001 --positive-class-weight 30 --threshold 0.5 --device auto`
  - Checkpoint：`artifacts/checkpoints/osteo_vision/d025_lesion_smoke.pt`
  - 训练报告：`research/reports/modeling/d025_lesion_smoke_model_20260704_zh.md` 和英文版。
  - 训练脚本内置验证：32 个 val 样本，Foreground Dice `0.1324`，IoU `0.0739`，sensitivity `0.8391`，precision `0.0794`。
- 对完整 val split 重新评估：
  - 命令：`conda run -n osteo-vision python scripts\evaluate_d025_proxy_model.py --split val --thresholds "0.30,0.40,0.50,0.60,0.70" --failure-count 6 --device auto`
  - 评估样本：53 个 val ROI。
  - 最优阈值：`0.60`。
  - Mean Dice：`0.1363`。
  - Mean IoU：`0.0787`。
  - Mean HD95：`71.0074`。
  - Mean NSD：`0.0454`。
  - Lesion sensitivity：`0.4979`。
  - Lesion precision：`0.0837`。
  - 评估报告：`research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md` 和英文版。
  - per-case CSV：`research/reports/modeling/d025_proxy_model_evaluation_20260704_per_case.csv`。
  - JSON：`research/reports/modeling/d025_proxy_model_evaluation_20260704.json`。
  - 低分样本预览：`research/reports/modeling/assets/d025_proxy_eval_20260704T011243Z/`。
- 更新 `configs/inference/osteo_vision.yml`：
  - `runtime.default_threshold` 从 `0.5` 调整为 `0.6`。
  - `convnext3d_d025_proxy_segmenter.extra.threshold` 从 `0.5` 调整为 `0.6`。
  - `d025_lesion_smoke_segmenter.extra.threshold` 从 `0.5` 调整为 `0.6`。
- 重新生成 `model_checkpoint_manifest_20260704.*`，当前清单仍显示：
  - 可用：`convnext3d_d025_proxy_segmenter`、`fluorescence_hotspot_2d_segmenter`、`d025_lesion_smoke_segmenter`、`fixture_default`。
  - 不可用：`nnunet_v2_osteo_baseline`、`medsam2_osteo_promptable`、`biomedclip_osteo_screening`。

验证结果：

- `conda run -n osteo-vision python -m ruff check scripts\evaluate_d025_proxy_model.py tests\unit\test_d025_proxy_model_evaluation.py --output-format concise`：通过。
- `conda run -n osteo-vision python -m pytest tests\unit\test_d025_proxy_model_evaluation.py -q`：通过。
- `conda run -n osteo-vision python scripts\evaluate_d025_proxy_model.py --split val --thresholds "0.30,0.40,0.50,0.60,0.70" --failure-count 6 --device auto`：通过。
- `conda run -n osteo-vision python scripts\model_inventory.py --config configs\inference\osteo_vision.yml`：通过；代理模型阈值已读到 `0.6`。
- `conda run -n osteo-vision python scripts\generate_model_checkpoint_manifest.py --config configs\inference\osteo_vision.yml`：通过。
- `conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise`：通过。
- `conda run -n osteo-vision python -m pytest tests\unit\test_d025_proxy_model_evaluation.py tests\unit\test_model_adapters.py tests\unit\test_model_checkpoint_manifest.py -q`：通过。

剩余：

- 当前模型仍是 D025 CBCT ROI 代理模型，不是术中 ICG MP4/JPEG 目标域模型；报告和答辩中必须继续这样表达。
- Mean Dice `0.1363` 只能说明代理模型链路比原 smoke 更可审计，不能称为高性能模型。
- 仍缺患者级交叉验证、更多训练轮次、模型对比、校准曲线、真实 CBCT 小样本适配和 MP4/JPEG keyframe 训练型模型。
- nnU-Net、MedSAM-like、BiomedCLIP 仍未成为可运行主线。

## 30. 2026-07-04 本轮缺口修复记录：MP4 上传鲁棒性和异常输入分级

本轮补第 27 节中的 P1/B-05：官方设备输入边界要求系统优先支持 4K MP4 和 JPEG。此前平台已经能处理合成 4K MP4 smoke，但对“容器签名看似 MP4、实际不可解码”的上传文件会进入后续流程，容易在演示或评审中形成隐性坏数据。现在上传入口已经在签名校验后继续调用内容级校验，无法被 OpenCV 解码或输入验证失败的 MP4/JPEG 会被阻断，并返回结构化 422 错误。

已完成：

- 更新 `backend/src/api/uploads.py`：
  - 文件签名和类型校验通过后，继续调用 `validate_input(path)` 做内容级校验。
  - 若 `summary.accepted` 为 `false`，立即删除上传临时文件并返回 HTTP `422`。
  - 错误详情使用 `code=upload_content_unreadable`，同时返回 `reason`、`input_type` 和阻断 warning，便于前端展示和测试断言。
- 更新 `backend/tests/contract/test_case_inputs_api.py`：
  - 新增 `test_raw_upload_rejects_corrupt_mp4_even_with_container_signature`。
  - 覆盖“伪 ftyp MP4、容器签名存在、但 OpenCV 无法打开”的异常路径。
- 更新 `frontend/src/utils/caseDisplay.ts` 和 `frontend/tests/CaseDisplayErrors.test.ts`：
  - 新增 `upload_content_unreadable` 的中文文案：“上传文件无法解码或校验未通过，请确认 MP4/JPEG 文件可正常打开。”
  - HTTP `422` 显示为“文件内容无法处理”。
- 新增 `tools/run_mp4_edge_case_smoke.py`：
  - 生成 48 帧、4K、6 FPS 的合成 MP4，用于比原 6 帧 pressure smoke 更长一点的代理验证。
  - 生成 1920x1080 低分辨率 MP4，验证官方 profile warning。
  - 生成坏签名 MP4，验证 HTTP `415`。
  - 生成伪 ftyp 不可解码 MP4，验证 HTTP `422` 和 `upload_content_unreadable`。
  - 跑通上传 keyframe job、case analysis job、timeline/frame detail manifest 和 evidence bundle 导出。

最新验证结果：

- 命令：`conda run -n osteo-vision python tools\run_mp4_edge_case_smoke.py --frames 48 --keyframes 5 --fps 6`
- 输出目录：`artifacts/platform_smoke/20260704T012617Z_mp4_edges/`
- 汇总 JSON：`artifacts/platform_smoke/20260704T012617Z_mp4_edges/mp4_edge_case_smoke_summary.json`
- Markdown 报告：`artifacts/platform_smoke/20260704T012617Z_mp4_edges/mp4_edge_case_smoke_report.md`
- 验证结论：`pass=true`。
- 48 帧 4K MP4：上传 job `completed`，分析 job `completed`，提取关键帧 `5`，热点候选 `95`。
- evidence bundle：存在；导出汇总显示 `total_artifact_count=29`，包含 DICOM Secondary Capture、heatmap、overlay、keyframe、CSV、JSON、Markdown 和 ZIP bundle。
- 低分辨率 MP4：HTTP `200`，profile 为 `accepted_with_profile_warnings`，warning 包含 `official_video_resolution_mismatch`。
- 坏签名 MP4：HTTP `415`，detail 为 `uploaded MP4 container signature is missing`。
- 伪 ftyp 不可解码 MP4：HTTP `422`，detail code 为 `upload_content_unreadable`，reason 为 `video capture could not be opened`。

验证命令：

- `conda run -n osteo-vision python -m ruff check backend\src\api\uploads.py backend\tests\contract\test_case_inputs_api.py tools\run_mp4_edge_case_smoke.py --output-format concise`：通过。
- `conda run -n osteo-vision python -m pytest backend\tests\contract\test_case_inputs_api.py::test_raw_upload_rejects_corrupt_mp4_even_with_container_signature tests\unit\test_input_validation.py::test_rejects_fake_mp4_payload -q`：通过。
- `npm --prefix frontend test -- --run CaseDisplayErrors.test.ts`：通过。
- `conda run -n osteo-vision python tools\run_mp4_edge_case_smoke.py --frames 48 --keyframes 5 --fps 6`：通过。

剩余：

- 该 smoke 仍是合成代理 MP4，不是真实术中 ICG 颌骨骨髓炎长视频。
- 还缺 1-10 分钟长视频压力测试、旋转 metadata、异常 codec、高码率/大文件、HEVC/H.265 兼容性和 multipart/resumable upload 验证。
- 当前环境缺 `psutil`，报告中 RSS 内存为 `null`，只能记录 Python heap；若要对外汇报内存峰值，需要补 `psutil` 或 Windows 性能计数采样。
- OpenCV/FFmpeg 对坏 MP4 会输出 `moov atom not found` 等 stderr 噪声，这是预期的异常路径，但后续可以在工具层做日志收敛，避免演示时误解为主流程崩溃。

## 31. 2026-07-04 扣除已修复项后的剩余项目缺口

本节按当前代码和验证结果重新列缺口。真实项目病例、真实术中 ICG 颌骨骨髓炎 MP4/JPEG、医生关键帧/ROI 标注目前不可得，已按外部数据依赖和一级风险处理；下表主要列这些外部前置以外，代码、模型、数据代理、文档和工程治理仍能继续推进的问题。

当前可核验证据：

- Python 质量门禁：`conda run -n osteo-vision python -m ruff check src backend tests scripts tools --output-format concise` 通过。
- Python 类型门禁：`conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary` 通过。
- Python 测试：`conda run -n osteo-vision python -m pytest -q` 通过；当前 105 个测试通过，仅有依赖库弃用 warning。
- 前端类型、单测、构建和 E2E：`npm --prefix frontend run typecheck`、`npm --prefix frontend test -- --run`、`npm --prefix frontend run build`、`npm --prefix frontend run test:e2e` 均通过；前端单测 9 个文件 24 个测试，E2E 4 条。
- 平台 smoke：`artifacts/platform_smoke/20260704T013335Z/platform_smoke_summary.json`，JPEG/MP4 上传、分析、复核导出和证据包通过。
- 官方 4K pressure smoke：`artifacts/platform_smoke/20260704T013352Z_4k/official_4k_pressure_smoke_summary.json`，4K JPEG、4K MP4、融合、关键帧分析、导出通过。
- MP4 edge smoke：`artifacts/platform_smoke/20260704T012617Z_mp4_edges/mp4_edge_case_smoke_summary.json`，低分辨率 warning、坏签名 415、不可解码 ftyp 422 均通过。
- 模型清单：`scripts/model_inventory.py --config configs\inference\osteo_vision.yml` 显示 7 个模型配置中 4 个可用，3 个不可用。
- readiness：`tools/check_project_readiness.py` 显示核心文件、文献/数据清单、工作区目录和主要工具存在；EGNet/FRS Loss 快照与 3 个候选模型 checkpoint 仍缺。

### 31.1 后端剩余缺口

| 编号 | 优先级 | 缺口 | 当前证据 | 建议动作 |
|---|---:|---|---|---|
| B-01 | P0 | 实时视频 AI 仍未接入。 | `backend/src/services/analysis_service.py` 对 realtime 入口仍是预留语义。 | 比赛版明确标为“低帧率抽样/离线上传优先”；若要演示实时，先做 1-2 FPS keyframe hotspot baseline。 |
| B-02 | P0 | 长视频上传缺 multipart/resumable 能力。 | `backend/src/api/uploads.py` 已有流式写入、大小上限、签名和内容校验，但仍是单请求上传。 | 补分片上传、断点续传、取消、重试、临时文件清理和前端进度协议。 |
| B-03 | P1 | 后台任务仍偏本地平台验证。 | `backend/src/services/job_service.py` 使用本地 registry；smoke 可跑，但不适合多进程/多用户可靠队列。 | 比赛版可保留；正式版改 SQLite/RQ/Celery，增加租约、心跳、重试和失败恢复。 |
| B-04 | P1 | 病例、ROI、run、artifact 持久化还未完全规范化。 | 当前 repository 已能支持演示，但协作冲突、版本合并、审计查询仍弱。 | 设计病例库 schema，把 ROI、run、artifact、review event 拆表或补版本合并策略。 |
| B-05 | P1 | 文件访问权限和远程协作安全边界不足。 | `backend/src/api/files.py` 主要做 artifact root 和后缀限制。 | 补 token/会话权限、下载审计、一次性链接、过期策略和脱敏策略文档。 |
| B-06 | P1 | DICOM 仍是 Secondary Capture 雏形。 | `backend/src/reports/dicom_secondary_capture.py` 和导出 summary 可生成 DICOM SC。 | 短期写清 SC 边界；下一阶段补 DICOM SR/SEG schema、字段映射和兼容测试。 |
| B-07 | P1 | 异常视频覆盖还不完整。 | 已覆盖低分辨率、坏签名、不可解码 ftyp；未覆盖旋转 metadata、异常 codec、高码率、长视频、抽帧为空。 | 扩展 `tools/run_mp4_edge_case_smoke.py`，增加 1-10 分钟代理 MP4、HEVC/H.265、旋转和大文件场景。 |
| B-08 | P2 | 系统资源监测不完整。 | smoke 报告中 `psutil` 缺失，RSS 为 `null`，只有 Python heap。 | 将 `psutil` 纳入依赖，或用 Windows 性能计数器采样。 |
| B-09 | P2 | 依赖 warning 需要后续处理。 | `pytest` 和 smoke 中出现 Starlette/httpx 弃用 warning；Torch JIT interface 也有弃用 warning。 | 锁定兼容版本或升级测试客户端；模型代码逐步避开已弃用接口。 |

### 31.2 前端剩余缺口

| 编号 | 优先级 | 缺口 | 当前证据 | 建议动作 |
|---|---:|---|---|---|
| F-01 | P0 | 长视频进度、取消和失败恢复体验不足。 | 前端能上传/分析/导出，E2E 通过；但 multipart/resumable 未完成，长任务进度仍偏基础。 | 做上传进度、任务进度、取消、重试、失败原因定位和历史任务恢复。 |
| F-02 | P1 | 本地路径输入仍带开发调试色彩。 | `frontend/src/components/CaseWorkspaceControls.vue` 仍保留路径输入形态。 | 默认突出文件上传/视频库；路径输入标为开发调试或折叠进高级模式。 |
| F-03 | P1 | frame detail 仍缺完整可视化抽屉。 | timeline summary 和 manifest 已存在，前端已有摘要与筛选，但逐帧详情主要靠下载/底层数据。 | 增加帧详情抽屉，展示 frame index、timestamp、score、duplicate、ROI hit、candidate count 和跳转预览。 |
| F-04 | P1 | ROI/bbox 编辑还不够成熟。 | `RoiCanvas` 可画矩形和回写候选，但缺角点 handle、边线拖拽、键盘微调、撤销/重做。 | 补 handle 编辑、微调、before/after 对比和复核事件可视化。 |
| F-05 | P1 | 导出证据包 schema 没有前端解释层。 | evidence bundle 可导出，但评审需要理解 JSON/CSV/DICOM/manifest 字段。 | 前端新增“证据包说明/字段说明”面板，或链接到 `docs/export_schema_v1.md`。 |
| F-06 | P1 | 视频库还不能直接服务训练闭环。 | `DataLibraryPage.vue` 有列表、预览、导入；缺批量筛选、训练 manifest 导出和质量标记。 | 增加搜索、分页、批量导入、荧光/非荧光筛选、训练 manifest 导出。 |
| F-07 | P2 | 失败态截图集仍不完整。 | E2E 覆盖了上传和分析失败主路径；缺 409/429、导出失败、403/404 文件预览、长任务超时截图。 | 补 Playwright 场景和演示截图目录，作为答辩证据。 |
| F-08 | P2 | 缺固定演示录屏。 | 已有 smoke/E2E 证据，但没有稳定 3 分钟演示视频。 | 录制“4K MP4 上传 -> 关键帧分析 -> 荧光融合证据 -> ROI 复核 -> 导出证据包”流程。 |

已修复、不再作为当前前端缺口的事项：

- 荧光融合 V2 元数据和 colorbar 已在主分析工作台展示。
- `upload_content_unreadable` 和 HTTP `422` 已有中文文案和单测覆盖。

### 31.3 模型和训练剩余缺口

| 编号 | 优先级 | 缺口 | 当前证据 | 建议动作 |
|---|---:|---|---|---|
| M-01 | P0 | 目标域病灶模型仍不存在。 | 当前可用模型是 D025 CBCT ROI 代理、2D hotspot 规则和 fixture；没有真实术中 ICG 颌骨骨髓炎训练模型。 | 报告中继续称“代理模型/工程闭环”；不要承诺目标域临床性能。 |
| M-02 | P0 | D025/ConvNeXt-style 代理模型效果低。 | 完整 val split 53 个 ROI，最佳阈值 0.60，Mean Dice `0.1363`，Mean IoU `0.0787`，Mean HD95 `71.0074`。 | 继续训练更合理的 3D backbone、损失函数和采样；增加患者级拆分、阈值曲线、失败样本分析。 |
| M-03 | P0 | MP4/JPEG keyframe 没有训练型分割模型。 | `fluorescence_hotspot_2d_segmenter` 是阈值/连通域规则。 | 用公开/代理视频帧建立弱标注或伪标注数据集，先训练 2D lightweight U-Net/SegFormer/ConvNeXt-UNet baseline。 |
| M-04 | P1 | nnU-Net 配置存在但不可运行。 | `model_inventory` 显示 `nnunet_v2_osteo_baseline` 缺 adapter inference 和 checkpoint。 | 把 D024/D025/D036 派生数据转 nnU-Net 标准格式，先完成最小训练/推理闭环。 |
| M-05 | P1 | MedSAM-like 仍未落地。 | `medsam2_osteo_promptable` 缺 checkpoint 和 adapter inference。 | 若采用 MedSAM，先做 2D keyframe bbox/point prompt：前端 ROI -> adapter -> mask -> 回写候选。 |
| M-06 | P1 | BiomedCLIP 不应作为短期主线。 | `biomedclip_osteo_screening` 缺 `open_clip`、checkpoint 和 adapter inference。 | 降级为图像级检索/筛查候选；短期不放进主线 demo。 |
| M-07 | P1 | 不确定性和校准尚未完成。 | 当前有阈值 sweep 和失败预览，但没有 calibration curve、uncertainty map、test-time augmentation 或人工复核优先级排序。 | 输出校准曲线、不确定性热图和“需医生复核”优先级。 |
| M-08 | P1 | 模型对比和消融不足。 | 已有 D025 单模型正式评估，缺 nnU-Net/MedNeXt/ConvNeXt-UNet/MedSAM prompt 对比。 | 至少补 2-3 个可运行 baseline 的同一 split 对比。 |
| M-09 | P2 | 外部模型快照不完整。 | readiness 显示 EGNet 缺 `CRA.py`、`Fusion.py`、`Transformer.py` 等；FRS Loss 缺 `models.py`、`loss_function.py`、`FRS.py`。 | 补完整源码和 license 前，只作为文献参考。 |

### 31.4 数据、文档和治理剩余缺口

| 编号 | 优先级 | 缺口 | 当前证据 | 建议动作 |
|---|---:|---|---|---|
| G-01 | P0 | 当前工作区没有冻结版本。 | `git diff --stat` 显示 71 个 tracked 文件改动，另有大量 untracked 新文件。 | 按“后端平台、前端工作台、模型/数据、报告/文献”拆分 review 和提交。 |
| G-02 | P0 | Spec checklist 未同步当前实现。 | `specs/001-software-platform-target/checklists/` 存在，但需要对照当前实现逐项打勾。 | 更新 checklist，把未完成项转为明确任务。 |
| G-03 | P1 | README/quickstart 可能滞后。 | 当前已新增 4K MP4、视频库、job、colorbar、edge smoke、D025 评估等能力。 | 同步 `README.md`、`README_CN.md` 和 docs 快速启动。 |
| G-04 | P1 | export schema 缺独立文档。 | export summary 有 schema_version，但缺字段级说明。 | 新建 `docs/export_schema_v1.md`，说明 JSON/CSV/DICOM SC/bundle manifest 字段。 |
| G-05 | P1 | 视频数据 manifest 需要继续审计。 | 已有 `video_library_manifest_20260704.csv` 等清单，但训练前仍需校验可用性、授权、荧光/非荧光、场景标签。 | 只使用已校验本地文件训练/演示；保留原始链接、下载时间、哈希和非目标域标记。 |
| G-06 | P2 | 文献清单需要与本地 PDF 资产继续对齐。 | readiness 显示 `paper_inventory.csv` 60 行、`dataset_inventory.csv` 45 行；本地 PDF 路径统计为 present=0 missing=0，说明当前清单没有用 local PDF path 字段驱动检查。 | 后续将本地 PDF 与论文清单建立 `local_pdf_path` 或单独 manifest。 |
| G-07 | P2 | Git 换行提示很多。 | `git diff --check` 无 whitespace error，但大量文件提示 LF 将被替换为 CRLF。 | 若要减少噪声，统一 `.gitattributes`；提交前避免大规模无意义换行变更。 |

### 31.5 下一步建议顺序

1. 先冻结当前可运行版本：同步 README/README_CN、Spec checklist、export schema，按主题拆分提交。
2. 然后补长视频和上传鲁棒性：multipart/resumable、1-10 分钟代理 MP4、旋转 metadata、异常 codec、高码率/大文件。
3. 再补模型主线：D025/ConvNeXt-style 代理模型继续训练，同时做 2D MP4/JPEG keyframe 训练 baseline。
4. 接着补前端审阅深度：frame detail 抽屉、ROI handle 编辑、证据包字段解释、完整失败态截图。
5. 最后推进正式版能力：DICOM SR/SEG、远程权限、正式队列、协作审计和脱敏策略。

## 32. 2026-07-04 本轮缺口修复记录：README、Spec checklist 和导出 Schema 冻结

本轮补第 31 节中的 G-02/G-03/G-04：当前平台已经能跑通 JPEG/MP4 上传、荧光融合、关键帧分析、医生复核、DICOM Secondary Capture 和 evidence bundle 导出，但 README、快速开始、Spec checklist 和导出字段说明此前没有同步到这一状态。现在已把当前可运行闭环、模型边界、验证命令和导出结构写入项目文档。

已完成：

- 新增 `docs/export_schema_v1.md`：
  - 定义 `ExportResponse`、`ExportSummary`、`ArtifactEntry`、bundle manifest、JSON report、quantification CSV 和 DICOM Secondary Capture 边界。
  - 明确当前 DICOM 只是 Secondary Capture，不是 DICOM SR/SEG。
  - 明确 evidence bundle 只能作为科研、比赛和受控演示证据，不能作为临床诊断报告。
- 更新 `README.md`：
  - 新增“当前可运行闭环”，说明病例创建、JPEG/MP4 上传、白光/ICG 融合、关键帧 hotspot、复核展示和 evidence bundle 导出。
  - 新增“当前模型状态”，区分可运行的 D025/ConvNeXt-style 代理模型、2D hotspot baseline、fixture，以及尚不可用的 nnU-Net、MedSAM-like、BiomedCLIP。
  - 新增当前闭环验证命令，包括 ruff、mypy、pytest、前端 typecheck/test/build/E2E、platform smoke、official 4K smoke、MP4 edge smoke、model inventory 和 readiness。
- 更新 `README_CN.md`：
  - 同步当前可运行闭环、模型边界、验证命令和关键文档入口。
  - 将基础 Python 命令改为显式 `conda run -n osteo-vision ...`。
- 更新 `docs/quickstart.md`：
  - 明确固定使用 Conda 环境 `osteo-vision`。
  - 同步当前闭环验证命令和三个 smoke 工具的覆盖范围。
  - 链接到 `docs/export_schema_v1.md`。
- 更新 `specs/001-software-platform-target/checklists/platform_requirements.md`：
  - 将 checklist 从全空状态更新为当前实现状态。
  - 42 项中 27 项已完成，15 项保留为未完成缺口。
  - 未完成项主要集中在：采集元数据细则、完整 warning taxonomy、approved method governance、候选区/ROI 生命周期规则、性能目标、导出中断恢复、无候选区报告、冲突复核规则、review-required 导出策略、可访问性、DICOM SR/SEG 和自动安全措辞检查。

验证结果：

- `git diff --check -- README.md README_CN.md docs\quickstart.md docs\export_schema_v1.md specs\001-software-platform-target\checklists\platform_requirements.md`：通过；仅有 Windows LF/CRLF 提示。
- `conda run -n osteo-vision python -m pytest backend\tests\unit\test_export_service.py backend\tests\contract\test_export_api.py -q`：通过；2 个测试。
- Checklist 统计：`done=27 open=15 total=42`。

剩余：

- 文档已经同步当前可运行闭环，但还没有冻结 Git 提交；工作区仍需按主题拆分 review 和提交。
- export schema 只是当前 V1 结构说明；下一阶段仍需补 DICOM SR/SEG roadmap、validator 计划和前端证据包字段说明面板。
- README 已列出完整验证命令，但正式交付前还应再跑一次全量门禁，并保留最新 smoke 输出路径。

## 33. 2026-07-04 本轮缺口修复记录：Smoke 资源监测依赖

本轮补第 31 节中的 B-08/G-05：此前 4K smoke 和 MP4 edge smoke 可以记录 Python heap，但因为环境缺 `psutil`，RSS/VMS 内存字段为 `null`，不利于后续对 4K 输入和长视频代理进行资源评估。现在已将 `psutil` 加入依赖并安装到固定 Conda 环境。

已完成：

- 更新 `requirements.txt`：新增 `psutil>=5.9,<8`。
- 当前环境验证：`conda run -n osteo-vision python -c "import psutil; print(psutil.__version__)"` 输出 `7.2.2`。
- 重新运行短 4K pressure smoke：
  - 命令：`conda run -n osteo-vision python tools\run_official_4k_pressure_smoke.py --frames 2 --keyframes 1`
  - 输出目录：`artifacts/platform_smoke/20260704T014547Z_4k/`
  - 汇总 JSON：`artifacts/platform_smoke/20260704T014547Z_4k/official_4k_pressure_smoke_summary.json`
  - 结论：`pass=true`
  - `memory_final.rss_mb=131.164`
  - `memory_final.vms_mb=722.664`
  - `memory_final.percent=0.4071`

剩余：

- RSS 监测已恢复，但这只是短 2 帧代理 4K smoke。正式长视频鲁棒性仍需 1-10 分钟代理 MP4、高码率、大文件、异常 codec 和旋转 metadata 验证。
- 当前 smoke 在启用 `psutil` 后不再启动 `tracemalloc`，因此该次报告的 Python heap 字段为 `null`；后续若要同时记录 RSS 和 heap，可改造工具让两类指标并行记录。

## 34. 2026-07-04 本轮缺口修复记录：MP4 逐帧详情列表

本轮补第 31 节中的 F-03：此前主分析工作台已经有 MP4 热点时间轴、Manifest 摘要和“当前帧详情”，但逐帧详情还没有以列表形式集中展示。评审想核对每个关键帧的候选数、阳性面积、ROI 命中和 Top BBox 时，仍需要反复点击时间轴或下载 manifest。现在前端已增加“逐帧详情”可展开列表，能直接查看所有已抽取关键帧的核心证据，并可点击任一帧切换主预览。

已完成：

- 更新 `frontend/src/pages/CaseWorkspacePage.vue`：
  - 新增 `hotspotFrameDetails` computed，使用 `hotspotFrameDetailsFromRun()` 从当前 analysis run 生成逐帧详情。
  - 将 `hotspotFrameDetails` 传入 `AnalysisWorkspaceCard`。
- 更新 `frontend/src/components/AnalysisWorkspaceCard.vue`：
  - 新增 `hotspotFrameDetails` prop。
  - 在 MP4 热点时间轴下方新增“逐帧详情”折叠列表。
  - 每行展示帧号、时间戳、候选数量、阳性面积、ROI 命中、Top BBox 和复核状态。
  - 点击某一行会触发 `selectHotspotFrame`，切换主预览和当前帧详情。
  - 增加桌面和移动端响应式样式，避免长文本和 BBox 撑破界面。
- 新增 `frontend/tests/AnalysisWorkspaceCardFrameDetails.test.ts`：
  - 挂载 `AnalysisWorkspaceCard`，验证逐帧详情列表展示 2 帧、候选/阳性面积/复核状态，并验证点击第二行会 emit 对应 frame key。
- 新增 `frontend/vitest.config.ts`：
  - 显式配置 Vue 插件和 `@` alias。
  - 解决直接挂载 Vue SFC 单测时 Vitest 无法解析 `@/components/...` 的问题。

验证结果：

- `npm --prefix frontend test -- --run AnalysisWorkspaceCardFrameDetails.test.ts`：通过；1 个测试。
- `npm --prefix frontend test -- --run`：通过；10 个测试文件、25 个测试。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend run build`：通过。
- `npm --prefix frontend run test:e2e`：通过；4 条 Chromium E2E。

剩余：

- 逐帧详情列表解决了 manifest 信息前端可见性，但还不是完整抽屉式深挖工具；后续仍可继续补单帧证据大图预览、候选 component 级列表、质量评分曲线和逐帧导出按钮。
- ROI/bbox 基础 handle 编辑、撤销/重做和修改前后面积对比已在第 35-36 节补齐；仍缺更细粒度边界编辑、候选 component 级精修和 mask 回写。

## 35. 2026-07-04 本轮缺口修复记录：ROI/BBox Handle 编辑和键盘微调

本轮补第 31 节中的 F-04：此前 `RoiCanvas` 可以拖拽新建矩形 ROI，也可以从候选框回填几何，但对已加载的候选 bbox 或手动 ROI 只能重新画，不能像正式复核工作台那样直接移动、拖角点/边线调整和键盘微调。现在 ROI 画布已支持基础 bbox 编辑。

已完成：

- 更新 `frontend/src/utils/roiGeometry.ts`：
  - 新增 `normalizeRect()`，将矩形保持在 0-1 归一化画布范围内。
  - 新增 `translateRect()`，用于移动 ROI 并保持宽高不越界。
  - 新增 `resizeRectFromHandle()`，用于角点和边线拖拽缩放。
  - 新增 `RoiResizeHandle` 类型。
- 更新 `frontend/src/components/RoiCanvas.vue`：
  - draft ROI 矩形本体支持拖拽移动。
  - 新增 4 个角点 handle：`nw`、`ne`、`sw`、`se`。
  - 新增 4 个边线 handle：`n`、`s`、`e`、`w`。
  - 外层画布增加键盘微调：方向键每次移动 `0.005`，`Shift + 方向键` 每次移动 `0.02`。
  - 状态文案更新为“可拖拽移动、拖动角点或边线调整大小、方向键微调”。
  - 画布增加 `role=application` 和键盘编辑说明。
- 更新 `frontend/tests/RoiGeometry.test.ts`：
  - 覆盖移动和缩放后保持 ROI 在归一化边界内。
- 新增 `frontend/tests/RoiCanvasEditing.test.ts`：
  - 覆盖从候选 bbox 加载 draft ROI、方向键微调、保存后输出更新 geometry。

验证结果：

- `npm --prefix frontend test -- --run RoiGeometry.test.ts RoiCanvasEditing.test.ts`：通过；2 个测试文件、4 个测试。
- `npm --prefix frontend test -- --run`：通过；11 个测试文件、27 个测试。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend run build`：通过。
- `npm --prefix frontend run test:e2e`：通过；4 条 Chromium E2E。

剩余：

- 当前已经支持移动、角点/边线拖拽和键盘微调；撤销/重做和修改前后对比在第 36 节补齐。仍缺候选框多选编辑和 component 级精修。
- 当前 ROI 仍是矩形；若后续要接近真实术中边界，还需支持 polygon/freehand 或从 MedSAM prompt mask 回写。

## 36. 2026-07-04 本轮缺口修复记录：ROI 撤销/重做和修改前后对比

本轮继续补第 31 节中的 F-04：第 35 节已实现 ROI/bbox 的移动、角点/边线拖拽和键盘微调，但医生复核场景还需要可回退的编辑体验，以及能看出“候选原始框”和“当前修改框”的差异。现在 ROI 画布已增加本地编辑历史和原始框对比。

已完成：

- 更新 `frontend/src/components/RoiCanvas.vue`：
  - 新增本地 `undoStack` 和 `redoStack`。
  - 新建 ROI、移动、缩放、键盘微调、清除 draft 前都会记录上一版矩形。
  - 工具栏新增“撤销”和“重做”按钮。
  - 从候选 bbox 或外部 draft geometry 载入时保存 `originalRect`，并重置编辑历史。
  - 当当前 draft 与原始 bbox 不一致时，在画布上显示原始蓝色虚线框。
  - 左下角显示修改前后面积对比，例如“原始 10.5% -> 当前 10.5% (+0.0%)”。
  - 保存事件仍沿用原有 `save` payload，不改变后端契约。
- 更新 `frontend/tests/RoiCanvasEditing.test.ts`：
  - 覆盖从候选 bbox 加载、键盘微调、显示“原始/当前”对比、撤销、重做和保存 geometry。

验证结果：

- `npm --prefix frontend test -- --run RoiGeometry.test.ts RoiCanvasEditing.test.ts`：通过；2 个测试文件、4 个测试。
- `npm --prefix frontend test -- --run`：通过；11 个测试文件、27 个测试。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend run build`：通过。
- `npm --prefix frontend run test:e2e`：通过；4 条 Chromium E2E。

剩余：

- 当前撤销/重做只管理画布本地 draft，不是跨页面或跨后端保存后的审计级版本管理；保存后的审计仍依赖 `review_events`。
- 当前前后对比只展示面积变化和原始框轮廓；后续可增加坐标变化、IoU、修改前后截图和事件时间线。
- 当前 ROI 仍是矩形；polygon/freehand 和 MedSAM prompt mask 回写仍未完成。
