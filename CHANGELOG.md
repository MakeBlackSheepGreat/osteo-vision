# 医学影像比赛框架变更日志

所有重要的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

- 暂无已冻结变更。

## [0.3.0-rc.1] - 2026-07-19

### 新增

- 完成官方 JPEG/MP4 主输入、三通道质量检查、4K tiling、关键帧与连续视频流分割、医生复核和证据包导出闭环。
- 完成受限患者条件分割的数据契约、临床特征向量、影像基础结果、患者条件结果、差异证据和失败回退。
- 完成骨面门控、低活性候选、过渡复核区、高活性参考、无法判断区、连续骨活性评分及医生人工标注版本链。
- 完成目标域晋级证据重算、双人独立签名、追加式审批哈希链、撤销、防重放和严格运行门控。
- 完成 CBCT/STL 三维工作台、L1 静态配准、L2 离线位姿回放、坐标契约、误差门控和 L0 失效回退。
- 完成医院数据批次准入、脱敏确认、SHA256、重复检查、隔离原因码和训练准入状态管理。
- 建立公开/代理数据来源清单、下载收据、许可与 SHA256 核验边界；原始影像、视频、模型输入、批量数据、派生数据和运行产物保持本地隔离，经许可记录的小型公开结构化临床表可作为来源元数据进入版本库。

### 变更

- 前端按数据准入、病例档案、病例工作台、三维导航、医生复核和报告导出的临床工程流程重组，并加入日间/夜间主题。
- 比赛启动入口收敛为根目录 `start_platform.cmd`，实际逻辑由 `scripts/start_platform.ps1` 承载，默认执行严格运行预检和模型预热。
- 清理过时桌面入口、模板训练器、旧 DOCX 生成器和一次性下载脚本；现行训练、验证和下载工具统一位于 `scripts/` 与 `tools/`。

### 患者安全

- 所有分割、骨活性和导航输出继续保持研发验证与医生复核边界，不提供自动确诊或疾病终判。
- 患者条件代理模型和 D074 骨活性代理模型均未获得目标域运行替换授权。
- L1/L2 任一来源、标定、同步、坐标、误差或复核证据失败时，平台回退至 `L0/unregistered_3d_reference`。

### 验证

- 核心 unit/smoke 584 项、后端 253 项、前端 186 项通过且 1 项跳过、Playwright E2E 5 项通过。
- Ruff、mypy、Python 3.11 compileall、`vue-tsc`、Vite build、项目 readiness 检查和 Git whitespace 检查通过；Black 与 isort 对本版本相对远端基线变更的 265 个 Python 文件检查通过。
- 15 份数据 manifest 的 47/47 条记录和 138/138 个本地文件通过来源与 SHA256 校验，总计 5,514,559,510 字节。

### 已知限制

- 真实目标域白光/荧光病例与医生像素级金标准仍缺失，患者自适应和骨活性空间模型保持代理工程验证状态。
- 真实设备全倍率/全工作距离 4K 标定、真实下颌仿体物理精度和真实术中导航性能仍待验证。
- 新型荧光造影剂的实物合成、光谱、选择性、安全性和组织实验属于后续独立验证工作。

## [0.2.0] - 日期未记录

### 新增

#### 项目规范

- **AGENTS.md** - 完善项目规范（18919 字节）
  - 项目定位与框架优先原则
  - 仓库事实基线
  - 框架目录与修改原则
  - LLM 自动环境核查规范
  - Python 类型安全规范
  - 通用实现规范
  - 提交修改前检查清单

#### 技能规则库

- **.rules/README.md** - 规则库索引
- **.rules/skill-data-preprocessing.md** - 数据预处理技能
- **.rules/skill-model-adapter.md** - 模型适配器技能
- **.rules/skill-pipeline-creation.md** - 流水线创建技能
- **.rules/skill-evaluation-metrics.md** - 评估指标技能
- **.rules/skill-configuration-management.md** - 配置管理技能
- **.rules/skill-competition-integration.md** - 比赛集成技能

#### 契约接口

- **src/core/contracts/__init__.py** - 核心配置、注册表、日志、生命周期接口
- **src/datasets/contracts/__init__.py** - 数据集加载、分割、清单读取接口
- **src/models/contracts/__init__.py** - 模型适配器、注册表、检查点管理接口
- **src/pipelines/contracts/__init__.py** - 流水线、流水线注册表接口
- **src/preprocess/contracts/__init__.py** - 预处理器、输入验证、后处理接口
- **src/engine/contracts/__init__.py** - 推理服务、实验运行、基准评估接口
- **src/reports/contracts/__init__.py** - 报告生成、验证、写入接口

#### 工具系统

- **src/utils/logging.py** - 统一日志系统
  - Logger 类，支持 debug/info/warning/error/critical
  - 专用日志方法：performance、lifecycle、inference、training
  - 全局日志注册表

- **src/utils/runtime.py** - 运行时工具
  - RuntimeEnvironment - 运行时环境检测
  - PerformanceMonitor - 性能监控
  - 设备检测和内存监控

#### 配置管理

- **mypy.ini** - 类型检查配置（严格模式）
- **src/py.typed** - 类型检查标记
- **src/core/config_validator.py** - 配置验证器
  - 任务配置验证
  - 模型配置验证
  - 流水线配置验证
  - 推理配置验证

#### 项目文档

- **README.md** - 更新项目文档（8699 字节）
  - 架构概述
  - 目录结构
  - 技能规则库
  - 契约接口
  - 类型安全

---

## [0.1.0] - 2024-01-01

### 新增

- 初始版本发布
- 配置驱动运行时
- 任务包契约
- 模型适配器接口
- 流水线实现
- 评估指标
- 报告生成
- Gradio Demo
- CLI 脚本
- 单元测试、冒烟测试、集成测试

---

## 统计

### 变更文件数

- 新增文件：21
- 修改文件：2
- 删除文件：0
- **总计：23**

### 代码行数变化

- 新增代码：约 1500 行
- 删除代码：约 500 行
- **净增：约 1000 行**

### 新增功能数

- 项目规范：1
- 技能规则库：7
- 契约接口：7
- 工具系统：2
- 配置管理：3
- 项目文档：1
- **总计：21**

---

## 兼容性

### 最低支持版本

- Python: 3.9+
- 依赖包版本见 `requirements.txt`

### 破坏性变更

本次更新无破坏性变更。

---

## 迁移指南

### 从 0.1.0 升级到 0.2.0

1. **无需修改现有代码** - 所有新增都是向后兼容的
2. **可选：使用新的日志系统** - 替换 print 语句为 Logger
3. **可选：使用配置验证器** - 验证配置文件
4. **可选：运行类型检查** - `mypy src/`

---

## 参考

- [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
- [语义化版本](https://semver.org/lang/zh-CN/)
