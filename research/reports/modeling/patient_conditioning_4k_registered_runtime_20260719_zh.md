# 患者条件分割 4K 可配准运行验证

日期：2026-07-19
状态：研发验证通过，目标域晋级关闭

## 1. 验证目的

验证官方输入边界下的 3840×2160 白光/荧光 JPEG 能通过双通道配准安全门，并在开发配置中实际执行患者条件代理 checkpoint，生成影像基础概率、患者条件概率、空间差异图和模型不确定性四类证据。验证同时要求代理模型保持零空间调制、禁止替换主线和医生复核边界。

## 2. 输入与严格比赛流

可配准代理输入位于 `artifacts/platform_competition/competition_flow_three_priority_registered_20260719/input/`：

| 输入 | 尺寸 | 字节数 | SHA256 |
| --- | ---: | ---: | --- |
| `competition_white_4k.jpg` | 3840×2160 | 689,677 | `db40d9ff75b39cbd8084ab5d5378c599bb4d15d49bab991089a7514a93b28d8a` |
| `competition_icg_4k.jpg` | 3840×2160 | 563,413 | `986aaa1b78f4c38104333312cdee22096684913612fcd036c89207dd6e7a76d8` |
| `competition_4k_proxy.mp4` | 3840×2160，6 帧 | 290,480 | `69000d11fd7e644efd546058d8f68bef8bc05426b335c351f6a818c0d836a95e` |

代理生成器使用固定随机种子构造跨通道共享纹理，使白光和荧光代理保留可检测的共同几何结构。该纹理只用于工程配准验证，输入清单保持 `not_real_patient_data=true`。

严格配置 `osteo_vision_competition_strict.yml` 的完整比赛流病例为 `case_98d0ff0d9c`。运行结果：

- 运行配置绑定、严格启动和模型预检全部通过。
- JPEG 与 MP4 均匹配官方 4K 格式档案。
- 相位相关配准 `applied=true`，响应 `0.366592`，安全阈值 `0.08`，估计平移 `[-0.0006, -0.0071] px`。
- 4K JPEG 融合、MP4 关键帧主线模型、工程复核和证据包导出全部通过。
- keyframe fallback 未触发，视频逐帧概率证据完整。
- 严格配置未登记患者条件候选，输出 `patient_conditioned_model_not_configured` 安全回退。

机器摘要位于 `artifacts/platform_competition/competition_flow_three_priority_registered_20260719/competition_flow_demo_check_summary.json`，SHA256 为 `c28a171f8bdc306c9253fe90851d7997520cc8fa4f3a08320a7f033750a71f1a`。

## 3. 开发配置患者条件运行

开发实例病例 `case_516176330f` 使用同一对 4K JPEG，并录入脱敏工程上下文：67 岁、男性、2 型糖尿病、高血压、二甲双胍、氨氯地平和 CRP 32 mg/L。复核状态保持 `review_required`。

实际执行模型为 `patient_conditioned_kits23_proxy_candidate`。运行结果：

- 四类证据均生成 3840×2160 PNG，模型状态 `available=true`。
- 临床变量可用率为 80%。
- `spatial_effect_applied=false`，差异面积为 `0 px / 0.00%`。
- 影像基础概率和患者条件概率 PNG 的 SHA256 均为 `35d11693ff35def529de03eb2199a79161851d29337c29ca8ac9385bf42e5610`，逐字节一致。
- 差异 mask 全零，SHA256 为 `96ca53dec30b3980d2d236295ecf1f50348e3c1746b7c8aed56a12e16fcfe008`。
- 不确定性图包含 89,531 个非零像素，最大显示值 248，SHA256 为 `65212519648ca1d60350b4b0ec34e5d92e744750ed5d012dce9402ef5bae8a06`。
- 证据 manifest SHA256 为 `217eb587cdec363aea8bf4468dbad4a71fce749b7bf6895b514ccbe9e76c4034`。

安全回退由临床上下文未可信核验、可信医生骨面缺失、目标域数据准入未通过和代理模型未晋级共同触发。全部原因已在前端中文化显示。

## 4. 浏览器与视觉验收

病例工作台已在 1600×1000 和 1280×800 桌面视口完成日间/夜间检查：

- 四张证据图均完成加载，浏览器自然尺寸均为 3840×2160。
- 水平溢出为 0，破损图片为 0，控制台错误为 0。
- 校验码、安全原因和长模型标识可完整换行。
- 日间与夜间主题均保持文字、边框和安全警示可读。

截图位于：

- `artifacts/e2e/three_priority_manual/case_516176330f_patient_conditioning_four_evidence.png`
- `artifacts/e2e/three_priority_manual/case_516176330f_patient_conditioning_1280_day.png`
- `artifacts/e2e/three_priority_manual/case_516176330f_patient_conditioning_1280_night.png`

## 5. 自动化验证

- `tests/unit/test_competition_flow_demo_check.py`：8 项通过。
- `backend/tests/unit/test_patient_conditioning_analysis.py`：5 项通过。
- `frontend/tests/PatientConditioningEvidence.test.ts`：2 项通过。
- Vue TypeScript 检查、Ruff、Black 和 `git diff --check` 通过。

## 6. 医学与数据边界

当前 4K 输入由程序生成，患者条件 checkpoint 来自 KiTS23 腹部 CT 非目标域代理。黑底概率图反映该代理对合成术野的低响应，不能解释为颌骨骨髓炎阴性结论。该闭环证明配准门、模型执行、四路证据、零差异安全回退和前端展示可运行。患者指标改变真实颌骨坏死边界的能力仍需颌骨骨髓炎术中白光/荧光、配对临床变量、可信医生骨面和独立目标域测试集完成训练与晋级验证。
