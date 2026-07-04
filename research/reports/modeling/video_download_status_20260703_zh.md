# 骨髓炎与荧光代理视频下载整理状态

日期：2026-07-03

本报告只整理当前本地文件状态，不继续触发外部下载。

## 1. 本轮清理动作

- 删除了 2 个由 NCBI/Google reCAPTCHA 返回、但被保存成 `.mp4` 的 HTML 占位文件。
- 删除了 6 个 0 字节的 PMC OA package `.part` 占位文件。
- 刷新 `research/literature/inventory/video_download_manifest_20260703.csv`，将浏览器后续下载成功的文件大小和 SHA256 写回清单。

## 2. 当前下载结果

| 类别 | 本地可用文件 | 本地体量 | 荧光属性 | 说明 |
|---|---:|---:|---|---|
| 骨髓炎相关 PMC 视频 | 23 个 | 约 452.82 MB | 非荧光 | 可用于 MP4 输入、关键帧、手术场景演示、自监督或后续医生标注；不能直接当作 ICG 颌骨骨髓炎训练集。 |
| OFDVDnet Dryad | `data.zip` + README | 约 2.93 GB | ICG 模拟荧光代理 | 可用于荧光视频去噪、伪彩、白光/荧光/overlay 三视图管线；不是口腔/骨髓炎。 |
| FGS video denoising Dryad | README | 约 4.8 KB | 荧光代理说明 | 34 GB 主数据包未下载，直接下载返回验证页面，暂不快速重试。 |

原始数据目录：

`research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/raw/`

下载清单：

`research/literature/inventory/video_download_manifest_20260703.csv`

## 3. 未完成项

| 记录 | 状态 | 原因 |
|---|---|---|
| `PMC12078111_S001` | 未下载 | NCBI/Google reCAPTCHA 页面被返回，已删除 HTML 占位文件。 |
| `PMC12914110_MMC2` | 未下载 | NCBI/Google reCAPTCHA 页面被返回，已删除 HTML 占位文件。 |
| `DRYAD_FGS_DATA_MODELS` | 未下载 | 数据包约 34 GB，直接下载返回 Dryad 验证 HTML，且不适合连续重试。 |

## 4. 使用边界

- 目前没有发现可直接用于训练的“颌骨骨髓炎 + ICG/荧光 + MP4 + 像素级标注”公开数据集。
- 已下载的骨髓炎视频均为非荧光视频，主要价值是系统输入和手术场景演示。
- OFDVDnet 是荧光代理数据，主要价值是赛点一的视频增强和伪彩稳定，不可包装成真实目标域数据。
- 后续若继续补下载，必须单文件、低频率、人工确认后再运行，避免继续触发验证码。
