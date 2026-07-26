# 当前参赛材料入口

适用工程版本：`0.3.0-rc.2`，报告数据更新至 2026-07-26。

本目录只保存当前可提交说明、证据清单配置和由工具生成的当前证据索引。2026-07-11 提交包已移动至 `../archive/submission_20260711/`。

## 当前材料

- 挑战杯精简可行性报告源稿：2026 年 7 月 26 日版本，面向评审提交。
- 挑战杯精简可行性报告 Word 与 PDF：与精简源稿同步生成的提交渲染件。
- 挑战杯完整证据版源稿：2026 年 7 月 26 日聚合版本，供团队审阅与答辩准备。
- 挑战杯完整证据版 Word 与 PDF：与完整源稿同步生成的渲染件。
- 挑战杯数据汇总：2026 年 7 月 26 日统一数据、模型、性能与三维工程口径。
- 挑战杯软件展示答辩运行单：`challenge_cup_demo_runbook_20260721_zh.md`
- 海南现场作品对标备忘录：`challenge_cup_hainan_benchmark_memo_20260722_zh.md`
- 技术方案源稿：`osteo_vision_technical_solution_20260719_zh.md`
- 技术方案 Word 提交稿：`osteo_vision_technical_solution_20260719_zh.docx`
- 技术方案 PDF 提交稿：`osteo_vision_technical_solution_20260719_zh.pdf`
- 证据清单配置：`evidence_manifest.yml`
- 机器可读证据索引：`competition_evidence_index_20260719.json`
- 中文证据索引：`competition_evidence_index_20260719_zh.md`
- 最新工程快照：`../release/README.md`

## 挑战杯报告重建

精简提交版作为当前建议提交件，完整证据版保留给答辩准备、团队复核和后续内容裁剪。两份报告共用同一图包，图像由本地 Markdown 以相对位置嵌入。图包的最小公开或合成重建材料已收敛，构建过程不依赖被忽略的本地运行产物。

```powershell
conda run -n osteo-vision python -X utf8 tools/build_challenge_cup_figures.py
conda run -n osteo-vision python -X utf8 tools/build_challenge_cup_report.py
powershell -ExecutionPolicy Bypass -File research/reports/submission/build_submission_documents.ps1
```

报告正文遵循 2026 年 7 月 26 日事实基线。数据叙述必须区分两类统计范围：来源核验集合由 15 份来源清单、47 条记录和 138 个文件组成；分层数据注册表登记 504 条记录。两者均保留来源、日期和用途，不合并为单一数据规模。

## 重新生成 Word 与 PDF

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File research/reports/submission/build_submission_documents.ps1
```

构建器使用根目录 `package.json` 声明的 `docx` 与 `marked`，从当前 Markdown 源稿生成 A4 DOCX。随后调用本机 Microsoft Word 更新目录、页码和字段，并导出 PDF。源稿发生变化后应同时重新生成两份提交稿，避免格式产物与 Markdown 内容漂移。

仅需重建 DOCX 时可运行：

```powershell
node research/reports/submission/build_submission_documents.mjs
```

PDF 导出依赖可通过 `Word.Application` COM 调用的桌面文字处理组件，推荐使用 Microsoft Word。若本机由 WPS 接管该 COM 注册，PDF 元数据中的 Creator 会显示 WPS；正式提交前应在最终交付环境复核 PDF 元数据和逐页渲染结果。

## 文档校验

Windows 下运行校验器时必须固定 Python UTF-8 模式，防止系统默认 GBK 编码误读 DOCX 内的 UTF-8 XML：

```powershell
$env:PYTHONUTF8 = "1"
conda run -n osteo-vision python -X utf8 "$env:USERPROFILE\.codex\skills\docx\scripts\office\validate.py" research/reports/submission/osteo_vision_technical_solution_20260719_zh.docx -v
```

安装 Poppler 后可复核 PDF 页数、纸张尺寸并渲染逐页图像：

```powershell
pdfinfo research/reports/submission/osteo_vision_technical_solution_20260719_zh.pdf
pdftoppm -png -r 120 research/reports/submission/osteo_vision_technical_solution_20260719_zh.pdf submission-page
```

## 重新生成证据索引

```powershell
conda run -n osteo-vision python tools/build_competition_evidence_index.py --manifest research/reports/submission/evidence_manifest.yml --stamp 20260719
```

生成器读取当前 Git、版本、严格配置、模型清单和证据文件，并记录缺失项。工作区未提交时可生成内部草稿；正式提交应在干净提交和冻结 tag 后重新运行。

## 声明边界

- 造影剂候选仍处于文献支持的设计与实验计划阶段。
- 当前模型指标来自公开异域、代理或伪标注数据。
- 患者条件与骨活性空间替换未通过目标域安全门。
- 三维 L1/L2 仅用于静态仿体与离线动态工程验证。
- 所有输出需要医生复核。
