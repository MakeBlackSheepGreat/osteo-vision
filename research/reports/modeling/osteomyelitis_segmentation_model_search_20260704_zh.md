# 骨髓炎/骨感染分割模型检索报告

生成日期：2026-07-04

## 1. 检索结论

本轮使用 Tavily CLI 检索“osteomyelitis segmentation”“MRONJ CBCT nnU-Net”“bone infection PET-CT segmentation”等关键词。结论是：目前未发现可直接用于“术中 ICG 颌骨骨髓炎 4K MP4/JPEG”的公开成品分割模型；但已经有若干高度可迁移的相近模型路线。

最接近本项目的是：

1. **MRONJ CBCT nnU-Net v2 分割**：与颌骨坏死/颌骨病灶位置高度相关，使用 52 例 CBCT，nnU-Net v2 3D low-resolution，5 折交叉验证，报告 Dice 约 0.716、IoU 约 0.569、HD95 约 4.045 mm。适合作为本项目 CBCT 病灶代理模型的最强方法依据。
2. **良性颌骨病灶 CBCT nnU-Net v2 分割**：使用 355 例良性颌骨病灶 CBCT，并按病灶类别建立模型，报告 DSC 约 0.70-0.72，外部数据集 DSC 约 0.84-0.87。适合作为 D025 牙源性病灶代理训练的直接参考。
3. **Dual-modality PET-CT 骨感染分割**：2026 CVPR Workshop/ArXiv 工作，提出 PET 代谢信号 + CT 骨窗解剖早期融合的 U-Net 框架，并强调骨感染边界模糊、标注策略差异和多源监督。这是“骨感染分割”关键词下最接近骨髓炎本体的深度学习分割研究。
4. **DentalSegmentator 预训练模型**：公开 Zenodo checkpoint 与 3D Slicer 扩展，基于 nnU-Net v2.2，可分割 upper skull、mandible、upper teeth、lower teeth、mandibular canal。它不是病灶模型，但可直接作为颌骨解剖先验和 ROI 裁剪工具。

## 2. 对比赛模型路线的影响

| 来源 | 是否可直接使用 | 对本项目帮助 | 当前决策 |
|---|---|---|---|
| MRONJ CBCT nnU-Net v2 | 无公开训练集/checkpoint 迹象 | 证明颌骨坏死类 CBCT 病灶可用 nnU-Net v2 分割 | 把 nnU-Net v2 作为正式 CBCT 病灶 baseline；报告引用其指标作为目标参照。 |
| 良性颌骨病灶 nnU-Net v2 | 未发现公开 checkpoint | 与 D025 牙源性病灶代理最接近 | 继续优化 D025 lesion proxy，按类别/病灶类型做失败分析。 |
| PET-CT 骨感染分割 | 论文公开，未确认公开代码/checkpoint | 提供骨髓炎/骨感染本体的边界模糊和多模态融合证据 | 报告中用于论证骨感染分割难点；暂不接入工程主线。 |
| DentalSegmentator | 有公开模型和 Slicer 扩展 | 颌骨、牙齿、下颌管解剖先验 | 后续可下载并接入为术前 CBCT ROI/解剖先验模块。 |
| 通用骨/骨肿瘤分割模型 | 多数非感染、非颌骨 | 可做方法参考 | 不作为主线。 |

## 3. 与我们当前训练结果的比较

本轮本地 D025 代理模型已经升级为 base12/3000 batch 候选并提升为主线 checkpoint：

- 验证病例：53。
- 最佳阈值：0.2。
- Mean Dice：0.6266。
- Mean IoU：0.5183。
- Mean HD95：17.6413。
- Mean NSD：0.4227。
- Lesion sensitivity：0.6756。
- Lesion precision：0.6932。

与 MRONJ CBCT nnU-Net v2 文献 Dice 约 0.716 相比，我们的 D025 代理模型仍有差距，但已经从初始 smoke 模型 Dice 约 0.136 提升到可作为比赛阶段性证据的水平。下一步应优先补 nnU-Net/SegResNetDS baseline，而不是继续只调 tiny ConvNeXt-U-Net。

## 4. 建议执行路线

### P0：短期比赛可交付

1. 保留当前 D025 base12 checkpoint 作为“CBCT 病灶代理分割模型 v0.2”。
2. 报告中引用 MRONJ CBCT nnU-Net v2 和良性颌骨病灶 nnU-Net v2，说明我们选 nnU-Net/CBCT 代理路线的依据。
3. 术中 ICG MP4/JPEG 继续定位为荧光增强、热点分析、ROI 定量和医生复核，不承诺已训练真实骨髓炎术中分割模型。

### P1：继续冲模型

1. 下载/接入 DentalSegmentator 预训练模型，先做颌骨/牙齿/下颌管自动 ROI。
2. 把 D025 训练从 64³ ROI 升级到高分辨率 patch，优先跑 nnU-Net v2 或 MONAI SegResNetDS baseline。
3. 对失败样本 `DC_9`、`RC_11`、`RC_3`、`RC_52`、`KCOT_68`、`DC_35`、`RC_25`、`DC_26` 做病例级错误分析。
4. 把 MRONJ/骨感染论文中的“边界模糊、不一致标注、多源监督”迁移为本项目的不确定性提示和医生复核设计。

## 5. 主要来源

- Deep learning-based automatic segmentation of MRONJ lesions on CBCT images: https://pmc.ncbi.nlm.nih.gov/articles/PMC13077929/
- PubMed MRONJ segmentation entry: https://pubmed.ncbi.nlm.nih.gov/41787411
- Development of a Preliminary Diagnostic Tool for the Segmentation of Benign Jaw Lesions in CBCT Images Using nnU-Net v2: https://pubmed.ncbi.nlm.nih.gov/41530422
- Cross-Source Supervision for Bone Infection Segmentation in Dual-Modality PET-CT: https://arxiv.org/abs/2605.16373
- CVPR Workshop PDF for PET-CT bone infection segmentation: https://openaccess.thecvf.com/content/CVPR2026W/AI4RWC/papers/Yang_Cross-Source_Supervision_for_Bone_Infection_Segmentation_in_Dual-Modality_PET-CT_CVPRW_2026_paper.pdf
- DentalSegmentator pretrained model: https://zenodo.org/records/10829675
- SlicerAutomatedDentalTools / DentalSegmentator extension: https://github.com/DCBIA-OrthoLab/SlicerAutomatedDentalTools
- Scaling nnU-Net for CBCT Segmentation: https://arxiv.org/html/2411.17213v2

## 6. 边界

以上模型和论文不能直接证明本项目已经具备真实术中 ICG 颌骨骨髓炎分割能力。它们支持的是：CBCT 病灶代理分割、颌骨解剖先验、骨感染边界模糊建模和未来多模态融合路线。
