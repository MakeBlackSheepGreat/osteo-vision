# D047 颌骨荧光论文图数据闭环报告

## 结果

- 来源论文：4 篇 PMC 开放全文论文。
- 下载图像：10 张，全部具有来源页面、直接资产或归档链接、许可、SHA256 和本地路径记录。
- 可进入静态人工复核队列：8 张 CC BY 图像。
- 仅供参考：2 张。其中 1 张为 CC BY-NC-ND 临床图，1 张为机制示意图。
- 目标域记录：0。
- 工程面板裁剪：7 个，全部保持 `review_required`。
- 像素级医生标注：0；训练候选：0。

## 数据价值

本批图像覆盖下颌慢性硬化性骨髓炎、ONJ/MRONJ 骨暴露、骨切除、自发荧光/VELscope 观察和部分组织病理对应关系。其病种和解剖条件比离体鸡腿荧光视频更接近项目目标，可用于视觉复核、面板筛选、标注规范准备和后续域迁移种子。

所有原图均为论文多面板图，含白光、荧光、术后或病理子图。当前已完成 7 个荧光面板的工程裁剪，未生成像素 mask，未直接进入分割训练。

## 许可与训练门控

- `weak_label_training_seed_with_attribution`：进入人工复核队列，保持 `review_required`、`training_eligible=false`。
- `reference_only_no_derivatives`：永久禁止裁剪、派生和训练。
- `literature_reference_only`：仅用于机理论证和人工参考。
- 弱种子优先级使用 `sampling_weight=0.25`；复核可信度权重继续使用统一的 `sample_weight=1.0`。

医生或项目复核人员完成面板裁剪，并提供 prompt mask 后，记录仍需经过 accepted/modified 状态、来源组切分、许可检查和训练准入门，方可成为训练候选。

## 质量门结果

D047 的 10 张原图已作为 `near_domain`、`unlabeled` 来源资产进入分层数据注册表。更新后的注册表共 403 条记录，质量门通过：

- `near_domain`：46 条。
- `training_eligible`：301 条，D047 原始多面板图均不计入。
- 许可待核验警告：23 条，全部属于未进入训练的公开源记录。
- 全部 403 条图像与训练标签 SHA256 已实际复算，质量错误为 0。
- 目标域记录仍为 0，所有现有指标继续属于非目标域工程证据。

## 可视化复核

Contact sheet 已检查。8 张复核候选确实包含颌骨术野、骨切除、自发荧光或病理对应面板。CC BY-NC-ND 临床图和机制示意图未进入复核种子队列。

本地复核产物：

- `research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/derived/figure_review/pmc_figure_review_contact_sheet.jpg`
- `research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/derived/figure_review/pmc_figure_review_queue.json`
- `research/datasets/public-candidates/d047_pmc_jaw_fluorescence_figures/derived/figure_review/pmc_figure_review_queue.csv`

## 复现

```powershell
conda run -n osteo-vision python tools/download_pmc_jaw_fluorescence_figures.py
conda run -n osteo-vision python tools/build_pmc_figure_review_seed.py
conda run -n osteo-vision python tools/build_layered_dataset_registry.py
```

## 边界

D047 提高了目标条件附近的数据覆盖，仍缺真实术中 ICG 颌骨骨髓炎 MP4/JPEG、原始同步白光/NIR、医生像素标注和病理/培养关联。论文图不能用于报告目标域临床性能。
