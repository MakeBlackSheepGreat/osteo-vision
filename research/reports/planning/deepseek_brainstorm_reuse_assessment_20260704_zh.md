# DeepSeek 头脑风暴思路复用评估

日期：2026-07-04

## 来源与结论

来源文件：`C:\Users\876762330\Downloads\chat-export-1783173330966.md`。

本次头脑风暴中有一部分内容可以直接转化为当前项目成果，但不能全部照搬。真正能落地的核心是：继续把项目做成“官方 4K JPEG/MP4 输入 -> 白光/荧光融合或伪彩增强 -> 帧级候选区/分割 mask -> 荧光叠加结果 -> 医生复核 -> 证据包输出”的软件闭环；CBCT 方向用作术前/代理病灶分割与解剖先验；四环素/骨自发荧光用作造影剂与边界识别机制的文献支撑。

不宜作为当前承诺的是：真实术中 ICG 颌骨骨髓炎临床级自动分割、真实造影剂合成实验、VISTA3D/MAISI 等大型基础模型实跑、以及把 2011 年近红外标记四环素衍生物作为核心方案。

## A. 已经落地或可以直接使用

### 1. 官方 JPEG/MP4 输入到分割叠加的软件闭环

DeepSeek 反复强调 4K MP4 上传、关键帧抽取、分割、叠加显示和报告输出。这部分已经与当前项目方向一致，并且已有代码落地：

- MP4 分析接入：`backend/src/services/analysis_service.py`
- 关键帧热点分割输出：`video_segmentation_manifest_path`、`segmentation_review_video_path`、`mask_review_video_path`
- 导出 artifact：`video_segmentation_manifest`、`video_overlay`、`video_mask`
- 说明报告：`research/reports/modeling/jpeg_mp4_hotspot_bridge_20260704_zh.md`

可直接用于比赛第二、三部分：多模态图像融合与 AI 辅助判读。注意当前是启发式热点分割基线，不是训练完成的临床模型。

### 2. D025 CBCT 病灶代理模型

DeepSeek 建议用 CT/CBCT 作为现实数据主线，这与项目已有判断一致。当前本地 D025 代理模型已经有可报告指标：

- 验证病例：53
- Mean Dice：0.6266
- Mean IoU：0.5183
- Lesion sensitivity：0.6756
- Lesion precision：0.6932

它适合写成“术前 CBCT 病灶代理分割模型”和“AI 判读能力原型”，不能写成真实术中 ICG 视频模型。

### 3. OFDVDnet 荧光视频代理资料

DeepSeek 提到荧光图像增强和去噪，这部分本地已处理 OFDVDnet baseline：

- 处理视频记录数：48
- 用途：荧光视图裁剪、去噪、归一化、CLAHE、伪彩、融合
- 报告：`research/reports/modeling/ofdvdnet_fluorescence_baseline_20260704_zh.md`

它可用于赛点一/第二部分的荧光增强、伪彩稳定性、低信噪比处理演示。它不是颌骨骨髓炎数据，也不是病灶分割训练集。

### 4. 四环素/骨自发荧光作为造影剂章节支撑

DeepSeek 讨论的四环素骨荧光和骨自发荧光是真正有用的材料。本地已有对应报告：

- `research/reports/planning/tetracycline_autofluorescence_value_assessment_20260704_zh.md`
- 本地资料包括 P061、P062、P063、P066、P068 等。

可用于补强完整赛题第一部分“新型荧光造影剂设计方案”：ICG 是企业已有产品和基础对照；四环素/自发荧光提供更贴近坏死骨/活性骨边界的文献机制与后续验证路线。

## B. 应该立即补入项目任务的内容

### 1. MedSAM/SAM2 的最小交互式分割闭环

DeepSeek 提到 MedSAM/SAM2 few-shot 有价值。当前项目已把 `MedSAMLikeAdapter` 补成 2D prompt contract fallback，适合作为真实 MedSAM/SAM2 checkpoint 接入前的最小可用接口：

1. 前端或后端使用热点候选框、医生 ROI 框作为 prompt。
2. MedSAM-like adapter 接收 `2d_image + bbox/points/roi_hints`。
3. 输出 mask、overlay、候选区和量化摘要。
4. 医生复核后回写为训练样本。

这比直接训练真实术中病灶模型更现实，也能服务“医生复核辅助”的比赛叙事。边界是：当前 fallback 不是真实 MedSAM2 权重推理。

### 2. DentalSegmentator 作为 CBCT 解剖 ROI 入口

DeepSeek 提到 DentalSegmentator、ToothFairy2、DentVoxel。当前项目已有 D024/D025/D036，本地报告也确认 DentalSegmentator 有公开预训练模型和 Slicer 扩展。本轮已新增 `src/preprocess/cbct_roi.py`，把它在本项目中的位置先固化为“颌骨、牙齿、下颌管等解剖 mask -> CBCT ROI 裁剪与 manifest”的本地预处理契约，而不是让病灶模型直接在全 CBCT 上盲找。

短期目标：

- 已完成：建立可消费 DentalSegmentator-style anatomy mask 的 ROI contract，输出裁剪 NPZ 和 manifest。
- 待后续：下载并记录 DentalSegmentator checkpoint/许可/来源。
- 待后续：先离线跑 1-3 个公开 CBCT 样例，输出 mandible/maxilla/teeth/canal mask，用作 D025 或医院 CBCT 的 ROI 前处理。

### 3. 4K 视频的工程增强

DeepSeek 提到的帧间闪烁和 4K 信息瓶颈是当前软件闭环的真实工程缺口。建议补两项低风险功能：

- 帧间平滑：对关键帧 mask 做面积、bbox 和连通区级别的时间平滑，减少闪烁。
- Patch-based 4K 推理：先保留 4K 原图，模型输入用 ROI/patch，输出再映射回原分辨率。

这两项比更换大模型更贴合官方 4K MP4/JPEG 输入。

### 4. 3D Slicer 数据交换，而不是先做完整插件

DeepSeek 提到 3D Slicer/SlicerIGT/3D 打印导板。当前阶段不建议先做完整 Slicer 插件，但可以先做轻量数据交换：

- CBCT 分割 mask 导出 NIfTI/STL。
- 病灶边界和安全区导出为可视化模型。
- 报告中说明后续可进入 Slicer 术前规划或导航。

这样能提高临床流程完整性，又不阻塞当前软件闭环。

## C. 可写进报告，但暂不作为短期实现承诺

### 1. nnU-Net v2 / DynUNet 高分辨率正式训练

DeepSeek 建议 nnU-Net 是正确方向。项目已有 nnU-Net 外部代码快照和 MRONJ CBCT nnU-Net 文献依据，但当前主线 checkpoint 仍是 D025 ConvNeXt-style 代理模型。下一阶段应跑 nnU-Net/DynUNet 高分辨率基线，但不能阻塞当前演示闭环。

### 2. VELscope / 骨自发荧光双路线

骨自发荧光适合写成“无药物、蓝紫光激发、活性骨/坏死骨边界提示”的备选造影/成像路线。它对比赛造影剂章节有价值，但当前没有设备和视频数据，不应写成已实现功能。

### 3. 域适应、合成数据、CT 到视频桥接

CT 派生伪视频、合成荧光帧、teacher-student 域适应都适合放在“数据缺失时的下一阶段训练策略”。当前可以实现数据生产和标注规范，不宜承诺已经完成真实域迁移。

### 4. SlicerIGT、导航、3D 打印导板

这些内容有助于提高完整性和应用价值，但本赛题短期优先级仍是：造影剂论证、双通道融合、AI 辅助判读。SlicerIGT 和导板建议作为“扩展应用场景”而不是主线开发任务。

## D. 谨慎使用或不宜作为核心的内容

### 1. 2011 年近红外标记四环素衍生物

它只能放在前瞻性讨论，不能作为本项目核心造影剂方案。当前更稳妥的主线是四环素天然荧光和骨自发荧光的临床/动物证据，再讨论未来如何适配显微镜多光谱通道。

### 2. MAISI 实跑

DeepSeek 提到 MAISI 合成 CT，但该类模型硬件门槛高，且生成数据不能替代真实颌骨骨髓炎标注。可以作为“未来增强”，不要列为当前必须完成的训练依赖。

### 3. VISTA3D 实际接入

VISTA3D 可作为医学分割基础模型趋势写入报告，但本项目当前没有目标域 checkpoint、推理契约和适配验证，不适合作为短期交付核心。

### 4. Grad-CAM 直接解释分割

Grad-CAM 对分类模型更自然。当前项目是分割与热点候选区主线，更适合输出概率热图、不确定性图、候选区来源和医生复核状态。除非增加分类头，否则不要把 Grad-CAM 写成核心解释模块。

### 5. 真实术中临床级 MP4 分割性能承诺

当前缺少真实术中 ICG/新型荧光颌骨骨髓炎 MP4/JPEG 和医生关键帧标注。所有公开视频、OFDVDnet、D025 CBCT、合成视频都必须标注为非目标域或代理数据。

## 对当前比赛路线的推荐调整

当前最可行路线应为：

```text
造影剂章节：
ICG 基础对照 + 四环素天然荧光/骨自发荧光文献支撑 + 后续验证路径

软件章节：
官方 4K JPEG/MP4 输入 + 白光/荧光融合 + 伪彩增强 + 关键帧热点/分割候选区

AI 章节：
D025 CBCT 代理病灶分割 + 2D 荧光热点分割 + MedSAM/SAM2 交互式修正计划

临床边界：
所有输出为科研/竞赛原型，不能替代医生诊断；缺少真实目标域样本是一级风险
```

## 可执行任务清单

1. 把 `MedSAMLikeAdapter` 从空 adapter 改成最小 prompt 分割接口，先支持 bbox 输入和 mask/overlay 输出。（已完成 prompt contract fallback；真实 MedSAM2 checkpoint 仍待接入。）
2. 给 MP4 keyframe 结果增加帧间平滑和 4K 坐标回映射说明。（已在后端 manifest 中补充 `spatial_mapping` 与 `temporal_stability` 元数据；当前不改变 mask。）
3. DentalSegmentator 方向已先完成本地 CBCT ROI 预处理 contract；真实 checkpoint 下载、许可记录和样例推理仍待后续。
4. 将四环素/骨自发荧光整理进最终技术方案“造影剂设计与验证路径”章节。
5. 把 Slicer/导板/导航写为扩展流程，先实现 NIfTI/STL/JSON 数据交换，不先做完整插件。
6. 继续保留 D025 ConvNeXt-style 代理模型作为当前可运行主线，同时准备 nnU-Net/DynUNet 高分辨率基线。

## 结论

DeepSeek 头脑风暴真正能立刻转化为项目成果的不是“大模型名录”，而是三个务实方向：四环素/自发荧光补足造影剂论证，D025/nnU-Net/DentalSegmentator 补足 CBCT 代理分割，MP4 keyframe 热点分割补足官方输入到软件输出的比赛闭环。当前项目已经具备闭环雏形，并已补入 MedSAM prompt fallback、DentalSegmentator-style CBCT ROI contract 和 MP4 4K 坐标/帧间稳定性元数据；下一步应优先做真实 checkpoint 接入、批量 CBCT ROI 转换和更稳定的 4K 长视频输出。
