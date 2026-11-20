@echo off
setlocal
set "FORGE_TARGET=%~dp0dist\app\FORGE.exe"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $exe=Get-Item -LiteralPath $env:FORGE_TARGET; $menu=[Environment]::GetFolderPath('Programs'); $path=Join-Path $menu 'FORGE.lnk'; $shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut($path); $link.TargetPath=$exe.FullName; $link.WorkingDirectory=$exe.DirectoryName; $link.IconLocation=$exe.FullName+',0'; $link.Description='FORGE 3D model builder'; $link.Save(); if($shell.CreateShortcut($path).TargetPath -ne $exe.FullName){throw 'Shortcut verification failed'}; Write-Host 'FORGE added. Open Start and search for FORGE.'"
if errorlevel 1 pause
