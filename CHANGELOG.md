# 医学影像比赛框架变更日志

所有重要的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

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

### 从 0.1.0 升级到 Unreleased

1. **无需修改现有代码** - 所有新增都是向后兼容的
2. **可选：使用新的日志系统** - 替换 print 语句为 Logger
3. **可选：使用配置验证器** - 验证配置文件
4. **可选：运行类型检查** - `mypy src/`

---

## 参考

- [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
- [语义化版本](https://semver.org/lang/zh-CN/)
