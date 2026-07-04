# 项目整理与缺口自查

日期：2026-07-03

## 1. 本轮整理结论

当前项目已经具备“官方 MP4/JPEG 输入雏形 + 前后端病例工作台 + 公开 CBCT 代理数据 + 荧光/骨髓炎公开视频资料”的基础，但核心风险没有消失：真实目标域 4K 白光/ICG 术中 MP4/JPEG、医生标注和可用于训练的颌骨骨髓炎荧光数据仍然缺失。近期开发应先把官方输入闭环、关键帧、ROI 标注和证据包做实，再用公开 CBCT 与荧光代理数据支撑模型原型。

## 2. 已具备内容

### 2.1 官方赛题输入对齐

- 已整理官方技术文档对齐说明：`research/reports/planning/official_technical_document_alignment_zh.md`。
- 工程配置已写入官方设备边界：4K `3840x2160`、JPEG 图片、MP4 视频、USB3.0 文件工作流。
- 后端已支持上传 MP4/JPEG，读取视频元数据并预抽取关键帧。
- 前端病例工作台已支持白光、荧光、MP4 文件和浏览器摄像头预览入口。

相关工程文件：

- `backend/src/api/uploads.py`
- `backend/src/services/analysis_service.py`
- `src/io/video_io.py`
- `src/preprocess/video.py`
- `frontend/src/pages/CaseWorkspacePage.vue`

### 2.2 本地数据基础

| 数据源 | 当前状态 | 本地规模 | 主要用途 |
|---|---:|---:|---|
| D024 DentVoxel | 已处理 | 100 例 manifest；derived 约 60.2 GB | 颌骨/牙齿/下颌管解剖先验。 |
| D025 DOLCHID lesion CBCT | 已处理 | 262 例 manifest；derived 约 91 MB | 牙源性病灶代理任务，当前最接近病灶训练路线。 |
| D036 ToothFairy2 | 已处理 | 480 例 manifest；derived 约 9.1 GB | 牙颌多结构分割和 nnU-Net 解剖基线。 |
| D042 MODID | 目录存在 | 0 文件 | 口腔多光谱候选，尚未落地。 |
| D044 FGS video | 目录存在 | 0 文件 | 旧候选目录，实际视频代理已转到 D046。 |
| D046 视频候选 | 已整理 | 23 个非荧光骨髓炎视频 + OFDVDnet 约 2.93 GB | MP4 输入演示、荧光代理增强、后续关键帧/ROI 管线。 |

### 2.3 文献与报告基础

- `research/literature/inventory/dataset_inventory.csv`：45 条数据集记录。
- `research/literature/inventory/paper_inventory.csv`：60 条论文记录；已把不存在的本地 PDF 路径改为 `link_only_no_local_pdf`，避免误判为已下载。
- `research/literature/inventory/local_paper_assets_20260703.csv`：当前真实可读的 5 个 PDF 和 3 个 HTML 备份清单。
- `research/literature/inventory/papers/`：当前实际存在 5 个 PDF 和 3 个 HTML 备份，主要是四环素/自发荧光/MRONJ/颌骨坏死相关资料。
- `research/reports/modeling/model_training_data_sources_zh.md`：已明确训练数据路线。
- `research/reports/modeling/fluorescence_osteomyelitis_video_dataset_search_20260703_zh.md`：已整理荧光代理与骨髓炎视频检索结论。
- `research/reports/modeling/video_download_status_20260703_zh.md`：本轮新增下载整理状态。

### 2.4 验证结果

- `conda run -n osteo-vision python check_env.py`：通过，Python 3.11.15，无 failure。
- `conda run -n osteo-vision python tools/check_project_readiness.py`：主结构通过，但提示论文 PDF 路径、EGNet/FRS 快照缺失。
- `conda run -n osteo-vision python -m pytest -q`：通过。
- `npm --prefix frontend run build`：通过。
- `npm --prefix frontend test -- --run`：4 个前端测试通过。

## 3. 当前最大缺口

### P0：真实目标域数据缺口

真实的 4K 白光/ICG 术中 MP4/JPEG 样本仍然是最大缺口。公开检索没有找到“颌骨骨髓炎 + ICG 荧光 + 可下载 MP4 + 像素级标注”的数据集；医院 CBCT 预计也只有 4-5 例，无法支撑独立临床级训练。赛点二必须定位为原型和医生复核辅助，不能承诺自动诊断。

### P0：医生标注协议尚未落地

当前已经能上传和抽关键帧，但还缺关键帧 ROI 标注、医生复核状态、病例级标签、时间戳和导出清单的稳定数据结构。没有这个闭环，后续即使拿到 MP4，也无法沉淀成可训练数据。

### P0：真实模型权重缺失

`configs/inference/osteo_vision.yml` 仍启用 fixture fallback。nnU-Net、MedSAM-like、BiomedCLIP 等模型已进入配置和适配器边界，但没有本项目可用 checkpoint。现有输出适合演示工程链路，不代表真实诊断性能。

### P1：视频代理数据还没有转成训练/演示资产

OFDVDnet `data.zip` 已下载，但尚未解压、三视图拆分、抽帧、建立 manifest，也未接入赛点一的去噪/伪彩增强实验。FGS 34 GB 主包未下载，暂时只能引用 README 和论文。

### P1：文献清单需要补下载和二次校准

`paper_inventory.csv` 的 60 条旧论文现在只保留链接，不再声称本地 PDF 已落地；项目内实际可读资料目前只有 `local_paper_assets_20260703.csv` 记录的 5 个 PDF 和 3 个 HTML。后续正式报告引用必须优先基于真实存在的 PDF/HTML，旧清单需要按优先级重新下载或剔除。

### P1：赛点三仍是雏形

当前可以导出结构化 JSON、Markdown 报告和证据文件，但 DICOM Secondary Capture、DICOM SR、远程协作/会诊仍停留在规划层。比赛方案里可以写扩展雏形，不能写成已完整实现。

### P2：外部模型快照不完整

`tools/check_project_readiness.py` 显示 EGNet 和 FRS Loss 快照关键文件缺失。若后续不再使用这些路线，应在研究归档中降级为“历史候选”；若要继续引用，需要补全代码快照或删除不实状态。

## 4. 下一步开发顺序

1. 固化 MP4/JPEG 输入闭环：上传、元数据、关键帧、预览、病例绑定、证据导出。
2. 建立 `official_video_keyframe_manifest.csv` 和医生 ROI 标注 JSON/mask 规范。
3. 解压并整理 OFDVDnet，生成 reference/fluorescence/overlay 三视图 manifest，用于赛点一。
4. 在 D025 上优先跑病灶代理模型基线；D024/D036 作为解剖先验，不把 anatomy Dice 写成骨髓炎性能。
5. 补论文：以 `local_paper_assets_20260703.csv` 为当前真实资料基线，优先补下载旧清单中仍有价值的 PDF。
6. 赛点三先完成结构化证据包，再开发 DICOM SC/SR 或远程协作雏形。

## 5. 表述边界

- ICG 是灌注、血管通透性和组织活性参考信号，不是颌骨骨髓炎特异性探针。
- 公开 CBCT 和公开视频均为代理数据，不能包装成真实术中 ICG 颌骨骨髓炎数据。
- 当前 AI 输出只能表述为候选区域、边界风险、不确定性提示和医生复核辅助。
