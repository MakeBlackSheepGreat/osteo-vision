# 快速开始

适用版本：`0.3.0-rc.2`。平台输出需要医生复核，仅供研发验证、比赛展示和受控工程评估。

## 1. 环境

固定运行环境为 Python 3.11、Conda、Node.js 和 FFmpeg：

```powershell
conda env create -f environment.yml
conda activate osteo-vision
npm --prefix frontend install
npm --prefix frontend/three-d-runtime ci
```

已有环境可更新依赖：

```powershell
conda run -n osteo-vision python -m pip install -r requirements.txt
npm --prefix frontend install
```

## 2. 启动比赛严格模式

```cmd
start_platform.cmd
```

无浏览器启动：

```cmd
start_platform.cmd -NoBrowser
```

后台启动且不打开浏览器：

```cmd
start_platform.cmd -NoBrowser -Headless
```

根目录启动器依次检查：

- 比赛严格配置及其哈希。
- 主线 checkpoint 与 SHA256 sidecar。
- FFmpeg 和 ffprobe。
- 隔离病例数据库与本地写入目录。
- 后端 `/health`、`/ready` 和 OpenAPI 必要路由。
- 实时帧主线模型预热。
- Vue 前端开发服务。

默认地址：

- 后端：`http://127.0.0.1:8001`
- 健康检查：`http://127.0.0.1:8001/health`
- 就绪检查：`http://127.0.0.1:8001/ready`
- 前端：`http://127.0.0.1:5174/`
- 独立三维渲染运行时：`http://127.0.0.1:5175/`，通过 `-StartThreeDRuntime` 作为可选独立进程启动。

端口覆盖变量：`OSTEO_BACKEND_PORT`、`OSTEO_FRONTEND_PORT`、`OSTEO_THREE_D_RUNTIME_PORT`、`VITE_OSTEO_API_URL`、`VITE_OSTEO_THREE_D_RUNTIME_URL`、`VITE_OSTEO_MAIN_APP_ORIGIN`、`OSTEO_ALLOWED_ORIGINS`。后端、主前端和独立三维运行时端口需使用三个不同值。

## 3. 手动启动

终端一：

```powershell
conda activate osteo-vision
python -m backend.osteo_vision_api.main
```

终端二：

```powershell
npm --prefix frontend run dev
```

终端三用于独立三维渲染运行时：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_three_d_runtime.ps1
```

主平台与渲染运行时一起启动：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_platform.ps1 -StrictCompetition -StartThreeDRuntime
```

独立运行时通过 `/runtime-manifest.json` 确认服务身份。主平台的病例、CBCT/STL 建模、L1/L2、安全状态、二维证据和医生复核不依赖该渲染进程保持可用。

Gradio 入口仅用于框架兼容性检查：

```powershell
conda run -n osteo-vision python app/main.py --config configs/inference/osteo_vision.yml
```

比赛展示与医生工作流统一使用 FastAPI + Vue 平台。

## 4. 复核身份

无凭据复核记录为 `engineering_reviewer`。可信医生和项目复核员身份由部署人员通过服务端令牌映射注入：

```powershell
$env:OSTEO_REVIEW_IDENTITIES_JSON = @'
{
  "replace-with-random-token-at-least-16-chars": {
    "actor_id": "institution-assigned-doctor-id",
    "role": "physician",
    "institution": "Authorized Institution",
    "auth_source": "verified_identity_token"
  }
}
'@
start_platform.cmd
```

令牌和真实身份映射属于部署秘密。仓库、报告和病例证据中禁止保存令牌。

目标域晋级审批使用仓库外 Ed25519 私钥，流程见 [promotion_approval_offline.md](promotion_approval_offline.md)。

## 5. 主工作流

前端导航按以下顺序使用：

1. **数据准入**：登记机构授权、用途、脱敏、病例映射保管状态并校验文件。
2. **病例档案**：创建病例、录入受限临床上下文、检查输入状态。
3. **病例工作台**：上传 JPEG 双通道或导入 MP4，执行融合、关键帧或连续帧分析。
4. **三维导航**：导入 CBCT/STL，检查对象树、建模、L1 配准和 L2 离线回放。
5. **医生复核**：接受、修改或拒绝候选结果。
6. **报告导出**：生成结构化报告和病例证据包。
7. **人工标注**：从病例关键帧进入像素级标注、版本和训练准入流程。

正式设备文件写入病例前应通过数据准入页面。`quarantined` 文件仅保留原因码，不能参与分析。

## 6. 运行与模型核验

```powershell
conda run -n osteo-vision python tools/check_runtime_readiness.py --config configs/inference/osteo_vision_competition_strict.yml --require-strict
conda run -n osteo-vision python scripts/model_inventory.py --config configs/inference/osteo_vision_competition_strict.yml
conda run -n osteo-vision python tools/check_project_readiness.py
```

严格配置只允许当前已核验 keyframe 主线运行。患者条件和骨活性代理模型保持安全关闭状态；它们仍可用于离线证据、失败原因和后续目标域晋级流程。

## 7. 测试

```powershell
conda run -n osteo-vision python -m ruff check osteo_vision_core backend tests scripts tools
conda run -n osteo-vision python -m mypy osteo_vision_core backend --hide-error-context --no-error-summary
conda run -n osteo-vision python -m pytest tests/unit tests/smoke
conda run -n osteo-vision python -m pytest backend/tests
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend/three-d-runtime run typecheck
npm --prefix frontend/three-d-runtime run test
npm --prefix frontend/three-d-runtime run build
```

发布聚合质量门：

```powershell
make release-check
make release-build
```

比赛流程与 4K 稳定性：

```powershell
conda run -n osteo-vision python tools/run_platform_smoke.py
conda run -n osteo-vision python tools/run_official_4k_pressure_smoke.py --frames 6 --keyframes 3
conda run -n osteo-vision python tools/run_mp4_edge_case_smoke.py --frames 48 --keyframes 5 --fps 6
conda run -n osteo-vision python tools/run_keyframe_tiling_smoke.py --width 3840 --height 2160
conda run -n osteo-vision python tools/run_competition_flow_demo_check.py
```

上述 smoke 使用合成或公开非目标域代理数据，结果只说明工程链路与输出完整性。

## 8. 性能基准

```powershell
conda run -n osteo-vision python tools/benchmark_core_hotpaths.py --repeats 3 --output artifacts/performance/core_hotpaths_current.json
```

输出记录运行环境、三个核心热路径的优化前后中位耗时、加速比和输出一致性。模型端优化继续使用 4K tiling、live fast-output 和完整比赛流工具，在相同输入、checkpoint、分辨率和运行次数下对比。

## 9. 文档与目录检查

```powershell
conda run -n osteo-vision python tools/audit_active_documentation.py
conda run -n osteo-vision python tools/clean_workspace.py
```

`clean_workspace.py` 默认只预览缓存与构建候选项。确认范围后使用 `--apply`；`--include-artifacts` 只扩展到可重复生成的 E2E/UI 产物。病例库、人工标注、smoke/性能证据、训练运行、`artifacts/tmp/` 和研究数据集均受保护。

目录所有权和清理范围见 [project_structure.md](project_structure.md)。
