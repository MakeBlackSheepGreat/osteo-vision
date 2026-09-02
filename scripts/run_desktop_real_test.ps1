param(
    [string]$PackageRoot = "",
    [switch]$SkipCamera,
    [switch]$SkipButtonAudit,
    [switch]$DisableGpu,
    [int]$TimeoutMs = 600000
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$desktopTest = Join-Path $repoRoot "frontend\e2e\desktop.real.mjs"

if (-not (Test-Path -LiteralPath $desktopTest -PathType Leaf)) {
    throw "桌面真实测试脚本不存在：$desktopTest"
}

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) {
    throw "未找到 node.exe。请先安装 Node.js，并在 frontend 目录执行 npm ci。"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "frontend\node_modules\playwright") -PathType Container)) {
    throw "未找到 frontend/node_modules/playwright。请先执行 npm --prefix frontend ci。"
}

if ($PackageRoot) {
    $resolvedPackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
    $verifyScript = Join-Path $resolvedPackageRoot "verify_release.ps1"
    if (Test-Path -LiteralPath $verifyScript -PathType Leaf) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verifyScript -PackageRoot $resolvedPackageRoot
        if ($LASTEXITCODE -ne 0) { throw "运行包完整性校验失败：$resolvedPackageRoot" }
    }
}

$arguments = @($desktopTest, "--timeout-ms", [string]$TimeoutMs)
if ($PackageRoot) { $arguments += @("--package-root", $resolvedPackageRoot) }
if ($SkipCamera) { $arguments += "--skip-camera" }
if ($SkipButtonAudit) { $arguments += "--skip-button-audit" }
if ($DisableGpu) { $arguments += "--disable-gpu" }

Write-Host "启动桌面真实测试：$desktopTest"
& $node.Source @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "桌面真实测试失败，退出码：$exitCode。请查看 output/playwright/desktop-real-test/ 下的结果文件和截图。"
}
Write-Host "桌面真实测试通过。结果目录：output/playwright/desktop-real-test/"
