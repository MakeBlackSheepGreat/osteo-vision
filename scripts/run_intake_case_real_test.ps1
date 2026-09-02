param(
    [string]$PackageRoot = "artifacts\release\offline-release\Osteo-Vision-Offline-Release-win32-x64-20260831-r28",
    [int]$TimeoutMs = 600000
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$testScript = Join-Path $repoRoot "frontend\e2e\intake-case.real.mjs"
$packagePath = if ([System.IO.Path]::IsPathRooted($PackageRoot)) {
    $PackageRoot
} else {
    Join-Path $repoRoot $PackageRoot
}
$resolvedPackageRoot = (Resolve-Path -LiteralPath $packagePath).Path

if (-not (Test-Path -LiteralPath $testScript -PathType Leaf)) {
    throw "专项真实测试脚本不存在：$testScript"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedPackageRoot "Osteo Vision Platform.exe") -PathType Leaf)) {
    throw "发行包入口不存在：$resolvedPackageRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "frontend\node_modules\playwright") -PathType Container)) {
    throw "未找到 frontend/node_modules/playwright。请先执行 npm --prefix frontend ci。"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "packaging\offline_release\verify_release.ps1") -PackageRoot $resolvedPackageRoot
if ($LASTEXITCODE -ne 0) { throw "发行包完整性校验失败：$resolvedPackageRoot" }

& node.exe $testScript --package-root $resolvedPackageRoot --timeout-ms $TimeoutMs
if ($LASTEXITCODE -ne 0) { throw "数据准入/病例档案专项真实测试失败。请查看 output/playwright/intake-case-real-test/。" }
Write-Host "数据准入/病例档案专项真实测试通过。结果目录：output/playwright/intake-case-real-test/"
