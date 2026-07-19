# 参赛方案内部验证记录

日期：2026-07-11

## 环境

- Conda 环境：`osteo-vision`
- Python：3.11.15
- `check_env.py`：0 failures，0 warnings

## 代码质量与测试

| 验证项 | 命令范围 | 结果 |
|---|---|---|
| Pytest | `python -m pytest tests/unit tests/smoke backend/tests/unit backend/tests/contract -q` | 304 项通过 |
| 前端测试 | `npm test -- --run` | 58 项通过，1 项跳过 |
| TypeScript/构建 | `npm run typecheck`、`npm run build` | 通过；保留单包体积提示 |
| Ruff | `python -m ruff check backend src tests scripts tools` | 通过 |
| Mypy | 数据注册、训练准入、复核回灌、关键帧训练及相关核心源文件 | 通过 |
| Black | 本轮修改的 Python 文件 | 通过 |
| Diff | `git diff --check` | 通过 |
| Readiness | `python tools/check_project_readiness.py` | 核心文件、CSV、数据目录和平台工作区检查通过 |

Python 测试保留三项依赖警告：Starlette TestClient/httpx 兼容性提示、两个 `torch.jit.interface` 弃用提示。它们未影响本轮测试结果。

## 动态量化

- 解码 MP4/JPEG 帧或 ROI 生成 `p95_intensity`、`background_intensity`、来源与单位域。
- 分割概率保持独立字段。
- 合成 MP4 端到端测试生成背景扣除、归一化曲线、达峰时间、上升斜率、AUC 和质量字段。
- OFDVDnet 公开真实视频四关键帧运行成功，曲线 `available=true`、`quality_status=limited`；动态范围不足时正确输出零斜率/AUC 和质量警告。
- 报告：`research/reports/modeling/public_video_dynamic_quantification_20260711_zh.md`。

## 模型运行策略

- 双通道模型 `enabled=true`、`runtime_allowed=false`，后端跳过执行并保留传统融合。
- 多 mask checkpoint 可由显式候选调用运行，自动模型选择跳过 `candidate_only` 模型。
- `bone_gate_mask` 固定输出 `review_required` 和 `physician_reviewed=false`。
- 当前多 mask 不具备主线替换资格，配置记录 `mainline_replacement_allowed=false`。

## 公开真实视频与 4K

- OFDVDnet：离体荧光代理，170.53 秒、15 FPS。
- PMC 胫骨骨髓炎：真实临床手术视频、无荧光，113.98 秒、29.97 FPS。
- 覆盖长 MP4、多帧率、不可读 H.264、公开源派生 4K JPEG、45-tile 推理、缺 checkpoint 回退和八次内存观察。
- 4K 单关键帧端到端 3.94-4.28 秒，模型概率推理 1.52-1.56 秒。
- 当前验证范围未包含企业 3840×2160 MP4。
- 报告：`research/reports/modeling/public_video_4k_validation_20260711_zh.md`。

## 数据注册与训练准入

- 分层注册表共 504 条记录，质量门通过，错误 0，训练准入候选 393 条，目标域记录仍为 0。
- D047 新增 10 张颌骨荧光论文图，其中 8 张 CC BY 图进入静态人工复核队列，2 张按许可或用途保持仅参考。
- D048 新增 18 张 CC BY 开放论文图，其中 15 张进入弱标签复核队列。
- D047/D048 静态复核队列已扩展为 61 条可操作记录。9 条已有原子面板裁剪，14 张多面板原图已形成 52 条可追溯裁剪建议；全部建议保持待复核和训练禁入。
- 9 条已裁剪记录已生成自动候选 mask，全部保持 `review_required`、`training_eligible=false`，人工 reviewed manifest 仍为空。
- Registry hotspot 代理改为 192 条、48 个来源视频组的 grouped manifest；边界风险、不确定性和 exposed-bone 代理继续分层保留，group split 泄漏为 0。
- 训练准入新增 `proxy_pretrain`、`reviewed_finetune` 和 `independent_evaluation` 三档；代理或待复核标签无法进入后两档。
- 全部注册图像和训练标签 SHA256 通过质量门；23 个许可警告均来自未进入训练的公开源记录。
- 一批次 domain-aware 训练 smoke 成功；checkpoint sidecar 已记录 registry 和 quality report SHA256、准入统计及数据边界。单批次 Dice 仅用于运行验证。
- 报告：`research/reports/modeling/d047_pmc_jaw_fluorescence_dataset_20260711_zh.md`。

## 实时视频软件链路

- 新增 OpenCV 通用实时输入，支持 `camera://opencv/<index>`、RTSP、HTTP、HTTPS 和本地视频源；浏览器摄像头保持预览模式并明确记录后端帧传输未连接。
- 实时输入采用后台读取线程、有界队列、开流/读帧/总时长超时和丢帧统计，所有退出路径释放 `VideoCapture`。
- 有限关键帧进入现有分割、风险、不确定性、动态量化和证据 manifest 链路。
- 输出记录采集时间、推理完成帧龄和 `display_allowed`；超过 `live_max_frame_age_ms` 的结果不进入候选区域显示。
- 无法匹配采集帧、帧身份冲突和缺少显式显示许可的结果均失败闭合；全部结果过期时 run 标记为 `failed`，病例不晋级，旧帧 AI artifact 不注册。
- 合成本地 MP4 的真实 capture-to-analysis smoke 已通过，输出模式为 `realtime_stream_keyframes`。

## 静态数据复核工作台

- `/dataset-review` 当前加载 61 条可操作记录，其中 52 条为原子面板裁剪建议，9 条为已有自动 seed；原始父图在建议子记录生成后退出可操作列表。
- 原图裁剪支持建议 bbox、橙色建议框、绿色编辑框、精确坐标、面板类型、白光/荧光 `pair_id`、配对可信度、备注和原图 SHA256，并在 crop 变化后撤销旧自动 seed。
- 52 条建议中 40 条质量门通过、12 条保留警告，覆盖 19 条荧光信号、13 条配对白光、13 条配对荧光和 7 条病理面板，形成 14 个配对 ID。
- 支持原始像素比例的添加、擦除、画刷、撤销、重做、清空、接受、修改、拒绝和备注。
- Mask 保存前检查 PNG、尺寸、二值、非空和面积范围，写入统一 reviewed manifest，并保留许可、来源组、双 checksum 和训练准入字段。
- 复核身份默认 `project_reviewer`；只有显式选择 `physician` 才写入 `physician_reviewed=true`。
- seed 与 reviewed manifest 已接入分层注册表默认构建路径。当前尚未生成真实人工 mask，目标域与医生金标准数量仍为 0。

## 医生复核回灌

- Active review training patch 逐样本保留许可、用途策略、来源 URL、来源记录、来源组和采样权重。
- `accepted`/`modified` 强制检查图像与 mask 存在、可读取、尺寸一致、非空及 checksum；`modified` 优先使用修订 mask。
- 训练许可采用 fail-closed 规则，来源未明确允许训练的记录保持 `training_eligible=false`。
- Review manifest training builder 同样继承逐样本来源字段，检查二值性与合理面积，并按来源组切分。

## 文档交付

- Markdown：`research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.md`
- Word：`research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.docx`
- PDF：`research/reports/submission/osteo_vision_final_technical_solution_20260711_zh.pdf`
- 证据索引：`research/reports/submission/competition_evidence_index_20260711.json`
- Word/PDF 在当前验证状态下重新构建，并完成逐页渲染检查。

## 基线缺口与外部依赖

Readiness 工具仍提示 EGNet/FRS Loss 外部代码快照不完整，以及 nnU-Net、真实 MedSAM2、BiomedCLIP 候选缺少 checkpoint 或依赖。上述候选未参与本轮赛题主线闭环。

造影剂实物、真实目标域病例、医生金标准、企业原始双通道、滤光片曲线和目标硬件实机证据仍需外部团队提供。
