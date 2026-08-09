param(
    [switch]$Yes,
    [switch]$SkipRuntimeSmoke = $true,
    [switch]$RuntimeSmoke,
    [switch]$ForceParentModel,
    [switch]$SkipGraphify,
    [switch]$Strict,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $Root

Write-Host ""
Write-Host "auto_learning_agent APPLY-EVERYTHING" -ForegroundColor Cyan
Write-Host "Repo: $Root"
Write-Host ""
Write-Host "This will:"
Write-Host "  1. Validate Codex config"
Write-Host "  2. Run discover -> Graphify cycle -> harvest -> optimized synthesis"
Write-Host "  3. APPLY optimized globals to ~/.codex and ~/.cursor (with backups)"
Write-Host "  4. APPLY orchestrator retrieval hints into registered repos"
Write-Host "  5. APPLY Graphify policy files (.graphifyignore, AGENTS block, Cursor rule)"
Write-Host ""
Write-Host "Not included: Neo4j/media/URL Graphify features; parent-model switch unless -RuntimeSmoke."
Write-Host ""

if (-not $Yes) {
    $answer = Read-Host "Type APPLY to continue (anything else aborts)"
    if ($answer -ne "APPLY") {
        Write-Host "Aborted. No files were changed by this launcher."
        exit 2
    }
}

$startup = Join-Path $Root "scripts\run-startup.ps1"
$startupArgs = @(
    "-ApplyGlobal",
    "-ConfirmGlobalWrite",
    "-ApplyRepoHints",
    "-ConfirmRepoWrite"
)
if ($Strict) { $startupArgs += "-Strict" }
if ($SkipGraphify) { $startupArgs += "-SkipGraphify" }
# Always request verbose startup so child Graphify/harvest lines stream live.
$startupArgs += "-Verbose"
if ($ForceParentModel) { $startupArgs += "-ForceParentModel" }
if ($RuntimeSmoke) {
    $startupArgs += "-RuntimeSmoke"
} elseif ($SkipRuntimeSmoke) {
    $startupArgs += "-SkipRuntimeSmoke"
}

Write-Host ""
Write-Host "==> Startup apply (globals + repo hints)" -ForegroundColor Yellow
& $startup @startupArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: startup apply failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host ""
Write-Host "==> Graphify integration apply" -ForegroundColor Yellow
& $Python "scripts\propagate_graphify_integration.py" "--apply" "--confirm-repo-write"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Graphify propagation failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "APPLY-EVERYTHING completed." -ForegroundColor Green
Write-Host "Reports: reports\optimized-knowledge-cycle-summary.md, reports\optimized-cutover-readiness.md,"
Write-Host "         reports\publication-applied.md (or publication-preview), reports\graphify-propagation-preview.md"
exit 0
