# 颌骨骨髓炎智能化荧光诊疗平台 — 挑战杯报告素材包

> 本文件为挑战杯报告撰写的素材汇总，基于 osteo-vision v0.3.0-rc.2 工程基线整理。
> 整理日期：2026-07-21
> 用途：挑战杯报告撰写素材，可在赛题允许范围内做有理有据的扩展叙述。
> 边界：所有工程证据均可追溯至项目文件；医学边界与不可声称范围必须保留。

---

**版本基线**：osteo-vision v0.3.0-rc.2，2026-07-19 冻结
**主线模型**：`keyframe_residual_attention_unet_s20260715_20260715`（代理测试集 Dice 0.9177、IoU 0.8483）
**严格配置 SHA256**：`9a2247035c27ba8f142d628f721bfb61d2e9b296a1201ccef375a98fc5f5e855`

---

## 第零章 产品定位与一句话讲清楚

**一句话**：一套面向颌骨骨髓炎术中辅助决策的纯软件平台，把"荧光造影剂 + 多模态图像融合 + AI 判读 + 医生复核 + 三维参考"五件事，在统一的安全架构下串成一条可证据追溯的闭环。

**产品形态**：
- 前端：Vue 3 + TypeScript 桌面工作站，临床工程主流程导航（数据准入 → 病例档案 → 病例工作台 → 三维导航 → 医生复核 → 报告导出）
- 后端：FastAPI（端口 8001）+ PyTorch 推理核心
- 启动：根目录 `start_platform.cmd` 一键启动，默认执行严格运行预检与模型预热
- 算力：NVIDIA GeForce RTX 5060 Laptop GPU 验证基线；4K tiled 推理峰值显存约 724 MB；连续帧 fast-output 模型 P95 36 ms，服务 E2E P95 176 ms；4K 全证据端到端 P95 5.78 s
- 无 GPU 时仍可工作：CPU 模式保留全功能，仅推理延迟上升

**比赛版主流程**：
1. 录入脱敏病例与临床上下文（年龄、性别、基础病、用药、血液指标）
2. 导入官方 4K JPEG（原彩图 + ICG 荧光图 + 可选设备叠加图）或 4K MP4
3. 自动配准、伪彩、融合、归一化、质控、ROI 定量
4. 4K tiled 关键帧分割 + 连续帧 fast-output 实时叠加
5. 输出 `bone_gate_mask` / `fluorescence_signal_mask` / `risk_mask` / `uncertain_mask` 四类 mask + 骨活性连续谱
6. 医生复核、人工标注、版本审计、双签晋级
7. 导出 JSON + CSV + Markdown + DICOM Secondary Capture + ZIP 证据包
8. 三维工作台：CBCT/STL 导入 → L1 静态仿体配准 → L2 离线位姿回放

---

## 第一章 新型荧光造影剂设计（赛题要求一）

> 赛题原文要求：重点说明显光荧光成像条件下的示踪机理、靶向或选择性依据、必要实验或验证数据支持、与显微荧光成像系统的适配性。

### 1.1 设计总思路：患者零用药优先的三源多光谱骨活性判读

**创新点表达**：以"原彩结构 + ICG 灌注时序 + 紫蓝光骨自体荧光"三源融合为核心，按"患者零用药 → ICG 基线 → 研究性多西环素预标记 → 新型骨亲和探针"四级递进设计，贯穿患者安全约束。

| 层级 | 造影剂 | 患者负担 | 表达信号 | 工程定位 |
|---|---|---|---|---|
| L0 零用药 | 骨自体荧光 | 无 | 405-460 nm 激发，500-560 nm 发射 | 首选紫蓝光验证路径 |
| L1 基线 | ICG | 静脉注射 2.5-10 mg | 750-810 nm 激发，820-840 nm 发射 | 灌注与时序基线，赛题方已有 |
| L2 研究性 | 多西环素预标记 | 口服 100 mg bid × 7 天 | 与自体荧光同波段 | 经伦理批准后探索 |
| L3 新型探针 | 模块化骨亲和探针 | 待合成验证 | 向 ICG 设备窗口适配 | 设计参照 + A0-A4 矩阵 |

### 1.2 ICG 机理与边界（项目已有工程基线）

- **化学**：水溶性三碳菁染料，1956 年起用于临床
- **药理**：与血浆白蛋白结合，肝脏快速吸收，半衰期 3-5 分钟，完全经胆汁排出
- **光学**：最大吸收约 800 nm，发射峰约 835 nm；赛题方官方文档确认激发约 750-810 nm，发射约 830 nm
- **剂量**：EAES 2023 共识最低组织灌注评估剂量 2.5-10 mg，推荐 0.25-0.5 mg/kg，最高 2 mg/kg
- **给药时机**：静脉注射后约 10 分钟开始成像，窗口 3-5 分钟
- **机理**：反映血流灌注、血管通透性、组织活性差异
- **关键边界**：赛题原文明确"ICG 在颌骨骨髓炎手术中容易受炎症、充血、水肿和操作因素影响，不能准确区分病灶组织与潜在活性骨组织"，**不是颌骨骨髓炎特异性探针**

**文献支撑**（可写入报告综述）：
- EAES 2023 共识（P036/P041）：ICG 荧光成像"有前景、安全、有效"，但"不应作为单一诊断工具"
- Dhiman 等 2022 系统综述（P039/P048）：23 项 NIR-ICG 研究、452 例患者，对骨髓炎诊断和骨活力评估有积极意义
- Naraghi 等 2018：ICG 显示深部骨感染区域，区分感染/坏死骨与正常骨
- Goloborodko 等 2024：115 例 NSTI 患者，存活感染组织均显荧光，坏死组织均无荧光
- Yoon 等 2019：首次体内验证 ICG 辅助近红外牙科成像可行性
- Kang 等 2019：骨特异性 ICG 药代动力学模型，量化骨膜/内膜血流量

### 1.3 四环素/自体荧光骨坏死检测机理（核心创新点）

**骨亲和机制**：四环素类抗生素与钙结合，在活跃矿化和骨重塑区域沉积。

**荧光特征**（讲故事核心）：
- 活性骨或具有骨重塑活动的骨组织 → 明亮绿色或黄绿色荧光
- 坏死骨 → 低荧光、微弱荧光或无荧光
- 信号同时受药物沉积、胶原结构、骨陷窝细胞状态和自体荧光影响

**波段**（项目文档已锁定）：
- 激发：390-410 nm 紫光灯（典型设备）；VELscope 400-460 nm 蓝紫光；**工程路线首选 405-460 nm 紫蓝光**
- 发射：四环素/多西环素骨切片峰值约 529 nm，集中在 500-560 nm
- 365-400 nm UVA 路线需更严格的眼、皮肤和术野光剂量控制

**文献证据**（项目已下载 PDF）：
- Pautke et al., 2010（PMID 20006166）：四环素骨荧光
- Ristow et al., 2017 随机可行性研究（PMID 27856150）：40 名 MRONJ 患者，自体荧光组与四环素荧光组短期黏膜完整率均较高，差异无统计显著性
- Ristow et al., 2020 小型猪前临床（PMID 32444918）：8 只小型猪，活骨绿色荧光、坏死骨弱荧光或无荧光
- 2021 感染性髋关节翻修（PMID 34084695）：3 例，低荧光切除骨病理与慢性骨髓炎一致
- 2025 范围综述：51 名患者、57 个病灶，手术成功率约 89%-100%（证据规模有限）
- MRONJ 荧光引导手术荟萃分析（PMID 41917690）：285 名患者、314 个病灶

**四环素用药风险**（必须写入报告"安全第一"章节）：
- 过敏；妊娠后半期、婴幼儿、8 岁以下儿童牙齿与骨发育风险；光敏反应；食管刺激；胃肠道反应；艰难梭菌相关腹泻；严重皮肤反应；颅内高压；少见肝毒性
- 药物相互作用：抗凝药、含钙/镁/铝制剂、铁剂、铋剂、异维 A 酸、部分抗癫痫药
- 为成像使用抗生素会引入耐药和微生态风险
- 文献剂量（多西环素 100 mg bid × 7 天）仅作文献证据，**禁止直接转化为本项目临床用药建议**

### 1.4 Evans blue（伊文思蓝）机理与用途边界

**机理**：强结合血清白蛋白；经典用途为血浆容量、血管通透性、蛋白渗漏和淋巴示踪；吸收峰约 620 nm，与白蛋白结合后发射约 680 nm。

**项目定位**：
- 原始 Evans blue 不进入患者应用主线
- 仅保留两类用途：白蛋白结合/通透性探针设计启发 + 非骨前临床数据机理对照
- 历史 FDA 注射产品已停产，公开记录未归因于安全性或有效性
- D052 候选数据集（小鼠声带损伤 Evans blue 自体荧光）与颌骨死骨距离较远，仅作机理对照

**衍生物文献**：
- In vivo albumin labeling and lymphatic imaging（PMCID PMC4291643）
- Evans blue nanocarriers for glioma margin visualization（PMID 25787737）
- Radioiodinated Evans blue necrosis targeting（PMID 29881678）

### 1.5 新型探针模块化设计（创新点）

**四模块设计**（来自技术方案 3.1 节）：
1. **骨亲和端**：双膦酸或膦酸基团，面向羟基磷灰石结合
2. **感染识别端**：革兰阳性菌细胞壁/生物膜结合分子为起点，设置革兰阴性菌、厌氧菌、无菌坏死对照
3. **近红外发光端**：选择可向设备 750-810 nm 激发与 830 nm 检测窗口适配的染料
4. **连接臂**：控制亲水性、空间位阻、药代和非特异吸附

### 1.6 分级实验矩阵 A0-A4（写报告"验证方案"章节）

| 阶段 | 输入 | 主要终点 | 停止条件 |
|---|---|---|---|
| A0 光谱 | 候选、ICG、单功能对照 | 激发/发射、量子产率、光漂白、设备滤光片覆盖 | 光谱不匹配或稳定性不足 |
| A1 材料 | HAp、蛋白、pH、血清 | 骨亲和、非特异吸附、信噪比 | 选择性不足 |
| A2 细菌/细胞 | 多菌种、生物膜、无菌对照 | 结合、竞争抑制、细胞毒性 | 毒性或菌种偏倚不可控 |
| A3 组织/仿体 | 活骨、坏死骨、炎症软组织 | 边界对比、深度、剂量与设备适配 | 边界重复性不足 |
| A4 前临床 | 经伦理批准模型 | 药代、安全性、病理与培养对照 | 安全门失败 |

### 1.7 与赛题方显微镜的适配性

赛题方 ICG 光学：激发 750-810 nm，发射 830 nm。新型探针设计向该窗口适配。紫蓝光骨荧光路径需新增或确认：405/450 nm 可控激发源、约 500-560 nm 发射滤光片、激发泄漏/白光串扰/血液吸收/烟雾/曝光饱和测试、光源互锁/计时/功率上限/异常关闭、原彩/紫蓝光/ICG 三路时空标定。

---

## 第二章 多模态医学图像融合与处理（赛题要求二）

> 赛题原文要求：白光通道与荧光通道等多源图像的获取、配准、融合，以及实时显示或辅助导航应用。

### 2.1 官方输入边界（写报告"输入"章节）

- 设备：4K 超高清影像摄录系统，分辨率 3840×2160
- 接口：USB3.0 文件存储
- 图片格式：JPEG
- 视频格式：MP4
- 赛题方三路输出（2026-07-17 确认）：原彩图、荧光图、叠加图 + 放大倍率、工作距离
- 医院（绵阳市第三人民医院）设备：可导出 JPG 与 AVI，黑白荧光和伪彩显示模式；AVI 受控转码保留原始 + SHA256 + 转码日志

### 2.2 白光/荧光双通道融合处理链（10 步，`fluorescence_fusion_v2`）

实现：`src/preprocess/fluorescence.py`（647 行），默认 `alpha=0.45`、`threshold=0.6`、`colormap="green"`、`registration="phase_correlation_translation"`、`background_percentile=5.0`

1. 文件签名与解码（PIL）
2. 尺寸对齐（双线性重采样）
3. 背景扣除（5% 百分位基底扣除）
4. 几何配准（`cv2.phaseCorrelate`，`min_response=0.08`、`max_translation_fraction=0.15`，低响应降级）
5. 归一化（1%-99% 百分位）
6. 伪彩映射（green/amber/magenta）
7. Alpha 混合（`overlay = (1-α)*白光 + α*伪彩`）
8. 信号增强（高斯降噪 + CLAHE）
9. 量化（面积/强度/ROI）
10. 色标与报告（colorbar + fusion.json + fusion.md）

视频级时序量化：`fluorescence_time_intensity_curve()` 输出基线-峰值归一化、AUC、最大上升斜率、time_to_peak。

### 2.3 三路输出质控（原彩图 / 荧光图 / 叠加图）

实现：`src/preprocess/three_channel_quality.py`（`three_channel_quality_v1` schema）

- 时间同步：三通道时间戳，默认容差 100 ms
- 几何一致性：宽高比 >2% 视为不一致
- 叠加图比较：MAE / RMSE / SSIM / edge_disagreement + 差异热图
- 整体状态：`pass / review_required / unavailable`
- **关键边界**：设备叠加图只用于显示、质控和证据核对，模型输入始终限定为原彩图与原始荧光图

### 2.4 4K tiled 推理（写报告"算力"章节）

- 输入 3840×2160，tile 512，overlap 64，共 45 块
- 主线 Residual Attention UNet：模型 P50/P95 = 415.7/724.4 ms，端到端 P50/P95 = 2181.5/5776.7 ms，GPU 峰值显存 723.6 MB
- 工程验证：4K 单图强制 tiling 45 个 tile，端到端约 3272 ms，峰值 GPU 显存约 724.8 MB
- 门控上限：端到端 P95 ≤ 15 s；模型 P95 ≤ 3 s；显存 ≤ 2048 MB；前景 0.0001-0.6

### 2.5 连续帧 fast-output（实时性创新点）

- 输入：D046/OFDVDNET 公开离体荧光代理 MP4
- 前端长边 960，JPEG quality 0.85，实际 960×720
- 协议：CUDA AMP + 关闭 TTA + 串行逐帧 + whole_frame 模式
- 主线 P50/P95：服务 E2E 154.7/176.5 ms，模型 34.4/36.4 ms，峰值显存 380.1 MB
- 相对上一版 ConvNeXt 主线：服务 E2E P95 -3.4%，模型 P95 -38.9%
- 每帧 mask / risk mask / uncertain mask / JPEG overlay 均有独立证据路径，避免浏览器复用首帧缓存

### 2.6 显微镜倍率、工作距离与 3D 模型配准

**设备解耦原则**：企业负责 SDK/驱动/硬件；软件通过离线 manifest 或人工元数据接入倍率、工作距离、相机标定、坐标变换、位姿记录。

**L1 静态仿体配准**（`static_registration_service.py` 1271 行 + `src/navigation/rigid_registration.py` + `camera_registration.py`）：
- Kabsch SVD 刚性点配准：`METHOD_ID="kabsch_svd_rigid_point_registration"`
- OpenCV solvePnP 相机配准：`METHOD_ID="opencv_solvepnp_iterative"`
- 最少 4 配准点 + 3 验证点，去重、非退化
- 输出 FRE / TRE / 重投影 RMSE
- 工程证据：无噪声合成 FRE `1.43e-14 mm`、TRE `1.68e-14 mm`；D086 牙列基准 0.5/1/2 mm 噪声 TRE `0.352/0.772/1.625` 代理 mm；L1 PnP 拟合 RMSE `0.2234 px`、独立 RMSE `0.2990 px`

**L2 离线动态 AR**（`offline_pose_replay_service.py` 2321 行）：
- FFprobe PTS 严格递增 + 恒定帧率校验
- 9 项安全参数：max_time_offset_ms=50、drift_threshold_mm=1.0、tre_proxy_threshold_mm=2.0、dynamic_target_error_threshold_mm=2.0、max_magnification_rate_per_s=25.0、max_working_distance_rate_mm_per_s=600.0、max_intrinsics_switch_rate_hz=10.0、minimum_visible_projection_points=4、calibration_ambiguity_margin=0.05
- 多倍率标定表 v2：按每帧倍率/工作距离选最近标定项，不做内插外推
- A/B/A 内参振荡检测，出现即撤销整次 L2
- D087 C3VD 代理：766 帧绑定、2556 位姿、最大时间差 9.693 ms、24 帧受控回放

**L0 失效回退**：任一门控失败 → `navigation_ready=false`、`navigation_level=L0`、`fallback_mode=unregistered_3d_reference`。当前所有 L1/L2 工程验证保持 L0 未配准参考。

**坐标契约**（`coordinate_contract.py`）：
- 4 种已知轴约定：DICOM LPS、RAS、phantom XYZ、OpenCV camera
- 矩阵规范：row_major + column_vector + left_multiply + x_y_z_1
- 单位固定 mm

### 2.7 CBCT/STL 三维工作台（`cbct_modeling_service.py` 1650 行）

5 种建模路径：
1. D036 ToothFairy2 nnU-Net 预测（颌骨专用分割验证优先数据）
2. D024 DentVoxel 公开标签
3. 上传标签体（自动区分强度体与标签体）
4. 原始 CBCT 硬组织代理（自适应 p95 阈值 + 形态学清理 + 连通域过滤）
5. 上传 STL/GLB/GLTF 表面模型

输出 `scene_manifest_v2`：subject_hierarchy / nodes / markups / geometry_jobs / review_state / data_boundary。前端 `ThreeDEvidenceControlPanel.vue` 提供受控输入、对象树、建模检查与医生复核状态；`ThreeDRendererRuntimeEmbed.vue` 通过独立渲染运行时读取受控场景快照，并保留主平台二维证据和复核路径。

**关键边界**：原始 CBCT 代理表面只能标注为"高阈值硬组织代理或工程检查表面"，不得展示为真实下颌分割模型。

---

## 第三章 AI 辅助显微成像判读（赛题要求三）

> 赛题原文要求：算法总体思路、特征提取或模型构建方式、叠加提示/风险标注/决策辅助形式。

### 3.1 任务定位：video_signal_segmentation（不是疾病终判）

**固定定义**：暴露骨区域 + 荧光/灌注信号 + 时间稳定性 + 边界风险 + 不确定性提示的组合，**不得直接包装为疾病终判 mask**。

**四类核心 mask 输出契约**（`configs/tasks/osteo_vision.yml`）：

| Mask | id | output_key | 用途 |
|---|---|---|---|
| 暴露骨面 | 10 | `bone_gate_mask` | 医生或 SAM 辅助复核生成，未复核前不可用 |
| 软组织 | 11 | `soft_tissue_mask` | 周围软组织 |
| 器械/遮挡 | 12 | `occlusion_mask` | 器械、烟雾、反光、遮挡 |
| 荧光热点 | 13 | `fluorescence_signal_mask` | 高荧光信号候选 |
| 低荧光骨 | 14 | `hypo_fluorescent_bone_mask` | 骨面内弱荧光/低灌注 |
| 边界风险 | 15 | `risk_mask` | 边界风险/过渡区决策提示 |
| 不确定 | 16 | `uncertain_mask` | 低置信或质量受限区 |

**医学边界**：ICG 与代理荧光 mask 描述灌注/活性线索，不能作为颌骨骨髓炎特异性真值。

### 3.2 骨活性连续谱 v2（核心创新点 — 区分坏死骨/半死骨/活骨/灰色地带）

**五元输出契约**（`bone_activity_spectrum-v2`）：

| 俗称 | 项目术语 | 工程字段 | 调色板 | 边界 |
|---|---|---|---|---|
| 坏死骨 | 低活性/疑似坏死候选 | `low_activity_candidate` (1) | 暗红 [187,56,56] | 灌注/活性偏低，不等于病理坏死骨 |
| 半死骨 | 过渡复核区 | `transition_candidate` (2) | 土黄 [194,139,39] | 信号/颜色/纹理/医生意见边界 |
| 活骨 | 高活性/可保留参考 | `high_activity_candidate` (3) | 青绿 [38,143,109] | 活性相对较高，不等于可保留结论 |
| 灰色地带 | 无法判断区 | `ignore_region` (4) | 灰 [104,113,124] | 遮挡/反光/焦外/饱和/冲突 |
| 连续评分 | 骨活性连续评分图 | `activity_score` | 0-1 灰度 | 仅信号参考，不表达切除成功率 |

**模型架构** `BoneActivityMultiTask2D`：
- 双编码器（白光 3 通道 + 荧光 1 通道）+ fusion + U-Net 多头解码器
- 4 个 head：`bone_gate_head` / `activity_head` / `class_head` / `uncertainty_head`
- 固定输出 6 项：bone_gate、activity_score、class_logits、class_probabilities、uncertainty、abstention
- `IGNORE_INDEX=255`，三类集合 `BONE_ACTIVITY_CLASSES = ("low_activity", "transition", "high_activity")`

**安全门控 fail-closed**（`apply_bone_activity_safety_gate`）：任一条件不满足时全图 abstain（候选全清零，不确定性固定为 1）：
- 模型输出含非有限值
- 非目标域代理
- 模型未通过目标域晋级
- 缺少可信医生复核骨面（含 12 类子原因：missing/untrusted/status_invalid/reviewer_identity_untrusted/annotation_binding_missing/source_checksum_mismatch/evidence_missing/file_missing/sha256_mismatch/dimension_mismatch/empty/positive_pixel_count_mismatch）

**关于"80% 切干净"**：项目验收协议明确禁止把 0.80 数值解释为切除成功率、治愈率、复发率或自动切除边界。任何 0.80 只能解释为候选置信度或目标覆盖率。报告写法建议："在医生复核骨面内，模型对低活性候选区给出置信度，目标覆盖率约 0.80，最终切除边界由医生决定"。

### 3.3 主线 keyframe 分割模型

**模型**：`keyframe_residual_attention_unet_s20260715_20260715`
- 家族：`residual_attention_unet_keyframe_segmenter`
- 参数量：403,785
- 阈值：0.4
- checkpoint SHA256：`826e90c2ee3efd45d0d0d979e85a2a3e2dcd60d853d8497f6328e46a406e0d39`

**多种子选型对比**（同数据清单、同来源分组切分、同预处理、同评价协议）：

| 模型 | 种子 | Dice ± SD | IoU ± SD | 召回 | P95 ms | 显存 MB | 门控 |
|---|---:|---:|---:|---:|---:|---:|---|
| ConvNeXt U-Net baseline | 1 | 0.8987 | 0.8164 | 0.8908 | 3.57 | 22.19 | baseline |
| multiscale_depthwise_unet | 3 | 0.8978 ± 0.0113 | 0.8149 ± 0.0183 | 0.8933 | 4.25 | 20.14 | hold |
| **residual_attention_unet** | 3 | **0.9149 ± 0.0041** | **0.8435 ± 0.0071** | **0.9099** | 5.13 | 26.03 | **pass** |

空 mask 率 / 过分割率：0 / 0。

### 3.4 边界风险与不确定性量化

**risk_mask 方法** `fluorescence_signal_with_uncertainty_v1`：以概率图与不确定性图共同派生灰度风险图，记录 mean_risk、max_risk、risk_area_fraction、uncertain_area_fraction。

**不确定性量化**：`uncertainty = 1 - |p - threshold| / max(threshold, 1-threshold)`，与预测熵、TTA 方差共同取最大值。

### 3.5 医生复核闭环（写报告"医生复核"章节）

**标注 SOP**（`three_priority_capabilities_acceptance_v1_zh.md`）：
1. 记录原彩图、原始荧光图、设备叠加图及同步、曝光、倍率、工作距离
2. 医生先标 `bone_gate` 和 `ignore`，不得先看模型三类结果形成锚定偏差
3. 在可信骨面内独立标低/过渡/高活性区域
4. 记录取样点、标本方向、切缘、离体照片、病理编号、回映射可信度
5. 第二位医生独立复核；分歧保留原始版本，第三位或专题会议仲裁
6. `accepted`/`modified` 进入高权重复核清单；`rejected` 进入负例；工程草稿独立来源

**前端 `/annotations` 页面**：画笔、橡皮擦、多边形、撤销/重做、缩放、标签选择、草稿保存、提交复核、版本历史。

**训练准入 v2**（`osteo-vision-manual-annotation-training-manifest-v2`）：独立医生复核只是准入条件之一，同时校验机构训练授权、显式 training 用途、脱敏确认、病例映射表机构保管、批次状态、来源输入准入、SHA256。`TRAINING_SCOPE_DENY_MARKERS` 拒绝 "analysis only / competition only / exclude training / no training / validation only"。

**复核权重**：`accepted=4.0`、`modified=4.0`、`rejected=0.5`、`review_required=1.0`。

### 3.6 双签晋级（Ed25519 + 哈希链）

- `REQUIRED_APPROVAL_ROLES = ("physician", "project_reviewer")`，两角色独立 Ed25519 密钥
- `TRUSTED_PROMOTION_AUTH_SOURCES = {institution_sso, signed_session, verified_identity_token}`
- 追加式 SQLite 哈希链：sequence / approval_id / nonce / target_fingerprint / previous_record_hash / record_hash / record_json / recorded_at_utc
- 防重放：approval_id 与 nonce 唯一；24 小时提交窗口；密钥有效期与撤销状态校验
- 签名绑定模型 ID、checkpoint、已批准策略、完整证据包哈希
- 当前生产策略 SHA256 信任表和 Ed25519 公钥信任表均为空，任何自行填写的策略都无法获得运行替换授权

### 3.7 D074 骨活性代理训练结果（写报告"工程验证"章节）

- 数据：5 个 5-ALA/PpIX 人脑显微荧光样本，3 个患者，train/val/test=1/2/2
- checkpoint SHA256：`e3b7f69f4ca3ff6f7a79180695e1b3e8946c082f8e9f056bbf870b4d916e8764`
- 测试 macro Dice：0.733064
- 三类 Dice：低活性 0.8036 / 过渡 0.6107 / 高活性 0.7849
- 连续评分 MAE：0.1314
- 骨面 Dice：0.1022（极低，骨面泛化缺口）
- 选择性错误率 0.3015（约束 ≤0.15 失败）
- `engineering_utility_ready=false`、`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`
- 22 项晋级阻断原因

**写报告建议措辞**：D074 代理证明代码、训练脚本、安全门控、晋级协议可运行，同时暴露骨面泛化与不确定性排序缺口，目标域骨活性多任务模型仍需真实颌骨骨髓炎术中白光/ICG 配对、医生像素标注和独立测试后才能申请运行替换。

---

## 第四章 患者条件分割与安全第一（讲故事章节）

### 4.1 临床特征向量契约 `clinical-feature-vector-v1`（13 项）

| # | 特征 | 类型 | 范围 | 临床意义 |
|---|---|---|---|---|
| 1 | age_years | 数值 | 0-130 | 年龄，分层基础 |
| 2 | sex_at_birth_female | 二值 | 0/1 | 性别（女=1，男=0；intersex/unknown=OOD） |
| 3 | diabetes | 二值 | 0/1 | 糖尿病，骨髓炎危险因素 |
| 4 | hypertension | 二值 | 0/1 | 高血压 |
| 5 | renal_disease | 二值 | 0/1 | 肾病，影响用药 |
| 6 | immunosuppression | 二值 | 0/1 | 免疫抑制 |
| 7 | antiresorptive_medication | 二值 | 0/1 | **抗骨吸收用药（双膦酸盐/地舒单抗）— MRONJ 核心风险** |
| 8 | wbc_10e9_l | 数值 | 0-200 | 白细胞 ×10⁹/L |
| 9 | neutrophil_percent | 数值 | 0-100 | 中性粒细胞% |
| 10 | crp_mg_l | 数值 | 0-500 | C 反应蛋白 mg/L |
| 11 | esr_mm_h | 数值 | 0-200 | 血沉 mm/h |
| 12 | hemoglobin_g_l | 数值 | 20-250 | 血红蛋白 g/L |
| 13 | egfr_ml_min_1_73m2 | 数值 | 0-200 | eGFR mL/min/1.73m² |

**三类 mask**：`present_mask`（在分布内）/ `missing_mask`（缺失）/ `ood_mask`（边界外或类别未编码）。`mask_semantics` 固定语义。

**年龄自动派生**：pediatric(<18) / young_adult(<40) / middle_aged(<65) / older_adult(≥65) / unknown。对应"青壮年/老年"分层。

### 4.2 血液指标讲故事（11 项标准化指标库）

| 指标 | 单位 | 工程参考范围 | 进入 v1 特征向量 | 临床讲故事 |
|---|---|---|---|---|
| CRP | mg/L | 0-10 | ✅ | 急性期炎症标志物，骨髓炎活动期显著升高，监测治疗反应 |
| WBC | 10⁹/L | 3.5-9.5 | ✅ | 急性感染全身反应，慢性期可正常 |
| NEUT% | % | 40-75 | ✅ | 细菌感染活动，与 WBC 联合 |
| ESR | mm/h | 0-20 | ✅ | 慢性炎症，骨髓炎病程中长期升高 |
| HGB | g/L | 110-170 | ✅ | 贫血是慢性感染常见并发症 |
| eGFR | mL/min/1.73m² | 60-120 | ✅ | 肾功能，影响双膦酸盐与抗生素剂量 |
| PCT | ng/mL | 0-0.5 | ❌ | 降钙素原，重症感染/脓毒症预警（v2 候选） |
| ALB | g/L | 35-55 | ❌ | 营养状态，慢性消耗致低蛋白血症 |
| GLU | mmol/L | 3.9-6.1 | ❌ | 糖尿病血糖控制 |
| HbA1c | % | 4.0-6.5 | ❌ | 糖尿病长期控制，与骨髓炎复发相关 |
| CREA | μmol/L | 44-133 | ❌ | 肌酐，与 eGFR 互补 |

**质量门控**：
- 7 天新鲜度窗（`LAB_FRESHNESS_HOURS=168`）
- 单位规范化（支持 mg/L、mg/dl、10⁹/L、g/L、mm/h、mm/hr 等多单位换算）
- 中英文别名识别（"C 反应蛋白"、"超敏 C 反应蛋白"、"白细胞"、"血沉"、"血红蛋白"、"降钙素原"等）
- 异常方向派生（low/normal/high）+ 源 `abnormal_flag` 冲突检测
- 同指标最新相同时间冲突值全部取消准入

### 4.3 模型架构 `TinyPatientConditionedSegmenter2D`

- 双通道输入：白光 Bx3xHxW + 荧光 Bx1xHxW
- 影像主干：local 或 unet，输出 `image_only_logits`
- 临床编码器：`Linear(feature_count*2 → hidden) → ReLU → Linear(hidden → modulation_basis_count)`，输入 `[normalized_values, present_mask]` 拼接
- 空间基函数：`Conv2d → modulation_basis_count, 1x1 + tanh`
- 临床系数：`tanh(clinical_encoder(...))`
- 原始差异：`raw_delta = mean(spatial_basis * coefficients, dim=1)`，被 `±max_logit_delta` 钳位（KiTS23 配置 0.25）
- `delta_map = raw_delta * eligible_mask`，eligible 由四项联合：authorized + trusted + ~invalid_declared + present_fraction ≥ min_present_fraction
- `conditioned_logits = image_only_logits + delta_map`

### 4.4 4K 验证病例讲故事（case_516176330f）

**录入**：67 岁、男性、2 型糖尿病、高血压、二甲双胍、氨氯地平、CRP 32 mg/L，`review_status=review_required`。

**输入**：
- `competition_white_4k.jpg`（3840×2160，689,677 字节）
- `competition_icg_4k.jpg`（3840×2160，563,413 字节）
- 配准响应 0.366592（安全阈值 0.08），平移 [-0.0006, -0.0071] px

**输出**（四类 4K 证据）：
- 影像基础概率 PNG SHA256 = 患者条件概率 PNG SHA256（**逐字节一致**）
- 差异 mask：全零
- 不确定性图：89,531 个非零像素，最大 248
- 差异面积：0 px / 0.00%
- `spatial_effect_applied=false`
- 临床变量可用率 80%

**讲故事核心**：CRP 32 mg/L 远超工程参考上限 10 mg/L（提示炎症活跃），但即便如此，模型在没有目标域晋级和医生复核的情况下**绝不擅自改变边界**。这是"安全第一"理念的最直接证据。

### 4.5 KiTS23 代理训练与 no-harm 门失败

- 数据：5 例 KiTS23 公开 CT + 像素 mask + 临床 JSON，50 张 2D 切片，train/val/test=30/10/10
- 训练：288 批次，max_logit_delta=0.25，min_present_fraction=0.8，conditioning_warmup=256
- checkpoint SHA256：`74844abe17efd6ad2b411afe7569af84cfd4aa403c0336e531a0a1328ca501c1`

**测试集结果**：

| 指标 | 数值 |
|---|---|
| 条件 Dice | 0.243974 |
| 影像基础 Dice | 0.244188 |
| `conditioned_minus_image_only_dice` | **-0.000214** |
| 最大物理边界位移 | **183.478281 mm** |

**三门失败**：
- no-harm 门：Dice 差 -0.000214（虽几乎不变，但物理边界位移远超 2 mm 门）
- 亚组门：最差代理亚组 Dice 差为负
- 物理边界门：183.48 mm 远超 2 mm provisional 门

**晋级状态**：`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`、`clinical_claim_allowed=false`。

### 4.6 七层安全门控（写报告"安全第一"章节）

1. **数据准入门**：机构授权、脱敏、病例映射、目标病种、批次准入、配对、SHA256
2. **临床上下文核验门**：review_status=verified、deidentified=True、quality.status=ready_for_rule_summary、新鲜度合格
3. **特征向量契约门**：schema、version、context_checksum、feature_names、mask 互斥、值有限性、行语义、vector_checksum 八类校验
4. **checkpoint-Manifest 绑定门**：双向 SHA256、capability、model_family、四项运行时标志一致性、训练域一致性、特征名一致性
5. **代理模型禁标志门**：非目标域 checkpoint 不得携带任何 runtime 标志
6. **空间安全门**：`reviewed_bone_gate ∩ image_uncertainty_region ∩ sample_available`，六类失败原因码
7. **晋级双签门**：医生 + 项目复核员双角色 Ed25519、24 小时窗口、nonce 防重放、哈希链

**失败闭合原则**：任一门失败，`delta_map` 精确归零，患者条件结果 = 影像基础结果，差异 mask 全零，记录全部失败原因码供医生审阅。

---

## 第五章 创新点汇总（写报告"创新点"章节）

按赛题三项核心要求 + 安全架构 + 工程证据组织：

### 创新点 1：患者安全优先的三源多光谱骨活性判读
原彩图表达解剖 + ICG 表达灌注时序 + 紫蓝光骨自体荧光/研究性多西环素表达骨活性，软件融合三类证据并显示冲突和不确定区域。患者零用药优先 → ICG 基线 → 研究性多西环素 → 新型骨亲和探针四级递进。

### 创新点 2：骨活性连续谱 + 三类候选 + 无法判断区的统一表达
医生复核骨面内，白光与原始荧光双通道多任务网络同时输出骨面门控、连续活性评分、低/过渡/高三类概率、不确定性、拒答区。把传统"坏死骨/活骨"二分扩展为包含灰色地带的复核导向表达。拒答阈值由验证集选择性错误率与覆盖率联合约束选出，并冻结到测试集；任一安全门失败全图 abstain。

### 创新点 3：影像基础结果与患者条件结果双轨保留 + no-harm 回退
患者条件模型未通过 no-harm、校准、边界位移、亚组独立验证前，运行时强制 `spatial_effect_applied=false`、`delta=0`，概率回退为影像基础。差异 mask 全零、不确定性图保留、失败原因码逐样本记录。

### 创新点 4：4K 文件证据链与视频流低延迟路径共享同一模型和输出契约
4K 走 tiled 全证据（P95 5.78 s），实时走 `live_fast` 960 长边 JPEG overlay（P95 176 ms），两路径共用 `keyframe_residual_attention_unet_s20260715_20260715` checkpoint。4K 模型 P95 724 ms，连续 fast-output 模型 P95 36 ms。

### 创新点 5：倍率、工作距离、标定、坐标和位姿通过设备解耦 manifest 进入 L1/L2 验证
L0 未配准参考 + L1 静态仿体配准（FRE/TRE/重投影误差）+ L2 离线动态 AR（FFprobe PTS + 9 项安全参数 + 多倍率标定表 v2 + A/B/A 振荡检测 + 双签批准）。任一门控失败回退 L0。

### 创新点 6：医生标注、独立复核、训练准入、逐病例预测重算和双签晋级闭环
Ed25519 哈希链 + physician/project_reviewer 双角色独立密钥 + 24 小时提交窗口 + nonce 防重放 + 追加式 SQLite 哈希链 + 完整 bundle 导出 + 最终晋级器独立重放。`accepted/modified=4.0`、`rejected=0.5`、`review_required=1.0` 权重。

### 创新点 7：模型、数据、身份、配置、阈值、SHA256 和失效原因随病例证据包导出
JSON + CSV + Markdown + DICOM Secondary Capture + ZIP 证据包完整可追溯。15 份 manifest、47 条记录、138 个本地文件、约 5.51 GB 全部通过来源、许可字段和 SHA256 校验。

### 创新点 8：造影剂、图像处理、AI 复核和三维证据在同一安全架构下联动
统一输出契约 `bone_gate_mask` / `fluorescence_signal_mask` / `risk_mask` / `uncertain_mask` + 骨活性连续谱 + 三类候选 + 无法判断区。安全状态机贯穿造影剂、影像、模型和导航。

### 创新点 9：四环素骨荧光 + ICG 灌注 + 患者临床变量的多模态讲故事
四环素骨亲和机制（钙结合、活跃矿化区沉积、活骨绿色荧光、坏死骨弱荧光）+ ICG 灌注时序（AUC、最大上升斜率、time_to_peak）+ 13 项临床特征向量（年龄/性别/5 类基础病/6 项血液指标）+ 11 项标准化化验指标库 + MRONJ 核心风险用药识别。

### 创新点 10：模块化新型骨亲和探针设计 + A0-A4 分级实验矩阵
骨亲和端（双膦酸/膦酸）+ 感染识别端（革兰阳性菌细胞壁/生物膜）+ 近红外发光端（向 ICG 设备窗口适配）+ 连接臂（亲水性/空间位阻/药代）。A0 光谱 → A1 材料 → A2 细菌/细胞 → A3 组织/仿体 → A4 前临床，每阶段明确停止条件。

---

## 第六章 产品实现与算力（写报告"产品/实现/算力"章节）

### 6.1 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| 后端 API | Python 3.11 + FastAPI |
| 推理核心 | PyTorch + OpenCV + SimpleITK + nibabel + pydicom |
| 数据 | numpy + pandas + scikit-learn |
| 配置 | YAML |
| 质量门 | pytest + mypy + ruff + black + isort |
| 编排 | pyproject.toml + Makefile + scripts/ + tools/ |

### 6.2 工程规模与测试

- 核心测试 603 passed
- 后端测试 281 passed
- 前端 Vitest 208 passed, 1 skipped
- Playwright E2E 5 passed
- Ruff / Black / isort / 严格 mypy / Python 3.11 compileall / vue-tsc / Vite build 全通过
- 项目 readiness / 严格运行预检 / 活动文档审计 / Git whitespace 全通过

### 6.3 算力与性能

**硬件基线**：NVIDIA GeForce RTX 5060 Laptop GPU

**4K tiled 推理**：
- 45 个 tile，tile 512，overlap 64
- 模型 P50/P95 = 415.7/724.4 ms
- 端到端 P50/P95 = 2181.5/5776.7 ms
- GPU 峰值显存 723.6 MB

**连续帧 fast-output**：
- 960×720，JPEG q=0.85，AMP，关闭 TTA
- 服务 E2E P50/P95 = 154.7/176.5 ms
- 模型 P50/P95 = 34.4/36.4 ms
- 峰值显存 380.1 MB

**核心热路径优化**（v0.3.0-rc.2 基准）：
- 1024 连通域候选统计：31.91x 加速
- 3840×2160 质量评估：4.56x 加速
- 10,000 位姿最近邻批量查询：324.87x 加速
- 1,000 任务记录缓存查询：5.64x 加速

### 6.4 实时帧鲁棒性

- 请求体前容量准入、格式/尺寸门控、取消传播、错误码透传、输出路径约束、每病例有界保留（默认 120 帧，可配 1-1000）
- 临时目录生成 + 原子提交，Windows 目录替换 10/25/50/100/200 ms 有界重试
- 150 帧压力回归通过
- MP4 与摄像头连续分析串行请求、超时取消、指数退避
- 每帧唯一证据路径，防止浏览器复用首帧缓存

### 6.5 启动与部署

```powershell
conda env create -f environment.yml
conda activate osteo-vision
npm --prefix frontend install
start_platform.cmd
```

默认端点：
- 后端：`http://127.0.0.1:8001`
- 前端：`http://127.0.0.1:5174/`

严格模式启动执行：严格运行预检 + 模型预热 + checkpoint sidecar 校验 + 模型身份/family/阈值核验。

---

## 第七章 数据现状与外部验证缺口（写报告"待验证"章节）

### 7.1 数据现状

- 15 份来源 manifest
- 47/47 记录通过结构检查
- 138/138 本地文件通过存在性与 SHA256 检查
- 约 5.51 GB
- **目标域记录：0**
- **训练准入记录：0**

公开/代理数据覆盖：荧光手术代理视频、骨感染近似场景、牙科 CBCT、解剖标签、位姿/深度、ORNJ 临床结构化变量、KiTS23、D024 DentVoxel、D036 ToothFairy2、D046 OFDVDNET、D074 5-ALA/PpIX 人脑显微荧光、D086 牙列基准、D087 C3VD 等。

### 7.2 外部验证缺口（保持显式待验证）

1. 真实颌骨骨髓炎白光/ICG 联合病例
2. 可信医生像素级金标准与患者级独立测试集
3. 足量患者结构化变量与亚组样本
4. 真实设备全倍率、全工作距离、4K 标定与同步证据
5. 真实下颌仿体配准、漂移与离线动态 AR 物理精度
6. 新型荧光造影剂实物、光谱、选择性、安全性与组织实验

### 7.3 当前代理模型晋级状态

| 模型 | 晋级状态 | 运行时 |
|---|---|---|
| `keyframe_residual_attention_unet_s20260715_20260715` | 主线，通过严格门控 | runtime_allowed=true |
| `patient_conditioned_kits23_proxy_candidate` | no-harm 门失败 | runtime_replacement_allowed=false，强制 delta=0 |
| `bone_activity_multitask_d074_proxy_candidate` | 选择性错误率门失败 | engineering_utility_ready=false，空间候选关闭 |
| L1/L2 三维导航 | 工程验证通过 | 所有结果保持 L0/unregistered_3d_reference |

---

## 第八章 不可声称范围（必须写入报告"医学边界"章节）

1. 临床级自动诊断或替代医生判断
2. ICG 对颌骨骨髓炎的特异性
3. 患者指标已产生获准的个体化切除边界
4. 低活性候选等同于病理坏死骨
5. 置信度（含 0.80）等同于切除成功率、治愈率或复发率
6. L1/L2 工程结果等同于真实术中导航
7. 新型探针已经完成合成、安全性或人体验证
8. 四环素文献剂量可直接转化为本项目临床用药建议
9. D074 PpIX 人脑显微荧光代理结果等同于颌骨骨髓炎临床性能
10. KiTS23 腹部 CT 代理结果等同于目标域患者条件分割性能

---

## 第九章 关键文件与证据索引（可追溯）

### 9.1 报告与母稿
- [技术方案 v0.3.0-rc.2](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/submission/osteo_vision_technical_solution_20260719_zh.md)
- [证据索引](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/submission/competition_evidence_index_20260719_zh.md)
- [三项优先能力固定目标](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/planning/three_priority_capabilities_target_20260717_zh.md)
- [三项优先能力验收协议 v1](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md)
- [造影剂可行性论证](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/planning/competition_advisor_suggestions_feasibility_20260717_zh.md)
- [四环素自体荧光价值评估](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/planning/tetracycline_autofluorescence_value_assessment_20260704_zh.md)
- [主线晋级报告](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/modeling/keyframe_residual_attention_mainline_promotion_20260715_zh.md)
- [4K tiled 运行门控](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/modeling/keyframe_residual_attention_4k_runtime_gate_20260715_zh.md)
- [live_fast 运行门控](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md)
- [4K 患者条件运行验证](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/modeling/patient_conditioning_4k_registered_runtime_20260719_zh.md)
- [v0.3.0-rc.2 发布快照](file:///c:/Users/876762330/Desktop/projects/osteo-vision/research/reports/release/v0.3.0-rc.2_20260719_zh.md)

### 9.2 核心配置
- [任务包](file:///c:/Users/876762330/Desktop/projects/osteo-vision/configs/tasks/osteo_vision.yml)
- [开发推理配置](file:///c:/Users/876762330/Desktop/projects/osteo-vision/configs/inference/osteo_vision.yml)
- [严格比赛配置](file:///c:/Users/876762330/Desktop/projects/osteo-vision/configs/inference/osteo_vision_competition_strict.yml)
- [KiTS23 代理训练配置](file:///c:/Users/876762330/Desktop/projects/osteo-vision/configs/training/patient_conditioned_kits23_proxy.yml)
- [骨活性 D074 代理训练配置](file:///c:/Users/876762330/Desktop/projects/osteo-vision/configs/training/bone_activity_multitask_d074_proxy.yml)

### 9.3 核心源码
- [白光/荧光融合](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/preprocess/fluorescence.py)
- [三通道质控](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/preprocess/three_channel_quality.py)
- [keyframe 分割器](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/keyframe_segmenter.py)
- [骨活性多任务模型](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/bone_activity_multitask.py)
- [骨活性运行时](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/bone_activity_runtime.py)
- [患者条件分割模型](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/patient_conditioned_segmenter.py)
- [患者条件运行时](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/patient_conditioned_runtime.py)
- [临床特征向量](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/clinical_feature_vector.py)
- [视频信号 mask 契约](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/models/video_signal_masks.py)
- [坐标契约](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/navigation/coordinate_contract.py)
- [刚性点配准](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/navigation/rigid_registration.py)
- [相机 PnP 配准](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/navigation/camera_registration.py)
- [离线位姿回放](file:///c:/Users/876762330/Desktop/projects/osteo-vision/src/navigation/offline_pose_replay.py)

### 9.4 后端服务
- [L1 静态配准服务](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/static_registration_service.py)
- [L2 离线位姿回放服务](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/offline_pose_replay_service.py)
- [3D 证据与导航安全门控](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/three_d_evidence.py)
- [CBCT 建模服务](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/cbct_modeling_service.py)
- [临床上下文评估](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/clinical_context_assessment.py)
- [患者条件门控](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/patient_conditioning_gate.py)
- [医生标注服务](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/manual_annotation_service.py)
- [双签晋级审批](file:///c:/Users/876762330/Desktop/projects/osteo-vision/backend/src/services/promotion_approval_service.py)

### 9.5 前端关键页面与组件
- [三维导航工作台](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/pages/NavigationWorkspacePage.vue)
- [病例工作台](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/pages/CaseWorkspacePage.vue)
- [医生标注页](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/pages/ManualAnnotationPage.vue)
- [三维证据控制面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/ThreeDEvidenceControlPanel.vue)
- [独立三维渲染运行时嵌入](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/ThreeDRendererRuntimeEmbed.vue)
- [L1 配准面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/L1RegistrationPanel.vue)
- [L2 位姿回放面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/L2PoseReplayPanel.vue)
- [导航安全状态面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/NavigationSafetyStatusPanel.vue)
- [三通道质控面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/ThreeChannelQualityPanel.vue)
- [骨活性谱面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/ViabilitySpectrumPanel.vue)
- [患者条件证据面板](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/PatientConditioningEvidencePanel.vue)
- [骨面门控编辑器](file:///c:/Users/876762330/Desktop/projects/osteo-vision/frontend/src/components/BoneGateMaskEditor.vue)

---

## 写报告建议的章节结构

1. **第一章 项目背景与意义**：颌骨骨髓炎临床痛点 + ICG 边界 + 赛题三项要求 + 本平台定位
2. **第二章 新型荧光造影剂设计**：三源多光谱 + ICG 基线 + 四环素/自体荧光 + Evans blue + 模块化探针 + A0-A4 矩阵
3. **第三章 多模态图像融合与处理**：官方输入 + 10 步融合链 + 三路质控 + 4K tiled + 连续帧 fast-output
4. **第四章 AI 辅助显微成像判读**：video_signal_segmentation + 四类 mask + 骨活性连续谱 + 主线模型 + 医生复核闭环 + 双签晋级
5. **第五章 患者条件分割与安全第一**：13 项特征向量 + 11 项血液指标 + 七层安全门控 + no-harm 回退 + 4K 验证讲故事
6. **第六章 三维配准与离线 AR**：设备解耦 + L0/L1/L2 + 坐标契约 + Kabsch SVD + solvePnP + 9 项安全参数 + 失效回退
7. **第七章 产品实现与算力**：技术栈 + 工程规模 + 测试 + 性能基准 + 启动部署
8. **第八章 创新点**：10 项创新点汇总
9. **第九章 工程验证与数据现状**：v0.3.0-rc.2 基线 + 15 manifest + 代理模型结果 + 外部验证缺口
10. **第十章 医学边界与不可声称范围**：10 项不可声称 + 患者安全总框架 + 医生复核边界

---

## 附录：挑战杯扩展叙述边界提示

挑战杯比赛允许有理有据的扩展叙述，但本素材包遵循以下边界：

- **工程证据**：所有 Dice/IoU/延迟/显存/SHA256/manifest 数值均来自项目实际运行结果，可追溯
- **医学机理**：ICG/四环素/Evans blue 机理来自项目下载的文献证据，PMID/DOI 可查
- **创新点表达**：可在工程证据基础上做叙事扩展，但不得声称未验证的临床性能
- **讲故事**：4K 验证病例（67 岁、男、糖尿病、CRP 32）为真实工程运行结果
- **代理数据**：KiTS23/D074/D086/D087 等代理结果明确标注为非目标域，不包装为目标域临床性能
- **不可声称**：第八章 10 项必须保留，无论报告如何扩展叙述
