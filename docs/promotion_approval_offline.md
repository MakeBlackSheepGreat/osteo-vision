# 目标域模型晋级离线签名

本流程用于 T107 的正式审批证据准备。它只解决审批载荷的身份绑定、目标哈希绑定、签名与本地自校验。真实颌骨骨髓炎目标域数据、医生像素标注、独立测试、指标策略批准、两类独立角色审批和运行晋级门仍需分别通过。

## 安全边界

- 私钥仅保存在仓库外的离线目录，平台后端只读取公钥信任表。
- CLI 拒绝仓库、`artifacts/` 和后端运行产物根目录中的私钥路径。
- 私钥使用 Ed25519 PKCS8 PEM；当前实现采用未加密 PEM，并强制检查文件 ACL/权限。离线介质、操作系统账户和物理保管仍需受控。
- 所有输出均拒绝覆盖已有文件，避免误覆盖审批证据或密钥。
- 签名前需人工核对模型 ID、checkpoint SHA256、策略 SHA256、证据包 SHA256、审批身份、决策和撤销引用。
- `sign` 会用本地公钥信任表自校验身份、能力范围、密钥有效期、签名时间和签名内容。
- 后端提交还会核对已认证复核身份并写入追加式哈希链；离线签名文件自身不会开放运行替换。

## 1. 生成离线密钥与公钥信任表

PowerShell 示例：

```powershell
$offline = Join-Path $env:USERPROFILE ".osteo-vision-offline-approval"
New-Item -ItemType Directory -Path $offline -Force | Out-Null

conda run -n osteo-vision python tools\sign_promotion_approval.py generate-key `
  --private-key "$offline\physician.private.pem" `
  --public-key "$offline\physician.public.pem" `
  --trust-store "$offline\physician.trust-store.json" `
  --key-id physician-key-001 `
  --actor-id doctor-id-from-institution `
  --role physician `
  --institution "Authorized Institution" `
  --allowed-capability patient_conditioned_segmentation `
  --allowed-capability bone_activity_multitask
```

项目复核员应生成独立密钥和独立 `key_id`。两人分别交付公钥信任表后，使用受控命令合并并校验双角色覆盖：

```powershell
conda run -n osteo-vision python tools\sign_promotion_approval.py merge-trust-stores `
  --input "$offline\physician.trust-store.json" `
  --input "$offline\project-reviewer.trust-store.json" `
  --output "$offline\deployment.trust-store.json" `
  --required-capability patient_conditioned_segmentation `
  --required-capability bone_activity_multitask
```

部署人员只传递合并后的公钥信任表；私钥文件始终留在各自离线保管目录。

## 2. 准备待审核载荷

以下哈希必须来自已冻结、已校验的目标域证据。先用晋级器从 checkpoint、策略和六类证据文件计算统一目标，避免人工转录哈希。示例文件 `configs/promotion/promotion_approval_payload.example.json` 仅展示字段结构，不可直接用于审批。

```powershell
conda run -n osteo-vision python tools\check_three_priority_model_promotion.py `
  <目标域checkpoint-manifest.json> `
  --gates configs\training\three_priority_promotion.yml `
  --write-approval-target "$offline\approval.target.json" `
  --output "$offline\promotion.preapproval.report.json"

conda run -n osteo-vision python tools\sign_promotion_approval.py prepare-payload `
  --output "$offline\approval.patient.review.json" `
  --approval-id approval-20260719-physician-001 `
  --target "$offline\approval.target.json" `
  --signer-actor-id doctor-id-from-institution `
  --signer-role physician `
  --signer-institution "Authorized Institution"
```

命令会生成随机 nonce 和带时区的 UTC 时间。签名提交窗口为 24 小时；超时后应重新生成载荷并再次人工核对。

## 3. 签名并自校验

```powershell
conda run -n osteo-vision python tools\sign_promotion_approval.py sign `
  --payload "$offline\approval.patient.review.json" `
  --private-key "$offline\physician.private.pem" `
  --trust-store "$offline\physician.trust-store.json" `
  --key-id physician-key-001 `
  --output "$offline\approval.patient.signed.json"
```

成功输出必须包含 `self_verified: true`。`approval.patient.signed.json` 可提交到 `POST /model-promotion/approvals`；请求仍需携带与签名身份完全一致的受信复核令牌。

## 4. 部署公钥信任表

平台默认从 `configs/security/promotion_trusted_keys.json` 读取公钥信任表，也可通过 `OSTEO_PROMOTION_TRUSTED_KEYS_PATH` 指向部署侧只读文件。正式表需要同时登记医生和项目复核员的独立公钥、身份、机构、有效期与允许能力。私钥路径和私钥内容不得进入环境变量、服务配置、病例证据、日志或 Git。

当前 T107 继续保持未完成，直到真实目标域数据、正式指标策略和两类独立签名审批全部通过。

## 5. 导出双签 bundle 并重放最终晋级门

两类签名均经认证接口提交后，根据 `approval.target.json` 的五个字段查询 bundle。随后让晋级器独立复算完整哈希链、签名、身份、撤销状态、证据资产和全部指标。

```powershell
$target = Get-Content "$offline\approval.target.json" -Raw | ConvertFrom-Json
$query = @{
  capability = $target.capability
  model_id = $target.model_id
  checkpoint_sha256 = $target.checkpoint_sha256
  policy_sha256 = $target.policy_sha256
  evidence_bundle_sha256 = $target.evidence_bundle_sha256
}

$bundle = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8001/model-promotion/approvals/bundle" `
  -Method Get `
  -Body $query
$bundle | ConvertTo-Json -Depth 100 | Set-Content "$offline\approval.bundle.json" -Encoding UTF8

conda run -n osteo-vision python tools\check_three_priority_model_promotion.py `
  <目标域checkpoint-manifest.json> `
  --gates configs\training\three_priority_promotion.yml `
  --approval-bundle "$offline\approval.bundle.json" `
  --approval-trust-store configs\security\promotion_trusted_keys.json `
  --output "$offline\promotion.final.report.json"
```

只有最终报告同时给出 `target_domain_promotion_ready: true`、`promotion_approval_valid: true` 和 `promotion_active_approval_count: 2` 时，才允许进入后续人工发布流程。`clinical_claim_allowed` 持续保持 `false`。
