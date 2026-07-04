# 比赛演示闭环说明

## 结论

当前比赛版主线应优先保持“可运行、可复现、可交付”的完整闭环，而不是在本轮继续切换模型架构。2026-07-04 的 4K 代理验收已经跑通：系统可完成官方边界内的 JPEG/MP4 输入、白光/ICG 融合、MP4 关键帧分析、AI 候选区、医生复核、结构化导出和 evidence bundle。

本闭环只用于科研、比赛和受控演示。当前没有真实术中 ICG 颌骨骨髓炎 MP4/JPEG 和医生 ROI 标注，验收输入为合成代理数据，不代表目标域临床性能。

## 官方输入边界

依据赛题官方技术文档和项目对齐记录，系统优先支持：

- 4K 超高清影像：`3840x2160`。
- 图片格式：JPEG。
- 视频格式：MP4。
- 存储/导入边界：USB3.0 导出文件或上传文件。

因此本轮验收脚本默认生成 4K JPEG 白光图、4K JPEG ICG 图和 4K MP4 代理视频，并通过后端真实 FastAPI 路由完成上传、分析、复核和导出。

## 四条比赛演示路径

### 1. 4K JPEG 白光 + ICG JPEG 双通道融合

流程：

1. 创建病例。
2. 上传白光 JPEG 和 ICG JPEG。
3. 将两个输入绑定到同一病例。
4. 执行伪彩增强、背景扣除、轻量配准、融合、热图和 ROI mask 生成。
5. 输出 overlay、heatmap、normalized fluorescence、colorbar、roi mask 和量化摘要。

对应赛点：荧光图像伪彩色增强和白光/ICG 可视化融合。

### 2. 4K MP4 上传、关键帧抽取、伪彩增强和热点候选区

流程：

1. 上传 MP4 文件。
2. 后端对视频进行元数据识别和关键帧抽取。
3. 使用 `fluorescence_hotspot_2d_segmenter` 对关键帧做热点候选区生成。
4. 输出 keyframe、timeline manifest、frame detail manifest 和候选区域。

对应赛点：官方 MP4 输入进入软件后的 AI 辅助候选区域提示。

### 3. 医生复核候选区/ROI 状态

流程：

1. 读取分析 run 中的候选区域。
2. 将首个候选区更新为 `accepted`。
3. 从候选区创建 ROI。
4. 写入 review event。
5. 导出报告时保留 review summary、review events 和 ROI 状态。

对应赛点：AI 结果不作为自动诊断结论，而是进入医生复核工作流。

### 4. 导出 JSON、CSV、Markdown、DICOM Secondary Capture 和 ZIP 证据包

流程：

1. 调用病例导出接口。
2. 生成结构化 JSON 报告。
3. 生成 Markdown 报告。
4. 生成量化 CSV。
5. 生成 DICOM Secondary Capture。
6. 生成 bundle manifest 和 evidence bundle ZIP。

对应赛点：DICOM 标准输出与远程协作雏形。本阶段 DICOM 仅为 Secondary Capture，不是 DICOM SR/SEG，也不承载临床诊断声明。

## 主线模型固化

当前主线模型保持如下配置：

| 入口 | 模型/规则 | 状态 | 用途 |
|---|---|---|---|
| `npz_roi` | `convnext3d_d025_proxy_segmenter` | 可用 | D025 CBCT lesion ROI 代理分割，用于工程闭环和方案展示 |
| `2d_image` / MP4 keyframe | `fluorescence_hotspot_2d_segmenter` | 可用 | 2D 荧光热点启发式候选区，用于 JPEG/MP4 演示 |
| 兼容入口 | `d025_lesion_smoke_segmenter` | 可用 | 与 D025 代理 checkpoint 兼容的 smoke 入口 |
| 对照模型 | `d025_monai_segresnetds.pt` | 不接主线 | 只作为建模对照证据 |

`SegResNetDS` 暂不接入 `configs/inference/osteo_vision.yml`。对比报告显示，它在当前 D025 64³ 代理缓存上的 Mean Dice 和 Mean IoU 低于 ConvNeXt-style baseline；下一阶段应将 nnU-Net v2 或 DynUNet 高分辨率/patch 级训练作为增强路线，而不是阻塞当前演示闭环。

## 一键验收命令

```powershell
conda run -n osteo-vision python tools\run_competition_flow_acceptance.py
```

可选小尺寸快速检查：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_acceptance.py --width 320 --height 180 --frames 3 --keyframes 2 --fps 3 --output-dir .pytest_tmp\competition_acceptance_smoke
```

默认输出写入：

```text
artifacts/platform_smoke/competition_acceptance_*
```

## 2026-07-04 验收结果

本次已执行默认 4K 验收：

```powershell
conda run -n osteo-vision python tools\run_competition_flow_acceptance.py
```

验收摘要：

- 运行目录：`artifacts/platform_smoke/competition_acceptance_20260704T111303Z`
- 病例 ID：`case_c01a9b9dbf`
- JPEG 融合：通过。
- MP4 关键帧分析：通过。
- 医生复核事件：已记录，候选区已转 ROI。
- evidence bundle：已生成。
- 必需格式：`report_json`、`report_md`、`dicom_secondary_capture`、`quantification_csv`、`bundle_manifest`、`evidence_bundle`、`overlay`、`heatmap`、`roi_mask`、`keyframe` 均存在。
- 主线模型：`convnext3d_d025_proxy_segmenter` 和 `fluorescence_hotspot_2d_segmenter` 均可用。
- 医学边界：已写入科研/竞赛原型免责声明，`clinical_claim_allowed=false`。

## 当前缺口

- 真实术中 ICG 颌骨骨髓炎 MP4/JPEG 仍缺失。
- 医生关键帧、ROI 和病例级标注仍缺失。
- 当前视频链路主要验证工程流程，不能证明真实目标域诊断性能。
- 当前 DICOM 为 Secondary Capture，尚不是 DICOM SR/SEG。
- `nnunet_v2_osteo_baseline`、`medsam2_osteo_promptable`、`biomedclip_osteo_screening` 仍缺可运行 checkpoint 或 adapter inference。

## 下一阶段准备

1. 保持当前闭环作为比赛演示主线。
2. 并行准备 nnU-Net v2/DynUNet 高分辨率或 patch 级训练。
3. 继续寻找可追溯的荧光手术视频、骨髓炎/骨坏死视频和论文补充视频，但必须标注非目标域属性。
4. 若医院只能提供 4-5 例 CBCT，则将其用于演示校准、病例叙事和专家反馈，不作为独立高性能训练集。
5. 增强 DICOM SR/SEG 映射草案和 DICOM 读取回归测试。

## 参考文件

- `research/literature/inventory/official/competition_official_technical_document_20260527.pdf`
- `research/reports/planning/official_technical_document_alignment_zh.md`
- `specs/001-software-platform-target/plan.md`
- `docs/export_schema_v1.md`
- `research/reports/modeling/model_checkpoint_manifest_20260704_zh.md`
- `research/reports/modeling/d025_proxy_model_comparison_20260704_zh.md`
- `tools/run_competition_flow_acceptance.py`
