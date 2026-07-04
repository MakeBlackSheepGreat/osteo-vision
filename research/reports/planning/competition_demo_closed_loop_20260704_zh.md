# 比赛演示闭环说明

## 结论

当前比赛版主线应优先保持“可运行、可复现、可交付”的演示闭环，而不是在本轮继续切换模型架构。2026-07-04 的 4K 代理演示自查已经跑通：系统可完成官方技术文档边界内的 JPEG/MP4 输入、白光/ICG 融合、MP4 关键帧分析、AI 候选区、医生复核、结构化导出和 evidence bundle。

本闭环只用于科研、比赛和受控演示，不是赛题方验收。当前没有真实术中 ICG 颌骨骨髓炎 MP4/JPEG 和医生 ROI 标注，自查输入为合成代理数据，不代表目标域临床性能。

## 官方输入边界

依据赛题官方技术文档和项目对齐记录，系统优先支持：

- 4K 超高清影像：`3840x2160`。
- 图片格式：JPEG。
- 视频格式：MP4。
- 存储/导入边界：USB3.0 导出文件或上传文件。

因此本轮演示自查脚本默认生成 4K JPEG 白光图、4K JPEG ICG 图和 4K MP4 代理视频，并通过后端真实 FastAPI 路由完成上传、分析、复核和导出。

完整赛题原文另有更高优先级要求：参赛方案必须回答“新型荧光造影剂设计、多模态医学图像融合与处理、AI 辅助显微成像判读”三项内容。下面的软件闭环只覆盖第二、三项的工程原型，并不能替代第一项造影剂设计方案。

## 四条比赛演示路径

### 1. 4K JPEG 白光 + ICG JPEG 双通道融合

流程：

1. 创建病例。
2. 上传白光 JPEG 和 ICG JPEG。
3. 将两个输入绑定到同一病例。
4. 执行伪彩增强、背景扣除、轻量配准、融合、热图和 ROI mask 生成。
5. 输出 overlay、heatmap、normalized fluorescence、colorbar、roi mask 和量化摘要。

对应答题要求：多模态医学图像融合与处理。

### 2. 4K MP4 上传、关键帧抽取、可训练分割和伪彩叠加

流程：

1. 上传 MP4 文件。
2. 后端对视频进行元数据识别和关键帧抽取。
3. 优先使用 `convnext2d_keyframe_proxy_segmenter` 对关键帧做 PyTorch 分割推理，输出 `png_binary_mask`、probability、伪彩和 overlay；模型不可用时回退 `fluorescence_hotspot_2d_segmenter`。
4. 对超过阈值的 4K keyframe 可走可配置 patch/tiling 推理，避免默认整帧一次性推理带来的显存/内存风险。
5. 输出 keyframe、timeline manifest、frame detail manifest、video segmentation manifest、overlay/mask review MP4 和候选区域。

对应答题要求：显微镜输出 MP4/JPEG 进入软件后的 AI 辅助候选区域提示。

### 3. 医生复核候选区/ROI 状态

流程：

1. 读取分析 run 中的候选区域。
2. 将首个候选区更新为 `accepted`。
3. 从候选区创建 ROI。
4. 写入 review event。
5. 导出报告时保留 review summary、review events 和 ROI 状态。

对应答题要求：AI 结果以叠加提示、风险标注或决策辅助形式呈现，并进入医生复核工作流。

### 4. 导出 JSON、CSV、Markdown、DICOM Secondary Capture 和 ZIP 证据包

流程：

1. 调用病例导出接口。
2. 生成结构化 JSON 报告。
3. 生成 Markdown 报告。
4. 生成量化 CSV。
5. 生成 DICOM Secondary Capture。
6. 生成 bundle manifest 和 evidence bundle ZIP。

对应价值：作为软件平台的结构化证据包和可追溯输出能力。完整赛题原文未将 DICOM/远程协作列为核心答题要求，本阶段 DICOM 仅为 Secondary Capture，不是 DICOM SR/SEG，也不承载临床诊断声明。

## 主线模型固化

当前主线模型保持如下配置：

| 入口 | 模型/规则 | 状态 | 用途 |
|---|---|---|---|
| `npz_roi` | `convnext3d_d025_proxy_segmenter` | 可用 | D025 CBCT lesion ROI 代理分割，用于工程闭环和方案展示 |
| `2d_image` / MP4 keyframe | `convnext2d_keyframe_proxy_segmenter` | 可用 | 可训练 2D ConvNeXt-style keyframe 代理分割，用于 JPEG/MP4 mask、伪彩和 overlay |
| `2d_image` / MP4 keyframe fallback | `fluorescence_hotspot_2d_segmenter` | 可用 | 2D 荧光热点启发式候选区，用于模型不可用时回退和可解释对照 |
| 兼容入口 | `d025_lesion_smoke_segmenter` | 可用 | 与 D025 代理 checkpoint 兼容的 smoke 入口 |
| 对照模型 | `d025_monai_segresnetds.pt` | 不接主线 | 只作为建模对照证据 |

`SegResNetDS` 暂不接入 `configs/inference/osteo_vision.yml`。对比报告显示，它在当前 D025 64³ 代理缓存上的 Mean Dice 和 Mean IoU 低于 ConvNeXt-style baseline。当前 2D keyframe 模型已接入 MP4 路径，并支持可配置 patch/tiling 推理，但仍是合成/伪标注代理模型；下一阶段应将 nnU-Net v2 或 DynUNet 高分辨率/patch 级训练作为增强路线，而不是阻塞当前演示闭环。

## 赛题对齐演示自查命令

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

可选小尺寸快速检查：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py --width 320 --height 180 --frames 3 --keyframes 2 --fps 3 --output-dir .pytest_tmp\competition_demo_check_smoke
```

默认输出写入：

```text
artifacts/platform_smoke/competition_demo_check_*
```

## 2026-07-04 演示自查结果

本次已执行默认 4K 演示自查：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_demo_check.py
```

历史自查摘要：

- 历史运行目录：`artifacts/platform_smoke/competition_acceptance_20260704T111303Z`
- 病例 ID：`case_c01a9b9dbf`
- JPEG 融合：通过。
- MP4 关键帧分析：通过。
- 医生复核事件：已记录，候选区已转 ROI。
- evidence bundle：已生成。
- 必需格式：`report_json`、`report_md`、`dicom_secondary_capture`、`quantification_csv`、`bundle_manifest`、`evidence_bundle`、`overlay`、`heatmap`、`roi_mask`、`keyframe` 均存在。
- 主线模型：`convnext3d_d025_proxy_segmenter` 和 `convnext2d_keyframe_proxy_segmenter` 均可用；`fluorescence_hotspot_2d_segmenter` 保留为 2D keyframe 回退和可解释对照。
- 2026-07-04 后续小型复核：`tools\run_competition_flow_demo_check.py --width 320 --height 180 --frames 3 --keyframes 2 --fps 3` 通过；`video_segmentation_manifest.json` 显示 `summary.model_id=convnext2d_keyframe_proxy_segmenter`，每帧 `analysis_method=trainable_keyframe_segmenter`，overlay/mask review MP4 均存在。
- 医学边界：已写入科研/竞赛原型免责声明，`clinical_claim_allowed=false`。

## 当前缺口

- 真实术中 ICG 颌骨骨髓炎 MP4/JPEG 仍缺失。
- 医生关键帧、ROI 和病例级标注仍缺失。
- 当前视频链路已接入可训练 2D keyframe 代理分割模型，但训练数据仍为合成/伪标注或非目标域代理数据，不能证明真实目标域诊断性能。
- 当前 DICOM 为 Secondary Capture，尚不是 DICOM SR/SEG；且 DICOM/远程协作是扩展亮点，不是完整赛题原文的核心答题要求。
- 完整赛题原文要求“新型荧光造影剂设计方案”，当前项目尚缺可独立支撑该项的实验或验证数据。
- `nnunet_v2_osteo_baseline` 和 `biomedclip_osteo_screening` 仍缺可运行 checkpoint 或 adapter inference。
- `medsam2_osteo_promptable` 已具备 2D prompt contract fallback，可用 ROI/bbox/point 生成复核 mask；但仍缺真实 MedSAM2 checkpoint，不能写成真实 MedSAM2 推理性能。

## 下一阶段准备

1. 保持当前闭环作为比赛演示主线。
2. 并行准备 nnU-Net v2/DynUNet 高分辨率或 patch 级训练。
3. 继续寻找可追溯的荧光手术视频、骨髓炎/骨坏死视频和论文补充视频，但必须标注非目标域属性。
4. 若医院只能提供 4-5 例 CBCT，则将其用于演示校准、病例叙事和专家反馈，不作为独立高性能训练集。
5. 把 DICOM SR/SEG 映射草案作为扩展项推进，避免挤占造影剂设计、双通道融合和 AI 判读三项核心答题要求。

## 参考文件

- `research/literature/inventory/official/competition_official_technical_document_20260527.pdf`
- 完整赛题原文本地忽略 PDF：`HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf`
- `research/reports/planning/official_technical_document_alignment_zh.md`
- `specs/001-software-platform-target/plan.md`
- `docs/export_schema_v1.md`
- `research/reports/modeling/model_checkpoint_manifest_20260704_zh.md`
- `research/reports/modeling/d025_proxy_model_comparison_20260704_zh.md`
- `tools/run_competition_flow_demo_check.py`
