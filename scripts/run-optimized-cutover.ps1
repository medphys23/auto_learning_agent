param(
    [switch]$Apply,
    [switch]$ConfirmGlobalWrite,
    [switch]$AllowDirty,
    [switch]$SkipDependencyAudit,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing repo-local interpreter: $Python"
}

$ArgsList = @("scripts\run_optimized_cutover.py")
if ($Apply) { $ArgsList += "--apply" }
if ($ConfirmGlobalWrite) { $ArgsList += "--confirm-global-write" }
if ($AllowDirty) { $ArgsList += "--allow-dirty" }
if ($SkipDependencyAudit) { $ArgsList += "--skip-dependency-audit" }
if ($Verbose) { $ArgsList += "--verbose" }

Push-Location $Root
try {
    & $Python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
