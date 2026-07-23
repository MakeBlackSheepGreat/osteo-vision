param(
    [int]$BackendPort = 8001,
    [int]$RuntimePort = 5175,
    [string]$HostAddress = "127.0.0.1",
    [string]$ApiUrl = "",
    [string]$MainAppOrigin = "",
    [switch]$NoInstall,
    [switch]$NoBrowser,
    [switch]$Headless,
    [switch]$PreflightOnly,
    [switch]$SkipBackendCheck,
    [int]$StartupTimeoutSeconds = 40
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Test-TcpPort {
    param(
        [string]$Address,
        [int]$Port
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(500)
        if ($connected) {
            $client.EndConnect($async)
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-HttpEndpoint {
    param([string]$Uri)

    try {
        $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 5 -UseBasicParsing
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch {
        return $false
    }
}

function Test-RendererRuntime {
    param([string]$RuntimeUrl)

    try {
        $manifestUri = "$($RuntimeUrl.TrimEnd('/'))/runtime-manifest.json"
        $manifest = Invoke-RestMethod -Uri $manifestUri -Method Get -TimeoutSec 5
        return (
            $manifest.runtime_id -eq "osteo-vision-three-d-runtime" -and
            $manifest.bridge_protocol -eq "osteo-vision-three-d-runtime-bridge-v1" -and
            $manifest.snapshot_schema_version -eq "osteo-vision-three-d-runtime-snapshot-v2" -and
            $manifest.snapshot_integrity_protocol -eq "osteo-vision-three-d-runtime-integrity-v2"
        )
    }
    catch {
        return $false
    }
}

function Test-RuntimeInstanceConfiguration {
    param(
        [string]$ManifestPath,
        [string]$RuntimeUrl,
        [string]$ApiUrl,
        [string]$MainAppOrigin
    )

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        return $false
    }
    try {
        $instance = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        return (
            $instance.runtime_url -eq $RuntimeUrl.TrimEnd('/') -and
            $instance.api_url -eq $ApiUrl.TrimEnd('/') -and
            $instance.main_app_origin -eq $MainAppOrigin.TrimEnd('/') -and
            $instance.bridge_protocol -eq "osteo-vision-three-d-runtime-bridge-v1" -and
            $instance.snapshot_schema_version -eq "osteo-vision-three-d-runtime-snapshot-v2"
        )
    }
    catch {
        return $false
    }
}

function Write-RuntimeInstanceConfiguration {
    param(
        [string]$ManifestPath,
        [string]$RuntimeUrl,
        [string]$ApiUrl,
        [string]$MainAppOrigin
    )

    $directory = Split-Path -Parent $ManifestPath
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $payload = [ordered]@{
        runtime_id = "osteo-vision-three-d-runtime"
        runtime_url = $RuntimeUrl.TrimEnd('/')
        api_url = $ApiUrl.TrimEnd('/')
        main_app_origin = $MainAppOrigin.TrimEnd('/')
        bridge_protocol = "osteo-vision-three-d-runtime-bridge-v1"
        snapshot_schema_version = "osteo-vision-three-d-runtime-snapshot-v2"
        started_at = [DateTime]::UtcNow.ToString("o")
    }
    $temporaryPath = "$ManifestPath.part"
    $payload | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $ManifestPath -Force
}

function Test-RuntimeDependencies {
    param([string]$RuntimeDirectory)

    $requiredPackages = @(
        "node_modules\vue\package.json",
        "node_modules\three\package.json",
        "node_modules\vite\package.json",
        "node_modules\@vitejs\plugin-vue\package.json",
        "node_modules\vue-tsc\package.json"
    )
    return @($requiredPackages | Where-Object { -not (Test-Path -LiteralPath (Join-Path $RuntimeDirectory $_) -PathType Leaf) }).Count -eq 0
}

function Start-DevWindow {
    param(
        [string]$Title,
        [string]$Command,
        [string]$WorkingDirectory,
        [switch]$Headless
    )

    $wrapped = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location -LiteralPath '$WorkingDirectory'
$Command
"@

    $arguments = @(
        $(if (-not $Headless) { "-NoExit" }),
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $wrapped
    ) | Where-Object { $_ }
    $launch = @{
        FilePath = "powershell.exe"
        ArgumentList = $arguments
        WorkingDirectory = $WorkingDirectory
    }
    if ($Headless) {
        $launch.WindowStyle = "Hidden"
    }
    Start-Process @launch
}

if ($BackendPort -eq $RuntimePort) {
    throw "BackendPort and RuntimePort must use different values."
}
if ($StartupTimeoutSeconds -lt 1) {
    throw "StartupTimeoutSeconds must be at least 1."
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$runtimeDir = Join-Path $repoRoot "frontend\three-d-runtime"
$runtimePackage = Join-Path $runtimeDir "package.json"
$runtimeNodeModules = Join-Path $runtimeDir "node_modules"
$runtimeDependenciesReady = Test-RuntimeDependencies -RuntimeDirectory $runtimeDir
$resolvedApiUrl = if ($ApiUrl.Trim()) { $ApiUrl.Trim().TrimEnd("/") } else { "http://${HostAddress}:$BackendPort" }
$runtimeUrl = "http://${HostAddress}:$RuntimePort"
$resolvedMainAppOrigin = if ($MainAppOrigin.Trim()) { $MainAppOrigin.Trim().TrimEnd("/") } else { "http://${HostAddress}:5174" }
$runtimeInstanceManifest = Join-Path $repoRoot "artifacts\runtime_logs\three_d_runtime_$RuntimePort.json"

if (-not (Test-Path -LiteralPath $runtimePackage -PathType Leaf)) {
    throw "Missing independent renderer package: $runtimePackage"
}
try {
    $mainAppUri = [System.Uri]$resolvedMainAppOrigin
    if (-not $mainAppUri.IsAbsoluteUri -or $mainAppUri.Scheme -notin @("http", "https")) {
        throw "invalid scheme"
    }
    $resolvedMainAppOrigin = $mainAppUri.GetLeftPart([System.UriPartial]::Authority)
}
catch {
    throw "MainAppOrigin must be an http(s) origin when provided."
}
if ($RuntimePort -eq $mainAppUri.Port) {
    throw "RuntimePort must differ from the MainAppOrigin port."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js first, then rerun this script."
}

$backendCheckSkipped = [bool]$SkipBackendCheck
$backendReachable = if ($backendCheckSkipped) { $null } else { Test-HttpEndpoint -Uri "$resolvedApiUrl/health" }
if (-not $backendCheckSkipped -and -not $backendReachable) {
    throw "Backend health endpoint is unavailable at $resolvedApiUrl/health. Start the primary platform first or use -SkipBackendCheck for local launcher checks."
}

if ($PreflightOnly) {
    [pscustomobject]@{
        runtime_directory = $runtimeDir
        runtime_package = $runtimePackage
        api_url = $resolvedApiUrl
        runtime_url = $runtimeUrl
        main_app_origin = $resolvedMainAppOrigin
        runtime_instance_manifest = $runtimeInstanceManifest
        backend_reachable = $backendReachable
        backend_check_skipped = $backendCheckSkipped
        node_modules_present = (Test-Path -LiteralPath $runtimeNodeModules)
        runtime_dependencies_ready = $runtimeDependenciesReady
    } | ConvertTo-Json -Depth 3
    exit 0
}

if (-not $runtimeDependenciesReady) {
    if ($NoInstall) {
        throw "Independent runtime dependencies are incomplete under $runtimeNodeModules. Remove -NoInstall to run npm ci."
    }
    Write-Host "[setup] independent three-d runtime dependencies are incomplete. Running npm ci..."
    npm --prefix $runtimeDir ci
    if ($LASTEXITCODE -ne 0) {
        throw "npm install failed for $runtimeDir with exit code $LASTEXITCODE"
    }
    if (-not (Test-RuntimeDependencies -RuntimeDirectory $runtimeDir)) {
        throw "npm ci completed but the independent renderer dependencies are still incomplete under $runtimeNodeModules."
    }
}

if (Test-TcpPort -Address $HostAddress -Port $RuntimePort) {
    if (-not (Test-RendererRuntime -RuntimeUrl $runtimeUrl)) {
        throw "Port $RuntimePort is in use and does not expose the verified independent renderer runtime."
    }
    if (-not (Test-RuntimeInstanceConfiguration -ManifestPath $runtimeInstanceManifest -RuntimeUrl $runtimeUrl -ApiUrl $resolvedApiUrl -MainAppOrigin $resolvedMainAppOrigin)) {
        throw "Port $RuntimePort is in use, but its renderer configuration cannot be verified for the requested API URL and main-platform origin. Stop the existing runtime or choose a separate port."
    }
    Write-Host "[three-d-runtime] Reusing existing renderer at $runtimeUrl"
    if (-not $NoBrowser) {
        Start-Process $runtimeUrl
    }
    exit 0
}

$runtimeCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_THREE_D_RUNTIME_PORT = '$RuntimePort'
`$env:VITE_OSTEO_API_URL = '$resolvedApiUrl'
`$env:VITE_OSTEO_MAIN_APP_ORIGIN = '$resolvedMainAppOrigin'
npm --prefix "$runtimeDir" run dev -- --host $HostAddress --port $RuntimePort --strictPort
"@
Start-DevWindow -Title "Osteo Vision 3D Renderer :$RuntimePort" -Command $runtimeCommand -WorkingDirectory $repoRoot -Headless:$Headless

Write-Host "[wait] Waiting for independent renderer at $runtimeUrl ..."
for ($i = 0; $i -lt $StartupTimeoutSeconds; $i++) {
    if ((Test-TcpPort -Address $HostAddress -Port $RuntimePort) -and (Test-RendererRuntime -RuntimeUrl $runtimeUrl)) {
        Write-RuntimeInstanceConfiguration -ManifestPath $runtimeInstanceManifest -RuntimeUrl $runtimeUrl -ApiUrl $resolvedApiUrl -MainAppOrigin $resolvedMainAppOrigin
        Write-Host "[ready] Three-dimensional renderer: $runtimeUrl"
        if (-not $NoBrowser) {
            Start-Process $runtimeUrl
        }
        exit 0
    }
    Start-Sleep -Seconds 1
}

throw "Independent renderer did not respond within $StartupTimeoutSeconds seconds at $runtimeUrl."
