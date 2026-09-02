param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5174,
    [int]$ThreeDRuntimePort = 5175,
    [string]$HostAddress = "127.0.0.1",
    [string]$CondaEnv = "osteo-vision",
    [string]$InferenceConfig = "configs/inference/osteo_vision.yml",
    [switch]$StrictRuntime,
    [switch]$PreflightOnly,
    [switch]$NoInstall,
    [switch]$NoBrowser,
    [switch]$Headless,
    [switch]$StartThreeDRuntime,
    [switch]$SkipThreeDRuntime
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

function Resolve-CondaEnvironmentPython {
    param(
        [string]$EnvironmentName
    )

    if (-not $EnvironmentName) {
        return $null
    }

    $candidatePaths = New-Object System.Collections.Generic.List[string]
    if ($env:CONDA_PREFIX -and (Split-Path -Leaf $env:CONDA_PREFIX) -eq $EnvironmentName) {
        $candidatePaths.Add((Join-Path $env:CONDA_PREFIX "python.exe"))
    }
    if ($env:USERPROFILE) {
        $candidatePaths.Add((Join-Path $env:USERPROFILE ".conda\envs\$EnvironmentName\python.exe"))
    }
    if ($env:CONDA_ENVS_PATH) {
        foreach ($envRoot in ($env:CONDA_ENVS_PATH -split [System.IO.Path]::PathSeparator)) {
            if ($envRoot) {
                $candidatePaths.Add((Join-Path $envRoot "$EnvironmentName\python.exe"))
            }
        }
    }

    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda) {
        try {
            $environmentList = (& conda env list --json 2>$null | ConvertFrom-Json).envs
            foreach ($environmentPath in @($environmentList)) {
                if ((Split-Path -Leaf $environmentPath) -eq $EnvironmentName) {
                    $candidatePaths.Add((Join-Path $environmentPath "python.exe"))
                }
            }
        }
        catch {
            Write-Verbose "Unable to query conda environment paths: $($_.Exception.Message)"
        }
    }

    foreach ($candidate in $candidatePaths | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
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

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$frontendDir = Join-Path $repoRoot "frontend"
$threeDRuntimeDir = Join-Path $frontendDir "three-d-runtime"
$threeDRuntimeLauncher = Join-Path $scriptRoot "start_three_d_runtime.ps1"
$backendEntry = Join-Path $repoRoot "backend\osteo_vision_api\main.py"
$runtimeCheck = Join-Path $repoRoot "tools\check_runtime_readiness.py"
$runtimePorts = @($BackendPort, $FrontendPort, $ThreeDRuntimePort)
if (($runtimePorts | Select-Object -Unique).Count -ne 3) {
    throw "BackendPort, FrontendPort and ThreeDRuntimePort must use three different values."
}
if ($StartThreeDRuntime -and $SkipThreeDRuntime) {
    throw "StartThreeDRuntime and SkipThreeDRuntime cannot be used together."
}
if ($StrictRuntime) {
    $InferenceConfig = "configs/inference/osteo_vision_strict.yml"
}
$inferenceConfigPath = if ([System.IO.Path]::IsPathRooted($InferenceConfig)) {
    (Resolve-Path -LiteralPath $InferenceConfig).Path
}
else {
    (Resolve-Path -LiteralPath (Join-Path $repoRoot $InferenceConfig)).Path
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "package.json"))) {
    throw "Missing frontend/package.json under $repoRoot"
}
if (-not (Test-Path -LiteralPath $backendEntry)) {
    throw "Missing backend/osteo_vision_api/main.py under $repoRoot"
}
if (-not (Test-Path -LiteralPath $runtimeCheck)) {
    throw "Missing tools/check_runtime_readiness.py under $repoRoot"
}

$projectPython = Resolve-CondaEnvironmentPython -EnvironmentName $CondaEnv
if (-not $projectPython) {
    throw "Python for conda environment '$CondaEnv' was not found. Expected the dedicated osteo-vision environment."
}
$preflightArguments = @($runtimeCheck, "--config", $inferenceConfigPath)
if ($StrictRuntime) {
    $preflightArguments += "--require-strict"
}
$preflightRaw = & $projectPython @preflightArguments 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Runtime preflight failed for $inferenceConfigPath`n$($preflightRaw -join [Environment]::NewLine)"
}
$preflight = ($preflightRaw -join [Environment]::NewLine) | ConvertFrom-Json
if ($PreflightOnly) {
    $preflight | ConvertTo-Json -Depth 8
    exit 0
}

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
    throw "npm was not found. Install Node.js first, then rerun this script."
}

if (-not $NoInstall -and -not (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[setup] frontend/node_modules missing. Running npm install..."
    npm --prefix $frontendDir install
}

$allowedOrigins = "http://localhost:$FrontendPort,http://${HostAddress}:$FrontendPort,http://localhost:$ThreeDRuntimePort,http://${HostAddress}:$ThreeDRuntimePort"
$apiUrl = "http://${HostAddress}:$BackendPort"
$frontendUrl = "http://${HostAddress}:$FrontendPort"
$threeDRuntimeUrl = "http://${HostAddress}:$ThreeDRuntimePort"
$expectStrictRuntime = if ($StrictRuntime) { "true" } else { "false" }
$platformArtifactRoot = Join-Path $repoRoot "artifacts\platform_platform"
$platformCaseStore = Join-Path $platformArtifactRoot "cases.sqlite"
$platformJobStore = Join-Path $platformArtifactRoot "jobs\jobs.json"

$backendRunning = Test-TcpPort -Address $HostAddress -Port $BackendPort
$frontendRunning = Test-TcpPort -Address $HostAddress -Port $FrontendPort

if ($backendRunning) {
    try {
        $existingReady = Invoke-RestMethod -Uri "$apiUrl/ready" -Method Get
        $existingOpenApi = Invoke-RestMethod -Uri "$apiUrl/openapi.json" -Method Get
    }
    catch {
        throw "Existing backend on port $BackendPort could not be verified. Stop it and restart with this launcher."
    }
    if (-not $existingReady.runtime_readiness) {
        throw "Existing backend on port $BackendPort does not expose runtime readiness. Restart it with this launcher."
    }
    if ($existingReady.runtime_readiness.config_sha256 -ne $preflight.config_sha256) {
        throw "Existing backend runtime config does not match $inferenceConfigPath. Stop the old backend before starting."
    }
    if ($StrictRuntime -and [System.IO.Path]::GetFullPath([string]$existingReady.storage) -ne [System.IO.Path]::GetFullPath($platformCaseStore)) {
        throw "Existing strict backend does not use the isolated platform case store. Stop it before starting."
    }
    $liveFrameRoute = "/cases/{case_id}/live-frames"
    $existingRoutes = @($existingOpenApi.paths.psobject.Properties.Name)
    if ($existingRoutes -notcontains $liveFrameRoute) {
        throw "Existing backend on port $BackendPort is an older build and lacks $liveFrameRoute. Stop it, then restart with this launcher."
    }
    Write-Host "[backend] Reusing verified backend profile $($preflight.runtime_profile) on port $BackendPort."
}
else {
    $backendRun = "& '$projectPython' -m backend.osteo_vision_api.main"
    $backendCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_FRONTEND_PORT = '$FrontendPort'
`$env:OSTEO_ALLOWED_ORIGINS = '$allowedOrigins'
`$env:OSTEO_INFERENCE_CONFIG = '$inferenceConfigPath'
$(if ($StrictRuntime) { "`$env:OSTEO_ARTIFACT_ROOT = '$platformArtifactRoot'`n`$env:OSTEO_CASE_STORE_PATH = '$platformCaseStore'`n`$env:OSTEO_JOB_STORE_PATH = '$platformJobStore'" })
$backendRun
"@
    Start-DevWindow -Title "Osteo Vision Backend :$BackendPort" -Command $backendCommand -WorkingDirectory $repoRoot -Headless:$Headless
}

Write-Host "[wait] Waiting for backend readiness at $apiUrl/ready ..."
$backendVerified = $false
$backendFailure = "Backend port $BackendPort is not listening."
for ($i = 0; $i -lt 60; $i++) {
    if (Test-TcpPort -Address $HostAddress -Port $BackendPort) {
        try {
            $ready = Invoke-RestMethod -Uri "$apiUrl/ready" -Method Get -TimeoutSec 5
            $openApi = Invoke-RestMethod -Uri "$apiUrl/openapi.json" -Method Get -TimeoutSec 5
            $routes = @($openApi.paths.psobject.Properties.Name)
            if (-not $ready.runtime_readiness -or -not $ready.runtime_readiness.passed) {
                $backendFailure = "Backend runtime readiness did not pass."
            }
            elseif ($ready.runtime_readiness.config_sha256 -ne $preflight.config_sha256) {
                $backendFailure = "Backend runtime config does not match $inferenceConfigPath."
            }
            elseif ($StrictRuntime -and [System.IO.Path]::GetFullPath([string]$ready.storage) -ne [System.IO.Path]::GetFullPath($platformCaseStore)) {
                $backendFailure = "Strict backend storage does not match $platformCaseStore."
            }
            elseif ($routes -notcontains "/cases/{case_id}/live-frames") {
                $backendFailure = "Backend is missing the live-frame analysis route."
            }
            else {
                $backendVerified = $true
                break
            }
        }
        catch {
            $backendFailure = $_.Exception.Message
        }
    }
    Start-Sleep -Seconds 1
}
if (-not $backendVerified) {
    throw "Backend failed to become ready at $apiUrl. $backendFailure"
}
Write-Host "[ready] Backend:  $apiUrl"

Write-Host "[wait] Preparing the standard demonstration case..."
try {
    $standardDemoCase = Invoke-RestMethod -Uri "$apiUrl/platform/standard-demo-case" -Method Post -TimeoutSec 180
    if (-not $standardDemoCase.case_id) {
        throw "Standard demonstration case API returned no case identifier."
    }
    $standardDemoCaseId = [string]$standardDemoCase.case_id
    Write-Host "[ready] Standard case: $standardDemoCaseId"
}
catch {
    throw "Standard demonstration case preparation failed. $($_.Exception.Message)"
}

Write-Host "[wait] Warming up the configured segmentation model..."
try {
    $warmup = Invoke-RestMethod `
        -Uri "$apiUrl/live-frames/warmup" `
        -Method Post `
        -ContentType "application/json" `
        -Body "{}" `
        -TimeoutSec 120
}
catch {
    throw "Configured segmentation model warmup failed. $($_.Exception.Message)"
}
if (-not $warmup.available) {
    throw "Configured segmentation model warmup reported unavailable for model '$($warmup.model_id)'."
}
$requiredModelIds = @($preflight.required_model_ids)
if ($requiredModelIds.Count -gt 0 -and $requiredModelIds -notcontains [string]$warmup.model_id) {
    throw "Warmup loaded model '$($warmup.model_id)', which is outside the verified runtime model set."
}
Write-Host "[ready] Model:    $($warmup.model_id)"

if ($frontendRunning) {
    Write-Host "[frontend] Port $FrontendPort is already in use. Reusing existing service."
}
else {
    $frontendCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_FRONTEND_PORT = '$FrontendPort'
`$env:VITE_OSTEO_API_URL = '$apiUrl'
`$env:VITE_OSTEO_THREE_D_RUNTIME_URL = '$threeDRuntimeUrl'
`$env:VITE_OSTEO_EXPECT_STRICT_RUNTIME = '$expectStrictRuntime'
`$env:VITE_OSTEO_DEFAULT_CASE_ID = '$standardDemoCaseId'
npm --prefix "$frontendDir" run dev -- --host $HostAddress --port $FrontendPort --strictPort
"@
    Start-DevWindow -Title "Osteo Vision Frontend :$FrontendPort" -Command $frontendCommand -WorkingDirectory $repoRoot -Headless:$Headless
}

Write-Host "[wait] Waiting for frontend at $frontendUrl ..."
$frontendReady = $false
for ($i = 0; $i -lt 40; $i++) {
    if (Test-TcpPort -Address $HostAddress -Port $FrontendPort) {
        Write-Host "[ready] Frontend: $frontendUrl"
        $frontendReady = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $frontendReady) {
    Write-Host "[warn] Frontend did not respond within 40 seconds. Check the frontend terminal window."
    Write-Host "[info] Expected frontend URL: $frontendUrl"
    exit 1
}

if (-not $SkipThreeDRuntime) {
    Write-Host "[three-d-runtime] Starting independent renderer on port $ThreeDRuntimePort..."
    try {
        if (-not (Test-Path -LiteralPath $threeDRuntimeDir)) {
            throw "Runtime directory is missing: $threeDRuntimeDir"
        }
        if (-not (Test-Path -LiteralPath $threeDRuntimeLauncher -PathType Leaf)) {
            throw "Runtime launcher is missing: $threeDRuntimeLauncher"
        }

        $threeDRuntimeArguments = @{
            BackendPort = $BackendPort
            RuntimePort = $ThreeDRuntimePort
            HostAddress = $HostAddress
            MainAppOrigin = $frontendUrl
            NoBrowser = $true
        }
        if ($NoInstall) {
            $threeDRuntimeArguments.NoInstall = $true
        }
        if ($Headless) {
            $threeDRuntimeArguments.Headless = $true
        }
        & $threeDRuntimeLauncher @threeDRuntimeArguments
        $threeDRuntimeLauncherSucceeded = $?
        $threeDRuntimeExitCode = $LASTEXITCODE
        if (-not $threeDRuntimeLauncherSucceeded -or ($null -ne $threeDRuntimeExitCode -and $threeDRuntimeExitCode -ne 0)) {
            throw "Three-dimensional renderer launcher returned exit code $threeDRuntimeExitCode"
        }
        Write-Host "[ready] Three-dimensional renderer: http://${HostAddress}:$ThreeDRuntimePort"
    }
    catch {
        Write-Warning "Independent three-dimensional renderer is unavailable. The primary platform remains available at $frontendUrl. $($_.Exception.Message)"
    }
}

if (-not $NoBrowser) {
    Start-Process $frontendUrl
}
exit 0
