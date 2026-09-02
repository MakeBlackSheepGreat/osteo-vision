# 13 篇文献元数据、开放获取与本地存档核验

核验日期：2026-07-28
范围：`competition_advisor_suggestions_feasibility_20260717_zh.md` 中四环素/骨活性、Evans blue、多模态模型与不确定性相关的 13 篇带 DOI 文献。DailyMed、openFDA 与无 DOI 的历史毒性记录不在本清单。

## 方法与边界

- 题名、DOI、PMID/PMCID：PubMed E-utilities 与 Crossref 交叉核验。
- 开放获取状态：Crossref 许可字段、Europe PMC、Unpaywall 与 OpenAlex 交叉核验。
- 本地全文只允许保存发布者、PMC 或明确开放入口提供的版本；不使用绕过付费墙、非授权镜像或来源不明的副本。
- 下载时发布者/PMC/Europe PMC PDF 端点遇到 TLS 超时或 HTTP 403。清单保留已验证的合法入口，并仅对既有的 L03 合法副本完成受控归档与 SHA256。

## 核验结果

| ID | 英文题名 | 建议中文译名 | DOI | 开放状态 | 本地状态 |
| --- | --- | --- | --- | --- | --- |
| L01 | Tetracycline Bone Fluorescence: A Valuable Marker for Osteonecrosis Characterization and Therapy | 四环素骨荧光：用于骨坏死表征与治疗的有价值标志物 | 10.1016/j.joms.2009.05.442 | 受限 | 仅合法入口 |
| L02 | Comparison of auto-fluorescence and tetracycline fluorescence for guided bone surgery of medication-related osteonecrosis of the jaw: a randomized controlled feasibility study | 药物相关颌骨坏死引导骨手术中自发荧光与四环素荧光的比较：随机对照可行性研究 | 10.1016/j.ijom.2016.10.008 | 受限 | 仅合法入口 |
| L03 | Differences between auto-fluorescence and tetracycline-fluorescence in medication-related osteonecrosis of the jaw—a preclinical proof of concept study in the mini-pig | 药物相关颌骨坏死中自发荧光与四环素荧光的差异：小型猪临床前概念验证研究 | 10.1007/s00784-020-03332-2 | 混合开放，CC BY 4.0 | 已归档并哈希 |
| L04 | Characterization of eight different tetracyclines: advances in fluorescence bone labeling | 八种不同四环素的表征：荧光骨标记的进展 | 10.1111/j.1469-7580.2010.01237.x | PMC 公开全文；复用许可待核 | 合法入口，待重试下载 |
| L05 | Fluorescent tetracycline bone labeling as an intraoperative tool to debride necrotic bone during septic hip revision: a preliminary case series | 荧光四环素骨标记作为感染性髋关节翻修术中清除坏死骨的工具：初步病例系列 | 10.5194/jbji-6-85-2021 | 金色开放，CC BY 4.0 | 合法入口，待重试下载 |
| L06 | Intraoperative assessment of bone viability through improved analysis and visualization of dynamic contrast-enhanced fluorescence imaging: technique report | 通过改进动态对比增强荧光成像的分析与可视化进行术中骨活性评估：技术报告 | 10.1097/OI9.0000000000000222 | 金色开放，CC BY 4.0 | 合法入口，待重试下载 |
| L07 | In vivo albumin labeling and lymphatic imaging | 体内白蛋白标记与淋巴成像 | 10.1073/pnas.1414821112 | 公开可读；复用许可未明 | 仅公开阅读入口 |
| L08 | Evans blue nanocarriers visually demarcate margins of invasive gliomas | 伊文思蓝纳米载体可视化勾画侵袭性胶质瘤边界 | 10.1007/s13346-013-0139-x | 受限 | 仅合法入口 |
| L09 | 131I-Evans blue: evaluation of necrosis targeting property and preliminary assessment of the mechanism in animal models | 碘-131伊文思蓝：坏死靶向特性的评价及其动物模型机制初步研究 | 10.1016/j.apsb.2017.08.002 | 金色开放，CC BY-NC-ND 4.0 | 合法入口，待重试下载 |
| L10 | Deep Learning Applications for Acute Stroke Management | 深度学习在急性卒中管理中的应用 | 10.1002/ana.26435 | 受限或许可未确认 | 仅合法入口 |
| L11 | Uncertainty estimation using a 3D probabilistic U-Net for segmentation with small radiotherapy clinical trial datasets | 采用三维概率 U-Net 对小型放疗临床试验数据集进行分割不确定性估计 | 10.1016/j.compmedimag.2024.102403 | 混合开放，CC BY 4.0 | 合法入口，待重试下载 |
| L12 | Multi-rater Prism: Learning self-calibrated medical image segmentation from multiple raters | 多标注者 Prism：从多名标注者学习自校准医学图像分割 | 10.1016/j.scib.2024.06.037 | 混合开放，CC BY 4.0 | 合法入口，待重试下载 |
| L13 | Evaluation of uncertainty estimation methods in medical image segmentation: Exploring the usage of uncertainty in clinical deployment | 医学图像分割中不确定性估计方法的评价：探索不确定性在临床部署中的应用 | 10.1016/j.compmedimag.2025.102574 | 受限 | 仅合法入口 |

## 归档与复核

已归档文件位置：`research/datasets/literature_audit_20260728/raw/L03_10.1007_s00784-020-03332-2.pdf`
SHA256：`CD2BA15BA6F39F9F0CC3FE44D95850C08B3FCFAAC79A03184FC1514ED3ECF27A`

机器可读明细见 `research/literature/inventory/literature_13_audit_manifest_20260728.csv`。其中 `open_entry_retry_required` 表示开放入口与许可已核验，本轮下载受网络链路限制；不得据此虚构本地文件或哈希。
