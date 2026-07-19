# osteo-vision

颌骨骨髓炎术中荧光辅助决策研发验证版平台。当前工程版本为 `0.3.0-rc.2`。

平台接收显微镜设备导出的 JPEG 图像、MP4 视频及可选标准化元数据，完成荧光处理、AI 候选区提示、医生复核、三维参考和证据导出。企业设备驱动、私有 SDK 与采集接口由设备方负责，平台保持文件与 manifest 解耦。

所有输出均需医生复核，不构成临床诊断、自动确诊、切除范围结论或真实术中导航结论。ICG 主要反映灌注、血管通透性和组织活性差异，缺少颌骨骨髓炎特异性。

## 赛题范围

项目按官方赛题三项核心要求组织：

1. 新型荧光造影剂设计及验证方案。
2. 白光与荧光多模态图像配准、融合、增强和定量。
3. AI 辅助病灶候选区、风险、不确定性和医生复核判读。

官方软件输入边界为 `3840x2160`、JPEG、MP4、USB3.0 文件存储。完整赛题原文和设备技术文档为本地资料，不进入 Git。DICOM、远程协作和三维参考属于平台扩展能力。

## 当前可运行闭环

1. 执行医院批次准入、授权与脱敏确认、SHA256、重复和解码检查。
2. 创建病例并录入受限临床上下文。
3. 上传 JPEG 白光/荧光/设备叠加图，或导入 MP4 视频。
4. 对双通道图像执行配准、伪彩、融合、背景扣除、质量检查和 ROI 定量。
5. 对 MP4 执行播放同步关键帧分析，或通过视频流入口连续提交帧进行串行推理。
6. 输出 `fluorescence_signal_mask`、`risk_mask`、`uncertain_mask`、候选区、叠加图和性能元数据。
7. 医生在复核与人工标注页面保存、修改、提交和复核像素级标注。
8. 导出 JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP 病例证据包。
9. 在独立三维工作台导入 CBCT/STL，执行 L1 静态配准和 L2 离线位姿回放安全门控。

## 三项持续目标

| 目标 | 当前软件状态 | 安全状态 |
|---|---|---|
| 患者条件分割 | 年龄、性别、基础病、用药和血液指标已有契约、持久化、界面、代理模型与差异证据 | KiTS23 非目标域代理未通过 no-harm 门，严格运行保持影像基线结果 |
| 骨活性分层 | 已有骨面门控、低活性、过渡区、高活性、无法判断区、连续评分和医生回灌链路 | D074 非目标域代理未通过工程效用门，空间候选默认关闭 |
| 三维配准与离线 AR | CBCT/STL、倍率、工作距离、标定、坐标变换、L1/L2 任务和证据可运行 | 来源、坐标、误差、同步或复核门失败时固定降级为 `L0/unregistered_3d_reference` |

固定目标与验收门见：

- `research/reports/planning/three_priority_capabilities_target_20260717_zh.md`
- `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`

## 当前模型与数据边界

比赛严格主线为 `keyframe_residual_attention_unet_s20260715_20260715`，支持 4K `512` 像素 tile、`64` 像素 overlap，以及 960 长边实时帧低延迟输出。代理测试 Dice `0.9177`、IoU `0.8483` 只用于非目标域工程比较。

项目现有公开、代理和近似数据清单覆盖 15 份 manifest、47 条记录、138 个本地文件，总计约 5.51 GB。目标域病例和训练准入记录均为 0。真实颌骨骨髓炎白光/ICG 联合病例、医生像素级金标准、真实设备全范围标定和下颌仿体物理精度仍待外部数据与实验解锁。

## 工程结构

```text
osteo-vision/
├── backend/                 FastAPI API、病例、复核、导出和三维服务
├── frontend/                Vue 3 + TypeScript 桌面工作站
├── src/                     推理、模型、数据、指标和导航核心库
├── configs/                 任务、研发运行和比赛严格运行配置
├── scripts/                 训练、评估、实验和启动脚本
├── tools/                   准入、核验、性能和证据生成工具
├── tests/                   核心 unit、smoke 与 integration 测试
├── backend/tests/           API contract、后端 unit 与 integration 测试
├── docs/                    当前工程文档
├── research/                文献、数据来源、建模证据和历史归档
├── artifacts/               本地运行产物，默认不进入 Git
├── app/                     Gradio 兼容性入口
└── start_platform.cmd       根目录唯一用户启动入口
```

完整目录所有权见 `docs/project_structure.md`。历史报告按日期保留，当前状态以根目录 README、`docs/` 当前文档、严格配置和最新 release 快照为准。

## 快速启动

环境固定为 Python 3.11、Conda 和 Node.js：

```powershell
conda env create -f environment.yml
conda activate osteo-vision
npm --prefix frontend install
start_platform.cmd
```

启动脚本默认执行严格运行预检、checkpoint 与 SHA256 sidecar 检查、FFmpeg/ffprobe 检查、后端 readiness、OpenAPI 路由检查和模型预热。默认地址：

- 后端：`http://127.0.0.1:8001`
- 前端：`http://127.0.0.1:5174/`

详细身份、离线签名和手动启动步骤见 `docs/quickstart.md`。

## 质量门

```powershell
conda run -n osteo-vision python -m ruff check src backend tests scripts tools
conda run -n osteo-vision python -m mypy src backend --hide-error-context --no-error-summary
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python -m pytest backend/tests
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
conda run -n osteo-vision python tools/check_runtime_readiness.py --config configs/inference/osteo_vision_competition_strict.yml --require-strict
conda run -n osteo-vision python tools/check_project_readiness.py
conda run -n osteo-vision python tools/audit_active_documentation.py
```

性能基准：

```powershell
conda run -n osteo-vision python tools/benchmark_core_hotpaths.py --repeats 3 --output artifacts/performance/core_hotpaths_current.json
```

基准记录连通域统计、4K 质量评估和位姿最近邻查询的优化前后耗时与输出一致性。结果属于本机工程性能证据。

## 文档入口

- 快速开始：`docs/quickstart.md`
- 项目状态：`docs/project_summary.md`
- 目录所有权：`docs/project_structure.md`
- 工程架构：`docs/development_framework.md`
- 导出契约：`docs/export_schema_v1.md`
- 模型晋级离线签名：`docs/promotion_approval_offline.md`
- 研究资料索引：`research/README.md`
- 版本记录：`CHANGELOG.md`
- 当前工程快照：`research/reports/release/`
- 当前参赛材料入口：`research/reports/submission/`

## 数据治理

- 真实患者资料默认脱敏并最小保留。
- 医院数据需先完成批次准入，隔离文件不能进入病例分析或训练清单。
- 原始影像、视频、权重、数据库、密钥、三维模型和大体积派生数据保持仓库外或 Git 忽略状态。
- 仅可信医生独立复核完成的标注可进入高权重训练准入评估。
- 所有代理数据、公开异域数据和伪标注均保留来源、许可、SHA256 与用途边界。
