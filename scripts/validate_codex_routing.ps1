param(
    [switch]$RuntimeSmoke
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Push-Location $repoRoot
try {
    $args = @("scripts\validate_codex_routing.py")
    if ($RuntimeSmoke) {
        $args += "--runtime-smoke"
    }
    & $python @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
