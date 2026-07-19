# D047/D048 论文多面板原子裁剪建议报告

生成日期：2026-07-11

## 1. 目的

本轮针对 D047/D048 中 14 张尚未裁剪的论文原图建立可追溯的多面板拆分流程，补充口腔荧光、骨块白光/荧光近似配对、荧光显微和病理证据。全部结果属于非目标域复核种子，不具备医生金标准身份。

## 2. 实现

- 新增 `src/datasets/static_panel_detection.py`：使用白色分隔带投影、递归切分、弱接缝双栏回退、bbox 去重和质量门生成面板建议。
- 新增 `tools/build_static_panel_crop_suggestions.py`：读取 D047/D048 队列，生成稳定子记录和统一建议 manifest。
- 对 14 张本地原图完成逐图目视审计，使用出版物 caption 校对面板角色、配对关系和弱时序边界。
- 后端队列暴露建议 bbox、检测方法、分数、质量警告、面板角色和配对可信度。
- 前端裁剪器以橙色虚线展示原始建议，以绿色实线展示当前修改；提供“接受建议”和“保存修改”两个动作。
- 保存裁剪后继续保持 `review_state=review_required`、`training_eligible=false`，并撤销该记录的旧自动 seed。

## 3. 当前数据结果

| 项目 | 数量 |
|---|---:|
| 待处理原始多面板图 | 14 |
| 原子面板裁剪建议 | 52 |
| 质量门通过 | 40 |
| 带警告建议 | 12 |
| `fluorescence_signal` | 19 |
| `paired_white_light` | 13 |
| `paired_fluorescence` | 13 |
| `histopathology` | 7 |
| 唯一配对 ID | 14 |
| 当前静态复核队列 | 61 |
| 人工/医生已复核 | 0 |
| 训练准入 | 0 |

52 条建议来自 14 张原图，保留相同 `source_group_id`，因此同一论文或病例来源可以继续执行组级切分。当前 9 条既有自动 mask seed 仍保留，新增 52 条只进入裁剪复核阶段。

## 4. 质量控制

质量门覆盖：

- bbox 越界和非法尺寸。
- 面板面积低于原图 2%。
- 短边低于 96 px。
- 极端长宽比。
- 接近整图的裁剪。
- 白色或黑色边框残留。
- 重复候选和高 IoU 候选。

PMC12829038 的 C-D 配对记录为 `weak_sequential`，只用于粗粒度双模态表征。PMC7666678 与 PMC8132458 的部分配对记录为 `approximate_view`。这些配对不得作为像素级配准监督。出版物字母、箭头和比例框可能形成模型捷径，后续训练需降权或遮挡增强。

## 5. 证据与复现

- 建议 manifest：`research/datasets/public-candidates/d047_d048_static_crop_suggestion_manifest.json`
- 复核工作台：`http://127.0.0.1:5174/dataset-review`
- 建议总览：`artifacts/data_review/d047_d048_52_crop_suggestions_contact_sheet.jpg`
- UI 截图：`artifacts/platform_smoke/dataset_crop_suggestions_ui_20260711.png`

执行命令：

```powershell
conda run -n osteo-vision python tools/build_static_panel_crop_suggestions.py --apply
conda run -n osteo-vision python -m pytest tests/unit/test_static_panel_detection.py backend/tests/contract/test_dataset_review_api.py -q
```

## 6. 医学与训练边界

- 自动建议只用于减少人工寻找面板的工作量。
- `suggested_panel_role` 和 `suggested_pair_id` 需要项目复核人员或医生确认。
- 裁剪接受不会自动生成医生 mask，也不会自动进入训练。
- 后续 mask 仍需独立提交 `accepted`、`modified` 或 `rejected` 状态。
- D047/D048 仍为公开近域或异域资料，不能支持颌骨骨髓炎术中 ICG 临床性能结论。
