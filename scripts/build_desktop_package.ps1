param(
    [string]$CondaEnv = "osteo-vision",
    [switch]$SkipFrontendBuild,
    [switch]$SkipBackendBuild,
    [string]$ElectronArchive = "$env:LOCALAPPDATA\electron\Cache\electron-v28.3.3-win32-x64.zip"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$releaseRoot = Join-Path $repoRoot "artifacts\release\desktop"
$stagingRoot = Join-Path $releaseRoot "staging"
$backendDist = Join-Path $stagingRoot "backend"
$pyinstallerBackendDist = Join-Path $stagingRoot "osteo-vision-api"
$runtimeAssets = Join-Path $stagingRoot "runtime_assets"
$frontendStaging = Join-Path $stagingRoot "frontend"
$threeDRuntimeStaging = Join-Path $stagingRoot "three_d_runtime"
$desktopPackageRoot = Join-Path $releaseRoot "Osteo Vision Platform-win32-x64"

function Resolve-CondaPython {
    param([string]$EnvironmentName)
    $candidates = @()
    if ($env:CONDA_PREFIX -and (Split-Path -Leaf $env:CONDA_PREFIX) -eq $EnvironmentName) {
        $candidates += Join-Path $env:CONDA_PREFIX "python.exe"
    }
    if ($env:USERPROFILE) {
        $candidates += Join-Path $env:USERPROFILE ".conda\envs\$EnvironmentName\python.exe"
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $condaCommand = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaCommand) {
        $pythonPath = (& $condaCommand.Source run -n $EnvironmentName python -c "import sys; print(sys.executable)").Trim()
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            return $pythonPath
        }
    }
    throw "Unable to resolve Python for conda environment '$EnvironmentName'."
}

function Rewrite-PackagedMetadataPaths {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$DevelopmentRoot
    )

    # Training manifests and model cards are useful provenance evidence, but
    # their source paths must not bind a copied release to the build machine.
    $textExtensions = @(".json", ".csv", ".yml", ".yaml", ".md", ".txt")
    $variants = @(
        $DevelopmentRoot,
        $DevelopmentRoot.Replace("\", "/"),
        $DevelopmentRoot.Replace("\", "\\")
    ) | Select-Object -Unique
    $encoding = New-Object System.Text.UTF8Encoding($false)
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
        Where-Object { $textExtensions -contains $_.Extension.ToLowerInvariant() }) {
        $original = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
        $rewritten = $original
        foreach ($variant in $variants) {
            $pattern = [regex]::Escape($variant)
            $rewritten = [regex]::Replace(
                $rewritten,
                $pattern,
                "runtime_external_root",
                [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
            )
        }
        if ($rewritten -ne $original) {
            [System.IO.File]::WriteAllText($file.FullName, $rewritten, $encoding)
        }
    }
}

$python = Resolve-CondaPython -EnvironmentName $CondaEnv
$condaEnvironmentRoot = Split-Path -Parent $python
$ffmpegRuntimeSource = Join-Path $condaEnvironmentRoot "Library\bin"
$ffmpegRuntimeFiles = @(
    "ffmpeg.exe", "ffprobe.exe", "aom.dll", "avcodec-62.dll", "avdevice-62.dll", "avfilter-11.dll",
    "avformat-62.dll", "avutil-60.dll", "brotlicommon.dll", "brotlidec.dll", "brotlienc.dll", "cairo.dll",
    "charset.dll", "dav1d.dll", "ffi-8.dll", "fontconfig-1.dll", "freetype.dll", "fribidi-0.dll",
    "gdk_pixbuf-2.0-0.dll", "gio-2.0-0.dll", "glib-2.0-0.dll", "gmodule-2.0-0.dll", "gobject-2.0-0.dll",
    "graphite2.dll", "harfbuzz.dll", "hwy.dll", "iconv.dll", "icudt78.dll", "icuuc78.dll", "intl-8.dll",
    "jpeg8.dll", "jxl.dll", "jxl_cms.dll", "jxl_threads.dll", "libbz2.dll", "libcrypto-3-x64.dll",
    "libexpat.dll", "liblzma.dll", "libmp3lame.dll", "libpng16.dll", "libsharpyuv.dll", "libssl-3-x64.dll",
    "libwebp.dll", "libwebpmux.dll", "libx264-164.dll", "libx265.dll", "libxml2.dll", "msvcp140.dll",
    "ogg.dll", "openh264-7.dll", "opus.dll", "pango-1.0-0.dll", "pangocairo-1.0-0.dll", "pangoft2-1.0-0.dll",
    "pangowin32-1.0-0.dll", "pcre2-8.dll", "pixman-1-0.dll", "rsvg-2-2.dll", "shaderc.dll", "svtav1enc.dll",
    "swresample-6.dll", "swscale-9.dll", "vcruntime140.dll", "vcruntime140_1.dll", "vorbis.dll", "zlib.dll"
)

& $python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) { throw "PyInstaller is missing. Run: conda run -n $CondaEnv python -m pip install pyinstaller" }

if (-not $SkipFrontendBuild) {
    $previousDesktop = $env:VITE_OSTEO_DESKTOP
    $previousApiUrl = $env:VITE_OSTEO_API_URL
    $previousStrictRuntime = $env:VITE_OSTEO_EXPECT_STRICT_RUNTIME
    $env:VITE_OSTEO_DESKTOP = "true"
    $env:VITE_OSTEO_API_URL = "http://127.0.0.1:8001"
    $env:VITE_OSTEO_EXPECT_STRICT_RUNTIME = "true"
    try {
        npm --prefix (Join-Path $repoRoot "frontend") run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
    }
    finally {
        $env:VITE_OSTEO_DESKTOP = $previousDesktop
        $env:VITE_OSTEO_API_URL = $previousApiUrl
        $env:VITE_OSTEO_EXPECT_STRICT_RUNTIME = $previousStrictRuntime
    }
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
if (-not $SkipBackendBuild) {
    foreach ($staleBackendPath in @($backendDist, $pyinstallerBackendDist)) {
        if (Test-Path -LiteralPath $staleBackendPath) {
            Remove-Item -LiteralPath $staleBackendPath -Recurse -Force
        }
    }
    & $python -m PyInstaller --noconfirm --clean --onedir --name "osteo-vision-api" --paths $repoRoot --distpath $stagingRoot --workpath (Join-Path $releaseRoot "pyinstaller-work") --specpath (Join-Path $releaseRoot "pyinstaller-spec") (Join-Path $repoRoot "backend\osteo_vision_api\main.py")
    if ($LASTEXITCODE -ne 0) { throw "Backend executable build failed." }
}

if (-not (Test-Path -LiteralPath $backendDist -PathType Container) -and (Test-Path -LiteralPath $pyinstallerBackendDist -PathType Container)) {
    Move-Item -LiteralPath $pyinstallerBackendDist -Destination $backendDist
}

if (-not (Test-Path -LiteralPath (Join-Path $backendDist "osteo-vision-api.exe") -PathType Leaf)) {
    throw "Packaged backend is missing: $(Join-Path $backendDist 'osteo-vision-api.exe')"
}

$threeDRuntimeRoot = Join-Path $repoRoot "frontend\three-d-runtime"
if (-not (Test-Path -LiteralPath (Join-Path $threeDRuntimeRoot "package.json") -PathType Leaf)) {
    throw "Three-dimensional runtime project is missing: $threeDRuntimeRoot"
}
npm --prefix $threeDRuntimeRoot run build
if ($LASTEXITCODE -ne 0) { throw "Three-dimensional runtime production build failed." }
$builderHasCuda = (& $python -c "import torch; print(int(torch.version.cuda is not None))").Trim()
$packagedCudaLibraries = @(Get-ChildItem -LiteralPath $backendDist -Recurse -File -Filter "torch_cuda.dll" -ErrorAction SilentlyContinue)
if ($builderHasCuda -eq "1" -and $packagedCudaLibraries.Count -eq 0) {
    throw "CUDA-enabled Torch was used for the build, but torch_cuda.dll is missing from the packaged backend."
}
if ($packagedCudaLibraries.Count -gt 0) {
    Write-Host "Packaged CUDA acceleration runtime: $($packagedCudaLibraries[0].FullName)"
}
else {
    Write-Warning "CUDA runtime is not bundled. The packaged application will use the CPU fallback path."
}

Remove-Item -LiteralPath $runtimeAssets -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $runtimeAssets | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "configs") -Destination (Join-Path $runtimeAssets "configs") -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeAssets "artifacts") | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "artifacts\checkpoints") -Destination (Join-Path $runtimeAssets "artifacts\checkpoints") -Recurse -Force
$developmentRoot = (Resolve-Path -LiteralPath $repoRoot).Path
Rewrite-PackagedMetadataPaths -Root $runtimeAssets -DevelopmentRoot $developmentRoot
$runtimeTools = Join-Path $runtimeAssets "runtime_tools"
New-Item -ItemType Directory -Force -Path $runtimeTools | Out-Null
foreach ($fileName in $ffmpegRuntimeFiles) {
    $source = Join-Path $ffmpegRuntimeSource $fileName
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required FFmpeg runtime file is missing: $source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $runtimeTools $fileName) -Force
}
$inventorySource = Join-Path $repoRoot "research\literature\inventory"
if (Test-Path -LiteralPath $inventorySource) {
    # Development inventory manifests contain absolute paths to datasets that are
    # intentionally not shipped. Copy only descriptive inventory files; the
    # runtime video manifests are supplied below from the portable demo_data tree.
    $runtimeInventory = Join-Path $runtimeAssets "research\literature\inventory"
    New-Item -ItemType Directory -Force -Path $runtimeInventory | Out-Null
    $developmentPathManifests = @(
        "ofdvdnet_fluorescence_baseline_manifest_20260704.csv",
        "ofdvdnet_video_manifest_20260704.csv",
        "video_download_manifest_20260703.csv",
        "video_library_manifest_20260704.csv"
    )
    Get-ChildItem -LiteralPath $inventorySource -File -Force |
        Where-Object { $developmentPathManifests -notcontains $_.Name } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $runtimeInventory $_.Name) -Force
        }
}

$demoDataRoot = Join-Path $runtimeAssets "demo_data"
$demoOfdvdRoot = Join-Path $demoDataRoot "ofdvdnet"
$demoOfdvdVideoSource = Join-Path $repoRoot "research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\raw\fluorescence_proxy\ofdvdnet_dryad_v6wwpzh3w\extracted\OL-2021-07-20-121707-000004-record.mp4"
$demoOfdvdManifestSource = Join-Path $repoRoot "packaging\desktop\demo_ofdvdnet_manifest.csv"
$demoOfdvdPreviewSource = Join-Path $repoRoot "research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\ofdvdnet\previews"
$demoD024Source = Join-Path $repoRoot "artifacts\platform\three_d_runtime\references\d024"
$demoD024Destination = Join-Path $runtimeAssets "artifacts\platform\three_d_runtime\references\d024"
$demoD036Root = Join-Path $runtimeAssets "research\datasets\public-candidates\d036_toothfairy2\raw\Dataset112_ToothFairy2"
$demoD036ImagesSource = Join-Path $repoRoot "research\datasets\public-candidates\d036_toothfairy2\raw\Dataset112_ToothFairy2\imagesTr\ToothFairy2F_001_0000.mha"
$demoSources = @(
    $demoOfdvdVideoSource,
    $demoOfdvdManifestSource,
    $demoD024Source,
    (Join-Path $demoOfdvdPreviewSource "OFDVDNET_001_full.jpg"),
    (Join-Path $demoOfdvdPreviewSource "OFDVDNET_001_overlay.jpg"),
    (Join-Path $demoOfdvdPreviewSource "OFDVDNET_001_fluorescence.jpg"),
    (Join-Path $demoOfdvdPreviewSource "OFDVDNET_001_reference.jpg"),
    (Join-Path $demoD024Source "mandible_d024_0001.stl"),
    (Join-Path $demoD024Source "mandible_d024_0001.brp_geometry_manifest.json"),
    (Join-Path $demoD024Source "mandible_d024_0001.three_d_evidence.json"),
    $demoD036ImagesSource
)
foreach ($source in $demoSources) {
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Required packaged demonstration asset is missing: $source"
    }
}
New-Item -ItemType Directory -Force -Path (Join-Path $demoOfdvdRoot "video") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $demoOfdvdRoot "previews") | Out-Null
New-Item -ItemType Directory -Force -Path $demoD024Destination | Out-Null
Copy-Item -LiteralPath $demoOfdvdVideoSource -Destination (Join-Path $demoOfdvdRoot "video\OFDVDNET_001.mp4") -Force
Copy-Item -LiteralPath $demoOfdvdManifestSource -Destination (Join-Path $demoOfdvdRoot "ofdvdnet_demo_manifest.csv") -Force
foreach ($previewName in @("OFDVDNET_001_full.jpg", "OFDVDNET_001_overlay.jpg", "OFDVDNET_001_fluorescence.jpg", "OFDVDNET_001_reference.jpg")) {
    Copy-Item -LiteralPath (Join-Path $demoOfdvdPreviewSource $previewName) -Destination (Join-Path $demoOfdvdRoot "previews\$previewName") -Force
}
Copy-Item -LiteralPath (Join-Path $demoD024Source "mandible_d024_0001.stl") -Destination (Join-Path $demoD024Destination "mandible_d024_0001.stl") -Force
Copy-Item -LiteralPath (Join-Path $demoD024Source "mandible_d024_0001.brp_geometry_manifest.json") -Destination (Join-Path $demoD024Destination "mandible_d024_0001.brp_geometry_manifest.json") -Force
Copy-Item -LiteralPath (Join-Path $demoD024Source "mandible_d024_0001.three_d_evidence.json") -Destination (Join-Path $demoD024Destination "mandible_d024_0001.three_d_evidence.json") -Force
New-Item -ItemType Directory -Force -Path (Join-Path $demoD036Root "imagesTr") | Out-Null
Copy-Item -LiteralPath $demoD036ImagesSource -Destination (Join-Path $demoD036Root "imagesTr\ToothFairy2F_001_0000.mha") -Force

Remove-Item -LiteralPath $frontendStaging -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $repoRoot "frontend\dist") -Destination $frontendStaging -Recurse -Force
Remove-Item -LiteralPath $threeDRuntimeStaging -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $threeDRuntimeRoot "dist") -Destination $threeDRuntimeStaging -Recurse -Force

if (-not (Test-Path -LiteralPath $ElectronArchive -PathType Leaf)) {
    throw "Electron runtime archive is missing: $ElectronArchive"
}
Remove-Item -LiteralPath $desktopPackageRoot -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $ElectronArchive -DestinationPath $desktopPackageRoot -Force
$desktopResources = Join-Path $desktopPackageRoot "resources"
$desktopApp = Join-Path $desktopResources "app"
New-Item -ItemType Directory -Force -Path $desktopApp | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\desktop\main.cjs") -Destination (Join-Path $desktopApp "main.cjs") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\desktop\desktopLifecycle.cjs") -Destination (Join-Path $desktopApp "desktopLifecycle.cjs") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\desktop\runtimeSupervisor.cjs") -Destination (Join-Path $desktopApp "runtimeSupervisor.cjs") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\desktop\desktopPermissions.cjs") -Destination (Join-Path $desktopApp "desktopPermissions.cjs") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\desktop\runtimeServer.cjs") -Destination (Join-Path $desktopApp "runtimeServer.cjs") -Force
@'
{
  "name": "osteo-vision-desktop",
  "version": "0.3.0-rc.2",
  "main": "main.cjs"
}
'@ | Set-Content -LiteralPath (Join-Path $desktopApp "package.json") -Encoding utf8
Copy-Item -LiteralPath $backendDist -Destination (Join-Path $desktopResources "backend") -Recurse -Force
Copy-Item -LiteralPath $runtimeAssets -Destination (Join-Path $desktopResources "runtime_assets") -Recurse -Force
Copy-Item -LiteralPath $frontendStaging -Destination (Join-Path $desktopResources "frontend") -Recurse -Force
Copy-Item -LiteralPath $threeDRuntimeStaging -Destination (Join-Path $desktopResources "three_d_runtime") -Recurse -Force
$electronExecutable = Join-Path $desktopPackageRoot "electron.exe"
if (-not (Test-Path -LiteralPath $electronExecutable -PathType Leaf)) {
    throw "Extracted Electron executable is missing: $electronExecutable"
}
Rename-Item -LiteralPath $electronExecutable -NewName "Osteo Vision Platform.exe"

Write-Host "Desktop package created at $desktopPackageRoot"
