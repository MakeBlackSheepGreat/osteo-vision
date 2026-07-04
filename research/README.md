# Research Archive

本目录保存颌骨骨髓炎项目启动前已经整理的研究资料、数据清单、旧脚本和外部模型代码快照。这里的内容用于论证、复查和数据落地，不作为正式应用源码入口。

## 目录约定

```text
research/
├── literature/inventory/  # 论文清单、数据集清单、可行性报告、PDF 资料
├── planning/              # 工程准备、数据获取、下载状态和原型依赖说明
├── reports/               # 规划、预处理、建模报告和 legacy DOCX/XLSX 项目资料
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

## 当前索引

- 项目记录整合：`research/reports/planning/project_records_integrated_20260704_zh.md`
- 完整赛题原文复核：`research/reports/planning/official_competition_problem_alignment_20260704_zh.md`
- 官方技术文档对齐：`research/reports/planning/official_technical_document_alignment_zh.md`
- 四环素/骨自发荧光价值评估：`research/reports/planning/tetracycline_autofluorescence_value_assessment_20260704_zh.md`
- DeepSeek 头脑风暴复用评估：`research/reports/planning/deepseek_brainstorm_reuse_assessment_20260704_zh.md`
- 比赛演示闭环说明：`research/reports/planning/competition_demo_closed_loop_20260704_zh.md`
- 模型训练数据来源：`research/reports/modeling/model_training_data_sources_zh.md`
- 模型 checkpoint 清单：`research/reports/modeling/model_checkpoint_manifest_20260705_zh.md`
- D025 代理模型评估：`research/reports/modeling/d025_proxy_model_evaluation_20260704_zh.md`
- D025 代理模型续训提升：`research/reports/modeling/d025_lesion_continue_training_promotion_20260704_zh.md`
- D025 SegResNetDS 训练：`research/reports/modeling/d025_monai_segresnetds_training_20260704_zh.md`
- D025 代理模型对比：`research/reports/modeling/d025_proxy_model_comparison_20260704_zh.md`
- 2D Keyframe ConvNeXt 代理分割模型：`research/reports/modeling/keyframe_convnext2d_proxy_segmenter_20260705_zh.md`
- 医生复核反馈转训练 manifest 工具：`tools/build_keyframe_training_manifest_from_review.py`，输出可带 `sample_weight`，用于下一轮合并 proxy manifest 的加权训练。
- MedSAM-like prompt 分割接口：`research/reports/modeling/medsam_prompt_contract_20260704_zh.md`
- DentalSegmentator 颌骨 ROI 预处理契约：`research/reports/modeling/dentalsegmentator_roi_contract_20260704_zh.md`
- 视频下载状态：`research/reports/modeling/video_download_status_20260703_zh.md`
- 历史交付物归档：`research/reports/legacy/`
