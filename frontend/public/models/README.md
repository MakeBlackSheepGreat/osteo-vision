# 本地三维模型临时资产

此目录可放置本地主前端的开发验证资产。独立三维渲染运行时不会从 `frontend/public/models/` 读取模型，也不会把该目录的文件视为可渲染病例证据。

独立运行时只接受后端场景快照中的受控模型资产：

1. 后端从 `$OSTEO_ARTIFACT_ROOT` 或项目 `artifacts/` 下的允许目录解析 STL、GLB 或 GLTF。
2. 场景快照提供版本、格式、文件名、字节数、SHA256 和受控下载地址。
3. 独立运行时下载后复核字节数与 SHA256，再加载 STL 或 GLB；GLTF 保留为可追溯的安全降级资产。

病例或公开参考模型应同时保留可核验 manifest，至少记录来源、许可、脱敏状态、文件大小、SHA256、模型坐标系、变换链、配准误差、医生复核状态和用途边界。空间候选 marker 还需绑定 `model_coordinate_space`、`transform_sha256` 与候选区的 `coordinate_space`、`coordinate_transform_sha256`。

公开 D024 参考资产由后端运行时数据目录管理：`$OSTEO_ARTIFACT_ROOT/three_d_runtime/references/d024/`。该参考保持 L0 未配准工程展示边界，不能用于临床导航或自动诊断表述。

禁止将原始 DICOM、NIfTI、可识别患者数据或许可状态不明的模型放入前端静态目录。
