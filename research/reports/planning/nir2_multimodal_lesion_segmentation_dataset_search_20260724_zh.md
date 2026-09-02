# NIR-II 多模态病灶分割数据检索与训练准入建议

日期：2026-07-24

## 1. 结论

本轮检索确认了 7 个 NIR-II/SWIR 数据来源。2026-07-25 对 `D096 EndmemberNet` 源码复核后，需取消其“已确认 NIR-II 病灶分割主数据集”的定位。其公开采集说明为 SWIR 荧光：使用 InGaAs 相机，并对 671、690、730、760、785 nm 五次激发依次采帧；公开文档未给出可由数据清单核验的发射峰值或 NIR-II 专属通道定义。其分割预处理将五张 TIFF 激发帧做最大值投影为单张灰度 PNG，分割 loader 再读取 PNG 和 `region_type` 条件，未提供同步白光/RGB 对。`tumor`、`intestine`、`colon`、`mln`、`vessel` 是可用的组织区域 mask 标签，`mln` 为源码标签，本报告不展开其医学全称。它可保留为 SWIR 光谱解混和异域组织 mask 代理候选。新确认的 `D102` 来自 PNAS 论文及作者公开仓库：数据可将 900-1300 nm NIR-I/IIa 图像映射到 1500-1700 nm NIR-IIb，包含 422.42 MB 宽场图像包和 136.57 MB 光片显微图像包。该来源无病灶像素 mask、无白光/RGB，数据许可也需作者确认；适合作为 NIR-IIb 图像域预训练和图像转换候选。`D100` 提供 NIR-I/SWIR 神经母细胞瘤荧光引导切除视频与论文图，病灶语义更接近手术边界，但缺少机器可读像素 mask。`D097` 只有 18 对 NIR-IIb 血管图和 mask，适合打通读取、切块、损失和评估流程，仓库未声明许可证，当前训练准入保持关闭。

当前未发现同时包含颌骨骨髓炎、白光、NIR-II、像素级病灶 mask、患者级元数据和医生复核记录的公开数据集。现有数据只能形成 NIR-II 模态预训练、异域病灶分割和工程验证证据，目标域性能需要后续设备数据和医生标注。

设备技术资料把 1000-1700 nm NIR-II 列为可参考研究方向。现有设备已经确认的光学窗口仍为 ICG 约 750-810 nm 激发和约 830 nm 发射。设备方确认 NIR-II 光源、InGaAs 探测器、滤光片和同步采集链路前，训练结果只能作为算法储备。

## 2. 候选优先级

| 优先级 | 数据源 | 可用内容 | 训练角色 | 准入状态 |
| --- | --- | --- | --- | --- |
| P1 条件候选 | D096 EndmemberNet | 公开代码确认 InGaAs SWIR 五次激发序列及五类区域 mask；训练预处理把五帧投影为单张灰度图 | SWIR 光谱解混复现、异域组织 mask 代理、数据适配器验证 | Hugging Face 数据镜像声明 GPL-3.0；Zenodo 许可与文件清单需逐文件复核；无白光/RGB 配对，不能直接用于双模态融合训练 |
| P0 | D100 AACR Neuroblastoma SWIR FGS | NIR-I/SWIR 装置对比、肿瘤切除视频、论文图和补充数据 | 手术病灶帧抽取、跨通道配准、人工复核 mask 种子 | CC BY 4.0；公开集合可用；原始数据仍需联系作者 |
| P1 | D097 NIR-IIb sO2 U-Net | 18 对 TIFF 图像和血管 mask，1500-1700 nm | 小规模 smoke、预处理、切块、损失和指标回归 | 已落盘并计算 SHA256；仓库无许可证，禁止进入正式训练清单 |
| P1 | D098 NIR-II vascular synthesis | 406 个真实 NIR-II patch；792 个视网膜血管 mask patch | 无配对域适配和 NIR-II 风格生成 | 论文声明联系作者获取 |
| P2 | D099 MamUNet | 人脑 NIR-II 血管分割实验数据 | 人体 NIR-II 血管表征 | 公开摘要未给出下载链接和规模 |
| P2 | D101 DOLPHIN | 约 7.34 GB NIR-II 高光谱和漫射样例 | 光谱校准、深度稳健性和重建 | CC0；缺少病灶 mask |
| P1 条件候选 | D102 Deep learning for in vivo NIR imaging | 900-1300 nm NIR-I/IIa 与 1500-1700 nm NIR-IIb 图像；422.42 MB 宽场包与 136.57 MB 光片包 | NIR-IIb 图像域预训练、图像转换、伪标签迁移研究 | 论文和仓库公开数据入口；无病灶 mask、无 RGB；数据许可需作者确认 |

完整机器可读清单见 `research/literature/inventory/nir2_multimodal_segmentation_candidates_20260724.csv`。

## 3. 直接下载入口

- D096 预处理训练数据：<https://zenodo.org/records/15253459>
- D096 原始预处理输入：<https://zenodo.org/records/15471213>
- D096 代码与数据组织：<https://github.com/Orange066/EndmemberNet>
- D097 小型 TIFF-mask 仓库：<https://github.com/ZhongLab2020/NIR-IIb_sO2_UNet>
- D100 AACR NIR-I/SWIR 神经母细胞瘤集合：<https://doi.org/10.1158/0008-5472.c.6678649.v2>
- D101 DOLPHIN 样例：<https://zenodo.org/records/4957897>
- D102 NIR-I/IIa 至 NIR-IIb 图像包与代码：<https://github.com/zhuoranzma/Deep-learning-for-in-vivo-near-infrared-imaging>

本地 D097 下载工具：

```powershell
python tools/download_nir2_segmentation_starter.py
```

输出目录：`research/datasets/public-candidates/d097_nir2b_vessel_masks_20260724/`。`raw/` 受 `.gitignore` 管理，manifest 和来源元数据可纳入版本控制。

## 4. 推荐训练组合

### 4.1 第一阶段：NIR-II 表征与分割管线

1. 使用 D097 完成 TIFF 解码、动态范围归一化、patch/tiling、二值分割损失、Dice/IoU/召回率/精确率、空 mask 率和过分割率测试。
2. 将 D096 置于条件准入：先核验上游数据许可、实际 TIFF 帧顺序、发射波段、动物或样本 group 及 mask 来源。准入后可仅用 `tumor` 子集复现 SWIR 异域 mask 基线，再加入 `mln` 和 `vessel` 作为辅助任务。
3. 将 D102 作为 NIR-IIb 图像域候选：先检查两份压缩包的图像计数、A/B 是否为成对样本、样本来源、许可证和 LFS SHA256，再决定用于无监督转换或成对图像转换；该数据不进入像素级病灶监督。
3. 将数据源、动物/人体、器官、探针、波段、采集设备、原始样本编号和 mask 类别写入患者或样本级 group，所有切分按 group 执行。

### 4.2 第二阶段：多模态病灶分割

建议采用双编码器：`白光/RGB encoder + NIR-II/SWIR encoder`，在四个尺度做 gated cross-attention 或 FiLM 融合。输出保留：影像基础结果、NIR-II 增益结果、差异图、不确定区和安全回退状态。

D096 的公开分割 loader 读取由五帧最大值投影形成的 PNG，并加入 `region_type` 条件；其模型输入为投影图与区域类别标量，缺少独立白光编码器和可核验的 NIR-II 原始通道。D096 可用于 SWIR 光谱解混或异域 mask 代理实验，不能直接充当白光-NIR-II 配对训练集，也不能据此声称完成 NIR-II 多模态训练。D100 视频需要先抽帧并核对画面布局，再由医生或项目标注页面生成 tumor mask 和配对关系。

### 4.3 第三阶段：颌骨骨髓炎目标域迁移

1. 白光分支优先使用已有颌面/骨病灶资源和医生复核 ROI。
2. SWIR 代理分支可在 D096 准入后使用其权重，只迁移低层光谱与边界表征；NIR-II 分支应优先使用已核验波段的来源或后续设备数据。
3. 真实设备数据到位后建立 `RGB + NIR-II + registration + lesion_mask + review_state` 五元组。
4. 目标域小金标准集按病例切分，保持独立测试集；在目标域测试通过前不替换生产主线 checkpoint。

## 5. 训练准入门

- D096：公开 Hugging Face 数据镜像标为 GPL-3.0，既有 Zenodo 记录许可信息与公开镜像不一致；保持 `training_eligible=false`，直至完成来源页、许可证、压缩包版本、SHA256、实际帧通道、样本 group 和 mask 有效性的逐项复核。
- D097：许可证与数据来源缺失，保持 `training_eligible=false`。可用于本地技术检查，正式训练需仓库所有者书面授权。
- D100：补充集合采用 CC BY 4.0；机器 mask 缺失，所有新标注必须记录标注者、版本、复核状态和来源帧。
- D098/D099：需要作者回复、许可范围和文件清单，授权前只保留候选条目。
- D102：论文的数据可用性声明和作者仓库已核验。代码为 BSD 类许可证，数据未见独立许可，保持 `training_eligible=false`，直至收到作者数据使用确认并完成压缩包内容、SHA256、样本来源和图像对关系审计。
- 所有动物、肿瘤、血管、肠道和神经母细胞瘤数据均标为非颌骨骨髓炎目标域。

## 6. 当前最可执行路线

近期训练应先完成 D097 管线 smoke。D096 的 `tumor` mask 可作为 SWIR 异域组织监督的候选，需先完成许可、发射波段和实际数据内容复核。D100 适合建立少量人工复核的手术病灶帧，补充跨通道与切除边界语义。分层完成后可训练“已核验 NIR-II 或 SWIR 模态预训练 + 异域肿瘤分割 + 目标域医生复核微调”的模型，不对颌骨骨髓炎临床性能作承诺。

## 7. 核验来源

- EndmemberNet 代码与采集说明：GitHub `Orange066/EndmemberNet`，其中 `imaging/README.md` 说明五次激发与 InGaAs 相机，`preprocess/weighted_synthesis.py` 与 `segmentation/dataset.py` 说明投影图训练流程；数据入口含 Zenodo `10.5281/zenodo.15253459`、`10.5281/zenodo.15471213` 与 Hugging Face `Orange066/Unmixing_TrainValTestData`，数据许可和文件清单以实际下载记录复核为准。
- EndmemberNet 论文：DOI `10.1038/s41566-025-01736-8`。
- D102：Ma et al., DOI `10.1073/pnas.2021446118`；PMC `PMC7817119` 的 Data Availability 明确指向作者公开训练与测试数据和代码；GitHub `zhuoranzma/Deep-learning-for-in-vivo-near-infrared-imaging` 的 README 说明 900-1300 nm 输入、1500-1700 nm NIR-IIb 目标及两个 Git LFS 数据包。
- NIR-II 合成数据：DOI `10.1038/s41598-025-91416-y`；PMCID `PMC11861915`。
- MamUNet：DOI `10.1109/ISBI60581.2025.10981261`。
- Neuroblastoma NIR-I/SWIR FGS：DOI `10.1158/0008-5472.CAN-22-2918`；PMCID `PMC10267675`；数据集合 DOI `10.1158/0008-5472.c.6678649.v2`。
- DOLPHIN：Zenodo `10.5281/zenodo.4957897`。
