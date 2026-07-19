# Residual Attention 当前生产模型实时单帧 fast-output 运行门控

## 结论

- 综合门控：`通过`。
- 当前生产模型门控：`通过`；上一版 ConvNeXt 主线同协议门控：`通过`。
- 同协议可比性：`True`。当前生产配置 SHA256 在运行前后保持一致，本门控未执行模型切换。
- 当前生产配置 SHA256：`9a2247035c27ba8f142d628f721bfb61d2e9b296a1201ccef375a98fc5f5e855`；上一版 ConvNeXt 隔离快照 SHA256：`4cbda808f7c8b4f75957dc62eb8176aff5c9db9892b00efee521e106cddf91f3`。
- 本结果仅提供非目标域工程延迟和输出完整性证据，所有分割结果继续要求医生复核。

## 实测协议

- 输入：D046/OFDVDNET_023 公开离体荧光代理 MP4 的连续帧，经浏览器档位生成 JPEG；长边 `960`，质量 `0.85`，实际尺寸 `960x720`。
- 设备：`NVIDIA GeForce RTX 5060 Laptop GPU`；CUDA：`True`。
- 每个模型先执行模型 warmup 和 `1` 帧完整尺寸 warmup，再串行运行 `8` 帧计时样本。
- 已目视抽查源视频第 319 帧与第 326 帧：画面为白光/荧光多视口离体组织场景，无标题页；用途边界保持为公开离体非目标域荧光代理。
- 端到端范围覆盖 JPEG 解码、唯一原始证据写入、模型推理、mask/risk/uncertain mask 与 JPEG overlay 生成及落盘；HTTP、浏览器调度和网络传输未计入。

## 结果对比

| 运行角色 / 模型 | 服务 E2E P50 / P95 ms | 模型 P50 / P95 ms | 峰值显存 MB | mask/overlay | 唯一路径 | 门控 |
|---|---:|---:|---:|---|---|---|
| `current_production_model_via_isolated_candidate_config` / `keyframe_residual_attention_unet_s20260715_20260715` | 154.685 / 176.457 | 34.368 / 36.377 | 380.134 | 通过 | 通过 | 通过 |
| `previous_mainline_comparator_snapshot` / `convnext2d_keyframe_proxy_segmenter` | 173.885 / 182.601 | 57.636 / 59.531 | 287.779 | 通过 | 通过 | 通过 |

当前生产 Residual Attention 相对上一版 ConvNeXt 主线的服务 E2E P95 变化为 `-3.365%`，模型 P95 变化为 `-38.894%`。正值表示当前生产模型耗时更高。

## 输出核验

- 当前生产模型 `8` 帧与上一版主线 `8` 帧均使用 `live_fast`、CUDA AMP、关闭 TTA 的协议。
- 实际推理模式：当前生产模型 `whole_frame`，上一版主线 `whole_frame`。
- 每帧源 JPEG、二值 mask、risk mask、uncertain mask 和 JPEG overlay 均有独立路径；mask 与 overlay 尺寸匹配输入。
- fast-output 路径不落盘 probability map、uncertainty map 和伪彩图，保留前端实时显示与复核所需的 mask、风险提示和 overlay。

## 边界

输入来自公开或代理非目标域图像，且通过直接服务调用执行。当前证据不覆盖企业显微镜传输、浏览器到 API 的网络开销、4K 连续逐帧推理、真实术中 ICG 颌骨骨髓炎临床性能和手术室长时稳定性。
