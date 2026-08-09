@echo off
setlocal
cd /d "%~dp0"

rem Drag this file into a PowerShell or CMD terminal and press Enter.
rem It resolves the repo root from its own location, so cwd does not matter.
rem Type APPLY at the prompt to confirm global and registered-repo writes.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply-everything.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXITCODE%
exit /b %EXITCODE%
