# R01-R08 问题修复与证据报告

## 1. 结论

2026 年 7 月 10-11 日已完成 R01-R08 的平台工程修复与复核。各项均已形成代码、测试、运行产物或证据索引；完成范围限于当前团队可执行的代理工程闭环。所有模型指标均来自公开 D046 非目标域视频的伪标注或 prompt-assisted 种子，不代表真实术中 ICG 颌骨骨髓炎临床性能。

| 编号 | 问题 | 修复状态 | 核心证据 |
|---|---|---|---|
| R01 | 视频源级数据泄漏 | 已完成 | 48 个视频源分组，train/val/test 为 28/14/6，`leakage_detected=false` |
| R02 | 多 mask 模型全零 | 工程修复完成 | 双头独立监督、有效性 mask、逐头阈值扫描；测试集两个头空 mask 率均为 0 |
| R03 | 历史 0.9093 指标可信度 | 已完成 | 旧值撤回泛化证据地位；独立测试源 Dice 0.9214，视频级 95% CI 0.9127-0.9302 |
| R04 | 最终平台证据链 | 已完成平台索引 | 按造影剂、多模态融合、AI 判读、设备边界和医学边界组织证据 |
| R05 | 白光/荧光联合 AI | 代理架构与接口已验证 | 四组消融均可运行；运行许可关闭时后端跳过执行并保留传统融合 |
| R06 | ICG 动态定量 | 解码帧软件链路已验证 | 原始解码帧/ROI 强度、背景扣除、归一化、达峰时间、上升斜率、AUC 和曲线质控 |
| R07 | 4K 分析稳定性 | 公开异域关键帧验证已完成 | 公开长 MP4、多帧率、异常编码、4K JPEG、45 tiles、回退和短时内存观察 |
| R08 | 不确定性 | 代理任务技术校准已验证 | 温度缩放、预测熵、TTA 方差、ECE/Brier、`uncertain_mask` 和复核优先级 |

## 2. R01 视频源级隔离

- 新增 `src/datasets/group_splits.py`，以 `source_video_path`、`source_path`、`video_path`、`patient_id`、`case_id` 为分组键。
- 清单生成、单 mask 训练、单 mask 评估和多 mask 清单均在发现跨 split 源时直接失败。
- 重建清单包含 192 帧和 48 个视频源：训练 112 帧/28 源，验证 56 帧/14 源，测试 24 帧/6 源。
- 训练集、验证集和测试集的源视频交集为空。

关键路径：

- `src/datasets/group_splits.py`
- `tools/build_keyframe_segmentation_proxy_manifest.py`
- `tools/build_video_signal_multimask_training_manifest.py`
- `scripts/train_keyframe_segmentation_proxy.py`
- `scripts/evaluate_keyframe_segmentation_proxy.py`

## 3. R02 多 mask 全零修复

新增 `src/models/video_signal_multimask.py`，训练脚本按图像聚合标签，并为 `fluorescence_signal` 与 `bone_gate` 提供独立有效性 mask、损失和阈值扫描。4-8 样本过拟合探针显示损失下降，完整训练后两个头均产出非空结果。

| 测试头 | 监督样本 | 阈值 | Dice | IoU | 空 mask 率 |
|---|---:|---:|---:|---:|---:|
| fluorescence_signal | 10 | 0.35 | 0.4984 | 0.3355 | 0 |
| bone_gate | 6 | 0.35 | 0.8722 | 0.7758 | 0 |

`bone_gate` 的 50 条标签仍为 `review_required` prompt-assisted 种子。该结果证明多头训练链路已经恢复，未形成医生骨面金标准。

## 4. R03 可信评估替换

历史 Dice `0.9093` 来自可能存在同源帧跨集合的代理实验，现降级为历史结果。新 checkpoint 使用验证集选择阈值 `0.45`，测试集只执行独立评估。

| 指标 | 独立测试源结果 |
|---|---:|
| Dice | 0.9214 |
| Dice 视频级 bootstrap 95% CI | 0.9127-0.9302 |
| IoU | 0.8546 |
| Boundary F1 | 0.9844 |
| 空 mask 率 | 0 |
| 过分割率 | 0 |
| ECE | 0.00524 |
| Brier score | 0.01973 |

评估对象为 D046 伪标注代理 mask。该表只支持工程泛化和相对比较。

## 5. R04 官方要求证据链

| 平台核心要求 | 当前平台证据 | 尚需外部补充 |
|---|---|---|
| 新型荧光造影剂设计 | ICG 基线、四环素/自体荧光、骨亲和与感染识别候选设计及验证矩阵 | 合成、光谱、稳定性、选择性、安全性和企业通道实测 |
| 多模态融合与处理 | 白光/荧光配准、背景扣除、伪彩、融合、ROI 定量、动态曲线、4K JPEG/MP4 关键帧闭环 | 企业原始双通道样片、标定数据和实机连续验证 |
| AI 辅助判读 | 无泄漏单 mask、多 mask、双通道消融、不确定性、医生复核和证据导出 | 真实目标域病例、医生金标准和前瞻性验证 |

最终提交应分别标注文献证据、代理工程证据、医生复核证据和真实目标域证据。造影剂实物、真实病例和企业实机证据仍属于外部依赖。

## 6. R05 双通道 AI

新增双编码器模型、训练脚本、推理 adapter 和后端附加输出。平台继续保留传统融合主流程。后端同时检查 `enabled`、`runtime_allowed`、checkpoint 和 adapter warmup；当前配置中的双通道模型 `runtime_allowed=false`，因此病例分析会记录跳过状态。四组消融使用同一无泄漏分组清单。

| 模式 | 验证 Dice | 测试 Dice | 测试 IoU | 测试空 mask 率 |
|---|---:|---:|---:|---:|
| white_only | 0.8530 | 0.8620 | 0.7580 | 0 |
| fluorescence_only | 0.8521 | 0.8594 | 0.7540 | 0 |
| early_fusion | 0.8573 | 0.8654 | 0.7632 | 0 |
| intermediate_fusion | 0.8509 | 0.8610 | 0.7563 | 0 |

验证集选择 `early_fusion`。当前白光由源图亮度合成，双通道结果用于证明架构、adapter、运行许可和传统融合回退可运行。

## 7. R06 动态荧光定量

关键帧链路从解码 MP4/JPEG 帧或显式 ROI 计算 8-bit luminance 强度统计，分割概率保持独立字段。`fluorescence_time_intensity_curve` 接受有效关键帧时间戳、P95 强度和背景强度，输出：

- 每帧背景扣除值和基线到峰值归一化值；
- 达峰时间 `time_to_peak_sec`；
- 最大归一化上升斜率；
- 归一化 AUC；
- 重复时间戳、动态范围和稀疏关键帧曲线标记。

视频 `quantitative_summary` 已加入 `fluorescence_time_intensity_curve`。当前 8-bit luminance 属于解码信号代理。跨病例解释仍需企业原始 NIR 通道，并锁定曝光、增益、照明、工作距离、ICG 剂量与注射时间。

## 8. R07 官方 4K 输入压力验证

首轮使用合成 3840x2160 JPEG 执行 5 次强制 tiling 推理：

- tile size 512，overlap 64，共 45 tiles；
- 5 次均生成全分辨率 mask、概率图、不确定性图、伪彩图和叠加图；
- 模型推理 P50 为 1587.4 ms；
- 端到端 P50 为 3481.8 ms，P95 为 7577.3 ms；
- 峰值 GPU 显存记录约 145.3 MB；
- mask 尺寸与 4K 输入一致。

当前性能支持 `keyframe-based playback analysis`。现有结果不支持整帧 30 FPS 声明，P95 仍受首次运行、TTA 和 PNG/JPEG 落盘影响。

2026 年 7 月 11 日补充公开真实视频验证：

- OFDVDnet 离体鸡腿荧光代理视频：170.53 秒、15 FPS；
- 胫骨骨髓炎内镜清创公开视频：113.98 秒、29.97 FPS、无荧光；
- 两个来源均生成 9 帧 contact sheet 并完成人工画面复核；
- 覆盖派生 6 FPS/29.97 FPS MP4、不可读 H.264 失败记录、公开源派生 4K JPEG、3 次 45-tile 推理、缺 checkpoint 回退和 8 次内存观察；
- 4K 单关键帧端到端耗时 3.94-4.28 秒，模型概率推理 1.52-1.56 秒；
- 报告：`research/reports/modeling/public_video_4k_validation_20260711_zh.md`。

## 9. R08 不确定性与复核优先级

- checkpoint 温度 `1.4138` 已进入运行配置；
- 推理启用水平翻转 TTA 方差；
- 概率熵和 TTA 方差合成技术不确定性；
- 输出概率图、不确定性图、`risk_mask`、`uncertain_mask` 和复核优先级；
- 独立测试源记录 ECE `0.00524`、Brier `0.01973`；
- 4K smoke 与公开视频 4K 验证已确认上述产物存在。

代理标签只能校准模型对代理任务的稳定性。疾病判断风险校准需要真实目标域医生金标准。

## 10. 主要产物

- 单 mask checkpoint：`artifacts/checkpoints/osteo_vision/keyframe_convnext2d_proxy_grouped_20260710.pt`
- 多 mask checkpoint：`artifacts/checkpoints/osteo_vision/keyframe_video_signal_multimask_v2_grouped.pt`
- 双通道 checkpoint：`artifacts/checkpoints/osteo_vision/dual_channel_proxy_20260710.pt`
- 独立测试报告：`research/reports/modeling/keyframe_threshold_eval_20260710_grouped_test/`
- 多 mask 报告：`research/reports/modeling/video_signal_multimask_v2_training_20260710_multimask_v2_grouped.json`
- 双通道消融：`research/reports/modeling/dual_channel_ablation_20260710_dual_channel.json`
- 4K 压力证据：`artifacts/platform_smoke/keyframe_tiling_20260710_grouped_5run/`
- 公开视频 4K 报告：`research/reports/modeling/public_video_4k_validation_20260711_zh.md`

## 11. 医学和交付边界

平台输出定位为荧光/灌注信号候选区、骨面待复核门控、边界风险、不确定性与医生复核辅助。所有代理指标都不能用于自动确诊、疾病终判或替代医生判断。真实目标域 MP4/JPEG、医生像素级标注、造影剂实物实验和企业显微镜实机验证仍需后续协作完成。
