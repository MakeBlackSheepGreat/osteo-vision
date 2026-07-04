# 项目记录整合与文件夹整理报告

生成日期：2026-07-04

## 1. 本轮整理结论

本轮把项目记录按“事实清单、研究报告、历史交付物、工程产物”重新分层。当前可以继续保留的主线记录已经比较清楚：论文与数据集以 `research/literature/inventory/` 下 CSV 为准，规划/建模/预处理报告分别放入 `research/reports/planning/`、`research/reports/modeling/` 和 `research/reports/preprocessing/`，早期 DOCX/XLSX 交付物统一归档到 `research/reports/legacy/`。

已清理不应继续进入 Git 的 .NET DOCX 生成器编译产物：`research/scripts/legacy/docx-gen/bin/` 和 `research/scripts/legacy/docx-gen/obj/`。同时 `.gitignore` 已补充 `**/bin/` 与 `**/obj/`，避免后续重新把编译输出加入版本库。

## 2. 当前记录统计

| 类别 | 当前数量/状态 | 主记录位置 | 说明 |
|---|---:|---|---|
| 论文清单 | 60 条 | `research/literature/inventory/paper_inventory.csv` | 全部为 `link_only_no_local_pdf`，PDF 本地证据链仍不足。 |
| 本地论文/网页资产 | 8 条 | `research/literature/inventory/local_paper_assets_20260703.csv` | 主要覆盖四环素荧光、MRONJ、nnU-Net MRONJ CBCT 和骨坏死荧光资料。 |
| 数据集清单 | 45 条 | `research/literature/inventory/dataset_inventory.csv` | 核心 5 条，重要 5 条，可选 13 条，低相关 22 条。 |
| 视频候选清单 | 19 条 | `research/literature/inventory/video_dataset_candidate_inventory.csv` | 用于记录荧光/非荧光视频来源和训练价值分层。 |
| 已下载/记录视频 | 29 条 | `research/literature/inventory/video_download_manifest_20260703.csv` | 25 条非荧光骨髓炎/清创类视频，4 条荧光代理视频；记录体量约 3379.1 MB。 |
| OFDVDnet 视频 | 50 条 | `research/literature/inventory/ofdvdnet_video_manifest_20260704.csv` | 作为荧光手术视频代理数据，不是颌骨骨髓炎目标域。 |
| OFDVDnet baseline | 48 条 | `research/literature/inventory/ofdvdnet_fluorescence_baseline_manifest_20260704.csv` | 已生成荧光增强、伪彩和融合预览记录。 |
| 模型清单 | 7 个模型 | `research/reports/modeling/model_checkpoint_manifest_20260704.json` | 当前可用 4 个，不可用 3 个。 |
| 研究报告 | 91 个文件左右 | `research/reports/` | 含规划、建模、预处理、legacy 和报告资产。 |

## 3. 论文记录整合

`paper_inventory.csv` 当前仍是论文总清单。按类别统计：

| 类别 | 数量 | 当前用途 |
|---|---:|---|
| 模型方法 | 17 | 支撑 U-Net、nnU-Net、MedSAM、EGNet、FRS Loss、医学图像融合等路线。 |
| ICG荧光 | 17 | 支撑 ICG 医学边界、骨灌注、牙科 ICG 和术中显微镜荧光视频论证。 |
| 口腔AI | 9 | 支撑牙科影像、颌骨病灶、全景片/CBCT AI 辅助判断。 |
| 病种影像 | 8 | 支撑颌骨骨髓炎、骨坏死和慢性骨髓炎影像组学论证。 |
| AI方法 | 7 | 支撑泛化、融合、不确定性等方法论。 |
| 相关方法 | 2 | 作为补充背景。 |

下一步需要把 60 条清单按“比赛必引、报告可引、仅备查”再分三档，并优先补齐 15-20 篇核心 PDF 或网页快照。本轮未重新联网下载，避免混入未经核验的新来源。

## 4. 数据集与视频记录整合

当前数据资产应按目标域距离分层：

| 层级 | 数据源 | 当前状态 | 比赛用途 | 边界 |
|---|---|---|---|---|
| P0 目标域 | 官方 4K MP4/JPEG、医院/企业脱敏术中 ICG 样本 | 当前缺失 | 最终训练和评估目标 | 没有真实目标域样本时不能宣称临床级性能。 |
| P1 CBCT 代理 | D024 DentVoxel、D025 DOLCHID、D036 ToothFairy2 | 本地已有派生目录和报告 | 解剖先验、病灶代理分割、模型闭环 | 非术中 ICG 视频。 |
| P2 荧光代理 | OFDVDnet、FGS video、公开荧光手术视频 | 已有 OFDVDnet manifest 和 baseline | 伪彩、增强、融合、视频链路验证 | 非口腔、非颌骨骨髓炎。 |
| P3 非荧光骨髓炎视频 | PMC 清创/教学视频 | 已有 25 条记录 | 演示视频库、非目标域视频处理 | 无 ICG，无分割标签，不适合作监督训练。 |
| P4 口腔/多光谱补充 | MODID、ODSI-DB、牙科全景片等 | 部分仅有入口 | 方法论与预训练参考 | 距离官方 4K MP4/JPEG + ICG 主线较远。 |

## 5. 模型记录整合

当前可用模型：

| 模型 | 状态 | 说明 |
|---|---|---|
| `convnext3d_d025_proxy_segmenter` | 可用 | 使用 D025 CBCT 病灶 ROI 代理 checkpoint，面向工程验证。 |
| `d025_lesion_smoke_segmenter` | 可用 | 已训练 smoke 模型，Mean Dice 仍低，只能说明训练/推理闭环。 |
| `fluorescence_hotspot_2d_segmenter` | 可用 | 2D 荧光热点启发式，不是训练模型。 |
| `fixture_default` | 可用 | 测试和 fallback。 |

当前不可用模型：

| 模型 | 缺口 |
|---|---|
| `nnunet_v2_osteo_baseline` | 缺 checkpoint，adapter 推理未实现。 |
| `medsam2_osteo_promptable` | 缺 checkpoint，adapter 推理未实现。 |
| `biomedclip_osteo_screening` | 缺依赖 `open_clip` 和 checkpoint。 |

模型记录以 `research/reports/modeling/model_checkpoint_manifest_20260704.*` 为准。比赛表述应继续强调：现有模型是科研/竞赛原型和代理验证，不是临床诊断模型。

本轮新增训练候选：

| 模型 | 状态 | 结论 |
|---|---|---|
| `d025_monai_segresnetds_proxy_segmenter` | 已训练，未接入主线配置 | 在 D025 CBCT lesion ROI 64³ 缓存上完成 3000 batch 训练，最优阈值 0.20，Mean Dice 0.5741，Mean IoU 0.4766。低于当前 ConvNeXt-style 主线的 Dice 0.6266 和 IoU 0.5183，因此仅保留为 MONAI 对照 baseline。 |

新增模型报告：

- `research/reports/modeling/d025_monai_segresnetds_training_20260704_zh.md`
- `research/reports/modeling/d025_monai_segresnetds_training_20260704_en.md`
- `research/reports/modeling/d025_proxy_model_comparison_20260704_zh.md`
- `research/reports/modeling/d025_proxy_model_comparison_20260704_en.md`

## 6. 文件夹整理动作

已完成：

- 将早期根目录报告资料移动到 `research/reports/legacy/`：
  - `3D数据集清单.docx`
  - `颌骨骨髓炎.docx`
  - `项目资料汇总.docx`
  - `dataset_inventory.xlsx`
  - `paper_inventory.xlsx`
- 新增 `research/reports/legacy/README.md`，说明 legacy 文件只作历史复核。
- 从 Git 追踪中移除 .NET 编译输出：
  - `research/scripts/legacy/docx-gen/bin/`
  - `research/scripts/legacy/docx-gen/obj/`
- 清理本地缓存目录：
  - `.mypy_cache/`
  - `.pytest_cache/`
  - `.pytest_tmp/`
  - `.ruff_cache/`
  - `pytest_tmp/`
  - `output/`
  - `frontend/dist/`
  - `frontend/test-results/`

未触碰：

- `research/datasets/` 下公开数据和派生数据。
- `artifacts/` 下运行证据、checkpoint 和 smoke 输出。
- `node_modules/` 与 `frontend/node_modules/`。
- `research/literature/inventory/papers/` 和 `official/` 内本地资料。

## 7. 后续整理规则

后续新增材料建议按以下位置放置：

| 新材料类型 | 推荐位置 |
|---|---|
| 论文总清单 | `research/literature/inventory/paper_inventory.csv` |
| 本地论文/PDF/网页快照索引 | `research/literature/inventory/local_paper_assets_*.csv` |
| 数据集清单 | `research/literature/inventory/dataset_inventory.csv` |
| 视频来源和下载状态 | `research/literature/inventory/video_*manifest*.csv` |
| 官方技术文档对齐 | `research/reports/planning/` |
| 数据预处理报告 | `research/reports/preprocessing/` |
| 模型训练、评估和数据来源报告 | `research/reports/modeling/` |
| 历史 DOCX/XLSX 交付物 | `research/reports/legacy/` |
| 运行产物、checkpoint、smoke 输出 | `artifacts/`，不进入 Git |

## 8. 仍需补齐的记录缺口

1. 论文 PDF 证据链不足：60 条论文清单仍以链接为主。
2. 数据集许可和下载状态需要继续分层：尤其是 MODID、FGS video、OFDVDnet 和公开视频。
3. 真实目标域数据缺失仍是一级风险：没有真实 4K MP4/JPEG + 医生 ROI 标注，赛点二只能做原型验证。
4. 模型记录已经补上 D025 ConvNeXt-style 与 MONAI SegResNetDS 的代理训练/评估对比；下一步应转向 nnU-Net v2/DynUNet 高分辨率或 patch 级路线，并继续保留训练日志、评估表和失败样本。
5. DICOM 输出当前是 Secondary Capture 雏形，DICOM SR/SEG 仍应列为后续扩展。
