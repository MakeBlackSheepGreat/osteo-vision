# 挑战杯图包可重建源材料

本目录保存图包构建器所需的公开或合成工程源材料副本，使 `tools/build_challenge_cup_figures.py` 在干净工作树中可直接重建 `assets/manifest.json` 和报告配图。每个文件均服务于报告工程证据展示，不包含患者身份信息、真实目标域临床标签或临床性能结论。

| 文件 | 作用 | 来源与边界 |
| --- | --- | --- |
| `d083_frame_details_manifest.json` | D083 公开人体 ICG 视频的关键帧时序工程数据 | PMC9478374，CC BY 4.0；公开人体骨移植 ICG 视频代理，非颌骨骨髓炎目标域 |
| `d083_frame_05_*` | D083 原图、候选、风险和不确定性图层 | 同上；工程显示与复核流程证据 |
| `competition_white_4k.jpg`、`competition_icg_4k.jpg` | 3840x2160 合成白光/荧光配对输入 | 平台合成工程输入，只验证文件、融合和推理工作流 |
| `bone_activity_multitask_d074_proxy_20260719.json` | D074 骨活性代理指标摘要 | 公开人脑 PpIX 显微荧光代理，非骨、非 ICG、非颌骨目标域 |
| `challenge_cup_showcase_20260722.png` | 挑战杯工程展示页截图 | 本仓库前端工程截图，展示状态固定为工程验证与医生复核边界 |

原始下载、运行产物和完整来源记录继续留在数据登记与 `artifacts/` 本地证据链中；本目录仅保留报告重建必需的最小公开或合成副本。更新任一材料后，重新运行图包构建器并复核 `assets/manifest.json` 的 SHA256。
