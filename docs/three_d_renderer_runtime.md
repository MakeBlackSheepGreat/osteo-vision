# 独立三维渲染运行时架构

## 1. 目标与边界

`frontend/three-d-runtime/` 是平台的独立三维渲染运行时。它负责 WebGL 能力检测、受控 STL/GLB 资源加载、Three.js 场景渲染、候选区显示和渲染状态反馈。GLTF 可保留在病例证据中，独立运行时当前会将其置为可追溯的安全降级状态，避免外部资源依赖进入渲染进程。

主平台继续承载病例管理、文件准入、CBCT/STL 建模任务、对象树、建模检查、L1 静态配准、L2 离线动态 AR 验证、医生复核、二维证据和报告导出。三维运行时不持有病例数据库，不执行模型推理，也不改变导航安全级别。

两端通过带 `schema_version` 的病例、模型、坐标变换、复核和证据数据契约交换信息。运行时只接收渲染所需的最小字段；临床上下文、原始患者信息、私有路径和未授权文件不进入运行时场景载荷。

当前场景快照使用 `osteo-vision-three-d-runtime-snapshot-v2`。`snapshot_sha256` 对无签名载荷执行 v2 字节分帧编码：空值、布尔值、UTF-8 字符串、数组和对象都有类型与长度标记；有限数值采用 IEEE 754 双精度大端位序；对象键按 UTF-8 字节序排序。该编码消除 Python 与浏览器在科学计数法、负零和整数键枚举上的序列化差异。SHA256 用于传输完整性检查。CORS 仅提供浏览器来源约束，生产病例访问须由部署侧认证和受控网关承担。

## 2. 启动方式

默认端口：主平台前端 `5174`，独立三维运行时 `5175`，后端 `8001`。

单独启动渲染运行时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_three_d_runtime.ps1
```

启动严格平台并额外尝试启动渲染运行时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_platform.ps1 -StrictCompetition -StartThreeDRuntime
```

主平台在三维运行时目录缺失、依赖安装失败、端口冲突、Web 服务未就绪或浏览器 WebGL 不可用时保持主工作流可用。二维证据、L0/L1/L2 状态和医生复核入口继续由主平台提供。

`start_three_d_runtime.ps1 -PreflightOnly` 输出启动器检查结果，其中 `runtime_dependencies_ready` 表示独立包自身的 Vue、Three.js、Vite、Vue 插件和类型检查依赖是否齐备。正常启动会在本地依赖不完整时执行 `npm ci`；传入 `-NoInstall` 会明确失败。`-SkipBackendCheck` 仅用于本地启动器检查或前端离线测试，不可用于受控演示部署。

严格比赛模式由主平台控制病例存储、推理配置和主前端状态。独立渲染运行时保持无业务模式的受控渲染职责。

根平台启动器要求三端口两两不同；独立启动器还会拒绝与 `MainAppOrigin` 使用同一端口。端口已被占用时，`start_three_d_runtime.ps1` 会读取 `/runtime-manifest.json`，再核对 `artifacts/runtime_logs/three_d_runtime_<port>.json` 内的 API 地址和主平台 origin。配置不一致或无法核验时启动器停止复用，避免连接到错误的渲染实例。

## 3. 构建与测试

Windows/PowerShell 环境优先使用根目录 npm 入口：

```powershell
npm run three-d-runtime:install
npm run three-d-runtime:check
npm run three-d-runtime:dev
npm run three-d-runtime:preview
```

`three-d-runtime:check` 依次执行独立运行时的类型检查、组件测试和生产构建。`make` 已安装的环境可使用以下等价目标：

```powershell
make three-d-runtime-install
make three-d-runtime-typecheck
make three-d-runtime-test
make three-d-runtime-build
make three-d-runtime-preview
```

`make release-check` 和 `make release-build` 聚合主平台与独立三维运行时的发布质量门和构建。主平台既有 `make test`、`make build` 与 `npm test` 保持原有范围，日常开发可独立运行。

Playwright 桌面联调会启动后端、主平台和独立运行时三个进程，并验证 D024 公开参考的 iframe 桥接、受控资产读取、WebGL 非空画布和模型缺失降级。E2E 使用独立的最小 STL 夹具，不依赖本机忽略的公开资产文件。

## 4. 数据与安全降级

渲染场景契约至少包含以下内容：

- 版本化场景标识、病例 ID、病例版本和生成时间。
- 模型资产 ID、格式、SHA256、坐标系、模型来源、受控下载地址及 `rendering_status`。
- 候选区、可视化参数、坐标变换摘要、配准误差和 L0/L1/L2 状态。
- 医生复核状态、证据摘要、失败原因和回退模式。

模型缺失、格式不支持、完整性校验失败、WebGL 不可用、坐标变换未通过验证或复核条件缺失时，三维运行时固定显示可追溯的失败状态。GLTF 会保留为受控证据资产，快照标记 `rendering_status=unsupported_format` 并提供失败原因；运行时不下载该资源。

空间候选标记需要同时满足以下门控：

- `safety.navigation_ready=true`、`navigation_level` 为 `L1/L2` 且 `registration_status=registered`。
- `spatial_mapping.schema_version=osteo-vision-three-d-runtime-spatial-mapping-v1`，`spatial_mapping.status=verified`，并包含模型坐标系和受控变换 SHA256。
- 候选区的 `coordinate_space` 与模型坐标系一致，`spatial_mapping_status=verified`，并且 `coordinate_transform_sha256` 与场景快照一致。

任一门控缺失时，运行时保留候选区的二维联动信息，停止在模型空间绘制 marker。后端快照适配层会复核安全门版本、医生复核状态、变换验证和坐标链验证；未通过的载荷会降为 L0 参考状态。

iframe 桥接使用 `osteo-vision-three-d-runtime-bridge-v1`。主平台为每次场景请求生成 `request_id`，在新 iframe 的 `load` 事件后发送 `load_case` 或 `load_reference`，并在会话确认前定时重发；独立运行时通过 `runtime_ready` 触发一次补发，重复请求会复用已载入场景。`scene_loaded`、失败状态和候选选择回包均回显该 ID。主平台忽略旧请求的回包，防止病例或场景切换时的延迟响应覆盖当前画面。独立窗口提供日间/夜间主题开关，并在自身 origin 的 `osteo-vision-theme` 存储中持久化用户选择；嵌入模式接收主平台主题后同步保存。

## 5. 部署产物

`npm --prefix frontend/three-d-runtime run build` 生成独立静态产物。`make three-d-runtime-preview` 与 `npm run three-d-runtime:preview` 使用 `5175` 预览，保持后端默认 CORS 来源一致。运行时目录带独立 `package-lock.json`，受控安装入口使用 `npm ci`，启动器只接受该目录本地依赖完整的运行时。默认从站点根目录部署；部署到子路径时设置 `VITE_OSTEO_THREE_D_RUNTIME_BASE=/renderer/` 并以该子路径访问页面与静态资源。

公开 D024 参考资产包位于后端运行时数据目录：`$OSTEO_ARTIFACT_ROOT/three_d_runtime/references/d024/`。其中包含 `mandible_d024_0001.stl`、`mandible_d024_0001.three_d_evidence.json` 与 `mandible_d024_0001.brp_geometry_manifest.json`。`scripts/export_cbct_mandible_surface.py` 和 `scripts/export_brp_geometry_manifest.py` 默认输出至该目录；部署包需将已核验的公开参考资产写入该目录或保持参考入口安全降级。

部署时需要同时配置以下来源边界：

- 独立运行时的 `VITE_OSTEO_API_URL` 指向 FastAPI 地址。
- 独立运行时的 `VITE_OSTEO_MAIN_APP_ORIGIN` 填写嵌入它的主平台 origin。
- 主平台的 `VITE_OSTEO_THREE_D_RUNTIME_URL` 填写独立运行时完整地址。
- 后端 `OSTEO_ALLOWED_ORIGINS` 包含主平台和独立运行时的全部 origin。

`scripts/start_platform.ps1` 会在本机默认端口及自定义端口下传递上述本地 origin 并启动独立运行时；仅需二维平台时追加 `-SkipThreeDRuntime`。独立手动部署需在构建环境中显式设置对应变量。

部署后应独立验证以下路径：

1. 主平台可以在渲染运行时未部署时完成病例、二维分析、复核和导出。
2. 三维运行时可以通过版本化契约加载已授权的场景。
3. WebGL、模型加载和网络失败均产生可读原因，主平台安全状态不受影响。
4. 桌面端浏览器验收覆盖非空画布、模型加载和失败降级。
