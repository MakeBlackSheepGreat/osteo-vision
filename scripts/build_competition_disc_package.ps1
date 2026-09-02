param(
    [string]$CondaEnv = "osteo-vision",
    [switch]$SkipFrontendBuild,
    [switch]$SkipBackendBuild,
    [string]$ElectronArchive = "$env:LOCALAPPDATA\electron\Cache\electron-v28.3.3-win32-x64.zip",
    [string]$ReleaseName = "Osteo-Vision-Competition-Disc-win32-x64",
    [ValidateRange(0.1, 100.0)]
    [double]$MediaCapacityGB = 8.5,
    [switch]$SkipMediaCapacityCheck
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$desktopBuilder = Join-Path $scriptRoot "build_desktop_package.ps1"
$sourceDesktopPackage = Join-Path $repoRoot "artifacts\release\desktop\Osteo Vision Platform-win32-x64"
$releaseRoot = Join-Path $repoRoot "artifacts\release\competition-disc"
$packageRoot = Join-Path $releaseRoot $ReleaseName
$stagingRoot = Join-Path $releaseRoot "$ReleaseName.staging"
$discAssets = Join-Path $repoRoot "packaging\competition_disc"
$userGuideRoot = Join-Path $repoRoot "docs\release"
$userGuideFiles = @(
    "Osteo_Vision_r28_使用说明.docx",
    "Osteo_Vision_r28_使用说明.pdf"
)

function Get-Sha256Hex {
    param([Parameter(Mandatory)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (Test-Path -LiteralPath $packageRoot) {
    throw "Release target already exists: $packageRoot. Set -ReleaseName to preserve the existing release."
}
if (Test-Path -LiteralPath $stagingRoot) {
    throw "Release staging directory already exists: $stagingRoot. Remove this generated staging directory after inspecting it."
}

$desktopParameters = @{
    CondaEnv = $CondaEnv
    ElectronArchive = $ElectronArchive
}
if ($SkipFrontendBuild) {
    $desktopParameters.SkipFrontendBuild = $true
}
if ($SkipBackendBuild) {
    $desktopParameters.SkipBackendBuild = $true
}
& $desktopBuilder @desktopParameters
if ($LASTEXITCODE -ne 0) {
    throw "Desktop package build failed."
}
if (-not (Test-Path -LiteralPath $sourceDesktopPackage -PathType Container)) {
    throw "Desktop package is missing after the build: $sourceDesktopPackage"
}

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
Get-ChildItem -LiteralPath $sourceDesktopPackage -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $stagingRoot -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $discAssets "verify_release.ps1") -Destination (Join-Path $stagingRoot "verify_release.ps1") -Force
Copy-Item -LiteralPath (Join-Path $discAssets "README.md") -Destination (Join-Path $stagingRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $stagingRoot "LICENSE") -Force
foreach ($userGuideFile in $userGuideFiles) {
    $sourcePath = Join-Path $userGuideRoot $userGuideFile
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Usage guide is missing: $sourcePath"
    }
    Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $stagingRoot $userGuideFile) -Force
}

$requiredFiles = @(
    "Osteo Vision Platform.exe",
    "verify_release.ps1",
    "README.md",
    "Osteo_Vision_r28_使用说明.docx",
    "Osteo_Vision_r28_使用说明.pdf",
    "resources\backend\osteo-vision-api.exe",
    "resources\runtime_assets\configs\inference\osteo_vision_competition_strict.yml",
    "resources\runtime_assets\demo_data\ofdvdnet\ofdvdnet_demo_manifest.csv",
    "resources\runtime_assets\demo_data\ofdvdnet\video\OFDVDNET_001.mp4",
    "resources\runtime_assets\artifacts\platform\three_d_runtime\references\d024\mandible_d024_0001.stl",
    "resources\runtime_assets\research\datasets\public-candidates\d036_toothfairy2\raw\Dataset112_ToothFairy2\imagesTr\ToothFairy2F_001_0000.mha"
)
foreach ($relativePath in $requiredFiles) {
    $path = Join-Path $stagingRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Competition disc layout is missing required file: $relativePath"
    }
}

$packageFiles = @(Get-ChildItem -LiteralPath $stagingRoot -File -Recurse | Sort-Object FullName)
$packageBytes = [int64](($packageFiles | Measure-Object -Property Length -Sum).Sum)
$capacityBytes = [int64][math]::Floor($MediaCapacityGB * 1000000000)
if (-not $SkipMediaCapacityCheck -and $packageBytes -gt $capacityBytes) {
    throw "Package size $packageBytes bytes exceeds the configured media capacity $capacityBytes bytes."
}

$manifestFiles = foreach ($file in $packageFiles) {
    $relativePath = $file.FullName.Substring($stagingRoot.Length).TrimStart("\", "/").Replace("\", "/")
    [ordered]@{
        path = $relativePath
        bytes = [int64]$file.Length
        sha256 = Get-Sha256Hex -Path $file.FullName
    }
}
$manifest = [ordered]@{
    schema_version = 1
    package_id = "osteo-vision-competition-disc"
    package_version = (Get-Content -LiteralPath (Join-Path $repoRoot "package.json") -Raw -Encoding utf8 | ConvertFrom-Json).version
    created_at_utc = [DateTime]::UtcNow.ToString("o")
    target = [ordered]@{ os = "Windows"; architecture = "x64"; offline = $true }
    accelerator = [ordered]@{
        default_policy = "auto"
        gpu_path = "CUDA when a compatible NVIDIA driver and GPU are available"
        cpu_fallback = "automatic when CUDA is unavailable or unusable"
    }
    media_capacity_gb = $MediaCapacityGB
    package_bytes = $packageBytes
    files = @($manifestFiles)
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $stagingRoot "release-manifest.json") -Encoding utf8

Move-Item -LiteralPath $stagingRoot -Destination $packageRoot
Write-Host "Competition disc package created at $packageRoot"
Write-Host "Package size: $packageBytes bytes; configured media capacity: $capacityBytes bytes"
