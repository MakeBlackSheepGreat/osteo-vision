---
title: "面向颌骨骨髓炎的智能化荧光诊疗完整技术方案"
subtitle: "赛题编号 HT-202604 | Osteo Vision 颌骨骨髓炎智能化荧光诊疗平台"
author: "参赛技术方案"
date: "2026-07-11"
---

## 摘要

本方案围绕企业荧光手术显微镜，形成“候选近红外造影剂设计、白光/荧光多模态处理、AI 辅助显微判读、4K JPEG 单帧处理、MP4 视频链路、医生复核与证据输出”的完整技术路线。平台接收企业影像系统产生的 JPEG 图片和 MP4 视频，通过通道质控、配准、荧光增强、伪彩融合、关键帧分析、动态时间强度曲线、多 mask 风险提示和医生复核，生成结构化 JSON、量化 CSV、截图、报告与病例证据包。当前已验证公开低分辨率长 MP4 和公开源派生 4K JPEG；企业 3840×2160 MP4 仍待样片测试。

造影剂部分提出 `BP-PEG-HCy7-PEG-Vanco` 模块化候选：双膦酸/膦酸端提供羟基磷灰石亲和，万古霉素端提供革兰阳性菌细胞壁与生物膜识别，七甲川菁近红外发光端面向企业 ICG 检测窗口设计。该候选目前属于文献支持的分子设计和逐级验证方案，尚无本项目合成、光谱、生物学、安全性或实机实验结果。ICG 用作灌注基线；四环素荧光和骨自发荧光用作坏死骨边界机制、对照组和未来多光谱扩展依据。

软件工程证据来自公开非目标域视频、代理标注、公开 CBCT 和合成压力样本。现有指标用于证明架构、训练、推理、4K 处理和证据导出链路可运行，不能解释为真实术中 ICG 颌骨骨髓炎临床性能。平台输出定位为荧光/灌注信号候选区、骨面待复核门控、边界风险、不确定性和医生复核辅助。

## 1. 官方要求与总体目标

### 1.1 官方一手资料

本方案依据两份本地一手资料编制：

1. `HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf`。
2. `research/literature/inventory/official/competition_official_technical_document_20260527.pdf`。

完整赛题要求同时覆盖三项内容：

1. 面向颌骨骨髓炎病灶精准示踪的新型荧光造影剂设计。
2. 白光通道、荧光通道等多源图像的获取、配准、融合和术中显示。
3. 结合白光与荧光信息的 AI 病灶识别和辅助判读，以叠加提示、风险标注或决策辅助形式呈现。

官方设备边界为 3840×2160 的 4K 摄录系统、USB3.0 存储、JPEG 图片与 MP4 视频。企业资料给出的 ICG 激发范围约为 750–810 nm，发射波长约为 830 nm。

### 1.2 评审标准映射

| 评审项 | 分值 | 已交付证据 | 尚缺证据 |
|---|---:|---|---|
| 创新性 | 20 | 骨矿物亲和、感染识别、近红外发光三模块候选；双通道 AI；多 mask；动态量化 | 化学新颖性检索、实物结构和同类探针对照实验 |
| 科学合理性 | 20 | 文献机制、对照设计、无泄漏划分、分层证据和医学边界 | 候选结构图、反应路线评审和定量湿实验 |
| 可行性 | 30 | 4K JPEG 单帧、公开长 MP4、多帧率、回退、adapter、验证矩阵 | 企业 4K MP4、原始双通道、滤光片和目标硬件实测 |
| 应用价值 | 20 | 候选区、边界风险、关键帧复核、量化曲线和证据包 | 医生工作量、复核时间和临床流程改进数据 |
| 完整性 | 10 | 三项核心方案、Word/PDF、证据索引、复现命令和外部资料清单 | 报名表与最终提交压缩包冻结 |

## 2. 临床问题与方案定位

颌骨骨髓炎、放射性颌骨骨坏死和药物相关性颌骨坏死均存在病灶边界隐匿、坏死骨与炎症组织及活性骨难以稳定区分的问题。ICG 主要反映血流灌注、血管通透性和组织活性差异，局部炎症、充血、水肿、出血、工作距离和曝光参数均会影响信号。

平台提供以下术中参考信息：

- 白光与荧光配准和融合图。
- 荧光/灌注信号候选区 `fluorescence_signal_mask`。
- 医生或 prompt-assisted 生成并待复核的 `bone_gate_mask`。
- 综合信号、边界和时序稳定性的 `risk_mask`。
- 模型过度不确定、通道缺失、时序跳变或域外输入对应的 `uncertain_mask`。
- 背景扣除、归一化时间强度曲线、达峰时间、上升斜率、AUC 和曲线质量。

所有输出均需医生复核。真实目标域病例、医生像素级标注和前瞻性临床验证尚未取得。

## 3. 新型荧光造影剂设计方案

### 3.1 主候选结构

主候选暂命名为 `BVN-800`，A0 版冻结拓扑为：

`Sulfo-HCy7-PEG4-Lys[PEG4-succinyl-alendronate]-CO-NH-Vanco`

其中骨亲和端固定采用阿仑膦酸模块，感染识别端采用万古霉素，发光端采用带磺酸基的水溶性七甲川菁骨架，两个功能臂均采用 PEG4 间隔。拟采用 `Fmoc-Lys(Alloc)-OH` 或同等正交保护的支化赖氨酸作为连接核心。按模块分子量估算，A0 候选约为 2.8-3.2 kDa，整体预计带多负电荷；准确分子式、净电荷和分子量需在供应商原料与连接位点冻结后由化学团队计算。

推荐从可合成性较高的分步路线推进：

1. 以正交保护赖氨酸支架分别暴露 α-氨基、ε-氨基和羧基反应位点。
2. 一条 PEG4 臂连接 succinyl-alendronate，形成阿仑膦酸骨矿物亲和端。
3. 第二条 PEG4 臂连接水溶性 sulfo-HCy7 发光端，目标光谱优先覆盖约 770-830 nm。
4. 支架羧基经活化后与万古霉素可用氨基偶联；该连接位点需通过细菌结合实验确认 D-Ala-D-Ala 识别是否保留。
5. 以 HPLC、LC-MS、高分辨质谱和必要的 NMR 完成纯度及结构确认。

该结构用于形成“骨表面定位 + 革兰阳性菌相关感染信号”的候选富集机制。分子尺寸、空间位阻、血浆蛋白结合、非特异吸附和组织清除均可能削弱双重识别，需要逐级实验筛选。

### 3.2 设计依据

| 模块 | 设计依据 | 当前证据等级 | 主要风险 |
|---|---|---|---|
| 骨亲和端 | 膦酸化近红外荧光团可与羟基磷灰石结合并用于骨成像 | 文献证据 | 亲和过强可能造成健康骨背景升高 |
| 感染识别端 | Vanco-800CW 可结合革兰阳性菌细胞壁和相关生物膜，已有植入感染及取出内固定物研究 | 文献与外部临床样本研究 | 对革兰阴性菌覆盖不足，死菌也可能保留结合信号 |
| 发光端 | 七甲川菁类染料可覆盖约 800 nm 近红外窗口，便于向 ICG 通道适配 | 文献和设备参数 | 候选峰值与企业滤光片可能错配 |
| 亲水间隔臂 | PEG 可降低位阻和疏水聚集风险 | 通用化学设计依据 | 可能影响药代与背景清除 |

Vanco-800CW 的外部研究表明，其适合革兰阳性菌和生物膜成像。IRDye800CW 常用光谱峰约为 Ex 778 nm、Em 794 nm。2022 年取出内固定物研究分别使用 IVIS 710 nm 激发与 ICG 发射滤光片，以及术中相机 760 nm 激发与 819/44 nm 发射滤光片；这些参数属于不同设备配置。企业约 830 nm 检测窗口能否覆盖 BVN-800，需要滤光片透过曲线和候选实测光谱共同确认。颌骨骨髓炎可能为多菌种感染，候选方案需要纳入革兰阴性菌、厌氧菌和无菌性骨坏死对照。

### 3.3 外部定量证据摘要

| 研究 | 外部样本与结果 | 本方案用途 |
|---|---|---|
| Vanco-800CW 取出内固定物研究 | 13 名患者、59 件取出装置；染色与成像流程将结果时间缩短至 30 分钟内；研究同时记录革兰阴性菌覆盖和金标准不足等限制 | 感染识别端、术中相机适配和菌种对照设计 |
| 2025 年 ONJ 骨自发荧光病理研究 | 22 名患者、56 份样本；35 份低荧光样本均为坏死骨；21 份高荧光样本中 18 份为正常活骨 | 坏死骨边界机制、病理对照和出血质控 |
| 2017 年 MRONJ 随机可行性研究 | 比较自发荧光与四环素荧光引导骨切除 | 对照组和未来蓝光通道扩展 |
| ICG 骨灌注系统综述 | 汇总近红外 ICG 骨灌注应用，强调成像协议和量化异质性 | ICG 灌注基线和动态曲线边界 |
| 膦酸化近红外骨成像研究 | 支持膦酸化荧光团对骨矿物的亲和与体内骨成像 | 阿仑膦酸/膦酸骨亲和端依据；具体 HAp 定量仍待复核 |

以上数据均来自外部文献。本项目当前提供设计论证和验证矩阵，官方要求中的原创实验数据仍需化学、微生物、光学和企业团队补齐。

### 3.4 ICG、四环素与骨自发荧光的角色

- **ICG**：承担企业设备灌注基线、软件动态量化和融合基线。可显示血流灌注与组织活性变化；缺少颌骨骨髓炎特异性，信号受成像条件影响。
- **四环素荧光**：承担活性骨标记机制、对照组和未来蓝光通道扩展。文献支持坏死骨与活性骨边界提示；典型激发位于约 390-430 nm，与 ICG 通道不一致。
- **骨自发荧光**：承担无外源药物对照和坏死骨边界机制。2025 年 56 份样本研究中低荧光样本均对应坏死骨，86% 高荧光样本对应正常活骨；出血、血红蛋白吸收和骨硬化可能干扰解释。

### 3.5 逐级验证矩阵

1. **化学确认**：对合成产物检查纯度、分子量、结构和批间一致性。纯度与结构通过后进入光谱实验。责任方为化学实验团队。
2. **光谱与稳定性**：在 PBS、血清和不同 pH 条件下测量吸收/激发/发射峰、量子产率、光漂白、聚集和 24 h 稳定性。晋级条件为峰值覆盖企业通道且背景可控。责任方为化学与光学团队。
3. **骨矿物结合**：使用羟基磷灰石、去矿化骨和健康骨片测量结合率、洗脱、目标背景比和竞争抑制。相对 dye-only 对照出现可重复增益后晋级。责任方为实验团队。
4. **细菌选择性**：覆盖金葡菌、表皮葡萄球菌、链球菌、革兰阴性菌和厌氧菌，报告结合强度、CFU 归一化信号、生物膜信号和死菌干扰。责任方为微生物团队。
5. **骨感染模型**：比较感染骨片、无菌坏死骨、健康骨和炎症软组织。候选信号需要与培养及组织学形成可解释关联。责任方为医院与实验团队。
6. **安全性**：检查细胞毒性、溶血、局部刺激、药代和器官分布，满足后续伦理与转化要求。责任方为实验与伦理团队。
7. **组织仿体**：在 NIR 组织仿体和分层骨仿体中测量检测限、线性、深度、均匀性、SNR 和空间分辨率，建立设备参数与可检测浓度范围。责任方为企业与光学团队。
8. **企业显微镜**：使用原始白光/NIR 双通道检查曝光、增益、工作距离、滤光片透过、串扰和连续稳定性，形成实机参数锁定与重复性记录。责任方为企业团队。

当前团队可以完成候选结构、对照组、实验设计、数据字段和软件分析模板。实物合成、湿实验、安全性和企业实机结果需要外部协作。

## 4. 白光/荧光多模态融合与处理

### 4.1 输入与通道获取

平台优先支持官方边界内的 4K JPEG 与 MP4。理想设备接口提供：

- 原始白光帧与原始 NIR 荧光帧分别导出。
- 两通道统一时间戳、帧率或硬件同步信号。
- 曝光、增益、光源功率、倍率、工作距离和滤光片信息。
- ICG 注射剂量、注射时刻和必要的病例协议字段。

若设备仅输出合成 overlay，平台仍可完成视频管理、关键帧分析和证据导出；荧光绝对量化、真实双通道配准和双通道 AI 的证据强度会降低。

### 4.2 标定与配准

1. 静态标定：使用双波段可见标记或多光谱标定板，求取白光/NIR 相机内参、畸变和通道间单应/外参。
2. 动态残差校正：采用互信息、ECC 或稠密光流处理轻微组织运动和机械漂移。
3. 质量门控：记录重投影误差、互信息增益、有效重叠率和边缘错位；超阈值时显示配准警告并回退为并排显示。
4. 坐标保持：4K 图像缩放或 tiling 推理后，将 mask、候选框和 ROI 精确映射回 3840×2160 原始坐标。

### 4.3 荧光增强、融合与定量

软件处理顺序为：

`输入质控 -> 背景估计 -> 强度归一化 -> 荧光伪彩 -> 白光/荧光配准 -> 透明度融合 -> ROI 量化 -> 时间曲线 -> 质量标记`

动态曲线必须使用解码帧或医生 ROI 内的图像强度统计。当前 MP4/JPEG 链路采用固定 8-bit luminance 强度域，并在结构化输出中记录来源与单位域。取得企业原始 NIR 通道后，该字段才具备原始荧光强度含义。分割概率只用于候选区和不确定性，禁止写入强度字段。至少两个有效且时间戳不同的关键帧时计算：

- 每帧 P95 强度与背景强度。
- 背景扣除强度。
- 基线到峰值归一化信号。
- 达峰时间 `time_to_peak_sec`。
- 最大归一化上升斜率。
- 归一化 AUC。
- 重复时间戳、动态范围不足、关键帧稀疏等曲线质量字段。

跨病例比较需要锁定曝光、增益、照明、工作距离、倍率、注射剂量和注射时刻。协议不完整时，曲线仅用于病例内相对变化。

### 4.4 4K 显示与运行策略

平台采用双速管线：

- 原始 4K 视频由浏览器正常播放。
- AI 在抽取关键帧、缩放帧或 ROI 上异步运行。
- 超过整帧像素阈值时自动启用 patch/tiling。
- 推理失败时保留传统荧光增强、融合和人工 ROI 流程。
- UI 同步显示最近关键帧的 mask、候选区、时间戳和复核状态。

该模式统一表述为 `keyframe-based playback analysis`。目标硬件完成持续基准前，不声明 4K 全帧 30 FPS AI。

## 5. AI 辅助显微成像判读

### 5.1 输出契约

| 输出 | 含义 | 复核边界 |
|---|---|---|
| `fluorescence_signal_mask` | 荧光/灌注信号候选区 | 反映图像信号，不代表疾病终判 |
| `bone_gate_mask` | 暴露骨区域门控 | 医生或 prompt-assisted 生成；未复核时标记 `review_required` |
| `risk_mask` | 融合信号强度、边界与时序稳定性的风险提示 | 用于复核排序和术中参考 |
| `uncertain_mask` | 预测熵、TTA 方差、通道缺失、时序跳变和域外风险 | 高不确定区域优先人工检查 |

### 5.2 数据分层与无泄漏评估

| 数据层 | 当前用途 | 可支持结论 | 禁止扩展的结论 |
|---|---|---|---|
| 公开荧光手术视频 | 去噪、融合、时序、视频工程、代理分割 | 软件链路和相对算法比较 | 颌骨骨髓炎目标域性能 |
| 公开骨感染/坏死视频 | 场景理解和演示复核 | 接近病种的视觉工程证据 | ICG 特异性和像素金标准 |
| 公开 CBCT | 上下颌解剖分割和三维证据 | 术前解剖工程能力 | 术中空间导航或病灶真值 |
| prompt-assisted mask | 多 mask 训练种子 | 标注工作流和模型闭环 | 医生金标准 |
| 后续医生小金标准 | 关键帧评估和校准 | 受限目标域性能 | 大规模临床有效性 |

所有视频帧先按 `source_video_id` 或 `case_id` 分组，再划分 train/val/test。阈值只在验证集选择，测试集用于独立报告。指标包括 Dice、IoU、Boundary F1、空 mask 率、过分割率、ECE、Brier 和视频源级 bootstrap 置信区间。

当前分层数据注册表共 504 条记录，覆盖公开荧光视频、骨髓炎手术视频、代理/半自动 mask、D047 颌骨荧光论文图和 D048 开放临床骨荧光近域图，质量错误为 0，训练准入候选 393 条，目标域记录数为 0。D047/D048 静态复核队列现有 61 条可操作记录：9 条已有原子面板裁剪和自动候选 mask，另外 14 张多面板原图已拆分为 52 条可追溯裁剪建议。52 条建议包括 19 条荧光信号、13 条配对白光、13 条配对荧光和 7 条病理面板，形成 14 个配对 ID；40 条通过自动质量门，12 条保留警告。全部建议和自动 seed 均保持 `review_required`、`training_eligible=false`，医生 mask 数量仍为 0。热点代理已扩展为 192 条、48 个来源视频组的 grouped manifest，train/val/test 组级泄漏为 0；边界风险、不确定性和 exposed-bone 代理继续分层保留。训练准入区分 `proxy_pretrain`、`reviewed_finetune` 与 `independent_evaluation`，代理或待复核标签无法进入后两档。

平台 `/dataset-review` 静态数据复核工作台直接加载 61 条可操作记录。自动建议以橙色虚线显示，当前裁剪以绿色实线显示；复核人员可接受建议或保存修改，并确认面板类型、白光/荧光 `pair_id` 和配对可信度。后端检查裁剪边界、最小尺寸、面积比例、长宽比、近整图、边框残留和建议身份；保存后仍保持 mask 待复核和训练禁入。原子面板进入自动 seed 和原始像素比例二值 mask 编辑。seed 与 reviewed manifest 保留来源、许可、来源组、权重及双 checksum，并接入分层注册表默认构建路径。当前尚未提交真实人工 mask。

### 5.3 模型组合

1. 主线关键帧模型：`convnext2d_keyframe_proxy_segmenter`，负责稳定输出荧光信号候选区、概率图、风险和不确定性。
2. 多 mask 候选：`video_signal_multimask`，独立输出 fluorescence 与 bone gate 两个头；bone gate 保持 `review_required`，通过晋级门槛后方可替换主线能力。
3. 双通道候选：白光编码器学习骨面、器械和纹理，荧光编码器学习强度与灌注特征，中间或早期融合后输出候选区。
4. 传统回退：阈值、形态学、伪彩、人工 ROI 和医生复核在 AI 不可用时继续运行。

当前双通道训练中的白光来自源图亮度代理，四组消融用于验证架构与接口。后端必须同时满足 `enabled`、`runtime_allowed`、checkpoint 存在和 adapter warmup 可用，才允许执行候选模型。当前双通道配置为 `runtime_allowed=false`，病例分析记录跳过原因、adapter 状态、合成白光边界和传统融合回退可用状态。

多 mask 的 150 条监督记录当前均为 `review_required`。bone gate 过拟合探针曾出现预测阳性比例接近 1.0 和过分割率 1.0，说明该头存在退化风险。当前 `runtime_allowed=true` 只用于显式选择的候选 adapter smoke；`candidate_only=true`、`mainline_replacement_allowed=false` 和 `checkpoint_runtime_allowed_at_training=false` 共同记录其尚未取得主线晋级资格。

### 5.4 多 mask 训练和医生回灌

训练样本保留 `accepted`、`modified`、`rejected`、`review_required` 状态和样本权重：

- `accepted` 与 `modified` 进入高权重训练集。
- `rejected` 进入负例或错误分析。
- `review_required` 保留为低权重种子，不能表述为医生标注。

医生标注流程采用模型选帧、SAM 2/CVAT 传播与人工修改相结合的方式，优先复核高不确定、时序跳变和边界模糊关键帧。

### 5.5 不确定性与质量控制

技术不确定性由温度缩放后的预测熵、TTA 方差和时序稳定性共同生成。报告 ECE 与 Brier 用于描述代理任务中的置信度校准。真实疾病判断校准仍需目标域医生金标准。

以下情况直接提高复核优先级：

- 通道缺失、严重配准失败或曝光饱和。
- 关键帧 mask 面积突变或候选框漂移。
- 输入与训练代理域差异明显。
- 多模型结果冲突。
- bone gate 尚未人工复核。

## 6. 企业显微镜集成方案

### 6.1 已覆盖接口

- 3840×2160 JPEG 上传与全分辨率输出。
- 公开 2048×1536/1280×720 长 MP4 上传、解码、关键帧抽取、同步播放分析和证据导出。
- 通用 OpenCV 有界实时输入，支持本地采集设备索引、RTSP、HTTP、HTTPS 和本地视频源。
- 实时关键帧进入分割、风险、不确定性、动态量化和证据输出，并记录丢帧、断流、采集时间、推理完成帧龄和显示许可。无法匹配采集帧、帧身份冲突、缺少显式显示许可及全部结果过期均采用失败闭合策略。
- 强制 tiling、坐标回映、失败回退和结构化 manifest。
- 白光/荧光图像融合、伪彩、ROI 量化和动态曲线。
- AI 候选区、医生复核状态和证据报告。

当前验证范围包含 4K JPEG 单帧、低分辨率长 MP4，以及合成本地 MP4 的 capture-to-analysis 实时流 smoke。帧龄超过配置上限时，结果标为不可显示并退出候选区；全部结果过期时 run 标记为 `failed`，病例不晋级，旧帧 AI artifact 与决策摘要不发布。浏览器摄像头仍属于本地预览，后端帧传输尚未连接。企业 3840×2160 MP4、采集接口和连续实机稳定性等待原始样片及接口资料。

### 6.2 企业需提供的参数

1. 白光与 NIR 是否能够分别导出原始帧。
2. 两通道同步方式、时间戳精度和丢帧策略。
3. ICG 激发滤光片、二向色镜和发射滤光片的完整透过曲线。
4. 相机传感器、位深、压缩参数、色彩空间和 MP4 编码器。
5. 曝光、增益、光源功率、倍率和工作距离的读取或锁定方式。
6. 典型与极端样片：静态 JPEG、短 MP4、长 MP4、快速移动、出血、低信号和过曝场景。
7. 目标工作站 CPU、GPU、内存和操作系统。

### 6.3 实机验收矩阵

| 类别 | 验收项 | 记录方式 |
|---|---|---|
| 光学 | 检测限、线性、均匀性、SNR、空间分辨率、串扰 | 组织仿体和标定板报告 |
| 通道 | 时间同步、帧丢失、配准误差 | 原始双通道 manifest |
| 视频 | 编码兼容、长视频稳定性、异常帧回退 | 解码与端到端性能报告 |
| AI | whole-frame/tiling 选择、P50/P95、内存峰值 | 目标硬件 benchmark |
| 显示 | 原视频播放、关键帧同步、overlay 与医生复核 | UI 截图和操作记录 |
| 造影剂 | 激发/发射匹配、组织仿体检测范围 | 光谱与显微镜适配报告 |

## 7. 当前工程证据

### 7.1 已形成的证据

- `research/reports/planning/official_competition_problem_alignment_20260704_zh.md`：官方对齐记录，用于复核三项核心内容和五项评审标准。
- `research/reports/modeling/r01_r08_remediation_20260710_zh.md`：R01-R08 修复报告，属于代理工程证据，完成范围需结合当前测试与数据边界解释。
- `research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/`：无泄漏关键帧评估，指标来自 D046 非目标域伪标注。
- `research/reports/modeling/dual_channel_ablation_20260710_dual_channel.json`：双通道消融，白光通道来自亮度合成代理。
- `research/reports/modeling/video_signal_multimask_v2_training_20260710_multimask_v2_grouped.json`：多 mask 训练，bone gate 仍为待复核种子，并存在过分割风险。
- `tools/run_keyframe_tiling_smoke.py`：4K tiling 入口，用于关键帧坐标和全分辨率输出验证。
- `research/reports/modeling/public_video_dynamic_quantification_20260711_zh.md`：动态量化报告，使用 OFDVDnet 真实公开视频链路和 8-bit luminance，曲线质量为 limited。
- `src/models/adapters.py` 与 `configs/inference/osteo_vision.yml`：模型运行许可记录，覆盖 checkpoint、`runtime_allowed`、候选选择和 warmup 边界。
- `research/reports/modeling/public_video_4k_validation_20260711_zh.md`：公开真实视频验证，覆盖 OFDVDnet 离体荧光代理与胫骨骨髓炎无荧光公开视频。
- `research/reports/modeling/d047_pmc_jaw_fluorescence_dataset_20260711_zh.md`：10 张颌骨荧光论文图的下载、许可、人工复核队列、注册表接入和训练门控记录。
- `research/reports/modeling/d048_open_clinical_bone_fluorescence_dataset_20260711_zh.md`：18 张开放临床骨荧光近域图、15 条复核种子和 2 个颌骨工程裁剪的来源及边界记录。
- `src/datasets/training_admission.py`：统一注册表到 keyframe 训练的三档准入门，记录来源、许可、checksum、复核状态、分组切分和 registry/quality SHA256。
- `backend/src/services/active_review_queue.py` 与 `tools/build_keyframe_training_manifest_from_review.py`：医生复核回灌的逐样本许可、来源组、采样权重、mask 质量和 checksum 门控。
- `src/io/live_stream.py` 与 `tests/smoke/test_live_stream_analysis.py`：有界实时采集、超时、丢帧、帧龄门控及 capture-to-analysis smoke。
- `src/datasets/static_panel_detection.py`、`tools/build_static_panel_crop_suggestions.py`、`backend/src/services/static_dataset_review.py` 与 `frontend/src/components/StaticCropEditor.vue`：D047/D048 14 张多面板原图形成 52 条可追溯原子裁剪建议，并支持建议接受/修改、双通道配对、自动 seed、静态 mask 复核和 manifest 输出。

公开真实视频验证覆盖两个超过 60 秒的 MP4、15/29.97 FPS 原始视频、6/29.97 FPS 派生视频、不可读 H.264 失败记录、公开来源帧派生 3840×2160 JPEG、三次 45-tile 推理、缺 checkpoint 回退和八次短时内存观察。4K 单关键帧端到端耗时为 3.94-4.28 秒，模型概率推理为 1.52-1.56 秒；该结果支持异步关键帧分析。

### 7.2 模型证据边界

当前可报告的模型结果均来自公开异域或代理任务。历史 Dice 0.9093 已降级为历史代理结果。新的无泄漏指标、双通道消融、多 mask 指标和 4K 性能均需要同时展示数据来源、分组策略、阈值来源、checkpoint SHA256、运行配置和非目标域说明。

### 7.3 仍需外部协作的证据

| 外部证据 | 当前状态 | 最小可用交付 |
|---|---|---|
| 候选造影剂实物 | 未合成 | 结构确认、光谱、HAp 结合和细菌选择性初步结果 |
| 真实目标域病例 | 暂缺 | 脱敏白光/NIR JPEG 或 MP4，病例协议和来源说明 |
| 医生金标准 | 暂缺 | 关键帧、ROI/mask、accepted/modified/rejected 状态 |
| 企业原始双通道 | 暂缺 | 同步样片、设备元数据、滤光片曲线和曝光参数 |
| 企业实机 benchmark | 暂缺 | 目标硬件 P50/P95、持续内存、失败回退和显示检查 |

## 8. 风险、解决路径与止损条件

1. **原创造影剂缺实物**。结论分类：需实验团队配合。执行路径：冻结 BVN-800 A0 候选、单功能对照和验证矩阵。止损条件：提交前无实验时，只报告设计论证与外部验证计划。
2. **真实目标域数据缺失**。结论分类：当前无可靠替代。执行路径：公开荧光代理、骨感染/坏死公开视频和 CBCT 派生数据分层使用。止损条件：禁止生成目标域临床性能结论。
3. **医生标注暂缺**。结论分类：需医院配合。执行路径：prompt-assisted 预标注和高不确定关键帧复核。止损条件：未复核样本保持 `review_required`。
4. **双通道原始数据缺失**。结论分类：需企业配合。执行路径：合成白光代理验证架构，并保留传统融合。止损条件：双通道 AI 持续受运行许可控制。
5. **4K 实时压力**。结论分类：当前可直接推进。执行路径：keyframe、ROI、tiling、异步队列和回退。止损条件：无目标硬件时保持关键帧分析表述。
6. **ICG 定量跨病例不稳定**。结论分类：只能降低风险。执行路径：背景扣除、归一化曲线和协议锁定。止损条件：采集参数缺失时仅作病例内相对解释。
7. **多菌种感染**。结论分类：当前无单一可靠替代。执行路径：万古霉素端作为革兰阳性主候选，并建立革兰阴性和厌氧菌对照。止损条件：不声明全病原覆盖。

## 9. 实施计划

### 9.1 比赛提交前

1. 冻结候选造影剂结构、机理、对照组和验证矩阵。
2. 完成动态强度链路、双通道运行许可、多 mask adapter、4K JPEG 单帧和公开长 MP4 验证。
3. 生成最新模型清单、checkpoint SHA256、阈值来源和测试报告。
4. 完成最终 Word、PDF、证据索引和逐页渲染检查。
5. 向企业、医院和实验团队发出最小资料清单并设置明确反馈截止点。

### 9.2 入围后的外部验证

1. 合成并筛选 BVN-800 及单功能对照分子。
2. 获取企业原始双通道样片和滤光片参数，完成组织仿体及实机标定。
3. 建立小规模脱敏目标域病例与医生关键帧金标准。
4. 开展目标域阈值校准、失败模式分析和前瞻性验证方案设计。

## 10. 交付物与证据索引

最终提交包包括：

- 中文技术方案 Word。
- 中文技术方案 PDF。
- 工程证据索引 JSON/Markdown。
- 内部验证记录 `internal_verification_20260711_zh.md`。
- 模型清单与 checkpoint SHA256。
- `competition_evidence_index_20260711.json` 与中文 Markdown 索引。
- 数据来源和公开视频验证 manifest。
- 关键测试命令、结果和已知基线问题。
- 企业、医院和实验团队资料清单。

证据分为四层：

1. 文献证据：候选造影剂、ICG、四环素、自发荧光、量化和标准化依据。
2. 代理工程证据：公开异域数据、代理标注、模型消融、4K 和视频链路测试。
3. 医生复核证据：后续 accepted/modified/rejected 关键帧与 ROI。
4. 企业实机证据：后续原始双通道、组织仿体、目标硬件和滤光片适配结果。

## 11. 医学与合规声明

Osteo Vision 为面向竞赛和研发验证的平台软件。平台结果用于荧光/灌注信号观察、风险提示、医生复核和工程验证，不能替代临床诊断、病理、微生物培养或医生手术判断。候选造影剂尚未完成本项目实物验证，不得用于人体。公开异域数据、代理标注和 CBCT 工程结果不得包装为真实术中 ICG 颌骨骨髓炎病例证据。

## 12. 主要参考资料

1. 官方赛题方案：HT-202604 面向颌骨骨髓炎的智能化荧光诊疗方案，2026。
2. 赛题方手术显微镜基本参数与荧光资料，2026-05-27。
3. Phosphonated Near-Infrared Fluorophores for Biomedical Imaging of Bone. DOI: https://doi.org/10.1002/anie.201404930
4. Real-time in vivo imaging of invasive- and biomaterial-associated bacterial infections using fluorescently labelled vancomycin. DOI: https://doi.org/10.1038/ncomms3584
5. Bacteria-targeted fluorescence imaging of extracted osteosynthesis devices for rapid visualization of fracture-related infections. DOI: https://doi.org/10.1007/s00259-022-05695-y
6. Comparison of two fluorescent probes in preclinical imaging and image-guided debridement of staphylococcal biofilm implant infections. DOI: https://doi.org/10.1038/s41598-020-78362-7
7. Comparison of auto-fluorescence and tetracycline fluorescence for guided bone surgery of MRONJ. PubMed: https://pubmed.ncbi.nlm.nih.gov/27856150/
8. Fluorescence-guided bone resection in diffuse chronic sclerosing osteomyelitis of the mandible. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC4628814/
9. Autofluorescence-Guided Surgery in ONJ: correlation with histopathology in 56 samples. DOI: https://doi.org/10.3390/life15050686
10. Fluorescence-guided surgery for osteoradionecrosis of the jaw. DOI: https://doi.org/10.1177/03000605221104186
11. Near-Infrared Fluorescence with ICG to Assess Bone Perfusion: A Systematic Review. DOI: https://doi.org/10.3390/life12020154
12. Setting Standards for Reporting and Quantification in Fluorescence-Guided Surgery. DOI: https://doi.org/10.1007/s11307-018-1220-0
13. Confidence Calibration and Predictive Uncertainty Estimation for Deep Medical Image Segmentation. DOI: https://doi.org/10.1109/TMI.2020.3006437
14. ICG time-intensity curve normalization study. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC10209496/
15. OnLume fluorescence video denoising data. DOI: https://doi.org/10.5061/dryad.8gtht76x9
16. OFDVDnet fluorescence surgery video data. DOI: https://doi.org/10.5061/dryad.v6wwpzh3w
17. SAM 2: https://github.com/facebookresearch/sam2
18. CVAT: https://github.com/cvat-ai/cvat
19. MONAI Label: https://github.com/Project-MONAI/MONAILabel
20. NVIDIA Holoscan SDK: https://developer.nvidia.com/holoscan-sdk

## 附录 A：外部团队资料清单

### A.1 企业团队

- 原始白光/NIR 同步 JPEG 或 MP4 样片。
- 滤光片、二向色镜、激发光源和传感器光谱参数。
- 曝光、增益、倍率、工作距离、编码器和时间戳说明。
- 目标工作站配置与可安排的实机测试窗口。

### A.2 医院与医生团队

- 脱敏病例基本信息和影像协议。
- 关键帧、ROI/mask、复核状态和失败样本。
- ICG 给药、注射时刻、曝光和工作距离记录。
- 病理、培养或随访结果的最小关联字段。

### A.3 化学与实验团队

- 候选结构的合成可行性、反应位点和纯化建议。
- 光谱、稳定性、HAp 结合和细菌选择性实验。
- 细胞毒性、溶血、组织仿体和必要动物伦理路径。

## 附录 B：Tavily 检索状态

2026-07-11 尝试使用 Tavily Research 与 Tavily Search 核验造影剂、动态量化和标准化资料，接口返回套餐用量上限错误。后续核验使用本地论文清单、Crossref、Europe PMC、PubMed、PMC、Dryad 和官方开源项目链接完成，所有新增结论仍需在正式提交前进行参考文献格式复核。
