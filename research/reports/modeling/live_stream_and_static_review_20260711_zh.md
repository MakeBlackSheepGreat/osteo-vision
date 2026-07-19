# 实时视频分析与静态数据复核闭环报告

日期：2026-07-11

## 实时视频软件链路

平台新增有界 OpenCV 实时输入，支持 `camera://opencv/<index>`、RTSP、HTTP、HTTPS 和本地视频源。浏览器摄像头继续承担本地预览；后端明确记录其帧传输尚未连接。

采集层使用后台读取线程和有界队列，记录开流超时、读帧超时、总采集时长、读取帧数、丢弃帧数、采集后端、分辨率、帧率和断流警告。有限关键帧保存为 JPEG，进入既有荧光候选分割、风险、不确定性、动态量化和证据 manifest 链路。

每个输出记录采集时间、采集阶段帧龄、推理完成帧龄、允许显示上限和 `display_allowed`。无法匹配采集帧、帧身份冲突、缺少显式显示许可或超过 `live_max_frame_age_ms` 的输出均采用失败闭合策略。全部结果过期时，run 标记为 `failed`，病例状态不晋级，候选区、决策摘要和 AI artifact 不发布。

实际合成本地 MP4 已完成 capture-to-analysis smoke：3 个关键帧经真实 `VideoCapture`、分割和 manifest 输出，模式记录为 `realtime_stream_keyframes`。该测试证明软件链路可运行，未覆盖企业显微镜接口、原始双通道、4K 连续采集或手术室延迟。

## D047/D048 静态复核工作台

平台 `/dataset-review` 当前加载 D047 8 条、D048 15 条，共 23 条近域论文记录。9 条已有原子面板裁剪，14 条原图进入新增裁剪工作台。工作台支持框选 bbox、精确坐标、面板类型、`pair_id`、裁剪备注和原图 SHA256，裁剪后进入自动 seed 与像素级 mask 复核。

9 条已裁剪记录均生成自动候选 mask。全部记录保持 `review_required`、`training_eligible=false`、`reviewer_role=automated_seed`；自动 seed 未写入人工 reviewed manifest。像素编辑器继续支持添加、擦除、画刷、撤销、重做、清空、接受、修改、拒绝和备注。

保存前质量门覆盖：

- PNG 与 base64 可读性。
- Mask 和裁剪图尺寸一致。
- 二值范围、非空区域和 0.0001-0.95 面积比例。
- D047/D048 根目录路径约束。
- 来源、许可、来源组、采样权重和图像/标签 SHA256。

复核身份默认 `project_reviewer`。只有明确选择 `physician` 时才记录 `physician_reviewed=true`。项目复核 mask 可作为近域工程训练种子，仍不等同于医生金标准或目标域标注。

统一 seed/reviewed manifest 已接入 `tools/build_layered_dataset_registry.py`。注册表改用 192 条、48 个来源视频组的 grouped hotspot manifest，并保留 boundary-risk、uncertain 与 exposed-bone 代理记录。当前注册表为 504 条、质量错误 0、训练准入候选 393 条、目标域 0 条。训练准入新增 `proxy_pretrain`、`reviewed_finetune` 与 `independent_evaluation` 三档，代理标签无法进入后两档。

## 验证

- Python：301 项测试通过。
- 前端：56 项通过，1 项跳过；TypeScript 检查和生产构建通过。
- Ruff、目标 Mypy、`git diff --check` 通过。
- 实际 API：`GET /dataset-review/queue` 返回 23 条，其中 14 条待裁剪、9 条已有自动 seed。
- 桌面截图：`artifacts/platform_smoke/dataset_crop_review_ui_20260711.png`。

## 边界

实时输入仍缺企业 SDK、原始白光/NIR 同步、目标硬件与 4K 长时实测。静态裁剪来自开放论文图，当前没有医生像素标注。所有输出继续用于研发验证、风险提示和复核辅助。
