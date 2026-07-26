# 挑战杯可行性报告包

本目录保存挑战杯可行性报告源稿、图包和可交付渲染件。它是活动报告包，目录外的参赛材料总入口用于管理更广泛的提交材料。

## 文件角色

| 内容 | 作用 |
|---|---|
| 九章源稿 | 分章维护临床需求、造影剂、融合、人工智能、验证和可行性内容 |
| 完整报告聚合稿 | 由九章源稿自动汇集，供团队审阅、答辩准备和证据追溯 |
| 精简提交稿 | 面向评审的提交正文，保留赛题三项要求、工程指标和后续验证路线 |
| 数据汇总 | 数据、模型、性能、三维验证和核验集合的统一口径 |
| 图包 | 报告配图、最小重建材料与完整性清单 |
| Word 与 PDF | 由报告正文渲染的交付件，提交前需与源稿和图包同步复核 |
| 格式校验记录 | 文档构建后的版式与内容检查结果 |

## 当前推荐交付件

- 2026 年 7 月 26 日精简提交稿的 Word 与 PDF 渲染件。

精简提交稿已按 2026 年 7 月 26 日事实基线更新，正文使用自然语言表达，不列出代码、字段、配置、文件或路径名称。数据部分明确区分来源核验集合与分层数据注册表：前者为 15 份来源清单、47 条记录和 138 个文件的核验集合，后者为 504 条分层登记记录。

完整证据版用于团队审阅、答辩准备和来源追溯。所有平台相关结论保持工程验证定位，公开代理数据、离线三维参考和医生复核边界必须随报告保留。

## 重建顺序

在仓库根目录执行以下两步：

```powershell
conda run -n osteo-vision python tools/build_challenge_cup_figures.py
conda run -n osteo-vision python tools/build_challenge_cup_report.py
conda run -n osteo-vision python scripts/generate_thesis_docx.py
conda run -n osteo-vision python scripts/generate_data_summary_docx.py
node research/reports/submission/build_submission_documents.mjs research/reports/submission/challenge_cup_report_draft_20260721/challenge_cup_concise_feasibility_report_20260726_zh.md research/reports/submission/challenge_cup_report_draft_20260721/challenge_cup_concise_feasibility_report_20260726_zh_final.docx
conda run -n osteo-vision python tools/validate_challenge_cup_documents.py
```

修改九章源稿、聚合稿或图包后，依次重建图包、完整报告和渲染件，并复核格式校验记录，确保提交件与源稿一致。

## 归档规则

正式提交后，将冻结版本复制到 `research/reports/archive/submission_<date>/`，同时保留本 README、源稿、图包 manifest 和生成入口。此操作应在提交清单确认后进行，现阶段文件继续原位保留。
