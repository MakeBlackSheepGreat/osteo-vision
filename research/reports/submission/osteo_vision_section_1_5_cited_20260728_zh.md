# 1.5 国内外技术研究现状（可直接替换报告原文）

> 引用范围：采用 2023-2025 年的近期研究为主体。引用序号对应文末“参考文献”。正文将 ICG、候选探针和 AI 输出限定为术中参考与研发验证依据，未将其表述为颌骨骨髓炎自动诊断证据。

## 1.5 国内外技术研究现状

近三年，术中荧光成像、骨灌注量化、医学图像融合与基础模型分割持续向“多源影像输入、可量化信号输出和临床复核”发展。颌骨相关的近期研究主要集中于 MRONJ 的影像分期、CBCT 管理、手术切除方式和复发影响因素[1-4]；荧光技术研究则在 ICG 引导手术、骨或软组织灌注评估、感染相关荧光识别、荧光设备与 AI 融合方面形成了较完整的方法学积累[5-17]。当前公开证据仍缺少真实术中 ICG 颌骨骨髓炎同步白光/荧光视频与医生像素级金标准，因此项目平台的近期定位应保持为术中信号分析、候选区域提示和医生复核辅助。

### 1.5.1 荧光造影与术中导航

#### 1. ICG 在外科的临床应用

ICG 荧光引导手术已在近年形成较成熟的术中成像方法学。EAES 共识将 ICG 荧光成像用于灌注、血管、胆道、淋巴和病灶相关的术中可视化场景，并强调成像协议、给药时机、设备参数和临床任务之间需要一致匹配[5]。综合综述及近年的设备技术综述进一步显示，荧光成像正与高灵敏探测、定量信号处理和术中导航工作流结合，但临床解释仍需要结合手术场景和其他临床信息[6,11]。2025 年 WSES 共识也将 ICG 荧光定位为急诊外科决策的辅助信息来源，并要求结合适应证、图像质量与术者判断使用[10]。

在骨与软组织场景中，近期研究已探索 ICG 近红外血管造影对术中伤口灌注的评估价值，并报告了骨及软组织手术中的应用经验[8]。模拟骨折模型研究进一步以荧光成像分析截骨和骨膜破坏后的骨灌注变化，为骨组织灌注信号量化提供了实验依据[9]。感染场景中，坏死性软组织感染的实时 ICG 研究展示了信号图、ROI 和术中判读结合的可行性[7]。这些研究可支撑本项目的 ICG 伪彩、ROI 定量、时序记录与医生复核链路；ICG 信号受灌注、血管通透性、炎症、成像条件和操作过程影响，不能直接等同于颌骨骨髓炎特异性病灶。

#### 2. 新型荧光造影剂与骨/感染靶向探索

新型荧光造影剂研究正在从通用血流或组织对比信号向骨亲和、细菌或生物膜识别等选择性模块延伸。TTQF-SO3 研究提出了用于 NIR-II 骨靶向成像的磺酸盐有机小分子，并报告了羟基磷灰石亲和性和动物骨成像结果[18]。万古霉素示踪剂研究则在取出骨科内固定装置和清创场景中探索革兰阳性菌相关信号的原位可视化[19]。两类研究可为“骨亲和模块 + 感染识别模块 + 发光模块”的候选探针架构提供文献依据；其生物分布、颌骨适配性、活体给药安全性、死骨与活骨区分能力及赛题设备光谱匹配仍需项目后续实验逐项验证。

### 1.5.2 医学图像智能分析、多模态融合与导航

医学图像智能分析已由单帧分类或分割扩展至多模态融合、视频处理和基础模型适配。近期综述系统整理了深度学习医学图像融合的网络结构、评价指标及跨模态信息保持问题[14]，2025 年综述进一步归纳了多模态融合在临床诊断中的算法进展、局限与转化挑战[15]。这些工作可为白光/ICG 配准、归一化、伪彩、融合和质量控制提供方法学参考。

面向术中视频，荧光引导手术视频去噪研究提供了公开数据与低照度荧光视频增强方法，为平台 MP4 导入、关键帧分析和时序稳定性验证提供工程代理路径[13]。荧光成像与人工智能融合的近期综述提出，应将图像质量、模型可解释性、临床工作流和人机协作共同纳入精准手术系统设计[12]。在医学分割方面，TransUNet 将 Transformer 与 U-Net 结构结合以提高全局上下文建模能力[16]；Medical SAM Adapter 则展示了将通用分割基础模型适配到医学图像任务的路线[17]。这些模型属于候选方法或适配器依据，主线模型仍应以相同数据清单、来源分组、预处理和评价协议完成独立训练与比较后确定。

### 1.5.3 当前空白与本项目切入点

综合近期文献，颌骨骨髓炎术中辅助判读仍存在以下三类关键空白：

1. **目标域证据不足。** 近期颌骨研究重点仍偏向 MRONJ 的临床管理、CBCT 评估和手术结局[1-4]；骨或感染 ICG 研究多来自非颌骨场景[7-9]。真实颌骨骨髓炎同步白光/ICG 视频、成对通道配准记录与医生像素级金标准仍需通过受控临床合作建立。
2. **造影剂选择性与设备适配缺少闭环验证。** 骨靶向和细菌靶向候选已具备可参考的分子与成像研究基础[18-19]，但与颌骨骨髓炎、活骨/死骨区分、复杂菌群、毒理药代以及当前显微镜光谱窗口之间仍存在待验证环节。
3. **从算法输出到医生复核的可追溯闭环仍需工程化。** 近期 AI、视频与融合研究已提供可复用方法[12-17]，临床应用仍需要将模型版本、输入来源、配准质量、ROI、风险提示、不确定性和医生复核状态关联到病例级证据包。

本项目据此构建“官方 JPEG/MP4 输入 - 荧光处理与多模态融合 - AI 候选区、风险与不确定性提示 - 医生复核 - 结构化证据输出”的软件闭环。该闭环服务于工程验证和术中辅助参考，临床诊断与清创范围的最终判断由医生完成。

## 参考文献

[1] Bedogni A, Mauceri R, Fusco V, et al. Italian position paper (SIPMO-SICMF) on medication-related osteonecrosis of the jaw (MRONJ)[J]. Oral Diseases, 2024, 30(6): 3679-3709. DOI: 10.1111/odi.14887.

[2] Ko Y Y, Yang W F, Leung Y Y. The role of cone beam computed tomography (CBCT) in the diagnosis and clinical management of medication-related osteonecrosis of the jaw (MRONJ)[J]. Diagnostics, 2024, 14(16): 1700. DOI: 10.3390/diagnostics14161700.

[3] Suyama K, Otsuru M, Nakamura N, et al. Bone resection methods in medication-related osteonecrosis of the jaw in the mandible: An investigation of 206 patients undergoing surgical treatment[J]. Journal of Dental Sciences, 2024, 19(3): 1758-1769. DOI: 10.1016/j.jds.2023.10.007.

[4] Ruan H J, Li M Y, Zhang Z Y, et al. Medication-related osteonecrosis of the jaw: A retrospective single center study of recurrence-related factors after surgical treatment[J]. Clinical Oral Investigations, 2024, 28(10): 549. DOI: 10.1007/s00784-024-05911-z.

[5] Cassinotti E, Al-Taher M, Antoniou S A, et al. European Association for Endoscopic Surgery (EAES) consensus on indocyanine green (ICG) fluorescence-guided surgery[J]. Surgical Endoscopy, 2023, 37(3): 1629-1648. DOI: 10.1007/s00464-023-09928-5.

[6] Sutton P A, van Dam M A, Cahill R A, et al. Fluorescence-guided surgery: Comprehensive review[J]. BJS Open, 2023, 7(3): zrad049. DOI: 10.1093/bjsopen/zrad049.

[7] Ray G S, Streeter S S, Bateman L M, et al. Real-time identification of life-threatening necrotizing soft-tissue infections using indocyanine green fluorescence imaging[J]. Journal of Biomedical Optics, 2024, 29(6): 066003. DOI: 10.1117/1.JBO.29.6.066003.

[8] Wang H, Tang X, Ji T, et al. Efficacy of indocyanine green fluorescence-based near-infrared angiography in assessing intraoperative wound perfusion for bone and soft-tissue surgery[J]. Bone & Joint Open, 2025, 6(7): 796-806. DOI: 10.1302/2633-1462.67.bjo-2024-0248.r1.

[9] Tang Y, Jiang S, Elliott J T, et al. Intraoperative bone perfusion assessment using fluorescence imaging in a simulated fracture model[J]. Journal of Bone and Joint Surgery, 2025, 107(18): 2031-2039. DOI: 10.2106/JBJS.24.01436.

[10] De Simone B, Abu-Zidan F M, Boni L, et al. Indocyanine green fluorescence-guided surgery in the emergency setting: The WSES international consensus position paper[J]. World Journal of Emergency Surgery, 2025, 20: 13. DOI: 10.1186/s13017-025-00575-w.

[11] Preziosi A, Cirelli C, Waterhouse D, et al. State of the art medical devices for fluorescence-guided surgery (FGS): Technical review and future developments[J]. Surgical Endoscopy, 2024, 38(11): 6227-6236. DOI: 10.1007/s00464-024-11236-5.

[12] Cheng H, Xu H, Peng B, et al. Illuminating the future of precision cancer surgery with fluorescence imaging and artificial intelligence convergence[J]. npj Precision Oncology, 2024, 8: 196. DOI: 10.1038/s41698-024-00699-3.

[13] Seets T, Selles A, Nunes J C, et al. Video denoising in fluorescence guided surgery[C]//Proceedings of the 27th International Conference on Artificial Intelligence and Statistics. 2024. Available: https://proceedings.mlr.press/v227/seets24a.html.

[14] Zhou T, Cheng Q, Lu H, et al. Deep learning methods for medical image fusion: A review[J]. Computers in Biology and Medicine, 2023, 160: 106959. DOI: 10.1016/j.compbiomed.2023.106959.

[15] Zubair M, Hussain M, Albashrawi M A, et al. A comprehensive review of techniques, algorithms, advancements, challenges, and clinical applications of multi-modal medical image fusion for improved diagnosis[J]. Computer Methods and Programs in Biomedicine, 2025, 272: 109014. DOI: 10.1016/j.cmpb.2025.109014.

[16] Chen J, Mei J, Li X, et al. TransUNet: Rethinking the U-Net architecture design for medical image segmentation through the lens of transformers[J]. Medical Image Analysis, 2024, 97: 103280. DOI: 10.1016/j.media.2024.103280.

[17] Wu J, Wang Z, Hong M, et al. Medical SAM adapter: Adapting segment anything model for medical image segmentation[J]. Medical Image Analysis, 2025, 102: 103547. DOI: 10.1016/j.media.2025.103547.

[18] Chen P, Qu F, He L, et al. Quasi-dendritic sulfonate-based organic small molecule for high-quality NIR-II bone-targeted imaging[J]. Journal of Nanobiotechnology, 2023, 21: 230. DOI: 10.1186/s12951-023-01999-9.

[19] Spoelstra G B, Elsinga P H, van Dijl J M, et al. Vancomycin-based tracers guiding in situ visualization of bacteria on osteosynthesis devices and surgical debridement[J]. European Journal of Nuclear Medicine and Molecular Imaging, 2025, 52(10): 3877-3890. DOI: 10.1007/s00259-025-07249-4.
