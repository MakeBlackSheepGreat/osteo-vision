param(
    [string]$PackageRoot = "artifacts\release\competition-disc\Osteo-Vision-Competition-Disc-win32-x64-20260831-r28",
    [string]$ArchivePath = "artifacts\release\competition-disc\Osteo-Vision-Competition-Disc-win32-x64-20260831-r28.zip",
    [string]$ExtractRoot = "output\portability\r28-other-computer",
    [int]$TimeoutMs = 600000,
    [switch]$SkipRealTest
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$resolvedPackageRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot $PackageRoot)).Path
$resolvedArchivePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ArchivePath))
$resolvedExtractRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ExtractRoot))
$packageName = Split-Path -Leaf $resolvedPackageRoot
$extractedPackageRoot = Join-Path $resolvedExtractRoot $packageName
$resultPath = Join-Path $resolvedExtractRoot "portability-result.json"
$textExtensions = @(".json", ".csv", ".yml", ".yaml", ".md", ".html", ".js", ".cjs", ".css", ".txt")
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

function Invoke-ReleaseVerification {
    param([Parameter(Mandatory)][string]$Root)
    $verify = Join-Path $Root "verify_release.ps1"
    if (-not (Test-Path -LiteralPath $verify -PathType Leaf)) {
        throw "发行包校验脚本不存在：$verify"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify -PackageRoot $Root
    if ($LASTEXITCODE -ne 0) { throw "发行包完整性校验失败：$Root" }
}

function New-ZipArchiveWithRootPrefix {
    param(
        [Parameter(Mandatory)][string]$SourceRoot,
        [Parameter(Mandatory)][string]$Destination
    )
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $parent = Split-Path -Parent $SourceRoot
    $rootName = Split-Path -Leaf $SourceRoot
    $archive = [System.IO.Compression.ZipFile]::Open($Destination, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $files = @(Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Force)
        $copied = 0
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($parent.Length + 1).Replace("\", "/")
            $entry = $archive.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
            $input = $null
            $output = $null
            try {
                $input = [System.IO.File]::OpenRead($file.FullName)
                $output = $entry.Open()
                $input.CopyTo($output)
            }
            finally {
                if ($output) { $output.Dispose() }
                if ($input) { $input.Dispose() }
            }
            $copied += 1
            if (($copied % 250) -eq 0) {
                Write-Host "已归档文件：$copied / $($files.Count)"
            }
        }
        return $copied
    }
    finally {
        $archive.Dispose()
    }
}

function Test-NoDevelopmentAbsolutePaths {
    param([Parameter(Mandatory)][string]$Root)
    $forbidden = @(
        $repoRoot,
        $repoRoot.Replace("\", "/"),
        $repoRoot.Replace("\", "\\"),
        "C:\Users\876762330\Desktop\projects\osteo-vision",
        "C:/Users/876762330/Desktop/projects/osteo-vision",
        "C:\\Users\\876762330\\Desktop\\projects\\osteo-vision"
    ) | Select-Object -Unique
    $matches = New-Object System.Collections.Generic.List[string]
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object { $textExtensions -contains $_.Extension.ToLowerInvariant() }) {
        foreach ($needle in $forbidden) {
            $found = Select-String -LiteralPath $file.FullName -SimpleMatch $needle -Quiet -ErrorAction SilentlyContinue
            if ($found) {
                $relative = $file.FullName.Substring($Root.Length + 1)
                $matches.Add($relative)
                break
            }
        }
    }
    return @($matches | Select-Object -Unique)
}

if (-not (Test-Path -LiteralPath (Join-Path $resolvedPackageRoot "Osteo Vision Platform.exe") -PathType Leaf)) {
    throw "发行包入口不存在：$resolvedPackageRoot"
}
Invoke-ReleaseVerification -Root $resolvedPackageRoot

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedArchivePath) | Out-Null
if (Test-Path -LiteralPath $resolvedArchivePath) {
    Remove-Item -LiteralPath $resolvedArchivePath -Force
}
if (Test-Path -LiteralPath $resolvedExtractRoot) {
    Remove-Item -LiteralPath $resolvedExtractRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $resolvedExtractRoot | Out-Null

$sourceFiles = @(Get-ChildItem -LiteralPath $resolvedPackageRoot -Recurse -File -Force)
$sourceBytes = [int64](($sourceFiles | Measure-Object -Property Length -Sum).Sum)
$archivedCount = New-ZipArchiveWithRootPrefix -SourceRoot $resolvedPackageRoot -Destination $resolvedArchivePath
$archiveItem = Get-Item -LiteralPath $resolvedArchivePath
Write-Host "ZIP 已创建：$resolvedArchivePath"
Write-Host "ZIP 大小：$($archiveItem.Length) bytes；源文件：$($sourceFiles.Count)；归档文件：$archivedCount"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($resolvedArchivePath, $resolvedExtractRoot)
if (-not (Test-Path -LiteralPath $extractedPackageRoot -PathType Container)) {
    throw "ZIP 解压后缺少根目录：$extractedPackageRoot"
}
Invoke-ReleaseVerification -Root $extractedPackageRoot

$externalPathMatches = @(Test-NoDevelopmentAbsolutePaths -Root $extractedPackageRoot)
if ($externalPathMatches.Count -gt 0) {
    throw "解压包包含开发机绝对路径：$($externalPathMatches -join ', ')"
}

$extractedFiles = @(Get-ChildItem -LiteralPath $extractedPackageRoot -Recurse -File -Force)
$extractedBytes = [int64](($extractedFiles | Measure-Object -Property Length -Sum).Sum)
if ($sourceFiles.Count -ne $extractedFiles.Count -or $sourceBytes -ne $extractedBytes) {
    throw "解压后文件数量或总字节数不一致：源 $($sourceFiles.Count)/$sourceBytes，解压 $($extractedFiles.Count)/$extractedBytes"
}

$realTestResult = $null
if (-not $SkipRealTest) {
    $testScript = Join-Path $repoRoot "frontend\e2e\intake-case.real.mjs"
    & node.exe $testScript --package-root $extractedPackageRoot --timeout-ms $TimeoutMs
    if ($LASTEXITCODE -ne 0) { throw "解压迁移包专项真实测试失败。" }
    $latest = Get-ChildItem -LiteralPath (Join-Path $repoRoot "output\playwright\intake-case-real-test") -Directory |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        $candidate = Join-Path $latest.FullName "result.json"
        if (Test-Path -LiteralPath $candidate) {
            $realTestResult = Get-Content -LiteralPath $candidate -Raw -Encoding utf8 | ConvertFrom-Json
        }
    }
}

$stopwatch.Stop()
$result = [ordered]@{
    status = "passed"
    package_root = $resolvedPackageRoot
    archive_path = $resolvedArchivePath
    archive_sha256 = (Get-FileHash -LiteralPath $resolvedArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    archive_bytes = [int64]$archiveItem.Length
    source_file_count = $sourceFiles.Count
    source_bytes = $sourceBytes
    extracted_root = $extractedPackageRoot
    extracted_file_count = $extractedFiles.Count
    extracted_bytes = $extractedBytes
    development_absolute_path_matches = @($externalPathMatches)
    real_test = if ($realTestResult) { $realTestResult } else { @{ status = "skipped" } }
    elapsed_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding utf8
Write-Host "迁移包校验通过：$resultPath"
Write-Host "归档 SHA256：$($result.archive_sha256)"
