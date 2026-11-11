param(
    [string]$Root = "$env:SystemDrive\",
    [string]$Output = (Join-Path (Split-Path $PSScriptRoot -Parent) 'reports')
)
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Repository Python missing: $python" }
& $python (Join-Path $PSScriptRoot 'audit_windows_storage.py') --root $Root --output $Output
exit $LASTEXITCODE
