$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$source = Join-Path $PSScriptRoot "osteo_vision_final_technical_solution_20260711_zh.md"
$reference = Join-Path $root "research\reports\planning\osteo_vision_competition_gap_solutions_archive_20260710_zh.docx"
$docx = Join-Path $PSScriptRoot "osteo_vision_final_technical_solution_20260711_zh.docx"
$pdf = Join-Path $PSScriptRoot "osteo_vision_final_technical_solution_20260711_zh.pdf"

$pandoc = (Get-Command pandoc.exe -ErrorAction Stop).Source
& $pandoc $source `
    --from=gfm `
    --standalone `
    --toc `
    --toc-depth=3 `
    --reference-doc=$reference `
    --output=$docx
if ($LASTEXITCODE -ne 0) {
    throw "Pandoc document generation failed with exit code $LASTEXITCODE."
}

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docx)
    foreach ($toc in $document.TablesOfContents) {
        $toc.Update()
    }
    $document.Fields.Update() | Out-Null
    $document.Save()
    $document.ExportAsFixedFormat($pdf, 17)
}
finally {
    if ($null -ne $document) {
        try {
            $document.Close($false)
        }
        catch {
        }
    }
    if ($null -ne $word) {
        try {
            $word.Quit()
        }
        catch {
        }
    }
}

if (-not (Test-Path -LiteralPath $docx) -or -not (Test-Path -LiteralPath $pdf)) {
    throw "Submission DOCX or PDF output is missing."
}

Write-Output $docx
Write-Output $pdf
