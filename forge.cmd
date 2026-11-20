@echo off
setlocal
set "PATH=C:\Projects\Structure;C:\Projects\Img;C:\Projects\Background;%PATH%"
set "JOBNAME=forge_%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%%time:~9,2%"
set "JOBNAME=%JOBNAME: =0%"
echo %* | findstr /c:"--name" >nul
if not errorlevel 1 ("C:\Users\Administrator\unirig\python311-rocm\python.exe" "%~dp0model_forge_local\forge_pipeline.py" %*) else ("C:\Users\Administrator\unirig\python311-rocm\python.exe" "%~dp0model_forge_local\forge_pipeline.py" --name "%JOBNAME%" %*)
endlocal
