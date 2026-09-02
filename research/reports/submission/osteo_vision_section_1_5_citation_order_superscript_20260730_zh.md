# 1.5 国内外技术研究现状（顺序编码角标版）

## 1.5 国内外技术研究现状

近三年，颌骨近域研究主要围绕药物相关性颌骨骨坏死的诊疗路径、影像评估和手术管理展开。2024 年意大利 MRONJ 立场文件总结了临床分期、风险控制和多学科管理要点；同期 CBCT 综述进一步讨论了锥形束 CT 在 MRONJ 诊断和临床管理中的价值。<sup>[1-2]</sup> 术中荧光研究则持续向定量信号、设备性能、骨灌注时序分析、视频人工智能处理和多模态融合发展。平台输出定位为术中参考信号、风险提示和医生复核辅助。

## 1.5.1 荧光造影与术中导航

### 1. ICG 在外科的临床应用

吲哚菁绿（ICG）是临床应用较成熟的近红外荧光造影剂。EAES 共识覆盖灌注、血管、胆道、淋巴及病灶相关术中可视化，并强调成像设备、给药方案、观察时相和临床任务共同影响结果解释。<sup>[3]</sup> 荧光引导手术的近期综述汇总了荧光探针、成像策略和转化路径；设备技术综述进一步指出，探测灵敏度、显示方式、图像处理和工作流设计会影响术中信息的可用性。<sup>[4-5]</sup>

在骨及软组织场景中，2025 年研究报告了 ICG 近红外血管造影用于术中伤口灌注评估的经验；模拟骨折模型研究量化了截骨与骨膜破坏后的骨灌注变化。<sup>[6-7]</sup> 感染场景的实时 ICG 研究展示了荧光图、ROI 定量和术中判读联动的工程可行性。<sup>[8]</sup> WSES 2025 共识将 ICG 荧光定位为急诊外科决策的辅助信息来源，并要求结合适应证、图像质量和术者判断使用。<sup>[9]</sup>

ICG 荧光信号与局部灌注、血管通透性、给药方案、观察时相、成像距离、视角及设备响应相关。炎症区域可出现较高信号，缺血或低灌注区域可出现较低信号。该类信号差异不构成颌骨骨髓炎的疾病特异性判定阈值，适合用于灌注和组织活性参考，并需与白光结构信息、时序曲线、质量控制和医生复核共同解释。<sup>[3,6-9]</sup>

### 2. 新型荧光造影剂与骨/感染靶向探索

候选探针研究正在由通用灌注信号延伸至骨亲和和细菌识别模块。TTQF-SO3 的研究提出了 NIR-II 骨靶向有机小分子，并报告了羟基磷灰石亲和性与动物骨成像结果。<sup>[10]</sup> 万古霉素示踪剂研究探索了革兰阳性菌相关信号在骨科内固定装置和清创场景中的原位可视化。<sup>[11]</sup> 这些结果可为“骨亲和模块 + 感染识别模块 + 发光模块”的候选探针架构提供设计依据。颌骨适配性、活体给药安全性、药代动力学、死骨与活骨区分能力及显微镜光谱匹配仍需项目后续验证。

## 1.5.2 医学图像智能分析

荧光引导手术视频去噪研究提供了公开数据和低照度荧光视频增强方法，为 MP4 导入、关键帧分析和时序稳定性验证提供工程代理路径。<sup>[12]</sup> 荧光成像与人工智能融合的近期综述提出，应将图像质量、模型可解释性、临床工作流和人机协作共同纳入精准手术系统设计。<sup>[13]</sup>

多模态医学图像融合已形成由传统配准向深度学习融合发展的技术路线。2023 年综述系统整理了深度学习医学图像融合的网络结构和评价问题；2025 年综述进一步归纳了算法进展、临床应用及转化限制。<sup>[14-15]</sup> 这些工作可为白光/ICG 配准、归一化、伪彩、融合和质量控制提供方法学依据。

在医学分割方面，TransUNet 将 Transformer 与 U-Net 结构结合以增强全局上下文建模；Medical SAM Adapter 展示了通用分割基础模型向医学图像任务的适配路线。<sup>[16-17]</sup> U-Mamba 与 SAM 2 分别代表长程依赖建模和视频提示式分割的发展方向。<sup>[18-19]</sup> 上述模型均应在真实白光/ICG 成对数据、颌骨组织标注、患者级独立划分和统一评价协议下开展适用性验证。

## 1.5.3 当前研究空白

1. 缺少颌骨骨髓炎特异性的荧光探针及经临床验证的荧光判别阈值。<sup>[1-3,6-11]</sup>
2. 真实术中白光/ICG 同步数据和医生标注规模有限，公开研究多为骨灌注、颌骨坏死或其他外科近域场景。<sup>[1-2,6-8]</sup>
3. 荧光信号容易受到炎症反应、组织遮挡、设备参数和观察时相影响，需要结合白光结构信息、时序特征和质量控制。<sup>[3-9]</sup>
4. 现有通用分割模型缺少面向颌骨骨髓炎的独立临床验证，医生复核、不确定性提示和证据追溯仍需完善。<sup>[12-19]</sup>

本项目据此构建“官方 JPEG/MP4 输入 - 荧光处理与多模态融合 - AI 候选区、风险与不确定性提示 - 医生复核 - 结构化证据输出”的软件闭环。该闭环服务于工程验证和术中辅助参考，临床诊断与清创范围的最终判断由医生完成。

## 英文缩写名词解释

| 缩写 | 英文全称 | 中文解释 |
| --- | --- | --- |
| AI | Artificial Intelligence | 人工智能 |
| CBCT | Cone-Beam Computed Tomography | 锥形束计算机断层扫描 |
| EAES | European Association for Endoscopic Surgery | 欧洲内镜外科学会 |
| ICG | Indocyanine Green | 吲哚菁绿 |
| JPEG | Joint Photographic Experts Group | 联合图像专家组制定的静态图像压缩格式 |
| MP4 | MPEG-4 Part 14 | MPEG-4 第 14 部分定义的视频封装格式 |
| MRONJ | Medication-Related Osteonecrosis of the Jaw | 药物相关性颌骨骨坏死 |
| NIR-II | Near-Infrared Window II | 近红外二区光学窗口 |
| ROI | Region of Interest | 感兴趣区域，用于局部图像或信号定量 |
| SAM 2 | Segment Anything Model 2 | 面向图像与视频提示式分割的基础模型 |
| WSES | World Society of Emergency Surgery | 世界急诊外科学会 |

## 参考文献

[1] Bedogni A, Mauceri R, Fusco V, et al. Italian position paper (SIPMO-SICMF) on medication-related osteonecrosis of the jaw (MRONJ)[J]. Oral Diseases, 2024, 30(6): 3679-3709. DOI: 10.1111/odi.14887.

[2] Ko Y Y, Yang W F, Leung Y Y. The role of cone beam computed tomography (CBCT) in the diagnosis and clinical management of medication-related osteonecrosis of the jaw (MRONJ)[J]. Diagnostics, 2024, 14(16): 1700. DOI: 10.3390/diagnostics14161700.

[3] Cassinotti E, Al-Taher M, Antoniou S A, et al. European Association for Endoscopic Surgery consensus on indocyanine green (ICG) fluorescence-guided surgery[J]. Surgical Endoscopy, 2023, 37(3): 1629-1648. DOI: 10.1007/s00464-023-09928-5.

[4] Sutton P A, van Dam M A, Cahill R A, et al. Fluorescence-guided surgery: Comprehensive review[J]. BJS Open, 2023, 7(3): zrad049. DOI: 10.1093/bjsopen/zrad049.

[5] Preziosi A, Cirelli C, Waterhouse D, et al. State of the art medical devices for fluorescence-guided surgery (FGS): Technical review and future developments[J]. Surgical Endoscopy, 2024, 38(11): 6227-6236. DOI: 10.1007/s00464-024-11236-5.

[6] Wang H, Tang X, Ji T, et al. Efficacy of indocyanine green fluorescence-based near-infrared angiography in assessing intraoperative wound perfusion for bone and soft-tissue surgery[J]. Bone & Joint Open, 2025, 6(7): 796-806. DOI: 10.1302/2633-1462.67.bjo-2024-0248.r1.

[7] Tang Y, Jiang S, Elliott J T, et al. Intraoperative bone perfusion assessment using fluorescence imaging in a simulated fracture model[J]. Journal of Bone and Joint Surgery, 2025, 107(18): 2031-2039. DOI: 10.2106/JBJS.24.01436.

[8] Ray G S, Streeter S S, Bateman L M, et al. Real-time identification of life-threatening necrotizing soft-tissue infections using indocyanine green fluorescence imaging[J]. Journal of Biomedical Optics, 2024, 29(6): 066003. DOI: 10.1117/1.JBO.29.6.066003.

[9] De Simone B, Abu-Zidan F M, Boni L, et al. Indocyanine green fluorescence-guided surgery in the emergency setting: The WSES international consensus position paper[J]. World Journal of Emergency Surgery, 2025, 20: 13. DOI: 10.1186/s13017-025-00575-w.

[10] Chen P, Qu F, He L, et al. Quasi-dendritic sulfonate-based organic small molecule for high-quality NIR-II bone-targeted imaging[J]. Journal of Nanobiotechnology, 2023, 21: 230. DOI: 10.1186/s12951-023-01999-9.

[11] Spoelstra G B, Elsinga P H, van Dijl J M, et al. Vancomycin-based tracers guiding in situ visualization of bacteria on osteosynthesis devices and surgical debridement[J]. European Journal of Nuclear Medicine and Molecular Imaging, 2025, 52(10): 3877-3890. DOI: 10.1007/s00259-025-07249-4.

[12] Seets T, Selles A, Nunes J C, et al. Video denoising in fluorescence guided surgery[C]//Proceedings of the 27th International Conference on Artificial Intelligence and Statistics. 2024. Available: https://proceedings.mlr.press/v227/seets24a.html.

[13] Cheng H, Xu H, Peng B, et al. Illuminating the future of precision cancer surgery with fluorescence imaging and artificial intelligence convergence[J]. npj Precision Oncology, 2024, 8: 196. DOI: 10.1038/s41698-024-00699-3.

[14] Zhou T, Cheng Q, Lu H, et al. Deep learning methods for medical image fusion: A review[J]. Computers in Biology and Medicine, 2023, 160: 106959. DOI: 10.1016/j.compbiomed.2023.106959.

[15] Zubair M, Hussain M, Albashrawi M A, et al. A comprehensive review of techniques, algorithms, advancements, challenges, and clinical applications of multi-modal medical image fusion for improved diagnosis[J]. Computer Methods and Programs in Biomedicine, 2025, 272: 109014. DOI: 10.1016/j.cmpb.2025.109014.

[16] Chen J, Mei J, Li X, et al. TransUNet: Rethinking the U-Net architecture design for medical image segmentation through the lens of transformers[J]. Medical Image Analysis, 2024, 97: 103280. DOI: 10.1016/j.media.2024.103280.

[17] Wu J, Wang Z, Hong M, et al. Medical SAM adapter: Adapting segment anything model for medical image segmentation[J]. Medical Image Analysis, 2025, 102: 103547. DOI: 10.1016/j.media.2025.103547.

[18] Ma J, Li F, Wang B. U-Mamba: Enhancing long-range dependency for biomedical image segmentation[EB/OL]. (2024-01-09)[2026-07-30]. https://arxiv.org/abs/2401.04722.

[19] Ravi N, Gabeur V, Hu Y T, et al. SAM 2: Segment anything in images and videos[EB/OL]. (2024-08-01)[2026-07-30]. https://arxiv.org/abs/2408.00714.
