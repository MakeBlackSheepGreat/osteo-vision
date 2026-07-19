# 参赛工程证据索引

生成时间：2026-07-19T14:58:00.023206+00:00

## 版本与状态

- Manifest 版本：`0.3.0-rc.2`
- Python / 根 Node / 前端：`0.3.0rc2` / `0.3.0-rc.2` / `0.3.0-rc.2`
- 版本一致：`True`
- 分支：`main`
- 生成基线提交：`d5364101dc701dc3e6e82e4467a5366458efe1a1`
- 最近标签：`v0.3.0-rc.2`
- 工作区条目：`0`

## 官方要求

- 赛题编号：HT-202604
- 核心内容：新型荧光造影剂设计、白光/荧光多模态融合与处理、AI 辅助显微成像判读。
- 设备输入边界：3840x2160、USB3.0、JPEG、MP4。

## 模型清单

| model_id | family | enabled | runtime_allowed | checkpoint | target_domain | 用途边界 |
|---|---|---:|---:|---:|---:|---|
| keyframe_residual_attention_unet_s20260715_20260715 | residual_attention_unet_keyframe_segmenter | True | True | True | False | Strict competition JPEG/MP4 keyframe fluorescence-signal segmentation after model-selection and runtime gates |

## 版本化证据

| 路径 | 存在 | Git | SHA256 |
|---|---:|---:|---|
| `README_CN.md` | True | True | `b723be745d7b40213688ebfcc42aacaf57f44c9905bceaf7479436d96faecb1a` |
| `docs/project_summary.md` | True | True | `cb64740a8c34fcbb5d0b5d39842e720f68dec643eb9033421e46b037dd474ada` |
| `docs/project_structure.md` | True | True | `f590601b8e01ffecbd86b8bdeb8e7aa5b66c8d498c787e891cb50ef5f66f91b3` |
| `research/reports/submission/osteo_vision_technical_solution_20260719_zh.md` | True | True | `88e0423635839c81e99932ce3687abac65ff5ec7e8892d5e66d391171fea423e` |
| `research/reports/submission/osteo_vision_technical_solution_20260719_zh.docx` | True | True | `7d6f151fc3183fea03c942f5bf6caf6ba5d8623e78040e0c1bdbf8d9da37232b` |
| `research/reports/submission/osteo_vision_technical_solution_20260719_zh.pdf` | True | True | `faf896c42698ba5231c1445b42cde680f35a4d310b91ef0409aafcf7755e8ddb` |
| `research/reports/planning/official_competition_problem_alignment_20260704_zh.md` | True | True | `e89de0d969e55de2bfc689cd94db0de978606bbf68e9b5c7f40eacfd3406b12c` |
| `research/reports/planning/official_technical_document_alignment_zh.md` | True | True | `db76f8c33fda98a4eae101daada736b23a5fea742ec6fcab7788c317b4287c8e` |
| `research/reports/planning/competition_advisor_suggestions_feasibility_20260717_zh.md` | True | True | `54000be1c08d907fca517667f71422c6c1d015ef5cef25cdc0907cd34d4c13e9` |
| `research/reports/planning/three_priority_capabilities_target_20260717_zh.md` | True | True | `a83a2913faf538846886a2789cd7837f01c5c577376e5e9499e682b475cafdac` |
| `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md` | True | True | `7619530b3af2f99a4702216af4651c46c8e63ec76b090951967317f67c07d358` |
| `research/reports/modeling/keyframe_model_selection_summary_20260715_zh.md` | True | True | `06d6481b6b1cd09b5c8df944f2c457d6b5ea3e54a5ff057b6bfd5a86ea0fcb97` |
| `research/reports/modeling/keyframe_residual_attention_4k_runtime_gate_20260715_zh.md` | True | True | `863868bea8115251d41221a98764bbc7c26aad49e2f0c85f69493321b93de99f` |
| `research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md` | True | True | `a1d07cac424ead3ebaf8b70bf8ae37bcbc89c72ad1383d8562990531646daef7` |
| `research/reports/modeling/patient_conditioning_4k_registered_runtime_20260719_zh.md` | True | True | `ae64bf638a4bd6f6cadee1e8c98b46e0994b27fcb9309a21b982cc14fc4b5563` |
| `research/reports/modeling/bone_activity_multitask_d074_proxy_20260719.json` | True | True | `50816b29384766fdc6b7dc23d7a04d523958343351b89ff6a1d2e7dc4f5d7a8f` |
| `research/datasets/public-candidates/three_priority_manifest_verification_20260719_d095.json` | True | True | `f1aaa8ec268ca994d65175ab318804fcb7ce973938fe8c93471f73a3eef60078` |
| `research/reports/release/v0.3.0-rc.2_20260719_zh.md` | True | True | `c3f71864c4db39a0713adf67f235a5d2c868c20662d56b68136b2b075c018641` |
| `backend/src/services/live_frame_service.py` | True | True | `8eb8d8916889246194e12b4270cc0da2ff62ff05057232795fe0a6cb5f2f9f6a` |
| `backend/src/services/manual_annotation_service.py` | True | True | `4ad910e712fa3e84aec67279ae6b30eca252bf81ba6829dd06e97fe308a72fc2` |
| `backend/src/services/static_registration_service.py` | True | True | `4f7db23c2d7c8b637cf4f36fef99e75940a61b539107ad9199a07be2931ec716` |
| `backend/src/services/offline_pose_replay_service.py` | True | True | `51d3461fd827c63bb7cb7353d16edce83304f15d0a4164a5a77b4e46855f8a09` |
| `src/models/keyframe_segmenter.py` | True | True | `48301c415b2c642954a5a481fe0811c2093e834fb43e5fe211bc08895b121902` |
| `src/models/patient_conditioned_runtime.py` | True | True | `40bf7ee756716d3d3a180239732ca1c6adb2cdb602e444233ac3cb9a390f7ea1` |
| `src/models/bone_activity_runtime.py` | True | True | `c4fcbe9819d141f71c6641de4736f9b797ccf896a99811401096474a0d76f433` |
| `tools/run_competition_flow_demo_check.py` | True | True | `444e98f1e005be58bb2814968a63c9a0079ee0e51bf8c86747b5aca9528ed265` |
| `tools/verify_three_priority_dataset_manifests.py` | True | True | `db6fa77c44ce857106edcf85a71a27c409df30c6fd184f2a7f759fcd5ee5686a` |

## 本地运行证据

| 路径 | 存在 | SHA256 |
|---|---:|---|
| `artifacts/performance/core_hotpaths_current.json` | True | `6ad4b033e8d38ee6f7284b8868ccb6b4253c3448c426173ccf75e7c8ff2def01` |
| `artifacts/release/v0.3.0-rc.2/dataset_manifest_verification.json` | True | `f1aaa8ec268ca994d65175ab318804fcb7ce973938fe8c93471f73a3eef60078` |

## 证据边界

- `literature`：文献、公开数据库和官方资料支撑机理与验证设计，不代表本项目原创实验结果。
- `proxy_engineering`：公开异域视频、伪标注、公开 CBCT 和代理临床表用于软件链路、训练复现和相对比较。
- `target_domain`：真实颌骨骨髓炎白光/ICG 联合病例与医生像素级金标准当前为零。
- `navigation`：L1 静态仿体和 L2 离线回放属于工程验证，真实术中导航未就绪。

## 完整性

- 必需证据：27，缺失：0
- 本地运行证据：2，缺失：0
- 可冻结提交：`True`

## 外部验证需求

- 候选造影剂实物合成、光谱、选择性、安全性和组织验证
- 真实目标域白光/ICG JPEG 或 MP4 与医生像素级金标准
- 真实设备全倍率/全工作距离标定、下颌仿体与术中导航验证

## 医学边界

平台输出用于荧光/灌注信号候选、骨面复核、边界风险、不确定性、离线三维参考和医生复核辅助；不提供自动确诊、切除成功率或真实术中导航结论。
