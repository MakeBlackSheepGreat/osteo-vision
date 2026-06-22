# 颌骨骨髓炎智能化荧光诊疗平台 — 项目进度汇报

> 汇报日期：2026年6月18日  
> 项目阶段：V1 → V2（V1 已闭环，V2 前后端分离原型已成型）  
> 版本号：0.2.0

---

## 一、项目定位（一句话）

**基于白光/ICG 双通道影像的颌骨骨髓炎术中边界风险提示与病例报告软件平台。**

面向三大赛点：荧光伪彩色增强（赛点一）、AI 辅助诊断（赛点二）、标准化输出与远程协作（赛点三）。

---

## 二、总体完成概览

| 维度 | 状态 | 关键产出 |
|------|------|---------|
| 🟢 **V1 荧光融合闭环** | ✅ 完成 | 白光+ICG → 伪彩融合图 + 热图 + 归一化图 + JSON/Markdown 报告 |
| 🟢 **V2 前后端分离原型** | ✅ 已成型 | Vue 3 前端 + FastAPI 后端 + 完整 REST API |
| 🟢 **V2 前端界面** | ✅ 有型 | 三页面（病例工作台、医生复核、报告导出），医学蓝配色 |
| 🟢 **AI 模型框架** | ✅ 就绪 | 配置驱动，4 模型注册（nnU-Net、MedSAM2、BiomedCLIP、Fixture） |
| 🟡 **AI 模型训练** | 🔄 进行中 | 10 模型基准测试完成，nnU-Net 基线 d024 1-epoch smoke 跑通 |
| 🟡 **真实样本接入** | ⏳ 待开始 | 公开 CBCT 三数据集预处理已完成 |
| 🔴 **DICOM 输出** | ⏳ 待开始 | 架构预留，需赛点三细化 |

---

## 三、各模块详细进度

### 3.1 荧光分析与图像融合（赛点一） ✅ 完成

**核心文件**：`src/preprocess/fluorescence.py`（240行）

**已实现能力**：
- 白光图像 + ICG 荧光图像双通道输入
- 自动尺寸对齐（resize to white-light）
- 荧光强度归一化（[1%, 99%] 百分位归一化）
- 伪彩映射（绿/琥珀/品红三种方案）
- Alpha 融合叠加（`overlay = (1-α)×white + α×pseudo_color`）
- 荧光定量统计：均值、最大值、P95、阳性面积、阳性面积占比
- 输出品：融合图 PNG、热图 PNG、归一化荧光 PNG、JSON 报告、Markdown 报告

**前端融合参数面板**：
- 透明度滑块（0.00–1.00）
- 荧光阈值滑块（0.00–1.00）
- 伪彩方案下拉（绿色/琥珀色/品红色）

**状态**：严格对标赛点一。所用注册方法是简单的 resize 对齐（标注为 initial demo），后续可升级为手术场景下的刚性/非刚性配准。

---

### 3.2 AI 辅助诊断框架（赛点二） 🔄 框架就绪 / 训练进行中

**模型注册表**（`configs/inference/osteo_vision.yml`）：

| 模型 ID | 家族 | 任务类型 | 说明 |
|---------|------|---------|------|
| `nnunet_v2_osteo_baseline` | nnU-Net v2 | 分割 | 颌骨骨髓炎分割基线 |
| `medsam2_osteo_promptable` | MedSAM-like | 分割 | 可提示病灶/坏死骨 ROI 分割 |
| `biomedclip_osteo_screening` | VLM 编码器 | 分类 | 图像级辅助筛查原型 |
| `fixture_default` | Fixture | 全部 | 确定性 fallback，测试和 Demo 用 |

**AI 模型训练成果**：

| 完成项 | 说明 |
|--------|------|
| D024 10 模型基准 | MONAI 框架 10 种 3D 模型在 DentVoxel jaw-roi 上完成比较（低分辨率短训练，用于可行性筛选） |
| D024 nnU-Net 1-epoch smoke | nnU-Net v2 在 D024 上跑通完整 1-epoch 训练/预测/评估链路 |
| D024 分割模型选型报告 | 中英文双语，推荐 nnU-Net v2 / MedNeXt / U-Mamba |
| 3 个公开 CBCT 数据集预处理 | D024 DentVoxel、D025 DolChID、D036 ToothFairy2，均有中英双语预处理报告 |
| 颌骨基础分割模型设计 | 架构设计报告，5-fold 验证与 HD95/NSD 指标定义完成 |

**AI 安全边界**：
- 所有模型 `clinical_claim_allowed: false`
- 输出定位为辅助提示 + 医生复核，不自动确诊
- 候选区域状态四态：`review_required` / `accepted` / `modified` / `rejected`

---

### 3.3 前端界面（Vue 3 + TypeScript） ✅ 已成型

**技术栈**：Vue 3.5 + Vite 6 + Pinia 3 + Vue Router 4 + TypeScript 5

**页面清单**：

| 页面 | 路由 | 状态 | 核心内容 |
|------|------|------|---------|
| 病例工作台 | `/case` | ✅ 完成 | 三栏布局：左侧控制面板 + 中央分析视图（三联图像+候选区+量化）+ 右侧证据面板 |
| 医生复核 | `/review` | ✅ 完成 | 两栏布局：ROI 画布 + 候选区列表/复核按钮/量化指标 |
| 报告导出 | `/report` | ✅ 完成 | 两栏布局：导出详情 + 输出边界说明 |

**已实现 UI 组件**（9 个）：
- `CaseInputPanel`、`FusionViewer`、`RoiCanvas`
- `CandidateRegionList`、`ReviewStateControls`、`QuantificationPanel`
- `QualityFlagPanel`、`ExportPanel`、`MedicalDisclaimer`

**设计语言**：
- 医学蓝主色调（`#1a5276` / `#2980b9` / `#1e6fa6`）
- 浅蓝灰底色（`#f3f6fa`），白色卡片，圆形按钮
- 清晰信息层级，临床级软件质感

---

### 3.4 后端服务（FastAPI） ✅ 已成型

**API 路由**（8 个端点）：
- `GET /health` — 健康检查
- `GET /ready` — 就绪状态
- 病例 CRUD、输入管理、分析执行、复核记录、证据包导出

**后端服务层**（5 个 service）：
- `AnalysisService` — 调用荧光融合 + AI 推理
- `InputService` — 双通道输入验证
- `ReviewService` — 医生复核状态管理
- `ExportService` — 证据包打包（ZIP）
- `RoiService` — ROI 几何与度量

**数据流**：前端 ↔ REST API ↔ Service 层 ↔ 荧光融合引擎 ↔ JSON 文件持久化

---

### 3.5 标准化输出（赛点三） 🟡 基础完成 / 待扩展

**已实现输出格式**：
- `overlay.png` — 白光/荧光融合图
- `heatmap.png` — 荧光热图
- `normalized_fluorescence.png` — 归一化荧光灰度图
- `report.json` — 结构化 JSON（含融合参数、量化指标、输出路径、免责声明）
- `report.md` — Markdown 单病例报告
- ZIP 证据包导出（含所有图和报告）

**待实现**：
- DICOM Secondary Capture（从 PNG 封装）
- DICOM Structured Report（结构化病灶描述）
- PDF 正式报告

---

### 3.6 研究文档 📚 已完成 32 份报告

**预处理报告**（6 份中英双语）：
- D024 DentVoxel 预处理报告
- D025 DolChID 预处理报告
- D036 ToothFairy2 预处理报告
- 公共 CBCT 三数据集预处理总结
- 公共 CBCT 本地训练缓存路线

**建模报告**（8 份中英双语）：
- D024 10 模型基准测试
- D024 前沿 10 模型基准
- D024 nnU-Net 1-epoch smoke
- D024 分割模型选型报告
- 颌骨基础分割模型设计
- 公开 CBCT 三数据集分割基准
- 解剖高分辨率 patch 实验

**规划文档**（8 份中英双语）：
- 平台目标说明（母稿，2778 字）
- V1 可演示闭环计划
- 最终目标与技术栈
- 软件优先平台目标
- 软件聚焦真实平台
- 软件平台目标任务

---

### 3.7 工程体系

| 维度 | 详情 |
|------|------|
| **Python 源码** | 72 个 `.py` 文件，模块化组织（core/datasets/engine/models/pipelines/preprocess/reports） |
| **后端源码** | 32 个 `.py` 文件（api/core/domains/services/reports） |
| **测试体系** | 29 个测试文件（unit + smoke + integration），`tests/fixtures/` 含 DICOM 系列和平台测试数据 |
| **代码质量** | black + isort + flake8 + mypy 配置就绪，`.pre-commit-config.yaml` 已配 |
| **配置驱动** | `configs/tasks/osteo_vision.yml`（任务契约）+ `configs/inference/osteo_vision.yml`（运行配置） |
| **前端测试** | Vitest，4 个组件测试全部通过 |
| **一键启动** | `make platform`（同时启动前后端），`make demo`（Gradio 备用入口） |

---

## 四、版本路线图

| 版本 | 目标 | 状态 |
|------|------|------|
| **V1** | Gradio/最小原型跑通双通道融合 + 报告闭环 | ✅ 已完成 |
| **V2** | 前后端分离 (Vue + FastAPI) + 完整病例工作台 | ✅ 已成型（代码就绪，虚函数对接） |
| **V3** | AI 基线接入 + 真实模型推理 | 🔄 框架就绪，训练进行中 |
| **V4** | 真实术中样本闭环 + DICOM 标准化 | ⏳ 待开始 |

---

## 五、当前阻塞与风险

| 风险项 | 等级 | 说明 |
|--------|------|------|
| 缺少真实术中白光/ICG 样本 | 🔴 高 | AI 模块只能用公开 CBCT 数据做间接验证，赛点二只能作为原型演示 |
| 缺少医生标注 | 🔴 高 | 下颌骨/坏死骨/灌注异常缺乏金标准标注，模型评估受限 |
| DICOM 输出未启动 | 🟡 中 | 赛点三的 DICOM SC/SR 扩展需要进一步调研和开发 |
| 虚函数对接 | 🟡 中 | 后端 AI 推理目前通过 Fixture 返回模拟结果，真实模型尚未上线 |

---

## 六、下周可演示内容

如明后天需要给领导看，建议聚焦以下可演示路径：

1. **启动平台**（2 分钟）
   ```bash
   make platform  # 一键启动 FastAPI + Vue
   ```
   浏览器打开 `http://127.0.0.1:5174`

2. **演示双通道融合工作流**（5 分钟）
   - 新建病例 → 输入两张测试图片路径 → 点击运行分析
   - 展示三联图像视图（融合图 / 热图 / 归一化荧光）
   - 展示候选区域列表 + 量化统计
   - 导出 ZIP 证据包

3. **展示 AI 辅助复核流程**（3 分钟）
   - 切换到医生复核页
   - ROI 画布 + 候选区 + 接受/修改/驳回操作

4. **展示研究文档体系**（5 分钟）
   - 32 份中英双语报告的完整性
   - 30+ 篇论文、11 个数据集、5 个外部模型快照的文献归档

---

## 七、核心文件索引（便于汇报现场翻阅）

| 用途 | 路径 |
|------|------|
| 项目目标母稿 | `research/reports/planning/osteo_vision_platform_target_zh.md` |
| V1 闭环计划 | `research/reports/planning/v1_demo_closure_zh.md` |
| 荧光融合引擎 | `src/preprocess/fluorescence.py` |
| 后端分析服务 | `backend/src/services/analysis_service.py` |
| 前端主页 | `frontend/src/pages/CaseWorkspacePage.vue` |
| 任务配置 | `configs/tasks/osteo_vision.yml` |
| 推理配置 | `configs/inference/osteo_vision.yml` |
| 10 模型基准报告 | `research/reports/modeling/d024_10_model_baseline_benchmark_zh.md` |
| 颌骨分割模型设计 | `research/reports/modeling/osteo_vision_foundation_segmentation_model_design_zh.md` |
