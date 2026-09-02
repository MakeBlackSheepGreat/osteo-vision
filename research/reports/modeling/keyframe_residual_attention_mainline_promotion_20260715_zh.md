# Residual Attention Keyframe 主线晋级报告

## 结论

`keyframe_residual_attention_unet_s20260715_20260715` 已晋级为平台软件的 JPEG/MP4 keyframe 分割主线。严格配置、研发配置和任务包已同步，上一版 `convnext2d_keyframe_proxy_segmenter` 保留为研发对照。

- 当前严格配置 SHA256：`9a2247035c27ba8f142d628f721bfb61d2e9b296a1201ccef375a98fc5f5e855`。
- 运行阈值：`0.4`；checkpoint SHA256：`826e90c2ee3efd45d0d0d979e85a2a3e2dcd60d853d8497f6328e46a406e0d39`。
- 严格启动预检通过：1 个必需模型完成 checkpoint、promotion sidecar、模型身份、family 和阈值核验；0 error、0 warning。
- 晋级后的 4K 完整平台流通过：`3840x2160` JPEG/MP4、2/2 keyframe probability map、医生工程复核、证据包导出均完成，未触发启发式回退。
- 960 长边连续 8 帧 fast-output 门控通过；当前主线服务 E2E P95 `176.457 ms`，模型 P95 `36.377 ms`。

## 模型选型

| 项目 | Residual Attention 主线 | 上一版 ConvNeXt 对照 |
|---|---:|---:|
| 锁定代理测试集 Dice | 0.917681 | 0.898711 |
| 锁定代理测试集 IoU | 0.848335 | 0.816431 |
| 三种子 Dice | 0.914894 +/- 0.004139 | 单基线运行 |
| 空 mask / 过分割率 | 0 / 0 | 0 / 0 |
| 4K tiled 模型 P95 | 724.432 ms | 800.159 ms |
| 4K 全证据 E2E P95 | 5776.683 ms | 5775.993 ms |
| 连续 960x720 fast-output 模型 P95 | 36.377 ms | 59.531 ms |
| 连续 960x720 fast-output E2E P95 | 176.457 ms | 182.601 ms |

Residual Attention 在锁定代理测试集、三种子稳定性、4K 模型延迟和连续 fast-output 延迟上均通过晋级门控。4K 全证据输出仍约需 5.78 秒，平台继续将该路径用于离线关键帧证据生成；播放同步采用独立 `live_fast` 输出协议。

## 运行配置

- `runtime.required_model_ids`、`runtime.tasks.segmentation.model_id` 和唯一严格运行模型均指向 Residual Attention checkpoint。
- `clinical_claim_allowed=false`、`target_domain=false` 和医生复核边界保持有效。
- 严格生产配置显式设置 `allow_heuristic_keyframe_fallback=false`；模型不可用时分析任务进入结构化失败状态。
- 4K 输入采用 `512` tile、`64` overlap、批量 `4`；实时输入采用前端长边 `960`、JPEG quality `0.85`、CUDA AMP、关闭 TTA、串行逐帧处理。
- 医生人工标注页 `/annotations` 已接入版本审计、身份记录、提交/复核和训练准入；可信 `accepted` / `modified` 标注可通过 `tools/build_keyframe_training_manifest_from_manual_annotations.py` 回灌，工程身份或未复核标注继续隔离。

## 晋级后验证

| 证据 | 结果 | SHA256 |
|---|---|---|
| 严格运行预检 `runtime_preflight.json` | 通过 | `2f6169b395719ac2f174d1d75c5425d39891d148a62bdf268e2722b12aa8b04b` |
| 晋级后 4K 完整平台流 | 通过 | `b51dc0d7df0d668bc6da2fe8eebf1d1a88fb10775a0a7780285ae0c4a2efe46b` |
| 连续真实代理视频帧 fast-output | 通过 | `6aa6c72e8c2898c8978e70c5a945d41d466d7a486afe57a95d9f9d614f10005b` |
| 候选 4K 技术门控 | 通过 | `0a4ea2acf9036de44fe5561c0feb5c31a36f131be7eb6f435f227eb16cff0ac3` |
| 晋级后模型 checkpoint manifest | 通过，无无效 promotion 证据 | `c4e413ca2084f28c0396a8ca747dd30d1b0f70f6d09b5a1b42407393fa140f8a` |

## 证据边界

精度指标来自公开、代理和伪标注的非目标域数据；连续帧来自 D046/OFDVDNET 公开离体荧光代理视频。当前结果证明模型选择、软件执行、输出完整性和医生复核回灌链路可运行，不构成真实术中 ICG 颌骨骨髓炎临床性能证据。所有候选区域继续要求医生复核。
