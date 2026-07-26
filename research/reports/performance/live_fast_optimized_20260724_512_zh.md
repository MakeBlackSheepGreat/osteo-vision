# Residual Attention 当前生产模型实时单帧 fast-output 运行门控

## 结论

- 综合门控：`通过`。
- 当前生产模型门控：`通过`；同协议对照运行门控：`通过`。
- 同协议可比性：`True`。当前生产配置 SHA256 在运行前后保持一致，本门控未执行模型切换。
- 当前生产配置 SHA256：`fae1ca7a840cbdb60c5051a690e33551956acba452d4fe8713557863b34fe190`；对照配置 SHA256：`fae1ca7a840cbdb60c5051a690e33551956acba452d4fe8713557863b34fe190`。
- 本结果仅提供非目标域工程延迟和输出完整性证据，所有分割结果继续要求医生复核。

## 实测协议

- 输入：D046/OFDVDNET_023 公开离体荧光代理 MP4 的连续帧，经浏览器档位生成 JPEG；长边 `512`，质量 `0.85`，实际尺寸 `512x384`。
- 设备：`NVIDIA GeForce RTX 5060 Laptop GPU`；CUDA：`True`。
- 每个模型先执行模型 warmup 和 `1` 帧完整尺寸 warmup，再串行运行 `20` 帧计时样本。
- 已目视抽查源视频第 319 帧与第 326 帧：画面为白光/荧光多视口离体组织场景，无标题页；用途边界保持为公开离体非目标域荧光代理。
- 端到端范围覆盖 JPEG 解码、唯一原始证据写入、模型推理、mask/risk/uncertain mask 与 JPEG overlay 生成及落盘；HTTP、浏览器调度和网络传输未计入。

## 结果对比

| 运行角色 / 模型 | 服务 E2E P50 / P95 ms | 模型 P50 / P95 ms | 峰值显存 MB | mask/overlay | 唯一路径 | 门控 |
|---|---:|---:|---:|---|---|---|
| `current_production_model_via_isolated_candidate_config` / `keyframe_residual_attention_unet_s20260715_20260715` | 45.390 / 47.416 | 9.753 / 10.251 | 109.454 | 通过 | 通过 | 通过 |
| `previous_mainline_comparator_snapshot` / `keyframe_residual_attention_unet_s20260715_20260715` | 47.025 / 55.343 | 9.852 / 12.637 | 109.454 | 通过 | 通过 | 通过 |

当前生产模型 `keyframe_residual_attention_unet_s20260715_20260715` 相对同协议对照 `keyframe_residual_attention_unet_s20260715_20260715` 的服务 E2E P95 变化为 `-14.323%`，模型 P95 变化为 `-18.881%`。正值表示当前生产运行耗时更高。

## 输出核验

- 当前生产模型 `20` 帧与上一版主线 `20` 帧均使用 `live_fast`、CUDA AMP、关闭 TTA 的协议。
- 实际推理模式：当前生产模型 `whole_frame`，上一版主线 `whole_frame`。
- 每帧源 JPEG、二值 mask、risk mask、uncertain mask 和 JPEG overlay 均有独立路径；mask 与 overlay 尺寸匹配输入。
- fast-output 路径不落盘 probability map、uncertainty map 和伪彩图，保留前端实时显示与复核所需的 mask、风险提示和 overlay。

## 边界

输入来自公开或代理非目标域图像，且通过直接服务调用执行。当前证据不覆盖企业显微镜传输、浏览器到 API 的网络开销、4K 连续逐帧推理、真实术中 ICG 颌骨骨髓炎临床性能和手术室长时稳定性。
