# V1 可演示平台闭环闭环计划

生成日期：2026-06-15

## 1. 目标

本阶段目标是把项目从资料整理推进到可演示平台闭环：输入白光图和 ICG 荧光图，输出伪彩融合、热图、归一化荧光图、ROI 强度统计和病例报告。

V1 演示流程不依赖 GPU，不依赖真实训练权重，不改变现有模型适配器和任务配置的公共契约。

## 2. 固定能力

- Demo 增加“White-light + ICG fluorescence”双通道入口。
- 参数固定为 alpha、threshold、colormap。
- 输出固定为 overlay、heatmap、normalized fluorescence、JSON report。
- 同步生成 Markdown 报告，便于答辩和人工复核。
- 旧的单文件模型推理入口继续保留，用于分类、分割、检测、量化和多任务 fixture 流程。

## 3. 产物治理

长期归档：

- `research/reports/planning/`：阶段规划与目标说明。
- `research/reports/preprocessing/`：预处理报告。
- `research/reports/modeling/`：模型选型、训练和评估报告。
- 必要的 preview assets：用于报告解释的少量图片。

本地临时产物：

- `.pytest_tmp/`
- `.pytest_cache/`
- `artifacts/reports/`
- `artifacts/visual_evidence/`
- nnU-Net validation `.npz`
- nnU-Net 中间预处理、验证和概率图文件

临时产物可用于本地复查，不作为长期证据进入 Git。

## 4. D024 定位

D024 继续作为 V2 技术基线，用于验证 CBCT 颌骨结构分割、训练、评估和报告闭环。D024 不包含颌骨骨髓炎、坏死骨或术中 ICG 标注，因此不并入 V1 荧光演示主流程。

## 5. 验收

- `python check_env.py` 通过。
- `python -m pytest tests/unit tests/smoke` 通过。
- Demo 可启动并展示双通道荧光融合入口。
- 双通道 handler 可直接返回 Markdown、三张图和 JSON 报告路径。

