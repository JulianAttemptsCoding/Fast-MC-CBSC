param(
    [string]$SourcePrefix = "",
    [int]$Port = 3000,
    [int]$SyncIntervalSeconds = 300
)

$ErrorActionPreference = "Stop"
if ($SyncIntervalSeconds -lt 300) {
    throw "SyncIntervalSeconds must be at least 300."
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$dashboardRoot = Join-Path $repositoryRoot "dashboard"
$dataRoot = Join-Path $dashboardRoot "public\data"
$syncScript = Join-Path $PSScriptRoot "sync_vertex_visualizations.py"
$syncLog = Join-Path $repositoryRoot "dashboard\vertex_sync.log"
$syncErrorLog = Join-Path $repositoryRoot "dashboard\vertex_sync_error.log"

if ($SourcePrefix) {
    $python = (Get-Command python -ErrorAction Stop).Source
    $arguments = @(
        "-u",
        "`"$syncScript`"",
        "--source",
        $SourcePrefix,
        "--destination",
        "`"$dataRoot`"",
        "--watch",
        "--interval-seconds",
        $SyncIntervalSeconds
    )
    Start-Process `
        -FilePath $python `
        -ArgumentList $arguments `
        -WorkingDirectory $repositoryRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $syncLog `
        -RedirectStandardError $syncErrorLog
}

Set-Location -LiteralPath $dashboardRoot
npm run dev -- --port $Port
