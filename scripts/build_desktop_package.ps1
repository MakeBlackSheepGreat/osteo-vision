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
    $env:VITE_OSTEO_DESKTOP = "true"
    $env:VITE_OSTEO_API_URL = "http://127.0.0.1:8001"
    try {
        npm --prefix (Join-Path $repoRoot "frontend") run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
    }
    finally {
        $env:VITE_OSTEO_DESKTOP = $previousDesktop
        $env:VITE_OSTEO_API_URL = $previousApiUrl
    }
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
if (-not $SkipBackendBuild) {
    & $python -m PyInstaller --noconfirm --clean --onedir --name "osteo-vision-api" --paths $repoRoot --distpath $stagingRoot --workpath (Join-Path $releaseRoot "pyinstaller-work") --specpath (Join-Path $releaseRoot "pyinstaller-spec") (Join-Path $repoRoot "backend\osteo_vision_api\main.py")
    if ($LASTEXITCODE -ne 0) { throw "Backend executable build failed." }
}

if (-not (Test-Path -LiteralPath $backendDist -PathType Container) -and (Test-Path -LiteralPath $pyinstallerBackendDist -PathType Container)) {
    Move-Item -LiteralPath $pyinstallerBackendDist -Destination $backendDist
}

if (-not (Test-Path -LiteralPath (Join-Path $backendDist "osteo-vision-api.exe") -PathType Leaf)) {
    throw "Packaged backend is missing: $(Join-Path $backendDist 'osteo-vision-api.exe')"
}

Remove-Item -LiteralPath $runtimeAssets -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $runtimeAssets | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "configs") -Destination (Join-Path $runtimeAssets "configs") -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeAssets "artifacts") | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "artifacts\checkpoints") -Destination (Join-Path $runtimeAssets "artifacts\checkpoints") -Recurse -Force
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
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeAssets "research\literature") | Out-Null
    Copy-Item -LiteralPath $inventorySource -Destination (Join-Path $runtimeAssets "research\literature\inventory") -Recurse -Force
}

Remove-Item -LiteralPath $frontendStaging -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $repoRoot "frontend\dist") -Destination $frontendStaging -Recurse -Force

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
$electronExecutable = Join-Path $desktopPackageRoot "electron.exe"
if (-not (Test-Path -LiteralPath $electronExecutable -PathType Leaf)) {
    throw "Extracted Electron executable is missing: $electronExecutable"
}
Rename-Item -LiteralPath $electronExecutable -NewName "Osteo Vision Platform.exe"

Write-Host "Desktop package created at $desktopPackageRoot"
