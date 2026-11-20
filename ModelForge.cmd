@echo off
cd /d "%~dp0"
if exist "%~dp0dist\app\FORGE.exe" (
    start "" "%~dp0dist\app\FORGE.exe"
    exit /b
)
set "PATH=C:\Projects\Structure;%PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ModelForge.ps1"
if errorlevel 1 pause
