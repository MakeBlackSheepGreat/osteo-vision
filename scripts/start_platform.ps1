param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5174,
    [string]$HostAddress = "127.0.0.1",
    [string]$CondaEnv = "osteo-vision",
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

if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "package.json"))) {
    throw "Missing frontend/package.json under $repoRoot"
}
if (-not (Test-Path -LiteralPath $backendEntry)) {
    throw "Missing backend/src/main.py under $repoRoot"
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

$backendRunning = Test-TcpPort -Address $HostAddress -Port $BackendPort
$frontendRunning = Test-TcpPort -Address $HostAddress -Port $FrontendPort

if ($backendRunning) {
    Write-Host "[backend] Port $BackendPort is already in use. Reusing existing service."
}
else {
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda -and $CondaEnv) {
        $backendRun = "conda run -n `"$CondaEnv`" python -m backend.src.main"
    }
    else {
        Write-Host "[backend] Conda not found or disabled. Falling back to python on PATH."
        $backendRun = "python -m backend.src.main"
    }
    $backendCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_FRONTEND_PORT = '$FrontendPort'
`$env:OSTEO_ALLOWED_ORIGINS = '$allowedOrigins'
$backendRun
"@
    Start-DevWindow -Title "Osteo Vision Backend :$BackendPort" -Command $backendCommand -WorkingDirectory $repoRoot
}

if ($frontendRunning) {
    Write-Host "[frontend] Port $FrontendPort is already in use. Reusing existing service."
}
else {
    $frontendCommand = @"
`$env:OSTEO_BACKEND_PORT = '$BackendPort'
`$env:OSTEO_FRONTEND_PORT = '$FrontendPort'
`$env:VITE_OSTEO_API_URL = '$apiUrl'
npm --prefix "$frontendDir" run dev -- --host $HostAddress --port $FrontendPort --strictPort
"@
    Start-DevWindow -Title "Osteo Vision Frontend :$FrontendPort" -Command $frontendCommand -WorkingDirectory $repoRoot
}

Write-Host "[wait] Waiting for frontend at $frontendUrl ..."
for ($i = 0; $i -lt 40; $i++) {
    if (Test-TcpPort -Address $HostAddress -Port $FrontendPort) {
        Write-Host "[ready] Frontend: $frontendUrl"
        Write-Host "[ready] Backend:  $apiUrl"
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
