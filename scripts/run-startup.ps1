param(
    [switch]$ApplyGlobal,
    [switch]$ConfirmGlobalWrite,
    [switch]$ApplyRepoHints,
    [switch]$ConfirmRepoWrite,
    [switch]$Strict,
    [switch]$SkipGraphify,
    [switch]$SkipDependencyAudit,
    [switch]$RuntimeSmoke,
    [switch]$SkipRuntimeSmoke,
    [switch]$ForceParentModel,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$ArgsList = @("scripts\run_startup.py")
if ($ApplyGlobal) { $ArgsList += "--apply-global" }
if ($ConfirmGlobalWrite) { $ArgsList += "--confirm-global-write" }
if ($ApplyRepoHints) { $ArgsList += "--apply-repo-hints" }
if ($ConfirmRepoWrite) { $ArgsList += "--confirm-repo-write" }
if ($Strict) { $ArgsList += "--strict" }
if ($SkipGraphify) { $ArgsList += "--skip-graphify" }
if ($SkipDependencyAudit) { $ArgsList += "--skip-dependency-audit" }
if ($RuntimeSmoke) { $ArgsList += "--runtime-smoke" }
if ($SkipRuntimeSmoke) { $ArgsList += "--skip-runtime-smoke" }
if ($ForceParentModel) { $ArgsList += "--force-parent-model" }
if ($Verbose) { $ArgsList += "--verbose" }

Push-Location $Root
try {
    & $Python @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
