# 四环素/骨自发荧光与 MRONJ 分割资料下载状态

日期：2026-07-03

目标目录：`research/literature/inventory/papers/`

说明：`papers/` 已被 `.gitignore` 排除，适合保存论文 PDF、网页备份等本地研究资料，不进入 Git。原始链接中的 `-` 是空占位项，未处理。

## 已下载 PDF

| 编号 | 本地文件 | 来源 | 对项目的用途 |
|---|---|---|---|
| P061 | `papers/P061_2025_tetracycline_fluorescence_MRONJ_scoping_review.pdf` | https://craniofacialres.com/media/posts/Art_06_1_2025_6gZaW9k.pdf | 四环素荧光引导 MRONJ 手术综述；用于造影剂/荧光边界章节。 |
| P063 | `papers/P063_2020_auto_vs_tetracycline_fluorescence_MRONJ_minipig.pdf` | https://link.springer.com/content/pdf/10.1007/s00784-020-03332-2.pdf | 小型猪 MRONJ 前临床研究；支持骨自发荧光与四环素荧光的边界识别机制。 |
| P064 | `papers/P064_2026_nnunet_v2_MRONJ_CBCT_segmentation.pdf` | https://europepmc.org/api/getPdf?pmcid=PMC13077929 | nnU-Net v2 分割 MRONJ CBCT 病灶；用于赛点二 AI 辅助判读 baseline。 |
| P066 | `papers/P066_2025_autofluorescence_guided_ONJ_histopathology.pdf` | https://pdfs.semanticscholar.org/af94/7f4c2f50e6bfea07149e310e11f271d303c4.pdf | ONJ 骨自发荧光与病理样本相关；用于补强无造影剂边界识别方案。 |
| P068 | `papers/P068_2022_fluorescence_guided_surgery_osteoradionecrosis_jaw.pdf` | https://epub.ub.uni-muenchen.de/94924/1/03000605221104186.pdf | 颌骨放射性骨坏死荧光引导手术；用于泛化说明荧光边界引导在颌骨坏死类病变中的应用。 |

## 已保存 HTML 备份

| 编号 | 本地文件 | 来源 | 说明 |
|---|---|---|---|
| P062 | `papers/html/P062_2010_tetracycline_bone_fluorescence_osteonecrosis_pubmed.html` | https://pubmed.ncbi.nlm.nih.gov/20006166/ | Pautke et al., 2010。ScienceDirect PDF 返回 403；当前保留 PubMed 元数据和摘要。 |
| P065 | `papers/html/P065_2017_3D_Slicer_surgical_navigation_system_pmc.html` | https://pmc.ncbi.nlm.nih.gov/articles/PMC5549678/ | 3D Slicer 术中导航系统。PMC PDF 触发 CloudPMC 下载挑战；当前保留全文 HTML。 |
| P067 | `papers/html/P067_2010_eight_tetracyclines_fluorescence_bone_labeling_pmc.html` | https://pmc.ncbi.nlm.nih.gov/articles/PMC2913014/ | 八种四环素衍生物骨荧光标记。PMC/Wiley PDF 下载受限；当前保留全文 HTML。 |

## 未直接下载 PDF 的原因

- P062 对应 Academia 链接是二级入口，不作为正式引用源；正式引用应使用 PubMed PMID `20006166` 或 DOI `10.1016/j.joms.2009.05.442`。
- P065 和 P067 的 PMC PDF 入口会返回 CloudPMC `Preparing to download` 页面，普通下载器无法直接取得 PDF；HTML 全文已保存。
- P067 的 Wiley DOI PDF 入口返回 403，未保存为 PDF。

## 研究使用建议

- 造影剂/荧光边界章节：优先读 P061、P062、P063、P066、P068。
- AI 分割章节：优先读 P064，并对照本项目已有 nnU-Net、D024、D036、D025 报告。
- 平台/导航/结果输出章节：优先读 P065，用于 3D Slicer、CT 注册、术前规划和术中导航扩展论证。
