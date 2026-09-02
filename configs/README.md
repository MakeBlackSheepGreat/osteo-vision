# 配置目录

配置按运行目的分层，当前平台入口以严格配置和研发配置为准。

| 路径 | 用途 | 状态 |
|---|---|---|
| `inference/osteo_vision_strict.yml` | 平台版严格运行、模型和安全门 | 当前主线 |
| `inference/osteo_vision.yml` | 研发验证、代理能力和模型清单 | 当前研发 |
| `training/` | 数据准备、训练、阈值和晋级配置 | 当前研发 |
| `data/` | 公开 CBCT 等预处理配置 | 当前研发 |
| `tasks/osteo_vision.yml` | 平台任务契约 | 当前主线 |
| `tasks/*.example.yml` | 通用任务参考模板 | 示例 |
| `inference/demo.yml`、`tasks/medical_demo.yml` | 早期通用 fixture 测试链 | 兼容测试 |

运行前使用 `tools/check_runtime_readiness.py` 校验配置、模型清单、checkpoint、sidecar 和安全边界。配置中记录的本地权重、病例和原始数据保持 Git 忽略状态。
