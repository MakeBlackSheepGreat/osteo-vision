# Research Archive

本目录保存颌骨骨髓炎项目启动前已经整理的研究资料、数据清单、旧脚本和外部模型代码快照。这里的内容用于论证、复查和数据落地，不作为正式应用源码入口。

## 目录约定

```text
research/
├── literature/inventory/  # 论文清单、数据集清单、可行性报告、PDF 资料
├── planning/              # 工程准备、数据获取、下载状态和原型依赖说明
├── reports/               # 规划、预处理、建模报告和既有 DOCX/XLSX 项目资料
├── model-snapshots/code/  # 外部模型代码快照，仅作参考或后续迁移来源
├── datasets/              # 公开候选数据集目录，大文件不进入 Git
├── media/                 # 图片素材
└── scripts/legacy/        # 旧报告生成、论文下载脚本
```

## 使用原则

- 正式开发从 `app/` 进入。
- 外部模型快照不要直接改成项目主线代码；需要接入时，优先通过 `app/` 内的模型适配器、任务配置和流水线机制迁移。
- 数据集原始文件、派生训练数据、checkpoint 和大体积 PDF 不进入 Git。
- 医院或企业样本必须先脱敏，并在对应 `SOURCE.md` 记录来源、许可、用途限制和处理记录。
- 新增正式研究报告默认放入 `research/reports/<topic>/`，中文和英文 Markdown 分别使用 `_zh.md` 与 `_en.md` 后缀。
