param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName Microsoft.Office.Interop.Word
$word = $null
$results = @()
$fatalError = $null

try {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.ScreenUpdating = $false
    $word.AutomationSecurity = 3

    foreach ($job in @($manifest)) {
        $document = $null
        $stage = "open document"
        try {
            $source = [string]$job.source
            $destination = [string]$job.destination
            $document = $word.Documents.Open($source, $false, $true, $false)
            $stage = "count pages"
            $pageCount = $document.ComputeStatistics(
                [Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticPages
            )
            $stage = "export PDF"
            $document.ExportAsFixedFormat(
                $destination,
                [Microsoft.Office.Interop.Word.WdExportFormat]::wdExportFormatPDF
            )
            $results += [pscustomobject]@{
                key = [string]$job.key
                success = $true
                error = $null
                page_count = [int]$pageCount
            }
        }
        catch {
            if (Test-Path -LiteralPath ([string]$job.destination)) {
                Remove-Item -LiteralPath ([string]$job.destination) -Force
            }
            $results += [pscustomobject]@{
                key = [string]$job.key
                success = $false
                error = "$stage`: $($_.Exception.Message)"
                page_count = $null
            }
        }
        finally {
            if ($null -ne $document) {
                try {
                    $document.Saved = $true
                    $document.Close()
                }
                catch {
                }
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
                $document = $null
            }
        }
    }
}
catch {
    $fatalError = $_.Exception.Message
}
finally {
    if ($null -ne $word) {
        try {
            $word.Quit()
        }
        catch {
        }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
        $word = $null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

[pscustomobject]@{
    fatal_error = $fatalError
    results = $results
} | ConvertTo-Json -Depth 5 -Compress

if ($null -ne $fatalError) {
    exit 1
}
