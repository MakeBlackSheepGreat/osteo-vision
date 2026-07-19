@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_platform.ps1" -StrictCompetition %*
endlocal
