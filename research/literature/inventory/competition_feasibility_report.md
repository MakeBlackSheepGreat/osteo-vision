# 面向颌骨骨髓炎的智能化荧光诊疗方案

## 学校评估用阶段性可行性报告（更新版）

更新日期：2026-05-30

---

## 1. 赛题核心判断

本赛题要求提交一套面向颌骨骨髓炎术中辅助决策的完整技术方案，重点不是单独做一个医学影像模型，而是围绕企业已有口腔数字观察仪（可见光+荧光双通道）系统，形成"造影剂 + 多模态图像融合 + AI 辅助判读"的集成方案。赛题设置三个赛点：荧光图像伪彩色增强（赛点一）、基于目标检测/分割模型的智能辅助诊断（赛点二）、DICOM标准输出与远程协作（赛点三），可全做或选做。

结合赛题文件和文献调研，本题的核心难点是：颌骨骨髓炎病灶边界隐匿，坏死骨、炎症组织和潜在活性骨之间缺少稳定术中判别标准。ICG（吲哚菁绿）虽然成熟、安全、可用，但其主要反映血流灌注和血管通透性，不是颌骨骨髓炎特异性探针。因此，基础方案应把ICG定位为组织灌注/活性差异的术中信号，再通过白光-荧光融合、AI分割和不确定性提示提升判读稳定性。

**阶段性结论：建议参赛，应选择"基础可行demo"路线，不建议承诺新型特异性造影剂合成。最现实方案是直接使用企业已有ICG，做成术中白光/荧光融合与病灶风险边界提示系统。**

---

## 2. ICG造影剂可行性论证

### 2.1 ICG临床安全性与成熟度

吲哚菁绿（ICG）是一种水溶性三碳菁染料，自1956年起用于临床，已在全世界获得批准用于多种医疗应用[41]。EAES（欧洲内镜外科协会）2023年发布的ICG荧光手术共识声明指出："ICG荧光成像代表了一种有前景的、安全的、有效的手术技术"，并强调ICG"安全、无创、不良事件率低"[41]。

ICG的药理学特性使其非常适合术中应用：
- **快速代谢**：ICG与血浆蛋白（主要是白蛋白）结合后被肝脏快速吸收，半衰期3-5分钟，完全经胆汁排出[48]
- **近红外特性**：ICG在约800nm处达到最大吸收，发射荧光峰约835nm（820-840nm），这些特性使其可利用近红外（NIR）成像系统进行实时荧光引导[41]
- **剂量安全范围宽**：EAES共识指出，ICG最低组织灌注评估剂量为2.5-10mg，推荐单次剂量0.25-0.5mg/kg体重，最高可达2mg/kg[41]
- **给药时机灵活**：静脉注射后约10分钟开始成像，成像时间窗口3-5分钟[41]

### 2.2 ICG在骨科/颌面领域的文献支持

系统综述（Dhiman等，2022）分析了23项NIR-ICG灌注评估研究（452例患者），证明**NIR-ICG灌注评估对骨髓炎诊断和骨活力评估具有积极意义**[48]。关键发现包括：

**骨髓炎相关应用：**
- Naraghi等（2018）报告ICG荧光显示深部骨感染区域（骨髓炎），证明其可用于区分感染/坏死骨与正常骨组织[48]
- Kanayama等（2022）在感染性骨折不愈合手术中使用ICG灌注评估，用于判断骨活力[48]
- D🅅-Pérez等（2024）利用ICG在创伤性感染伤口中区分感染/坏死组织与健康组织[48]
- Matter等（2022）在开放性骨折中使用ICG评估骨灌注，研究区室综合征对骨灌注的影响[48]

**牙科/颌面直接证据：**
- Yoon等（2019）首次在体内验证ICG辅助近红外牙科成像的可行性，优化了成像条件，证明**ICG可用于口腔/牙科近红外成像场景**[52]
- Khandaker等（2022）开发ICG漱口液作为非侵入性递送方法用于近红外荧光牙科成像，证明**局部给药途径的可行性**[53]

**坏死/感染组织识别：**
- Goloborodko等（2024）在回顾性研究中使用SPY-PH成像系统（ICG近红外荧光成像）识别坏死性软组织感染（NSTI）：研究对115例患者分析显示，**所有存活感染组织在SPY成像中均显示荧光**，而所有坏死组织在评估时均无荧光，**ICG灌注与疾病严重程度和患者预后呈正相关**[49]

**骨灌注动力学模型：**
- Kang等（2019）开发了骨特异性ICG药代动力学模型，量化骨膜和内膜血流量，为**术中骨灌注的定量分析**提供了方法学基础[96]

### 2.3 ICG的局限性与本方案的应对策略

ICG的主要局限是**缺乏病灶特异性**——它反映的是血流灌注差异，而非骨髓炎的病理标志。这意味着ICG不能单独用于确诊骨髓炎。

本方案的应对策略是：将ICG荧光信号定位为**组织灌注/活性差异的术中参考信号**，而非确诊依据。通过以下方式弥补特异性不足：
1. **多模态融合**：将ICG信号与白光图像、术前CBCT/CT/MRI信息融合，提供解剖上下文
2. **AI辅助判读**：利用深度学习模型对荧光模式进行量化分析，减少主观判断偏差
3. **不确定性提示**：在边界模糊区域输出不确定性热图，提醒医生注意

这一策略的合理性得到了EAES共识的支持：共识指出ICG荧光成像"不应作为单一诊断工具"，而应结合其他临床信息综合判断[41]。

---

## 3. AI技术路线可行性论证

### 3.1 医学图像分割技术成熟度

本项目涉及的核心AI任务是**医学图像分割**——从显微镜图像中自动识别并标注病灶边界。该领域的技术已高度成熟，有多种经过大规模验证的开源框架可直接使用：

**基础分割框架：**

| 模型 | 发表/引用 | 核心能力 | 适用场景 | 代码可用性 |
|------|----------|---------|---------|-----------|
| U-Net [20] | 2015, 88277引 | 编码器-解码器+跳连 | 小样本医学分割基线 | 经典架构，全框架实现 |
| nnU-Net [21] | 2020 (Nature Methods), 8323引 | 自配置预处理/网络/训练策略 | 快速搭建可靠baseline | github.com/MIC-DKFZ/nnUNet |
| TransUNet [22] | 2021, 3825引 | Transformer编码器+U-Net | 边界模糊病灶（兼顾局部纹理与全局上下文） | github.com/Beckschen/TransUNet |
| Swin UNETR [23] | 2022 | Swin Transformer 3D分割 | 术前CBCT/MRI 3D分割 | github.com/Project-MONAI/research-contributions |
| UNETR [24] | 2022 (WACV), 2799引 | 纯Transformer 3D分割 | CT/CBCT/MRI体数据 | github.com/Project-MONAI/MONAI |
| MedSAM [26] | 2024 (Nature Communications), 2315引 | 医学图像通用分割基础模型 | 交互式ROI标注、少样本辅助 | github.com/bowang-lab/MedSAM |

**关键说明：nnU-Net**是一个自配置的分割框架，能够自动决定预处理、网络架构、训练策略和后处理方案，已被验证在医学分割基准上取得top性能[21]。本项目建议以nnU-Net作为首选baseline，因为它能在无人工调参的情况下快速搭建可靠的分割系统。

### 3.2 边界感知与不确定性量化——针对"病灶边界隐匿"的核心解法

赛题的核心难点是颌骨骨髓炎**病灶边界隐匿**，坏死骨、炎症组织和潜在活性骨之间没有清晰分界。本方案采用两类前沿技术来专门应对：

**（1）边界感知分割**

EGNet（2026）提出"边界-区域闭环"架构，通过双注意力边界检测模块（DABD）和区域边界交互模块（RBI）形成正反馈循环。在多个基准上的表现：

| 数据集 | Dice | IoU | HD95(mm) |
|--------|------|-----|----------|
| ISIC2018（皮肤病变，边界模糊） | **0.9164** | **0.8543** | **31.92** |
| Kvasir-SEG（息肉分割） | **0.9203** | **0.8638** | **27.60** | 
| CVC-ClinicDB（息肉分割） | **0.9360** | **0.8855** | **15.89** |

EGNet在所有测试数据集上均达到SOTA性能，证明其对模糊边界的处理能力[35]。

**（2）模糊粗糙集损失函数（FRS Loss）**

FRS Loss（2026）将模糊粗糙集理论引入深度学习损失函数，能同时处理边界模糊和类别不平衡。消融实验表明：

| 配置 | Dice | IoU | Precision | Recall |
|------|------|-----|-----------|--------|
| Baseline（BCE+Dice） | 0.7392 | 0.7113 | 0.7366 | 0.7817 |
| +FRS Loss | **0.7508** | **0.7157** | 0.7365 | **0.8050** |

FRS Loss在不牺牲精度的情况下显著提升召回率（+2.33%），这对于**确保不遗漏病灶区域**至关重要[36]。

**（3）不确定性量化**

Stochastic Segmentation Networks（2020）[32]可通过建模空间相关的偶然不确定性，将分割输出从硬分割（是/否）升级为**风险热图**（0-1连续值），直接对应"术中边界风险提示"需求。

本方案建议的技术组合：**nnU-Net + EGNet边界分支 + FRS Loss + 不确定性热图**。

### 3.3 口腔/颌骨AI——直接任务证据

**（1）颌骨骨髓炎分类（最直接证据）**

Ayoub等（2024）提出WaveletFusion-ViT模型，用**半监督学习**区分全景片中的成釉细胞瘤、根尖囊肿和**慢性化脓性骨髓炎**。在有限标注数据下取得：

| 指标 | 结果 |
|------|------|
| 平均精度 | 84.03% |
| F1分数 | 0.84 |
| 平均AUC | **0.9568** |
| 对比方法 | 超过12种其他方法 |

该研究直接证明：①口腔全景片中区分骨髓炎与良性肿瘤是可行的；②半监督学习可以有效应对标注数据不足的问题；③在小数据集（约140张图像）上也能取得有临床价值的性能[16]。

**（2）全景片骨溶解病灶检测**

Tuzoff等（2025）用CNN和视觉Transformer在全景片中自动检测和分类骨溶解病灶，能区分边界清晰和**边界不清**的病灶，这与本赛题"病灶边界隐匿"的需求直接相关[9]。

**（3）CBCT口腔病灶分割**

多项研究（P014, P024等）已验证深度学习在CBCT口腔病灶分割上的可行性，Dice系数在0.75-0.92范围。

### 3.4 影像组学对手术决策的支持

Zhang等（2024）发表于Frontiers的慢性骨髓炎MRI影像组学研究发现：**扩展ROI（包含病灶周围组织）比仅使用原始ROI有更好的诊断效果**，强调了病灶周边区域的临床决策价值[3]。

Liu等（2026）发表于BMC Medical Imaging的多中心研究（120例患者，五个中心）使用habitat imaging和影像组学指导慢性骨髓炎的**手术切除范围决策**，从"是否有病灶"推进到"如何确定手术切除边界"，证明AI辅助手术规划的可行性[4]。

---

## 4. 公开数据集基础

### 4.1 直接相关数据集

| 编号 | 数据集 | 模态 | 规模 | 用途 |
|------|--------|------|------|------|
| D025 | Dental Odontogenic Lesion CBCT + 病理 | CBCT + 组织病理 | 含牙源性病灶CBCT及病理标签 | 颌骨病灶分类/分割，**最接近骨髓炎任务** |
| D024 | DentVoxel | CBCT | 38种解剖结构实例标注 | 颌骨3D分割预训练 |
| D026 | Mandibular Canal Segmentation | CBCT | 下颌管分割标注 | 下颌管结构分割 |
| D005 | Mendeley下颌全景片分割 | 全景片 | 含下颌分割标注 | 下颌骨ROI提取 |
| D014 | HuggingFace全景片 | 全景片 | 约27900张 | 大规模全景片预训练 |

### 4.2 迁移学习数据集

| 类别 | 数据集 | 用途 |
|------|--------|------|
| 口腔AI | D001 DENTEX、D002 Tufts、D003儿童全景片、D004 OdontoAI(4K)、D015-D016 Kaggle | 全景片预训练、牙齿/颌骨定位 |
| 骨病灶 | D006 BTXRD骨肿瘤、D017骨折检测、D018 MURA肌骨(40K) | 骨病灶检测迁移学习 |
| 通用分割 | D007 MSD、D008 BraTS、D021 ISIC、D022 REFUGE、D023 PROMISE12 | 分割框架验证 |
| ICG/荧光 | D012/D035 OFDVDnet荧光手术视频 | 荧光视频去噪/增强 |
| 临床 | D013骨髓炎治疗、D033骨髓炎临床数据 | 临床背景支撑 |

### 4.3 数据集局限性与应对

**关键限制**：目前没有公开的"颌骨骨髓炎术中ICG荧光"数据集。

**应对策略**：
1. 使用牙科全景片数据集（D001-D005, D014-D016, 共3万+张）预训练口腔/颌骨检测与分割模型
2. 使用骨病灶数据集（D006, D017, D018）迁移学习骨病灶特征
3. 使用CBCT数据集（D024, D025, D026）预训练颌骨3D结构理解
4. **半监督学习**：参考WaveletFusion-ViT[16]的方法，在少量标注数据上用半监督策略训练
5. **数据增强**：通过模拟荧光图像（从白光图转换）和公开ICG手术视频（D012/D035）生成训练数据
6. 若学校决定参赛，应**尽早向企业或合作医院确认**是否可获得少量脱敏术中白光/荧光图像或视频

---

## 5. 推荐技术路线

### 5.1 总体方案

**方案名**：基于ICG荧光成像与多模态AI融合的颌骨骨髓炎术中辅助判读系统

**系统输入**：
- 术前影像：全景片、CBCT、CT或MRI，用于病灶粗定位和术前ROI
- 术中白光显微图像：提供真实组织结构、骨面形态和术野上下文
- 术中ICG荧光图像：提供灌注、血管通透性、潜在活性组织差异

**系统输出**：
- 白光/荧光配准叠加图（赛点一：伪彩色增强）
- 病灶疑似区分割或热图（赛点二：智能辅助诊断）
- 边界不确定性提示（风险区域量化）
- DICOM标准输出（赛点三：标准化与远程协作）

### 5.2 算法模块详解

**第一层：术前ROI建立**
- 使用全景片/CBCT上的口腔AI模型做颌骨区域、牙齿结构、骨病灶候选区提取
- 推荐模型：nnU-Net（自动配置，Dice 0.86-0.92）[21] 或 U-Net baseline
- 可用D005（全景片+下颌分割）、D024（牙科CBCT 38结构标注）预训练
- MedSAM[26]可用于交互式快速标注辅助

**第二层：术中白光/荧光融合**
- 白光和荧光通道进行显微视野配准
- 融合策略保留白光组织结构，同时突出ICG信号区域
- 参考多模态医学图像融合综述[33]中的像素级/特征级融合方法
- ICG荧光成像参数参考EAES共识[41]：激发波长780-805nm，发射波长835nm，给药后约10分钟开始成像，成像窗口3-5分钟

**第三层：病灶边界和风险提示**
- **基础分割**：nnU-Net（自动配置，快速可靠）
- **边界增强**：EGNet双注意力边界检测[35]（Dice 0.92，对模糊边界有专门优化）+ FRS Loss[36]（提升召回率+2.33%，确保不遗漏病灶）
- **不确定性输出**：Stochastic Segmentation Networks[32] 或 MC Dropout，输出边界风险热图
- **分类辅助**：参考WaveletFusion-ViT[16]的半监督方法（AUC 0.96），在有限标注数据下区分骨髓炎与其他病灶

**第四层：显微镜端呈现**
- 在显微图像上叠加透明热图、边界线和风险标签
- 输出MP4/JPEG结果，便于答辩演示
- 若无实时接口，可先完成离线视频demo，展示可集成性

### 5.3 竞赛评分匹配分析

| 评审维度 | 权重 | 本方案优势 |
|----------|------|-----------|
| 先进性 | 40% | EGNet边界感知分割（2026年SOTA）+ FRS模糊粗糙集损失 + 不确定性热图 + 半监督学习 |
| 可行性 | 30% | ICG已有CE认证和大量临床证据[41,48,49,52]；9个开源模型可直接使用；公开数据集可支撑预训练 |
| 完整度 | 20% | 覆盖术前ROI→术中融合→边界分割→风险提示→DICOM输出全链条 |
| 经济性 | 10% | ICG造影剂成本低（企业已有产品）；模型使用开源框架；无需专用硬件 |

---

## 6. 最低可行作品形态

若只有公开数据和现有文献，最低可行作品可以是：

1. **完整技术方案报告**（含文献综述、技术路线、可行性论证）
2. **Python/Gradio平台软件**
   - 输入：全景片/CBCT/白光图/荧光图
   - 输出：融合图、病灶热图、边界不确定性图
3. **算法验证**：使用D024/D025 CBCT数据训练颌骨分割模型，使用D001-D005全景片数据训练术前ROI模型
4. **ICG文献支撑**：引用P048骨灌注综述、P041 EAES共识、P052牙科ICG可行性、P055显微镜ICG AI等论文
5. **公开数据演示**：使用公开牙科/骨病灶数据和模拟荧光图完成完整流程演示

若能拿到企业或医院样本，作品竞争力会明显提高：
- 至少10-30例术中白光/ICG图像或视频
- 至少有医生标注的坏死骨/病灶边界/保留区
- 有一两个实际病例展示术前影像、术中荧光和AI输出的一致性

---

## 7. 参赛收益与风险

### 收益

- 题目方向有临床痛点，且与企业口腔数字观察仪产品结合度高
- ICG造影剂安全性已被EAES共识确认[41]，骨灌注评估有系统综述支撑[48]，牙科成像可行性已验证[52]
- 9个核心模型有开源代码，可快速搭建baseline
- D024/D025公开CBCT数据集支撑颌骨分割预训练
- P016已证明全景片上区分骨髓炎与其他颌骨病灶的可行性（AUC 0.96）[16]
- AI + 荧光成像 + 术中决策辅助的组合有展示效果

### 风险

- ICG不具备颌骨骨髓炎特异性，不能把它包装成精准靶向造影剂——本方案已将其定位为灌注/活性提示
- 公开数据缺少"颌骨骨髓炎术中荧光"真实样本——通过迁移学习和半监督学习缓解
- 如果没有企业/医院数据，作品会偏方案和平台软件——建议尽早争取少量脱敏样本
- 实时成像接入可能受设备接口限制——先用离线视频demo展示可集成性

---

## 8. 学校侧决策建议

**建议参赛条件**：
- 学校能组织影像算法、口腔/颌面医学、平台软件三类成员
- 能接受基础方案以ICG为主，不承诺新探针合成
- 能尽快联系企业争取少量脱敏样本或技术交流
- 能在比赛截止前完成报告、平台软件、文献综述和演示材料

**不建议参赛的情况**：
- 学校要求必须做新型靶向造影剂合成
- 完全拿不到任何企业或医院样本，且团队无法做出可视化平台软件
- 团队只有算法成员，没有医学老师或口腔/颌面方向顾问

**综合判断**：这题可以打，但应以"ICG基础造影剂 + AI多模态显微判读"的工程方案切入。短期目标不是证明ICG能特异识别颌骨骨髓炎，而是证明在企业现有平台上，ICG荧光信号可以被稳定采集、融合、量化，并通过AI转化为术中可读的边界风险提示。

---

## 9. 当前资料包内容

### 论文（61篇，全部有PDF）

| 类别 | 数量 | 代表文献 |
|------|------|---------|
| 病种影像 | 8 | P001 MRI纹理分析骨髓炎、P004多中心影像组学[4]、P005多模态比较 |
| 口腔AI | 11 | P009全景片骨溶解检测[9]、P016半监督骨髓炎分类[16]、P018牙齿检测 |
| 模型方法 | 17 | P021 nnU-Net[21]、P022 TransUNet[22]、P026 MedSAM[26]、P035 EGNet[35]、P036 FRS Loss[36] |
| ICG荧光 | 16 | P041 EAES共识[41]、P048骨灌注综述[48]、P052牙科ICG[52]、P055显微镜ICG AI[55] |
| AI方法 | 7 | P070 DL骨髓炎诊断、P076 ML纹理分析 |
| 相关方法 | 2 | P071荧光引导评估、P081慢性骨髓炎荧光成像 |

### 数据集（35个）
- 直接相关（颌骨/口腔）：5个（D024 DentVoxel、D025牙源性病灶CBCT+病理、D026下颌管、D005下颌分割、D014全景片）
- 迁移学习用：30个（口腔AI 8个、骨/感染12个、ICG/荧光2个、口腔其他8个）

### 可用开源模型（9个）
nnU-Net、TransUNet、Swin UNETR、UNETR、MedSAM、Medical SAM Adapter、EGNet、FRS Loss、Retuve

---

## 10. 参考文献

[3] Zhang et al. Optimizing diagnosis and surgical decisions for chronic osteomyelitis through radiomics in the precision medicine era. Front Bioeng Biotechnol, 2024.

[4] Liu et al. A multicenter study: habitat imaging and radiomics to guide precision and individualized surgical treatment in chronic osteomyelitis. BMC Med Imaging, 2026.

[9] Tuzoff et al. Automated detection and classification of osteolytic lesions in panoramic radiographs using CNNs and vision transformers. BMC Oral Health, 2025.

[16] Ayoub et al. Classification of Ameloblastoma, Periapical Cyst, and Chronic Suppurative Osteomyelitis with Semi-Supervised Learning: The WaveletFusion-ViT Model Approach. Bioengineering, 2024.

[20] Ronneberger et al. U-Net: Convolutional Networks for Biomedical Image Segmentation. MICCAI, 2015.

[21] Isensee et al. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nature Methods, 2020.

[22] Chen et al. TransUNet: Transformers Make Strong Encoders for Medical Image Segmentation. arXiv, 2021.

[23] Hatamizadeh et al. Swin UNETR: Swin Transformers for Semantic Segmentation of Brain Tumors in MRI Images. arXiv, 2022.

[24] Hatamizadeh et al. UNETR: Transformers for 3D Medical Image Segmentation. WACV, 2022.

[26] Ma et al. Segment anything in medical images. Nature Communications, 2024.

[32] Monteiro et al. Stochastic Segmentation Networks: Modelling Spatially Correlated Aleatoric Uncertainty. arXiv, 2020.

[33] Bhosale et al. A Review of Multimodal Medical Image Fusion Techniques. Comput Math Methods Med, 2020.

[35] Wang et al. EGNet: A boundary-region closed-loop network for medical image segmentation with fuzzy lesions. Biomed Signal Process Control, 2026.

[36] Furkh et al. Fuzzy rough set loss for deep learning-based precise medical image segmentation. Comput Med Imaging Graph, 2026.

[41] Dip et al. European Association for Endoscopic Surgery (EAES) consensus on Indocyanine Green (ICG) fluorescence-guided surgery. Surg Endosc, 2023.

[48] Dhiman et al. Near-Infrared Fluorescence with Indocyanine Green to Assess Bone Perfusion: A Systematic Review. Life, 2022.

[49] Grumme et al. Real-time identification of life-threatening necrotizing soft-tissue infections using indocyanine green fluorescence imaging. J Biomed Opt, 2024.

[52] Yoon et al. Indocyanine-green-assisted near-infrared dental imaging: the feasibility of in vivo imaging. Sci Rep, 2019.

[53] Khandaker et al. Mouthwash as a non-invasive method of indocyanine green delivery for near-infrared fluorescence dental imaging. J Biomed Opt, 2022.

[55] Li et al. Deep-Learning-Based Cerebral Artery Semantic Segmentation in Neurosurgical Operating Microscope Vision Using Indocyanine Green Fluorescence Videoangiography. Front Neurorobot, 2022.

[96] Kang et al. Bone-specific kinetic model to quantify periosteal and endosteal blood flow using indocyanine green in fluorescence guided orthopedic surgery. J Biophotonics, 2019.
