# D051 MRONJ 成像质谱平衡启动集

## 1. 来源与许可

- 数据名称：Raw Data and Supplementary Data of *Imaging Mass Cytometry Unveils Functional and Spatial Remodeling of Peri-lesional Cells in Jaw Osteonecrosis*。
- 来源页：[Figshare DOI 10.6084/m9.figshare.30383407](https://doi.org/10.6084/m9.figshare.30383407)。
- 版本化 API：[Figshare article 30383407 version 1](https://api.figshare.com/v2/articles/30383407/versions/1)。
- 许可：`CC BY 4.0`，已由 Figshare v1 元数据核验。
- 数据治理：论文 Data Availability 声明说明 Figshare 中为去标识化 IMC 原始数据及补充数据。
- 源记录：46 个文件、6,868,922,827 字节，包括 21 个 MRONJ ROI、21 个对照 ROI、2 个扁桃体参考 ROI、抗体 panel 和补充材料。

## 2. 本地下载范围

当前采用有界平衡启动策略：从每位 `Patient01-Patient06` 和 `CTRL01-CTRL08` 中选择体积最小的一个 ROI。启动集包含 6 位 MRONJ 受试者和 8 位对照受试者，每人一个 ROI，共 14 个原始 TXT。连同 `panel.csv`、补充材料和 Figshare API 元数据，共登记 17 个来源文件、1,111,860,023 字节。

原始 TXT 位于 `raw/`，大型原始文件受 Git 忽略规则保护。下载收据为 `d051_download_receipt.json` 和 `d051_download_receipt.csv`；数据集来源与用途清单为 `manifest.json` 和 `manifest.csv`。

## 3. 数据内容

- 每个 TXT 是带空间坐标的逐像素成像质谱强度表。
- 14 个 TXT 均有 54 列，并包含 `X`、`Y`、`Z` 坐标字段。
- `panel.csv` 登记 38 个抗体/标志物条目；TXT 还包含 DNA、金属和技术控制通道。
- 补充材料描述了上皮、基质、血管、细胞类型及功能状态等空间分析内容。
- 当前病例来自人类颌骨坏死围病灶组织，病理尺度与项目目标较接近，可用于空间标志物预处理、近疾病域表征和灰区生物学概念复核。

完整逐行校验结果见 `verification_20260718.json`：14 个 TXT 的列数、`X/Y/Z`、每行字段数、坐标可解析性、官方 MD5、本地 SHA256、文件大小、panel 和 DOCX 完整性均已通过。

## 4. 使用边界

该资源没有术中白光、ICG、CBCT、骨面真值、坏死/过渡/活骨手术边界，也没有与 ROI 配对的年龄、性别、基础病、用药和血液指标。当前 14 人、每人一个 ROI 的启动规模没有形成充分的患者级独立测试集。

因此本目录固定为 `target_domain_flag=false`、`training_eligible=false` 和 `review_required`。完成许可复核、内容复核、任务适配和训练准入前，不得进入主线训练；任何结果均不能用于患者条件空间分割、切除边界、导航精度或临床性能声明。

## 5. 复现命令

```powershell
conda run -n osteo-vision python tools/download_d051_mronj_imc_starter.py
conda run -n osteo-vision python tools/verify_d051_mronj_imc_starter.py --write
conda run -n osteo-vision python tools/verify_three_priority_dataset_manifests.py
```

下载工具默认只获取 14 人平衡启动集。只有明确需要完整源数据并确认本地容量后，才使用 `--all-rois` 获取全部患者、对照和扁桃体 ROI。
