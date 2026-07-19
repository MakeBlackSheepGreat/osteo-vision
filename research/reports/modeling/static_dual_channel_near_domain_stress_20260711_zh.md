# 静态近域双通道压力评估报告

生成时间：2026-07-11T06:12:31.897178+00:00

## 结果摘要

- 真实公开近域白光/荧光配对：6 对。
- 配对边界：{"approximate_view": 6}。
- 配准探针：{"pass": 2, "weak": 4}。
- 风险标记：{"context_fusion_low_white_sensitivity": 6, "intermediate_fusion_high_disagreement": 6, "pair_registration_unreliable": 4}。
- checkpoint SHA256：`0dd4d47f09b0a760f464619f20fdc402493d8bb62b2cfac02acb14ebff8fa397`。
- 双通道 checkpoint 继续保持 `runtime_allowed=false`，本轮只执行离线压力评估。

## 方法

每对图像使用固定尺寸输入五种模式：`white_only`、`fluorescence_only`、`early_fusion`、`intermediate_fusion`、`context_fusion`。其中 `context_fusion` 只使用白光全局上下文调制荧光特征，避免依赖像素对齐。报告各模式平均概率、阳性面积比例和预测熵，同时计算跨模式概率差异。近似同视野配对使用 ORB 与 RANSAC 单应探针；弱时序配对跳过像素配准。

## 工程结论

- 这些数据已经替换了压力评估中的合成白光输入，能够直接暴露模型面对真实口腔/骨荧光近域图像时的退化与模式冲突。
- `context_fusion` 与荧光单模态的平均概率差异约为 0.0013，空间错配敏感性较低；差异过小同时提示白光贡献可能不足，当前不能作为双通道增益证据。
- 配对均缺少像素级病灶 mask，当前无法计算 Dice、IoU 或边界误差。
- `weak_sequential` 和 `approximate_view` 记录不进入像素配准监督。
- 出版物箭头、字母和比例框可能影响预测，后续需加入遮挡增强和人工复核。

## 证据

- JSON：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\platform_smoke\static_dual_channel_stress_20260711\static_dual_channel_stress.json`
- 配对 manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d047_d048_static_paired_preview_manifest.json`
- checkpoint：`C:\Users\876762330\Desktop\projects\osteo-vision\artifacts\checkpoints\osteo_vision\dual_channel_proxy_20260710.pt`

## 医学边界

该评估只描述非目标域近域输入下的工程稳定性，不提供病灶识别准确性或临床性能结论。
