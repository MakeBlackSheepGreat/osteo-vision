# 模型训练数据来源与近期训练路线（中文）

生成日期：2026-07-03

## 1. 当前结论

本项目的训练数据不能只从公开 3D CBCT 数据集里找答案。赛题官方设备给软件输入的是 4K MP4 视频和 JPEG 图片，AI 训练路线应拆成两条再汇合：

1. **术中白光/ICG 视频与图片线**：来自官方设备或后续企业/医院脱敏样本，是比赛系统最终要处理的目标域。现阶段主要用于上传、质控、关键帧抽取、医生 ROI 标注、伪彩增强和病例证据输出；在没有医生标注前，不应直接宣称可训练临床级病灶分割模型。
2. **术前/辅助 CBCT 结构与病灶线**：使用 D024、D025、D036 等公开 CBCT 数据训练颌骨、牙齿、下颌管和病灶代理分割模型，形成解剖先验和病灶候选能力。它能支撑赛点二的 AI 判读能力，但不能替代术中 ICG 标注。

因此，近期最稳妥的模型策略是：**CBCT 上用 nnU-Net/SegResNetDS 做解剖与病灶代理基线；术中 MP4/JPEG 上先做关键帧、ROI、MedSAM/SAM2 辅助标注与轻量 ConvNeXt/2D 分割平台验证；最后在报告层做晚期融合，而不是一开始做端到端多模态诊断模型。**

## 2. 已有本地数据基础

| 数据源 | 本地状态 | 当前用途 | 训练价值 | 边界 |
|---|---:|---|---|---|
| D024 DentVoxel | 已处理，100 例清单 | 颌骨、牙齿、下颌管等解剖结构 | 训练 3D anatomy prior，辅助 ROI 裁剪 | 非骨髓炎、非 ICG |
| D025 DOLCHID lesion CBCT | 已处理，262 例清单 | 牙源性病灶 CBCT + 病理代理 | 最接近“颌骨病灶分割/分类”的公开数据 | 不是颌骨骨髓炎，也不是术中视频 |
| D036 ToothFairy2 | 已处理，480 例清单 | 42 类牙颌 CBCT 多结构分割 | 强解剖先验与 nnU-Net 基线 | 需避免把 anatomy Dice 当病灶性能 |
| D042 MODID | 本地目录存在，当前 0 文件 | 口腔多光谱图像候选 | 可做光谱/颜色域增强参考 | 需重新下载与核验许可 |
| D044 FGS video | 本地目录存在，当前 0 文件 | 荧光手术视频去噪候选 | 可迁移到 ICG 视频增强/去噪 | 非口腔、非骨髓炎，需下载后确认 |

本地报告依据：

- `research/reports/preprocessing/public_cbct_datasets_preprocessing_summary_zh.md`
- `research/reports/modeling/public_cbct_3dataset_segmentation_benchmark_zh.md`
- `research/reports/modeling/osteo_vision_foundation_segmentation_model_design_zh.md`
- `research/reports/planning/official_technical_document_alignment_zh.md`

## 3. 外部来源核验要点

| 来源 | 核验信息 | 对本项目的帮助 |
|---|---|---|
| DentVoxel | Figshare 页面说明其包含 100 个大视野 CBCT，38 个实例级解剖标签，包括上颌、下颌、上颌窦、下颌管和 32 颗牙。 | 适合作为颌骨/牙齿/神经管结构预训练数据。 |
| ToothFairy2 | 挑战和论文材料显示其是 CBCT 多结构分割任务，含 42 类专家 3D 标注；nnU-Net ResEnc L 方案在公开材料中表现很强。 | 适合作为正式 3D 结构分割基线和 nnU-Net 训练范式依据。 |
| DOLCHID | Scientific Data/Figshare 说明包含 4 类牙源性病灶、CBCT 分割 mask 和病理 ROI。 | 当前最适合做颌骨病灶代理任务，优先训练 lesion cascade。 |
| MRONJ CBCT nnU-Net 研究 | 公开 PMC 文章显示 nnU-Net v2 可用于 MRONJ 病灶 CBCT 自动分割可行性验证。 | 方法高度相关，但样本集未确认公开，适合作方法论参考。 |
| OFDVDnet / FGS 视频数据 | Dryad/PMLR 材料说明其面向荧光引导手术视频去噪，包含 ICG/mock surgery 相关数据与模型。 | 可迁移到赛点一的视频去噪、弱荧光增强、伪彩稳定性。 |
| MODID / ODSI-DB | MODID 为 16 波段口腔多光谱疾病图像；ODSI-DB 为口腔/牙科光谱图像并有专家标注。 | 支持“口腔光谱/多光谱图像 AI 可行性”论证，但不是 ICG 830 nm 数据。 |

## 4. 训练数据来源优先级

### P0：真实目标域数据

来源：

- 官方设备导出的 4K MP4。
- 官方设备 JPEG 图片。
- 后续企业/医院脱敏术中白光/ICG 样本。
- 医生标注的关键帧 ROI、坏死骨/可疑边界、保留区、不确定区。

用途：

- 训练和评估术中 2D/视频模型。
- 校准 ICG 强度归一化、阈值和颜色映射。
- 建立病例级证据链和失败样本库。

最低标注协议：

| 字段 | 说明 |
|---|---|
| `case_id` | 脱敏病例编号 |
| `source_file` | MP4/JPEG 本地路径或归档 ID |
| `frame_index` / `timestamp_sec` | 视频关键帧定位 |
| `channel` | white_light / fluorescence / overlay / video |
| `icg_time_sec` | 给药后或显影相关时间，未知则留空 |
| `roi_mask_path` | 医生 ROI 或 AI 辅助后修订 mask |
| `label` | viable、suspected_necrotic、boundary_risk、uncertain、background |
| `review_state` | accepted / modified / rejected / review_required |
| `notes` | 医生备注、伪影、出血、烟雾、遮挡等 |

### P1：公开 CBCT 解剖与病灶代理数据

近期直接使用：

- D024 + D036：训练 5 类或多类牙颌结构分割，得到颌骨 ROI、牙齿、下颌管等先验。
- D025：训练 lesion mask 二分类或多分类代理，验证病灶检测/分割链路。

推荐训练顺序：

1. D024/D036 先做 5 类解剖先验：上颌、下颌、上牙、下牙、下颌管。
2. D025 做 ROI-crop lesion cascade，loss 用 Dice+Focal 或 Tversky+Focal。
3. nnU-Net v2 ResEnc 作为正式可靠基线；SegResNetDS/UXNet/ConvNeXt3D 作为项目可控候选。

### P2：公开荧光/多光谱/手术视频数据

可下载和核验：

- D044 FGS Video Denoising / OFDVDnet：服务视频去噪、低信噪比荧光增强、伪彩稳定。
- D042 MODID：口腔多光谱疾病图像，可做口腔光谱分割/分类参考。
- ODSI-DB：口腔/牙科光谱数据库，可做光谱分割方法参考。

边界：

- 这些数据不能替代 ICG 颌骨骨髓炎术中数据。
- 主要用于图像增强、域适配、颜色/光谱鲁棒性和方法论论证。

### P3：其他公开牙科影像数据

全景片、根尖片、口腔黏膜 RGB 数据可用于通用口腔视觉预训练、病例报告多模态检索或界面演示，但它们与赛题核心的“4K MP4/JPEG + ICG + 颌骨骨髓炎术中辅助判读”距离更远，不应放在主线训练优先级前面。

## 5. 模型训练路线

### 路线 A：CBCT 3D 基线

目标：形成稳定的颌骨结构和病灶代理分割能力。

配置建议：

- 主基线：nnU-Net v2 3D fullres / ResEnc。
- 可控候选：MONAI SegResNetDS、SwinUNETR Tiny、3D UXNet/ConvNeXt3D proxy。
- 数据：D024、D025、D036 的本地 derived manifest。
- 指标：Dice、IoU、HD95、NSD、Sensitivity、Precision；小结构单独报告。

短期验收：

- D024/D036：从 64³ smoke 转向高分辨率 patch。
- D025：先保证非零 Dice 和可控 sensitivity，再用阈值/连通域过滤提升 precision。

### 路线 B：术中 MP4/JPEG 2D/视频平台验证

目标：贴合官方设备输入，先把训练数据生产链建起来。

配置建议：

- 关键帧抽取：已接入均匀采样，后续增加医生指定时间点和荧光峰值采样。
- 辅助标注：MedSAM/SAM2 用于医生快速勾 ROI，输出需医生复核。
- 轻量模型：ConvNeXt 可做帧级质量/风险分类；2D U-Net/DeepLab/SegFormer 可做 ROI mask 平台验证。
- 视频增强：先接 OFDVDnet/FGS 思路做低信噪比荧光稳定化，不先做临床诊断。

短期验收：

- 每个上传 MP4 自动生成关键帧和元数据。
- 每个关键帧可绑定 ROI mask、医生标签和复核状态。
- 输出病例证据包时包含关键帧路径、帧号、时间戳和免责声明。

### 路线 C：晚期融合

第一阶段不建议直接训练“CBCT + ICG 视频端到端诊断模型”。更稳妥的融合方式是：

1. CBCT 模型给出解剖 ROI 和病灶代理候选。
2. ICG/JPEG 模型给出帧级荧光强度、灌注异常和边界风险提示。
3. 报告层或医生工作台并排展示二者，由医生复核。
4. 等真实配对病例足够后，再考虑多模态 transformer 或时序融合模型。

## 6. 下一步任务

1. 建立 `official_video_keyframe_manifest.csv`，把 MP4 上传文件、关键帧、帧号、时间戳、分辨率和预览路径记录下来。
2. 给前端关键帧增加医生 ROI 标注入口，先保存 JSON/mask，不急于训练。
3. D025 lesion 继续作为病灶代理主线，优先跑高分辨率 ROI crop + nnU-Net/SegResNetDS。
4. D024/D036 先合并成 5 类解剖任务，给术中分析提供下颌/上颌 ROI 先验。
5. 重新下载并核验 D042、D044；若下载成本过高，先只作为报告中“增强与多光谱参考”，不纳入本轮训练。
6. 准备真实数据采集模板：病例脱敏表、文件命名规范、医生标注规范、复核状态和数据使用授权。

## 7. 医学与比赛表述边界

- ICG 反映血流灌注、血管通透性和组织活性差异，不是颌骨骨髓炎特异性探针。
- D024/D036 是解剖结构数据，D025 是牙源性病灶代理数据，不能直接写成“颌骨骨髓炎临床训练集”。
- 真实目标域训练必须依赖脱敏术中 MP4/JPEG、医生标注和病例级复核。
- 比赛报告中可表述为“AI 辅助提示、候选区、边界风险和医生复核”，不表述为自动确诊。

## 8. 参考链接

- 官方技术文档对齐：`research/reports/planning/official_technical_document_alignment_zh.md`
- DentVoxel: https://figshare.com/articles/dataset/DentVoxel_a_fully_annotated_dental_CBCT_dataset_with_38_instance_anatomical_structures/31239889
- ToothFairy2: https://toothfairy2.grand-challenge.org/
- Scaling nnU-Net for CBCT Segmentation: https://arxiv.org/abs/2411.17213
- DOLCHID dataset: https://springernature.figshare.com/articles/dataset/Dental_Odontogenic_Lesion_CBCT_and_Histopathology_Integrated_Dataset_for_Benchmarking_Deep_Learning_Algorithms/30156622
- MRONJ CBCT nnU-Net study: https://pmc.ncbi.nlm.nih.gov/articles/PMC13077929/
- FGS video denoising dataset: https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9
- OFDVDnet paper: https://proceedings.mlr.press/v227/seets24a.html
- MODID: https://datadryad.org/dataset/doi%3A10.5061/dryad.nvx0k6dxw
- ODSI-DB: https://sites.uef.fi/spectral/databases-software/odsi-db/
