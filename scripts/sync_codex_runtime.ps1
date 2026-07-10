param(
    [switch]$WhatIf,
    [switch]$Apply,
    [switch]$ConfirmGlobalWrite,
    [string]$CodexCli = "codex",
    [string]$Profile = "optimized"
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [string]$Level,
        [string]$Phase,
        [string]$Message
    )
    $stamp = (Get-Date).ToString("o")
    Write-Output "$stamp [$Level] [$Phase] $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Push-Location $repoRoot
try {
    Write-Log "INFO" "SYNC" "Source validated"
    & $python scripts\validate_codex_config.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python scripts\validate_codex_routing.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($WhatIf -or -not $Apply) {
        Write-Log "INFO" "SYNC" "Preview publication"
        & $python scripts\publish_global_rules.py --preview --profile $Profile
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Log "INFO" "SUMMARY" "created=0 updated=0 unchanged=0 failed=0"
        exit 0
    }

    if (-not $ConfirmGlobalWrite) {
        Write-Log "ERROR" "SYNC" "Apply requires -ConfirmGlobalWrite"
        exit 2
    }

    Write-Log "INFO" "SMOKE" "Validating GPT-5.6 models before apply"
    & $python scripts\validate_codex_routing.py --runtime-smoke --codex-cli $CodexCli
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Log "INFO" "SYNC" "Applying guarded publication"
    & $python scripts\publish_global_rules.py --apply --confirm-global-write --profile $Profile
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Log "INFO" "SUMMARY" "created=see-publication-report updated=see-publication-report unchanged=see-publication-report failed=0"
}
finally {
    Pop-Location
}
