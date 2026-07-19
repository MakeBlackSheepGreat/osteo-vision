# 公开真实视频与官方 4K 输入验证报告

日期：2026-07-11

## 验证目标

本轮依据赛题原文和赛题方设备技术文档，验证平台对官方输入边界的工程适配能力。设备文档明确规定 4K 摄录分辨率为 `3840x2160`，图片格式为 JPEG，视频格式为 MP4。本轮覆盖公开真实视频抽帧复核、长 MP4、不同帧率、不可读 MP4、公开来源帧派生 4K JPEG、强制 tiling、模型失败回退和短时持续内存观察。

平台表述固定为 `keyframe-based playback analysis`。本报告不提供 4K 全帧 30 FPS AI 性能声明。

## 数据与目视复核

| 记录 | 公开来源 | 医学场景 | 荧光属性 | 参数 | 目视复核 |
|---|---|---|---|---|---|
| `OFDVDNET_023` | [Dryad OFDVDnet](https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w) | 离体鸡腿荧光引导手术代理 | 有荧光 | 2048x1536，15 FPS，170.53 秒，H.264 | 可见术野、参考图、荧光图和叠加图；属于离体非目标域数据 |
| `PMC12350196_MMC1` | [PMC12350196](https://pmc.ncbi.nlm.nih.gov/articles/PMC12350196/) | 胫骨骨髓炎内镜髓内清创 | 无荧光 | 1280x720，29.97 FPS，113.98 秒，H.264 | 可见内镜清创、硬化骨切除及教学帧；属于非颌骨、非荧光异域数据 |

验证脚本对每个来源均匀抽取 9 帧生成 contact sheet。目视检查排除了将标题页、讲解页或离体材料误写成真实颌骨术中 ICG 病例的风险。完整来源路径、页面链接、下载链接、文件大小和 SHA256 进入本地验证 summary 与派生资产 manifest。

## 覆盖结果

- 长 MP4：两个公开来源均超过 60 秒，完整视频进入关键帧质量筛选流程。
- 不同帧率：原始 15 FPS 与 29.97 FPS 均可读取；另从 OFDVDnet 公开源派生 6 FPS、29.97 FPS MP4V 变体，派生关系与 SHA256 已记录。
- 异常编码：`OFDVDNET_004` 文件存在且大小为 88,276,992 字节，OpenCV 无法打开，原 manifest 同样记录 `Could not open video`。平台验证保留失败证据并选择另一条可追溯可读源继续分析。
- 4K JPEG：从 OFDVDnet 荧光象限关键帧派生 `3840x2160` JPEG，用于官方分辨率输入与强制 tiling 验证。派生图继续继承离体非目标域边界。
- 强制 tiling：3 次 4K 推理均进入 `tiled` 模式，每次 45 个 tile，输出 mask、概率图、伪彩、叠加图和不确定性结果。
- 回退：构造缺失 checkpoint 的主模型 warmup 失败，传统 `fluorescence_hotspot_2d_segmenter` 成功输出候选区 mask。
- 持续内存：1024x768 公开荧光代理关键帧连续运行 8 次，RSS 从 1284.492 MB 到 1284.582 MB，增长 0.090 MB；该结果属于短时稳定性观察。

## 性能结果

测试环境：`osteo-vision` Conda 环境，NVIDIA GeForce RTX 5060 Laptop GPU。数值来自本地一次验证运行。

| 阶段 | 样本数 | P50 ms | P95 ms | 最小 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|
| 公开视频关键帧解码/筛选 | 6 | 1104.421 | 1770.028 | 438.814 | 1770.028 |
| RGB 加载预处理 | 11 | 13.108 | 49.401 | 4.352 | 53.576 |
| 模型概率推理 | 8 | 287.117 | 1557.461 | 140.784 | 1558.022 |
| 后处理估算 | 8 | 272.998 | 2600.093 | 203.073 | 2674.173 |
| Adapter 端到端 | 8 | 575.405 | 4195.170 | 349.735 | 4284.168 |

4K 强制 tiling 的单帧端到端耗时为 3.94-4.28 秒，模型概率推理为 1.52-1.56 秒。该性能支持异步关键帧分析路线，也说明当前结果无法支撑 4K 全帧实时 AI 声明。原始 1024x768 荧光象限关键帧在首轮 warmup 后，端到端约 0.35-0.38 秒。

模型概率推理耗时由 adapter 内部计时产生。RGB 加载采用隔离测量。后处理数值使用 `adapter 端到端 - 模型概率推理 - 隔离 RGB 加载` 的非负余量估算，包含输出图生成、候选区计算、序列化以及重复加载差异，后续可通过核心流水线分段埋点提高精度。

## 证据与复现

- 验证脚本：`tools/run_public_video_4k_validation.py`
- 单元测试：`tests/unit/test_public_video_4k_validation.py`
- 本地 summary：`artifacts/platform_smoke/public_video_4k_20260711/public_video_4k_validation_summary.json`
- 本地派生 manifest：`artifacts/platform_smoke/public_video_4k_20260711/public_video_derived_assets_manifest.json`
- 本地目视 contact sheet：`artifacts/platform_smoke/public_video_4k_20260711/visual_review/`

复现命令：

```powershell
conda run -n osteo-vision python tools/run_public_video_4k_validation.py --output-dir artifacts/platform_smoke/public_video_4k_20260711 --keyframes 3 --native-runs 5 --tiled-runs 3 --memory-iterations 8
```

## 证据边界

OFDVDnet 只提供离体荧光视频处理与时序工程证据。PMC 视频只提供骨髓炎相关真实手术场景和 MP4 工程证据。当前仍缺企业显微镜原始双通道 4K 样片、真实术中 ICG 颌骨骨髓炎病例、医生关键帧/ROI 金标准和目标硬件长时压力数据。所有模型输出均定位为荧光或灌注信号候选区、风险提示、不确定性和医生复核辅助。
