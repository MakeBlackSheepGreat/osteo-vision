# 荧光颌骨骨髓炎术中视频分割预期路线与锚定报告

生成日期：2026-07-06

## 1. 核心结论

本项目短期不应把术中 MP4/JPEG 分割任务定义为“自动分割颌骨骨髓炎病灶”。在真实颌骨骨髓炎 ICG 术中视频和医生像素级标注缺失的条件下，更稳妥、可实现且符合医学边界的任务定义是：

> 术中视频分割 = 暴露骨区域分割 + 荧光/灌注信号分割 + 时间稳定性判断 + 边界风险提示 + 医生复核。

平台软件应输出可解释的 mask 和风险层，而不是直接输出“疾病终判 mask”。当前最重要的显示对象是“暴露骨上的低灌注/弱荧光稳定区域”和“边界风险区域”。

## 2. 赛题与设备锚点

完整赛题要求围绕三项内容组织：新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助病灶识别与判读。软件侧主要支撑第二项和第三项，同时为第一项提供 ICG 基线、四环素/自体荧光文献依据和未来验证接口。

赛题方设备技术文档给定的软件输入边界为：

| 输入 | 官方约束 | 本项目落地方式 |
|---|---|---|
| 视频 | 4K MP4，3840x2160 | 后端上传、关键帧抽取、tiled inference、前端视频流预览 |
| 图片 | JPEG | 单帧分析、白光/荧光融合、证据截图 |
| 荧光背景 | ICG 近红外成像 | 作为灌注/活性参考信号，不作为骨髓炎特异性真值 |

## 3. 五层技术路线

### 第一层：视频信号分割，而非疾病终判

输入官方 4K MP4/JPEG 后，优先输出以下可解释 mask：

| mask 名称 | 含义 | 当前可做程度 |
|---|---|---|
| `exposed_bone` | 暴露骨/疑似骨面区域 | 需要 SAM2/MedSAM2 辅助标注和少量人工复核 |
| `soft_tissue` | 周围软组织区域 | 可由人工/SAM 辅助标注，后续训练 |
| `instrument_or_occlusion` | 器械、遮挡、烟雾、反光等干扰 | 先做质量提示，后续训练 |
| `fluorescence_hotspot` | 荧光高信号热点 | 当前已有启发式和 D046 伪标注模型 |
| `hypo_fluorescent_bone` | 暴露骨上的弱荧光/低灌注稳定区域 | 需要 `exposed_bone` 门控 + 荧光分支 |
| `boundary_risk` | 可疑切除边界/风险过渡区 | 由骨区域、荧光信号和时序稳定性融合得到 |
| `uncertain` | 模型或图像质量不确定区域 | 可由低置信度、空 mask、过分割、遮挡触发 |

### 第二层：保留 ConvNeXt 主线，改成双分支

当前 `convnext2d_keyframe_proxy_segmenter` 继续作为主线，但模型输入和输出语义需要升级。

输入组织：

- 白光纹理分支：骨面纹理、软组织、器械、遮挡。
- 荧光强度分支：ICG/近红外信号、热点、弱荧光区。
- 伪彩叠加分支：白光与荧光融合后的空间提示。
- 质量/遮挡分支：模糊、过曝、欠曝、烟雾、反光、器械遮挡。

输出组织：

- `bone_gate_mask`：骨面/可分析区域门控。
- `fluorescence_signal_mask`：荧光高信号、弱信号、漏光/噪声候选。
- `risk_mask`：在骨面门控内融合得到的灌注/活性风险提示。

这比“直接预测骨髓炎 mask”更稳，也更符合 ICG 的医学属性。

### 第三层：用 SAM2/MedSAM2 做标注加速和视频传播

SAM2/MedSAM2 不应在当前阶段被包装成全自动临床模型。它们更适合作为交互标注器：

1. 医生或团队在关键帧上点选、框选或粗略涂抹。
2. SAM2/MedSAM2 生成初始 mask。
3. 视频传播到相邻关键帧或短片段。
4. 复核状态进入 manifest：`accepted`、`modified`、`rejected`。
5. `accepted`/`modified` 作为高权重样本，`rejected` 用于负例、失败模式或错误分析。

此环节是解决真实标签缺口的核心，不应继续只依赖公开视频伪标注训练。

### 第四层：用 OFDVDnet/FGS 思路稳定荧光视频质量

荧光视频天然存在低光子、漏光、噪声、运动和白光/荧光错位问题。分割前需要先做：

- reference-guided denoising；
- temporal smoothing；
- leakage correction；
- 白光/荧光视图拆分与配准；
- 帧级质量评分。

当前 D046 中的 OFDVDnet/FGS 代理视频正适合训练和验证这部分工程能力。

### 第五层：D025/D024/D036 作为术前先验，不硬塞进术中视频

D025 继续训练 CBCT 病灶代理模型，D024/D036 训练颌骨、牙齿、下颌管等解剖先验。它们在术中视频里只提供：

- 病例侧先验；
- 报告解释；
- 术前/术中并列证据；
- 后续配对数据到位后的晚期融合基础。

不能把 CBCT 指标当作显微镜 MP4/JPEG 分割指标。

## 4. 当前数据锚点

| 数据 | 本地状态 | 本路线中的角色 |
|---|---|---|
| D046 OFDVDnet/FGS 荧光代理视频 | C 盘已下载/派生，含 48 个可读 OFDVDnet 视频和 keyframe 伪标注 | 荧光视频质量、伪彩、关键帧分割、前端 MP4 演示 |
| D046 骨髓炎 PMC 公开视频 | C 盘已下载多段非荧光视频 | 真实骨髓炎手术/影像场景参考，不能做 ICG 真值 |
| D025 DOLCHID | D 盘完整 raw，C 盘有 262 个 lesion ROI 缓存 | 3D 病灶代理分割主线 |
| D024 DentVoxel | D 盘完整 raw，C 盘有 derived/nnU-Net/patch 缓存 | 颌骨/牙齿/下颌管解剖先验 |
| D036 ToothFairy2 | D 盘完整 raw，C 盘有部分 raw 与 derived 缓存 | 牙颌多结构分割先验 |

## 5. 第一阶段可执行训练路线

1. 从 D046 生成新版 manifest：每条 MP4 拆出白光/reference、荧光、overlay、关键帧、时间戳和质量指标。
2. 先训练 `fluorescence_signal_mask`：荧光热点、弱荧光区、漏光/噪声区，不称为病灶。
3. 用 SAM2/MedSAM2 给 50 到 100 个关键帧做半自动标注，重点标 `exposed_bone`、器械遮挡、软组织和可疑边界。
4. 训练双分支 keyframe 模型：白光骨区域门控 + 荧光信号分割。
5. MP4 推理时做 keyframe-based segmentation，再用时序传播和平滑生成复核视频。
6. 前端展示三张图：原视频、分割叠加、风险/不确定性图；医生能接受、修改、驳回。
7. 报告里输出“荧光灌注/活性风险提示”，不输出“自动确诊骨髓炎边界”。

## 6. 近期工程锚定

| 工作包 | 目标文件/模块 | 产出 |
|---|---|---|
| D046 manifest 升级 | `tools/` 新增构建脚本 | `video_signal_segmentation_manifest.csv` |
| mask taxonomy 固化 | `configs/tasks/osteo_vision.yml` | 七类 mask 定义、标签说明、医学边界 |
| 双分支模型输入契约 | `configs/inference/osteo_vision.yml`、`src/models/keyframe_segmenter.py` | `bone_gate_mask`、`fluorescence_signal_mask`、`risk_mask` |
| SAM2/MedSAM2 标注闭环 | `backend/src/services/review_*`、前端复核组件 | accepted/modified/rejected 回灌 manifest |
| 复核视频输出 | `backend/src/services/video_review_writer.py` | 原视频同步 overlay、mask、risk map |
| 报告更新 | `backend/src/reports/` | 平台报告展示灌注/活性风险提示 |

## 7. 判断标准

第一阶段成功不以临床 Dice 为标准，而以工程闭环和可复核性为标准：

- 任意官方边界内 MP4/JPEG 可进入分析链路；
- 每个关键帧至少产出 mask、probability map、overlay、risk map 和质量元数据；
- 视频播放可同步显示最近关键帧分割结果；
- 医生复核结果可保存并转换为训练 manifest；
- 报告中明确 ICG、公开代理数据和伪标注边界；
- 4K keyframe tiled inference 稳定，空 mask 有 fallback。

## 8. 外部证据锚点

- ICG 骨/感染清创研究协议：`https://cdn.clinicaltrials.gov/large-docs/11/NCT04245111/Prot_SAP_000.pdf`
- OFDVDnet / FGS 视频数据：`https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w`
- FGS 视频去噪数据和模型：`https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9`
- OFDVDnet 论文：`https://proceedings.mlr.press/v227/seets24a.html`
- MedSAM2：`https://medsam2.github.io/`
- SAM2 医学视频方向：`https://arxiv.org/abs/2504.03600`
- 颌骨坏死自体荧光/四环素荧光证据：`https://pmc.ncbi.nlm.nih.gov/articles/PMC7666678/`

## 9. 医学边界

- ICG 反映血流灌注、血管通透性和组织活性差异，不是颌骨骨髓炎特异性探针。
- 当前 D046 指标是公开/代理/伪标注验证结果，不等同真实术中 ICG 颌骨骨髓炎临床分割性能。
- 当前平台输出应表述为灌注/活性风险提示、候选区和医生复核辅助，不得表述为自动确诊或替代医生判断。

## 10. 第一轮代码落地状态

- 已把 MP4/JPEG keyframe 输出契约升级为 `video_signal_segmentation`，包括 `bone_gate_mask`、`fluorescence_signal_mask`、`risk_mask`、`uncertain_mask`。
- 已生成 D046 视频信号分割 manifest：20 个公开视频、100 个 keyframe 样本，来源链接、原视频路径、时间戳、质量状态和 mask 类型均有记录。
- 已把风险图、不确定性图、复核权重和视频分割 manifest 接入后端输出、报告导出和前端同步分析。
- 当前 `bone_gate_mask` 仍为待复核槽位，不在无医生/SAM 辅助标注时伪造骨面真值。
