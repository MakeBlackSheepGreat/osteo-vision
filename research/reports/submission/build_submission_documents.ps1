[CmdletBinding()]
param(
    [string]$SourceMarkdown,
    [string]$OutputDocx,
    [string]$OutputPdf,
    [switch]$KeepWordVisible
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = (Resolve-Path (Join-Path $scriptDirectory "..\..\..")).Path

if (-not $SourceMarkdown) {
    $SourceMarkdown = Join-Path $scriptDirectory "osteo_vision_technical_solution_20260719_zh.md"
}
if (-not $OutputDocx) {
    $OutputDocx = Join-Path $scriptDirectory "osteo_vision_technical_solution_20260719_zh.docx"
}
if (-not $OutputPdf) {
    $OutputPdf = Join-Path $scriptDirectory "osteo_vision_technical_solution_20260719_zh.pdf"
}

$SourceMarkdown = [System.IO.Path]::GetFullPath($SourceMarkdown)
$OutputDocx = [System.IO.Path]::GetFullPath($OutputDocx)
$OutputPdf = [System.IO.Path]::GetFullPath($OutputPdf)
$nodeBuilder = Join-Path $scriptDirectory "build_submission_documents.mjs"

function Repair-WordStyleOrder {
    param([Parameter(Mandatory = $true)][string]$DocxPath)

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $archive = $null
    $reader = $null
    $writer = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::Open(
            $DocxPath,
            [System.IO.Compression.ZipArchiveMode]::Update
        )
        $entry = $archive.GetEntry("word/styles.xml")
        if (-not $entry) {
            throw "word/styles.xml is missing from the generated DOCX."
        }

        $reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8, $true)
        $stylesXmlText = $reader.ReadToEnd()
        $reader.Close()
        $reader = $null

        $stylesXml = New-Object System.Xml.XmlDocument
        $stylesXml.PreserveWhitespace = $true
        $stylesXml.LoadXml($stylesXmlText)
        $namespaceManager = New-Object System.Xml.XmlNamespaceManager($stylesXml.NameTable)
        $namespaceManager.AddNamespace(
            "w",
            "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        )

        $styles = $stylesXml.SelectNodes("/w:styles/w:style", $namespaceManager)
        foreach ($style in $styles) {
            $priority = $style.SelectSingleNode("./w:uiPriority", $namespaceManager)
            if (-not $priority) {
                continue
            }

            $anchor = $style.SelectSingleNode(
                "./w:semiHidden | ./w:unhideWhenUsed | ./w:qFormat | ./w:locked | " +
                "./w:personal | ./w:personalCompose | ./w:personalReply | ./w:rsid | " +
                "./w:pPr | ./w:rPr | ./w:tblPr",
                $namespaceManager
            )
            if ($anchor -and $priority.NextSibling -ne $anchor) {
                [void]$style.RemoveChild($priority)
                [void]$style.InsertBefore($priority, $anchor)
            }
        }

        $entry.Delete()
        $updatedEntry = $archive.CreateEntry(
            "word/styles.xml",
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        $settings = New-Object System.Xml.XmlWriterSettings
        $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
        $settings.Indent = $false
        $settings.OmitXmlDeclaration = $false
        $writer = [System.Xml.XmlWriter]::Create($updatedEntry.Open(), $settings)
        $stylesXml.Save($writer)
        $writer.Flush()
    }
    finally {
        if ($reader) {
            $reader.Dispose()
        }
        if ($writer) {
            $writer.Dispose()
        }
        if ($archive) {
            $archive.Dispose()
        }
    }
}

if (-not (Test-Path -LiteralPath $SourceMarkdown -PathType Leaf)) {
    throw "Markdown source file not found: $SourceMarkdown"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js was not found. Install the runtime declared by the root package.json."
}
if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot "node_modules\docx"))) {
    throw "The docx dependency is missing. Run npm install from the repository root."
}
if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot "node_modules\marked"))) {
    throw "The marked dependency is missing. Run npm install from the repository root."
}

& node $nodeBuilder $SourceMarkdown $OutputDocx
if ($LASTEXITCODE -ne 0) {
    throw "The Node.js DOCX build failed with exit code $LASTEXITCODE."
}

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = [bool]$KeepWordVisible
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($OutputDocx, $false, $false)

    foreach ($tableOfContents in $document.TablesOfContents) {
        $tableOfContents.Update()
    }
    $document.Fields.Update() | Out-Null
    foreach ($section in $document.Sections) {
        foreach ($header in $section.Headers) {
            $header.Range.Fields.Update() | Out-Null
        }
        foreach ($footer in $section.Footers) {
            $footer.Range.Fields.Update() | Out-Null
        }
    }
    $document.Repaginate()
    $document.Save()

    $wdExportFormatPdf = 17
    $document.ExportAsFixedFormat($OutputPdf, $wdExportFormatPdf)
}
finally {
    if ($document) {
        try {
            $document.Close($false)
        }
        catch [System.Runtime.InteropServices.COMException] {
            Write-Verbose "The Word-compatible COM endpoint closed the document after export."
        }
        finally {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
        }
    }
    if ($word) {
        try {
            $word.Quit()
        }
        catch [System.Runtime.InteropServices.COMException] {
            Write-Verbose "The Word-compatible COM endpoint had already exited after export."
        }
        finally {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
        }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

# Word 2019 can move w:uiPriority behind w:qFormat when saving. Reorder those
# style children so the saved package remains valid against strict OOXML XSDs.
Repair-WordStyleOrder -DocxPath $OutputDocx

if (-not (Test-Path -LiteralPath $OutputPdf -PathType Leaf)) {
    throw "Microsoft Word did not generate the PDF: $OutputPdf"
}

Write-Host "Generated DOCX: $OutputDocx"
Write-Host "Generated PDF: $OutputPdf"
