# 项目目录与所有权

适用版本：`0.3.0-rc.2`。本文件定义活动代码、文档、研究证据、生成产物和历史归档的边界。

## 根目录

| 路径 | 所有权 | 内容 | Git 策略 |
|---|---|---|---|
| `backend/` | 平台后端 | `osteo_vision_api/` FastAPI、领域模型、服务、报告与后端测试 | 跟踪 |
| `frontend/` | 平台前端 | Vue 桌面工作站、组件、类型与前端测试 | 源码跟踪，依赖和构建忽略 |
| `frontend/three-d-runtime/` | 独立三维渲染运行时 | 独立 Vue/Vite/Three.js 包、场景测试、锁文件和静态运行时标识 | 源码与 lockfile 跟踪，`node_modules/` 与 `dist/` 忽略 |
| `osteo_vision_core/` | 核心库 | 推理、模型、数据、指标、I/O、导航 | 跟踪 |
| `configs/` | 运行配置 | 任务、研发与严格运行配置 | 公共配置跟踪，本机覆盖忽略 |
| `scripts/` | 工程脚本 | 启动、训练、评估、实验和模型清单 | 跟踪 |
| `tools/` | 核验工具 | 准入、下载、smoke、性能、证据与清理 | 跟踪 |
| `tests/` | 核心测试 | unit、smoke、integration、fixtures | 跟踪，小型 fixture 例外 |
| `docs/` | 当前文档 | 快速开始、架构、目录、导出和审批 | 跟踪，内容保持当前 |
| `research/` | 研究证据 | 文献、来源清单、建模报告、计划和归档 | 小型证据跟踪，大文件忽略 |
| `artifacts/` | 本地运行与临时产物 | 病例运行证据、UI 验收截图、文档临时物、checkpoint、报告、数据库与性能结果 | `.gitkeep` 外默认忽略 |
| `app/` | 兼容入口 | Gradio 框架兼容性检查 | 跟踪，不作为平台主界面 |
| `packaging/` | 打包 | 桌面与发布打包说明 | 跟踪 |
| `specs/` | 规格 | Spec Kit 功能规格与任务 | 跟踪 |

## 活动文档

以下文件描述当前事实：

- `README.md`、`README_CN.md`
- `docs/quickstart.md`
- `docs/project_summary.md`
- `docs/project_structure.md`
- `docs/development_framework.md`
- `research/README.md`
- `CHANGELOG.md` 的最新版本节
- `research/reports/release/README.md`
- `research/reports/release/README.md`
- `research/reports/release/platform_evidence_manifest.yml`

活动文档禁止引用已删除目录、旧阶段编号、已归档提交包和冻结时瞬时 Git 状态。

## 历史证据

日期化研究报告、训练报告和 release 快照记录生成时事实。它们保持原日期、配置和声明边界。被替换的规划与早期可行性材料进入带日期的 `archive/` 子目录；各归档目录通过 README 说明原因与后继入口。

历史证据中的旧模型、旧指标和旧 Git 状态不能覆盖当前配置、最新 release 索引或可运行代码事实。

## 本地生成目录

以下目录可由工具重建：

- `.pytest_cache/`、`.pytest_tmp*/`、`.pytest-tmp*/`
- `.mypy_cache/`、`.ruff_cache/`、`__pycache__/`
- `.codex_tmp*`、根目录 `build/` 与 `dist/`
- `frontend/dist/`、`frontend/three-d-runtime/dist/`、`frontend/coverage/`、`frontend/test-results/`
- `artifacts/e2e/` 与 `artifacts/ui/` 中可重复生成的界面验收产物

`artifacts/tmp/` 保存文档渲染、研究整理和人工检查的中间工作物，不进入通用清理。数据集整合输出统一进入对应 `research/datasets/<dataset-id>/derived/`，并保留同级说明或 manifest。`artifacts/platform*`、`artifacts/platform_smoke/`、`artifacts/performance/`、`artifacts/reports/`、`artifacts/runs/` 和 `artifacts/visual_evidence/` 保存病例状态或研发证据，同样保持受保护状态。

本地目录的职责保持单向：`artifacts/ui/playwright/` 只放置可再现的前端或浏览器验收截图；`research/datasets/<dataset-id>/derived/` 只放置受控数据整合输出；`artifacts/tmp/` 只放置阶段性中间工作物；其余 `artifacts/` 承担可追溯运行证据。生成器需要在 manifest、日志或同级说明中给出来源、生成入口与用途边界。这样可避免把报告提交件、源码和本地运行物混放。

## 发布证据

`research/reports/release/` 保存版本快照、平台证据 manifest 和可再生成的发布索引。大体积渲染件、原始影像与运行输出继续按 `.gitignore` 规则保留在本机受控目录。

安全清理预览：

```powershell
conda run -n osteo-vision python tools/clean_workspace.py
```

执行缓存清理：

```powershell
conda run -n osteo-vision python tools/clean_workspace.py --apply
```

仅清理可重复生成的 E2E/UI 产物时显式增加 `--apply --include-artifacts`。原始数据、checkpoint、病例数据库、人工标注、smoke/性能证据、密钥、训练运行和研究数据集不会进入清理清单。活动服务器锁定的日志会保留并列入 JSON `failures`，其余候选继续清理；关闭对应进程后可再次执行。

## 新文件放置规则

- 可复用运行代码进入 `osteo_vision_core/` 或 `backend/osteo_vision_api/`。
- 独立 WebGL 场景代码、Three.js 依赖和运行时专用测试进入 `frontend/three-d-runtime/`；主平台只保留业务控制、嵌入桥接与安全降级。
- 一次执行即可复现的工程入口进入 `scripts/` 或 `tools/`。
- 当前使用说明进入 `docs/`。
- 研究结论和实验记录进入 `research/reports/<topic>/` 并带日期。
- 来源、许可和下载状态进入对应数据集目录的 `SOURCE.md`、manifest 或 receipt。
- 性能与 smoke 运行输出进入 `artifacts/`。
- 浏览器验收截图进入 `artifacts/ui/playwright/`；文档渲染与人工检查临时物进入 `artifacts/tmp/`。
- 数据集整合结果进入所属数据集的 `derived/`，不得再创建根目录 `outputs/`。
- 过期材料进入 `research/reports/archive/`，当前入口只引用 `release/`。

## 自动审计

```powershell
conda run -n osteo-vision python tools/audit_active_documentation.py
```

审计覆盖版本一致性、活动文档过期标记、本地 Markdown 链接和当前提交目录命名。
