# 1.5 国内外技术研究现状（整合修订版）

> 本版采用“近期研究为主、必要基础文献保留”的引用策略。2023-2025 年文献用于描述当前技术状态；早期文献仅用于 ICG 光学机制、经典配准方法、直接骨灌注研究或当前方法的原始出处。所有结论保持术中辅助和医生复核边界。

## 1.5 国内外技术研究现状

近三年，颌骨近域临床研究主要围绕 MRONJ 的诊疗路径、CBCT 评估、手术范围和复发影响因素展开[27-28]；术中荧光研究则持续向 ICG 定量、骨灌注时序分析、设备能力规范、视频 AI 处理和多模态融合发展[3,10,20-26]。公开研究仍缺少真实术中颌骨骨髓炎同步白光/ICG 视频、医生像素级标注与统一临床阈值。本项目平台将荧光信号定位为灌注、组织活性与风险提示参考，并通过医生复核与证据包实现可追溯的研发验证闭环。

## 1.5.1 荧光造影与术中导航

### 1. ICG 在外科的临床应用

吲哚菁绿（ICG）是临床应用较成熟的近红外荧光造影剂，静脉注射后主要与血浆蛋白结合，可用于显示组织灌注、血管通透性和血流动力学变化[1-2]。目前，ICG 荧光成像已应用于血管评估、组织灌注判断、淋巴示踪和荧光引导手术等场景；EAES 共识强调成像设备、给药方案、观察时相和临床任务会共同影响结果解释[3]。近期设备综述及 ICG 定量综述进一步指出，荧光信号的临床转化需要同时记录设备性能、采集条件和定量方法[10,22]。

在骨组织及口腔颌面应用方面，国外研究已探索 ICG 对游离腓骨瓣松质骨灌注、开放骨科手术骨灌注及骨活性的动态评估[5-6,8-9]。2025 年的骨及软组织手术研究报告了 ICG 近红外血管造影用于术中伤口灌注评估的经验[20]；模拟骨折模型研究进一步量化了截骨与骨膜破坏后的灌注变化[21]。国内学者 Xia 等开展了 ICG 定位双膦酸盐相关性颌骨坏死受累骨组织的可行性研究，但样本和疾病范围有限，尚不足以建立颌骨骨髓炎的通用判别阈值[7]。

ICG 荧光信号受局部血流、血管通透性、给药剂量、观察时相、相机距离、成像角度及设备响应等因素共同影响[1-4,10]。炎症区域可因充血和血管通透性增加呈现较高信号；缺血或坏死骨可因灌注下降呈现较低信号。由此形成的信号差异难以直接对应“健康骨、炎症骨、坏死骨”三类组织。ICG 适宜作为灌注和组织活性参考信号，颌骨骨髓炎疾病特异性仍需进一步验证。

Michi 等的系统综述纳入 10 项骨灌注研究，其中人体研究 4 项、前瞻性人体研究 1 项；各研究在设备、剂量、分析参数和阈值方面存在较大异质性，客观参数的临床意义尚未获得充分验证[6]。因此，当前研究重点正在从单纯肉眼观察转向荧光定量、时序曲线分析、多模态融合和医生复核辅助[10,20-23]。

### 2. 新型荧光造影剂与骨/感染靶向探索

在候选探针方向，近年研究正在由通用灌注信号延伸至骨亲和和细菌识别模块。TTQF-SO3 的研究提出了 NIR-II 骨靶向有机小分子，并报告了羟基磷灰石亲和性与动物骨成像结果[29]。万古霉素示踪剂研究则在取出骨科内固定装置和清创场景中探索革兰阳性菌相关信号的原位可视化[30]。这些工作可为“骨亲和模块 + 感染识别模块 + 发光模块”的候选探针架构提供设计依据；其颌骨适配性、活体给药安全性、药代动力学、死骨与活骨区分能力及当前显微镜光谱匹配仍需分阶段验证。

## 1.5.2 医学图像智能分析

多模态医学图像处理早期主要采用互信息配准、特征匹配和可变形配准等方法，实现不同模态之间的空间对齐与信息融合[11-13]。近年来，医学图像分析逐渐发展为基于深度学习的分割、检测、概率预测和交互式标注。2023 年和 2025 年综述系统整理了深度学习医学图像融合的网络结构、评价指标、临床应用与转化限制，可为白光/ICG 配准、归一化、伪彩、融合和质量控制提供方法学参考[24-25]。

在分割方法方面，nnU-Net 提供了自配置医学图像分割基线[14]，MedNeXt 探索了卷积网络的尺度扩展能力[15]，MedSAM 将提示式基础模型引入医学图像分割[16]；Medical SAM Adapter 进一步展示了通用分割基础模型向医学任务的适配路线[26]。在显微镜 ICG 视频分析方面，Kim 等利用深度学习对神经外科显微镜 ICG 血管造影视频进行脑动脉语义分割，证明了“显微镜视频、ICG 信号、自动分割”的工程可行性[17]。该任务对象为脑血管，与颌骨骨髓炎存在目标域差异，不能直接代表颌骨病灶识别性能。

U-Mamba 和 SAM 2 可用于说明长程依赖建模及视频提示式分割的发展趋势[18-19]。荧光成像与人工智能融合的近期综述也强调，应将图像质量、模型可解释性、临床工作流和人机协作共同纳入系统设计[23]。这些模型和方法当前应作为候选技术路线或辅助标注工具，后续仍需使用真实白光/ICG 成对数据、颌骨组织标注及患者级独立验证评估其适用性。

## 1.5.3 当前研究空白

1. 缺少颌骨骨髓炎特异性的荧光探针及经临床验证的荧光判别阈值。
2. 真实术中白光/ICG 同步数据和医生标注规模有限，公开研究多为骨灌注、颌骨坏死或其他外科近域场景[5-9,20-21,27-28]。
3. 荧光信号容易受到炎症反应、组织遮挡、设备参数和观察时相影响，需要结合白光结构信息、时序特征和质量控制[3,10,22]。
4. 现有通用分割模型缺少面向颌骨骨髓炎的独立临床验证，医生复核、不确定性提示和证据追溯仍需完善[14-19,23-26]。

本项目据此构建“官方 JPEG/MP4 输入 - 荧光处理与多模态融合 - AI 候选区、风险与不确定性提示 - 医生复核 - 结构化证据输出”的软件闭环。该闭环服务于工程验证和术中辅助参考，临床诊断与清创范围的最终判断由医生完成。

## 参考文献

[1] Desmettre T, Devoisselle J M, Mordon S. Fluorescence properties and metabolic features of indocyanine green (ICG) as related to angiography[J]. Survey of Ophthalmology, 2000, 45(1): 15-27. DOI: 10.1016/S0039-6257(00)00123-5.

[2] Alander J T, Kaartinen I, Laakso A, et al. A review of indocyanine green fluorescent imaging in surgery[J]. International Journal of Biomedical Imaging, 2012, 2012: 940585. DOI: 10.1155/2012/940585.

[3] Cassinotti E, Al-Taher M, Antoniou S A, et al. European Association for Endoscopic Surgery consensus on indocyanine green fluorescence-guided surgery[J]. Surgical Endoscopy, 2023, 37(3): 1629-1648. DOI: 10.1007/s00464-023-09928-5.

[4] D'Souza A V, Lin H, Henderson E R, et al. Review of fluorescence guided surgery systems: Identification of key performance capabilities beyond indocyanine green imaging[J]. Journal of Biomedical Optics, 2016, 21(8): 080901. DOI: 10.1117/1.JBO.21.8.080901.

[5] Fichter A M, Ritschl L M, Georg R, et al. Effect of segment length and number of osteotomy sites on cancellous bone perfusion in free fibula flaps[J]. Journal of Reconstructive Microsurgery, 2019, 35(2): 108-116. DOI: 10.1055/s-0038-1667364.

[6] Michi M, Madu M, Winters H A H, et al. Near-infrared fluorescence with indocyanine green to assess bone perfusion: A systematic review[J]. Life, 2022, 12(2): 154. DOI: 10.3390/life12020154.

[7] Xia C W, Pan J R, Fan L, et al. The feasibility of locating the affected bone of BRONJ with indocyanine green[J]. Oral Diseases, 2020, 26(5): 1086-1089. DOI: 10.1111/odi.13299.

[8] Gitajn I L, Elliott J T, Gunn J R, et al. Evaluation of bone perfusion during open orthopedic surgery using quantitative dynamic contrast-enhanced fluorescence imaging[J]. Biomedical Optics Express, 2020, 11(11): 6458-6469. DOI: 10.1364/BOE.399587.

[9] Han X, Demidov V, Vaze V S, et al. Spatial and temporal patterns in dynamic-contrast enhanced intraoperative fluorescence imaging enable classification of bone perfusion in patients undergoing leg amputation[J]. Biomedical Optics Express, 2022, 13(6): 3171-3186. DOI: 10.1364/BOE.459497.

[10] Pollmann L, Juratli M, Roushansarai N, et al. Quantification of indocyanine green fluorescence imaging in general, visceral and transplant surgery[J]. Journal of Clinical Medicine, 2023, 12(10): 3550. DOI: 10.3390/jcm12103550.

[11] Maes F, Collignon A, Vandermeulen D, et al. Multimodality image registration by maximization of mutual information[J]. IEEE Transactions on Medical Imaging, 1997, 16(2): 187-198. DOI: 10.1109/42.563664.

[12] Sotiras A, Davatzikos C, Paragios N. Deformable medical image registration: A survey[J]. IEEE Transactions on Medical Imaging, 2013, 32(7): 1153-1190. DOI: 10.1109/TMI.2013.2265603.

[13] James A P, Dasarathy B V. Medical image fusion: A survey of the state of the art[J]. Information Fusion, 2014, 19: 4-19. DOI: 10.1016/j.inffus.2013.12.002.

[14] Isensee F, Jaeger P F, Kohl S A A, et al. nnU-Net: A self-configuring method for deep learning-based biomedical image segmentation[J]. Nature Methods, 2021, 18(2): 203-211. DOI: 10.1038/s41592-020-01008-z.

[15] Roy S, Koehler G, Ulrich C, et al. MedNeXt: Transformer-driven scaling of ConvNets for medical image segmentation[C]//Medical Image Computing and Computer Assisted Intervention. Cham: Springer, 2023: 405-415. DOI: 10.1007/978-3-031-43901-8_39.

[16] Ma J, He Y, Li F, et al. Segment anything in medical images[J]. Nature Communications, 2024, 15: 654. DOI: 10.1038/s41467-024-44824-z.

[17] Kim M S, Cha J H, Lee S, et al. Deep-learning-based cerebral artery semantic segmentation in neurosurgical operating microscope vision using indocyanine green fluorescence videoangiography[J]. Frontiers in Neurorobotics, 2022, 15: 735177. DOI: 10.3389/fnbot.2021.735177.

[18] Ma J, Li F, Wang B. U-Mamba: Enhancing long-range dependency for biomedical image segmentation[EB/OL]. (2024-01-09)[2026-07-28]. https://arxiv.org/abs/2401.04722.

[19] Ravi N, Gabeur V, Hu Y T, et al. SAM 2: Segment anything in images and videos[EB/OL]. (2024-08-01)[2026-07-28]. https://arxiv.org/abs/2408.00714.

[20] Wang H, Tang X, Ji T, et al. Efficacy of indocyanine green fluorescence-based near-infrared angiography in assessing intraoperative wound perfusion for bone and soft-tissue surgery[J]. Bone & Joint Open, 2025, 6(7): 796-806. DOI: 10.1302/2633-1462.67.bjo-2024-0248.r1.

[21] Tang Y, Jiang S, Elliott J T, et al. Intraoperative bone perfusion assessment using fluorescence imaging in a simulated fracture model[J]. Journal of Bone and Joint Surgery, 2025, 107(18): 2031-2039. DOI: 10.2106/JBJS.24.01436.

[22] Preziosi A, Cirelli C, Waterhouse D, et al. State of the art medical devices for fluorescence-guided surgery (FGS): Technical review and future developments[J]. Surgical Endoscopy, 2024, 38(11): 6227-6236. DOI: 10.1007/s00464-024-11236-5.

[23] Cheng H, Xu H, Peng B, et al. Illuminating the future of precision cancer surgery with fluorescence imaging and artificial intelligence convergence[J]. npj Precision Oncology, 2024, 8: 196. DOI: 10.1038/s41698-024-00699-3.

[24] Zhou T, Cheng Q, Lu H, et al. Deep learning methods for medical image fusion: A review[J]. Computers in Biology and Medicine, 2023, 160: 106959. DOI: 10.1016/j.compbiomed.2023.106959.

[25] Zubair M, Hussain M, Albashrawi M A, et al. A comprehensive review of techniques, algorithms, advancements, challenges, and clinical applications of multi-modal medical image fusion for improved diagnosis[J]. Computer Methods and Programs in Biomedicine, 2025, 272: 109014. DOI: 10.1016/j.cmpb.2025.109014.

[26] Wu J, Wang Z, Hong M, et al. Medical SAM adapter: Adapting segment anything model for medical image segmentation[J]. Medical Image Analysis, 2025, 102: 103547. DOI: 10.1016/j.media.2025.103547.

[27] Bedogni A, Mauceri R, Fusco V, et al. Italian position paper (SIPMO-SICMF) on medication-related osteonecrosis of the jaw (MRONJ)[J]. Oral Diseases, 2024, 30(6): 3679-3709. DOI: 10.1111/odi.14887.

[28] Ko Y Y, Yang W F, Leung Y Y. The role of cone beam computed tomography (CBCT) in the diagnosis and clinical management of medication-related osteonecrosis of the jaw (MRONJ)[J]. Diagnostics, 2024, 14(16): 1700. DOI: 10.3390/diagnostics14161700.

[29] Chen P, Qu F, He L, et al. Quasi-dendritic sulfonate-based organic small molecule for high-quality NIR-II bone-targeted imaging[J]. Journal of Nanobiotechnology, 2023, 21: 230. DOI: 10.1186/s12951-023-01999-9.

[30] Spoelstra G B, Elsinga P H, van Dijl J M, et al. Vancomycin-based tracers guiding in situ visualization of bacteria on osteosynthesis devices and surgical debridement[J]. European Journal of Nuclear Medicine and Molecular Imaging, 2025, 52(10): 3877-3890. DOI: 10.1007/s00259-025-07249-4.
