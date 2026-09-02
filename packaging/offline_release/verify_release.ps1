param(
    [string]$PackageRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$resolvedRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
$manifestPath = Join-Path $resolvedRoot "release-manifest.json"

function Get-Sha256Hex {
    param([Parameter(Mandatory)][string]$Path)

    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        if ($stream) { $stream.Dispose() }
        $hasher.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Release manifest is missing: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$requiredFiles = @(
    "verify_release.ps1",
    "README.md",
    "Osteo_Vision_r28_使用说明.docx",
    "Osteo_Vision_r28_使用说明.pdf",
    "Osteo Vision Platform.exe",
    "resources\backend\osteo-vision-api.exe",
    "resources\runtime_assets\configs\inference\osteo_vision_strict.yml",
    "resources\runtime_assets\demo_data\ofdvdnet\ofdvdnet_demo_manifest.csv",
    "resources\runtime_assets\demo_data\ofdvdnet\video\OFDVDNET_001.mp4",
    "resources\runtime_assets\artifacts\platform\three_d_runtime\references\d024\mandible_d024_0001.stl",
    "resources\runtime_assets\research\datasets\public-candidates\d036_toothfairy2\raw\Dataset112_ToothFairy2\imagesTr\ToothFairy2F_001_0000.mha"
)
$failures = New-Object System.Collections.Generic.List[string]

foreach ($relativePath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedRoot $relativePath) -PathType Leaf)) {
        $failures.Add("Missing required file: $relativePath")
    }
}

foreach ($file in @($manifest.files)) {
    $relativePath = [string]$file.path
    $path = Join-Path $resolvedRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failures.Add("Missing manifest file: $relativePath")
        continue
    }
    $actualLength = (Get-Item -LiteralPath $path).Length
    if ([int64]$file.bytes -ne [int64]$actualLength) {
        $failures.Add("Size mismatch: $relativePath")
        continue
    }
    $actualHash = Get-Sha256Hex -Path $path
    if ($actualHash -ne [string]$file.sha256) {
        $failures.Add("SHA256 mismatch: $relativePath")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host "Release verification passed: $resolvedRoot"
