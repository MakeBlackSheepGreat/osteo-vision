# 荧光手术 / 骨髓炎视频数据集补充检索

生成日期：2026-07-03

## 1. 检索结论

本轮检索没有发现可直接用于本项目的“颌骨骨髓炎 ICG 荧光手术 MP4 数据集”。更现实的公开数据形态分为三类：

1. **可下载的荧光手术视频数据集**：主要是模拟手术或非口腔场景，适合训练视频去噪、弱荧光增强、伪彩稳定和 MP4 管线，不适合训练颌骨骨髓炎诊断模型。
2. **骨/感染/骨髓炎相关 ICG 荧光临床研究**：高度相关，但目前看到的是论文、临床试验协议或补充图像，未发现开放 MP4 数据下载。
3. **颌骨骨坏死/颌骨骨髓炎荧光引导手术文献**：医学场景最接近，但多为自体荧光、四环素荧光或 VELscope 临床研究，数据通常未公开或需联系作者，未发现公开视频数据集。

因此，项目不能把模型路线押在“公开颌骨骨髓炎荧光 MP4 数据集”上。可执行路线应改为：公开荧光视频用于赛点一和视频预处理；公开骨/感染 ICG 研究用于医学依据；真实目标域不足时用公开 CBCT、少量医院 CBCT 和 CBCT 派生伪视频支撑赛点二原型。

## 2. 候选数据源分级

| 等级 | 数据/来源 | 可获得性 | 内容 | 对项目的作用 | 限制 |
|---|---|---|---|---|---|
| A | Dryad FGS video denoising dataset | 可下载，约 34 GB | OnLume Avata 系统采集的 ICG 模拟鸡腿手术视频、低剂量 ICG、无 ICG 激光泄漏、校准数据和训练模型 | 最适合作为本项目公开视频数据；可训练去噪、增强、伪彩和三视图拆分 | 模拟鸡腿，不是口腔/颌骨/骨髓炎 |
| A | OFDVDnet Dryad dataset | 可下载，约 50 个视频、约 100 分钟 | 鸡腿模拟荧光引导手术；包含 reference、fluorescence、overlay 三视图 | 可做白光/荧光/叠加三通道管线和视频增强基线 | 模拟数据，不是疾病数据 |
| B | NCT04245111 / Dartmouth ICG fracture-infection study | 临床研究，未发现开放视频 | 骨/软组织灌注、感染、骨髓炎清创，ICG 视频速率采集约 4 分钟 | 医学依据强，可作为论文/方案论证和潜在作者联系对象 | 当前未公开原始 MP4 |
| B | Real-time NSTI ICG fluorescence study | 论文开放，未发现原始视频开放 | 14 例软组织感染，含 1 例 osteomyelitis，展示白光与 ICG 快照、参数图和 ROI | 感染 + ICG 灌注异常证据，可借鉴信号空洞、SBR、时间强度曲线 | 不是颌骨；没有开放视频数据 |
| B | Bone perfusion ICG systematic review | 文献开放 | 总结骨灌注 ICG 研究，指出视频记录通常 3-4 分钟，证据有限 | 支撑“ICG 主要是灌注/活性信号”的医学边界 | 不是数据集 |
| C | MRONJ/ORNJ fluorescence-guided surgery studies | 文献开放或摘要可见 | 自体荧光、四环素荧光、VELscope 颌骨手术 | 场景接近颌骨骨坏死/骨髓炎，可用于方法和报告论证 | 多数数据不开放，常需联系作者；不是 ICG MP4 |
| C | Zenodo rectal neoplasia ICG video study | 记录开放，但文件只有论文 PDF | 190 个 ICG 内镜视频用于直肠肿瘤灌注分析 | 证明 ICG 视频 AI 管线存在临床应用 | 不提供视频文件；部位完全不同 |

## 3. 可下载数据优先级

### 3.1 Dryad FGS video denoising dataset

- 链接：https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9
- DOI：https://doi.org/10.5061/dryad.8gtht76x9
- 规模：34 GB。
- 格式特点：README 描述为 triple view 视频，包含 reference、fluorescence、false-color overlay；全视频为 2048x1536、15 fps，每个 quadrant 为 1024x768。
- 内容：mock chicken thigh surgery、低浓度 ICG、无 ICG 激光泄漏、phantom 校准、真实噪声和训练模型。
- 本项目用途：
  - 视频上传和关键帧抽取压力测试。
  - 白光/荧光/叠加视图拆分。
  - ICG 低信噪比视频去噪。
  - 伪彩增强稳定性。
  - 作为“没有真实口腔视频时”的公开荧光视频代理。
- 不能做的事：不能作为颌骨骨髓炎病灶分割标签。

### 3.2 OFDVDnet dataset

- 链接：https://datadryad.org/dataset/doi%3A10.5061/dryad.v6wwpzh3w
- 代码：https://github.com/WillianJrLin/OFDVDnet
- 论文：https://proceedings.mlr.press/v227/seets24a.html
- 内容：约 50 个视频，约 100 分钟，mock chicken thigh surgery；每个视频含 fluorescence、reference 和 overlay。
- 本项目用途：
  - 作为赛点一“荧光图像伪彩增强/视频增强”的最直接公开基线。
  - 可把 reference 视作白光，fluorescence 视作 ICG，overlay 视作伪彩融合目标或参考输出。
- 限制：不是骨，也不是感染或口腔。

## 4. 高相关但未开放原始 MP4 的来源

### 4.1 骨/感染 ICG 研究

- NCT04245111 协议：Fluorescence Imaging to Guide Debridement of Fracture and Infection。
- 协议显示研究对象包括骨折、感染和需要清创/开窗的 osteomyelitis；ICG 注射后采集视频速率荧光图像约 4 分钟。
- 价值：这是目前检索到的“骨/感染/骨髓炎 + ICG 荧光 + 手术清创”最接近的数据来源。
- 问题：公开页面目前是协议和论文，不是公开视频数据集。若比赛时间允许，可尝试联系 Dartmouth/论文作者申请研究样本或合作。

### 4.2 软组织感染 ICG 研究

- 论文：Real-time identification of life-threatening necrotizing soft-tissue infections using indocyanine green fluorescence imaging。
- 论文样本含 14 例，包含 1 例 osteomyelitis；报告白光、ICG 快照、参数图、ROI 和 SBR。
- 价值：可作为“感染区域灌注缺损/信号空洞”的医学依据。
- 问题：仍未开放原始视频。

### 4.3 颌骨骨坏死/颌骨骨髓炎荧光引导手术

可用作方法依据的方向：

- osteoradionecrosis of the jaw fluorescence-guided surgery。
- MRONJ autofluorescence/tetracycline fluorescence-guided surgery。
- diffuse chronic sclerosing osteomyelitis of the mandible with VELscope。

价值：

- 与颌骨坏死、骨髓炎和术中边界判断最接近。
- 支持“荧光可辅助坏死骨/活骨边界”的报告表述。

问题：

- 多数不是 ICG，而是自体荧光、四环素/米诺环素荧光或 VELscope。
- 没有发现开放 MP4 数据集；部分研究数据声明为联系作者获取或未公开。

## 5. 对本项目的直接策略

### 路线一：公开视频代理

先下载 Dryad FGS/OFDVDnet，转换出：

- `reference.mp4`
- `fluorescence.mp4`
- `overlay.mp4`
- `keyframes/*.jpg`
- `manifest.csv`

用于：

- 前端/后端 MP4 输入演示。
- 荧光视频增强、去噪和伪彩增强。
- 赛点一的可视化和工程证据。

### 路线二：骨/感染论文证据

整理 NCT04245111、NSTI ICG、骨灌注 ICG systematic review 作为医学依据：

- ICG 是灌注和组织活性信号。
- 骨/感染清创场景确实有人用 ICG 视频速率荧光。
- 但公开数据缺失，必须保留原型边界。

### 路线三：CBCT 派生伪视频

对公开 CBCT 和 4-5 例医院 CBCT 生成：

- axial/coronal/sagittal cine MP4。
- ROI fly-through MP4。
- 3D volume-rendering rotation MP4。

用途：

- 让系统保持官方 MP4 输入形式。
- 训练和展示 3D 病灶/解剖模型时有视频接口。
- 作为比赛演示桥接，不包装为真实术中 ICG 视频。

## 6. 近期行动建议

1. 优先下载 Dryad `10.5061/dryad.8gtht76x9` 和 `10.5061/dryad.v6wwpzh3w`，本地只保留到 ignored 数据目录，不进 Git。
2. 写三视图视频拆分脚本：从 2048x1536 triple view 中切出 reference、fluorescence、overlay。
3. 对 D025 和医院 4-5 例 CBCT 生成 cine MP4，补齐官方 MP4 输入演示。
4. 建立 `video_dataset_candidate_inventory.csv`，字段包括数据类型、是否 ICG、是否骨/感染、是否口腔、是否可下载、能否训练、能否只作演示。
5. 将赛点二改成“CBCT 病灶代理 + ICG 视频灌注/增强代理 + 医生复核”，避免承诺真实 ICG 骨髓炎分割。

## 7. 参考链接

- Dryad FGS video denoising dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9
- OFDVDnet Dryad dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.v6wwpzh3w
- OFDVDnet code: https://github.com/WillianJrLin/OFDVDnet
- OFDVDnet paper: https://proceedings.mlr.press/v227/seets24a.html
- Video Denoising in Fluorescence Guided Surgery: https://arxiv.org/abs/2411.09798
- NCT04245111 protocol: https://clinicaltrials.gov/study/NCT04245111
- NCT04245111 PDF protocol: https://cdn.clinicaltrials.gov/large-docs/11/NCT04245111/Prot_SAP_000.pdf
- Real-time NSTI ICG fluorescence study: https://pmc.ncbi.nlm.nih.gov/articles/PMC11092151/
- Bone perfusion ICG systematic review: https://www.mdpi.com/2075-1729/12/2/154
- ORNJ fluorescence-guided surgery: https://journals.sagepub.com/doi/abs/10.1177/03000605221104186
- DCSO mandible VELscope paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC4628814/

## 8. 非颌骨骨髓炎公开视频补充

用户进一步明确“不局限颌骨，先找骨髓炎视频”。本轮补充检索发现：公开可下载的骨髓炎视频主要是 PMC 论文补充视频和手术技术视频，不是成体系训练数据集。它们可用于系统 MP4 输入、关键帧抽取、术式演示和小样本原型，但缺少像素级标注，不能直接作为监督分割训练集。

| 来源 | 场景 | 视频状态 | 对项目价值 | 限制 |
|---|---|---|---|---|
| Surgical Debridement for Acute and Chronic Osteomyelitis in Children | 儿童急/慢性骨髓炎清创技术 | PMC 页面含多段可下载 MP4 | 骨髓炎清创真实手术/技术视频，最适合做“骨髓炎公开视频”演示素材 | 儿童长骨为主；无 ICG；无分割标注 |
| Biportal Endoscopic Intramedullary Debridement for Management of Tibial Osteomyelitis | 胫骨骨髓炎双通道内镜髓腔清创 | PMC 页面含 `mmc1.mp4` | 与骨髓炎清创和骨腔处理高度相关；可作为 MP4 输入与关键帧测试 | 无荧光、非颌骨、单例/技术视频 |
| Phalangeal Reaming and Irrigation for Combined Proximal and Distal Phalangeal Osteomyelitis of the Thumb | 拇指指骨骨髓炎扩髓冲洗 | PMC 页面含 `mmc1.mp4` | 小骨骨髓炎处理视频，和颌骨小骨结构比长骨更接近 | 无 ICG，病例量极少 |
| Treatment for Calcaneal Osteomyelitis with Pseudoarthrosis | 跟骨骨髓炎伴假关节重建 | PMC 页面含手术补充 MP4 | 骨感染重建视频，可做异域骨髓炎视频参考 | 不适合训练颌骨模型 |
| Tuberculous osteomyelitis of the maxilla | 上颌结核性骨髓炎病例 | PMC 页面含两个 FLV 视频 | 目前发现的少数“上颌骨髓炎”视频资料，场景接近颌骨 | FLV 格式，病例报告，非 ICG，需转码 |
| Mucormycotic osteomyelitis following ACL reconstruction | ACL 重建后真菌性骨髓炎 | PMC 页面含 3 个 MP4 | 骨感染/骨髓炎病例视频，可用于扩充公开视频素材 | 与口腔距离远 |
| Tibialization of Fibula for Large Segment Tibia Loss Following Chronic Osteomyelitis | 慢性骨髓炎后胫骨大段缺损重建 | PMC 页面含 MP4 | 可做慢性骨髓炎后重建场景参考 | 非 ICG、非诊断数据 |
| Metacarpal osteomyelitis following cat bite | 猫咬伤后掌骨骨髓炎 | PMC 页面含 MP4 | 小骨骨髓炎公开视频，适合格式和关键帧演示 | 非颌骨、无标注 |
| Abscess pulsatility: a sonographic sign of osteomyelitis | 骨髓炎超声征象 | PMC 页面含 MP4 | 可作“骨髓炎影像视频”补充，非手术但与诊断相关 | 超声视频，不是白光/荧光手术视频 |

### 8.1 可直接优先下载的骨髓炎视频

建议先下载以下 3 类，规模相对小、项目相关度高：

1. 儿童急/慢性骨髓炎清创技术视频：`https://pmc.ncbi.nlm.nih.gov/articles/PMC10807896/`
2. 胫骨骨髓炎内镜髓腔清创视频：`https://pmc.ncbi.nlm.nih.gov/articles/PMC12350196/`
3. 拇指指骨骨髓炎扩髓冲洗视频：`https://pmc.ncbi.nlm.nih.gov/articles/PMC12147590/`

这些视频的用途是补充“骨髓炎公开视频输入”和“手术清创场景理解”，不是训练 ICG 荧光分割模型。若要纳入训练，只能先作为无标签视频做自监督预训练、关键帧抽取、质量控制或医生再标注样本。

### 8.2 数量与荧光属性核查

按 PMC 页面中可下载的原始补充视频文件计数，不重复计算页面里的 streaming duplicate，本轮确认的骨髓炎相关公开视频共 **25 个文件**，其中 **23 个 MP4 + 2 个 FLV**。这些骨髓炎视频均为 **非荧光视频**；本轮未发现“骨髓炎 + ICG/荧光 + 可下载原始视频”。

| 来源 | 视频数 | 格式 | 是否荧光 | 类型 |
|---|---:|---|---|---|
| Surgical Debridement for Acute and Chronic Osteomyelitis in Children | 14 | MP4 | 否 | 骨髓炎清创手术技术 |
| Biportal Endoscopic Intramedullary Debridement for Management of Tibial Osteomyelitis | 1 | MP4 | 否 | 胫骨骨髓炎内镜清创 |
| Phalangeal Reaming and Irrigation for Thumb Osteomyelitis | 1 | MP4 | 否 | 小骨骨髓炎扩髓冲洗 |
| Treatment for Calcaneal Osteomyelitis with Pseudoarthrosis | 1 | MP4 | 否 | 跟骨骨髓炎重建 |
| Tuberculous osteomyelitis of the maxilla | 2 | FLV | 否 | 上颌骨髓炎病例视频 |
| Abscess pulsatility: a sonographic sign of osteomyelitis | 1 | MP4 | 否 | 骨髓炎超声诊断视频 |
| Mucormycotic osteomyelitis following ACL reconstruction | 3 | MP4 | 否 | 真菌性骨髓炎病例视频 |
| Tibialization of Fibula for Large Segment Tibia Loss Following Chronic Osteomyelitis | 1 | MP4 | 否 | 慢性骨髓炎后骨缺损重建 |
| Metacarpal osteomyelitis following cat bite | 1 | MP4 | 否 | 掌骨骨髓炎病例视频 |

另外，真正属于荧光手术视频的数据源目前是异域代理数据：

| 来源 | 视频数/时长 | 是否荧光 | 与骨髓炎关系 |
|---|---:|---|---|
| OFDVDnet Dryad dataset | 50 个原始视频，约 100 分钟；论文训练切片约 590 个 100-frame clips | 是，ICG 模拟荧光手术，含 reference/fluorescence/overlay 三视图 | 非骨髓炎、非口腔 |
| Dryad FGS video denoising dataset / OL-2024 | 公开页面描述约 130 分钟新 mock surgical video，另含非荧光 LLL、校准和真实噪声数据 | 是，含荧光视频，也含非荧光/校准组件 | 非骨髓炎、非口腔 |
