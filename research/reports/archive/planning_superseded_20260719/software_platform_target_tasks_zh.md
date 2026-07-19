# 前后端分离平台目标任务报告

## 背景

本轮实现把项目从 Gradio 临时演示推进到前后端分离的软件平台骨架。平台仍然聚焦赛题后三层：荧光分析、AI 与医生交互判读、结果输出。

## 技术边界

- 前端：TypeScript、Vue 3、Vite、Pinia、Vue Router。
- 后端：Python 3.11、FastAPI、Pydantic。
- 分析核心：继续复用 `src/preprocess/fluorescence.py` 和既有医学影像框架。
- 存储：V1 使用本地 JSON 元数据和本地 artifact 文件夹。
- 输出：JSON、Markdown、CSV 和 evidence bundle manifest。

## 已落地内容

- `frontend/`：Vue 前端工程骨架、病例工作台、复核页、报告预览页、API client、case store。
- `backend/`：FastAPI 应用工厂、病例 API、输入 API、分析 API、复核 API、导出 API。
- `backend/src/domains/cases/`：病例、输入、质量标记、分析运行、ROI、复核事件和证据 artifact 的 Pydantic 模型。
- `backend/src/services/`：输入质量标记、荧光融合分析、ROI 量化、复核状态和证据包导出服务。
- `tests/` 与 `backend/tests/`：平台 workflow smoke、后端 contract/unit 测试和医学安全措辞测试。

## 验证结果

- 平台相关 Python 测试通过。
- 前端 `vitest` 测试通过。
- 前端生产构建通过。

## 当前限制

- V1 使用本地路径输入，尚未实现浏览器 multipart 上传。
- 前端组件目前是可运行骨架，尚未进入细致影像阅片交互和视觉设计阶段。
- ROI 绘制目前是接口和组件占位，后续需要接入 canvas 图形编辑。
- 模型输出仍以荧光融合和启发式候选区域为主，真实病灶模型待数据和标注明确后接入。

## 下一步

1. 将前端病例工作台升级为真实双通道文件上传和预览。
2. 将 ROI 组件从占位升级为 canvas 标注工具。
3. 把导出 evidence bundle 与前端下载/预览连通。
4. 根据真实样本或比赛演示材料调整质量标记阈值和候选区域生成方式。
5. 在 `spec.md` 中逐项处理 `platform_requirements.md` 的需求质量清单。
