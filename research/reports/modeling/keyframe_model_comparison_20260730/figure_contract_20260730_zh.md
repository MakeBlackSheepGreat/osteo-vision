# 关键帧模型对比图图件契约

- 核心结论：Residual Attention U-Net 在同一锁定代理测试协议下取得最高 Dice 与 IoU。
- 可视化：三张测试帧按 Residual Attention 相对其余四个模型的 Dice 优势选取，且来自不同 source group。
- checkpoint：对比使用 2026-07-26 选型批次的 Residual Attention checkpoint；严格运行配置仍绑定 2026-07-15 的同家族已晋级 checkpoint。
- 颜色：绿色为真阳性，红色为假阳性，蓝色为假阴性。
- 数据边界：全部标签来自公开 OFDVDnet 荧光代理视频的强度伪标注，属于非目标域工程验证数据。
- 医学边界：结果只能作为研发验证和医生复核辅助，不能表示真实术中 ICG 颌骨骨髓炎临床分割性能。
