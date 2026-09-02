<p align="center">
  <img src="frontend/public/showcase/d083_frame_05_overlay.png" alt="OSTEO VISION 荧光候选区预览" width="180" />
</p>

<h1 align="center">OSTEO VISION</h1>

<p align="center">
  面向颌骨骨髓炎辅助判读的荧光与三维证据平台软件
</p>

<p align="center">
  <a href="#是什么">是什么</a> ·
  <a href="#为什么这样设计">为什么这样设计</a> ·
  <a href="#实现方式">实现方式</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#桌面发行">桌面发行</a> ·
  <a href="#维护本项目">维护本项目</a>
</p>

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" />
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-42B883?logo=vuedotjs&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white" />
  <img alt="PyTorch" src="https://img.shields.io/badge/AI-PyTorch-EE4C2C?logo=pytorch&logoColor=white" />
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-1F6FEB" />
</p>

> [!IMPORTANT]
> 平台输出用于研发验证和医生复核。结果不能作为临床诊断、自动确诊或手术边界结论。ICG 信号主要反映灌注、血管通透性和组织活性差异，目标域性能与真实设备精度需要独立验证。

## 是什么

OSTEO VISION 是一个可离线运行的医学影像平台软件，面向颌骨骨髓炎相关的荧光辅助判读、病例证据整理和三维参考验证。平台把文件准入、病例管理、图像处理、AI 候选提示、医生复核、人工标注和证据导出放在同一条可追溯流程中。

平台的使用对象包括研发人员、数据管理员、算法工程师和参与复核的医生。当前软件以标准文件和离线 manifest 为输入边界，适配设备导出的 JPEG、MP4、医院 AVI 受控转码文件，以及 CBCT、STL 等三维参考数据。设备驱动、采集卡和厂商私有 SDK 保持在部署侧，软件通过文件、元数据和版本化契约接入。

| 输入 | 平台处理 | 可复核输出 |
|---|---|---|
| JPEG 白光/荧光/设备叠加图 | 质量检查、配准、伪彩、融合、背景扣除、ROI 定量 | 原图、融合图、伪彩、质量指标和处理参数 |
| MP4 单路、独立双路或三视图视频 | 解码探测、播放同步、关键帧分析、视频流连续帧推理 | 帧级 mask、风险图、不确定性图、时间戳和视频 manifest |
| CBCT、STL、离线标定与位姿 manifest | 体数据读取、表面建模、坐标检查、L1 静态配准、L2 离线回放 | 三维场景快照、坐标与误差证据、降级原因 |
| 医院或研发批次文件 | 授权、脱敏、签名、SHA256、重复项和可解码性校验 | admitted / quarantined 状态、原因码和批次记录 |

软件输出定位为术中参考信号、风险提示、工程验证结果和医生复核材料。ICG 反映的信号受灌注、曝光、组织状态和设备配置影响，平台保留不确定性、回退状态和来源信息，便于复核人员判断结果是否可用。

## 为什么这样设计

平台的结构围绕可迁移、可测试和可追溯三个目标展开。每个设计决策都对应一个可观察的工程约束：

| 工程约束 | 设计决策 | 可观察的收益 |
|---|---|---|
| 设备型号、驱动和采集接口存在差异 | 以 JPEG、MP4、受控 AVI 和标准化 manifest 作为输入契约 | 更换设备时只需调整导出或转码适配，核心服务保持稳定 |
| 医学数据需要来源和处理链证据 | 批次准入、病例状态、模型清单、参数和 SHA256 全程记录 | 每个结果都能追溯到输入、版本、配置和处理时间 |
| AI 能力可能因显卡、驱动或权重状态变化 | 运行时预检、CUDA 优先、CPU 自动降级和明确原因码 | 无兼容 GPU 时仍可完成基础演示与复核流程 |
| 三维渲染依赖 WebGL 和较大的前端资源 | 三维运行时独立构建、独立端口和独立进程 | 三维故障不会阻断二维证据和医生复核路径 |
| 4K 视频单帧计算容易造成内存和延迟压力 | 可配置 tiling、重叠拼接、关键帧缓存和串行实时请求 | 在固定输入下控制峰值资源，减少请求堆积和结果跳帧 |
| 研发模型不能直接代表目标域性能 | ModelSpec、checkpoint manifest、阈值记录和晋级门控 | 代理数据、目标域数据和待验证模型保持清晰边界 |
| 离线电脑缺少开发环境 | Electron 宿主、PyInstaller 后端、前端静态资源、FFmpeg 和示例数据一起分发 | 复制完整目录即可启动，发行包可在无 Conda 电脑上校验 |

这种设计让“能启动”与“结果可信”分开验证：启动、输入、分析、复核、导出和退出各自有状态和测试入口；任一环节缺少必要证据时，平台保留安全降级状态并显示具体原因。

## 实现方式

### 数据流

~~~mermaid
flowchart LR
    A[JPEG / MP4 / 受控 AVI] --> B[批次准入]
    B --> C[病例与输入契约]
    C --> D[解码与质量检查]
    D --> E[配准 / 伪彩 / 融合 / ROI]
    E --> F[AI 候选 / 风险 / 不确定性]
    F --> G[人工标注与医生复核]
    G --> H[JSON / CSV / Markdown / DICOM / ZIP]
    C --> I[CBCT / STL / 标定数据]
    I --> J[独立三维运行时]
    J --> G
~~~

### 分层架构

| 层 | 主要目录 | 责任 |
|---|---|---|
| 桌面宿主层 | packaging/desktop/ | 创建应用窗口、管理本地资源、启动后端和三维运行时、处理退出与进程树清理 |
| 前端工作站 | frontend/src/ | Vue 页面、交互状态、视频预览、复核与导出操作；通过 API 客户端访问服务 |
| 独立三维运行时 | frontend/three-d-runtime/ | Three.js 场景、模型载入、视角控制和运行时 manifest；单独构建与测试 |
| API 与应用服务 | backend/osteo_vision_api/ | FastAPI 路由、病例持久化、分析任务、准入、复核、导出和三维任务 |
| 核心算法库 | osteo_vision_core/ | 输入输出契约、预处理、模型 adapter、推理管线、指标、数据和导航工具 |
| 配置与清单 | configs/ | 推理档位、任务包、模型、路径、安全策略和数据来源清单 |
| 工程工具 | scripts/、tools/ | 启动、训练、评估、打包、准入、性能基准、清理和文档审计 |
| 质量与证据 | tests/、backend/tests/、frontend/tests/、frontend/e2e/ | 单元、契约、集成、smoke、前端组件、桌面真实工作流和三维运行时测试 |

### 关键运行机制

1. 前端只通过后端 API 和版本化场景数据契约访问业务状态，路由层不承载模型算法。
2. 应用服务把解码、融合、实时帧、病例、复核、导出和三维任务拆成可测试的业务边界。
3. SQLite 病例和任务存储使用受控写入目录，分析结果带有来源、时间戳、处理分辨率、配置和模型信息。
4. ModelSpec 描述模型输入语义、任务类型、checkpoint、设备策略、运行许可和医学声明；运行时不依赖散落在页面中的模型假设。
5. 三维运行时只接收最小场景快照。WebGL 不可用、资源载入失败或坐标证据不足时，主平台回到二维证据和 L0 未配准参考。
6. 桌面宿主统一负责后端与三维进程生命周期，主窗口关闭、启动失败或异常退出时清理受控进程并写入日志。

## 平台能力

| 工作区 | 已实现能力 | 安全边界 |
|---|---|---|
| 数据准入 | 机构授权、脱敏确认、文件签名、SHA256、重复项、可解码性和隔离原因码 | 仅 admitted 文件可以写入病例输入 |
| 病例档案 | 病例建立、输入关联、受限临床上下文、分析历史和状态查看 | 示例身份与真实患者资料分离，敏感字段按最小必要原则保存 |
| 病例工作台 | JPEG 双通道融合；单路、独立双路和三视图 MP4；浏览器视频流连续帧串行推理 | 结果携带来源、时间戳、处理分辨率和刷新类型 |
| AI 辅助判读 | fluorescence_signal_mask、risk_mask、uncertain_mask、候选区与性能元数据 | 代理指标用于工程比较，不能替代目标域验证 |
| 人工标注与医生复核 | 画笔、橡皮擦、多边形、撤销/重做、版本历史、提交、复核和训练准入状态 | 未复核标注保持受控训练权重 |
| 三维参考 | CBCT/STL、对象树、表面建模检查、L1 静态配准、L2 离线位姿回放 | 坐标、误差、同步或复核证据缺失时降级为 L0 未配准参考 |
| 结果导出 | JSON、Markdown、CSV、DICOM Secondary Capture 和 ZIP 证据包 | 导出保留输入、模型、参数、警告和复核记录 |

## 典型工作流

下面的顺序适用于研发验证和受控部署：

1. 在数据准入工作区登记机构授权、用途范围、脱敏状态和文件来源。
2. 对每个文件执行签名、SHA256、可解码性、重复项和通道关系检查；失败文件进入隔离状态并保留原因码。
3. 创建病例，录入最小必要的年龄、性别、基础病、用药和血液指标等受限上下文。
4. 在病例工作台导入 JPEG 或 MP4。双通道输入先完成通道角色、共同有效区间和同步预览，再执行融合分析。
5. 播放 MP4 时可使用关键帧同步分析；视频流入口按上一帧完成后处理当前帧的方式串行提交，界面显示当前时间戳和刷新状态。
6. 检查原始图、融合图、伪彩、候选区、风险图、不确定性图和处理元数据。
7. 从病例输入或模型候选区进入人工标注工作台，保存草稿、修改版本并提交医生复核。
8. 在三维工作台载入随包的 MHA 或 STL 示例，检查方向、包围盒、对象树和标准视角；配准证据不足时保留 L0 状态。
9. 导出结构化报告和病例证据包，核对输入、模型、配置、警告、复核记录和文件哈希。

## 快速开始

### 环境要求

- Windows 10/11 x64
- Conda 与 Python 3.11
- Node.js 与 npm
- FFmpeg 与 ffprobe
- 开发阶段建议使用可运行 PyTorch 的 NVIDIA CUDA 环境；无兼容 GPU 时会自动使用 CPU

### 安装与启动

~~~powershell
conda env create -f environment.yml
conda activate osteo-vision
npm --prefix frontend install
npm --prefix frontend/three-d-runtime ci
.\start_platform.cmd
~~~

根目录启动器会依次检查严格运行配置、模型清单与 SHA256 sidecar、FFmpeg、病例写入目录、后端就绪接口、实时模型预热和前端服务，并准备标准示例病例。

开发工作站的默认地址如下：

| 服务 | 地址 | 用途 |
|---|---|---|
| 后端 API | http://127.0.0.1:8001 | 病例、分析、复核、导出和三维任务 |
| 前端工作站 | http://127.0.0.1:5174/ | 开发调试和浏览器自动化 |
| 独立三维运行时 | http://127.0.0.1:5175/ | Three.js 模型与场景渲染 |

仅运行二维平台时，可执行 .\start_platform.cmd -SkipThreeDRuntime。需要无浏览器启动时，可追加 -NoBrowser；后台运行可同时追加 -Headless。Gradio 入口 app/main.py 保留用于框架兼容性检查，平台工作流使用 FastAPI、Vue 和桌面宿主。

### 常用配置覆盖

| 变量 | 作用 |
|---|---|
| OSTEO_BACKEND_PORT | 后端监听端口 |
| OSTEO_FRONTEND_PORT | 前端开发服务端口 |
| OSTEO_THREE_D_RUNTIME_PORT | 独立三维运行时端口 |
| VITE_OSTEO_API_URL | 前端访问后端的地址 |
| VITE_OSTEO_THREE_D_RUNTIME_URL | 前端访问三维运行时的地址 |
| VITE_OSTEO_DEFAULT_CASE_ID | 启动后默认打开的病例 |
| OSTEO_REVIEW_IDENTITIES_JSON | 受控部署的复核身份映射 |
| OSTEO_ACCELERATOR_POLICY | auto、gpu、cpu 或 multi_gpu 设备策略 |

三个本地服务必须使用不同端口。身份令牌、真实身份映射和本机路径覆盖只保存在部署环境或 Git 忽略文件中。

## 运行模式与加速策略

| 模式 | 入口 | 适用场景 |
|---|---|---|
| 开发工作站 | .\start_platform.cmd | 修改前后端、运行组件测试和浏览器调试 |
| 严格运行 | .\start_platform.cmd -StrictRuntime | 使用已核验配置、模型和受控示例完成平台流程 |
| 桌面应用 | npm run desktop:package 后双击 exe | 无开发环境电脑上的本地应用窗口 |
| 完整离线目录 | npm run offline-release:package | 复制、刻录或归档完整运行目录 |

加速器采用“预检后选择”的策略：

1. auto 模式探测 PyTorch、CUDA 可用性、设备数量和设备名称。
2. GPU 与运行时条件满足时使用 CUDA；实时任务复用已加载模型并限制在途请求数量。
3. torch 不可用、CUDA 不可用、设备缺失或探测异常时切换到 CPU，并记录 fallback_reason。
4. 可以通过 OSTEO_ACCELERATOR_POLICY=cpu 强制复现 CPU 路径，也可以使用 gpu 检查 GPU 依赖。
5. 运行状态、配置和导出证据保留 selected_device、GPU 名称、CUDA 版本、模型版本和降级原因。

CPU 降级保证基础输入、处理、复核和导出流程保持可用。性能对比需在相同输入、模型、分辨率、线程和运行次数下记录，不能把不同设备上的单次耗时当成模型性能结论。

## 桌面发行

桌面宿主位于 packaging/desktop/，将前端静态资源、PyInstaller 后端、独立三维运行时、模型、配置、FFmpeg 和示例数据装入一个本地应用目录。统一打包命令如下：

~~~powershell
npm run desktop:package
~~~

生成的唯一用户启动入口为：

~~~text
artifacts/release/desktop/Osteo Vision Platform-win32-x64/Osteo Vision Platform.exe
~~~

发行目录必须整体复制。仅复制 exe 会缺少 resources、locales、模型或运行时文件。主窗口关闭时，桌面宿主停止后端进程树、关闭独立三维服务并写入退出日志。

### 完整离线目录

~~~powershell
npm run offline-release:package
~~~

默认输出目录为 artifacts/release/offline-release/Osteo-Vision-Offline-Release-win32-x64/。该目录包含：

~~~text
Osteo Vision Platform.exe
resources/
  backend/                 PyInstaller 后端运行时
  frontend/                Vue 静态资源
  three_d_runtime/         独立三维静态资源
  runtime_assets/          配置、模型、FFmpeg、示例和平台服务资源
locales/                   Electron 本地化资源
verify_release.ps1         完整性校验脚本
release-manifest.json      文件清单与 SHA256
Osteo_Vision_r28_使用说明.docx
Osteo_Vision_r28_使用说明.pdf
~~~

发行包内的示例路径均相对于 resources/runtime_assets/ 解析。复制到其他电脑前先运行 verify_release.ps1；迁移验证还应检查无开发机绝对路径、示例文件可解码、后端 /ready 可用和关闭窗口后的进程树退出。

## 随附示例

| 示例 | 用途与边界 |
|---|---|
| OFDVDNET_001.mp4 | 公开非目标域三视图荧光代理视频，用于导入、同步预览和关键帧分析 |
| mandible_d024_0001.stl | 公开下颌表面参考，用于三维对象树、表面显示和静态配准检查 |
| ToothFairy2F_001_0000.mha | 公开 CBCT 体数据参考，用于三维建模示例和输入格式验证 |

示例数据的来源、许可、SHA256 和用途边界见 frontend/public/showcase/README.md 以及发行包内的 release-manifest.json。示例不包含颌骨骨髓炎目标域标签或医生复核骨面真值，示例结果用于验证软件流程和输出完整性。

## 工程结构

~~~text
osteo-vision/
├── app/                         兼容性入口，供框架检查使用
├── backend/
│   ├── osteo_vision_api/        FastAPI 路由、领域模型、服务、持久化和导出
│   └── tests/                   后端契约、单元和集成测试
├── frontend/
│   ├── src/                     Vue 页面、组件、状态和 API 客户端
│   ├── tests/                   Vitest 组件与页面测试
│   ├── e2e/                     Playwright 桌面真实工作流
│   └── three-d-runtime/         独立 Vue/Vite/Three.js 三维运行时
├── osteo_vision_core/           推理、预处理、模型、数据、指标、I/O 和导航
├── configs/                     inference、tasks、training、data 和 security 配置
├── scripts/                     启动、训练、评估、打包、迁移和清理脚本
├── tools/                       准入、就绪、性能、证据和文档审计工具
├── tests/                       unit、smoke、integration 和 fixture
├── docs/                        当前架构、快速开始、导出和发布文档
├── research/                    来源清单、建模证据和日期化历史归档
├── packaging/                   桌面宿主与离线发行说明
├── artifacts/                   本地运行产物，默认不进入 Git
└── start_platform.cmd           Windows 根目录启动入口
~~~

目录职责和 Git 策略见 docs/project_structure.md。源码、配置和测试属于可复现边界；node_modules、frontend/dist、缓存、临时日志、大体积模型和本地病例库属于派生产物。

## 维护本项目

### 日常工作顺序

1. 进入固定 Conda 环境 osteo-vision，确认当前分支、工作区状态和目标配置。
2. 先阅读相关契约、服务、组件和已有测试，再修改最小责任范围内的源码。
3. 业务变化先更新领域模型或 API 契约，再实现服务、前端交互和导出字段。
4. 为成功、失败、降级、并发和路径边界补充测试；涉及桌面或三维时增加对应真实工作流。
5. 更新当前文档、配置说明和变更记录，确认示例路径仍指向受控数据根目录。
6. 运行质量门和就绪检查，检查 Git diff、敏感文件、绝对路径和生成产物。

### 新增功能流程

| 阶段 | 需要完成的内容 | 主要位置 |
|---|---|---|
| 需求 | 明确输入、输出、错误状态、权限、医学边界和可观测指标 | specs/、docs/ |
| 契约 | 定义 Pydantic schema、枚举、版本和向后兼容策略 | backend/osteo_vision_api/domains/、osteo_vision_core/core/ |
| 后端 | 实现路由、服务、持久化、任务状态和日志 | backend/osteo_vision_api/ |
| 前端 | 实现页面状态、加载中、失败、降级、空状态和可恢复操作 | frontend/src/ |
| 测试 | 覆盖单元、契约、组件、smoke、E2E 和桌面退出行为 | tests/、backend/tests/、frontend/tests/、frontend/e2e/ |
| 文档 | 补充 README、架构、运行命令、输入限制和排障路径 | README.md、docs/ |
| 发布 | 重新构建、校验 manifest、迁移验证并记录版本 | scripts/、packaging/、artifacts/ |

### 数据与模型变更

- 新数据必须记录来源页面、直接下载地址、许可、数据域、患者或样本数量、模态、标签、临床变量、文件大小、SHA256、下载时间、本地路径和用途边界。
- 医院文件在进入病例前必须经过批次准入；admitted 文件才可分析，quarantined 文件只保留隔离原因。
- 新模型必须提供 adapter、配置入口、checkpoint manifest、SHA256 sidecar、输入语义、设备策略、最小测试和独立评估报告。
- 主线模型更换前，在同一 manifest、分组切分、预处理、阈值和资源协议下比较 Dice、IoU、Precision、Recall、Boundary F1、校准、空 mask 率、过分割率、延迟、吞吐量和峰值显存。
- 目标域数据和医生复核金标准缺失时，模型保持研发验证状态；代理数据结果需要在报告、UI 和导出中标明来源与边界。

### 清理与归档

预览清理范围：

~~~powershell
conda run -n osteo-vision python tools/clean_workspace.py
~~~

确认后清理缓存和可重复生成的 UI 产物：

~~~powershell
conda run -n osteo-vision python tools/clean_workspace.py --apply --include-artifacts
~~~

清理前保留必要的发布 manifest、性能摘要、病例证据和模型晋级记录。原始患者资料、训练数据、checkpoint、密钥和受控病例数据库禁止使用通配符批量删除。

## 质量门

### 源码与配置

~~~powershell
conda run -n osteo-vision python -m ruff check osteo_vision_core backend app tests scripts tools
conda run -n osteo-vision python -m black --check osteo_vision_core backend app tests scripts tools --line-length=120
conda run -n osteo-vision python -m isort --check-only osteo_vision_core backend app tests scripts tools --profile black --line-length=120
conda run -n osteo-vision python -m mypy osteo_vision_core backend --hide-error-context --no-error-summary
~~~

### 自动化测试

~~~powershell
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python -m pytest tests/integration
conda run -n osteo-vision python -m pytest backend/tests
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend/three-d-runtime run typecheck
npm --prefix frontend/three-d-runtime run test
npm --prefix frontend/three-d-runtime run build
npm run desktop:test
~~~

### 运行、性能与发行

~~~powershell
conda run -n osteo-vision python tools/check_runtime_readiness.py --config configs/inference/osteo_vision_strict.yml --require-strict
conda run -n osteo-vision python tools/check_project_readiness.py
conda run -n osteo-vision python tools/audit_active_documentation.py
conda run -n osteo-vision python tools/benchmark_core_hotpaths.py --repeats 3 --output artifacts/performance/core_hotpaths_current.json
npm run desktop:real-test
npm run desktop:package
npm run offline-release:package
~~~

发布检查应在构建后再次运行 verify_release.ps1，并使用 scripts/validate_offline_release_portability.ps1 做压缩、解压、绝对路径和迁移验证。真实桌面测试需要记录截图、点击结果、错误提示、布局稳定性、/ready 响应和退出日志。

## 故障排查

| 现象 | 优先检查 | 处理方式 |
|---|---|---|
| 启动后端未就绪 | 8001 端口、严格配置、模型 sidecar、FFmpeg 和运行日志 | 关闭占用端口的进程，重新执行启动器并查看 health、ready 和退出日志 |
| 界面能打开但分析失败 | 浏览器控制台、病例输入状态、任务状态和后端错误码 | 确认输入为 admitted、路径属于受控数据根目录，并保留任务失败原因 |
| GPU 未启用 | PyTorch、驱动、CUDA 版本和 OSTEO_ACCELERATOR_POLICY | 使用 auto 允许 CPU 降级；需要复现时设置 cpu 或 gpu 并记录运行环境 |
| 三维页面空白或模型不完整 | 5175 端口、runtime-manifest.json、模型文件和 WebGL 能力 | 单独启动三维运行时，检查资源路径；失败时使用二维证据和 L0 参考 |
| 示例路径超出允许根目录 | 病例记录中的绝对路径、发行包 runtime_assets 和输入 manifest | 将示例复制到受控目录，改用包内相对路径并重新准备病例 |
| 发行包在其他电脑无法启动 | 是否只复制 exe、杀毒软件隔离、目录写权限和完整性清单 | 整体复制发行目录，运行 verify_release.ps1，选择可写目录后重试 |
| 修改前端后桌面界面未变化 | frontend/dist 是否重建、桌面包是否重新生成 | 先执行 npm --prefix frontend run build，再执行 npm run desktop:package |

故障报告至少包含版本、操作系统、GPU 状态、输入文件哈希、配置名、任务 ID、日志路径和可复现步骤；患者信息和身份令牌不得放入 Issue 或公开日志。

## 数据治理与安全边界

- 真实患者资料采用脱敏与最小保留原则，病例映射和身份令牌由部署方单独保管。
- 原始影像、视频、权重、数据库、密钥、三维模型和大体积派生数据保持在仓库外或 Git 忽略路径。
- 公开、代理和伪标注数据保留来源、许可、SHA256 与用途边界，训练缓存和预览图不重复计数。
- 只有可信医生独立复核完成的标注才进入高权重训练准入评估；工程标注和未复核草稿保持独立来源。
- 所有报告、UI 和导出均保留医生复核边界。平台不提供自动临床诊断、真实术中导航或临床结局承诺。

## 文档导航

| 主题 | 入口 |
|---|---|
| 快速启动、端口和身份配置 | [docs/quickstart.md](docs/quickstart.md) |
| 当前项目状态和缺口 | [docs/project_summary.md](docs/project_summary.md) |
| 分层架构、运行时和扩展边界 | [docs/development_framework.md](docs/development_framework.md) |
| 目录所有权和清理规则 | [docs/project_structure.md](docs/project_structure.md) |
| 导出字段与证据契约 | [docs/export_schema_v1.md](docs/export_schema_v1.md) |
| 独立三维运行时 | [docs/three_d_renderer_runtime.md](docs/three_d_renderer_runtime.md) |
| 桌面发行与迁移验证 | [docs/release/README.md](docs/release/README.md) |
| 离线发行目录说明 | [packaging/offline_release/README.md](packaging/offline_release/README.md) |
| 展示静态资产来源 | [frontend/public/showcase/README.md](frontend/public/showcase/README.md) |
| 研究资料索引 | [research/README.md](research/README.md) |
| 版本记录 | [CHANGELOG.md](CHANGELOG.md) |

## 版本与许可证

当前工程版本为 0.3.0-rc.2，严格运行配置为 configs/inference/osteo_vision_strict.yml，主线模型为 keyframe_residual_attention_unet_s20260715_20260715。版本变更、迁移影响和验证摘要记录在 CHANGELOG.md 与 research/reports/release/。

本项目按 LICENSE 中的 Apache License 2.0 条款发布。公开数据、第三方模型代码和外部资产遵循各自许可；使用前请核对来源清单和授权范围。

---

<p align="center">
  <sub>OSTEO VISION · 颌骨骨髓炎荧光辅助判读平台软件</sub>
</p>
