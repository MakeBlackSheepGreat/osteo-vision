param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5174,
    [string]$HostAddress = "127.0.0.1",
    [string]$CondaEnv = "osteo-vision",
    [string]$InferenceConfig = "configs/inference/osteo_vision.yml",
    [switch]$StrictCompetition,
    [switch]$PreflightOnly,
    [switch]$NoInstall,
    [switch]$NoBrowser
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
        [string]$WorkingDirectory
    )

    $wrapped = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location -LiteralPath '$WorkingDirectory'
$Command
"@

    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $wrapped
    ) -WorkingDirectory $WorkingDirectory
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$frontendDir = Join-Path $repoRoot "frontend"
$backendEntry = Join-Path $repoRoot "backend\src\main.py"
$runtimeCheck = Join-Path $repoRoot "tools\check_runtime_readiness.py"
if ($StrictCompetition) {
    $InferenceConfig = "configs/inference/osteo_vision_competition_strict.yml"
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
    throw "Missing backend/src/main.py under $repoRoot"
}
if (-not (Test-Path -LiteralPath $runtimeCheck)) {
    throw "Missing tools/check_runtime_readiness.py under $repoRoot"
}

$projectPython = Resolve-CondaEnvironmentPython -EnvironmentName $CondaEnv
if (-not $projectPython) {
    throw "Python for conda environment '$CondaEnv' was not found. Expected the dedicated osteo-vision environment."
}
$preflightArguments = @($runtimeCheck, "--config", $inferenceConfigPath)
if ($StrictCompetition) {
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

$allowedOrigins = "http://localhost:$FrontendPort,http://${HostAddress}:$FrontendPort"
$apiUrl = "http://${HostAddress}:$BackendPort"
$frontendUrl = "http://${HostAddress}:$FrontendPort"
$expectStrictRuntime = if ($StrictCompetition) { "true" } else { "false" }
$competitionArtifactRoot = Join-Path $repoRoot "artifacts\platform_competition"
$competitionCaseStore = Join-Path $competitionArtifactRoot "cases.sqlite"
$competitionJobStore = Join-Path $competitionArtifactRoot "jobs\jobs.json"

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
    if ($StrictCompetition -and [System.IO.Path]::GetFullPath([string]$existingReady.storage) -ne [System.IO.Path]::GetFullPath($competitionCaseStore)) {
        throw "Existing strict backend does not use the isolated competition case store. Stop it before starting."
    }
    $liveFrameRoute = "/cases/{case_id}/live-frames"
    $existingRoutes = @($existingOpenApi.paths.psobject.Properties.Name)
    if ($existingRoutes -notcontains $liveFrameRoute) {
        throw "Existing backend on port $BackendPort is an older build and lacks $liveFrameRoute. Stop it, then restart with this launcher."
    }
    Write-Host "[backend] Reusing verified backend profile $($preflight.runtime_profile) on port $BackendPort."
}
else {
    $backendRun = "& '$projectPython' -m backend.src.main"
    $backendCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_FRONTEND_PORT = '$FrontendPort'
`$env:OSTEO_ALLOWED_ORIGINS = '$allowedOrigins'
`$env:OSTEO_INFERENCE_CONFIG = '$inferenceConfigPath'
$(if ($StrictCompetition) { "`$env:OSTEO_ARTIFACT_ROOT = '$competitionArtifactRoot'`n`$env:OSTEO_CASE_STORE_PATH = '$competitionCaseStore'`n`$env:OSTEO_JOB_STORE_PATH = '$competitionJobStore'" })
$backendRun
"@
    Start-DevWindow -Title "Osteo Vision Backend :$BackendPort" -Command $backendCommand -WorkingDirectory $repoRoot
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
            elseif ($StrictCompetition -and [System.IO.Path]::GetFullPath([string]$ready.storage) -ne [System.IO.Path]::GetFullPath($competitionCaseStore)) {
                $backendFailure = "Strict backend storage does not match $competitionCaseStore."
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
`$env:VITE_OSTEO_EXPECT_STRICT_RUNTIME = '$expectStrictRuntime'
npm --prefix "$frontendDir" run dev -- --host $HostAddress --port $FrontendPort --strictPort
"@
    Start-DevWindow -Title "Osteo Vision Frontend :$FrontendPort" -Command $frontendCommand -WorkingDirectory $repoRoot
}

Write-Host "[wait] Waiting for frontend at $frontendUrl ..."
for ($i = 0; $i -lt 40; $i++) {
    if (Test-TcpPort -Address $HostAddress -Port $FrontendPort) {
        Write-Host "[ready] Frontend: $frontendUrl"
        if (-not $NoBrowser) {
            Start-Process $frontendUrl
        }
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Host "[warn] Frontend did not respond within 40 seconds. Check the frontend terminal window."
Write-Host "[info] Expected frontend URL: $frontendUrl"
exit 1
