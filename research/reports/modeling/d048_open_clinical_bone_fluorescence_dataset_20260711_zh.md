# D048 开放临床骨荧光近域资产检索与下载报告

日期：2026-07-11

## 结论

本轮在 D047 之外新增 18 张可追溯原始论文图，来自 7 篇开放获取论文。全部来源经 PMC OA API 与全文许可段双重核验为 CC BY，原始图已经下载并完成 SHA256、尺寸、来源链接和许可记录。

- 人体临床手术图：11 张。
- 人体颌骨 ORN/MRONJ 荧光手术图：2 张。
- 人体口腔邻域荧光手术图：7 张。
- 人体非颌骨感染清创邻域图：2 张。
- 大动物颌骨荧光代理图：4 张。
- 荧光病理机制参考图：3 张。
- 许可允许进入后续弱标签复核流程的种子图：15 张。
- 已完成工程面板裁剪：2 个，均来自人体颌骨临床近域图并保持 `review_required`。
- 当前可直接训练的图：0 张。
- 新增开放补充视频：0 条。

所有论文图均为多面板合成图。当前已经为两张最接近目标条件的人体颌骨图生成工程裁剪；它们仍需候选 mask、`accepted`/`modified` 状态和组级切分。全部 D048 记录保持 `training_eligible=false`。

## 数据产物

- 下载工具：`tools/download_open_clinical_bone_fluorescence_assets.py`
- JSON manifest：`research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.json`
- CSV manifest：`research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/open_clinical_bone_fluorescence_manifest.csv`
- 原图目录：`research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/raw/`
- 本地视觉复核图：`research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/derived/contact_sheet_20260711.jpg`
- 颌骨面板复核更新：`research/datasets/public-candidates/d048_open_clinical_bone_fluorescence/jaw_clinical_panel_review_updates_20260711.json`

`raw/` 与 `derived/` 受 Git 忽略规则保护。manifest 保留每条记录的 PMC 页面、全文 XML、OA API、OA 包、CDN 资产链接、本地路径、许可文本、尺寸、文件大小、SHA256 和下载时间。

## 新增来源

| 来源 | 场景 | 选取图 | 许可 | 当前用途 |
|---|---|---:|---|---|
| [PMC9201330](https://pmc.ncbi.nlm.nih.gov/articles/PMC9201330/) | 人体颌骨放射性骨坏死荧光引导切除 | Figure 1 | CC BY 4.0 | 颌骨临床近域弱标签种子 |
| [PMC11355438](https://pmc.ncbi.nlm.nih.gov/articles/PMC11355438/) | 人体上颌 MRONJ，Qray 红色生物荧光引导切除及病理对应 | Figure 2、5 | CC BY 4.0 | Figure 2 为近域种子；Figure 5 为机制参考 |
| [PMC12829038](https://pmc.ncbi.nlm.nih.gov/articles/PMC12829038/) | 人体口腔种植体周围炎，BIS 引导 implantoplasty | Figure 1、3-8 | CC BY 4.0 | 口腔荧光邻域种子 |
| [PMC8132458](https://pmc.ncbi.nlm.nih.gov/articles/PMC8132458/) | 人体感染性髋关节翻修，四环素荧光引导坏死骨清创 | Figure 1、2 | CC BY 4.0 | 非颌骨感染清创邻域种子 |
| [PMC7666678](https://pmc.ncbi.nlm.nih.gov/articles/PMC7666678/) | 小型猪 MRONJ，自体荧光与四环素荧光对照 | Figure 2-5 | CC BY 4.0 | 大动物颌骨代理种子 |
| [PMC10222433](https://pmc.ncbi.nlm.nih.gov/articles/PMC10222433/) | 小型猪 MRONJ 氧四环素荧光组织学 | Figure 15 | CC BY 4.0 | 机制参考 |
| [PMC12129460](https://pmc.ncbi.nlm.nih.gov/articles/PMC12129460/) | 人体 MRONJ 红色荧光组织学 | Figure 3 | CC BY 4.0 | 机制参考 |

## 视觉复核

逐图 contact sheet 检查确认：

- `PMC9201330_Figure 1` 同时包含颌骨暴露、切除前绿色荧光、切除后均匀荧光和术中白光面板，适合建立成对面板复核任务。
- `PMC11355438_Figure 2` 包含上颌 MRONJ 清创过程与 Qray 红色荧光面板。单张图内非荧光面板比例较高，必须人工裁图。
- `PMC12829038` 七张病例图均包含多个口腔术野和红色/蓝紫色荧光面板，同时混有 X 线片与随访照片。仅荧光术野面板可进入候选训练队列。
- `PMC8132458` 两张图显示人体感染清创前后白光/紫外激发视图，解剖部位为髋部，需保持低权重邻域标记。
- `PMC7666678` 图像包含小型猪颌骨宏观、荧光和病理面板，可用于机制与域增强实验，禁止标记为人体临床数据。
- 三张病理参考图不进入术野分割训练。

## 训练准入边界

许可允许衍生处理只解决法律复用门槛。医学和标签门槛仍需独立完成。

1. 多面板原图先进入 `review_required` 队列。
2. 人工标记面板边界，保留荧光术野与匹配白光面板。
3. 每个裁图记录原始 `pmcid`、figure label、crop bbox 和 SHA256。
4. 采用 prompt-assisted mask 生成候选区域。
5. `accepted` 与 `modified` 样本进入低权重训练；`rejected` 样本进入负例或错误分析。
6. 同一论文、病例或原始 figure 只允许落入一个数据切分。
7. 人体颌骨临床图建议初始采样权重 0.30；口腔邻域图为 0.15；非颌骨感染与大动物代理图为 0.10。
8. 所有 D048 样本保持 `target_domain_flag=false`，直至获得真实颌骨骨髓炎白光/ICG 数据与医生金标准。

## 补充视频核验

Europe PMC `supplementaryFiles` 接口已核查本轮相关开放论文。发现的补充材料主要为 PDF、DOCX、XLSX、JPG 和 GIF。未发现 MP4、MOV、AVI、MPEG、WMV、M4V 或 WebM 文件。

目前仍未获得许可明确的 CC BY/CC0 颌骨骨髓炎、ONJ 或 MRONJ 荧光手术补充视频。该缺口继续列为一级数据风险。

## 排除与仅参考候选

| 文献 | 许可核验 | 处理 |
|---|---|---|
| [10.1016/j.pdpdt.2023.103867](https://doi.org/10.1016/j.pdpdt.2023.103867) | Crossref 记录为 CC BY-NC-ND 4.0 | 禁止衍生裁图与训练，仅作论文参考 |
| [10.1016/j.pdpdt.2024.104370](https://doi.org/10.1016/j.pdpdt.2024.104370) | Crossref 记录为 CC BY-NC 4.0 | 未纳入 D048；用途需另行审查平台研究与训练的非商业边界 |
| [10.1016/j.oooo.2020.10.018](https://doi.org/10.1016/j.oooo.2020.10.018) | Crossref 未给出开放衍生许可 | 未下载训练资产 |
| [10.1016/j.joms.2017.10.024](https://doi.org/10.1016/j.joms.2017.10.024) | Crossref 未给出开放衍生许可 | 未下载训练资产 |

## 医学边界

D048 增强了颌骨坏死、口腔荧光手术和感染骨清创的视觉先验。数据仍缺少真实颌骨骨髓炎白光/ICG 同步视频、设备原始 NIR 强度、医生像素标注、病理或培养对应和病例级独立测试集。任何代理训练指标仅能说明工程闭环与近域迁移准备程度。
