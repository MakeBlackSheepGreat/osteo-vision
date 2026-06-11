# 数据集链接验证报告

验证时间：2026-06-11
来源文档：`3D数据集清单.docx`

---

## 验证结果统计

| 状态 | 数量 | 占比 |
|------|------|------|
| ✅ 可访问 | 18 | 90% |
| ⚠️ 超时 | 1 | 5% |
| ❌ 无法访问 | 1 | 5% |
| **合计** | **20** | **100%** |

---

## ✅ 已验证可用链接（18个）

### 3D数据集
| # | 链接 | 说明 |
|---|------|------|
| 1 | https://ditto.ing.unimore.it/toothfairy2/ | ToothFairy2 主页 |
| 2 | https://toothfairy2.grand-challenge.org/dataset/ | ToothFairy2 数据集（MICCAI 2024） |
| 3 | https://springernature.figshare.com/articles/dataset/MMDental... | MMDental 数据集 |
| 4 | https://physionet.org/content/multimodal-dental-dataset/ | PhysioNet 多模态牙科 |
| 5 | https://arxiv.org/abs/2208.01643 | CTooth+ CBCT 论文 |
| 6 | https://figshare.com/articles/dataset/DentVoxel... | DentVoxel（已在 D024） |

### 2D全景片
| # | 链接 | 说明 |
|---|------|------|
| 7 | https://www.nature.com/articles/s41597-026-07021-9 | ToothPix 论文 |
| 8 | https://physionet.org/content/inredd-dataset-pan924/ | InReDD 数据集 |
| 9 | https://dentex.grand-challenge.org/data/ | DENTEX 挑战赛页面 |
| 10 | https://tdd.ece.tufts.edu/ | Tufts 牙科数据库（已在 D002） |
| 11 | https://datasetninja.com/dental-panoramic-x-rays | 下颌分割数据集 |

### 多光谱/荧光
| # | 链接 | 说明 |
|---|------|------|
| 12 | https://datadryad.org/dataset/doi%3A10.5061/dryad.nvx0k6dxw | MODID 多光谱数据 |
| 13 | https://www.nature.com/articles/s41597-024-04099-x | MODID 论文 |
| 14 | https://sites.uef.fi/spectral/databases-software/odsi-db/ | ODSI-DB 光谱数据库 |
| 15 | https://arxiv.org/abs/2303.08252 | ODSI-DB 分割论文 |
| 16 | https://datadryad.org/dataset/doi%3A10.5061/dryad.8gtht76x9 | FGS 荧光视频去噪 |

### CBCT + 病历
| # | 链接 | 说明 |
|---|------|------|
| 17 | https://pmc.ncbi.nlm.nih.gov/articles/PMC12241571/ | MMDental 论文全文 |
| 18 | https://openreview.net/forum?id=nxGSj1xkm3 | MMOral 基准（NeurIPS 2025） |

---

## ❌ 已移除的问题链接（2个）

### 1. zenodo.org/records/13980878
- **状态**：无法访问（Transport error）
- **可能原因**：Zenodo 记录已删除或迁移
- **影响**：低（该数据集主存储在 Dryad，主链接 D042/D044 可用）
- **处理**：已从数据集清单中移除

### 2. github.com/ibrahimethemhamamci/DENTEX
- **状态**：响应超时
- **可能原因**：GitHub 仓库响应慢或暂时不可用
- **影响**：低（DENTEX 主数据在 Zenodo 和 Grand Challenge 页面）
- **替代方案**：使用 `dentex.grand-challenge.org/data/` 作为主入口
- **处理**：已从数据集清单中移除

---

## 结论

- **90% 链接可访问**，项目数据集清单整体可用
- 2 个问题链接已移除，不影响核心数据获取
- 建议优先使用已验证的核心数据集（D024、D025、D036、D037、D044）
