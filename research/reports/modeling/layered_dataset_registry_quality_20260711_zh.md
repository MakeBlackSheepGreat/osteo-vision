# 分层数据注册与质量门控报告

## 结果

- 注册记录：504
- 质量门：通过
- 错误：0
- 警告：63
- 目标域记录：0
- 可进入训练准入检查的记录：393
- 隔离的缺失文件记录：3
- 按 source group 重分配的泄漏风险行：95
- 分层统计：`{"derived_proxy": 393, "fluorescence_proxy": 56, "near_domain": 55}`
- 标签统计：`{"automated_seed_mask": 9, "none": 102, "prompt_assisted_mask": 1, "proxy_mask": 392}`
- 使用策略统计：`{"engineering_source_reference": 74, "jaw_clinical_weak_label_seed_after_panel_crop_and_review": 4, "literature_reference_only": 1, "mechanism_reference_only": 3, "non_jaw_bone_infection_seed_after_panel_crop_and_review": 2, "oral_adjacent_weak_label_seed_after_panel_crop_and_review": 7, "preclinical_proxy_seed_after_panel_crop_and_review": 4, "proxy_pretrain_only_with_boundary": 192, "proxy_training_allowed_with_boundary": 201, "reference_only_no_derivatives": 1, "weak_label_training_seed_with_attribution": 15}`

## 质量门范围

来源链接与本地文件、SHA256、分组切分泄漏、重复内容、标签与复核状态、目标域标记、样本权重契约均纳入自动检查。
缺失本地文件的源记录进入隔离清单。多 mask 原始 manifest 中跨组切分不一致的行已按原始视频组统一切分，并保留逐行修正记录。

## 数据边界

当前注册表包含 OFDVDnet 鸡腿模拟荧光手术视频、公开骨髓炎清创视频、颌骨荧光论文图及代理/半自动多 mask 样本。目标域记录数为 0。论文多面板原图只作为近域来源资产注册，不直接进入分割训练。所有训练指标均属于非目标域工程证据。

## 后续使用

训练候选应先通过本质量门。医生复核产生的 accepted/modified/rejected 状态需继续沿用 4.0/4.0/0.5 权重契约；review_required 保持 1.0。
