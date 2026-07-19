# 软件三项优先能力固定目标

冻结日期：2026-07-17

再次确认日期：2026-07-19
状态：固定持续目标；仅在用户明确调整时变更
数据责任：项目侧自主检索、下载、校验和维护所需公开、代理及近似数据

## 1. 文档目的

本文固定患者条件分割、骨活性分层和显微影像—三维参考配准三项软件能力，作为后续软件开发、数据集获取、医生协作、工程验证、模型训练和比赛证据整理的共同目标。三项软件能力主要映射官方赛题第二项“多模态医学图像融合与处理”和第三项“AI 辅助显微成像判读”；官方第一项“新型荧光造影剂设计及必要验证”继续独立维护和交付。所有能力均以患者安全、医生复核、证据可追溯和失败闭合为前提。

## 2. 目标一：患者临床变量参与受限空间分割

平台接收年龄、出生性别、基础病、用药、CRP、WBC、ESR、PCT、白蛋白、血糖、HbA1c、肌酐及采样时间、单位和复核状态。最终模型在医生复核骨面和影像不确定区内，使用患者条件模块对影像 logits 进行有界调整，同时保留：

- 纯影像基础 mask。
- 患者条件 mask。
- 两者差异 mask。
- 临床特征版本、缺失值掩码、上下文校验码和影响摘要。
- 临床资料缺失、过期、异常、未复核或分布外时的基础模型回退。

空间影响只能由患者级配对的目标域影像、临床变量和医生像素标注训练与独立验证后启用。禁止用人工规则直接规定高龄、糖尿病或炎症指标升高时扩大坏死区域。

## 3. 目标二：低活性、过渡、高活性和连续骨活性评分

平台在可信医生复核的骨面范围内输出：

- 低活性/疑似坏死候选。
- 过渡复核区。
- 高活性/可保留参考。
- 无法判断区 `ignore`。
- 连续骨活性评分图。
- 边界风险和不确定性图。

最终模型采用白光与原始荧光双通道、多任务结构，至少覆盖骨面门控、连续评分、三类概率和不确定性。设备叠加图只用于显示、质控和证据核对。规则阈值生成的三类区域继续作为待复核种子，不得替代目标域金标准。

金标准优先建立“术中关键帧—医生骨面与取样点—标本方向/切缘—离体照片—病理切片—术中影像回映射”证据链，并保留多医生独立标注、仲裁、分歧区域和证据等级。

任何 `0.80` 数值只允许解释为经过定义和校准的候选置信度，禁止解释为切净率、治愈率、复发率或自动切除边界。

## 4. 目标三：倍率/工作距离感知的三维配准与导航验证

平台通过离线 manifest、人工录入或标准文件接收倍率、工作距离、相机内参、畸变、帧时间戳、位姿、配准点、独立目标点和坐标变换，不依赖企业私有设备接口。

目标分级：

- L0：CBCT/STL 与影像候选区并列显示，保持未配准三维参考。
- L1：完成下颌仿体静态配准，覆盖相机标定、倍率/距离内参表、刚性点配准、PnP、可选 ICP、FRE、独立 TRE、重投影误差、变换文件和医生复核。
- L2：仅在受控 SHA256 manifest 绑定已准入 MP4、已验证 L1 PnP、v2 多点相机标定表、逐帧位姿、三维投影点、独立动态误差、漂移、九项安全参数批准和可信医生复核时，使用 FFprobe PTS 完成逐帧内参选择、`3D -> 2D` 投影与叠加证据；九项参数覆盖时间偏移、漂移、TRE 代理、动态目标误差、最小可见投影点、倍率变化率、工作距离变化率、内参切换率和标定歧义裕量。当前只允许已验证恒定帧率视频，VFR 与任何其他门控失败均撤销叠加并回退 L0。普通 pose-only 位姿链检查永久保持 L0。

任何模型、变换、标定、位姿、同步、误差或医生复核证据缺失时，必须撤销空间叠加并回退至 L0。L2 只允许表述为动态 AR 工程验证。

## 5. 固定推进顺序

1. 修复共同安全门控、完整测试回归和 Git 稳定基线。
2. 冻结三个版本化数据契约、医生标注 SOP 和验收协议。
3. 完成无需重训练的 API、持久化、前端对照、证据报告和安全降级。
4. 主动检索、下载、校验公开/代理/近似数据集并维护来源 manifest。
5. 制作下颌仿体和相机标定数据，完成 L1 静态配准。
6. 完成 L2 离线动态 AR、误差统计和失效注入。
7. 建立少量真实目标域病例的采集、标注、取样和病理对应流程。
8. 最后训练患者条件分割和骨活性多任务模型，并执行患者级、机构级和时间级独立验证。
9. 通过严格运行、概率校准、亚组审计、4K/实时性能、医生复核和失败闭合后，才允许申请启用空间自适应或替换比赛主线。

## 6. 数据集获取原则

项目侧主动寻找并下载可用于以下目的的数据：

- 白光/荧光配准、融合、时序和关键帧信号分割代理。
- 颌骨骨坏死、骨髓炎、MRONJ、骨自体荧光和四环素荧光近似证据。
- 带患者临床变量的医学分割数据，用于患者条件模型结构和消融联调。
- 带CBCT、颌骨标签、STL或可生成表面的三维解剖数据。
- 带相机位姿、标志点或可构造已知变换的配准/导航工程数据。

每项数据必须记录来源页面、直接下载链接、许可、数据域、模态、标签、患者/样本数量、临床变量、用途、本地路径、大小、SHA256和下载时间。代理数据只用于工程和方法验证；目标域临床性能只能由真实颌骨骨髓炎术中数据和医生复核证据支持。

## 7. 首批数据基线

截至 2026-07-19，已建立首批可追溯数据基线：

- 患者条件分割：KiTS23 临床 JSON、5 例患者级 CT 与像素 mask，HCC-TACE-Seg 临床表与 TCIA 清单，NSCLC-Radiomics 临床表，以及 MRONJ 临床/围术期化验表。清单位于 `research/datasets/public-candidates/patient_conditioning_starter_20260717/`。
- 骨活性与灰区工程代理：荧光手术降噪资源、2 段公开 ICG 手术视频、5-ALA/PPIX 显微荧光与医生逻辑 mask 数据。清单位于 `research/datasets/public-candidates/three_priority_zenodo_20260717/`。
- 三维配准：本地既有 DentVoxel、ToothFairy2，以及新增 SERV-CT 简化验证包。清单位于 `research/datasets/public-candidates/navigation_starter_20260717/`。

2026-07-18 的补充缺口审计进一步形成三组可追溯资源：

- 患者条件补充：HCC-TACE-Seg、NSCLC-Radiomics 和 Head-Neck-Radiomics-HN1 的官方来源页、临床表、TCIA 清单与治理信息。前两者可作为临床变量和分割联合工程代理；Head-Neck-Radiomics-HN1 影像受 NIH 受控访问政策管理。D069 MMDental 的 68,087,010,723 字节 ZIP64 远程包已通过 HTTP Range 选择性物化 `medical_records.csv` 和 1 例配对牙科 CBCT，保留 2,124 条就诊记录、660 个脱敏患者标识、年龄、性别、现病史、既往史、诊断和治疗字段。聚合质控确认 390 个患者存在多次就诊记录、2 个患者存在年龄冲突、0 个患者存在性别冲突，并记录所有 12 个字段的非空与缺失计数；这些冲突和缺失值必须在后续患者级切分与编码时显式处理。病例 `492` 为 `640×640×400`、`0.25 mm` 等体素 NIfTI，并生成 118,452 顶点、244,000 面的受控硬组织代理 STL。远端 MD5、源 CBCT、本地 STL、建模 manifest 的 SHA256 和 ZIP 成员 CRC32 均已绑定；建模结果保持未配准、未复核和 `navigation_ready=false`。该数据缺少骨髓炎像素标注、骨活性分层和白光/ICG 配对，保持非目标域、禁止训练晋级。清单位于 `research/datasets/public-candidates/patient_conditioning_gap_audit_20260718/`，D069 物化证据位于 `research/datasets/public-candidates/mmdental_patient_context_starter_20260719/`。
- 骨活性补充：D079-D084 覆盖 MRONJ CBCT 医生共识标注论文资产、下肢截肢骨面动态 ICG 三档灌注、感染性骨不连清创前后 ICG、骨移植 ICG 视频和骨/软组织术后坏死关联研究。D080 的“正常、可疑、受损”三档灌注最接近连续骨活性和过渡复核区的方法设计；原始序列、患者级 ROI 和像素金标准仍未公开。清单位于 `research/datasets/public-candidates/bone_activity_gap_20260718/`。
- 导航补充：D085-D089 覆盖头颈 CT/CBCT 配对元数据、340 例 IOS 三维牙标志点、C3VD 手眼标定与位姿契约、EndoSLAM 定时 6DoF 位姿及 ToothFairy3 多类颌面 CBCT 候选。D086 受 CC BY-NC-ND 4.0 约束，只用于保留原许可的内部非商业工程检查。D087 C3VD 官方样例已按 CC BY-NC-SA 4.0 下载 1,515,094,074 字节，ZIP CRC、官方远端长度和本地 SHA256 `ce6b285c578d9ebe42d9013bc21eb244d6df93ca0de63333b5ab38a80acc16ff` 均通过；样例含 766 对 RGB/depth 帧和 2,558 条位姿记录。项目已对 2 个重复时间戳采用“保留最后来源行”策略完成逐行哈希审计，得到 2,556 条唯一位姿；全部 766 帧在 10 ms 容差内完成绑定，未匹配 0 帧、歧义 0 帧，最大绝对时间差 9.693 ms。Scaramuzza OCamCalib polynomial v1 已按官方渲染方程接入，24 帧受控回放每帧投影 12 个可见模型点，并完成跟踪丢失、时间错位和漂移超限注入。全部代理回放由非目标域门控保持 `L0/unregistered_3d_reference`，`target_domain_flag=false`、`training_eligible=false`、`navigation_claim_allowed=false`。C3VD 继续保持结肠仿体、非荧光、非颌骨和禁止物理导航声明边界。受控数据位于 `research/datasets/public-candidates/c3vd_l2_proxy_20260719/d087/materialized/`，回放证据位于 `artifacts/navigation/c3vd_l2_proxy_replay_20260719/`。
- 近目标域病理补充：D051 人类 MRONJ 围病灶成像质谱平衡启动集已下载 6 位 MRONJ 和 8 位对照受试者、每人 1 个 ROI，并登记抗体 panel、补充材料和 Figshare API 元数据。17 个来源文件共 1,111,860,023 字节，官方 MD5、本地 SHA256、54 列表结构及 `X/Y/Z` 坐标均通过校验。该数据缺少术中白光/ICG、手术边界和配对临床变量，继续保持非目标域及训练未准入状态。清单位于 `research/datasets/public-candidates/d051_mronj_imaging_mass_cytometry_starter_20260718/`。
- 临床 ICG 视频补充：D090 从 Zenodo CC BY 4.0 记录下载 569,008,591 字节 ZIP，安全解压 3 段 1920×1080、25 FPS 的人体乳腺前哨淋巴结 ICG 视频，归档 MD5、逐视频 ZIP CRC 和 SHA256 均通过；D091 下载 2 段 960×540、约 29.97 FPS 的人体肝切除 ICG 视频，抽帧确认其合成画面同时包含白光、绿色伪彩叠加和灰度荧光面板。D090/D091 均缺少颌骨、骨面、骨活性分层、配对患者临床表和像素金标准，只用于视频解码、时序、三通道显示质控、拒答和鲁棒性工程验证。清单分别位于 `research/datasets/public-candidates/d090_breast_sentinel_icg_video_20260719/` 与 `research/datasets/public-candidates/d091_icg_hepatic_dynamic_proxy_20260719/`。
- 颌面几何补充：D092 PMCanalSeg 已从 Harvard Dataverse 的 CC0 1.0 公开记录选择性下载 5 位患者的上、下颌 CBCT 与配对翼腭管/下牙槽神经管标签，共 22 个来源或元数据文件、75,757,662 字节。10 对影像/标签的形状、仿射和二值标签均已核验，方向仍需 Slicer 或医生复核。该数据只用于多患者物理坐标、标签对齐、CBCT 导入和配准鲁棒性工程验证，保持 `navigation_claim_allowed=false`。清单位于 `research/datasets/public-candidates/pmcanalseg_navigation_starter_20260719/`。
- 近目标域影像补充：D093 已从 Mendeley Data 的 CC BY 4.0 记录下载 1 张 ROC 曲线、1 张 MRONJ SPECT/CT 与牙科影像复合图及两份官方元数据，共 524,188 字节，尺寸和逐文件 SHA256 已核验。公开资产缺少原始 DICOM、患者级临床变量、白光/ICG 配对和像素金标准，只进入目标病种近似视觉复核与证据边界测试。清单位于 `research/datasets/public-candidates/d093_mronj_spect_ct_figures_20260719/`。
- 近目标域临床变量补充：D094 ClinRad ORNJ 已从 Figshare CC BY 4.0 记录下载 53 例匿名人类 ORNJ 的 12 字段 XLSX，包含年龄、性别、治疗信息、Watson 分级及 CT/CBCT/全景片文字判读；原始文件为 19,198 字节，SHA256 为 `022075cfc73b13f7b7e6bcfbeacd6f30bb1eb506525333f83214742bc12c268e`。D095 MDACC ORNJ 已下载 1,129 例匿名头颈放疗患者的 61 字段 CSV，包含年龄、性别、危险因素、治疗、ORN 状态、Tsai 0-4 级及下颌剂量体积特征；原始文件为 403,524 字节，SHA256 为 `1aa85466fa34c3444908f89a03b4cfeff0fa80a668828f576eb146bde3fa25fb`。两项均可用于患者条件字段映射、患者级分组、弱分级标签、亚组审计和 no-harm 门控设计；由于缺少原始术中白光/荧光、像素标注、病理回映射和导航坐标，继续保持 `target_domain_flag=false`、`training_eligible=false` 和 `review_required`。清单分别位于 `research/datasets/public-candidates/d094_clinrad_orn_context_20260719/` 与 `research/datasets/public-candidates/d095_mdacc_orn_time_to_event_20260719/`。

上述资源均保持 `training_eligible=false` 和非目标域边界，需完成内容复核、许可复核、质量检查及相应任务准入后再进入训练或工程测试。

## 8. 当前边界

- 当前患者临床变量仍不改变像素空间边界。
- 当前低活性、过渡和高活性区域仍由概率图、阈值和复核骨面派生。
- 当前三维工作台通常保持 L0 未配准参考。
- 当前公开和代理数据不能支持真实颌骨骨髓炎术中临床性能结论。
- 企业设备接入、私有 SDK 和驱动适配不属于本项目软件交付范围。

## 9. 2026-07-18 软件安全基线进展

本轮已完成模型重训练前的共同安全门控：

- 临床上下文 `verified` 只允许可信医生或项目复核者提交；普通工程会话保持待复核状态。平台持久化复核人、角色、机构、认证来源和 UTC 时间，并在再次编辑后清除旧核验快照。
- 严格比赛配置与 artifact 输出目录解耦；骨面 prompt fallback 统一受当前运行配置控制。严格模式关闭 fallback 时，API 失败闭合并返回 `prompt_fallback_disabled_by_runtime_policy`。
- 三维证据升级为 v2 门控：验证变换文件存在性、SHA256、支持格式、4×4 有限齐次矩阵、可逆性、坐标链方向和单位连续性、配准误差与阈值来源、倍率/工作距离标定范围、医生复核，以及 L2 的位姿同步、TRE 和漂移。
- 三维任一门控失败时统一输出 `navigation_ready=false`、`navigation_level=L0` 和 `fallback_mode=unregistered_3d_reference`。
- 前端已展示临床核验凭证、L1/L2 安全状态和新增三维失败原因；L1 通过时明确显示静态配准验证状态。
- 版本化数据契约、三路影像角色、骨活性标注词典、医生仲裁 SOP、失效注入清单和验收定义已冻结在 `research/reports/planning/three_priority_capabilities_acceptance_v1_zh.md`。
- D049 大体积感染骨荧光显微数据已完成续传、MD5/SHA256 校验和 manifest 登记。当前三项目标 Zenodo 起始包共 8 个文件、672,217,319 字节，全部保持 `training_eligible=false`。

三项目标数据清单已通过扩展统一机器校验：15 个 manifest 共 47 条逻辑记录、138 个本地文件、5,514,559,510 字节，逐文件存在性、声明大小、SHA256 和 18 项来源字段全部通过。最新验证结果位于 `research/datasets/public-candidates/three_priority_manifest_verification_20260719_d095.json`，复核工具为 `tools/verify_three_priority_dataset_manifests.py`。全部源记录继续保持 `target_domain_flag=false`、`training_eligible=false` 和独立的数据域边界。当前公开检索仍未确认同时具备颌骨骨髓炎术中白光/ICG、患者临床变量、可信骨面及坏死/过渡/活骨像素标注的可直接下载联合目标域数据。

2026-07-19 最新全量工程自测：`backend/tests` 250 项通过；核心 `tests/unit` 与 `tests/smoke` 共 535 项通过；前端 47 个测试文件、179 项通过，1 项跳过；`vue-tsc`、Vite build、全量 Ruff 及 `src backend` mypy 通过。`NavigationWorkspacePage` 路由块约 61.97 kB，三维视口作为约 709.67 kB 的异步块按需加载；Vite 仅对该独立三维块保留大块提示。桌面浏览器已载入病例 STL 完成三维视口检查，画布像素检查通过，开启自动旋转后抽样变化比例为 `0.07086`，更新后的浏览器控制台为 0 错误、0 警告；病例输入路径也已取消字符串压缩并保持完整换行显示。2026-07-18 的严格比赛配置预检已通过，主线 checkpoint、SHA256 sidecar、FFmpeg 和 FFprobe 均已核验。上述结果均为项目工程自测，不能替代赛题方评审、真实下颌仿体或目标域验证。

公开真实视频 4K 工程验证已通过：使用 OFDVDnet 离体荧光手术代理视频与胫骨骨髓炎清创视频，完成来源追溯、抽帧可视化、不同帧率解码、不可读容器拒绝、4K JPEG 强制 tiling、短时内存观察和目标域声明阻断。当前 4K 单图强制 tiling 为 45 个 tile，端到端工程耗时约 3272 ms，峰值 GPU 显存约 724.8 MB；这些数值只反映本机单次工程运行。

严格比赛流工程自查已通过：4K JPEG 白光/ICG 融合、4K MP4 关键帧分割、工程复核、报告与证据包导出全部闭环，主线模型实际执行且未触发 keyframe fallback。结果分别位于 `artifacts/platform_competition/runtime_readiness_three_priority_20260718.json`、`artifacts/platform_competition/public_video_4k_three_priority_20260718/` 和 `artifacts/platform_competition/competition_flow_three_priority_20260718/`。上述检查属于项目工程自测，仍需与赛题方评审和后续目标域验证分开表述。

## 10. L1 静态配准工程闭环

平台已新增 Kabsch/SVD 刚性点配准适配器，输出 4×4 齐次变换、FRE、独立留出点 TRE、坐标空间、毫米单位、JSON 变换文件和 SHA256 sidecar。后端新增 `/three-d/registration-jobs` 任务接口，支持人工元数据和离线 manifest，成功与失败均写回病例三维证据；未完成可信医生复核时继续保持 L0。

离线验证工具 `tools/run_l1_static_registration_validation.py` 使用固定随机种子仿体点集，并引用 D076 SERV-CT 来源 manifest 形成可追溯工程证据。当前实测 FRE 为 `1.43e-14 mm`、独立 TRE 为 `1.68e-14 mm`，仅证明无噪声合成刚性变换的数值实现正确。SERV-CT 不含显式三维标志点对应表，后续需制作真实下颌仿体点集、加入定位噪声和独立测量真值，才能制定可用阈值。

D086 牙列标志点基准进一步使用 24 例公开真实牙列形状，每例 12 个配准点和 8 个独立 TRE 点，在 0、0.5、1、2 代理毫米噪声下共运行 96 次。0.5、1、2 噪声的 TRE 均值分别为 `0.352`、`0.772`、`1.625` 代理毫米，三类失败注入均被拒绝。D086 坐标单位未经来源证实，结果固定为 `L1_proxy_engineering_validation`、`navigation_ready=false`，禁止解释为物理精度或临床导航性能。证据位于 `artifacts/navigation/d086_landmark_registration_benchmark/d086_l1_landmark_benchmark.json`。

L1 已进一步接入显微相机内参、畸变、图像尺寸、倍率、工作距离、三维仿体点与二维像素点，通过 OpenCV `solvePnP` 估计静态参考到相机的刚性变换，并与 CBCT 到仿体的三维点配准变换组成 `CBCT -> phantom -> camera` 坐标链。API、前端向导和病例三维证据均记录内参标识、PnP 拟合误差、独立重投影误差、像素阈值、变换文件及 SHA256；独立重投影超限、验证点缺失或像素越界时回退 L0。固定合成仿体验证的拟合重投影 RMSE 为 `0.2234 px`，独立验证 RMSE 为 `0.2990 px`，两类失效注入均被安全拒绝。该结果只证明算法和证据链可运行，仍保持 `navigation_ready=false`、`review_status=review_required`，不能解释为物理相机标定精度或真实术中导航性能。证据位于 `artifacts/navigation/l1_camera_pnp_validation/l1_camera_pnp_validation.json`，复现工具为 `tools/run_l1_camera_pnp_validation.py`。

L1 输入已升级为可追溯契约：静态验证只读取 SHA256 绑定的版本化 registration manifest，manifest 必须绑定病例、模型文件及 SHA256、点对 artifact 及 SHA256、训练点与独立验证点、坐标空间、单位、变换方向和阈值证据。平台使用同一份字节完成哈希校验与 JSON 解析，并检查 STL/GLB/GLTF 可解析性、点数量、唯一性、有限性、非退化和独立验证集。人工直传点对只保留 L0 静态几何工程检查。L1 失败重跑会撤销同病例旧 L2 active 引用，历史文件仅供审计；取消任务不会改写病例证据。前端已支持 manifest 路径与 SHA256 提交。

坐标契约进一步固定每个 frame 的名称、手性、轴约定、显式轴方向、单位和来源，并固定 `row_major + column_vector + left_multiply + x_y_z_1` 矩阵约定。L1 刚性配准、PnP、组合变换及导出证据均保留 source/target frame；L2 从同一份校验字节复核 L1 artifact、transform chain、病例持久化 frame contract、投影点 frame 和逐帧 pose frame。字段缺失、手性与轴方向冲突、矩阵约定冲突或持久化证据篡改均立即撤销空间叠加并回退 L0。人工直传继续保留 L0 几何计算能力，不能取得导航就绪状态。

## 11. L2 离线动态回放软件工程闭环

平台明确区分 `pose_only_engineering` 与 `dynamic_ar_validation`。pose-only 支持人工元数据或离线日志完成位姿链、同步和失效注入检查，输出永久固定为 `navigation_ready=false`、`navigation_level=L0`，不能开启空间叠加。

严格动态请求只允许提交 `case_id`、`replay_mode=dynamic_ar_validation`、`input_mode=offline_manifest`、受控 manifest 路径及 SHA256、病例 `video_input_id` 和医生复核状态。安全参数、批准快照、逐帧 pose、三维投影点、相机内参和失效注入等安全关键字段必须来自 SHA256 绑定 manifest；API 拒绝客户端覆盖这些字段。manifest 必须绑定视频 ID、视频 SHA256、视频帧数、内参标识、`calibration_table_id`、三维投影点及坐标空间、逐帧位姿、显式跟踪漂移及独立来源、显式动态目标误差及独立来源，以及时间偏移、漂移、TRE 代理、动态目标误差、最小可见投影点、倍率变化率、工作距离变化率、内参切换率和标定歧义裕量九项安全参数、完整批准快照和医生复核状态。

动态回放只读取病例中已持久化且通过标定文件 SHA256、内参、畸变、图像尺寸、标定范围、独立 TRE、独立重投影误差、阈值批准和可信医生复核门控的 L1 PnP 证据。相机标定 artifact 强制使用 `osteo-vision-camera-calibration-v2`，包含唯一 `calibration_table_id`、`nearest_validated_entry_v1` 选择策略和一个或多个独立校验的倍率/工作距离内参项。manifest 表 ID 必须与病例 L1 标定一致；平台按每帧倍率和工作距离在已验证范围内选择距离最近的标定项，并输出 `calibration_selection` 证据。当前没有连续内参插值或外推。

输入视频必须经过病例批次准入并为实际可解码 MP4；平台使用 FFprobe 取得严格递增的逐帧 PTS，并要求帧间隔满足已验证恒定帧率门。VFR 被识别后输出 `video_variable_frame_rate_unsupported`、回退 L0 且不生成 overlay。视频/manifest SHA256、输入 ID 和帧数核对通过后，平台逐帧组合 `CBCT -> phantom -> baseline camera -> current camera` 坐标链，执行 `3D -> 2D` 投影、正深度、画幅内可见点、时间偏移、显式漂移和独立动态误差检查。倍率和工作距离变化率按 FFprobe PTS 计算；相邻内参切换率、重叠标定选择歧义及 `A/B/A` 内参振荡均进入时序连续性门控，任一超限或歧义会撤销整次 L2。

全部帧和外部证据通过后，平台生成逐帧 CSV、回放 JSON manifest、叠加 MP4 及各自 SHA256，并把 `three_d_ar_overlay` 证据写回病例。独立漂移/DTE 必须来自 SHA256 绑定、逐帧对应且经可信医生接受的测量 artifact；九项安全参数必须来自 SHA256 绑定的 `osteo-vision-l2-threshold-policy-v2` 批准策略 artifact，且只能保持或收紧平台安全边界。视频在解码和 overlay 前后均复核 SHA256；输出 FPS 由已验证 FFprobe PTS 中位间隔推导，并复核输出帧数、PTS、恒定间隔和时长。失败重跑会撤销旧 overlay、manifest、CSV、测量和策略的 active 引用，恢复可信 L1 snapshot 并标记 `failed_closed`；取消任务保持零病例持久化。任一门控失败时整次回放回退 `L0/unregistered_3d_reference`。坐标契约补强后的 L1/L2 聚焦回归 99 项通过，Black、Ruff 和 `git diff --check` 通过。时序连续性扩展的增量回归为核心与工具单测 44 项、后端合同 22 项、前端 6 项通过，并通过 Vue 类型检查、Ruff、Black 和聚焦 mypy。现有数据用于自动化工程测试，真实设备全倍率/全工作距离 4K 标定、真实下颌仿体物理精度、独立动态测量阈值和真实术中导航性能仍待验证。

## 12. 患者条件分割代理训练闭环

平台已实现双通道影像与结构化临床变量联合模型，输出 `image_only_logits`、`conditioned_logits`、`delta_map` 和 `uncertainty`。临床变量通过缺失掩码、有限值检查、可信上下文门控和运行时晋级授权共同控制；任一条件不满足时，`delta_map` 精确归零，患者条件结果与影像基础结果保持一致。空间调制幅度受 `max_logit_delta` 限制。运行安全门进一步要求目标域模型晋级、临床上下文核验和医生复核骨面，只允许在“复核骨面 ∩ 影像不确定区”内应用有限调制，并输出基础/条件概率、差异 mask、空间门控和逐样本原因码。

确定性非目标域代理 smoke 使用 20 个样本、10 个患者组和无泄漏分组切分完成 8 个训练批次。当前代理测试 Dice 为 `0.7337`、IoU 为 `0.5806`，checkpoint SHA256 为 `8a7aa6ee844e9030b4decc7f57c3a1d488afd275954a73337da9d5617e9de89a`。该结果只证明模型结构、训练脚本、缺失回退和有界调制可运行；`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`。

KiTS23 五患者公开代理闭环进一步完成了 5 例 CT、像素 mask 和临床 JSON 的一对一关联、RAS 标准化、形状/仿射/标签核验及患者级无泄漏切分，共物化 50 张二维切片，`train/val/test=30/10/10`。条件输入为年龄、出生性别、糖尿病、肾病和 eGFR，辅助影像通道固定标记为 `non_fluorescence_ct_proxy`，且已记录辅助通道与白光红通道重复这一输入局限。manifest 训练现在逐文件校验白光、辅助通道和 mask 的 SHA256、声明字节数、像素尺寸一致性与二值 mask，并绑定 provisional promotion policy 的路径、SHA256、schema 和状态。物化 CSV 进一步保存 source/canonical 4x4 affine 的规范 JSON 与 SHA256、canonical axis0/axis1 spacing、毫米单位和轴契约；trainer 复算 affine 哈希与列向量范数，并按模型 resize 后的有效行列 spacing 计算条件 mask 与纯影像 mask 的对称二维边界 Hausdorff 距离。

按最终契约复跑完成 288 个训练批次，`restricted_spatial_effect_passed=true`、`engineering_ready=true`；checkpoint SHA256 为 `74844abe17efd6ad2b411afe7569af84cfd4aa403c0336e531a0a1328ca501c1`，source CSV SHA256 为 `f2e57ac9d3fcb5f7901b5aac18ab90105ba5b3570019d25703bee196df194ba9`。代理测试集条件 Dice、IoU、召回率和精确率分别为 `0.243974`、`0.151192`、`0.195572`、`0.553163`，影像基础 Dice 为 `0.244188`，`conditioned_minus_image_only_dice=-0.000214`，测试 ECE 为 `0.005700`，最差代理亚组 Dice 差为 `-0.000214`，最大物理边界位移为 `183.478281 mm`。10/10 测试记录均具有可用边界位移证据；该最大值远超 provisional `2 mm` 门。no-harm、亚组和物理边界门继续失败，`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`、`clinical_claim_allowed=false`。六类 checkpoint-SHA 绑定证据覆盖 split、逐样本 prediction、calibration、subgroup、safety 和 physician review，训练证据位于 `artifacts/patient_conditioned_kits23_proxy/training/patient_conditioned_manifest_proxy_manifest.json`。

患者条件代理已接入平台开发配置的病例双通道分析调用链。`PatientConditionedSegmenterAdapter` 在 warmup 阶段校验 checkpoint、训练 manifest 及其 SHA256，并强制代理模型保持 `candidate_only=true`、`runtime_replacement_allowed=false` 和 `clinical_claim_allowed=false`；严格比赛配置未登记该代理候选。针对开发配置中实际登记的 KiTS23 checkpoint，端到端配置回归已生成完整证据文件，并核对 `proxy_checkpoint=true`、患者条件概率与影像基础概率完全一致、`delta=0` 和 `runtime_replacement_allowed=false`。`AnalysisService` 只选择一份由可信医生接受或修改、绑定当前白光 JPEG 的 `exposed_bone` 标注作为骨面门控，多份合格标注、来源不一致、尺寸或校验和异常均失败闭合。分析结果持久化 `image-only`、患者条件概率、差异图、空间门控、不确定性、逐项原因码和证据 manifest，并登记病例 artifact；病例工作台、结构化 JSON、Markdown 报告和量化 CSV 已展示同一份患者条件证据。当前 KiTS23 checkpoint 属于非目标域代理，目标域输入与正式晋级门均未通过，因此运行结果继续强制 `spatial_effect_applied=false`、患者条件概率等于影像基础概率且差异为零，不能据此声称患者指标已经改变颌骨病灶边界。

## 13. 骨活性多任务代理训练闭环

平台已实现白光与荧光双编码多任务网络，输出骨面门控、连续活性评分、低活性/过渡/高活性三类 logits 与概率、不确定性和拒答区域。未复核骨面、空骨面、非目标域输入或未通过目标域模型晋级时，空间候选全部拒答并输出 `IGNORE_INDEX`。拒答/ignore 像素的连续评分和三类概率统一清零，同时输出 `ignore_mask` 与 `activity_score_available_mask`；任一模型输出含非有限值时整幅结果进入拒答，不确定性固定为有限的最大值提示。

确定性非目标域代理 smoke 已生成 checkpoint 和 manifest。当前代理测试骨面 Dice 为 `0.9594`、活性评分 MAE 为 `0.1118`、三分类像素准确率为 `0.5627`，checkpoint SHA256 为 `e4fe9f162d9b92dc59f1753fce29e676fdcb2aed880f6dbc2eb68c2c310b12c2`。这些数值来自程序化代理标签，只用于代码和优化过程检查；`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`。

D074 公开真实显微荧光代理已完成独立物化和训练：从 Zenodo CC BY 4.0 源 ZIP 读取 5 个 5-ALA/PpIX 人脑显微荧光样本，按 3 个患者组固定 `train/val/test=1/2/2`，逐项校验源文件大小、SHA256、ZIP 路径、图像与 MAT mask 配对以及派生文件 SHA256。训练 manifest 额外绑定源病例、源序列、源帧、ZIP 成员路径、源图成员 SHA256 和源 mask 成员 SHA256，并对病例、源身份和六类派生资产执行跨 split 重复检查。公开 logical fluorescence mask 仅作为非骨 review-gate proxy；连续评分、低/过渡/高三类和不确定性由 gate 内红通道规则派生。该数据属于人脑 PpIX、非骨、非 ICG、非颌骨、非目标域。

D074 训练只在验证集扫描骨面阈值和拒答阈值，选定 `bone_gate_threshold=0.225` 与 `abstention_threshold=0.86` 后一次性冻结到测试集。测试 macro Dice 为 `0.733064`，三类 Dice 分别为 `0.803579/0.610677/0.784935`，连续评分 MAE 为 `0.131430`；骨面 Dice 为 `0.102190`，接受覆盖率为 `0.056417`，接受像素选择性错误率为 `0.301527`。预设测试约束要求覆盖率至少 `0.10` 且选择性错误率不高于 `0.15`，两项均失败，`engineering_utility_ready=false`。manifest 保留完整验证集阈值扫描、选参规则复算、测试集未参与选参声明和 frozen-test 失败证据；checkpoint SHA256 为 `e3b7f69f4ca3ff6f7a79180695e1b3e8946c082f8e9f056bbf870b4d916e8764`，source CSV SHA256 为 `a4a264a2572dbaccfbf2cf252a1a08a234afa0433afde0d9bba08f77f9e64c2a`，训练证据位于 `artifacts/bone_activity_d074_proxy/training/bone_activity_multitask_d074_proxy_manifest.json`。`target_domain_promotion_ready=false`、`runtime_replacement_allowed=false`。当前结果说明代码与训练闭环可运行，同时暴露了骨面泛化和不确定性排序缺口。

医生复核的 `ignore` 标注已接入骨活性证据回灌。平台只合并由可信医生创建并接受或修改、且绑定当前模型候选源图的 `ignore` 像素 mask，随后同步更新候选区、帧级 `video_signal_segmentation`、视频分割 manifest、病例 artifact 和 `bone_activity_spectrum-v2` 的无法判断区。工程人员创建、草稿、待提交、被拒绝或训练未准入的标注不进入该空间；来源变更、尺寸不一致、mask 损坏或 SHA256 不一致会失败闭合并清除旧的有效引用。该闭环记录医生复核结果及其版本来源，不构成目标域骨活性模型性能证据。

## 14. 目标域晋级门控状态

统一晋级验证器已升级为失败闭合 v3。正式替换主线需同时满足：经批准的目标域策略状态、完整必需指标、checkpoint 与预测/校准/亚组/安全/医生复核证据 SHA256 绑定、患者/病例/源文件/机构/时间切分重新计算、真实目标域测试集准入、可信医生身份、概率校准和能力专属安全指标。逐病例 prediction evidence v2 直接读取 SHA256 绑定的预测数组和医生复核真值，独立重算患者条件的 Dice、IoU、召回率、精确率、ECE、空掩膜、过分割、no-harm、亚组、回退和物理边界指标，以及骨活性的三类 Dice、类别支持、骨面 Dice、ECE、覆盖率、拒答错误率、选择性错误率、包含率和连续评分 MAE。骨活性晋级额外要求阈值只由验证集选择、冻结到测试集且不再调参，并同时检查选择性错误率、非拒答覆盖率和复核骨面包含率，避免全拒答造成虚假的低错误率。NaN、无穷值、布尔型样本数、空策略和临时策略均无法通过。

当前策略状态为 `provisional_internal_engineering_gate`，因此只允许生成目标域候选待审结果。T101 患者条件目标域训练、T102 骨活性目标域训练和 T107 正式策略批准继续保持未完成，等待真实颌骨骨髓炎术中影像、配对临床变量、医生像素标注、可信骨面和独立测试证据进入准入清单。

批准策略 SHA256 信任表和生产 Ed25519 公钥信任表当前均保持为空，任何自行填写 `approved_target_domain_runtime_gate` 的策略都无法获得运行替换授权。晋级器已拒绝负 ECE、负错误率、负 MAE、未准入代理指标、全拒答低错误率、缺失类别支持、阈值扫描篡改、测试阈值不一致、证据资产篡改、病例绑定不一致和患者身份错配。T107 审批链已实现认证身份绑定、医生与项目复核员双角色独立密钥、24 小时提交窗口、nonce/approval ID 防重放、签名撤销、密钥有效期与撤销状态、追加式 SQLite 哈希链、完整 bundle 导出和最终晋级器独立重放。离线 CLI 可在仓库外生成受 ACL 保护的 Ed25519 私钥、合并并校验双角色公钥信任表、从晋级器精确目标准备载荷、签名和本地自校验；后端全程不读取私钥。

T134-T135 聚焦回归已覆盖逐病例证据重放、签名模型、bundle 独立验证、后端审批服务/API、离线密钥与签名 CLI，以及患者条件训练 manifest，共 74 项通过；相关代码通过 Black、Ruff 和聚焦 mypy。T101、T102 和 T107 继续等待准入后的真实目标域数据、正式指标策略、独立医生审批和项目安全审批，当前任何代理 checkpoint 均无法进入运行替换。测试仅证明本地工程闭环，临床与物理导航边界保持不变。

## 15. D083 公开骨移植 ICG 视频工程证据

平台已对 D083 `Video1.mpeg` 完成源 ZIP SHA256、成员 CRC32、安全提取和浏览器兼容 H.264 MP4 转码，并使用严格比赛配置的主线关键帧模型完成 12 个全时段均匀关键帧的分割、时序量化、联系表和证据 manifest。源视频为 1024×768、约 29.97 FPS、约 105 秒的血管化骨移植物 ICG 灌注视频，属于人骨灌注近似域，缺少颌骨骨髓炎标签、患者—视频对应、固定 ROI、注射时间戳、曝光增益和像素金标准。

全时段采样显示前 4 帧处于暗场，代理模型在暗场仍产生非空候选 mask，平台已写入 `d083_dark_baseline_nonempty_mask` 安全警告。荧光解码亮度曲线可用于验证时序处理链路，空间 mask 只能作为待复核信号候选。所有结果保持 `target_domain_flag=false`、`training_eligible=false`、`runtime_replacement_allowed=false` 和 `navigation_ready=false`。证据位于 `artifacts/data_review/d083_icg_video_evidence_20260718/`，复现工具为 `tools/materialize_d083_icg_video_evidence.py`。

## 16. 患者条件分割 4K 可配准运行证据

官方 4K 代理生成器已加入固定种子的跨通道共享纹理，使白光/荧光代理在保持合成数据边界的同时具备可验证共同几何结构。新严格比赛流 `case_98d0ff0d9c` 的相位相关配准响应为 `0.366592`，超过 `0.08` 安全门；JPEG/MP4 官方规格检查、严格配置绑定、主线关键帧模型、工程复核和证据包均通过。输入路径、字节数、SHA256、官方规格档案和配准详情已直接写入机器摘要 `artifacts/platform_competition/competition_flow_three_priority_registered_20260719/competition_flow_demo_check_summary.json`。

开发配置病例 `case_516176330f` 使用同一对 3840×2160 JPEG 实际执行 `patient_conditioned_kits23_proxy_candidate`，生成影像基础概率、患者条件概率、空间差异图和模型不确定性四张 4K 证据。代理门控使基础与条件概率逐字节一致、差异 mask 全零、`spatial_effect_applied=false` 和主线替换关闭。前端已中文化全部患者条件失败原因，并在 1600×1000、1280×800 的日间/夜间桌面视口通过无水平溢出、无破损图片和零控制台错误检查。完整证据见 `research/reports/modeling/patient_conditioning_4k_registered_runtime_20260719_zh.md`。该结果保留非目标域、非临床性能和医生复核边界。

## 17. `clinical-feature-vector-v1` 患者变量证据闭环

平台已固定 `clinical-feature-vector-v1` 的 13 项特征并集：年龄、出生性别女性编码、糖尿病、高血压、肾病、免疫抑制、抗骨吸收用药、WBC、中性粒细胞百分比、CRP、ESR、血红蛋白和 eGFR。前 12 项覆盖目标域训练默认契约，eGFR 保留当前 KiTS23 代理兼容性。当前 KiTS23 checkpoint 只声明年龄、出生性别女性编码、糖尿病、肾病和 eGFR；运行时从完整平台向量安全投影到 checkpoint 子集，并明确列出未消费输入，禁止暗示未声明特征已经参与模型计算。

基础病阴性编码要求清单经过显式完整性复核；阳性编码只接受受控精确词表。否定描述、家族史和含糊自由文本保持缺失并等待结构化确认。同一指标在最新相同时间出现冲突值时，所有冲突记录均取消特征准入。化验单位、时间新鲜度、有限值和分布范围继续受失败闭合门控。

病例上下文、标准化化验、质量证据和特征向量由独立 assessment SHA256 绑定；运行时重新构建固定向量，并校验上下文、assessment、特征顺序、mask 语义、有限数值和双校验码。训练清单、checkpoint 和运行时还双向绑定 feature encoder schema/version、范围、逐特征临床值来源及来源证据 SHA256；版本不兼容、字段篡改、单侧缺失和来源不一致均失败闭合。空间调制还要求病例显式选择“受限患者条件分割”用途，并继续通过目标域模型晋级、可信医生核验、医生复核骨面和影像不确定区门控。前端、结构化 JSON、Markdown、量化 CSV 与证据包均展示录入输入、有效特征、checkpoint 消费、最终空间应用和失败原因。

当前 KiTS23 非目标域代理的最终空间应用仍为 0 项，患者条件概率保持影像基础回退，不能据此声称患者指标已经改变颌骨病灶边界。患者条件相关 Python 回归 67 项、前端聚焦测试、Vue 类型检查、Black、Ruff 和 mypy 均通过。本轮未重训练模型，旧 12 特征 smoke checkpoint 继续保持未注册。

## 18. D036 数字下颌仿体 L1/L2 工程证据

平台已使用 D036 ToothFairy2 公开下颌标签导出的真实 STL 作为数字解剖表面，通过真实 FastAPI、病例持久化、L1 配准任务和 L2 离线回放路径生成可重放证据。点对、相机内参、双倍率 4x/6x 标定、六帧视频、位姿、独立误差和阈值策略均为受控数字仿体数据；该运行不包含真实显微镜、物理下颌仿体或术中跟踪。

无噪声数字变换的 L1 FRE 为 `2.93e-14 mm`、独立 TRE 为 `2.34e-14 mm`、独立重投影误差为 `6.23e-14 px`，只用于验证坐标、API、持久化和数值链路。L2 软件门完成 6/6 帧、同一 L1 链绑定和双倍率内参选择；篡改 `l1_model_sha256` 后正确触发 `l1_chain_binding_mismatch`。随后注入医生复核未完成状态，病例主动回退 `L0/unregistered_3d_reference`，最终 `navigation_ready=false`。

证据包已重算 35 个文件、931,753 字节及全部 SHA256，摘要位于 `artifacts/navigation/d036_digital_phantom_navigation_validation_20260719/runs/20260719T0204410263800d7649/validation_summary.json`，摘要 SHA256 为 `6b865abf37733b8db0135f10af57f247094c5baf628a7bcf5d5da87134f879dd`。来源审计保留 STL 二进制头部残留 D024 token 与 D036 邻接证据不一致警告；模型文件 SHA256 与 D036 证据 manifest 一致。包内固定 `target_domain_flag=false`、`physical_phantom_flag=false`、`real_device_flag=false` 和 `navigation_claim_allowed=false`。根代理导航聚焦回归 104 项通过，证据包独立重算通过。

## 19. 医生标注训练准入 v2

医生标注训练清单已升级为 `osteo-vision-manual-annotation-training-manifest-v2`。独立医生复核只是准入条件之一；平台还会失败闭合检查机构训练授权、显式 `training` 用途、脱敏确认、病例映射表机构保管、病例批次状态、来源输入准入、批次与病例绑定、受控存储路径和来源输入 SHA256。禁止训练、仅分析、仅验证等用途文本会被明确拒绝。复核时与清单导出时均执行门控，清单转换层再次复验全部治理证据。

可信医生确认的 `ignore` 区可继续用于当前病例的骨活性复核空间更新，其训练资格单独受 v2 数据治理门控制约。前端已取消“点击接受即准入”的预判文案，显示真实隔离原因。聚焦后端测试 18 项、训练准入/下游消费测试、前端测试、Vue 类型检查、Vite 构建、Black、Ruff 和 mypy 均通过。

## 20. 骨活性 checkpoint 运行与病例证据闭环

D074 骨活性代理 checkpoint 已通过校验码绑定的真实 adapter 推理。Checkpoint SHA256 为 `e3b7f69f4ca3ff6f7a79180695e1b3e8946c082f8e9f056bbf870b4d916e8764`，训练 manifest SHA256 为 `50816b29384766fdc6b7dc23d7a04d523958343351b89ff6a1d2e7dc4f5d7a8f`。运行生成的原始工程 NPZ 为 `artifacts/visual_evidence/osteo_vision/bone_activity_multitask/d074-runtime-adapter-validation_92bba542485ec338_bone_activity_raw_engineering_outputs.npz`，文件大小 `950,152` 字节，SHA256 为 `ecb4c27c8a98abe883b8f09510de1e1fe25c3ca9617ab4b40d5c357425b68bf9`；运行证据 JSON SHA256 为 `05aff753b29e6b34e5463a685581b276a09eef6c629e6182b2ff9723c199ef25`。

实际运行记录 `engineering_inference_executed=true`，同时保持 `proxy_checkpoint=true`、`engineering_utility_ready=false`、`spatial_candidates_available=false`、`spatial_effect_applied=false`、`safe_fallback_applied=true` 和 `runtime_replacement_allowed=false`。原始工程数组只作为模型执行与数值审计证据，禁止直接转换为低活性、过渡、高活性空间图、面积比例、连续评分或切除边界。

平台开发配置只按精确模型 ID `bone_activity_multitask_d074_proxy_candidate` 和模型家族显式调用该候选。`AnalysisService` 将配准后的荧光图、配准状态、可信医生骨面门控和目标域输入门传入 adapter，并把结果持久化为 `fused_outputs.bone_activity_checkpoint_evidence`。平台层失效测试故意让测试 adapter 返回代理空间类别图和面积，服务仍强制清除类别图、空间路径与面积量化，保留 conventional fusion 和医生复核路径。证据 JSON 与原始 NPZ 分别登记为独立病例 artifact；结构化 JSON、Markdown、量化 CSV 和 ZIP 证据包均独立记录 `checkpoint_engineering_evidence`，与现有 `rule_derived_spectrum` 分开。

病例工作台已增加独立 checkpoint 工程证据区，显示模型 ID、非目标域训练域、执行状态、空间关闭状态、checkpoint/manifest/NPZ/JSON SHA256、失败原因以及 NPZ/JSON 下载入口；视频帧选择时只读取当前帧绑定证据，避免借用其他帧或旧运行结果。现有骨活性连续谱面板明确标记为规则派生证据。

聚焦验证覆盖后端 checkpoint 持久化与导出、真实 runtime/config、患者条件骨面门解耦共 `21` 项通过，前端 checkpoint 与规则谱 `8` 项通过；Ruff、Black、聚焦 mypy、Vue 类型检查、Vite 生产构建和 `git diff --check` 通过。现有 3D 异步 chunk 体积警告保持为性能优化项，不影响本闭环的安全门控。D074 仍属于人脑 PpIX、非骨、非 ICG、非颌骨代理，目标域骨活性模型训练、独立验证和正式晋级继续由 T102/T107 门控。
