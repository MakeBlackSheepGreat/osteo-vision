# 挑战杯可行性报告包

本目录保存 2026-07-21 至 2026-07-22 形成的挑战杯可行性报告源稿、图包和可交付渲染件。它是活动报告包，目录外的 `research/reports/submission/README.md` 是提交目录总入口。

## 文件角色

| 内容 | 作用 |
|---|---|
| `Cap1_*.md` 至 `Cap9_*.md` | 分章可编辑源稿，便于团队分别维护临床需求、造影剂、融合、AI、验证和可行性内容 |
| `challenge_cup_feasibility_report_20260722_zh.md` | 完整证据版聚合源稿 |
| `challenge_cup_concise_feasibility_report_20260722_zh.md` | 精简提交版聚合源稿 |
| `assets/` | 报告配图、可重建源材料 `sources/` 及 `manifest.json`，由 `tools/build_challenge_cup_figures.py` 生成和登记 |
| `*.docx`、`*.pdf` | 由聚合 Markdown 渲染的交付件，提交前需与源稿和图包同步复核 |
| `格式校验报告.md` | 文档构建后的版式与内容检查记录 |

## 当前推荐交付件

- `challenge_cup_concise_feasibility_report_20260722_zh.docx`
- `challenge_cup_concise_feasibility_report_20260722_zh.pdf`

完整证据版用于团队审阅、答辩准备和来源追溯。所有平台相关结论保持工程验证定位，公开代理数据、离线三维参考和医生复核边界必须随报告保留。

## 重建顺序

在仓库根目录执行：

```powershell
conda run -n osteo-vision python tools/build_challenge_cup_figures.py
conda run -n osteo-vision python tools/build_challenge_cup_report.py
```

构建器的具体参数和 DOCX/PDF 依赖见上级目录的 `README.md` 与 `build_submission_documents.mjs`。修改分章源稿、聚合稿或图包后，重新生成渲染件并复核 `格式校验报告.md`，避免提交件与源稿漂移。

## 归档规则

正式提交后，将冻结版本复制到 `research/reports/archive/submission_<date>/`，同时保留本 README、源稿、图包 manifest 和生成入口。此操作应在提交清单确认后进行，现阶段文件继续原位保留。
