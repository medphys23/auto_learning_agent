# Drag into PowerShell: type & then drop this file, then press Enter.
# Example: & "C:\Users\ppyxe\Documents\GitHub\auto_learning_agent\APPLY-EVERYTHING.ps1"
# Confirm with APPLY, or pass -Yes to skip the prompt.
& "$PSScriptRoot\scripts\apply-everything.ps1" @args
exit $LASTEXITCODE
