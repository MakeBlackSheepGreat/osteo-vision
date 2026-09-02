# Osteo Vision 离线发行包

本目录提供离线发行包随附的校验脚本和说明文件。`Osteo Vision Platform.exe` 是唯一启动入口，
`resources`、`locales` 等相邻目录属于应用运行时组成部分，复制或刻录时必须与可执行文件保持同级。
这些目录包含受控 API、界面资源、模型 checkpoint、FFmpeg、运行配置、CUDA 运行时和最小公开演示数据。

## 运行

1. 将整个发行目录复制到本机可写目录。
2. 双击根目录的 `Osteo Vision Platform.exe`。
3. 等待运行时预热完成，从病例工作台导入 JPEG 或 MP4 示例。

平台默认使用 `configs/inference/osteo_vision_strict.yml`，支持 3840x2160 JPEG、MP4 以及受控转码后的 AVI。
GPU 条件满足时优先使用 CUDA；检测不到兼容 GPU、驱动或 CUDA 运行时异常时自动降级到 CPU，并在日志和界面状态中记录原因。

## 内置演示

发行包内置 OFDVDnet 公开三视图荧光代理 MP4、通道预览图、D024 公开下颌表面参考和 D036 ToothFairy2 MHA 示例。
这些数据用于验证文件导入、双通道会话、关键帧复核和三维参考流程，不能作为临床诊断依据。

## 完整性校验

在 PowerShell 中从发行目录运行：

```powershell
.\verify_release.ps1
```

脚本检查启动文件、受控运行时、模型、示例数据、使用指南和 `release-manifest.json` 的 SHA256。
校验失败时请保留终端输出，以便定位缺失或损坏文件。

## 目录约定

```text
Osteo Vision Platform.exe
resources/
  backend/                 受控 FastAPI 运行时
  runtime_assets/          配置、模型、示例数据和平台服务资源
  three_d_runtime/         独立三维渲染运行时
locales/                   Electron 本地化资源
verify_release.ps1         完整性校验脚本
release-manifest.json      文件清单与 SHA256
Osteo_Vision_r28_使用说明.docx
Osteo_Vision_r28_使用说明.pdf
```

请保持目录结构完整。应用关闭时会清理受控后端进程，并保留退出日志。

## 医学边界

平台输出用于研发验证和医生复核，不提供自动临床诊断，也不替代医生判断。
