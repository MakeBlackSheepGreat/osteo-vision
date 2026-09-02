# 骨活性多任务模型闭环缺口独立审计

日期：2026-07-19

## 1. 审计边界

本次审计覆盖低活性、过渡、高活性、无法判断区和连续骨活性评分的模型结构、训练、运行适配器、病例分析接入、前端、报告及医生标注回灌。所有结论保持研发验证、医生复核和非诊断边界。

## 2. 当前证据

- `src/models/bone_activity_multitask.py` 已提供白光与荧光双编码、多任务输出、拒答、可信骨面门控和非有限值失败闭合。
- `scripts/train_bone_activity_multitask_proxy.py` 已完成确定性代理训练和 D074 真实公开显微荧光代理训练，训练 manifest 固定验证集阈值选择、测试集冻结和患者组隔离。
- D074 测试集 `macro Dice=0.733064`、连续评分 `MAE=0.131430`、接受覆盖率 `0.056417`、选择性错误率 `0.301527`。覆盖率与选择性错误率未通过预设约束，`engineering_utility_ready=false`。
- `backend/src/services/review_service.py` 与 `src/models/video_signal_masks.py` 已基于医生复核骨面、荧光概率图和无法判断区生成规则派生三类空间候选。
- 前端 `ViabilitySpectrumPanel.vue` 和报告导出已能展示、汇总规则派生的 `bone_activity_spectrum-v2`。
- 人工标注页已提供 `low_activity`、`transition`、`high_activity`、`ignore` 标签；现有训练清单仍缺少把同一源图的多类医生标注、可信骨面和连续评分组合成多任务训练样本的专用构建器。

## 3. 本轮修复

本轮补齐了训练 checkpoint 到统一模型适配器之间的真实运行链：

1. 新增 `src/models/bone_activity_runtime.py`，加载 checkpoint 前校验 manifest schema、manifest SHA256、checkpoint SHA256、模型配置、训练域、输出契约、冻结阈值、晋级字段和临床声明字段。
2. 新增 `BoneActivityMultiTaskAdapter` 并注册 `bone_activity_multitask` 模型家族。
3. 在开发配置登记 `bone_activity_multitask_d074_proxy_candidate`。该候选只能显式选择，保持 `candidate_only=true`、`runtime_replacement_allowed=false`、`mainline_replacement_allowed=false`、`strict_promotion_authorized=false`。
4. 代理 checkpoint 可执行真实前向推理并输出 SHA256 绑定的原始工程数组、来源图像校验码和证据 JSON。安全输出保持所有空间候选不可用。
5. 空间候选解锁同时要求目标域输入、已批准模型晋级、已验证双通道配准，以及绑定标注版本、源图 SHA256、像素数、时间和可信医生身份的骨面门控。
6. 严格生产配置继续排除该代理候选，当前主线模型配置保持原状。

真实 D074 checkpoint 已经通过统一适配器执行：

- 原始工程数组：`artifacts/visual_evidence/osteo_vision/bone_activity_multitask/d074-runtime-adapter-validation_92bba542485ec338_bone_activity_raw_engineering_outputs.npz`
- 原始工程数组 SHA256：`ecb4c27c8a98abe883b8f09510de1e1fe25c3ca9617ab4b40d5c357425b68bf9`
- 运行证据：`artifacts/visual_evidence/osteo_vision/bone_activity_multitask/d074-runtime-adapter-validation_92bba542485ec338_bone_activity_evidence.json`
- 运行证据 SHA256：`05aff753b29e6b34e5463a685581b276a09eef6c629e6182b2ff9723c199ef25`
- 结果：`engineering_inference_executed=true`、`spatial_candidates_available=false`、`runtime_replacement_allowed=false`。

## 4. 剩余真实缺口

### P0：病例分析链尚未调用骨活性 checkpoint 适配器

`AnalysisService` 当前没有选择或执行 `bone_activity_multitask`。病例工作台、病例证据包和报告中的骨活性连续谱仍来自规则派生链。统一适配器已经可运行，下一步需要在已配准 JPEG 双通道分析中显式调用候选，并把运行证据作为独立模型证据持久化。代理状态下只能展示工程执行状态、校验码和安全回退原因。

### P0：医生多类标注尚未形成多任务训练 manifest

人工标注存储能够保存四类 mask，训练脚本要求每个样本同时提供白光、荧光、骨面、连续评分、三分类和不确定性六类资产。当前缺少以下组合逻辑：

- 按源图、病例、帧和标注版本聚合同一组医生标注。
- 校验低活性、过渡、高活性、无法判断区互斥并覆盖可信骨面。
- 记录独立医生复核、仲裁状态、来源图 SHA256、各 mask SHA256 和样本权重。
- 将未覆盖骨面转入 `ignore`，将冲突像素转入仲裁队列。
- 按患者、机构和时间生成隔离切分，并输出训练脚本可直接读取的 CSV。

### P1：骨活性候选缺少同协议多模型比较

当前只有一个双编码多任务家族完成 D074 训练。最终选型仍需在同一数据清单、切分、预处理、阈值选择和冻结测试协议下比较至少两个可复现候选，并记录三类 Dice、连续评分 MAE、骨面 Dice、ECE、覆盖率、选择性错误率、延迟和资源占用。

### P1：前端和报告尚未区分规则谱与 checkpoint 谱

前端当前只消费 `bone_activity_spectrum-v2`。后续接入病例分析链时需同时显示 `evidence_source=rule_derived` 或 `checkpoint_multitask`、checkpoint SHA256、manifest SHA256、晋级状态、拒答原因和原始工程证据边界。代理 checkpoint 的三类图、面积和连续评分空间图保持隐藏。

## 5. 下一实施顺序

1. 将统一适配器接入双通道病例分析，持久化独立模型证据并保持代理空间输出关闭。
2. 实现医生四类标注与可信骨面聚合的多任务训练 manifest 构建器和冲突仲裁队列。
3. 在公开代理和后续目标域医生标注上运行同协议多模型比较。
4. 取得目标域配对白光/荧光、可信骨面和独立医生四类像素标注后，执行患者级、机构级和时间级训练与冻结测试。
5. 通过校准、亚组、安全、双签名审批和独立晋级验证后，再申请启用 checkpoint 空间候选。

当前软件已经证明 D074 checkpoint 可由统一运行框架真实执行并生成可追溯证据。目标域训练、临床三分类性能和运行替换仍未完成。
