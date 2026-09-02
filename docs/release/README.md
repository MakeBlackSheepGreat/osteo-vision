# r28 Windows x64 发行说明

本目录保存 `Osteo Vision Platform r28` 的使用说明和可复核验证摘要。GitHub 发行版使用 `v0.3.0-rc.2-r28` 标签，对应 Windows x64 离线运行包。

## 下载与解压

GitHub 单个附件容量有限，发行包以分卷 7z 文件上传。请下载同一发行版中全部 `Osteo-Vision-Offline-Release-win32-x64-20260831-r28.7z.00*` 文件和 `SHA256SUMS.txt`，并放入同一目录。

1. 使用 7-Zip 在 `.7z.001` 文件上执行“解压到当前目录”。
2. 解压完成后保留生成的 `Osteo-Vision-Offline-Release-win32-x64-20260831-r28` 目录结构。
3. 双击该目录根部的 `Osteo Vision Platform.exe` 启动平台。

`Osteo Vision Platform.exe` 是面向使用者的唯一启动入口。`resources`、`locales` 及其他同级文件夹均为运行时组成部分，复制或刻录时须完整保留。

## 完整性校验

发行页的 `SHA256SUMS.txt` 列出每个分卷的 SHA256。Windows PowerShell 可执行以下命令后与清单比对：

```powershell
Get-FileHash .\Osteo-Vision-Offline-Release-win32-x64-20260831-r28.7z.001 -Algorithm SHA256
```

解压后，运行包根目录的 `verify_release.ps1` 会检查启动文件、示例数据、文件长度和每个受控文件的 SHA256。

## 运行边界

- 支持 Windows 10 或 Windows 11 x64。
- CUDA 条件满足时运行时使用 GPU；GPU、驱动或 CUDA 条件不满足时自动记录 CPU 降级状态。
- 内置 OFDVDnet 公开三视图代理视频、D024 公开下颌参考与 D036 ToothFairy2 MHA 建模示例，仅用于研发验证演示。
- 平台结果服务于医生复核，不提供自动临床诊断结论。

## r28 验证摘要

- 桌面真实工作流：28 / 28 项通过，见 `validation/desktop-real-test-r28.json`。
- 数据准入与病例档案真实工作流：27 / 27 项通过，见 `validation/intake-case-real-test-r28.json`。
- 源码质量门：前端 255 项、三维运行时 21 项、桌面宿主 6 项、后端目标测试 51 项通过。
