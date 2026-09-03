param(
    [string]$ReleaseTag = "v0.3.0-rc.2-r28",
    [string]$AssetBaseName = "Osteo-Vision-Competition-Disc-win32-x64-20260831-r28",
    [string]$Destination = "",
    [ValidateRange(1, 32)]
    [int]$Concurrency = 4,
    [ValidateRange(8, 512)]
    [int]$ChunkMiB = 32
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $repoRoot "artifacts\release\competition-disc"
}
$destinationRoot = (New-Item -ItemType Directory -Force -Path $Destination).FullName
$partsRoot = Join-Path $destinationRoot ".parts"
$baseUrl = "https://github.com/MakeBlackSheepGreat/osteo-vision/releases/download/$ReleaseTag"
$curl = (Get-Command curl.exe -ErrorAction Stop).Source
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path -LiteralPath $sevenZip -PathType Leaf)) {
    throw "7-Zip is required to extract the multi-volume archive: $sevenZip"
}

function Get-RemoteLength {
    param([Parameter(Mandatory)][string]$Url)

    $headers = & $curl -L -sS -I $Url 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect remote asset: $Url`n$($headers -join "`n")"
    }
    $match = $headers | Select-String -Pattern "^Content-Length:\s*(\d+)" -CaseSensitive:$false | Select-Object -Last 1
    if (-not $match) {
        throw "Remote asset length is unavailable: $Url"
    }
    return [int64]$match.Matches[0].Groups[1].Value
}

function Get-Sha256Hex {
    param([Parameter(Mandatory)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Download-Asset {
    param(
        [Parameter(Mandatory)][string]$FileName,
        [Parameter(Mandatory)][int64]$Length,
        [Parameter(Mandatory)][string]$ExpectedHash
    )

    $assetPath = Join-Path $destinationRoot $FileName
    $assetPath = [IO.Path]::GetFullPath($assetPath)
    $partialPath = "$assetPath.partial"
    if ($FileName -eq "SHA256SUMS.txt") {
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
            & $curl -L --fail --retry 8 --retry-delay 2 --silent --show-error --output $assetPath "$baseUrl/$FileName"
            if ($LASTEXITCODE -ne 0) { throw "Download failed: $FileName" }
        }
        return $assetPath
    }

    $safePartName = $FileName -replace "[^A-Za-z0-9._-]", "_"
    $partDir = Join-Path $partsRoot $safePartName
    $legacyPartDir = Join-Path $partsRoot ([IO.Path]::GetFileNameWithoutExtension($FileName))
    if (-not (Test-Path -LiteralPath $partDir -PathType Container) -and $FileName.EndsWith(".7z.001") -and (Test-Path -LiteralPath $legacyPartDir -PathType Container)) {
        Move-Item -LiteralPath $legacyPartDir -Destination $partDir
    }
    New-Item -ItemType Directory -Force -Path $partDir | Out-Null
    $chunkBytes = [int64]$ChunkMiB * 1MB
    $partCount = [int][math]::Ceiling($Length / [double]$chunkBytes)
    $jobs = @{}

    for ($index = 0; $index -lt $partCount; $index++) {
        $start = [int64]$index * $chunkBytes
        $end = [math]::Min($Length - 1, $start + $chunkBytes - 1)
        $expectedPartLength = $end - $start + 1
        $partPath = Join-Path $partDir ("part_{0:D5}.bin" -f $index)
        if ((Test-Path -LiteralPath $partPath -PathType Leaf) -and ((Get-Item -LiteralPath $partPath).Length -eq $expectedPartLength)) {
            continue
        }
        Remove-Item -LiteralPath $partPath -Force -ErrorAction SilentlyContinue
        while ($jobs.Count -ge $Concurrency) {
            foreach ($key in @($jobs.Keys)) {
                $entry = $jobs[$key]
                $process = $entry.Process
                if ($process.HasExited) {
                    if ($process.ExitCode -ne 0) { throw "Range download failed for $FileName part $key (exit $($process.ExitCode))." }
                    $jobPath = $entry.PartPath
                    $jobLength = (Get-Item -LiteralPath $jobPath).Length
                    $jobExpected = $entry.ExpectedLength
                    if ($jobLength -ne $jobExpected) { throw "Range length mismatch for $FileName part ${key}: $jobLength / $jobExpected." }
                    $jobs.Remove($key)
                }
            }
            if ($jobs.Count -ge $Concurrency) { Start-Sleep -Milliseconds 400 }
        }
        $argumentList = @(
            "-L", "--fail", "--retry", "10", "--retry-all-errors", "--retry-delay", "2", "--connect-timeout", "30", "--silent", "--show-error",
            "--range", "$start-$end", "--output", $partPath, "$baseUrl/$FileName"
        )
        $process = Start-Process -FilePath $curl -ArgumentList $argumentList -WindowStyle Hidden -PassThru
        $jobs[$index] = [pscustomobject]@{
            Process = $process
            PartPath = $partPath
            ExpectedLength = $expectedPartLength
        }
    }

    while ($jobs.Count -gt 0) {
        foreach ($key in @($jobs.Keys)) {
            $entry = $jobs[$key]
            $process = $entry.Process
            if (-not $process.HasExited) { continue }
            if ($process.ExitCode -ne 0) { throw "Range download failed for $FileName part $key (exit $($process.ExitCode))." }
            $partPath = $entry.PartPath
            $partLength = (Get-Item -LiteralPath $partPath).Length
            if ($partLength -ne $entry.ExpectedLength) { throw "Range length mismatch for $FileName part ${key}: $partLength / $($entry.ExpectedLength)." }
            $jobs.Remove($key)
        }
        if ($jobs.Count -gt 0) { Start-Sleep -Milliseconds 400 }
    }

    Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
    $output = [IO.File]::Open($partialPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        for ($index = 0; $index -lt $partCount; $index++) {
            $partPath = Join-Path $partDir ("part_{0:D5}.bin" -f $index)
            $input = [IO.File]::OpenRead($partPath)
            try { $input.CopyTo($output) } finally { $input.Dispose() }
        }
    }
    finally { $output.Dispose() }
    if ((Get-Item -LiteralPath $partialPath).Length -ne $Length) {
        throw "Reassembled length mismatch for $FileName."
    }
    Move-Item -LiteralPath $partialPath -Destination $assetPath -Force
    if ((Get-Sha256Hex -Path $assetPath) -ne $ExpectedHash) {
        throw "SHA256 mismatch for $FileName."
    }
    return $assetPath
}

$checksumPath = Join-Path $destinationRoot "SHA256SUMS.txt"
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
    & $curl -L --fail --retry 8 --retry-delay 2 --silent --show-error --output $checksumPath "$baseUrl/SHA256SUMS.txt"
    if ($LASTEXITCODE -ne 0) { throw "Unable to download SHA256SUMS.txt" }
}
$checksumLines = Get-Content -LiteralPath $checksumPath -Encoding UTF8
$assets = foreach ($suffix in @(".7z.001", ".7z.002")) {
    $name = "$AssetBaseName$suffix"
    $line = $checksumLines | Where-Object { $_ -match [regex]::Escape($name) } | Select-Object -First 1
    if (-not $line) { throw "Checksum entry is missing for $name" }
    $hash = ($line -split "\s+")[0].ToLowerInvariant()
    [ordered]@{ Name = $name; Url = "$baseUrl/$name"; Hash = $hash }
}

foreach ($asset in $assets) {
    $length = Get-RemoteLength -Url $asset.Url
    Write-Host "Restoring $($asset.Name) ($length bytes)"
    Download-Asset -FileName $asset.Name -Length $length -ExpectedHash $asset.Hash | Out-Null
}

$archivePath = Join-Path $destinationRoot $assets[0].Name
$packageMarker = Join-Path $destinationRoot "$AssetBaseName"
if (-not (Test-Path -LiteralPath $packageMarker -PathType Container)) {
    & $sevenZip x $archivePath "-o$destinationRoot" -y
    if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed." }
}
if (-not (Test-Path -LiteralPath $packageMarker -PathType Container)) {
    throw "Extracted r28 package directory is missing: $packageMarker"
}
Write-Host "r28 release restored at $packageMarker"
Write-Host "Run $packageMarker\verify_release.ps1 to verify the extracted package."
