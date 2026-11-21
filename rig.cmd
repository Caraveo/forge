@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0desktop\rig.ps1" %*
exit /b %errorlevel%
