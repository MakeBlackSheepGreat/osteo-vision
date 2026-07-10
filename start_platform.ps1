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

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$implementation = Join-Path $repoRoot "scripts\start_platform.ps1"

if (-not (Test-Path -LiteralPath $implementation)) {
    throw "Missing scripts\start_platform.ps1 under $repoRoot"
}

$arguments = @{
    BackendPort = $BackendPort
    FrontendPort = $FrontendPort
    HostAddress = $HostAddress
    CondaEnv = $CondaEnv
}
if ($NoInstall) {
    $arguments.NoInstall = $true
}
if ($NoBrowser) {
    $arguments.NoBrowser = $true
}

& $implementation @arguments
