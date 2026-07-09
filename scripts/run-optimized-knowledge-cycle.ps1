param(
    [switch]$Strict,
    [switch]$ContinueOnDirty,
    [switch]$SkipDependencyAudit,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing repo-local interpreter: $Python"
}

$ArgsList = @("scripts\run_optimized_knowledge_cycle.py")
if ($Strict) { $ArgsList += "--strict" }
if ($ContinueOnDirty) { $ArgsList += "--continue-on-dirty" }
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
